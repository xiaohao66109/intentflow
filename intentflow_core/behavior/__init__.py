"""Finite, deterministic business rules. No generated code or arbitrary DSL."""
from __future__ import annotations

from copy import deepcopy
from pathlib import PurePosixPath
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class BusinessRule(Strict):
    domain: Literal["campus", "inventory", "reservation"]
    capacity: int = Field(ge=1, le=100000)
    cancel_requires_approval: bool = False
    waitlist_enabled: bool = False
    quotas: dict[str, int] = Field(default_factory=dict, max_length=30)
    window_start: int = Field(default=0, ge=0, le=1000000)
    window_end: int = Field(default=1440, ge=1, le=1000001)

    @model_validator(mode="after")
    def bounds(self):
        if self.window_end <= self.window_start:
            raise ValueError("时间窗口结束值必须大于开始值")
        if any(type(v) is not int or v < 0 or v > self.capacity or not k or len(k) > 50
               for k, v in self.quotas.items()):
            raise ValueError("组配额必须是容量范围内的非负整数")
        return self


def relative_path(value, *, python=False):
    if not isinstance(value, str) or not value or len(value) > 300 or "\\" in value or ":" in value:
        raise ValueError("请输入仓库内使用 / 分隔的相对路径")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value.startswith("-") or ".git" in path.parts:
        raise ValueError("路径不能越出仓库或指向 Git 内部目录")
    if python and path.suffix != ".py":
        raise ValueError("首版只支持 Python 文件")
    return value


class CodeReference(Strict):
    path: str


class TestReference(Strict):
    path: str
    framework: Literal["unittest", "pytest"] = "unittest"
    rule_ids: list[str] = Field(min_length=1, max_length=100)
    code_paths: list[str] = Field(default_factory=list, max_length=100)
    rule_revisions: dict[str, str] = Field(default_factory=dict)


class ArchitectureRule(Strict):
    scope: str
    forbidden_imports: list[str] = Field(default_factory=list, max_length=30)
    required_calls: list[str] = Field(default_factory=list, max_length=30)
    entry_functions: list[str] = Field(default_factory=list, max_length=30)
    reason: str = Field(min_length=1, max_length=2000)
    exception_reason: str = ""
    exception_until: str = ""


def validate_object(kind, content):
    models = {"RULE": BusinessRule, "CODE": CodeReference, "TEST": TestReference, "ARCHITECTURE": ArchitectureRule}
    if kind not in models:
        raise ValueError("不支持的工程对象类型")
    try:
        value = models[kind].model_validate(content)
    except ValidationError as exc:
        # Do not echo arbitrary supplied content in API validation errors.
        raise ValueError("规则结构或取值不正确：" + "; ".join(e["msg"] for e in exc.errors(include_input=False))) from None
    if kind in {"CODE", "TEST"}:
        relative_path(value.path, python=True)
    if kind == "TEST":
        for path in value.code_paths:
            relative_path(path, python=True)
    if kind == "ARCHITECTURE":
        relative_path(value.scope)
        if not value.forbidden_imports and not value.required_calls:
            raise ValueError("请至少指定一项架构检查")
        if bool(value.exception_reason) != bool(value.exception_until):
            raise ValueError("例外需要同时填写理由和到期日期")
        if value.exception_until:
            from datetime import date
            try:
                date.fromisoformat(value.exception_until)
            except ValueError:
                raise ValueError("例外到期日期必须为 YYYY-MM-DD") from None
    return value.model_dump()


class Action(Strict):
    event: Literal["enroll", "cancel", "approve", "reject"]
    user: str = Field(min_length=1, max_length=80)
    group: str = Field(default="普通", min_length=1, max_length=50)
    quantity: int = Field(default=1, ge=1, le=100000)
    start: int = Field(default=0, ge=0, le=1000000)
    end: int = Field(default=60, ge=1, le=1000001)
    at: int = Field(default=0, ge=0, le=1000000)


def transition(rule, state, event):
    """Pure state transition. Rejections are observable outcomes, not crashes."""
    config = BusinessRule.model_validate(rule)
    action = Action.model_validate(event)
    state = deepcopy(state or {"entries": []})
    entries = state.setdefault("entries", [])
    active = {"enrolled", "pending_cancel"}
    current = next((e for e in entries if e["user"] == action.user and e["status"] in active | {"waiting"}), None)
    reason = ""
    def fit(candidate):
        others = [e for e in entries if e["status"] in active and e is not candidate]
        if config.domain == "reservation":
            others = [e for e in others if e["start"] < candidate["end"] and candidate["start"] < e["end"]]
            # Count at every interval endpoint; summing all overlapping intervals
            # would incorrectly reject disjoint reservations in a long window.
            points = {candidate["start"]} | {max(candidate["start"], e["start"]) for e in others}
            return all(sum(e["quantity"] for e in others if e["start"] <= p < e["end"]) + candidate["quantity"] <= config.capacity
                       and sum(e["quantity"] for e in others if e["group"] == candidate["group"] and e["start"] <= p < e["end"]) + candidate["quantity"] <= config.quotas.get(candidate["group"], config.capacity)
                       for p in points)
        return (sum(e["quantity"] for e in others) + candidate["quantity"] <= config.capacity
                and sum(e["quantity"] for e in others if e["group"] == candidate["group"]) + candidate["quantity"] <= config.quotas.get(candidate["group"], config.capacity))
    if action.event == "enroll":
        if current:
            reason = "该用户已有有效记录，不能重复申请"
        elif config.domain != "inventory" and action.quantity != 1:
            reason = "报名和预约每次只支持一个名额"
        elif not config.window_start <= action.at < config.window_end:
            reason = "不在允许的操作时间窗口内"
        elif config.domain == "reservation" and not (config.window_start <= action.start < action.end <= config.window_end):
            reason = "预约时间必须完整处于允许窗口内"
        else:
            item = {"user": action.user, "group": action.group, "quantity": action.quantity,
                    "start": action.start, "end": action.end, "status": "enrolled"}
            if not fit(item):
                if config.waitlist_enabled:
                    item["status"] = "waiting"
                else:
                    reason = "容量、库存或组配额不足"
            if not reason:
                entries.append(item)
    elif not current:
        reason = "没有可处理的有效记录"
    elif action.event == "cancel":
        if current["status"] == "waiting":
            current["status"] = "cancelled"
        elif current["status"] == "pending_cancel":
            reason = "取消申请正在等待审批"
        else:
            current["status"] = "pending_cancel" if config.cancel_requires_approval else "cancelled"
    elif current["status"] != "pending_cancel":
        reason = "只有待取消审批的记录可执行审批"
    else:
        current["status"] = "cancelled" if action.event == "approve" else "enrolled"
    if not reason:
        for item in entries:
            if item["status"] == "waiting" and fit(item):
                item["status"] = "enrolled"
    return {"state": state, "accepted": not reason, "reason": reason or "操作完成",
            "event": action.model_dump(), "evidence_type": "prototype_simulation"}
