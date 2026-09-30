[CmdletBinding()]
param(
    [int]$Port = 8765,
    [switch]$NoBrowser,
    [switch]$CheckOnly,
    [switch]$AllowEnvironmentRepair,
    [switch]$AllowDependencyInstall,
    [switch]$AllowWebBuild,
    [switch]$AllowDatabaseMigration,
    [switch]$AllowRepositoryPathRepair,
    [switch]$AllowStopExisting,
    [string]$DataDirectory = '',
    [string]$LogDirectory = ''
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$repoRoot = $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'

function Get-PortListener {
    param([int]$LocalPort)
    $listener = Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.OwningProcess -and $_.OwningProcess -ne $PID } |
        Select-Object -First 1
    if ($listener) { return $listener }

    # Get-NetTCPConnection can be denied for a standard Windows user. netstat's
    # numeric table exposes the same listener PID without requiring elevation.
    try {
        foreach ($line in & netstat.exe -ano -p tcp 2>$null) {
            if ($line -match "^\s*TCP\s+\S+:$LocalPort\s+\S+\s+LISTENING\s+(\d+)\s*$") {
                $owner = [int]$Matches[1]
                if ($owner -and $owner -ne $PID) {
                    return [pscustomobject]@{ OwningProcess = $owner }
                }
            }
        }
    } catch {}
    return $null
}

function Resolve-PortPolicy {
    param([bool]$Occupied, [bool]$IsIntentFlow, [bool]$AllowStop)
    if (-not $Occupied) { return 'AVAILABLE' }
    if (-not $IsIntentFlow) { return 'REFUSE_UNKNOWN' }
    if ($AllowStop) { return 'STOP_VERIFIED' }
    return 'USE_EXISTING'
}

function Stop-PreviousIntentFlow {
    param([int]$LocalPort, [string]$Url, [switch]$AllowStop)
    $listener = Get-PortListener $LocalPort
    if (-not $listener) { return $true }

    $isIntentFlow = $false
    try {
        $runningHealth = Invoke-RestMethod "$Url/api/health" -TimeoutSec 2
        $isIntentFlow = $runningHealth.application -eq 'IntentFlow'
    } catch {}

    if (-not $isIntentFlow) {
        try {
            $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
            $commandLine = [string]$processInfo.CommandLine
            $isIntentFlow = $commandLine -match 'uvicorn' -and $commandLine -match 'apps\.api\.main:app'
        } catch {}
    }

    $policy = Resolve-PortPolicy $true $isIntentFlow ([bool]$AllowStop)
    if ($policy -eq 'REFUSE_UNKNOWN') {
        throw "Port $LocalPort is used by another application. IntentFlow did not stop it. Choose another port with -Port."
    }
    if ($policy -eq 'USE_EXISTING') {
        Write-Host "IntentFlow is already running at $Url (PID $($listener.OwningProcess)). No process was stopped." -ForegroundColor Green
        return $false
    }

    Write-Host "Stopping previous IntentFlow process $($listener.OwningProcess)..." -ForegroundColor Yellow
    Stop-Process -Id $listener.OwningProcess -Force -ErrorAction Stop
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if (-not (Get-PortListener $LocalPort)) { return $true }
        Start-Sleep -Milliseconds 250
    }
    throw "Previous IntentFlow process stopped, but port $LocalPort was not released in time."
}

function Resolve-StartupAction {
    param([string]$Condition, [bool]$Allowed)
    if (-not $Condition) { return 'READY' }
    if ($Allowed) { return 'AUTHORIZED' }
    return 'BLOCKED'
}

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Executable (exit $LASTEXITCODE)" }
}

function Get-MajorMinorVersion {
    param([string]$Version)
    if ($Version -match '^(\d+)\.(\d+)') { return '{0}.{1}' -f $Matches[1], $Matches[2] }
    return $null
}

function Get-MachinePython {
    $exeList = New-Object System.Collections.ArrayList
    $cmd = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { [void]$exeList.Add(@{ Exe = $cmd.Source; Prefix = @('-3') }) }
    if ($env:SystemRoot) {
        $systemPy = Join-Path $env:SystemRoot 'py.exe'
        $known = @($exeList | ForEach-Object { $_.Exe })
        if ((Test-Path -LiteralPath $systemPy) -and ($known -notcontains $systemPy)) {
            [void]$exeList.Add(@{ Exe = $systemPy; Prefix = @('-3') })
        }
    }
    foreach ($name in @('python.exe', 'python3.exe')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source) { [void]$exeList.Add(@{ Exe = $cmd.Source; Prefix = @() }) }
    }
    foreach ($root in @($env:LOCALAPPDATA, $env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if (-not $root) { continue }
        foreach ($sub in @('Programs\Python', 'Python')) {
            $pythonRoot = Join-Path $root $sub
            if (-not (Test-Path -LiteralPath $pythonRoot)) { continue }
            Get-ChildItem -LiteralPath $pythonRoot -Directory -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -like 'Python3*' } |
                ForEach-Object {
                    $exe = Join-Path $_.FullName 'python.exe'
                    if (Test-Path -LiteralPath $exe) { [void]$exeList.Add(@{ Exe = $exe; Prefix = @() }) }
                }
        }
    }

    # The probe code deliberately contains no double quotes: PowerShell 5.1 escaping of
    # embedded quotes in native arguments is unreliable.
    $probeCode = 'import sys; print(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)'
    $diagnostics = New-Object System.Collections.ArrayList
    $fallback = $null
    foreach ($candidate in $exeList) {
        # NOTE: an inline @(...) is NOT a splat in PowerShell; it is passed as one array
        # argument. Only a variable (@name) splats, so build the argument list first.
        $probeArgs = @($candidate.Prefix) + @('-c', $probeCode)
        $previousEap = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $probe = & $candidate.Exe @probeArgs 2>$null
            $exitCode = $LASTEXITCODE
        } catch {
            $probe = $null
            $exitCode = 1
        } finally {
            $ErrorActionPreference = $previousEap
        }
        $version = ''
        if ($probe) {
            $parts = @(([string]$probe).Trim() -split '\s+')
            if ($parts.Count -ge 3) { $version = ($parts[0..2] -join '.') }
        }
        [void]$diagnostics.Add("$($candidate.Exe) [$(($candidate.Prefix) -join ' ')] exit=$exitCode version='$version'")
        if ($exitCode -eq 0 -and $version) {
            $entry = [pscustomobject]@{ Exe = $candidate.Exe; PrefixArgs = @($candidate.Prefix); Version = $version }
            if ([version]$version -ge [version]'3.11') { return $entry }
            if (-not $fallback) { $fallback = $entry }
        }
    }
    if ($fallback) { return $fallback }
    Write-Host 'Python detection failed. Probed candidates:' -ForegroundColor DarkYellow
    if ($diagnostics.Count -eq 0) {
        Write-Host '  (no python.exe / py.exe found on PATH or in standard install folders)' -ForegroundColor DarkYellow
    } else {
        foreach ($line in $diagnostics) { Write-Host "  $line" -ForegroundColor DarkYellow }
    }
    return $null
}

function Get-VenvPythonVersion {
    param([string]$VenvRoot)
    $configPath = Join-Path $VenvRoot 'pyvenv.cfg'
    if (-not (Test-Path -LiteralPath $configPath)) { return $null }
    foreach ($line in Get-Content -LiteralPath $configPath) {
        if ($line -match '^\s*version\s*=\s*(.+?)\s*$') { return $Matches[1] }
    }
    return $null
}

function Test-VenvRunnable {
    param([string]$VenvRoot)
    $exe = Join-Path $VenvRoot 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $exe)) { return $false }
    $previousEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $exe '-c' 'import sys' 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $previousEap
    }
}

function Show-EnvironmentAlert {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
    try {
        Start-Job -ScriptBlock {
            param($text)
            Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
            [void][System.Windows.Forms.MessageBox]::Show($text, 'IntentFlow Environment Check', 'OK', 'Warning')
        } -ArgumentList $Message | Out-Null
    } catch {}
}

function Repair-IntentFlowVenv {
    param([string]$RepoRoot, [pscustomobject]$MachinePython)
    Write-Host 'Repairing the .venv environment, please wait...' -ForegroundColor Yellow
    $venvRoot = Join-Path $RepoRoot '.venv'
    if (Test-Path -LiteralPath $venvRoot) { Remove-Item -LiteralPath $venvRoot -Recurse -Force }
    $createArgs = @($MachinePython.PrefixArgs) + @('-m', 'venv', $venvRoot)
    Invoke-Checked -Executable $MachinePython.Exe -Arguments $createArgs
    $venvPython = Join-Path $venvRoot 'Scripts\python.exe'
    Invoke-Checked $venvPython @('-m', 'pip', 'install', '-r', (Join-Path $RepoRoot 'requirements-v02.txt'))
    Write-Host '.venv environment repaired.' -ForegroundColor Green
}
function Invoke-IntentFlow {
    if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Port must be between 1024 and 65535' }
    if ($CheckOnly -and ($AllowEnvironmentRepair -or $AllowDependencyInstall -or $AllowWebBuild -or
            $AllowDatabaseMigration -or $AllowRepositoryPathRepair -or $AllowStopExisting)) {
        throw '-CheckOnly cannot be combined with switches that authorize changes; no action was taken.'
    }
    Push-Location $repoRoot
    try {
        Write-Host 'IntentFlow V3 - Software Engineering Workspace' -ForegroundColor Green
        $url = "http://127.0.0.1:$Port"
        # A second launch should reopen the healthy existing service immediately,
        # even if this checkout's local environment has since moved or become stale.
        if (-not $CheckOnly -and -not $AllowStopExisting) {
            if (-not (Stop-PreviousIntentFlow $Port $url)) {
                if (-not $NoBrowser) { Start-Process $url }
                return
            }
        }
        $machinePython = Get-MachinePython
        if (-not $machinePython) { throw 'No usable Python interpreter was found (see the detection diagnostics above). Install Python 3.11 or newer and retry.' }
        if ([version]$machinePython.Version -lt [version]'3.11') {
            throw "Machine Python $($machinePython.Version) is older than 3.11. Install Python 3.11 or newer and retry."
        }

        $venvRoot = Join-Path $repoRoot '.venv'
        $venvVersion = Get-VenvPythonVersion $venvRoot
        $machineMajorMinor = Get-MajorMinorVersion $machinePython.Version
        $venvMajorMinor = Get-MajorMinorVersion $venvVersion
        $mismatch = $null
        if (-not $venvVersion) {
            $mismatch = 'Project .venv environment was not found.'
        } elseif (-not (Test-VenvRunnable $venvRoot)) {
            $mismatch = "Project .venv cannot run: its base interpreter may have been removed or moved (.venv records Python $venvVersion)."
        } elseif ($venvMajorMinor -ne $machineMajorMinor) {
            $mismatch = "Project .venv does not match the machine Python: .venv = Python $venvVersion, machine = Python $($machinePython.Version)."
        }
        if ((Resolve-StartupAction $mismatch ([bool]$AllowEnvironmentRepair)) -eq 'BLOCKED') {
            throw "$mismatch Re-run with -AllowEnvironmentRepair and -AllowDependencyInstall only after reviewing the destructive environment rebuild."
        }
        if ($mismatch) {
            if (-not $AllowDependencyInstall) {
                throw 'Environment repair also requires -AllowDependencyInstall; no files were changed.'
            }
            Repair-IntentFlowVenv $repoRoot $machinePython
        }

        Invoke-Checked $python @('-B', '-c', 'import sys; assert sys.version_info >= (3,11)')
        $expectedVersion = (& $python -B -c 'from intentflow_core.release import VERSION; print(VERSION)').Trim()
        & $python -B -c "import importlib.util,sys; sys.exit(0 if all(importlib.util.find_spec(m) for m in ['fastapi','uvicorn','sqlalchemy','pydantic','jsonschema','yaml','httpx']) else 1)"
        $dependenciesMissing = $LASTEXITCODE -ne 0
        if ($dependenciesMissing) {
            if ((Resolve-StartupAction 'missing-dependencies' ([bool]$AllowDependencyInstall)) -eq 'BLOCKED') {
                throw 'Required Python dependencies are missing. No packages were installed; review and re-run with -AllowDependencyInstall.'
            }
            Invoke-Checked $python @('-m', 'pip', 'install', '-r', (Join-Path $repoRoot 'requirements-v02.txt'))
        }

        $dist = Join-Path $repoRoot 'apps\web\dist\index.html'
        $needsBuild = -not (Test-Path -LiteralPath $dist)
        if (-not $needsBuild) {
            $sourceFiles = @(Get-ChildItem -LiteralPath (Join-Path $repoRoot 'apps\web\src') -Recurse -File)
            $sourceFiles += Get-Item -LiteralPath (Join-Path $repoRoot 'apps\web\package.json')
            $latestSource = ($sourceFiles | Measure-Object -Property LastWriteTimeUtc -Maximum).Maximum
            $needsBuild = $latestSource -gt (Get-Item -LiteralPath $dist).LastWriteTimeUtc
        }
        if ((Resolve-StartupAction $(if ($needsBuild) { 'stale-build' } else { '' }) ([bool]$AllowWebBuild)) -eq 'BLOCKED') {
            throw 'The Web build is missing or stale. No build was started; review and re-run with -AllowWebBuild.'
        }
        if ($needsBuild) {
            $npm = Get-Command npm.cmd -ErrorAction Stop
            if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'apps\web\node_modules'))) {
                if (-not $AllowDependencyInstall) {
                    throw 'Web dependencies are missing. No packages were installed; -AllowWebBuild alone does not authorize installation.'
                }
            }
            Push-Location (Join-Path $repoRoot 'apps\web')
            try {
                if (-not (Test-Path -LiteralPath 'node_modules')) { Invoke-Checked $npm.Source @('ci') }
                Invoke-Checked $npm.Source @('run', 'build')
            } finally { Pop-Location }
        }

        if ($DataDirectory) { $env:INTENTFLOW_DATA_DIR = [System.IO.Path]::GetFullPath($DataDirectory) }
        if ($AllowDatabaseMigration) { $env:INTENTFLOW_ALLOW_DATABASE_MIGRATION = '1' } else { Remove-Item Env:INTENTFLOW_ALLOW_DATABASE_MIGRATION -ErrorAction SilentlyContinue }
        if ($AllowRepositoryPathRepair) {
            $env:INTENTFLOW_ALLOW_REPOSITORY_PATH_REPAIR = '1'
            $dataRoot = if ($DataDirectory) { [System.IO.Path]::GetFullPath($DataDirectory) } else { Join-Path $repoRoot '.intentflow-data' }
            $repairCode = 'from intentflow_core.projects import repair_repository_paths_in_data_root as repair; import sys; count = repair(sys.argv[1]); print(f''Repository paths repaired: {count}'')'
            Invoke-Checked $python @('-B', '-c', $repairCode, $dataRoot)
        } else {
            Remove-Item Env:INTENTFLOW_ALLOW_REPOSITORY_PATH_REPAIR -ErrorAction SilentlyContinue
        }

        $listener = Get-PortListener $Port
        if ($CheckOnly) {
            if ($listener) {
                Write-Host "Check complete: port $Port is currently occupied; no process was stopped." -ForegroundColor Yellow
            } else {
                Write-Host "Check complete: environment, dependencies and build are ready; port $Port is available." -ForegroundColor Green
            }
            return
        }
        if (-not (Stop-PreviousIntentFlow $Port $url -AllowStop:$AllowStopExisting)) {
            if (-not $NoBrowser) { Start-Process $url }
            return
        }

        $logDir = if ($LogDirectory) { [System.IO.Path]::GetFullPath($LogDirectory) } elseif ($DataDirectory) { [System.IO.Path]::GetFullPath($DataDirectory) } else { Join-Path $repoRoot '.intentflow-data' }
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        $health = $null
        $serverProcess = Start-Process -FilePath $python -WorkingDirectory $repoRoot -ArgumentList @('-B','-m','uvicorn','apps.api.main:app','--host','127.0.0.1','--port',"$Port") -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir "server-$Port.log") -RedirectStandardError (Join-Path $logDir "server-$Port-error.log")
        try {
            for ($attempt = 0; $attempt -lt 40; $attempt++) {
                if ($serverProcess.HasExited) { throw "API exited. See $logDir\server-$Port-error.log" }
                try { $health = Invoke-RestMethod "$url/api/health" -TimeoutSec 1 } catch {}
                if ($health -and $health.version -eq $expectedVersion) { break }
                Start-Sleep -Milliseconds 250
            }
            if (-not $health -or $health.version -ne $expectedVersion) { throw 'API did not become ready at the expected version. Inspect the server log.' }
            Write-Host "Ready: $url" -ForegroundColor Green
            Write-Host 'Keep this window open. Ctrl+C stops the server. Manual mode requires no API key.'
            if (-not $NoBrowser) { Start-Process $url }
            Wait-Process -Id $serverProcess.Id
        } finally {
            if (-not $serverProcess.HasExited) { Stop-Process -Id $serverProcess.Id }
        }
    } finally { Pop-Location }
}

if ($MyInvocation.InvocationName -ne '.') {
    try { Invoke-IntentFlow } catch {
        Write-Host $_.Exception.Message -ForegroundColor Red
        exit 1
    }
}
