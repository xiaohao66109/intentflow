export const SIDEBAR_COLLAPSED_KEY='intentflow:sidebar-collapsed'

type PreferenceStorage={
 getItem(key:string):string|null
 setItem(key:string,value:string):void
}

export function homeProjects<T>(projects:T[],showAll=false):T[]{
 return showAll?[...projects]:projects.slice(0,3)
}

export function readSidebarCollapsed(storage:PreferenceStorage|null):boolean{
 try{return storage?.getItem(SIDEBAR_COLLAPSED_KEY)==='true'}catch{return false}
}

export function writeSidebarCollapsed(storage:PreferenceStorage|null,collapsed:boolean):boolean{
 try{storage?.setItem(SIDEBAR_COLLAPSED_KEY,collapsed?'true':'false');return storage!==null}catch{return false}
}
