// One project journey. Version numbers are never navigation modes.
export const stages:Record<string,string>={
 'project-context':'项目理解','problem-evidence':'问题与证据','specification':'需求与原型',
 'engineering-intent':'工程设计','software-change':'代码变更','verification':'验证与复验',
 'runtime-outcome':'运行评估','next-change':'过程复盘',
}
export const areas:Record<string,string[]>={
 'specification':['rules','prototype','negotiate'], 'engineering-intent':['architecture'],
 'software-change':['change'], 'verification':['verify'], 'runtime-outcome':['outcome'], 'next-change':['training'],
}
export const stageForArea=(area:string)=>Object.keys(areas).find(key=>areas[key].includes(area))||'specification'
