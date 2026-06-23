import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from .models import ScanRecord


def _is_content_seen_before(db: Optional[Session], content: str) -> bool:
    """查询数据库：该二维码是否在任何订单、任何时间被扫描过。"""
    if db is None:
        return False
    return (
        db.query(ScanRecord).filter(ScanRecord.content == content).first() is not None
    )


def classify_code(
    content: str,
    state: Dict,
    now: datetime.datetime,
    db: Optional[Session] = None,
) -> Dict:
    order_codes = state.get("order_codes", set())

    base = {
        "content": content,
        "is_duplicate": False,
        "is_abnormal": False,
        "alarm_type": None,
        "should_record": True,
    }

    # 格式校验：空串或极短
    if not content or len(content) < 3:
        return {
            **base,
            "status": "format_error",
            "is_abnormal": True,
            "alarm_type": "format_error",
        }

    # 全局历史去重：数据库中已存在该码 -> 重码报警
    if _is_content_seen_before(db, content):
        return {
            **base,
            "status": "duplicate",
            "is_duplicate": True,
            "is_abnormal": True,
            "alarm_type": "duplicate",
        }

    # 码库比对（如果码库为空则跳过，方便第一阶段不接上游数据时直接测试）
    if order_codes and content not in order_codes:
        return {
            **base,
            "status": "not_in_library",
            "is_abnormal": True,
            "alarm_type": "not_in_library",
        }

    # 正常通过
    state.setdefault("scanned", set()).add(content)
    return {
        **base,
        "status": "ok",
    }


def refresh_order_state(db, order_id: int) -> Dict:
    from .orders import get_code_library

    codes = get_code_library(db, order_id)
    return {
        "order_id": order_id,
        "order_codes": {c.content for c in codes},
        "last_seen": {},
        "scanned": set(),
    }
