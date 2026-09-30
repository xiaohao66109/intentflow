<script setup lang="ts">
import {computed} from 'vue'
import NaturalData from './NaturalData.vue'
import {stages} from './journey'
import {formatDateTime} from './presentation'

type Run={id:string;workflow_step:string;mode:string;status:string;created_at:string;inputs?:any;sources?:string[];result_ids?:string[]}
type Suggestion={skill_run_id:string;provider:string;model:string;status:string;output:any;rationale?:string;input_snapshot_hash:string}
type Artifact={id:string;kind:string;title:string;data?:any}
const props=defineProps<{runs:Run[];suggestions:Suggestion[];artifacts:Artifact[];step?:string;pending?:boolean}>()
const visibleRuns=computed(()=>props.runs.filter(run=>run.mode==='llm'&&(!props.step||run.workflow_step===props.step)).slice().reverse())
const suggestionFor=(run:Run)=>props.suggestions.find(item=>item.skill_run_id===run.id)
const resultsFor=(run:Run)=>props.artifacts.filter(item=>(run.result_ids||[]).includes(item.id))
const latestArtifact=(kind:string)=>[...props.artifacts].reverse().find(item=>item.kind===kind)
const sourceTitles=(run:Run)=>{
 const named=(run.inputs?.sources||[]).map((item:any)=>item.title).filter(Boolean)
 return named.length?named.join('、'):'本次未关联独立材料'
}
const runStatus:Record<string,string>={GENERATING:'模型生成中',DRAFT:'候选待审阅',ACCEPTED:'已人工确认',REJECTED:'已人工拒绝',ERROR:'模型调用失败'}
const suggestionStatus:Record<string,string>={GENERATED:'尚待人工确认',ACCEPTED:'原样采纳',EDITED:'人工修改后采纳',REJECTED:'人工拒绝'}
</script>

<template>
 <section class="agent-run-trace" aria-label="智能体运行记录">
  <header><h2>智能体运行记录</h2><span>请求、候选与可核对结果</span></header>
  <p v-if="pending" class="agent-run-pending" role="status">正在整理项目资料并请求智能模型；候选生成后仍需人工确认。</p>
  <p v-if="!visibleRuns.length&&!pending" class="agent-run-empty">本阶段尚无模型运行记录。人工模式的案例参考草稿不代表模型生成结果。</p>
  <article v-for="item in visibleRuns" :key="item.id" class="agent-run-card">
   <div class="agent-run-heading"><div><b>{{stages[item.workflow_step]||item.workflow_step}}</b><small>{{formatDateTime(item.created_at)}}</small></div><span :class="{'agent-run-error':item.status==='ERROR'}">{{runStatus[item.status]||item.status}}</span></div>
   <ol class="agent-run-steps">
    <li><b>1 · 收到任务</b><p>{{item.inputs?.project_context?.project?.description||item.inputs?.project_context?.project?.details?.problem_statement||'项目未填写任务说明'}}</p></li>
    <li><b>2 · 读取资料</b><p>{{sourceTitles(item)}}</p><small v-if="item.inputs?.project_context?.version_basis?.baseline_id">需求版本：{{item.inputs.project_context.version_basis.baseline_id}}</small></li>
    <li><b>3 · 生成候选</b><p v-if="suggestionFor(item)">{{suggestionFor(item)?.provider}} / {{suggestionFor(item)?.model}}；输入摘要 {{suggestionFor(item)?.input_snapshot_hash.slice(0,12)}}</p><p v-else>{{item.status==='ERROR'?'本次调用失败，可重新开始分析。':'模型输出尚未生成。'}}</p><details v-if="suggestionFor(item)"><summary>查看模型候选</summary><NaturalData :value="suggestionFor(item)?.output"/></details><p v-if="suggestionFor(item)?.rationale">可核对依据摘要：{{suggestionFor(item)?.rationale}}</p><p v-else-if="suggestionFor(item)">模型未提供依据摘要，请核对上列来源材料和候选字段。</p></li>
    <li><b>4 · 人工审阅</b><p>{{suggestionFor(item)?suggestionStatus[suggestionFor(item)!.status]||suggestionFor(item)!.status:runStatus[item.status]||item.status}}</p></li>
    <li><b>5 · 正式结果</b><p v-if="resultsFor(item).length">{{resultsFor(item).map(result=>result.title).join('、')}}</p><p v-else>尚无人工确认的正式产物。</p></li>
   </ol>
  </article>
  <section v-if="!step&&visibleRuns.length" class="agent-module-chain" aria-label="模块协同结果">
   <h3>与其他模块的协同</h3>
   <p>模型候选经人工审阅才成为正式产物；代码验证和工单回放由工具独立执行。</p>
   <ul>
    <li><b>人工决策</b><span>{{props.artifacts.filter(item=>['Specification','EngineeringIntent','EngineeringEvaluation'].includes(item.kind)).map(item=>item.title).join('、')||'尚无正式决策'}}</span></li>
    <li><b>工具验证</b><span>{{latestArtifact('Verification')?.title||'尚未执行'}}{{latestArtifact('Verification')?.data?.status?' · '+latestArtifact('Verification')?.data?.status:''}}</span></li>
    <li><b>模拟工单回放</b><span v-if="latestArtifact('RuntimeEvidence')">正确显示联系时间 {{latestArtifact('RuntimeEvidence')?.data?.before?.metrics?.contact_visible??'—'}} → {{latestArtifact('RuntimeEvidence')?.data?.metrics?.contact_visible??'—'}}</span><span v-else>尚未执行</span></li>
   </ul>
  </section>
 </section>
</template>
