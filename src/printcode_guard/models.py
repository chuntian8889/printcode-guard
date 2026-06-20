import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    codes = relationship("Code", back_populates="order", cascade="all, delete-orphan")
    scans = relationship("ScanRecord", back_populates="order")
    alarms = relationship("AlarmRecord", back_populates="order")


class Code(Base):
    __tablename__ = "codes"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    content = Column(String(512), nullable=False)
    scanned = Column(Boolean, default=False)
    order = relationship("Order", back_populates="codes")


class ScanRecord(Base):
    __tablename__ = "scan_records"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    content = Column(String(512), nullable=False)
    read_at = Column(DateTime, default=datetime.datetime.utcnow)
    result_status = Column(String(50), default="ok")
    is_duplicate = Column(Boolean, default=False)
    is_abnormal = Column(Boolean, default=False)
    order = relationship("Order", back_populates="scans")


class AlarmRecord(Base):
    __tablename__ = "alarm_records"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    alarm_type = Column(String(50), nullable=False)
    content = Column(String(512), nullable=False)
    alarm_at = Column(DateTime, default=datetime.datetime.utcnow)
    screenshot_path = Column(String(1024), nullable=True)
    order = relationship("Order", back_populates="alarms")


class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text, nullable=True)
