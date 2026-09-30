// API times remain lossless; only the presentation uses clocks and local dates.
export function formatClock(minutes: number): string {
  if (!Number.isInteger(minutes) || minutes < 0) return '未设置'
  const day = Math.floor(minutes / 1440)
  const clock = `${String(Math.floor(minutes % 1440 / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
  return `${day === 0 ? '' : day === 1 ? '次日 ' : `第 ${day + 1} 天 `}${clock}`
}
export function formatDateTime(value?: string): string {
  if (!value) return '未记录时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间格式有误'
  const parts = new Intl.DateTimeFormat('zh-CN', {timeZone:'Asia/Shanghai', year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hourCycle:'h23'}).formatToParts(date)
  const part = (type: string) => parts.find(p => p.type === type)?.value
  return `${part('year')}年${part('month')}月${part('day')}日 ${part('hour')}:${part('minute')}`
}
export const stageGuidance: Record<string, {goal: string; done: string}> = {
  'project-context': {goal:'说明谁在使用项目、要解决什么问题，以及本轮的范围。', done:'保存经核对的项目背景、用户和边界。'},
  'problem-evidence': {goal:'区分观察到的事实、用户观点和待验证的推断。', done:'问题有具体证据支持，并写清影响与信息缺口。'},
  specification: {goal:'明确业务规则，通过原型检查正常操作、边界和例外。', done:'需求与验收标准已确认；发现的冲突已有处理决定。'},
  'engineering-intent': {goal:'写清修改范围、保留行为、设计理由和验收方法。', done:'设计与已确认需求一致，关键约束有业务理由。'},
  'software-change': {goal:'按约定范围修改代码，审阅差异并提交版本。', done:'修改及测试已提交，并记录本次要验证的代码版本。'},
  verification: {goal:'检查测试是否覆盖当前需求，运行测试并处理失败。', done:'当前版本的测试和约束检查有有效结果，失败与未知项已处理。'},
  'runtime-outcome': {goal:'记录使用现场的变化，比较目标与实际结果。', done:'保存观察、指标及决策依据，明确结束、观察、调整或回退到上一版本。'},
  'next-change': {goal:'回顾本轮证据和遗留问题，再确定下一轮改进。', done:'保留本轮结果，明确下一轮的变更依据与验证计划。'},
}
