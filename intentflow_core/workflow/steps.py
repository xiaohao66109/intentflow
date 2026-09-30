"""The public V1.0 workflow contract."""
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class WorkflowStep:
    id: str
    title: str
    required_input: tuple[str, ...]
    optional_input: tuple[str, ...]
    skill: str | None
    ai_context: tuple[str, ...]
    candidate_output: str
    confirmed_output: str
    entry_gate: str
    exit_gate: str
    next_action: str

    def as_dict(self):
        value = asdict(self)
        value["required_input"] = list(self.required_input)
        value["optional_input"] = list(self.optional_input)
        value["ai_context"] = list(self.ai_context)
        return value

STEPS = (
    WorkflowStep("project-context", "项目理解", ("项目", "代码仓库或项目说明"), ("原始证据",),
                 "project-understanding", ("说明文档", "仓库目录", "开发语言", "测试结构", "版本历史", "原始材料"),
                 "候选项目上下文", "正式项目上下文", "项目已经创建", "项目上下文已确认", "分析问题与证据"),
    WorkflowStep("problem-evidence", "问题与证据", ("正式项目上下文", "原始证据"), ("候选问题", "运行证据"),
                 "evidence-analysis", ("项目上下文", "可见证据"),
                 "候选问题", "正式问题", "项目上下文和可见证据已经存在", "问题已确认", "定义需求规格"),
    WorkflowStep("specification", "需求规格", ("已确认问题", "支持证据", "项目上下文"), (),
                 "requirement-engineering", ("已确认问题", "支持证据", "项目上下文"),
                 "候选需求规格", "正式需求规格", "已确认问题存在", "变更提案通过且需求规格已确认", "设计工程意图"),
    WorkflowStep("engineering-intent", "工程意图", ("正式需求规格", "仓库上下文"), ("相关证据",),
                 "intent-design", ("需求规格", "仓库结构", "相关证据"),
                 "候选工程意图", "正式工程意图", "需求规格和代码仓库已经存在", "工程意图已确认", "开始外部软件变更"),
    WorkflowStep("software-change", "软件变更", ("正式工程意图", "代码仓库"), (), None, (),
                 "待完成变更记录", "正式变更记录", "工程意图和代码仓库已经存在", "基线提交已记录", "在外部开发并提交最终版本"),
    WorkflowStep("verification", "工程验证", ("工程意图", "变更记录", "版本差异", "测试"), (), None, (),
                 "验证证据", "正式验证结果", "待验证变更和最终提交已经存在", "四级确定性判定已记录", "录入运行证据"),
    WorkflowStep("runtime-outcome", "效果评估", ("变更前证据", "正式验证结果", "变更后运行证据", "现场目标"), (),
                 "outcome-evaluation", ("确定性指标对比", "验证结果", "变更前后证据"),
                 "候选效果评估", "正式工程评估", "验证结果和关联的变更后证据已经存在", "下一步操作已确认", "结束、观察、调整或回滚"),
    WorkflowStep("next-change", "下一轮改进", ("正式工程评估",), ("候选问题",), None, (),
                 "候选问题", "下一轮工作流", "评估操作已经存在", "调整候选必须先确认成正式问题才能复用", "返回问题与证据"),
)

BY_ID = {item.id: item for item in STEPS}

def step(step_id):
    try:
        return BY_ID[step_id]
    except KeyError:
        raise ValueError("Unknown workflow step") from None

def contract():
    return [item.as_dict() for item in STEPS]
