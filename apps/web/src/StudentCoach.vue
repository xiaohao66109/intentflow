<script setup lang="ts">
import {computed,nextTick,onMounted,ref,watch} from 'vue'
import {studentLessons,reflectionFeedback,gradeLearningRecord,learningAnswerGuide,learningSample,type LearningGrade} from './studentGuide'
import {stages} from './journey'
import {readSession,writeSession,removeSession} from './session'
import './student.css'

const props=defineProps<{projectId:string;stage:string;example:boolean;property:boolean;artifacts:any[];repository?:string;busy?:boolean}>()
const emit=defineEmits<{(e:'action',action:string):void;(e:'material',id:string):void;(e:'navigate',stage:string):void;(e:'changed'):void}>()
const lesson=computed(()=>studentLessons[props.stage])
type GradedAttempt=LearningGrade&{signature:string;submittedAt:string;number:number}
type LearningNote={attempt:string;evidence:string;reflection:string;checked:string[];assessment?:GradedAttempt;attempts?:GradedAttempt[]}
const note=ref<LearningNote>({attempt:'',evidence:'',reflection:'',checked:[],attempts:[]})
const revision=ref(0),loading=ref(true),saving=ref(false),error=ref(''),message=ref(''),feedback=ref<string[]>([]),sampleOpen=ref(false)
const repositoryInput=ref(''),linking=ref(false),draftAvailable=ref(true)
const key=`student:${props.projectId}:${props.stage}`
const current=computed(()=>props.artifacts.filter(a=>a.current_iteration!==false&&a.current_result!==false))
const formalKinds:Record<string,string[]>={'project-context':['Context'],'problem-evidence':['Problem'],specification:['Specification'],'engineering-intent':['EngineeringIntent'],'software-change':['ChangeRecord'],verification:['Verification'],'runtime-outcome':['EngineeringEvaluation']}
const formal=computed(()=>current.value.some(a=>(formalKinds[props.stage]||[]).includes(a.kind)))
const materialList=computed(()=>lesson.value.materials.map(title=>props.artifacts.find(a=>a.kind==='Evidence'&&a.title===title)).filter(Boolean))
const stageIndex=computed(()=>Object.keys(stages).indexOf(props.stage))
const nextStage=computed(()=>Object.keys(stages)[stageIndex.value+1])
const answerSteps=computed(()=>learningAnswerGuide(props.stage))
const sample=computed(()=>learningSample(props.stage))
const actionNames:Record<string,string>={'project-context':'打开项目理解表单','problem-evidence':'打开问题分析表单',specification:'打开需求填写表单','engineering-intent':'打开设计填写表单','software-change':'定位代码变更操作',verification:'定位测试与复验操作','runtime-outcome':'定位运行观察与评估','next-change':'查看本轮追溯记录'}
const plainChecks:Record<string,{label:string;help:string}>={
 '指标有口径和来源':{label:'我清楚这些数据从哪里来、怎么计算',help:'例如说明使用哪批工单、统计时间范围、分母和计算方式。'},
 '区分测试结果与实际效果':{label:'我能分清测试现象和真实业务效果',help:'测试通过只说明已覆盖场景正确，不能直接证明真实催办量或满意度改善。'},
 '下一步决策与证据强度一致':{label:'我确认现有证据足以支持下一步判断',help:'证据不足时应继续观察，不能把模拟结果写成真实业务结论。'},
}
const selfChecks=computed(()=>lesson.value.checks.map((text,index)=>({id:`${props.stage}:${index+1}`,label:plainChecks[text]?.label||text,help:plainChecks[text]?.help||`请用本阶段的材料或操作结果说明“${text}”。`,legacy:text})))
function normalizeNote(value:any):LearningNote{const attempts=Array.isArray(value?.attempts)?value.attempts.filter((item:any)=>typeof item?.number==='number'):[];const assessment=typeof value?.assessment?.number==='number'?value.assessment:attempts.at(-1);const saved=Array.isArray(value?.checked)?value.checked:[];const checked=selfChecks.value.filter(item=>saved.includes(item.id)||saved.includes(item.legacy)).map(item=>item.id);return{attempt:value?.attempt||'',evidence:value?.evidence||'',reflection:value?.reflection||'',checked,attempts,assessment}}
const gradeSignature=computed(()=>JSON.stringify([note.value.attempt,note.value.evidence,note.value.reflection,[...note.value.checked].sort()]))
const assessment=computed(()=>note.value.assessment?.signature===gradeSignature.value?note.value.assessment:undefined)
const gradeAttempts=computed(()=>note.value.attempts||[])
const previousGrade=computed(()=>gradeAttempts.value.length>1?gradeAttempts.value.at(-2):undefined)
const scoreChange=computed(()=>assessment.value&&previousGrade.value?assessment.value.score-previousGrade.value.score:0)
async function request(path:string,method='GET',body?:unknown){
 const response=await fetch(`/api/projects/${props.projectId}${path}`,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)})
 const result=await response.json();if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'保存失败，请核对输入后重试。');return result
}
onMounted(async()=>{
 try{
  const notes=await request('/learning');const stored=notes.find((n:any)=>n.stage===props.stage)
  if(stored){note.value=normalizeNote(stored.content);revision.value=stored.revision}
  const draft=readSession<{note:typeof note.value;revision:number}>(key)
  if(draft){note.value=normalizeNote(draft.note);revision.value=draft.revision;message.value='已恢复此标签页未保存的学习记录。'}
 }catch(e){error.value=(e as Error).message}finally{loading.value=false}
})
watch(note,()=>{if(!loading.value){draftAvailable.value=writeSession(key,{note:note.value,revision:revision.value});message.value='有未保存修改；点击保存可随项目长期保留。';feedback.value=[]}},{deep:true,flush:'sync'})
async function save(){
 if(saving.value||loading.value)return;saving.value=true;error.value=''
 try{const result=await request(`/learning/${props.stage}`,'PUT',{revision:revision.value,content:note.value});revision.value=result.revision;removeSession(key);message.value='学习记录已保存到此项目，重新打开仍可继续。'}
 catch(e){error.value=(e as Error).message}finally{saving.value=false}
}
async function submitGrade(){
 const result=gradeLearningRecord(props.stage,note.value.attempt,note.value.evidence,note.value.reflection,note.value.checked.length,selfChecks.value.length)
 const record:GradedAttempt={...result,signature:gradeSignature.value,submittedAt:new Date().toISOString(),number:gradeAttempts.value.length+1}
 note.value.assessment=record
 note.value.attempts=[...gradeAttempts.value,record]
 feedback.value=[]
 await save()
}
const attemptField=ref<HTMLTextAreaElement>(),evidenceField=ref<HTMLTextAreaElement>(),reflectionField=ref<HTMLTextAreaElement>()
async function focusQuestion(id:'attempt'|'evidence'|'reflection'){
 await nextTick();const target={attempt:attemptField.value,evidence:evidenceField.value,reflection:reflectionField.value}[id]
 target?.scrollIntoView({behavior:'smooth',block:'center'});target?.focus()
}
async function link(){
 if(!repositoryInput.value.trim()||linking.value)return;linking.value=true;error.value=''
 try{await request('/repository','POST',{repository:repositoryInput.value.trim()});emit('changed');message.value='仓库已连接，请确认已有初始提交。'}catch(e){error.value=(e as Error).message}finally{linking.value=false}
}
</script>

<template>
 <section class="student-coach" aria-label="学生学习导航">
  <div class="student-heading"><div><span class="student-kicker">{{example?'示例带练':'自建项目学习支架'}} · 第 {{stageIndex+1}} / 8 阶段</span><h2>{{lesson.question}}</h2></div><span class="student-time">建议 {{lesson.minutes}}</span></div>
  <details class="course-start" :open="stage==='project-context'&&!revision"><summary>开始前：学习目标与准备</summary><p>本轮练习把一个有证据的问题，转成可验收需求，完成设计、代码修改、测试与效果评估。先修：基本编程、文件与函数；进入代码阶段需了解 Git 提交和测试命令。</p><p>{{property?'物业示例已准备代码、访谈和测试，可先在网页内跟做。完整带练建议分 3–4 次完成，每次约 45–60 分钟。':'自建项目建议第一轮只选择一条业务流程。不会 Git 或暂时没有代码时，可先完成前四阶段；进入实现前需准备可运行仓库。'}}时间为学习安排建议，可按自己的节奏暂停。</p><p>{{example?'案例学习记录可按四项公开标准批改；分数用于指出缺漏，不代替教师判断。':'阶段成果记录工程进度；下面的检查用于完善学习记录，不自动判定是否掌握。'}}</p></details>
  <p class="student-concept">{{lesson.concept}}</p>
  <ol class="student-steps"><li v-for="(step,index) in (example?lesson.steps:lesson.ownSteps)" :key="step"><span>{{index+1}}</span><div>{{step}}</div></li></ol>
  <div v-if="materialList.length" class="student-reading"><b>本阶段先读（按顺序）</b><button v-for="(material,index) in materialList" :key="material.id" @click="emit('material',material.id)">{{index+1}}. {{material.title}}</button></div>
  <p class="student-deliverable"><b>本步交付：</b>{{lesson.deliverable}}</p>
  <div class="student-actions">
   <el-button :disabled="busy" @click="emit('action',stage==='next-change'?'trace':'work')">{{actionNames[stage]}}</el-button>
   <el-button v-if="!example&&['project-context','problem-evidence'].includes(stage)" :disabled="busy" @click="emit('action','evidence')">添加原始证据</el-button>
   <el-button v-if="property&&stage==='problem-evidence'" @click="emit('action','experiment')">定位初始问题复现</el-button>
   <el-button v-if="property&&stage==='specification'" @click="emit('action','experiment')">定位报修角色带练</el-button>
   <el-button v-if="property&&stage==='runtime-outcome'" @click="emit('action','experiment')">定位工单回放</el-button>
  </div>
  <p class="student-status">{{formal?'本阶段已有工程记录，请继续核对操作结果与学习自查。':'本阶段尚无对应工程记录；学习笔记不会代替正式需求或验证结果。'}}</p>
  <details v-if="!example&&!repository&&['project-context','engineering-intent','software-change'].includes(stage)" class="student-support"><summary>没有代码仓库，怎样继续？</summary><p>前四阶段可以先做分析。进入代码阶段前：在开发工具中建立项目，编写一个可运行入口和测试，初始化版本库并完成首次提交，然后连接本地仓库。</p><details><summary>查看初始化命令（开发者）</summary><pre>git init
git add .
git commit -m "建立可运行的初始版本"</pre></details><p>提交前检查将纳入的文件，排除密钥和不应入库的数据。测试命令应先在项目目录独立运行成功。</p><label>本地版本库路径<input v-model="repositoryInput" aria-label="本地版本库路径" placeholder="例如：项目所在文件夹" :disabled="linking"/></label><el-button :loading="linking" :disabled="!repositoryInput.trim()" @click="link">连接我的版本库</el-button></details>
  <details class="student-notebook" :open="!revision||!!assessment"><summary>{{example?'主观题作答与批改':'学习记录'}}</summary>
   <el-alert v-if="error" :title="error" type="error" :closable="false"/>
   <fieldset :disabled="loading||saving"><legend>{{example?'建议先独立作答；需要参考时可查看内置样例':'记录判断与证据'}}</legend>
    <div class="sample-toolbar"><span>样例只用于参考回答结构，不会填入或覆盖你的答案。</span><el-button plain @click="sampleOpen=true">查看示例</el-button></div>
    <label><b>问题一：我的判断</b><span class="question-copy">{{lesson.question}}</span><span class="answer-guide"><b>建议按顺序回答</b><span v-for="(step,index) in answerSteps.attempt" :key="step">{{index+1}}. {{step}}</span></span><textarea ref="attemptField" v-model="note.attempt" aria-label="我的判断" rows="4" maxlength="10000" placeholder="按上面的三个小步骤组织答案。"/></label>
    <label><b>问题二：证据与判断的对应关系</b><span class="question-copy">哪些材料或操作结果支持你的判断？它们分别说明了什么？</span><span class="answer-guide"><b>建议按顺序回答</b><span v-for="(step,index) in answerSteps.evidence" :key="step">{{index+1}}. {{step}}</span></span><textarea ref="evidenceField" v-model="note.evidence" aria-label="证据与判断的对应关系" rows="4" maxlength="10000" placeholder="材料或操作结果 → 可核对事实 → 支持的判断。"/></label>
    <label><b>问题三：反思与下一步</b><span class="question-copy">{{lesson.reflection}}</span><span class="answer-guide"><b>建议按顺序回答</b><span v-for="(step,index) in answerSteps.reflection" :key="step">{{index+1}}. {{step}}</span></span><textarea ref="reflectionField" v-model="note.reflection" aria-label="我的反思与下一步" rows="4" maxlength="10000" placeholder="未知内容 → 验证方法 → 可能改变判断的结果。"/></label>
    <template v-if="!example||gradeAttempts.length"><details v-for="(hint,index) in lesson.hints" :key="hint" class="student-hint"><summary>提示 {{index+1}}</summary><p>{{hint}}</p></details></template>
    <details v-if="!example||gradeAttempts.length>=1" class="student-hint"><summary>查看写法对比</summary><div class="student-examples"><div><b>不充分</b><p>{{lesson.bad}}</p></div><div><b>更具体</b><p>{{lesson.good}}</p></div></div></details>
    <div class="student-selfcheck"><b>学习自查（请用自己的成果逐项说明）</b><div v-for="check in selfChecks" :key="check.id" class="selfcheck-row"><label><input v-model="note.checked" type="checkbox" :value="check.id"/><span>{{check.label}}</span></label><details class="check-help"><summary :aria-label="`查看${check.label}的说明`">?</summary><span>{{check.help}}</span></details></div></div>
   </fieldset>
   <div class="student-actions"><el-button v-if="!example" :disabled="loading||saving" @click="feedback=reflectionFeedback(note.attempt,note.evidence,note.reflection)">检查我的记录</el-button><el-button v-else type="primary" :loading="saving" :disabled="loading" @click="submitGrade">提交案例批改</el-button><el-button :type="example?'default':'primary'" :loading="saving" :disabled="loading" @click="save">保存本阶段学习记录</el-button></div>
   <ul v-if="feedback.length" class="student-feedback" role="status"><li v-for="item in feedback" :key="item">{{item}}</li></ul>
   <div v-if="assessment" class="grading-card" role="status"><div class="grading-score"><strong>{{assessment.score}}</strong><div><b>第 {{assessment.number}} 次：{{assessment.level}}</b><span>三道题合计 100 分；四项能力维度用于解释原因</span><span v-if="previousGrade" :class="{'score-up':scoreChange>0}">{{scoreChange>=0?'+':''}}{{scoreChange}} 分</span></div></div><section class="question-grades" aria-label="逐题批改结果"><article v-for="item in assessment.questions||[]" :key="item.id"><div><b>{{item.title}}：{{item.score}} / {{item.maximum}}</b><span>{{item.status}}</span></div><p>{{item.comment}}</p><el-button plain @click="focusQuestion(item.id)">返回修改{{item.title.split(/[：:]/)[0]}}</el-button></article></section><details class="dimension-details"><summary>查看四项能力维度</summary><div class="grading-dimensions"><div v-for="item in assessment.dimensions" :key="item.name"><b>{{item.name}}：{{item.score}} / 25</b><span>{{item.comment}}</span></div></div></details><p class="grading-next"><b>下一步：</b>{{assessment.next}}</p><p class="grading-source"><b>建议核对：</b>{{assessment.sourceHint}}</p><details v-if="assessment.number>=2" class="grading-reference"><summary>查看案例参考要点</summary><ul><li v-for="point in assessment.referencePoints" :key="point">{{point}}</li></ul></details></div>
   <el-alert v-else-if="example&&note.assessment" title="学习记录已修改，请重新提交批改。" type="warning" :closable="false"/>
   <p role="status" class="student-save">{{loading?'正在读取学习记录…':message}}<span v-if="!draftAvailable">浏览器暂存不可用，请及时保存到项目。</span></p>
  </details>
  <el-dialog v-model="sampleOpen" title="内置作答样例" width="720px" class="sample-dialog" append-to-body>
   <p class="sample-notice">以下内容展示回答结构。请结合自己的材料和判断作答；关闭弹窗后，原输入保持不变。</p>
   <div class="sample-answer-list">
    <article><h3>问题一：我的判断</h3><p>{{sample.attempt}}</p></article>
    <article><h3>问题二：证据与判断的对应关系</h3><p>{{sample.evidence}}</p></article>
    <article><h3>问题三：反思与下一步</h3><p>{{sample.reflection}}</p></article>
   </div>
   <template #footer><el-button type="primary" @click="sampleOpen=false">关闭示例</el-button></template>
  </el-dialog>
  <div class="student-next"><p>{{stage==='next-change'?'完成迁移练习后，可带着新证据返回问题分析，开启下一轮。':'完成本步交付并自查后，可以预习下一阶段；正式操作仍需满足前置条件。'}}</p><el-button v-if="nextStage" :disabled="busy" @click="emit('navigate',nextStage)">预习下一阶段：{{stages[nextStage]}}</el-button><el-button v-else :disabled="busy" @click="emit('navigate','problem-evidence')">带着新问题开始下一轮</el-button></div>
 </section>
</template>
