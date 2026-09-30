export type AgileIteration={number:number;title:string;goal:string;length_weeks:number}

export const requiredIterations:Omit<AgileIteration,'length_weeks'>[]=[
 {number:1,title:'最小可用原型',goal:'用最小范围跑通核心业务流程，交付可演示、可验证的版本。'},
 {number:2,title:'前向部署与用户访谈',goal:'把原型交给目标用户试用，通过访谈记录真实阻力、误解与新增需求。'},
 {number:3,title:'从数据中获取需求',goal:'分析运行指标、用户行为与异常数据，用证据确定下一批需求。'},
 {number:4,title:'运行与维护',goal:'处理业务变更、故障、性能与持续维护，并形成后续迭代计划。'},
]

export const propertyIterationGoals=[
 '跑通居民提交、客服派单、维修处理和居民确认的最小可用报修原型。',
 '将原型前向部署给居民、客服和维修人员，通过角色体验与访谈记录真实反馈。',
 '分析 12 条模拟工单、催办记录与运行日志，从数据中确定联系时间展示需求。',
 '在运行维护中处理状态规则、旧工单兼容、权限保护与后续业务变更。',
]

// Reading guides for planned rounds; selecting a round does not mark it complete.
export const iterationReading:Record<number,{focus:string[];propertyFiles:string[]}>= {
 1:{focus:['核对项目背景、角色和现有业务规则。','完成本轮八阶段交付并保留验证证据。'],propertyFiles:['01-project-brief.md','02-roles-and-journey.md','05-business-rules.md']},
 2:{focus:['对照居民、客服与维修人员的访谈，识别角色差异。','记录前向试用中发现的问题，并区分模拟材料与真实反馈。'],propertyFiles:['02-roles-and-journey.md','03-resident-interview.md','04-staff-interview.md','08-priority-and-conflicts.md']},
 3:{focus:['对照问题单、运行日志和工单样本寻找可复现差距。','用验收口径核对需求优先级，避免从单条数据直接推断实际效果。'],propertyFiles:['06-support-log.md','07-runtime-log.md','work-orders.json','10-acceptance-plan.md']},
 4:{focus:['核对状态、权限和历史工单的维护边界。','阅读观察口径与下一轮变更请求，形成后续验证计划。'],propertyFiles:['05-business-rules.md','09-design-map.md','11-observation-plan.md','12-next-iteration.md']},
}

export function iterationGoals(count:number,current:string[]=[]){
 return Array.from({length:Math.max(4,Math.min(count||4,8))},(_,index)=>
  current[index]||requiredIterations[index]?.goal||'根据上一轮反馈与运行证据，交付下一项可验证改进。')
}

export function iterationTitle(index:number){
 return requiredIterations[index]?.title||`持续改进 ${index+1}`
}
