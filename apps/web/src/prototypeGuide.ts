export const prototypeSteps = [
 {actor:'resident-a',event:'submit',accepted:true,title:'居民提交报修',question:'提交后应进入哪个状态？',why:'从真实用户目标开始，建立后续角色协作的同一张工单。'},
 {actor:'dispatcher',event:'accept',accepted:true,title:'客服受理报修',question:'为什么居民不能替客服完成受理？',why:'角色有不同职责，状态转换必须符合权限。'},
 {actor:'dispatcher',event:'assign',accepted:true,title:'客服指派王师傅',question:'派单后谁可以处理这张工单？',why:'指派建立责任关系，后续权限应依赖这项关系。'},
 {actor:'worker-b',event:'start',accepted:false,title:'尝试由未被指派的赵师傅处理',question:'同为维修人员，赵师傅应被允许处理吗？',why:'预期拒绝也是有效的边界验证；不能只检查正常流程。'},
 {actor:'worker-a',event:'set_contact',accepted:true,title:'王师傅填写预计联系时间',question:'已填写时间是否应向居民展示？',why:'把用户需要的信息连接到明确的数据来源。'},
 {actor:'resident-a',event:'view',accepted:true,title:'居民查看联系安排',question:'居民详情应显示什么？未填写时又应怎样？',why:'检查验收标准的可观察结果；原型与实际代码仍需分别验证。'},
 {actor:'resident-a',event:'cancel',accepted:false,title:'尝试在派单后取消',question:'派单后的取消是否仍应立即生效？',why:'状态条件是业务规则的一部分，不能只凭按钮存在判断允许操作。'},
 {actor:'worker-a',event:'start',accepted:true,title:'王师傅开始处理',question:'负责人开始处理后，状态应如何变化？',why:'验证合法角色与合法前置状态同时成立的路径。'},
 {actor:'worker-a',event:'complete',accepted:false,title:'尝试不填维修结果就完成',question:'缺少处理说明时应接受提交吗？',why:'输入校验保护后续验收所需的信息。'},
 {actor:'worker-a',event:'complete',accepted:true,title:'填写结果并提交维修完成',question:'维修人员提交后，是否已经等于居民验收完成？',why:'区分实现者完成与使用者验收。'},
 {actor:'resident-a',event:'close',accepted:true,title:'居民确认维修完成',question:'工单结束后，还应继续显示联系承诺吗？',why:'验收是闭环的一环，终态信息也应遵循需求。'},
]

export function prototypeProgress(events:any[],ticketId:string):number {
 let step=0
 for(const event of events){
  const expected=prototypeSteps[step]
  if(!expected)break
  if(step>0&&event.ticket_id!==ticketId)continue
  if(event.actor===expected.actor&&event.event===expected.event&&event.accepted===expected.accepted)step++
 }
 return step
}
