<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import {naturalEntries,naturalLabel,naturalScalar} from './naturalData'

type FieldSchema={title:string;type?:string}
type FieldEntry=[string,FieldSchema]
type Source={title:string;content:string}
const props=defineProps<{inputs:any;fieldEntries:FieldEntry[];suggestion:any}>()

const fieldIndex=ref(0),phase=ref(0),hovering=ref(false)
let timer:ReturnType<typeof setInterval>|undefined
const phases=[{title:'明确问题',hint:'先确定这一项要回答什么，不急着抄材料。'},{title:'提取证据',hint:'只记录材料中能直接核对的事实。'},{title:'形成答案',hint:'把多条事实归纳成自己的判断，并保留未知项。'}]
const field=computed(()=>props.fieldEntries[fieldIndex.value]||['',{title:'本阶段结论'}] as FieldEntry)
const sourceList=computed<Source[]>(()=>{
 const inputs=props.inputs||{},result:Source[]=[]
 const project=inputs.project_context?.project
 if(project?.description)result.push({title:'项目说明',content:String(project.description)})
 for(const item of inputs.sources||[])if(typeof item.data?.content==='string')result.push({title:item.title||'原始材料',content:item.data.content})
 const repository=inputs.project_context?.repository
 if(repository?.readme)result.push({title:'仓库说明',content:String(repository.readme)})
 if(repository?.files?.length)result.push({title:'仓库文件',content:repository.files.join('、')})
 return result
})
const fieldRules:Record<string,{question:string;keywords:RegExp;logic:string}>={
 stakeholders:{question:'谁使用系统、谁执行流程、谁会受到变化影响？',keywords:/居民|客服|维修|用户|角色|人员/,logic:'按职责而不是按姓名罗列角色，避免漏掉执行者和受影响者。'},
 system_boundary:{question:'系统负责什么？本轮明确不负责什么？',keywords:/范围|本轮|不在|不能保证|系统|负责/,logic:'用“包含什么 + 不包含什么”画清责任边界，不把目标写成承诺。'},
 core_modules:{question:'哪些模块真正承载本轮流程？',keywords:/模块|\.py|代码|读取|管理/,logic:'把模块与职责配对，不只抄文件名。'},
 repository_structure:{question:'从哪里能找到业务代码、测试和材料？',keywords:/文件|目录|tests|materials|\.py/,logic:'只保留理解和验证本轮任务所需的结构。'},
 business_objects:{question:'流程围绕哪些角色、记录和状态展开？',keywords:/报修|工单|记录|时间|状态|居民/,logic:'选择在流程中有身份、状态或数据关系的核心对象。'},
 workflow:{question:'事情按什么顺序发生？正常和例外路径是什么？',keywords:/路径|提交|受理|派单|处理|确认|取消/,logic:'按“角色 + 动作 + 结果”串起主路径，再补关键例外。'},
 constraints:{question:'哪些规则和保护行为不能被这次修改破坏？',keywords:/保持|只能|不能|不得|兼容|权限|状态/,logic:'把目标限制、权限规则和已有兼容要求分开记录。'},
 unknown_questions:{question:'材料没有回答、必须进一步核实的是什么？',keywords:/待确认|尚未|需要|是否|真实|观察/,logic:'未知项要写成可调查的问题，不能用猜测补齐。'},
 problem_statement:{question:'实际结果与期望结果之间的可观察差距是什么？',keywords:/问题|不知道|未显示|询问|期望|实际/,logic:'先写可复现差距，再讨论原因；原因未经验证要标成假设。'},
 supporting_evidence:{question:'哪些材料能直接支持这个问题确实存在？',keywords:/访谈|日志|问题单|记录|测试|观察/,logic:'同时保留来源和可核对事实，不用结论代替证据。'},
}
const rule=computed(()=>fieldRules[field.value[0]]||(/unknown/.test(field.value[0])?fieldRules.unknown_questions:{question:`“${field.value[1].title}”需要由哪些事实支持？`,keywords:/问题|范围|用户|流程|规则|结果|证据/,logic:'先引用可核对事实，再写归纳判断；没有依据的部分标为待确认。'}))
const evidence=computed(()=>{
 const candidates=sourceList.value
 const source=candidates.find(item=>rule.value.keywords.test(item.title))||candidates.find(item=>rule.value.keywords.test(item.content))||candidates[0]
 if(!source)return{title:'尚无可用材料',excerpt:'请先补充项目说明、访谈、日志或仓库信息。'}
 const lines=source.content.replace(/\r\n?/g,'\n').split('\n').map(line=>line.replace(/^\s*#{1,6}\s*/, '').trim()).filter(Boolean)
 const excerpt=lines.find(line=>rule.value.keywords.test(line))||lines[0]||source.content
 return{title:source.title,excerpt:excerpt.length>180?excerpt.slice(0,180)+'…':excerpt}
})
function summarize(value:any):string{
 if(Array.isArray(value))return value.map(summarize).join('；')
 if(value&&typeof value==='object')return naturalEntries(value).map(([key,item])=>`${naturalLabel(key)}：${summarize(item)}`).join('；')
 return naturalScalar(value)
}
const answer=computed(()=>{
 const value=props.suggestion?.[field.value[0]]
 return value===undefined||value===null||value===''?'参考内容尚未提供；请根据证据先写自己的判断。':summarize(value)
})
const progress=computed(()=>Math.round(((fieldIndex.value*phases.length+phase.value+1)/Math.max(1,props.fieldEntries.length*phases.length))*100))
function stop(){if(timer)clearInterval(timer);timer=undefined}
function advance(){if(hovering.value)return;if(phase.value<phases.length-1){phase.value++;return}phase.value=0;fieldIndex.value=(fieldIndex.value+1)%Math.max(1,props.fieldEntries.length)}
function play(){stop();timer=setInterval(advance,3000)}
function focusModule(index:number){hovering.value=true;fieldIndex.value=index;phase.value=0}
function focusPhase(index:number){hovering.value=true;phase.value=index}
function resume(){hovering.value=false;play()}
watch(()=>props.fieldEntries.length,()=>{fieldIndex.value=0;phase.value=0;play()})
onMounted(play)
onBeforeUnmount(stop)
</script>

<template>
 <section class="analysis-walkthrough" aria-label="自动分析过程演示">
  <header><h3>从材料到答案</h3><span class="analysis-auto">自动演示</span></header>
  <div class="analysis-progress" aria-hidden="true"><i :style="{width:progress+'%'}"/></div>
  <div class="analysis-modules" aria-label="分析模块"><button v-for="(item,index) in fieldEntries" :key="item[0]" :class="{active:fieldIndex===index}" @mouseenter="focusModule(index)" @mouseleave="resume" @focus="focusModule(index)" @blur="resume">{{item[1].title}}</button></div>
  <ol class="analysis-phase-list"><li v-for="(item,index) in phases" :key="item.title" :class="{active:phase===index,done:phase>index}"><button :aria-label="item.title" @mouseenter="focusPhase(index)" @mouseleave="resume" @focus="focusPhase(index)" @blur="resume"><span aria-hidden="true">{{index+1}}</span>{{item.title}}</button></li></ol>
  <div class="analysis-stage" :key="field[0]+'-'+phase" aria-live="polite">
   <template v-if="phase===0"><b>{{field[1].title}}</b><p class="analysis-question">{{rule.question}}</p></template>
   <template v-else-if="phase===1"><b>依据：{{evidence.title}}</b><blockquote>{{evidence.excerpt}}</blockquote><p>材料没有说明的内容仍需确认。</p></template>
   <template v-else><b>候选答案</b><div class="analysis-equation"><span>材料事实</span><em>＋</em><span>判断规则</span><em>→</em><strong>可核对答案</strong></div><p>{{rule.logic}}</p><div class="analysis-answer">{{answer}}</div></template>
  </div>
 </section>
</template>
