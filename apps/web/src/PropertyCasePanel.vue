<script setup lang="ts">
import {computed,onMounted,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import BusinessTimeInput from './BusinessTimeInput.vue'
import {formatClock,formatDateTime} from './presentation'
import './property.css'
import {prototypeSteps,prototypeProgress} from './prototypeGuide'
import {readSession,removeSession,writeSession} from './session'
import NaturalData from './NaturalData.vue'
import MarkdownContent from './MarkdownContent.vue'
const props=defineProps<{projectId:string;stage:string;artifacts:any[]}>()
const emit=defineEmits<{(e:'changed'):void;(e:'navigate',stage:string):void}>()
const state=ref<any>({actors:[],statuses:{},drafts:[],specification_id:''})
const busy=ref(false),error=ref(''),sessionId=ref(''),feedback=ref(''),materialId=ref(''),materialsOpen=ref(false)
const patch=ref(''),patchReviewed=ref(false),decision=ref('display'),reason=ref('只展示已填写信息，保持责任边界；短信和自动承诺留到后续评估。')
const action=ref({actor:'resident-a',event:'submit',ticket_id:'',title:'厨房漏水',location:'1 栋 201',assignee:'worker-a',at:540,contact_at:630,result:''})
const materials=computed(()=>props.artifacts.filter(a=>a.kind==='Evidence'))
const material=computed(()=>materials.value.find(a=>a.id===materialId.value))
const currentArtifacts=computed(()=>props.artifacts.filter(a=>a.current_iteration!==false&&a.current_result!==false&&a.status==='CONFIRMED'))
const specification=computed(()=>[...currentArtifacts.value].reverse().find((a:any)=>a.kind==='Specification'))
const intent=computed(()=>[...currentArtifacts.value].reverse().find((a:any)=>a.kind==='EngineeringIntent'))
const sessions=computed(()=>state.value.drafts.filter((d:any)=>d.kind==='PROPERTY_PROTOTYPE').slice().reverse())
const session=computed(()=>sessions.value.find((d:any)=>d.id===sessionId.value))
const checks=computed(()=>state.value.drafts.filter((d:any)=>d.kind==='PROPERTY_CHECK').slice().reverse())
const decisions=computed(()=>state.value.drafts.filter((d:any)=>d.kind==='PROPERTY_DECISION').slice().reverse())
const replays=computed(()=>props.artifacts.filter(a=>a.kind==='RuntimeEvidence'&&a.data.after).slice().reverse())
const currentReplay=computed(()=>replays.value.find(a=>a.current_iteration!==false))
const verified=computed(()=>props.artifacts.some(a=>a.kind==='Verification'&&a.current_iteration!==false&&a.data.status==='PASS'))
const hasChange=computed(()=>props.artifacts.some(a=>a.kind==='ChangeRecord'&&a.current_iteration!==false&&a.data.status==='OPEN'))
const role=computed(()=>state.value.actors.find((a:any)=>a.id===action.value.actor)?.role||'resident')
const currentSession=computed(()=>!!session.value&&!!state.value.specification_id&&session.value.content.specification_id===state.value.specification_id)
const tickets=computed(()=>(session.value?.content.state.tickets||[]).filter((t:any)=>role.value==='dispatcher'||(role.value==='resident'?t.owner===action.value.actor:t.assignee===action.value.actor)))
const selectedTicket=computed(()=>tickets.value.find((t:any)=>t.id===action.value.ticket_id))
const names:Record<string,string>={submit:'提交报修',accept:'受理报修',assign:'派单',start:'开始处理',set_contact:'填写联系时间',complete:'提交维修结果',close:'确认维修完成',cancel:'取消报修',reopen:'申请继续处理',view:'查看详情'}
const options:Record<string,string>={display:'展示已填写的预计时间',sms:'后续增加短信提醒',promise:'自动承诺一小时内上门'}
const decisionKey=()=>`property-decision:${props.projectId}`
function restoreDecision(){const saved=readSession<{decision:string;reason:string}>(decisionKey());if(saved){decision.value=saved.decision;reason.value=saved.reason}}
watch([decision,reason],()=>writeSession(decisionKey(),{decision:decision.value,reason:reason.value}),{flush:'sync'})
const events=computed(()=>role.value==='resident'?['submit','view','cancel','close','reopen']:role.value==='dispatcher'?['accept','assign']:['start','set_contact','complete'])
const actorName=(id:string)=>state.value.actors.find((a:any)=>a.id===id)?.name||'未分派'

const tutorTicket=computed(()=>session.value?.content.state.tickets.find((t:any)=>t.owner==='resident-a'))
const tutorIndex=computed(()=>prototypeProgress(session.value?.content.events||[],tutorTicket.value?.id||''))
const tutor=computed(()=>prototypeSteps[tutorIndex.value])
const prediction=ref(''),tutorPrepared=ref(false)
watch([sessionId,tutorIndex],()=>{prediction.value=readSession<string>(`prediction:${props.projectId}:${sessionId.value}:${tutorIndex.value}`)||'';tutorPrepared.value=false},{immediate:true})
watch(prediction,()=>{if(sessionId.value)writeSession(`prediction:${props.projectId}:${sessionId.value}:${tutorIndex.value}`,prediction.value)})
function prepareTutor(){
 if(!tutor.value||!currentSession.value)return
 action.value={...action.value,actor:tutor.value.actor,ticket_id:tutorTicket.value?.id||'',assignee:'worker-a',at:Math.max(540,...(session.value?.content.events||[]).map((e:any)=>e.at)),contact_at:630,result:tutor.value.event==='complete'&&tutor.value.accepted?'更换厨房阀门，漏水停止。':''}
 tutorPrepared.value=true
}
async function performTutor(){if(tutor.value&&prediction.value.trim()&&tutorPrepared.value&&!busy.value)await perform(tutor.value.event)}

async function api(path:string,method='GET',body?:any){const r=await fetch(`/api/projects/${props.projectId}/property${path}`,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});const value=await r.json();if(!r.ok)throw new Error(typeof value.detail==='string'?value.detail:'请核对输入后重试');return value}
async function act(fn:()=>Promise<void>){if(busy.value)return;busy.value=true;error.value='';try{await fn()}catch(e:any){if(e!=='cancel'&&e!=='close'){error.value=e.message;ElMessage.error(e.message)}}finally{busy.value=false}}
async function reload(){const id=props.projectId;const value=await api('');if(id!==props.projectId)return;state.value=value;if(!sessions.value.some((d:any)=>d.id===sessionId.value))sessionId.value=sessions.value[0]?.id||''}
async function begin(){await act(async()=>{const d=await api('/prototypes','POST',{specification_id:state.value.specification_id});sessionId.value=d.id;action.value={actor:'resident-a',event:'submit',ticket_id:'',title:'厨房漏水',location:'1 栋 201',assignee:'worker-a',at:540,contact_at:630,result:''};feedback.value='报修体验已开始，先以居民身份提交一条报修。';await reload()})}
async function perform(event:string){await act(async()=>{const r=await api(`/prototypes/${sessionId.value}/actions`,'POST',{...action.value,event});feedback.value=(r.accepted?'操作成功：':'操作未接受：')+r.reason;await reload();if(event==='submit'&&r.accepted)action.value.ticket_id=r.session.content.state.tickets.at(-1).id})}
defineExpose({showMaterial})
function showMaterial(id:string){materialId.value=id;materialsOpen.value=true}
async function saveDecision(){await act(async()=>{await api('/decisions','POST',{specification_id:state.value.specification_id,option:decision.value,reason:reason.value});removeSession(decisionKey());decision.value='display';reason.value='只展示已填写信息，保持责任边界；短信和自动承诺留到后续评估。';await reload();ElMessage.success('方案讨论已记录；如改变范围，请同步修改需求。')})}
async function preview(){await act(async()=>{patch.value=(await api('/change-preview')).diff;patchReviewed.value=false;if(!patch.value)ElMessage.info('当前代码已经包含该参考修改')})}
async function apply(){await act(async()=>{await ElMessageBox.confirm('将只修改 readmodel.py 的联系时间展示并创建代码提交。之后仍需执行验证。','应用已审阅的参考修改',{confirmButtonText:'应用修改并提交'});await api('/apply-fix','POST',{confirmed:true});patch.value='';patchReviewed.value=false;emit('changed');ElMessage.success('修改已提交，请执行本轮验证。')})}
async function baseline(){await act(async()=>{await ElMessageBox.confirm('将在初始版本的临时副本中运行项目测试。','复现初始问题',{confirmButtonText:'运行初始测试'});await api('/baseline-check','POST',{confirmed:true});await reload()})}
async function replay(){await act(async()=>{await ElMessageBox.confirm('将运行修改前后两个已提交版本，对同一批模拟工单比较结果，并保存为本轮运行证据。','回放工单并记录结果',{confirmButtonText:'运行并保存'});await api('/replay','POST',{confirmed:true});emit('changed');ElMessage.success('回放完成，已保存前后对比和代码版本。')})}
watch(()=>props.projectId,()=>{sessionId.value='';feedback.value='';patch.value='';patchReviewed.value=false;state.value={actors:[],statuses:{},drafts:[],specification_id:''};restoreDecision();act(reload)})
watch(()=>props.artifacts,()=>act(reload))
onMounted(()=>{restoreDecision();act(reload)})
</script>

<template>
<section class="property-case" v-loading="busy" element-loading-text="正在处理，请稍候…" :aria-busy="busy" aria-label="物业管理示例">
 <el-alert v-if="error" :title="error" type="error" :closable="false"/>
 <article class="property-brief"><div><span class="case-label">青禾社区物业服务</span><h2>让居民看清报修进度和联系安排</h2><p>从一条“已派单却不知道几点联系”的反馈出发，完成问题分析、需求确认、角色体验、代码修改、验证和效果评估。</p></div><div class="case-facts"><span><b>{{materials.length}}</b>份项目材料</span><span><b>12</b>条模拟工单</span><span><b>5</b>个操作身份</span><span><b>14</b>项项目测试</span></div><p class="case-source">人员、访谈和工单均为虚构场景；回放结果来自实际运行的案例代码。</p></article>
 <details class="property-materials" :open="stage==='project-context'||stage==='problem-evidence'"><summary>项目资料室</summary><p>先阅读项目背景、角色职责和访谈，再对照工单与日志判断问题。所有材料可随时返回查看。</p><div class="material-grid"><button v-for="m in materials" :key="m.id" @click="showMaterial(m.id)"><b>{{m.title}}</b><span>阅读材料</span></button></div></details>
 <article v-if="stage==='problem-evidence'" class="property-card"><h3>先复现，再判断原因</h3><p>初始代码已支持报修流转和时间填写，但居民详情遗漏了联系时间。运行初始版本测试，查看哪些行为通过、哪些验收失败。</p><el-button @click="baseline">运行初始版本测试</el-button><details v-for="r in checks" :key="r.id"><summary>{{formatDateTime(r.created_at)}}，{{r.content.exit_code===0?'初始测试通过':'初始测试存在失败'}}</summary><p>{{r.content.exit_code===0?'所有初始检查均已通过。':'初始检查发现未满足的行为，请结合问题材料继续分析。'}}</p><details><summary>查看测试技术输出（开发者）</summary><pre>{{r.content.output}}</pre></details></details></article>
 <template v-if="stage==='specification'">
  <article class="property-card"><h3>用不同身份走完报修流程</h3><p>确认本阶段的需求草稿后开始体验。按居民、客服、维修人员、居民的顺序切换身份；也可以尝试越权、漏填结果和派单后取消，观察系统反馈。</p><el-button type="primary" :disabled="!state.specification_id" @click="begin">开始报修流程体验</el-button><p v-if="!state.specification_id">请先通过上方“开始形成需求规格”确认需求与验收标准。</p>
   <label v-if="sessions.length" class="property-field">体验记录<select v-model="sessionId"><option v-for="s in sessions" :key="s.id" :value="s.id">{{formatDateTime(s.created_at)}}，{{s.content.events.length}} 次操作{{s.content.specification_id===state.specification_id?'':'（历史需求）'}}</option></select></label>
   <template v-if="session"><el-alert v-if="!currentSession" title="需求已更新，此记录只供回顾。请开始新的报修体验。" type="warning" :closable="false"/>
    <section v-if="currentSession" class="prototype-tutor" aria-label="报修逐步带练"><template v-if="tutor"><span>角色实验 {{tutorIndex+1}} / {{prototypeSteps.length}}</span><h4>{{tutor.title}}</h4><p>{{tutor.question}}</p><label>本步操作预测<textarea v-model="prediction" rows="2" placeholder="先预测会成功还是被拒绝，并写明理由。"/></label><div class="student-actions"><el-button :disabled="busy||!prediction.trim()" @click="prepareTutor">准备本步角色与输入</el-button><el-button type="primary" :disabled="busy||!tutorPrepared||!prediction.trim()" @click="performTutor">执行本步操作</el-button></div><p>先写预测，再准备角色和输入；准备不会提交操作。也可在下方手动修改，观察边界行为。</p><details><summary>需要提示：这一步在验证什么？</summary><p>{{tutor.why}}</p></details></template><template v-else><h4>正常与边界场景带练已完成</h4><p>你已按顺序走过 {{prototypeSteps.length}} 个场景。请对照预测解释越权、派单后取消和空结果提交为什么被拒绝，再在下方保存方案讨论。操作完成不等于已经掌握。</p></template><details><summary>查看全部实验步骤与进度</summary><ol class="tutor-step-list"><li v-for="(step,index) in prototypeSteps" :key="index" :class="{completed:index<tutorIndex}">{{step.title}} · {{index<tutorIndex?'已有匹配操作记录':index===tutorIndex?'当前步骤':'待体验'}}</li></ol></details></section><div class="property-form"><label>当前操作身份<select v-model="action.actor" aria-label="当前操作身份"><option v-for="a in state.actors" :key="a.id" :value="a.id">{{a.name}}（{{({resident:'居民',dispatcher:'客服',worker:'维修人员'} as any)[a.role]}}）</option></select></label><label>报修单编号<input v-model="action.ticket_id" placeholder="提交后自动填入编号"/></label><BusinessTimeInput v-model="action.at" label="本次操作时间"/>
     <template v-if="role==='resident'"><label>报修内容<input v-model="action.title"/></label><label>报修位置<input v-model="action.location"/></label></template><label v-if="role==='dispatcher'">指派维修人员<select v-model="action.assignee"><option value="worker-a">王师傅</option><option value="worker-b">赵师傅</option></select></label><BusinessTimeInput v-if="role==='worker'" v-model="action.contact_at" label="预计联系时间"/><label v-if="role!=='dispatcher'">维修结果或继续处理原因<textarea v-model="action.result" rows="2"/></label></div>
    <p class="role-context">当前身份：{{actorName(action.actor)}}；{{selectedTicket?'已选择 '+selectedTicket.id+'，'+state.statuses[selectedTicket.status]:'可从下方列表选择报修单，或填写编号体验边界操作。'}}</p><div class="property-actions"><el-button v-for="event in events" :key="event" :disabled="!currentSession||busy" @click="perform(event)">{{names[event]}}</el-button></div><p v-if="feedback" class="property-feedback" :class="{'feedback-warning':feedback.startsWith('操作未接受')}" role="status" aria-live="polite">{{feedback}}</p>
    <div class="property-table"><table><thead><tr><th>报修单</th><th>内容</th><th>处理状态</th><th>负责人</th></tr></thead><tbody><tr v-for="t in tickets" :key="t.id" :class="{'selected-ticket':t.id===action.ticket_id}"><td><button :aria-pressed="action.ticket_id===t.id" @click="action.ticket_id=t.id">{{t.id}}</button></td><td>{{t.title}}</td><td>{{state.statuses[t.status]}}</td><td>{{actorName(t.assignee)}}</td></tr></tbody></table></div><p v-if="!tickets.length">当前身份暂无可查看的报修单。</p>
    <div v-if="selectedTicket" class="ticket-detail"><h4>{{selectedTicket.id}} 报修详情</h4><p>{{selectedTicket.title}}，{{selectedTicket.location}}</p><p>当前状态：{{state.statuses[selectedTicket.status]}}</p><p v-if="['assigned','processing'].includes(selectedTicket.status)">预计联系时间：{{selectedTicket.expected_contact===null||selectedTicket.expected_contact===undefined?'待维修人员填写':formatClock(selectedTicket.expected_contact)}}</p><p v-if="selectedTicket.result">处理说明：{{selectedTicket.result}}</p><p>这里展示的是需求原型。代码是否实现相同行为，需要后续测试验证。</p></div>
    <details><summary>操作过程（{{session.content.events.length}} 条）</summary><ol><li v-for="(e,i) in session.content.events" :key="i">{{formatClock(e.at)}}，{{actorName(e.actor)}}{{names[e.event]}}：{{e.accepted?'成功':e.reason}}</li></ol></details>
   </template>
  </article>
  <article class="property-card"><h3>讨论本轮做什么、暂缓什么</h3><div class="property-options"><div><b>展示已填写时间</b><p>信息来源明确，修改范围小；离线居民不会收到提醒。</p></div><div><b>增加短信提醒</b><p>需要通知服务、授权、费用和失败处理，适合作为后续需求。</p></div><div><b>自动承诺一小时内上门</b><p>缺少资源和履约依据，不能只靠修改页面作出承诺。</p></div></div><form @submit.prevent="saveDecision"><label class="property-field">本次讨论方案<select v-model="decision"><option v-for="(title,key) in options" :key="key" :value="key">{{title}}</option></select></label><label class="property-field">取舍理由<textarea v-model="reason" rows="3" required/></label><el-button native-type="submit" :disabled="!state.specification_id">保存方案讨论</el-button></form><p>讨论记录不会自动改变正式需求；如果选择扩展范围，请先修改需求再进入设计。</p><div v-for="d in decisions" :key="d.id"><p>{{options[d.content.option]}}：{{d.content.reason}}</p></div></article>
 <el-button type="primary" :disabled="!state.specification_id" @click="emit('navigate','engineering-intent')">继续明确工程设计</el-button>
 </template>
 <article v-if="stage==='engineering-intent'" class="property-card"><h3>明确修改边界和验收方法</h3><div class="property-options"><div><b>允许修改</b><p>readmodel.py 组装的居民详情接口返回数据。</p></div><div><b>保留行为</b><p>本人访问、维修人员权限、工单流转、旧工单兼容。</p></div><div><b>验证依据</b><p>状态回归、权限检查、新增展示验收和同批工单回放。</p></div></div><div class="term-grid"><div><b>表单输入</b><span>用户在页面表单中填写的内容。</span></div><div><b>接口请求参数</b><span>前端调用接口时提交给后端的参数。</span></div><div><b>接口返回字段</b><span>后端读取已有工单并返回给页面的数据。</span></div><div><b>页面展示字段</b><span>前端根据接口返回结果显示的内容。</span></div></div><p><b>readmodel 的职责：</b>读取已有业务数据并组装只读详情，不新增数据库记录、不推测负责人，也不改变工单。</p><p>本阶段设计草稿提供了对应的文件范围和可运行测试命令。请对照你已确认的需求修改并确认。</p></article>
 <article v-if="['software-change','verification'].includes(stage)" class="property-card"><h3>审阅并实现联系时间展示</h3><section class="task-contract" aria-labelledby="task-contract-title"><h4 id="task-contract-title">本次任务需求</h4><p><b>业务问题：</b>维修人员已经填写预计联系时间，但居民详情接口没有返回，居民页面无法显示。</p><div class="task-contract-grid"><div><b>输入</b><span>已有工单数据和当前访问居民身份。</span></div><div><b>输出</b><span>已派单、处理中返回联系时间；未填写或旧工单返回待填写。</span></div><div><b>允许修改</b><span>{{intent?.data?.allowed_scope?.join('、')||'readmodel.py'}}</span></div><div><b>禁止改变</b><span>{{intent?.data?.protected_behavior?.join('、')||'访问权限、填写权限、工单流转和历史兼容'}}</span></div></div><p><b>本次不做：</b>{{specification?.data?.constraints?.join('；')||'不新增数据库写入，不接入短信，不改变派单和状态规则。'}}</p><p><b>验收条件：</b>{{intent?.data?.acceptance_criteria?.join('；')||specification?.data?.success_criteria?.join('；')||'展示、空值、历史数据、终态和越权场景均有明确结果。'}}</p></section><div class="data-flow" aria-label="本次数据流"><b>数据流</b><span>工单中已保存的 expected_contact</span><i>→</i><span>readmodel 读取并返回 contact_time</span><i>→</i><span>居民页面显示预计联系时间</span></div><p class="task-clarification"><b>改动性质：</b>这是补充接口返回和页面展示字段，不是新增数据库字段，也不会写入新的业务数据。</p><p>可以在开发工具中自行修改，也可以审阅参考修改后应用。代码差异只是实现参考，需求以上方当前正式规格和工程意图为准。</p><el-button @click="preview">查看参考修改</el-button><details v-if="patch" open><summary>参考修改的代码差异（开发者）</summary><pre>{{patch}}</pre></details><label v-if="patch" class="property-check"><input v-model="patchReviewed" type="checkbox"/>我已核对修改范围、状态条件和旧工单兼容</label><el-button v-if="patch" type="primary" :disabled="!patchReviewed||!hasChange" @click="apply">应用已审阅的参考修改</el-button><p v-if="!hasChange&&!verified">请先在本轮记录修改前的代码版本。</p></article>
 <article v-if="stage==='runtime-outcome'" class="property-card"><h3>比较同一批工单的修改前后结果</h3><p>使用12条相同模拟工单，检查应显示的6条联系安排、越权读取和终态承诺。回放会运行实际代码并保存为本轮证据。</p><el-button type="primary" :disabled="!verified" @click="replay">回放工单并保存运行证据</el-button><p v-if="!verified">请先通过本轮代码验证。</p><div v-if="currentReplay"><div class="property-table"><table><thead><tr><th>指标</th><th>修改前</th><th>修改后</th><th>本轮目标</th></tr></thead><tbody><tr v-for="metric in [{key:'contact_visible',name:'正确显示联系时间',target:6},{key:'unauthorized_visible',name:'越权读取次数',target:0},{key:'invalid_promises',name:'终态仍显示联系承诺',target:0}]" :key="metric.key"><td>{{metric.name}}</td><td>{{currentReplay.data.before.metrics[metric.key]}}</td><td>{{currentReplay.data.after.metrics[metric.key]}}</td><td>{{metric.target}}</td></tr></tbody></table></div><p>来源：模拟工单回放。记录时间：{{formatDateTime(currentReplay.created_at)}}。真实催办量和满意度仍需现场观察。</p></div></article>
 <article v-if="stage==='next-change'" class="property-card"><h3>回顾本轮，准备下一轮改进</h3><p>核对需求、原型、方案讨论、代码修改、测试和运行对比是否相互对应。下一轮可调查“预计时间已过，居民仍不知道是否应继续等待”的问题。</p><div class="case-facts"><span><b>{{sessions.length}}</b>次角色体验</span><span><b>{{decisions.length}}</b>次方案讨论</span><span><b>{{replays.length}}</b>份回放记录</span></div><el-button @click="emit('navigate','problem-evidence')">返回问题分析，开始下一轮</el-button><details v-for="a in artifacts.filter(a=>a.kind!=='Evidence')" :key="a.id"><summary>{{a.title}}，{{formatDateTime(a.created_at)}}</summary><NaturalData :value="a.data"/></details></article>
</section>
<el-drawer v-model="materialsOpen" :title="material?.title||'项目材料'" size="min(760px,96vw)"><p>来源：虚构场景与模拟数据</p><MarkdownContent :source="material?.data.content||''"/></el-drawer>
</template>
