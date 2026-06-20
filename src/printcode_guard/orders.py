from typing import List
from sqlalchemy.orm import Session
from models import Order, Code


def create_order(db: Session, name: str) -> Order:
    order = Order(name=name, status="active")
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_active_order(db: Session) -> Order | None:
    return (
        db.query(Order)
        .filter(Order.status == "active")
        .order_by(Order.id.desc())
        .first()
    )


def get_order(db: Session, order_id: int) -> Order | None:
    return db.query(Order).get(order_id)


def list_orders(db: Session, limit: int = 20):
    return db.query(Order).order_by(Order.id.desc()).limit(limit).all()


def import_codes_for_order(
    db: Session, order_id: int, contents: List[str]
) -> int:
    existing = {
        c.content
        for c in db.query(Code).filter(Code.order_id == order_id).all()
    }
    added = 0
    for content in contents:
        content = content.strip()
        if not content or content in existing:
            continue
        db.add(Code(order_id=order_id, content=content, scanned=False))
        existing.add(content)
        added += 1
    db.commit()
    return added


def get_code_library(db: Session, order_id: int) -> List[Code]:
    return db.query(Code).filter(Code.order_id == order_id).all()


def mark_code_scanned(db: Session, order_id: int, content: str):
    code = db.query(Code).filter_by(order_id=order_id, content=content).first()
    if code:
        code.scanned = True
        db.commit()
