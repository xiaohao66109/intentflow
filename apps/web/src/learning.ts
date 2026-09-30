export type LearningTask={id:string;title:string;area:string;state:'待处理'|'可开始'|'待复验'|'已完成';detail:string}
export function learningTasks(state:any, drafts:any[], evidence:any, impact:any):LearningTask[]{
 const objects=state.objects||[], base=state.baseline_id
 const rules=objects.filter((o:any)=>o.kind==='RULE'), hasRules=rules.length>0
 const pending=drafts.some(d=>d.kind==='REQUIREMENT'&&d.status==='DRAFT')
 const preview=drafts.some(d=>d.kind==='PROTOTYPE'&&d.baseline_id===base&&d.content.events?.length)
 const design=objects.some((o:any)=>o.kind==='ARCHITECTURE')
 const code=!!state.baseline?.code_commit
 const verified=!!evidence.baseline_supported
 const observed=verified&&drafts.some(d=>d.kind==='OUTCOME'&&d.baseline_id===base&&d.content.code_commit===state.baseline?.code_commit&&d.content.baseline_supported_at_confirmation)
 return [
  {id:'rules',title:'核对业务规则',area:'rules',state:hasRules&&!pending?'已完成':'可开始',detail:pending?'有待审阅的修改，请核对后确认。':'写清容量、操作时间和取消条件，确认后保存为需求版本。'},
  {id:'prototype',title:'体验正常与边界操作',area:'prototype',state:preview?'已完成':hasRules?'可开始':'待处理',detail:preview?'已保存当前需求版本的操作记录，可继续补充边界场景。':'先确认规则，再模拟成功、容量不足和取消操作；操作记录用于讨论需求。'},
  {id:'architecture',title:'核对设计约束',area:'architecture',state:design?'已完成':hasRules?'可开始':'待处理',detail:'说明哪些模块可以修改、哪些行为必须保留，以及理由。'},
  {id:'change',title:'提交并记录代码',area:'change',state:code?'已完成':hasRules?'可开始':'待处理',detail:code?'已记录代码提交；需求变化后仍需修改代码并记录新的提交。':'按需求和设计修改代码及测试，在开发工具中提交后回来确认版本。'},
  {id:'verify',title:'验证当前需求与代码',area:'verify',state:verified?'已完成':hasRules&&code?(impact.test_mapping_gaps?.length||evidence.runs?.length?'待复验':'可开始'):'待处理',detail:impact.test_mapping_gaps?.length?'需求已变化，请检查测试覆盖、确认映射，再重新运行。':'审阅影响范围与测试覆盖，执行真实测试，检查失败和未知项。'},
  {id:'outcome',title:'评估实际使用效果',area:'outcome',state:observed?'已完成':verified?'可开始':'待处理',detail:verified?'填写现场观察、指标和决策依据。':'可先保存观察；结束本轮前须补齐当前版本的验证证据。'},
 ]
}
