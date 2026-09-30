"""Property maintenance domain: roles, state transitions and audit history."""
from copy import deepcopy

ACTORS = {"resident-a": ("resident", "林女士"), "resident-b": ("resident", "周先生"),
          "dispatcher": ("dispatcher", "陈客服"), "worker-a": ("worker", "王师傅"),
          "worker-b": ("worker", "赵师傅")}
STATUS = {"submitted": "待受理", "accepted": "已受理", "assigned": "已派单", "processing": "处理中",
          "completed": "待居民确认", "closed": "已关闭", "cancelled": "已取消"}


class MaintenanceSystem:
    def __init__(self, state=None):
        self.state = deepcopy(state or {"tickets": [], "next_number": 1})

    def act(self, actor, event, ticket_id="", *, title="", location="", assignee="worker-a",
            at=540, contact_at=None, result=""):
        if actor not in ACTORS:
            raise ValueError("请选择有效的操作身份")
        role = ACTORS[actor][0]
        if not isinstance(at, int) or at < 0:
            raise ValueError("操作时间不正确")
        if event == "submit":
            if role != "resident":
                raise ValueError("只有居民可以提交报修")
            if not title.strip() or not location.strip():
                raise ValueError("请填写报修内容和位置")
            ticket = {"id": f"BX-{self.state['next_number']:03}", "owner": actor, "title": title.strip(),
                      "location": location.strip(), "status": "submitted", "assignee": "", "result": "",
                      "expected_contact": None, "history": []}
            self.state["next_number"] += 1
            self.state["tickets"].append(ticket)
        else:
            ticket = next((t for t in self.state["tickets"] if t["id"] == ticket_id), None)
            if not ticket:
                raise ValueError("请先选择报修单")
            if ticket["history"] and at < ticket["history"][-1]["at"]:
                raise ValueError("操作时间不能早于上一条记录")
            status = ticket["status"]
            if event == "accept":
                if role != "dispatcher" or status != "submitted":
                    raise ValueError("客服只能受理待受理的报修单")
                ticket["status"] = "accepted"
            elif event == "assign":
                if role != "dispatcher" or status != "accepted":
                    raise ValueError("客服只能给已受理的报修单派单")
                if assignee not in ACTORS or ACTORS[assignee][0] != "worker":
                    raise ValueError("请选择维修人员")
                ticket.update(status="assigned", assignee=assignee)
            elif event in {"start", "set_contact", "complete"}:
                if role != "worker" or ticket["assignee"] != actor:
                    raise ValueError("只有该单的维修人员可以处理")
                if event == "start":
                    if status != "assigned":
                        raise ValueError("只有已派单的报修单可以开始处理")
                    ticket["status"] = "processing"
                elif event == "set_contact":
                    if status not in {"assigned", "processing"}:
                        raise ValueError("当前状态不能填写预计联系时间")
                    if type(contact_at) is not int or not at <= contact_at <= at + 1440:
                        raise ValueError("预计联系时间应在操作时间之后的 24 小时内")
                    ticket["expected_contact"] = contact_at
                else:
                    if status != "processing" or not result.strip():
                        raise ValueError("处理中的报修单填写维修结果后，才能提交完成")
                    ticket.update(status="completed", result=result.strip(), expected_contact=None)
            elif event == "cancel":
                if actor != ticket["owner"] or status not in {"submitted", "accepted"}:
                    raise ValueError("居民只能取消本人尚未派单的报修单")
                ticket.update(status="cancelled", expected_contact=None)
            elif event == "close":
                if actor != ticket["owner"] or status != "completed":
                    raise ValueError("居民只能确认本人已完成维修的报修单")
                ticket["status"] = "closed"
            elif event == "reopen":
                if actor != ticket["owner"] or status != "completed" or not result.strip():
                    raise ValueError("居民可对待确认的报修单填写原因并申请继续处理")
                ticket.update(status="processing", result=result.strip(), expected_contact=None)
            elif event == "view":
                if role == "resident" and actor != ticket["owner"]:
                    raise ValueError("居民只能查看本人的报修单")
                if role == "worker" and actor != ticket["assignee"]:
                    raise ValueError("维修人员只能查看分派给自己的报修单")
            else:
                raise ValueError("未知操作")
        ticket["history"].append({"actor": actor, "event": event, "at": at, "status": ticket["status"]})
        return deepcopy(ticket)


def simulate(state, action):
    system = MaintenanceSystem(state)
    try:
        ticket = system.act(**action)
        return {"accepted": True, "reason": "操作已完成", "ticket": ticket, "state": system.state}
    except ValueError as exc:
        return {"accepted": False, "reason": str(exc), "state": deepcopy(state)}
