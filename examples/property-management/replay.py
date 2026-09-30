import json
from pathlib import Path
from readmodel import resident_detail

def replay():
    tickets = json.loads((Path(__file__).parent / "case-materials" / "work-orders.json").read_text(encoding="utf-8"))
    visible = unauthorized = invalid = 0
    rows = []
    for ticket in tickets:
        detail = resident_detail(ticket, ticket["owner"])
        expected = ticket.get("expected_contact") if ticket["status"] in {"assigned", "processing"} else None
        actual = detail.get("contact_time")
        if expected is not None and actual == expected:
            visible += 1
        if ticket["status"] not in {"assigned", "processing"} and actual is not None:
            invalid += 1
        try:
            resident_detail(ticket, "resident-b" if ticket["owner"] == "resident-a" else "resident-a")
            unauthorized += 1
        except ValueError:
            pass
        rows.append({"number": ticket["id"], "status": detail["status"], "expected": expected, "actual": actual})
    return {"source": "模拟工单回放", "sample_count": len(tickets), "metrics": {"contact_visible": visible, "unauthorized_visible": unauthorized, "invalid_promises": invalid}, "rows": rows}

if __name__ == "__main__":
    print(json.dumps(replay(), ensure_ascii=False))
