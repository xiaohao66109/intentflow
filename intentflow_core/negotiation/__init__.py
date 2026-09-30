"""Finite integer constraint negotiation; no language-model verdicts."""
from typing import Literal
from pydantic import Field, model_validator
from intentflow_core.behavior import Strict


class Constraints(Strict):
    capacity: int = Field(ge=1, le=100000)
    existing: int = Field(ge=0, le=100000)
    incoming: int = Field(ge=0, le=100000)
    group_existing: int = Field(default=0, ge=0, le=100000)
    group_quota: int | None = Field(default=None, ge=0, le=100000)
    requested_start: int = Field(default=0, ge=0, le=1000000)
    requested_end: int = Field(default=60, ge=1, le=1000001)
    window_start: int = Field(default=0, ge=0, le=1000000)
    window_end: int = Field(default=1440, ge=1, le=1000001)
    allow_waitlist: bool = False
    allow_capacity_increase: bool = False
    allow_window_expansion: bool = False
    capacity_limit: int = Field(default=100000, ge=1, le=100000)
    preference: Literal["least_change", "admit_more"] = "least_change"

    @model_validator(mode="after")
    def bounds(self):
        if self.requested_start >= self.requested_end or self.window_start >= self.window_end:
            raise ValueError("结束时间必须大于开始时间")
        if self.group_existing > self.existing:
            raise ValueError("该组现有人数不能超过总现有人数")
        if self.capacity > self.capacity_limit:
            raise ValueError("允许扩容上限不能小于当前容量")
        return self


def solve(raw):
    constraints = Constraints.model_validate(raw)
    c = constraints.model_dump()
    conflict = []
    if c["existing"] + c["incoming"] > c["capacity"]:
        conflict.append("保留现有数量 + 新增全部成功 > 当前容量")
    if c["group_quota"] is not None and c["group_existing"] + c["incoming"] > c["group_quota"]:
        conflict.append("该组现有数量 + 该组新增数量 > 组配额")
    if not c["window_start"] <= c["requested_start"] < c["requested_end"] <= c["window_end"]:
        conflict.append("申请时间不完全位于允许窗口内")
    candidates = []
    capacities = {c["capacity"]}
    if c["allow_capacity_increase"]:
        capacities.add(max(c["capacity"], c["existing"] + c["incoming"]))
    for capacity in sorted(capacities):
        if capacity > c["capacity_limit"] or c["existing"] > capacity:
            continue
        quota = c["group_quota"] if c["group_quota"] is not None else capacity
        available = min(capacity - c["existing"], quota - c["group_existing"])
        if available < 0:
            continue
        admit = min(c["incoming"], available)
        waiting = c["incoming"] - admit
        if waiting and not c["allow_waitlist"]:
            continue
        start, end = c["window_start"], c["window_end"]
        if not start <= c["requested_start"] < c["requested_end"] <= end:
            if not c["allow_window_expansion"]:
                continue
            start, end = min(start, c["requested_start"]), max(end, c["requested_end"])
        relaxed = []
        if capacity != c["capacity"]:
            relaxed.append("容量由 " + str(c["capacity"]) + " 调整为 " + str(capacity))
        if waiting:
            relaxed.append(str(waiting) + " 个新增申请进入候补，不承诺立即成功")
        if (start, end) != (c["window_start"], c["window_end"]):
            relaxed.append("允许窗口扩大为 " + str(start) + "—" + str(end))
        candidate = {"capacity": capacity, "admitted": admit, "waiting": waiting,
                     "window_start": start, "window_end": end, "relaxed": relaxed}
        assert satisfies(c, candidate), "Independent constraint postcondition failed"
        candidates.append(candidate)
    candidates.sort(key=lambda p: (-p["admitted"], len(p["relaxed"])) if c["preference"] == "admit_more"
                    else (len(p["relaxed"]), p["capacity"] - c["capacity"], -p["admitted"]))
    return {"status": "FEASIBLE" if candidates else "INFEASIBLE", "constraints": c,
            "conflicts": conflict, "candidates": candidates,
            "scope": "对已确认的有限容量、单组配额与时间窗口求解；不是全局最小冲突集"}


def satisfies(c, p):
    """Separate arithmetic postcondition, independent of candidate construction."""
    return (p["admitted"] >= 0 and p["waiting"] >= 0 and p["admitted"] + p["waiting"] == c["incoming"]
            and c["existing"] + p["admitted"] <= p["capacity"] <= c["capacity_limit"]
            and (c["allow_capacity_increase"] or p["capacity"] == c["capacity"])
            and (c["allow_waitlist"] or p["waiting"] == 0)
            and (c["group_quota"] is None or c["group_existing"] + p["admitted"] <= c["group_quota"])
            and p["window_start"] <= c["requested_start"] < c["requested_end"] <= p["window_end"]
            and (c["allow_window_expansion"] or (p["window_start"], p["window_end"]) == (c["window_start"], c["window_end"])))
