"""Resident-facing work order detail. The current release omits contact information."""
from maintenance import ACTORS, STATUS

def resident_detail(ticket, actor):
    if actor not in ACTORS or ACTORS[actor][0] != "resident" or actor != ticket["owner"]:
        raise ValueError("居民只能查看本人的报修单")
    return {
        "number": ticket["id"],
        "title": ticket["title"],
        "status": STATUS[ticket["status"]],
        "result": ticket.get("result", ""),
        # CONTACT_DISPLAY: pending implementation
    }
