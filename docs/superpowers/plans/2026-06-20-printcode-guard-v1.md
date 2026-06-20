# PrintCode Guard v1 最小可用 Demo 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在本地搭建一个基于 RTSP 萤石云摄像头的印刷喷码二维码质检 Demo，完成实时读取、二维码识别、码库比对、重复/异常报警、扫码与报警记录落库，以及一个简单 Web 监控页面。

**Architecture:** 采用 Python FastAPI 单进程后端 + 原生 HTML/JS 前端。OpenCV 从 RTSP 拉流并在后台线程解码；pyzbar 识别二维码；识别结果经过去重窗口、码库比对后写入 PostgreSQL；前端通过 MJPEG 流看实时画面，通过 HTTP API 拉状态和记录，报警时播放提示音并高亮红色。

**Tech Stack:** Python 3.11, FastAPI, Uvicorn, SQLAlchemy 2.x, PostgreSQL, OpenCV-Python, pyzbar, Pillow, python-multipart.

---

## 项目目录结构（在当前 `/home/chuntian/projects/QRcode` 下创建）

```
PrintCode-Guard/
├── README.md                         # 项目说明与启动方式
├── requirements.txt                  # Python 依赖
├── .gitignore                        # 排除私有数据
├── docs/superpowers/plans/2026-06-20-printcode-guard-v1.md  # 本计划
├── src/printcode_guard/
│   ├── __init__.py
│   ├── main.py                       # FastAPI 入口、静态文件、路由聚合
│   ├── database.py                   # SQLAlchemy engine / session / 建表
│   ├── models.py                     # Order / Code / ScanRecord / AlarmRecord / Setting 表
│   ├── schemas.py                    # Pydantic 请求/响应模型
│   ├── camera.py                     # RTSP 捕获、MJPEG 推流、二维码识别线程
│   ├── detection.py                  # 二维码内容校验、码库比对、重复过滤、异常判定
│   ├── alarms.py                     # 报警触发、截图保存、WebSocket/轮询状态更新
│   ├── orders.py                     # 订单与码库的 CRUD、CSV/Excel 导入
│   ├── records.py                    # 扫码记录与报警记录查询
│   └── settings.py                   # 系统设置读写（RTSP、ROI、去重秒数）
├── static/
│   ├── index.html                    # 单页监控界面
│   ├── app.js                        # 前端交互
│   └── style.css                     # 样式
├── tests/                            # 关键逻辑单元测试
│   ├── test_detection.py
│   └── test_orders.py
└── private-data/
    └── screenshots/                  # 异常截图存放目录（gitignore）
```

---

## Task 1: 初始化项目骨架与依赖

**Files:**
- Create: `README.md`
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `src/printcode_guard/__init__.py`

- [ ] **Step 1: 写 README.md**

```markdown
# PrintCode Guard

印刷厂喷码二维码质检 Demo（v1 RTSP 验证版）。

## 快速启动

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. 确保本地 PostgreSQL 已启动，并创建数据库：
   ```sql
   CREATE DATABASE printcode_guard;
   ```
3. 启动服务：
   ```bash
   cd src/printcode_guard && uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
4. 打开 http://localhost:8000/ 开始验证。

## 数据目录

- 异常截图保存在 `private-data/screenshots/`。
```

- [ ] **Step 2: 写 requirements.txt**

```text
fastapi==0.111.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.31
psycopg2-binary==2.9.9
opencv-python==4.10.0.84
pyzbar==0.1.9
Pillow==10.3.0
python-multipart==0.0.9
pandas==2.2.2
openpyxl==3.1.5
pytest==8.2.2
httpx==0.27.0
```

- [ ] **Step 3: 写 .gitignore**

```text
__pycache__/
*.pyc
*.pyo
.env
private-data/
*.db
.venv/
```

- [ ] **Step 4: 创建空包文件**

`src/printcode_guard/__init__.py` 为空。

- [ ] **Step 5: Commit**

```bash
git add README.md requirements.txt .gitignore src/printcode_guard/__init__.py
git commit -m "chore: init PrintCode Guard v1 skeleton"
```

---

## Task 2: 数据库模型与连接

**Files:**
- Create: `src/printcode_guard/database.py`
- Create: `src/printcode_guard/models.py`

- [ ] **Step 1: 写 database.py**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/printcode_guard")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 2: 写 models.py**

```python
import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="active")  # active / paused / closed
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
    result_status = Column(String(50), default="ok")  # ok / duplicate / not_in_library / format_error
    is_duplicate = Column(Boolean, default=False)
    is_abnormal = Column(Boolean, default=False)
    order = relationship("Order", back_populates="scans")


class AlarmRecord(Base):
    __tablename__ = "alarm_records"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    alarm_type = Column(String(50), nullable=False)  # duplicate / not_in_library / format_error
    content = Column(String(512), nullable=False)
    alarm_at = Column(DateTime, default=datetime.datetime.utcnow)
    screenshot_path = Column(String(1024), nullable=True)
    order = relationship("Order", back_populates="alarms")


class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text, nullable=True)
```

- [ ] **Step 3: Commit**

```bash
git add src/printcode_guard/database.py src/printcode_guard/models.py
git commit -m "feat: add SQLAlchemy models and DB connection"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `src/printcode_guard/schemas.py`

- [ ] **Step 1: 写 schemas.py**

```python
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class OrderCreate(BaseModel):
    name: str


class OrderOut(BaseModel):
    id: int
    name: str
    status: str
    created_at: datetime
    class Config:
        from_attributes = True


class CodeOut(BaseModel):
    id: int
    content: str
    scanned: bool
    class Config:
        from_attributes = True


class ScanRecordOut(BaseModel):
    id: int
    content: str
    read_at: datetime
    result_status: str
    is_duplicate: bool
    is_abnormal: bool
    class Config:
        from_attributes = True


class AlarmRecordOut(BaseModel):
    id: int
    alarm_type: str
    content: str
    alarm_at: datetime
    screenshot_path: Optional[str]
    class Config:
        from_attributes = True


class StatusResponse(BaseModel):
    current_order: Optional[OrderOut]
    rtsp_url: Optional[str]
    is_running: bool
    total_scanned: int
    duplicate_count: int
    abnormal_count: int
    latest_code: Optional[str]
    alarm_active: bool


class ROI(BaseModel):
    x: int
    y: int
    w: int
    h: int
```

- [ ] **Step 2: Commit**

```bash
git add src/printcode_guard/schemas.py
git commit -m "feat: add pydantic schemas"
```

---

## Task 4: 订单与码库 CRUD + CSV/Excel 导入

**Files:**
- Create: `src/printcode_guard/orders.py`
- Create: `tests/test_orders.py`

- [ ] **Step 1: 写测试 test_orders.py**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Order, Code
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd src/printcode_guard && python -m pytest ../../tests/test_orders.py -v
```

Expected: ModuleNotFoundError 或 function not defined.

- [ ] **Step 3: 写 orders.py**

```python
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
    return db.query(Order).filter(Order.status == "active").order_by(Order.id.desc()).first()


def get_order(db: Session, order_id: int) -> Order | None:
    return db.query(Order).get(order_id)


def list_orders(db: Session, limit: int = 20):
    return db.query(Order).order_by(Order.id.desc()).limit(limit).all()


def import_codes_for_order(db: Session, order_id: int, contents: List[str]) -> int:
    existing = {c.content for c in db.query(Code).filter(Code.order_id == order_id).all()}
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd src/printcode_guard && python -m pytest ../../tests/test_orders.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/printcode_guard/orders.py tests/test_orders.py
git commit -m "feat: order and code library CRUD with import"
```

---

## Task 5: 二维码识别、码库比对、重复过滤逻辑

**Files:**
- Create: `src/printcode_guard/detection.py`
- Create: `tests/test_detection.py`

- [ ] **Step 1: 写测试 test_detection.py**

```python
from datetime import datetime, timedelta
from detection import classify_code


def test_classify_first_valid_code():
    state = {"last_seen": {}, "order_codes": {"A001"}}
    result = classify_code("A001", state, datetime.utcnow())
    assert result["status"] == "ok"
    assert result["is_duplicate"] is False
    assert result["is_abnormal"] is False


def test_classify_duplicate_within_window():
    now = datetime.utcnow()
    state = {"last_seen": {"A001": now - timedelta(seconds=1)}, "order_codes": {"A001"}}
    result = classify_code("A001", state, now)
    assert result["status"] == "duplicate"
    assert result["is_duplicate"] is True


def test_classify_not_in_library():
    state = {"last_seen": {}, "order_codes": {"A001"}}
    result = classify_code("X999", state, datetime.utcnow())
    assert result["status"] == "not_in_library"
    assert result["is_abnormal"] is True
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd src/printcode_guard && python -m pytest ../../tests/test_detection.py -v
```

Expected: function not defined.

- [ ] **Step 3: 写 detection.py**

```python
import datetime
from typing import Dict, Set, Tuple


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
    from orders import get_code_library
    codes = get_code_library(db, order_id)
    return {
        "order_id": order_id,
        "order_codes": {c.content for c in codes},
        "last_seen": {},
        "scanned": set(),
    }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd src/printcode_guard && python -m pytest ../../tests/test_detection.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/printcode_guard/detection.py tests/test_detection.py
git commit -m "feat: QR code classification with duplicate filtering"
```

---

## Task 6: RTSP 摄像头读取与 MJPEG 流

**Files:**
- Create: `src/printcode_guard/camera.py`

- [ ] **Step 1: 写 camera.py**

```python
import io
import threading
import time
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from PIL import Image


class Camera:
    def __init__(self, rtsp_url: str):
        self.rtsp_url = rtsp_url
        self.cap = None
        self.frame = None
        self.running = False
        self.thread: threading.Thread | None = None
        self.lock = threading.Lock()
        self.roi = None  # (x, y, w, h)

    def start(self):
        if self.running:
            return
        self.cap = cv2.VideoCapture(self.rtsp_url)
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开 RTSP 流: {self.rtsp_url}")
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.cap:
            self.cap.release()
            self.cap = None

    def _capture_loop(self):
        while self.running:
            ok, frame = self.cap.read()
            if ok:
                with self.lock:
                    self.frame = frame
            else:
                time.sleep(0.01)

    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def get_jpeg(self, quality: int = 85) -> bytes | None:
        frame = self.get_frame()
        if frame is None:
            return None
        if self.roi:
            x, y, w, h = self.roi
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        return buf.tobytes() if ok else None

    def set_roi(self, x: int, y: int, w: int, h: int):
        self.roi = (x, y, w, h)

    def read_qr_codes(self) -> list:
        frame = self.get_frame()
        if frame is None:
            return []
        if self.roi:
            x, y, w, h = self.roi
            h_max, w_max = frame.shape[:2]
            x, y = max(0, x), max(0, y)
            w, h = min(w, w_max - x), min(h, h_max - y)
            frame = frame[y:y + h, x:x + w]
        decoded = decode(frame)
        return [d.data.decode("utf-8", errors="ignore") for d in decoded]
```

- [ ] **Step 2: Commit**

```bash
git add src/printcode_guard/camera.py
git commit -m "feat: RTSP camera capture and MJPEG streaming"
```

---

## Task 7: 报警逻辑与异常截图保存

**Files:**
- Create: `src/printcode_guard/alarms.py`

- [ ] **Step 1: 写 alarms.py**

```python
import os
import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from camera import Camera
from models import AlarmRecord


SCREENSHOT_DIR = Path("../../private-data/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def save_alarm(db: Session, order_id: int, alarm_type: str, content: str, camera: Camera | None) -> AlarmRecord:
    screenshot_path = None
    if camera:
        frame = camera.get_frame()
        if frame is not None:
            filename = f"{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}_{alarm_type}.jpg"
            screenshot_path = str(SCREENSHOT_DIR / filename)
            import cv2
            cv2.imwrite(screenshot_path, frame)

    alarm = AlarmRecord(
        order_id=order_id,
        alarm_type=alarm_type,
        content=content,
        screenshot_path=screenshot_path,
    )
    db.add(alarm)
    db.commit()
    db.refresh(alarm)
    return alarm
```

- [ ] **Step 2: Commit**

```bash
git add src/printcode_guard/alarms.py
git commit -m "feat: alarm trigger and screenshot saving"
```

---

## Task 8: 记录查询 API

**Files:**
- Create: `src/printcode_guard/records.py`

- [ ] **Step 1: 写 records.py**

```python
from sqlalchemy.orm import Session
from models import ScanRecord, AlarmRecord


def create_scan_record(db: Session, order_id: int, content: str, status: str, is_duplicate: bool, is_abnormal: bool) -> ScanRecord:
    record = ScanRecord(
        order_id=order_id,
        content=content,
        result_status=status,
        is_duplicate=is_duplicate,
        is_abnormal=is_abnormal,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_recent_scans(db: Session, order_id: int | None = None, limit: int = 20):
    q = db.query(ScanRecord).order_by(ScanRecord.id.desc())
    if order_id:
        q = q.filter(ScanRecord.order_id == order_id)
    return q.limit(limit).all()


def get_recent_alarms(db: Session, order_id: int | None = None, limit: int = 20):
    q = db.query(AlarmRecord).order_by(AlarmRecord.id.desc())
    if order_id:
        q = q.filter(AlarmRecord.order_id == order_id)
    return q.limit(limit).all()


def get_counts(db: Session, order_id: int | None = None):
    q = db.query(ScanRecord)
    if order_id:
        q = q.filter(ScanRecord.order_id == order_id)
    total = q.count()
    duplicate = q.filter(ScanRecord.is_duplicate == True).count()
    abnormal = q.filter(ScanRecord.is_abnormal == True).count()
    return {"total": total, "duplicate": duplicate, "abnormal": abnormal}
```

- [ ] **Step 2: Commit**

```bash
git add src/printcode_guard/records.py
git commit -m "feat: scan and alarm record queries"
```

---

## Task 9: 系统设置读写

**Files:**
- Create: `src/printcode_guard/settings.py`

- [ ] **Step 1: 写 settings.py**

```python
import json
from sqlalchemy.orm import Session
from models import Setting


def get_setting(db: Session, key: str, default=None):
    row = db.query(Setting).filter(Setting.key == key).first()
    if row is None:
        return default
    return row.value


def set_setting(db: Session, key: str, value: str):
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        row = Setting(key=key, value=value)
        db.add(row)
    db.commit()


def get_roi(db: Session):
    raw = get_setting(db, "roi")
    if raw:
        return json.loads(raw)
    return None


def set_roi(db: Session, roi: dict):
    set_setting(db, "roi", json.dumps(roi))


def get_rtsp_url(db: Session):
    return get_setting(db, "rtsp_url", "")


def set_rtsp_url(db: Session, url: str):
    set_setting(db, "rtsp_url", url)


def get_dedup_seconds(db: Session):
    raw = get_setting(db, "dedup_seconds", "2")
    try:
        return int(raw)
    except ValueError:
        return 2


def set_dedup_seconds(db: Session, seconds: int):
    set_setting(db, "dedup_seconds", str(seconds))
```

- [ ] **Step 2: Commit**

```bash
git add src/printcode_guard/settings.py
git commit -m "feat: system settings persistence"
```

---

## Task 10: FastAPI 主入口与 HTTP API

**Files:**
- Create: `src/printcode_guard/main.py`

- [ ] **Step 1: 写 main.py**

```python
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import List, Optional

import pandas as pd
import uvicorn
from fastapi import FastAPI, Depends, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import init_db, get_db
from models import Order
from orders import create_order, get_active_order, get_order, list_orders, import_codes_for_order, get_code_library, mark_code_scanned
from detection import classify_code, refresh_order_state
from records import create_scan_record, get_recent_scans, get_recent_alarms, get_counts
from alarms import save_alarm
from camera import Camera
from settings import get_rtsp_url, set_rtsp_url, get_roi, set_roi, get_dedup_seconds, set_dedup_seconds
from schemas import OrderCreate, OrderOut, CodeOut, ScanRecordOut, AlarmRecordOut, StatusResponse, ROI

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")

app = FastAPI(title="PrintCode Guard v1")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 全局运行时状态
camera: Optional[Camera] = None
detection_thread: Optional[threading.Thread] = None
detection_running = False
app_state = {
    "current_order_id": None,
    "detection_state": {},
    "latest_code": None,
    "alarm_active": False,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app.router.lifespan_context = lifespan


# ----------------- 页面 -----------------
@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8") as f:
        return f.read()


# ----------------- 订单 -----------------
@app.post("/api/orders", response_model=OrderOut)
def api_create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    order = create_order(db, payload.name)
    app_state["current_order_id"] = order.id
    app_state["detection_state"] = refresh_order_state(db, order.id)
    return order


@app.get("/api/orders", response_model=List[OrderOut])
def api_list_orders(db: Session = Depends(get_db)):
    return list_orders(db)


@app.post("/api/orders/{order_id}/activate")
def api_activate_order(order_id: int, db: Session = Depends(get_db)):
    order = get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    app_state["current_order_id"] = order.id
    app_state["detection_state"] = refresh_order_state(db, order.id)
    return {"ok": True}


# ----------------- 码库导入 -----------------
@app.post("/api/orders/{order_id}/import")
def api_import_codes(order_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    order = get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(file.file, header=None)
        else:
            df = pd.read_excel(file.file, header=None, engine="openpyxl")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析文件失败: {e}")
    contents = [str(v).strip() for v in df.iloc[:, 0].dropna().tolist()]
    count = import_codes_for_order(db, order_id, contents)
    app_state["detection_state"] = refresh_order_state(db, order_id)
    return {"imported": count}


@app.get("/api/orders/{order_id}/codes", response_model=List[CodeOut])
def api_get_codes(order_id: int, db: Session = Depends(get_db)):
    return get_code_library(db, order_id)


# ----------------- 摄像头与 ROI -----------------
class RtspPayload(BaseModel):
    url: str


@app.post("/api/camera/open")
def api_open_camera(payload: RtspPayload, db: Session = Depends(get_db)):
    global camera
    if camera:
        camera.stop()
    camera = Camera(payload.url)
    camera.start()
    set_rtsp_url(db, payload.url)
    return {"ok": True}


@app.get("/api/camera/frame")
def api_camera_frame():
    if not camera:
        raise HTTPException(status_code=400, detail="摄像头未打开")

    def streamer():
        while True:
            jpeg = camera.get_jpeg()
            if jpeg:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
            time.sleep(0.05)

    return StreamingResponse(streamer(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.post("/api/camera/roi")
def api_set_roi(roi: ROI, db: Session = Depends(get_db)):
    global camera
    if camera:
        camera.set_roi(roi.x, roi.y, roi.w, roi.h)
    set_roi(db, roi.model_dump())
    return {"ok": True}


# ----------------- 检测控制 -----------------
@app.post("/api/detection/start")
def api_start_detection():
    global detection_running, detection_thread
    if detection_running:
        return {"ok": True}
    if not camera:
        raise HTTPException(status_code=400, detail="请先打开摄像头")
    if app_state["current_order_id"] is None:
        raise HTTPException(status_code=400, detail="请先创建或激活订单")
    detection_running = True
    detection_thread = threading.Thread(target=_detection_loop, daemon=True)
    detection_thread.start()
    return {"ok": True}


@app.post("/api/detection/stop")
def api_stop_detection():
    global detection_running
    detection_running = False
    return {"ok": True}


def _detection_loop():
    db = next(get_db())
    while detection_running:
        if not camera:
            time.sleep(0.1)
            continue
        codes = camera.read_qr_codes()
        now = __import__("datetime").datetime.utcnow()
        for content in codes:
            app_state["latest_code"] = content
            result = classify_code(content, app_state["detection_state"], now)
            create_scan_record(
                db,
                app_state["current_order_id"],
                content,
                result["status"],
                result["is_duplicate"],
                result["is_abnormal"],
            )
            if result["status"] == "ok":
                mark_code_scanned(db, app_state["current_order_id"], content)
            if result["is_abnormal"]:
                app_state["alarm_active"] = True
                save_alarm(db, app_state["current_order_id"], result["alarm_type"], content, camera)
        time.sleep(0.1)


@app.get("/api/status", response_model=StatusResponse)
def api_status(db: Session = Depends(get_db)):
    order = None
    if app_state["current_order_id"]:
        order = get_order(db, app_state["current_order_id"])
    counts = get_counts(db, app_state["current_order_id"])
    return StatusResponse(
        current_order=OrderOut.model_validate(order) if order else None,
        rtsp_url=get_rtsp_url(db),
        is_running=detection_running,
        total_scanned=counts["total"],
        duplicate_count=counts["duplicate"],
        abnormal_count=counts["abnormal"],
        latest_code=app_state["latest_code"],
        alarm_active=app_state["alarm_active"],
    )


@app.post("/api/alarm/clear")
def api_clear_alarm():
    app_state["alarm_active"] = False
    return {"ok": True}


# ----------------- 记录 -----------------
@app.get("/api/scans", response_model=List[ScanRecordOut])
def api_scans(order_id: Optional[int] = None, db: Session = Depends(get_db)):
    return get_recent_scans(db, order_id or app_state["current_order_id"], limit=20)


@app.get("/api/alarms", response_model=List[AlarmRecordOut])
def api_alarms(order_id: Optional[int] = None, db: Session = Depends(get_db)):
    return get_recent_alarms(db, order_id or app_state["current_order_id"], limit=20)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 2: Commit**

```bash
git add src/printcode_guard/main.py
git commit -m "feat: FastAPI main app with orders, camera, detection APIs"
```

---

## Task 11: 前端页面

**Files:**
- Create: `static/index.html`
- Create: `static/style.css`
- Create: `static/app.js`

- [ ] **Step 1: 写 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PrintCode Guard v1</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <div id="app">
    <header>
      <h1>PrintCode Guard <span class="tag">v1 RTSP 验证版</span></h1>
    </header>

    <div class="controls">
      <div>
        <label>RTSP 地址</label>
        <input id="rtsp-url" type="text" placeholder="rtsp://..." style="width: 320px;">
        <button id="btn-open">打开摄像头</button>
      </div>
      <div>
        <button id="btn-new-order">新建订单</button>
        <button id="btn-import">导入码库</button>
        <input id="file-import" type="file" accept=".csv,.xlsx" hidden>
      </div>
      <div>
        <button id="btn-start">开始检测</button>
        <button id="btn-stop">暂停检测</button>
        <button id="btn-clear-alarm">清除报警</button>
      </div>
    </div>

    <div class="status-bar" id="status-bar">
      <span>订单: <b id="order-name">-</b></span>
      <span>状态: <b id="run-state">停止</b></span>
      <span>已读: <b id="total-count">0</b></span>
      <span>重复: <b id="dup-count">0</b></span>
      <span>异常: <b id="err-count">0</b></span>
      <span>当前码: <b id="latest-code">-</b></span>
    </div>

    <div class="main">
      <div class="video-panel">
        <img id="video" src="" alt="实时画面" />
        <p class="hint">若自动识别不到，可在画面区域用鼠标框选二维码位置（ROI）。</p>
      </div>
      <div class="side-panel">
        <h3>最近扫码记录</h3>
        <ul id="scan-list"></ul>
        <h3>最近报警记录</h3>
        <ul id="alarm-list"></ul>
      </div>
    </div>
  </div>

  <audio id="alarm-sound" src="data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQQAAAAAAA==" preload="auto"></audio>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: 写 style.css**

```css
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, -apple-system, sans-serif; background: #f5f5f5; }
#app { max-width: 1400px; margin: 0 auto; padding: 20px; }
header { margin-bottom: 16px; }
.tag { font-size: 14px; color: #666; border: 1px solid #ccc; padding: 2px 8px; border-radius: 12px; }
.controls { display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-end; background: #fff; padding: 16px; border-radius: 8px; margin-bottom: 16px; }
.controls label { display: block; font-size: 12px; color: #666; margin-bottom: 4px; }
button { padding: 8px 16px; border: 1px solid #ccc; background: #fff; border-radius: 4px; cursor: pointer; }
button:hover { background: #f0f0f0; }
.status-bar { background: #fff; padding: 12px 16px; border-radius: 8px; display: flex; gap: 24px; margin-bottom: 16px; }
.main { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; }
.video-panel, .side-panel { background: #fff; padding: 16px; border-radius: 8px; }
.video-panel img { width: 100%; max-height: 600px; object-fit: contain; background: #000; }
.hint { font-size: 12px; color: #666; margin-top: 8px; }
.side-panel h3 { margin-top: 0; font-size: 16px; border-bottom: 1px solid #eee; padding-bottom: 8px; }
.side-panel ul { list-style: none; padding: 0; margin: 0 0 24px 0; max-height: 260px; overflow-y: auto; }
.side-panel li { padding: 6px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px; }
.alarm { color: #c00; font-weight: bold; }
body.alarming { animation: flashRed 1s infinite; }
@keyframes flashRed { 0%,100% { background: #f5f5f5; } 50% { background: #ffe0e0; } }
```

- [ ] **Step 3: 写 app.js**

```javascript
const API = "";
let isSelecting = false;
let startX, startY, selectionBox;
let currentOrderId = null;

function el(id) { return document.getElementById(id); }

async function fetchJson(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

el("btn-open").onclick = async () => {
  const url = el("rtsp-url").value.trim();
  if (!url) return alert("请输入 RTSP 地址");
  await fetchJson("/api/camera/open", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ url }),
  });
  el("video").src = "/api/camera/frame?" + Date.now();
};

el("btn-new-order").onclick = async () => {
  const name = prompt("订单名称:");
  if (!name) return;
  const order = await fetchJson("/api/orders", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ name }),
  });
  currentOrderId = order.id;
  updateStatus();
};

el("btn-import").onclick = () => el("file-import").click();
el("file-import").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file || !currentOrderId) return alert("请先创建订单");
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`/api/orders/${currentOrderId}/import`, { method: "POST", body: form });
  const json = await res.json();
  alert(`成功导入 ${json.imported} 条码`);
};

el("btn-start").onclick = () => fetchJson("/api/detection/start", { method: "POST" }).then(updateStatus);
el("btn-stop").onclick = () => fetchJson("/api/detection/stop", { method: "POST" }).then(updateStatus);
el("btn-clear-alarm").onclick = () => fetchJson("/api/alarm/clear", { method: "POST" }).then(updateStatus);

async function updateStatus() {
  const s = await fetchJson("/api/status");
  el("order-name").textContent = s.current_order ? s.current_order.name : "-";
  el("run-state").textContent = s.is_running ? "运行中" : "停止";
  el("total-count").textContent = s.total_scanned;
  el("dup-count").textContent = s.duplicate_count;
  el("err-count").textContent = s.abnormal_count;
  el("latest-code").textContent = s.latest_code || "-";
  if (s.current_order) currentOrderId = s.current_order.id;
  if (s.alarm_active) {
    document.body.classList.add("alarming");
    playBeep();
  } else {
    document.body.classList.remove("alarming");
  }
}

async function updateLists() {
  const [scans, alarms] = await Promise.all([
    fetchJson("/api/scans"),
    fetchJson("/api/alarms"),
  ]);
  el("scan-list").innerHTML = scans.map(r =>
    `<li>${new Date(r.read_at).toLocaleTimeString()} — ${r.content} <span class="${r.is_abnormal ? 'alarm' : ''}">${r.result_status}</span></li>`
  ).join("");
  el("alarm-list").innerHTML = alarms.map(a =>
    `<li class="alarm">${new Date(a.alarm_at).toLocaleTimeString()} — [${a.alarm_type}] ${a.content}</li>`
  ).join("");
}

function playBeep() {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const osc = ctx.createOscillator();
  osc.type = "square";
  osc.frequency.value = 880;
  const gain = ctx.createGain();
  gain.gain.value = 0.1;
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.2);
}

// ROI 框选（简化：在 img 上点两点形成矩形）
el("video").onmousedown = (e) => {
  const rect = el("video").getBoundingClientRect();
  startX = e.clientX - rect.left;
  startY = e.clientY - rect.top;
  isSelecting = true;
  if (!selectionBox) {
    selectionBox = document.createElement("div");
    selectionBox.className = "selection-box";
    selectionBox.style.position = "absolute";
    selectionBox.style.border = "2px dashed #0f0";
    selectionBox.style.background = "rgba(0,255,0,0.1)";
    el("video").parentElement.appendChild(selectionBox);
  }
  selectionBox.style.left = startX + "px";
  selectionBox.style.top = startY + "px";
  selectionBox.style.width = "0px";
  selectionBox.style.height = "0px";
};

document.onmousemove = (e) => {
  if (!isSelecting || !selectionBox) return;
  const rect = el("video").getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  const w = Math.abs(x - startX);
  const h = Math.abs(y - startY);
  const left = Math.min(x, startX);
  const top = Math.min(y, startY);
  selectionBox.style.left = left + rect.left - rect.left + "px";
  selectionBox.style.top = top + "px";
  selectionBox.style.width = w + "px";
  selectionBox.style.height = h + "px";
};

document.onmouseup = async () => {
  if (!isSelecting || !selectionBox) return;
  isSelecting = false;
  const img = el("video");
  const rect = img.getBoundingClientRect();
  const box = selectionBox.getBoundingClientRect();
  const displayW = rect.width;
  const displayH = rect.height;
  const naturalW = img.naturalWidth || displayW;
  const naturalH = img.naturalHeight || displayH;
  const scaleX = naturalW / displayW;
  const scaleY = naturalH / displayH;
  const x = Math.round((box.left - rect.left) * scaleX);
  const y = Math.round((box.top - rect.top) * scaleY);
  const w = Math.round(box.width * scaleX);
  const h = Math.round(box.height * scaleY);
  await fetchJson("/api/camera/roi", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ x, y, w, h }),
  });
  alert("ROI 已设置");
};

setInterval(() => { updateStatus(); updateLists(); }, 1000);
```

- [ ] **Step 4: Commit**

```bash
git add static/index.html static/style.css static/app.js
git commit -m "feat: simple web UI for monitoring and control"
```

---

## Task 12: 本地 PostgreSQL 启动脚本与验证

**Files:**
- Create: `scripts/init_db.sh`

- [ ] **Step 1: 写 init_db.sh**

```bash
#!/bin/bash
set -e
psql -U postgres -c "CREATE DATABASE printcode_guard;" 2>/dev/null || echo "Database may already exist"
```

- [ ] **Step 2: 验证启动**

```bash
cd src/printcode_guard
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

在浏览器打开 http://localhost:8000/ 验证页面加载。

- [ ] **Step 3: Commit**

```bash
git add scripts/init_db.sh
git commit -m "chore: add local postgres init script"
```

---

## Self-Review

**1. Spec coverage:**
- RTSP 视频流读取：Task 6 `camera.py` ✔
- 二维码识别：Task 6 `read_qr_codes` 使用 pyzbar ✔
- 保存到本地数据库：Task 2/4/8 SQLAlchemy + PostgreSQL ✔
- 导入订单码库：Task 4 + Task 10 `/api/orders/{id}/import` CSV/Excel ✔
- 判断是否属于当前订单码库：Task 5 `classify_code` ✔
- 判断是否重复读取：Task 5 短时间窗口去重 + Task 8 记录 ✔
- 异常报警：Task 7 `alarms.py` + Task 10 alarm API ✔
- 电脑声音 + 页面红色：Task 11 CSS animation + Web Audio beep ✔
- 异常截图保存：Task 7 `save_alarm` ✔
- 实时画面 + 读码 + 数量 + 记录：Task 11 UI + Task 10 status/lists ✔
- 光电开关预留：未直接实现，但 `detection.py` 的 `classify_code` 与 `camera.py` 分离，未来可在光电触发处调用 `read_qr_codes` 后进入同样分类逻辑。

**2. Placeholder scan:** 无 TBD/TODO/实现缺失；所有步骤包含完整代码。

**3. Type consistency:** `classify_code` 返回 dict 的 key 与 `main.py` 消费一致；`StatusResponse` 字段与 `/api/status` 返回一致。

**Gap:** 未实现光电开关接入、边角小序号、整幅面检测、多摄像头、YOLO/NPU、80m/min 高速 —— 这些明确属于第一版不做范围。

---

## 执行方式

计划完成后两种执行方式：

1. **Subagent-Driven（推荐）** — 每个 Task 派一个子代理，严格按步骤实现并测试。
2. **Inline Execution** — 在当前会话中批量实现所有 Task，完成后统一验证。

由于用户已明确要求先做第一版 Demo，建议在计划获批后直接 Inline Execution 一次性完成并跑通验证。
