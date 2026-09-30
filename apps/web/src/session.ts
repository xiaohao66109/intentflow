// Keep unfinished work in this browser tab; never store project credentials.
export function readSession<T>(key: string): T | null {
  try { return JSON.parse(sessionStorage.getItem(`intentflow:${key}`) || 'null') }
  catch { return null }
}
export function writeSession(key: string, value: unknown): boolean {
  try { sessionStorage.setItem(`intentflow:${key}`, JSON.stringify(value)); return true }
  catch { return false }
}
export function removeSession(key: string) {
  try { sessionStorage.removeItem(`intentflow:${key}`) } catch { /* Storage may be disabled. */ }
}
