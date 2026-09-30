<script setup lang="ts">
import {computed,onMounted,ref,watch,nextTick} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {decodeField,encodeField,needsValue,editableFields} from './forms'
import EngineeringWorkspace from './EngineeringWorkspace.vue'
import PropertyCasePanel from './PropertyCasePanel.vue'
import StudentCoach from './StudentCoach.vue'
import {studentLessons} from './studentGuide'
import {stages,areas,stageForArea} from './journey'
import {formatDateTime,stageGuidance} from './presentation'
import NumberEntries from './NumberEntries.vue'
import MarkdownContent from './MarkdownContent.vue'
import NaturalData from './NaturalData.vue'
import {naturalScalar} from './naturalData'
import AnalysisWalkthrough from './AnalysisWalkthrough.vue'
import AgentRunTrace from './AgentRunTrace.vue'
import TextEntries from './TextEntries.vue'
import {readSession,writeSession,removeSession} from './session'
import {iterationGoals,iterationTitle,iterationReading,propertyIterationGoals,requiredIterations} from './agile'
import {homeProjects,readSidebarCollapsed,writeSidebarCollapsed} from './uiLayout'
const sidebarCollapsed=ref(false),projectSelect=ref<any>(null)
function browserStorage(){try{return window.localStorage}catch{return null}}
function toggleSidebar(){sidebarCollapsed.value=!sidebarCollapsed.value;writeSidebarCollapsed(browserStorage(),sidebarCollapsed.value)}
async function expandSidebar(focusProject=false){sidebarCollapsed.value=false;writeSidebarCollapsed(browserStorage(),false);if(focusProject){await nextTick();projectSelect.value?.focus?.()}}
const propertyPanel=ref<InstanceType<typeof PropertyCasePanel>|null>(null)
const currentArea=ref('rules'),engineeringTrace=ref<any>({objects:[],relations:[],history:[],events:[]})
const hasEngineering=computed(()=>engineeringTrace.value.objects.length>0)
const activeAreas=computed(()=>areas[activeStep.value]||[])
const analysisTitle=computed(()=>({'specification':'需求分析记录','engineering-intent':'修改范围与验收约定','software-change':'记录修改前的版本','verification':'范围与测试验证','runtime-outcome':'效果评估记录'} as any)[activeStep.value]||stages[activeStep.value])
function followStage(){currentArea.value=(areas[activeStep.value]||['rules'])[0]}
async function navigateEngineering(area:string){const step=stageForArea(area);currentArea.value=area;if(step!==activeStep.value){activeStep.value=step;await act(loadInput)}}
async function selectEngineeringProject(id:string){projectId.value=id;activeStep.value='specification';currentArea.value='rules';await act(refresh)}

type Artifact={id:string;kind:string;title:string;data:any;sources:string[];workflow_step:string;status:string;created_at:string;current_iteration?:boolean;current_result?:boolean}
const projects=ref<any[]>([]),projectId=ref(''),showAllProjects=ref(false),artifacts=ref<Artifact[]>([]),workflow=ref<any>({steps:[]}),assembled=ref<any>({sources:[],missing:[]})
watch(projectId,(id,oldId)=>{if(oldId){writeSession(`evidence:${oldId}`,evidenceForm.value);writeSession(`runtime:${oldId}`,runtimeForm.value)}engineeringTrace.value={objects:[],relations:[],history:[],events:[]};artifacts.value=[];workflow.value={steps:[]};assembled.value={sources:[],missing:[]};runs.value=[];suggestions.value=[];evidenceForm.value=readSession<typeof evidenceForm.value>(`evidence:${id}`)||{title:'',type:'User Feedback',content:''};runtimeForm.value=readSession<typeof runtimeForm.value>(`runtime:${id}`)||{title:'',verification_id:'',content:'',metrics:'{}'}})
const skills=ref<any[]>([]),runs=ref<any[]>([]),suggestions=ref<any[]>([]),busy=ref(false),error=ref(''),agentPending=ref(false)
const activeStep=ref('project-context'),selectedIteration=ref(1),creating=ref(false),evidenceOpen=ref(false),runtimeOpen=ref(false),reviewOpen=ref(false),traceOpen=ref(false),helpOpen=ref(false)
watch(projectId,()=>{selectedIteration.value=1})
const run=ref<any>(null),skill=ref<any>(null),fields=ref<Record<string,string>>({}),checks=ref<boolean[]>([])
const referenceFilled=ref<string[]>([])
const legacyProblemStatement='内部已有预计联系时间，但居民详情未返回该信息。'
const reviewSourcePanel=ref<HTMLElement|null>(null)
const finalRef=ref(''),aiTest=ref(''),projectDescription=ref(''),createForm=ref({name:'',description:'',mode:'property',repository:'',branch:'',base_commit:'',problem_statement:'',raw_materials:'',manifest_path:'',iteration_count:4,iteration_length_weeks:2,iteration_goals:[...propertyIterationGoals],ai_enabled:false,ai_provider:'bigmodel',ai_model:'glm-4-flash-250414',api_key:''})
const evidenceForm=ref({title:'',type:'User Feedback',content:''}),runtimeForm=ref({title:'',verification_id:'',content:'',metrics:'{}'})
watch(evidenceForm,value=>{if(projectId.value)writeSession(`evidence:${projectId.value}`,value)},{deep:true,flush:'sync'})
watch(runtimeForm,value=>{if(projectId.value)writeSession(`runtime:${projectId.value}`,value)},{deep:true,flush:'sync'})
const project=computed(()=>projects.value.find(p=>p.id===projectId.value)),definition=computed(()=>workflow.value.steps?.find((s:any)=>s.id===activeStep.value))
const visibleHomeProjects=computed(()=>homeProjects(projects.value,showAllProjects.value))
const latest=(kind:string)=>[...artifacts.value].reverse().find(o=>o.kind===kind&&o.current_iteration!==false)
const openChange=computed(()=>[...artifacts.value].reverse().find(o=>o.kind==='ChangeRecord'&&o.data.status==='OPEN'&&o.current_iteration!==false))
const fieldEntries=computed(()=>editableFields(skill.value?.output_schema))
const candidate=computed(()=>suggestions.value.find(s=>s.skill_run_id===run.value?.id))
const isProperty=computed(()=>project.value?.details?.example_kind==='property-management')
const exampleProject=computed(()=>[...projects.value].reverse().find(p=>p.details?.example_kind==='property-management'))
const isExample=computed(()=>project.value?.details?.dataset_name==='intentflow-examples'&&project.value?.details?.instance_id==='campus-activity-001')
const agilePlan=computed(()=>project.value?.details?.agile)
const plannedIterations=computed(()=>agilePlan.value?.iterations||requiredIterations.map(item=>({...item,length_weeks:2})))
const selectedIterationPlan=computed(()=>plannedIterations.value.find((item:any)=>item.number===selectedIteration.value)||plannedIterations.value[0])
const selectedReading=computed(()=>iterationReading[selectedIteration.value]||{focus:['根据上一轮的反馈和证据，确定可验证的改进目标。'],propertyFiles:[]})
const iterationMaterials=computed(()=>{
 const evidence=artifacts.value.filter(item=>item.kind==='Evidence')
 if(!isProperty.value)return evidence
 return selectedReading.value.propertyFiles.flatMap(file=>evidence.filter(item=>item.data?.origin===`case-materials/${file}`))
})
const completedCount=computed(()=>workflow.value.steps?.filter((s:any)=>s.status==='completed'&&s.id!=='next-change').length||0)
const progressPercent=computed(()=>Math.round(completedCount.value/7*100))
const labels:Record<string,string>={Context:'正式项目上下文',Problem:'正式问题',Specification:'正式需求规格',EngineeringIntent:'正式工程意图',ChangeRecord:'变更记录',Verification:'验证结果',RuntimeEvidence:'运行证据',EngineeringEvaluation:'工程评估',Evidence:'原始证据',CandidateProblem:'候选问题',ChangeProposal:'变更提案',Requirement:'需求'}
const sourceTypes:Record<string,string>={blank:'空白项目',git:'版本库项目',benchmark:'基准案例',case:'物业管理示例'}
const statusNames:Record<string,string>={GENERATED:'已生成',ACCEPTED:'已接受',EDITED:'已编辑',REJECTED:'已拒绝',CONFIRMED:'已确认',PASS:'通过',WARNING:'警告',OPEN:'待完成',VERIFIED:'已验证'}
const enumNames:Record<string,string>={GO:'通过',OBSERVE:'观察',REJECT:'拒绝',CLOSE:'结束',ADJUST:'调整',ROLLBACK:'回退到上一版本'}
const evidenceTypes=[{value:'User Feedback',label:'用户反馈'},{value:'Runtime Log',label:'运行日志'},{value:'Metric',label:'指标'},{value:'Business Data',label:'业务数据'},{value:'Issue',label:'问题单'},{value:'Document',label:'文档'},{value:'Observation',label:'现场观察'}]
const skillNames:Record<string,string>={'project-understanding':'项目理解方法','evidence-analysis':'证据分析方法','requirement-engineering':'需求工程方法','intent-design':'工程意图设计方法','outcome-evaluation':'效果评估方法'}
const providerNames:Record<string,string>={bigmodel:'智谱智能服务',siliconflow:'硅基流动智能服务'}
const sourceListNames=(items:any[]|undefined)=>items?.map((item:string)=>labels[item]||naturalScalar(item)).join('、')||'无'
const guideText:Record<string,{goal:string;how:string;result:string}>={
 'project-context':{goal:'了解项目的用户、目标与边界',how:'查看项目说明和现有材料，写清主要用户、业务流程与本轮范围。启用智能辅助时，可在草稿基础上核对和修改。',result:'确认后自动解锁“问题与证据”。'},
 'problem-evidence':{goal:'从已有材料中确认真正的问题',how:'点击“开始问题分析”，重点核对问题是否有证据支持、影响了谁，以及还缺什么信息。',result:'继续明确需求与验收标准。'},
 'specification':{goal:'把问题转成可验收的需求',how:'检查功能需求、业务规则和成功标准，确认提案决策为“通过”后提交。',result:'继续核对设计、修改范围和验证方法。'},
 'engineering-intent':{goal:'限定代码变更的边界和验收方法',how:'核对允许修改的文件、禁止修改的文件、必须保持的条件和测试命令。',result:'确认后即可记录修改前的代码版本。'},
 'software-change':{goal:'记录修改前的代码版本',how:'点击下方按钮记录修改前的版本。示例项目随后可以在网页内应用演示修改。',result:'完成后自动进入“工程验证”。'},
 'verification':{goal:'验证修改范围、保护行为和验收标准',how:'示例项目先点击“一键应用演示修复”，再点击“执行确定性验证”；普通项目请先在外部开发工具中提交代码。',result:'通过后即可录入修改后的运行证据。'},
 'runtime-outcome':{goal:'比较修改前后的真实效果',how:'先录入变更后的观察和指标，再让系统评估目标是否达到。',result:'最后由你决定结束、继续观察、调整或回退到上一版本。'},
 'next-change':{goal:'回顾本轮结果，确定后续改进',how:'可打开全过程追溯查看每个正式结论来自哪些证据。',result:'如需继续改进，可返回问题与证据开始下一轮。'},
}
const lesson=computed(()=>stageGuidance[activeStep.value])
const canAct=computed(()=>assembled.value.ready||(activeStep.value==='runtime-outcome'&&!!latest('Verification')&&!latest('RuntimeEvidence')))
function stageStatus(s:any){
 const taskIds:Record<string,string[]>={'specification':['rules','prototype'],'engineering-intent':['architecture'],'software-change':['change'],'verification':['verify'],'runtime-outcome':['outcome']}
 const tasks=(engineeringTrace.value.tasks||[]).filter((t:any)=>(taskIds[s.id]||[]).includes(t.id))
 if(hasEngineering.value&&tasks.length){if(tasks.every((t:any)=>t.state==='已完成'))return '已有成果';if(tasks.some((t:any)=>t.state==='待复验'))return '需要复验';return tasks.some((t:any)=>t.state==='可开始')?'有待办任务':'待前序成果'}
 return s.status==='completed'?'已有分析记录':s.status==='blocked'?'待补充资料':'可开始'
}
const guide=computed(()=>{
 const base=guideText[activeStep.value]||guideText['project-context']
 if(!isProperty.value)return base
 const how:Record<string,string>={'project-context':'先阅读项目资料室中的背景、角色与访谈，再核对下方参考草稿。','problem-evidence':'对照工单、日志与初始测试，确认联系时间遗漏的原因和影响。','specification':'确认需求草稿后，切换身份体验报修，并记录本轮方案取舍。','engineering-intent':'核对本轮只修改居民详情，保护权限、状态流转与历史兼容。','software-change':'先记录修改前版本，再审阅并应用参考修改，或在开发工具中自行完成。','verification':'先完成并提交修改，再执行本轮代码验证，检查每项结果。','runtime-outcome':'先回放同一批工单并保存前后对比，再核对评估草稿、确认下一步。'}
 return {...base,how:how[activeStep.value]||base.how}
})
const stepNumber=computed(()=>Math.max(1,(workflow.value.steps||[]).findIndex((s:any)=>s.id===activeStep.value)+1))

async function api(path:string,method='GET',body?:any){const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});const v=await r.json();if(!r.ok)throw new Error(typeof v.detail==='string'?v.detail:'操作未完成，请核对输入后重试。');return v}
async function act(fn:()=>Promise<void>){if(busy.value)return;busy.value=true;error.value='';try{await fn()}catch(e){if(e!=='cancel'&&e!=='close'){error.value=e instanceof Error?e.message:'操作未完成，请重试';ElMessage.error(error.value)}}finally{busy.value=false}}
async function refresh(advance=false){projects.value=await api('/projects');if(!projectId.value)return;[artifacts.value,workflow.value,runs.value,suggestions.value]=await Promise.all([api(`/projects/${projectId.value}/artifacts`),api(`/projects/${projectId.value}/workflow`),api(`/projects/${projectId.value}/runs`),api(`/projects/${projectId.value}/suggestions`)]);if(!definition.value||advance){activeStep.value=workflow.value.current_step;followStage()}await loadInput()}
async function loadInput(){if(projectId.value)assembled.value=await api(`/projects/${projectId.value}/workflow/${activeStep.value}/input`)}
async function selectProject(){activeStep.value='project-context';finalRef.value='';await act(async()=>{await refresh();if(project.value?.details?.v2_case){activeStep.value='specification';followStage();await loadInput()}})}
async function enterProject(id:string){projectId.value=id;await selectProject()}
async function chooseExample(){if(!exampleProject.value){await act(async()=>{const p=await api('/projects','POST',{name:'青禾社区物业管理',mode:'property'});projectId.value=p.id;activeStep.value='project-context';await refresh()});return}projectId.value=exampleProject.value.id;activeStep.value='project-context';finalRef.value='';await act(refresh)}
function startNewPropertyDemo(){createForm.value={...createForm.value,name:`青禾社区物业智能演示 ${new Date().toLocaleString('zh-CN',{hour12:false})}`,description:'居民反馈：维修人员已填写预计联系时间，但报修详情没有显示。请分析原因，提出可验证的修复方案，并保留权限和工单状态规则。',mode:'property',problem_statement:'',raw_materials:'',iteration_count:4,iteration_length_weeks:2,iteration_goals:[...propertyIterationGoals],ai_enabled:true,api_key:''};aiTest.value='';creating.value=true}
async function selectStep(id:string){if(busy.value)return;activeStep.value=id;followStage();await act(loadInput);await nextTick();document.querySelector('.stage-overview')?.scrollIntoView({block:'nearest'})}
function projectLabel(p:any){return `${p.name}，${p.details?.v2_case?'教学案例':sourceTypes[p.source_type]||'项目'}`}
function onModeChange(mode:string){if(['case','property'].includes(mode)&&!createForm.value.name.trim()){createForm.value.name=mode==='property'?'我的物业管理实践':'校园报名旧示例';createForm.value.description=mode==='property'?'居民反馈：报修详情看不到已填写的预计联系时间。请分析并提出可验证的改进方案。':'跟随页面引导完成四轮敏捷迭代'}if(['case','property'].includes(mode)){createForm.value.iteration_count=4;createForm.value.iteration_length_weeks=2;createForm.value.iteration_goals=mode==='property'?[...propertyIterationGoals]:iterationGoals(4)}}
function resizeIterationGoals(){createForm.value.iteration_goals=iterationGoals(createForm.value.iteration_count,createForm.value.iteration_goals)}
async function createProject(){await act(async()=>{const body={...createForm.value,base_commit:createForm.value.base_commit||'HEAD',raw_materials:createForm.value.raw_materials.split(/\r?\n/).map(item=>item.trim()).filter(Boolean)};const p=await api('/projects','POST',body);projectId.value=p.id;activeStep.value='project-context';creating.value=false;await refresh();ElMessage.success('项目已创建，请先核对项目背景')})}
async function testAI(){await act(async()=>{const r=await api('/ai/test','POST',{provider:createForm.value.ai_provider,model:createForm.value.ai_model,api_key:createForm.value.api_key});aiTest.value=`连接成功：${r.model}`})}
function openEvidence(){evidenceOpen.value=true}
function openRuntime(){runtimeForm.value.verification_id=runtimeForm.value.verification_id||latest('Verification')?.id||'';runtimeOpen.value=true}
async function saveEvidence(){await act(async()=>{await api(`/projects/${projectId.value}/evidence`,'POST',evidenceForm.value);removeSession(`evidence:${projectId.value}`);evidenceForm.value={title:'',type:'User Feedback',content:''};evidenceOpen.value=false;await refresh()})}
async function saveProjectDescription(){await act(async()=>{await api(`/projects/${projectId.value}`,'PATCH',{description:projectDescription.value.trim()});projectDescription.value='';await refresh();ElMessage.success('项目说明已保存，可以开始项目理解')})}
async function beginAnalysis(){if(busy.value)return;if(currentDraft.value){resume(currentDraft.value);return}agentPending.value=!!project.value?.details?.ai?.enabled;try{await act(async()=>{run.value=await api(`/projects/${projectId.value}/workflow/${activeStep.value}/runs`,'POST',{mode:project.value?.details?.ai?.enabled?'llm':'manual'});skill.value=skills.value.find(s=>s.id===run.value.skill_id);fields.value={};referenceFilled.value=[];for(const [key,schema] of Object.entries(skill.value.output_schema.properties) as [string,any][])fields.value[key]=isProperty.value?'':encodeField(run.value.suggestion?.[key],schema);checks.value=skill.value.checklist.map(()=>false);reviewOpen.value=true;await refresh()})}finally{agentPending.value=false}}

function fillReference(){
 const filled=new Set(referenceFilled.value)
 for(const [key,schema] of fieldEntries.value)if(!fields.value[key]?.trim()){const value=encodeField(run.value?.suggestion?.[key],schema);if(value.trim()){fields.value[key]=value;filled.add(key)}}
 referenceFilled.value=[...filled]
 checks.value=checks.value.map(()=>false)
}
function clearReference(){
 let cleared=0,kept=0
 for(const [key,schema] of fieldEntries.value)if(referenceFilled.value.includes(key)){if(fields.value[key]===encodeField(run.value?.suggestion?.[key],schema)){fields.value[key]='';cleared++}else kept++}
 referenceFilled.value=[];checks.value=checks.value.map(()=>false)
 ElMessage.success(kept?`已清除 ${cleared} 个参考补全；${kept} 个你修改过的字段已保留`:`已清除 ${cleared} 个参考补全`)
}
async function studentAction(action:string){
 if(action==='evidence'){openEvidence();return}
 if(action==='trace'){traceOpen.value=true;return}
 if(action==='work'&&['project-context','problem-evidence','specification','engineering-intent'].includes(activeStep.value)){
  if(canAct.value){await beginAnalysis();return}
  ElMessage.info('先完成前序正式成果；可先填写学习记录和查看提示。');return
 }
 await nextTick()
 const target=action==='experiment'?'.property-card':activeStep.value==='software-change'||activeStep.value==='verification'?'.property-card, .verification-actions, .engineering':'.property-card, .unified-analysis'
 const elements=Array.from(document.querySelectorAll<HTMLElement>(target))
 const element=activeStep.value==='runtime-outcome'&&action==='experiment'?elements.find(e=>e.textContent?.includes('比较同一批工单')):elements[0]
 if(element){element.closest('details')?.setAttribute('open','');element.scrollIntoView({block:'start'})}
}

function resume(r:any){
 run.value=r;skill.value=skills.value.find(s=>s.id===r.skill_id)
 const saved=readSession<{fields:Record<string,string>;checks:boolean[];referenceFilled?:string[]}>(`review:${projectId.value}:${r.id}`)
 fields.value={};for(const [key,schema] of fieldEntries.value){const stored=saved?.fields?.[key];fields.value[key]=key==='problem_statement'&&stored===legacyProblemStatement?encodeField(r.suggestion?.[key],schema):stored??(isProperty.value?'':encodeField(r.suggestion?.[key],schema))}
 checks.value=skill.value.checklist.map((_:string,i:number)=>saved?.checks?.[i]===true)
 referenceFilled.value=saved?.referenceFilled||[];reviewOpen.value=true
}
const currentDraft=computed(()=>[...runs.value].reverse().find(r=>r.status==='DRAFT'&&r.workflow_step===activeStep.value))
const draftStored=ref(true)
watch(fields,()=>{if(reviewOpen.value&&checks.value.some(Boolean))checks.value=checks.value.map(()=>false)},{deep:true,flush:'sync'})
watch([fields,checks,referenceFilled],()=>{if(reviewOpen.value&&run.value)draftStored.value=writeSession(`review:${projectId.value}:${run.value.id}`,{fields:fields.value,checks:checks.value,referenceFilled:referenceFilled.value})},{deep:true,flush:'sync'})
const missingFields=computed(()=>fieldEntries.value.filter(([key,schema])=>needsValue(schema)&&!fields.value[key]?.trim()).map(([,schema])=>schema.title))
const canFinish=computed(()=>!busy.value&&checks.value.length>0&&checks.value.every(Boolean)&&!missingFields.value.length)
const reviewClose=(done:()=>void)=>{if(!busy.value)done()}
const previousStage=computed(()=>workflow.value.steps[stepNumber.value-2])
const startLabel=computed(()=>currentDraft.value?'继续审阅草稿':actionLabel.value)
watch([projectId,activeStep,currentArea],()=>{if(projectId.value){writeSession('location',{projectId:projectId.value,step:activeStep.value,area:currentArea.value})}},{flush:'post'})

async function finish(decision:'accept'|'reject'){await act(async()=>{if(decision==='reject')await ElMessageBox.confirm('放弃后，此草稿中的填写内容将不再用于本次分析。若想稍后继续，请选择“暂存并关闭”。','放弃本次内容',{confirmButtonText:'确认放弃',cancelButtonText:'继续编辑',type:'warning'});const output=decision==='reject'?{}:Object.fromEntries(fieldEntries.value.map(([k,s])=>[k,decodeField(fields.value[k]||'',s)]));await api(`/projects/${projectId.value}/runs/${run.value.id}/review`,'POST',{decision,output,checklist:checks.value});removeSession(`review:${projectId.value}:${run.value.id}`);reviewOpen.value=false;const reviewedStep=activeStep.value;await refresh(true);if(isProperty.value&&reviewedStep==='specification'&&decision==='accept'){activeStep.value='specification';await loadInput()}ElMessage.success(decision==='accept'?'已确认正式输出':'候选已拒绝')})}
async function startChange(){const intent=latest('EngineeringIntent');if(!intent)return;await act(async()=>{await api(`/projects/${projectId.value}/changes`,'POST',{intent_id:intent.id,branch:''});await refresh();ElMessage.success('修改前版本已记录，请在本阶段完成并提交代码修改')})}
async function applyDemoFix(){await act(async()=>{const result=await api(`/projects/${projectId.value}/demo/apply-fix`,'POST');finalRef.value=result.commit;ElMessage.success(result.changed?'演示修复已应用并提交，可以执行验证了':'演示修复已经存在，可以执行验证了');await refresh()})}
async function verify(){const change=openChange.value;if(!change)return;await act(async()=>{await ElMessageBox.confirm('将在固定提交的临时副本执行真实测试。本机执行不是安全沙箱，请只运行你信任的项目。','确定性验证',{confirmButtonText:'执行验证',cancelButtonText:'取消'});await api(`/projects/${projectId.value}/changes/${change.id}/verify`,'POST',{final_commit:finalRef.value||'HEAD',execute_tests:true});await refresh(true)})}
async function saveRuntime(){await act(async()=>{await api(`/projects/${projectId.value}/runtime`,'POST',{...runtimeForm.value,metrics:JSON.parse(runtimeForm.value.metrics)});removeSession(`runtime:${projectId.value}`);runtimeForm.value={title:'',verification_id:'',content:'',metrics:'{}'};runtimeOpen.value=false;await refresh(true)})}
async function explainVerification(){const v=latest('Verification');if(!v)return;await act(async()=>{await api(`/projects/${projectId.value}/verification/explain`,'POST',{verification_id:v.id});await refresh()})}
function primary(){if(['project-context','problem-evidence','specification','engineering-intent'].includes(activeStep.value))return beginAnalysis();if(activeStep.value==='software-change')return startChange();if(activeStep.value==='verification')return verify();if(activeStep.value==='runtime-outcome'){if(!latest('RuntimeEvidence')){if(isProperty.value)return studentAction('experiment');openRuntime();return}return beginAnalysis()}activeStep.value='problem-evidence';return loadInput()}
const actionLabel=computed(()=>({"project-context":"开始项目理解","problem-evidence":"开始问题分析","specification":"开始形成需求规格","engineering-intent":"开始设计工程意图","software-change":isProperty.value?'记录修改前版本':isExample.value?'记录修改前版本，进入示例变更':'记录修改前版本，开始外部变更',"verification":"执行确定性验证","runtime-outcome":latest('RuntimeEvidence')?'开始效果评估':isProperty.value?'前往工单回放':'录入修改后的运行证据',"next-change":"返回问题与证据"} as any)[activeStep.value])
onMounted(()=>{
 document.documentElement.classList.add('if-home-first')
 window.setTimeout(()=>document.documentElement.classList.remove('if-home-first'),600)
 void act(async()=>{
  sidebarCollapsed.value=readSidebarCollapsed(browserStorage())
  skills.value=await api('/skills');await refresh()
  const location=readSession<{projectId:string;step:string;area:string}>('location')
  if(location&&projects.value.some(p=>p.id===location.projectId)){
   projectId.value=location.projectId;activeStep.value=stages[location.step]?location.step:'project-context';followStage()
   if(activeAreas.value.includes(location.area))currentArea.value=location.area
   await refresh()
  }
 })
})
</script>

<template>
<a class="skip-link" href="#workspace-main">跳到当前任务</a><div class="shell" :class="{'sidebar-collapsed':sidebarCollapsed}"><aside aria-label="项目侧栏"><button class="sidebar-toggle" type="button" :aria-label="sidebarCollapsed?'展开项目侧栏':'折叠项目侧栏'" :title="sidebarCollapsed?'展开项目侧栏':'折叠项目侧栏'" :aria-expanded="!sidebarCollapsed" @click="toggleSidebar">{{sidebarCollapsed?'展开':'收起'}}</button><div class="brand"><img src="/logo.jpg" alt="院系教学单位标识" class="brand-img"><div>IntentFlow<small>软件工程教学工作台</small></div></div><div class="workspace-label">当前项目</div><el-select ref="projectSelect" v-model="projectId" class="project-select" placeholder="请选择一个项目" aria-label="当前项目" filterable :disabled="busy" @change="selectProject"><el-option v-for="p in projects" :key="p.id" :label="projectLabel(p)" :value="p.id"/></el-select><el-button :disabled="busy" class="new-project" @click="creating=true">新建项目</el-button><div v-if="project" class="project-meta"><b>{{project.details?.v2_case?'教学案例':sourceTypes[project.source_type]||'项目'}}</b><span>{{project.repository?'已连接代码仓库':'无代码仓库'}}</span><span>{{plannedIterations.length}} 轮敏捷迭代，当前第 {{agilePlan?.current_iteration||1}} 轮</span><span>{{project.details.ai?.enabled?'已启用智能辅助':'手工填写模式'}}</span></div><button class="sidebar-help" @click="helpOpen=true">学习与操作指南</button><div class="sidebar-footer"><span class="dot"></span> 学习、实践与复盘<br><small>本地教学版</small></div><div class="collapsed-sidebar-actions"><span :title="project?.name||'尚未选择项目'">{{project?'当前项目':'未选项目'}}</span><button type="button" aria-label="展开侧栏并选择项目" title="展开侧栏并选择项目" @click="expandSidebar(true)">项目</button><button type="button" aria-label="创建新项目" title="创建新项目" @click="creating=true">新建</button><button type="button" aria-label="打开学习与操作指南" title="打开学习与操作指南" @click="helpOpen=true">帮助</button></div></aside>
 <main id="workspace-main" tabindex="-1" v-loading="busy" :element-loading-text="agentPending?'正在读取材料并请求智能模型…':'正在处理，请稍候…'" :aria-busy="busy"><header><div class="breadcrumb">{{project?.name||'软件工程实践'}}：{{stages[activeStep]}}</div><div class="header-actions"><el-button @click="helpOpen=true">操作帮助</el-button><el-button :disabled="!projectId" @click="traceOpen=true">查看全过程追溯</el-button></div></header><el-alert v-if="error" :title="error" type="error" role="alert" show-icon @close="error=''"/><span class="motion-status" role="status" aria-live="polite">{{busy?(agentPending?'正在请求智能模型，候选生成后仍需人工确认…':'正在处理，请稍候…'):''}}</span>

  <div v-if="!projectId" class="home-view"><section class="home-hero" aria-labelledby="home-title"><div class="home-hero-copy"><div class="home-brand"><img src="/logo.jpg" alt="院系教学单位标识"><span>院系教学单位</span></div><div class="eyebrow">IntentFlow · 软件工程教学与实践工作台</div><h1 id="home-title">从真实项目开始学习、实践与复盘</h1><p>使用同一套八阶段流程梳理问题、确认规则、完成工程修改并保留全过程证据。</p><div class="welcome-actions"><el-button type="primary" size="large" @click="chooseExample">体验物业管理完整示例</el-button><el-button plain size="large" @click="startNewPropertyDemo">开始新的物业智能演示</el-button><el-button size="large" @click="creating=true">创建自己的项目</el-button><el-button text size="large" @click="helpOpen=true">学习与操作指南</el-button></div><ul class="home-capabilities" aria-label="工作台能力"><li><b>证据驱动</b><span>从真实材料识别问题</span></li><li><b>八阶段协作</b><span>让规则、实现与验证对应</span></li><li><b>全过程留痕</b><span>保留可复核的工程记录</span></li></ul></div><section class="home-learning-route" aria-labelledby="learning-route-title"><div class="route-heading"><div><div class="eyebrow">四轮敏捷迭代教学路线</div><h2 id="learning-route-title">在实践中逐轮深化</h2></div><span>教学计划</span></div><p class="route-note">以下是课程路线说明，不表示任何项目的实际进度或完成状态。</p><ol><li><span>01</span><div><b>最小可用原型</b><p>从问题证据出发，完成第一轮可验证交付。</p></div></li><li><span>02</span><div><b>前向部署与访谈</b><p>让真实使用反馈进入下一轮需求判断。</p></div></li><li><span>03</span><div><b>数据驱动需求</b><p>结合运行数据修订规则与工程意图。</p></div></li><li><span>04</span><div><b>运行与维护</b><p>验证业务变化，并形成持续改进闭环。</p></div></li></ol></section></section><div class="home-lower-grid"><section class="home-projects" aria-labelledby="project-list-title"><div class="home-section-heading"><div><div class="eyebrow">本地项目</div><h2 id="project-list-title">继续项目</h2></div><el-button v-if="projects.length>3" :aria-expanded="showAllProjects" aria-controls="home-project-list" @click="showAllProjects=!showAllProjects">{{showAllProjects?'收起项目':`查看全部项目（${projects.length}）`}}</el-button></div><div v-if="visibleHomeProjects.length" id="home-project-list" class="home-project-grid"><article v-for="p in visibleHomeProjects" :key="p.id" class="home-project-card"><div><el-tag size="small" effect="plain">{{p.details?.v2_case?'教学案例':sourceTypes[p.source_type]||'项目'}}</el-tag><span>{{p.repository?'已连接代码仓库':'未连接代码仓库'}}</span></div><h3>{{p.name}}</h3><p>{{p.description||'尚未填写项目说明，可进入项目后补充。'}}</p><el-button :aria-label="`进入项目 ${p.name}`" @click="enterProject(p.id)">进入项目</el-button></article></div><div v-else class="home-project-empty"><h3>还没有本地项目</h3><p>可先体验完整物业示例，或创建自己的项目。</p></div></section><section class="home-secondary" aria-label="辅助入口"><button type="button" :disabled="!projectId" @click="traceOpen=true"><b>全过程追溯</b><span>进入项目后查看分析、规则、版本与验证证据。</span></button><button type="button" @click="helpOpen=true"><b>学习与操作帮助</b><span>了解八阶段任务、完成条件和常见问题。</span></button><details class="small-examples"><summary>其他小型练习</summary><p>通过可运行领域案例练习规则、代码与测试的对应关系。</p><EngineeringWorkspace project-id="" embedded @project-created="selectEngineeringProject"/></details></section></div></div>
  <template v-else><section class="iteration-roadmap" aria-label="敏捷迭代计划"><div class="iteration-heading"><div><div class="eyebrow">敏捷交付路线</div><h2>{{plannedIterations.length}} 轮迭代计划</h2></div><p>每轮 {{agilePlan?.length_weeks||2}} 周；实际执行第 {{agilePlan?.current_iteration||1}} 轮</p></div><ol><li v-for="item in plannedIterations" :key="item.number" :class="{current:item.number===(agilePlan?.current_iteration||1),selected:item.number===selectedIteration}"><button type="button" :aria-pressed="item.number===selectedIteration" aria-controls="iteration-preview" @click="selectedIteration=item.number"><span>第 {{item.number}} 轮 <small v-if="item.number===(agilePlan?.current_iteration||1)">正在执行</small></span><b>{{item.title}}</b><span class="iteration-goal">{{item.goal}}</span><em>查看本轮材料</em></button></li></ol><div id="iteration-preview" class="iteration-preview" aria-live="polite"><div class="iteration-preview-heading"><div><span>第 {{selectedIteration}} 轮 · 材料预览</span><h3>{{selectedIterationPlan?.title}}</h3></div><small>{{selectedIteration===(agilePlan?.current_iteration||1)?'当前执行轮次':'计划轮次'}}</small></div><p>{{selectedIterationPlan?.goal}}</p><p class="iteration-preview-note">浏览材料不会改变当前执行轮次或正式结果。</p><ul><li v-for="focus in selectedReading.focus" :key="focus">{{focus}}</li></ul><div v-if="iterationMaterials.length" class="iteration-materials"><h4>{{isProperty?'案例材料 · 虚构场景与模拟数据':'本项目已有材料 · 跨轮参考'}}</h4><details v-for="material in iterationMaterials" :key="material.id"><summary>{{material.title}}</summary><pre v-if="material.data?.origin?.endsWith('.json')" class="iteration-json">{{material.data.content}}</pre><MarkdownContent v-else-if="typeof material.data?.content==='string'" :source="material.data.content"/><NaturalData v-else :value="material.data"/></details></div><p v-else class="iteration-preview-empty">本项目尚无可展示的原始材料；请在当前执行轮次补充证据。</p></div></section><nav class="workflow-bar unified-journey" aria-label="当前迭代的项目流程"><button v-for="(s,i) in workflow.steps" :key="s.id" :class="[s.status,{active:s.id===activeStep}]" :aria-current="s.id===activeStep?'step':undefined" :disabled="busy" @click="selectStep(s.id)"><span>{{Number(i)+1}}</span><b>{{stages[s.id]||s.title}}</b><small>{{stageStatus(s)}}</small></button></nav>   <section class="coach stage-overview" v-if="activeStep!=='next-change'" aria-label="当前阶段任务"><div class="coach-icon">{{stepNumber}}</div><div class="coach-copy"><div class="eyebrow">第 {{agilePlan?.current_iteration||1}} 轮 · 当前任务</div><h2>{{guide.goal}}</h2><p>{{guide.how}}</p><strong>完成条件：{{lesson.done}}</strong><form v-if="activeStep==='project-context'&&!canAct&&!project?.repository&&!project?.description" class="inline-project-description" @submit.prevent="saveProjectDescription"><label>先补充项目说明<textarea v-model="projectDescription" rows="3" placeholder="说明主要用户、当前流程和这次想改进什么" required/></label><el-button native-type="submit" type="primary" :disabled="!projectDescription.trim()">保存项目说明</el-button></form></div><div class="coach-progress"><b>{{completedCount}} / 7</b><span>项文档步骤已确认</span><el-progress :percentage="progressPercent" :show-text="false"/><el-button type="primary" :loading="busy" :disabled="!canAct||busy" @click="primary">{{startLabel}}</el-button><span v-if="!canAct" class="blocked-help">请先完成前序阶段并补齐资料。<button v-if="previousStage" @click="selectStep(previousStage.id)">前往{{stages[previousStage.id]}}</button></span></div></section><details v-if="project.details.ai?.enabled" class="agent-run-details" :open="agentPending||runs.some((r:any)=>r.mode==='llm'&&r.workflow_step===activeStep)"><summary>查看本阶段智能体运行记录</summary><AgentRunTrace :runs="runs" :suggestions="suggestions" :artifacts="artifacts" :step="activeStep" :pending="agentPending"/></details>
   <section v-if="latest('Verification')&&['verification','runtime-outcome'].includes(activeStep)" class="student-verification" aria-label="本轮验证结果"><h2>本轮代码验证：{{latest('Verification')?.data.status==='PASS'?'通过':'未通过'}}</h2><p>{{latest('Verification')?.data.status==='PASS'?'当前代码版本已经通过验证，接下来用运行证据检查实际效果。测试通过不等于用户问题已经解决。':'请先对照预期与实际定位失败，修改后重新验证；不要把失败或未知当作完成。'}}</p><details><summary>逐项查看验证依据</summary><div v-for="(row,index) in latest('Verification')?.data.evidence_matrix||[]" :key="index"><b>{{row.intent_clause}}</b><p>{{statusNames[row.result]||naturalScalar(row.result)}}</p></div><NaturalData :value="latest('Verification')?.data"/></details></section><StudentCoach v-if="project" :key="projectId+activeStep" :project-id="projectId" :stage="activeStep" :example="isProperty||!!project.details?.v2_case||project.source_type==='benchmark'" :property="isProperty" :artifacts="artifacts" :repository="project.repository" :busy="busy" @action="studentAction" @material="propertyPanel?.showMaterial($event)" @navigate="selectStep" @changed="act(refresh)"/>
   <PropertyCasePanel ref="propertyPanel" v-if="isProperty" :key="projectId" :project-id="projectId" :stage="activeStep" :artifacts="artifacts" @changed="act(refresh)" @navigate="selectStep"/><details v-if="activeStep!=='next-change'" class="unified-analysis" :class="{'property-workflow':isProperty}" :open="!hasEngineering||['project-context','problem-evidence'].includes(activeStep)"><summary>{{analysisTitle}}</summary>


   <div v-if="assembled.missing?.length" class="gate-warning"><b>开始分析前需要补充资料</b><span v-for="m in assembled.missing" :key="m">缺少 {{m}}</span></div>
   <section class="workspace-grid"><article class="stage-card"><h2>本阶段参考资料</h2><p>分析前先核对这些资料是否准确、完整。</p><div v-if="!assembled.sources?.length" class="quiet">项目说明和代码仓库已准备</div><details class="source-item" v-for="o in assembled.sources" :key="o.id"><summary>{{o.title}}</summary><MarkdownContent v-if="typeof o.data?.content==='string'" :source="o.data.content"/><NaturalData v-else :value="o.data"/></details><el-collapse><el-collapse-item title="查看详细输入要求"><p>必需资料：{{sourceListNames(definition?.required_input)}}</p><p>可选资料：{{sourceListNames(definition?.optional_input)}}</p></el-collapse-item></el-collapse></article>
    <article class="stage-card"><h2>本阶段要完成什么</h2><p>{{lesson.done}}</p><div class="trace-chip">使用方法，{{skillNames[definition?.skill]||'确定性验证'}}</div><div class="trace-chip">参考内容，{{definition?.ai_context?.join('，')||'代码版本与测试结果'}}</div></article>
    <article class="stage-card"><h2>填写方式</h2><template v-if="project.details.ai?.enabled"><el-tag>智能模型先填写</el-tag><p>{{providerNames[project.details.ai.provider]||'智能模型服务'}}，{{project.details.ai.model}}</p><div v-for="s in suggestions.filter((x:any)=>x.workflow_step===activeStep)" :key="s.id" class="suggestion"><b>{{statusNames[s.status]||s.status}}</b><span>模型已生成候选内容，最终以你的确认结果为准。</span></div></template><template v-else><el-tag type="info">你来手工填写</el-tag><p>系统会提供结构化表单，不需要接口密钥。</p></template><p class="policy">无论哪种方式，都必须由你检查并确认后才会进入下一步。</p></article>
    <article class="stage-card output-card"><h2>本步确认结果</h2><div v-for="o in artifacts.filter(x=>x.workflow_step===activeStep&&x.current_iteration!==false&&x.current_result!==false)" :key="o.id" class="output-item"><small>{{labels[o.kind]||'工程记录'}}</small><b>{{o.title}}</b><el-tag size="small">{{statusNames[o.status]||naturalScalar(o.status)}}</el-tag><div v-if="o.kind==='Verification'" class="matrix-row" v-for="(row,index) in o.data.evidence_matrix" :key="index"><b>{{row.level.replace('L','第')}}级</b><span>{{row.intent_clause}}</span><em>{{statusNames[row.result]||naturalScalar(row.result)}}</em></div><details><summary>查看完整内容</summary><NaturalData :value="o.data"/></details></div><div v-if="!artifacts.some(x=>x.workflow_step===activeStep&&x.current_iteration!==false&&x.current_result!==false)" class="quiet">确认当前任务后，正式结果会显示在这里</div></article></section>
   <section v-if="activeStep==='software-change'&&openChange" class="action-context"><div><b>已记录修改前版本</b><span>{{openChange.data.baseline_commit}}</span></div><el-button type="primary" @click="selectStep('verification')">修改已提交，进入验证</el-button></section><section v-if="activeStep==='verification'" class="action-context verification-actions"><template v-if="isExample&&openChange"><div><b>示例项目快捷操作</b><span>无需打开开发工具，系统会应用预置的并发安全修复并创建提交。</span></div><el-button type="primary" @click="applyDemoFix">一键应用演示修复</el-button></template><el-input v-else v-model="finalRef" placeholder="最终提交编号；留空表示当前版本"/><el-button v-if="latest('Verification')&&project.details.ai?.enabled" @click="explainVerification">解释验证结果（不改变判定）</el-button></section>

   </details>
   <EngineeringWorkspace v-if="!isProperty" :key="projectId" v-show="activeAreas.length" :project-id="projectId" :repository="project?.repository" :area="currentArea" :sections="activeAreas" :artifacts="artifacts" embedded @navigate="navigateEngineering" @trace="engineeringTrace=$event" @project-created="selectEngineeringProject" @changed="act(refresh)"/>
  </template></main></div>

<el-dialog v-model="creating" title="创建 IntentFlow 项目" width="min(860px,96vw)" :close-on-click-modal="false" :before-close="reviewClose">
 <el-form :disabled="busy" label-position="top">
  <el-alert v-if="error" :title="error" type="error" :closable="false"/>
  <el-alert title="所有项目都按敏捷方式推进；物业管理示例已安排完整四轮。" type="info" :closable="false"/>
  <el-form-item label="你想从哪里开始？"><el-radio-group v-model="createForm.mode" @change="onModeChange"><el-radio-button value="property">物业管理示例</el-radio-button><el-radio-button value="case">校园报名旧示例</el-radio-button><el-radio-button value="blank">空白项目</el-radio-button><el-radio-button value="git">版本库项目</el-radio-button><el-radio-button value="benchmark">基准案例</el-radio-button></el-radio-group><div class="source-description">{{createForm.mode==='property'?'四轮体验物业报修改进：最小原型、前向部署访谈、数据需求、运行维护。':createForm.mode==='case'?'校园报名的小型并发修复练习，同样采用四轮计划。':createForm.mode==='git'?'从已有 Git 仓库开始，系统会读取目录、说明和历史。':createForm.mode==='benchmark'?'从符合格式的本地案例清单导入。':'从项目说明开始，代码仓库可以稍后连接。'}}</div></el-form-item>
  <div class="form-two"><el-form-item label="项目名称"><el-input v-model="createForm.name" aria-label="项目名称" placeholder="例如：青禾社区物业服务改进"/></el-form-item><el-form-item :label="createForm.mode==='property'?'本次用户请求':'项目说明'"><el-input v-model="createForm.description" :type="createForm.mode==='property'?'textarea':'text'" :rows="3" :placeholder="createForm.mode==='property'?'说明居民遇到的问题和希望智能体完成的任务':'一句话说明要改进什么'"/></el-form-item></div>
  <template v-if="createForm.mode==='git'||createForm.mode==='blank'"><el-form-item :label="createForm.mode==='git'?'代码仓库网址或本地路径':'代码仓库（可选）'"><el-input v-model="createForm.repository"/></el-form-item><div class="form-two"><el-form-item label="分支（可选）"><el-input v-model="createForm.branch"/></el-form-item><el-form-item label="初始代码版本"><el-input v-model="createForm.base_commit" placeholder="留空表示使用当前版本"/></el-form-item></div></template>
  <el-form-item v-if="createForm.mode==='benchmark'" label="基准案例清单本地路径"><el-input v-model="createForm.manifest_path"/></el-form-item><el-form-item v-if="!['case','property'].includes(createForm.mode)" label="问题陈述"><el-input v-model="createForm.problem_statement" placeholder="用一句话说明当前结果与期望结果的差距"/></el-form-item><el-form-item v-if="!['case','property'].includes(createForm.mode)" label="原始材料（可选）"><TextEntries v-model="createForm.raw_materials" label="原始材料" placeholder="例如：访谈记录、运行日志或问题单"/></el-form-item>
  <el-divider>敏捷迭代计划</el-divider>
  <el-alert v-if="['case','property'].includes(createForm.mode)" title="示例固定为 4 轮，每轮 2 周；创建后可在工作台查看完整路线。" type="info" :closable="false"/>
  <div v-else class="form-two"><el-form-item label="计划迭代轮数（至少 4 轮）"><el-select v-model="createForm.iteration_count" @change="resizeIterationGoals"><el-option v-for="n in [4,5,6,7,8]" :key="n" :value="n" :label="`${n} 轮`"/></el-select></el-form-item><el-form-item label="每轮周期"><el-select v-model="createForm.iteration_length_weeks"><el-option v-for="n in [1,2,3,4]" :key="n" :value="n" :label="`${n} 周`"/></el-select></el-form-item></div>
  <div class="iteration-editor" aria-label="迭代目标"><article v-for="(goal,index) in createForm.iteration_goals" :key="index"><span>第 {{index+1}} 轮</span><b>{{iterationTitle(index)}}</b><el-input v-if="!['case','property'].includes(createForm.mode)" v-model="createForm.iteration_goals[index]" :aria-label="`第 ${index+1} 轮目标`" placeholder="用一句话说明本轮要验证或交付什么"/><p v-else>{{goal}}</p></article></div>
  <el-divider>智能辅助（可选）</el-divider><p v-if="createForm.mode==='property'" class="demo-mode-note">启用后会调用真实模型生成分析候选；案例材料与工单为模拟数据，正式结论仍需人工确认。</p><el-switch v-model="createForm.ai_enabled" active-text="使用智能辅助" inactive-text="使用手工模式"/><template v-if="createForm.ai_enabled"><el-alert title="启用后请先测试连接。密钥仅保存在本机独立密钥目录中。" type="info" :closable="false"/><div class="form-two"><el-form-item label="模型"><el-select v-model="createForm.ai_model"><el-option value="glm-4-flash-250414" label="智谱轻量模型"/><el-option value="glm-4-flashx-250414" label="智谱增强轻量模型"/></el-select></el-form-item><el-form-item label="智谱接口密钥"><el-input v-model="createForm.api_key" type="password" show-password/></el-form-item></div><el-button :disabled="!createForm.api_key.trim()" @click="testAI">测试连接</el-button><span class="success-text">{{aiTest}}</span></template>
 </el-form>
 <template #footer><el-button :disabled="busy" @click="creating=false">取消</el-button><el-button type="primary" :loading="busy" :disabled="busy||!createForm.name.trim()||(createForm.mode==='property'&&!createForm.description.trim())||(createForm.ai_enabled&&!createForm.api_key.trim())" @click="createProject">创建并进入第 1 轮</el-button></template>
</el-dialog>
<el-dialog v-model="reviewOpen" :title="'确认'+(skill?.name||'分析结果')" width="min(1180px,96vw)" class="review-dialog" :close-on-click-modal="false" :before-close="reviewClose" :show-close="!busy" :close-on-press-escape="!busy">
 <el-alert v-if="!isProperty" :title="run?.inputs?.draft_source?run.inputs.draft_source:candidate?'请检查或修改候选内容。':'请填写并确认下面的内容。'" type="info" :closable="false" show-icon/>
 <el-alert v-if="error" :title="error" type="error" :closable="false"/>
 <AnalysisWalkthrough v-if="isProperty&&run?.suggestion&&run.mode==='manual'" :inputs="run.inputs" :field-entries="fieldEntries" :suggestion="run.suggestion"/><details v-if="run?.mode==='llm'" class="agent-review-details"><summary>查看本次智能体运行记录</summary><AgentRunTrace :runs="runs" :suggestions="suggestions" :artifacts="artifacts" :step="activeStep" :pending="agentPending"/></details>
 <div class="review-layout">
  <section ref="reviewSourcePanel" class="review-source-panel" aria-label="本次分析资料">
   <h3>分析资料</h3>
   <details v-if="run?.inputs?.project_context?.project?.description" class="source-item" open><summary>项目说明</summary><MarkdownContent :source="run.inputs.project_context.project.description"/></details>
   <details v-for="(o,index) in run?.inputs?.sources" :key="o.id" class="source-item" :open="index===0"><summary>{{o.title}}</summary><MarkdownContent v-if="typeof o.data?.content==='string'" :source="o.data.content"/><NaturalData v-else :value="o.data"/></details>
   <template v-if="run?.inputs?.project_context?.engineering?.objects?.length"><h3>当前正式规则与设计约束</h3><details v-for="o in run.inputs.project_context.engineering.objects" :key="o.id"><summary>{{o.title}}，第 {{o.number}} 次修订</summary><NaturalData :value="o.content"/></details></template>
   <template v-if="run?.inputs?.project_context?.repository"><h3>项目说明文件</h3><MarkdownContent :source="run.inputs.project_context.repository.readme||'没有说明文档'"/><details><summary>查看项目文件（开发者）</summary><ul><li v-for="file in run.inputs.project_context.repository.files||[]" :key="file">{{file}}</li><li v-if="!run.inputs.project_context.repository.files?.length">没有文件信息</li></ul></details><details><summary>查看版本记录（开发者）</summary><pre>{{run.inputs.project_context.repository.history||'没有版本历史'}}</pre></details></template>
  </section>
  <el-form label-position="top" :disabled="busy" class="review-fields">
   <div class="review-section-title">填写结论</div>
   <div v-if="isProperty&&run?.suggestion" class="reference-actions"><el-button :disabled="busy" @click="fillReference">补充空白字段</el-button><el-button plain :disabled="busy||!referenceFilled.length" @click="clearReference">撤销参考补全</el-button><span v-if="referenceFilled.length">已补充 {{referenceFilled.length}} 项</span></div>
   <details class="student-reference"><summary>查看写法示例</summary><p>不充分：{{studentLessons[activeStep].bad}}</p><p>更具体：{{studentLessons[activeStep].good}}</p></details>
    <el-form-item v-for="([key,schema]) in fieldEntries" :key="key" :label="schema.title" :required="needsValue(schema)"><el-select :aria-label="schema.title" v-if="schema.enum" v-model="fields[key]"><el-option v-for="v in schema.enum" :key="v" :value="v" :label="enumNames[v]||v"/></el-select><TextEntries v-else-if="schema.type==='array'&&schema.items?.type!=='array'" v-model="fields[key]" :label="schema.title" :placeholder="`添加${schema.title}`"/><el-input v-else-if="schema.type==='array'" :aria-label="schema.title" v-model="fields[key]" type="textarea" :rows="3"/><el-input v-else :aria-label="schema.title" v-model="fields[key]"/><span v-if="schema.description" class="field-help">{{schema.description}}</span></el-form-item>
   <div class="review-check-panel"><div class="review-section-title review-check-title">确认质量</div><el-checkbox v-for="(c,i) in skill?.checklist" :key="c" v-model="checks[Number(i)]" class="review-check">{{c}}</el-checkbox></div>
  </el-form>
 </div>
 <template #footer><div class="review-remain" role="status"><span v-if="missingFields.length">未完成：{{missingFields.join('、')}}</span><span v-else-if="checks.some(x=>!x)">还有 {{checks.filter(x=>!x).length}} 项待确认</span><small v-if="!draftStored">当前浏览器无法暂存。</small></div><el-button :disabled="busy" @click="reviewOpen=false">暂存并关闭</el-button><el-button :disabled="busy" type="danger" plain @click="finish('reject')">放弃</el-button><el-button type="primary" :loading="busy" :disabled="!canFinish" @click="finish('accept')">确认并进入下一步</el-button></template>
</el-dialog>
<el-dialog v-model="evidenceOpen" :title="'为“'+project?.name+'”添加原始证据'" :close-on-click-modal="false" :before-close="reviewClose"><el-alert v-if="error" :title="error" type="error" :closable="false"/><el-form label-position="top"><el-form-item label="标题"><el-input v-model="evidenceForm.title"/></el-form-item><el-form-item label="类型"><el-select v-model="evidenceForm.type"><el-option v-for="t in evidenceTypes" :key="t.value" :value="t.value" :label="t.label"/></el-select></el-form-item><el-form-item label="内容"><el-input v-model="evidenceForm.content" type="textarea" :rows="8"/></el-form-item></el-form><template #footer><span>未保存内容只在此项目和当前标签页保留。</span><el-button :disabled="busy" @click="evidenceOpen=false">暂存并关闭</el-button><el-button type="primary" :loading="busy" :disabled="busy||!evidenceForm.title.trim()||!evidenceForm.content.trim()" @click="saveEvidence">保存证据</el-button></template></el-dialog>
<el-dialog v-model="runtimeOpen" title="录入变更后运行证据" :close-on-click-modal="false" :before-close="reviewClose"><el-alert v-if="error" :title="error" type="error" :closable="false"/><el-form label-position="top"><el-form-item label="对应验证"><el-select v-model="runtimeForm.verification_id"><el-option v-for="v in artifacts.filter(x=>x.kind==='Verification')" :key="v.id" :label="v.title" :value="v.id"/></el-select></el-form-item><el-form-item label="标题"><el-input v-model="runtimeForm.title"/></el-form-item><el-form-item label="观察"><el-input v-model="runtimeForm.content" type="textarea"/></el-form-item><NumberEntries v-model="runtimeForm.metrics" label="运行指标（可选）"/></el-form><template #footer><el-button type="primary" :loading="busy" :disabled="busy||!runtimeForm.metrics||!runtimeForm.title.trim()||!runtimeForm.content.trim()||!runtimeForm.verification_id" @click="saveRuntime">保存运行证据</el-button></template></el-dialog>
<el-drawer v-model="helpOpen" title="软件工程学习与操作指南" size="560px"><h2>用多轮迭代持续完成软件改进</h2><p>每轮都从证据出发，依次完成需求、设计、修改、验证和复盘。第一轮交付最小可用原型，第二轮进行前向部署与用户访谈，第三轮从数据中获取需求，第四轮进入包含业务变更的运行与维护。</p><ol class="help-list"><li v-for="(name,id) in stages" :key="id"><b>{{name}}</b><span>{{id==='specification'?'在同一阶段完成需求分析、规则修订、原型体验与需求协商。':id==='engineering-intent'?'工程意图与带业务理由的设计约束放在一起。':id==='verification'?'同时查看变更约定与基于当前规则的真实复验。':id==='runtime-outcome'?'记录现场观察，关联当前真实证据，并人工确认下一步。':id==='next-change'?'查看统一追溯和工程实践记录。':guideText[id]?.goal}}</span></li></ol><h3>阶段任务</h3><ul class="help-list"><li v-for="(item,id) in stageGuidance" :key="id"><b>{{stages[id]}}</b><span>{{item.done}}</span></li></ul><h3>如何开始？</h3><p>首页可进入物业管理完整示例，或创建自己的项目。所有项目至少安排四轮迭代，每轮都使用同一套八阶段流程；自定义项目还可调整迭代轮数、周期和各轮目标。</p><h3>为什么结果失效？</h3><p>新需求不能直接沿用旧结论。请核对当前需求版本、代码与测试对应关系，再执行真实复验。原型用于核对需求；代码测试检查实现；现场观察用于判断使用效果。</p></el-drawer>
<el-drawer v-model="traceOpen" title="项目全过程追溯" size="70%"><AgentRunTrace :runs="runs" :suggestions="suggestions" :artifacts="artifacts"/><h2>分析与确认记录</h2><div class="trace-row" v-for="o in artifacts" :key="o.id"><span>{{o.sources.map(id=>artifacts.find(x=>x.id===id)?.title||'已有项目记录').join('、')||'原始输入'}}</span><b>→</b><button>{{labels[o.kind]||'工程记录'}}，{{o.title}}</button></div><h2>规则、代码与测试</h2><div v-for="o in engineeringTrace.objects" :key="o.id" class="trace-row"><span>{{o.title}}</span><b>→</b><span>第 {{o.number}} 次修订</span></div><h2>当前关系</h2><NaturalData :value="engineeringTrace.relations"/><h2>版本与操作记录</h2><p>时间均为北京时间。</p><details v-for="e in engineeringTrace.events" :key="e.id"><summary>{{formatDateTime(e.created_at)}}，{{naturalScalar(e.kind)}}</summary><NaturalData :value="e.details"/></details></el-drawer>
<el-button v-if="projectId&&activeStep==='problem-evidence'" class="floating-evidence" @click="openEvidence">添加原始证据</el-button>
</template>
