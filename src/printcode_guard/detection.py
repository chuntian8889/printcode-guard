import datetime
from typing import Dict


DUPLICATE_WINDOW_SECONDS = 2


def classify_code(content: str, state: Dict, now: datetime.datetime) -> Dict:
    last_seen = state.get("last_seen", {})
    order_codes = state.get("order_codes", set())

    result = {
        "content": content,
        "status": "ok",
        "is_duplicate": False,
        "is_abnormal": False,
        "alarm_type": None,
    }

    # 格式校验：空串或极短
    if not content or len(content) < 3:
        result["status"] = "format_error"
        result["is_abnormal"] = True
        result["alarm_type"] = "format_error"
        return result

    # 短时间重复过滤
    last_time = last_seen.get(content)
    if last_time and (now - last_time).total_seconds() < DUPLICATE_WINDOW_SECONDS:
        result["status"] = "duplicate"
        result["is_duplicate"] = True
        result["is_abnormal"] = True
        result["alarm_type"] = "duplicate"
        return result

    if content not in order_codes:
        result["status"] = "not_in_library"
        result["is_abnormal"] = True
        result["alarm_type"] = "not_in_library"
    else:
        state.setdefault("scanned", set()).add(content)

    last_seen[content] = now
    return result


def refresh_order_state(db, order_id: int) -> Dict:
    from .orders import get_code_library

    codes = get_code_library(db, order_id)
    return {
        "order_id": order_id,
        "order_codes": {c.content for c in codes},
        "last_seen": {},
        "scanned": set(),
    }
