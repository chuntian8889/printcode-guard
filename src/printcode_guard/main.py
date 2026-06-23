import datetime
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import List, Optional

import pandas as pd
import uvicorn
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import init_db, get_db, SessionLocal
from .models import Order
from .orders import (
    create_order,
    get_order,
    list_orders,
    import_codes_for_order,
    get_code_library,
    mark_code_scanned,
)
from .detection import classify_code, refresh_order_state
from .records import create_scan_record, get_recent_scans, get_recent_alarms, get_counts
from .alarms import save_alarm
from .scanner import ScannerSource
from .buzzer import AlarmBuzzer
from .settings import get_scanner_device, set_scanner_device
from .schemas import (
    OrderCreate,
    OrderOut,
    CodeOut,
    ScanRecordOut,
    AlarmRecordOut,
    StatusResponse,
    ScannerDevicePayload,
)

STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static"
)

# 全局运行时状态
scanner: Optional[ScannerSource] = None
detection_thread: Optional[threading.Thread] = None
detection_running = False
buzzer: Optional[AlarmBuzzer] = None
app_state = {
    "current_order_id": None,
    "detection_state": {},
    "latest_code": None,
    "alarm_active": False,
    "scanner_error": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    global buzzer, scanner
    buzzer = AlarmBuzzer()

    db = SessionLocal()
    try:
        scanner_device = get_scanner_device(db)
        try:
            scanner = ScannerSource(device_path=scanner_device)
            scanner.start()
        except Exception as e:
            app_state["scanner_error"] = str(e)
            scanner = None
    finally:
        db.close()
    yield
    if scanner:
        scanner.stop()
    if buzzer:
        buzzer.stop()


app = FastAPI(title="PrintCode Guard v1", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ----------------- 页面 -----------------
@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8") as f:
        return f.read()


# ----------------- 订单 -----------------
@app.post("/api/orders", response_model=OrderOut)
def api_create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    global app_state
    order = create_order(db, payload.name)
    app_state["current_order_id"] = order.id
    app_state["detection_state"] = refresh_order_state(db, order.id)
    return order


@app.get("/api/orders", response_model=List[OrderOut])
def api_list_orders(db: Session = Depends(get_db)):
    return list_orders(db)


@app.post("/api/orders/{order_id}/activate")
def api_activate_order(order_id: int, db: Session = Depends(get_db)):
    global app_state
    order = get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    app_state["current_order_id"] = order.id
    app_state["detection_state"] = refresh_order_state(db, order.id)
    return {"ok": True}


# ----------------- 码库导入 -----------------
@app.post("/api/orders/{order_id}/import")
def api_import_codes(
    order_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    global app_state
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
    if app_state["current_order_id"] == order_id:
        app_state["detection_state"] = refresh_order_state(db, order_id)
    return {"imported": count}


@app.get("/api/orders/{order_id}/codes", response_model=List[CodeOut])
def api_get_codes(order_id: int, db: Session = Depends(get_db)):
    return get_code_library(db, order_id)


# ----------------- 扫描头配置 -----------------
@app.post("/api/scanner/device")
def api_set_scanner_device(
    payload: ScannerDevicePayload, db: Session = Depends(get_db)
):
    set_scanner_device(db, payload.device)
    return {"ok": True, "device": payload.device}


# ----------------- 检测控制 -----------------
@app.post("/api/detection/start")
def api_start_detection():
    global detection_running, detection_thread
    if detection_running:
        return {"ok": True}
    if not scanner:
        raise HTTPException(status_code=400, detail="扫描头未初始化")
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
    db = SessionLocal()
    try:
        while detection_running:
            if not scanner:
                time.sleep(0.1)
                continue
            code = scanner.get_code(timeout=0.5)
            if not code:
                continue
            now = datetime.datetime.utcnow()
            app_state["latest_code"] = code
            result = classify_code(
                code, app_state["detection_state"], now, db
            )

            if result["should_record"]:
                create_scan_record(
                    db,
                    app_state["current_order_id"],
                    code,
                    result["status"],
                    result["is_duplicate"],
                    result["is_abnormal"],
                )

            if result["status"] == "ok":
                mark_code_scanned(
                    db, app_state["current_order_id"], code
                )

            if result["is_abnormal"]:
                app_state["alarm_active"] = True
                save_alarm(
                    db,
                    app_state["current_order_id"],
                    result["alarm_type"],
                    code,
                )
                if buzzer:
                    buzzer.start()
    finally:
        db.close()


@app.get("/api/status", response_model=StatusResponse)
def api_status(db: Session = Depends(get_db)):
    order = None
    if app_state["current_order_id"]:
        order = get_order(db, app_state["current_order_id"])
    counts = get_counts(db, app_state["current_order_id"])
    scanner_device = scanner.device_path if scanner else get_scanner_device(db)
    scanner_online = scanner.is_alive if scanner else False
    scanner_error = app_state.get("scanner_error")
    if scanner and scanner.error:
        scanner_error = scanner.error
    buzzer_backend = buzzer.backend if buzzer else None
    return StatusResponse(
        current_order=OrderOut.model_validate(order) if order else None,
        scanner_device=scanner_device,
        scanner_online=scanner_online,
        scanner_error=scanner_error,
        buzzer_backend=buzzer_backend,
        is_running=detection_running,
        total_scanned=counts["total"],
        duplicate_count=counts["duplicate"],
        abnormal_count=counts["abnormal"],
        latest_code=app_state["latest_code"],
        alarm_active=app_state["alarm_active"],
    )


@app.post("/api/alarm/clear")
def api_clear_alarm():
    global app_state
    app_state["alarm_active"] = False
    if buzzer:
        buzzer.stop()
    return {"ok": True}


@app.post("/api/buzzer/test")
def api_buzzer_test(duration: int = 2):
    """测试蜂鸣器/喇叭，持续指定秒数。"""
    if not buzzer:
        raise HTTPException(status_code=500, detail="报警器未初始化")
    buzzer.start()
    threading.Timer(duration, buzzer.stop).start()
    return {"ok": True, "backend": buzzer.backend, "duration": duration}


# ----------------- 记录 -----------------
@app.get("/api/scans", response_model=List[ScanRecordOut])
def api_scans(order_id: Optional[int] = None, db: Session = Depends(get_db)):
    return get_recent_scans(
        db, order_id or app_state["current_order_id"], limit=20
    )


@app.get("/api/alarms", response_model=List[AlarmRecordOut])
def api_alarms(order_id: Optional[int] = None, db: Session = Depends(get_db)):
    return get_recent_alarms(
        db, order_id or app_state["current_order_id"], limit=20
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8700, reload=True)
