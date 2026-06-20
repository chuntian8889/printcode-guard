from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from orders import create_order, import_codes_for_order, get_code_library

engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)


def test_create_order_and_import():
    db = SessionLocal()
    order = create_order(db, "TEST-001")
    assert order.name == "TEST-001"
    import_codes_for_order(db, order.id, ["A001", "A002", "A003"])
    codes = get_code_library(db, order.id)
    assert len(codes) == 3
    assert codes[0].content == "A001"
