const labels:Record<string,string>={
 title:'标题',type:'类型',content:'内容',status:'状态',goal:'目标',rationale:'判断依据',decision:'下一步决定',
 observation:'观察结果',effect_gap:'实际效果与目标差距',new_problem:'新发现的问题',recommended_action:'建议行动',
 stakeholders:'相关人员',system_boundary:'系统边界',core_modules:'核心模块',business_objects:'业务对象',
 repository_structure:'项目结构',workflow:'业务流程',constraints:'约束条件',unknown_questions:'待确认问题',
 problem_statement:'问题陈述',supporting_evidence:'支持证据',affected_area:'影响范围',affected_users:'受影响人员',
 current_state:'当前情况',expected_state:'期望情况',sufficiency:'证据充分性',impact:'影响',user_need:'用户需要',
 functional_requirements:'功能要求',quality_requirements:'质量要求',business_rules:'业务规则',success_criteria:'成功标准',
 why_change:'变更原因',allowed_scope:'允许修改',protected_scope:'不可修改',protected_behavior:'必须保留的行为',
 invariants:'始终成立的条件',acceptance:'验收要求',acceptance_criteria:'验收标准',open_questions:'待确认问题',
 field_target:'现场目标',metrics:'运行指标',before:'修改前',after:'修改后',source:'信息来源',origin:'材料来源',
 execution_status:'执行情况',exit_code:'结束情况',reason:'原因',result:'结果',verdict:'判定',seconds:'耗时（秒）',
 changes:'拟议变化',kind:'内容类别',domain:'业务场景',capacity:'容量上限',window_start:'开放时间',window_end:'结束时间',
 cancel_requires_approval:'取消是否需要审批',waitlist_enabled:'是否允许候补',quotas:'分组配额',path:'文件位置',framework:'测试方式',
 code_paths:'相关代码',rule_ids:'对应规则',forbidden_imports:'禁止依赖',required_calls:'必须调用',entry_functions:'入口函数',
 rationale_required:'是否需要说明理由',expires_on:'有效期至',owner:'负责人',scope:'适用范围',risk:'风险',mitigation:'应对措施',
 contact_visible:'正确显示联系时间',unauthorized_visible:'越权读取次数',invalid_promises:'无效联系承诺',
 iteration_count:'迭代轮数',length_weeks:'每轮周期（周）',current_iteration:'当前迭代',iterations:'迭代安排',number:'序号',
 members:'包含的工程内容',relations:'关联关系',conclusions:'验证结论',tests:'测试计划',affected:'受影响内容',unknown:'待确认内容',
 source_label:'来源说明',task_type:'任务类型',language:'开发语言',branch:'代码分支',model:'使用的模型',provider:'服务提供方',
}

const values:Record<string,string>={
 PASS:'通过',FAIL:'未通过',UNKNOWN:'尚未确认',STALE:'需要重新验证',DRAFT:'待确认',CONFIRMED:'已确认',
 OPEN:'进行中',CLOSED:'已结束',CLOSE:'结束本轮',OBSERVE:'继续观察',ADJUST:'继续调整',ROLLBACK:'建议回退',
 GO:'继续推进',NO_GO:'暂不推进',QUEUED:'等待执行',RUNNING:'正在执行',CANCELLING:'正在取消',CANCELLED:'已取消',
 SUCCEEDED:'执行完成',ERROR:'执行出错',TIMEOUT:'执行超时',INTERRUPTED:'执行中断',FINISHED:'执行完成',
 RULE:'业务规则',CODE:'代码',TEST:'测试',ARCHITECTURE:'工程设计',REQUIREMENT:'需求',OUTCOME:'运行评估',
 Evidence:'原始证据',Context:'项目背景',Problem:'问题分析',Specification:'需求说明',EngineeringIntent:'工程设计',
 Verification:'验证结果',RuntimeEvidence:'运行证据',EngineeringEvaluation:'效果评估',ChangeRecord:'变更记录',
 manual:'手工填写',llm:'智能辅助',property:'物业管理示例',blank:'空白项目',git:'版本库项目',benchmark:'基准案例',
 campus:'校园报名',inventory:'库存扣减',reservation:'预约冲突',true:'是',false:'否',
}

const hidden=new Set(['id','project_id','artifact_id','object_id','revision_id','parent_id','baseline_id','iteration_id','run_id','run_ids','test_id','rule_id','rule_ids','sources','source_id','target_id','credential_ref','input_snapshot_hash','content_hash','members'])
const eventValues:Record<string,string>={MIGRATED:'整理历史记录',BASELINE_CONFIRMED:'确认新需求版本',VERIFICATION_QUEUED:'提交复验',VERIFICATION_FINISHED:'完成复验',ARCHITECTURE_CHECKED:'检查工程设计',NEGOTIATION_SOLVED:'完成方案计算',NEGOTIATION_ADOPTED:'采用协商方案',TRAINING_STARTED:'开始实践',TRAINING_CHANGE:'确认容量调整',TRAINING_SUBMITTED:'提交实践结果',IMPACT_REVIEWED:'审阅变化影响',CASE_CREATED:'创建领域案例',OUTCOME_CONFIRMED:'确认运行观察与决策'}

export function visibleField(key:string){
 return !hidden.has(key)&&!key.endsWith('_id')&&!key.endsWith('_ids')&&!['base_commit','code_commit','final_commit','baseline_commit','rule_revisions'].includes(key)
}

export function naturalLabel(key:string){
 if(labels[key])return labels[key]
 return '补充信息'
}

export function naturalScalar(value:unknown){
 if(value===null||value===undefined||value==='')return '暂无记录'
 if(typeof value==='boolean')return value?'是':'否'
 const text=String(value)
 if(eventValues[text])return eventValues[text]
 if(values[text])return values[text]
 if(/^[0-9a-f]{32,64}$/i.test(text)||/^[0-9a-f-]{36}$/i.test(text))return '已记录'
 return text
}

export function naturalEntries(value:Record<string,unknown>){
 return Object.entries(value).filter(([key])=>visibleField(key))
}
