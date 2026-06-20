import os
import threading
import time
from typing import List, Optional, Tuple
import cv2
from pyzbar.pyzbar import decode


class Camera:
    def __init__(self, rtsp_url: str):
        self.rtsp_url = rtsp_url
        self.cap: Optional[cv2.VideoCapture] = None
        self.frame: Optional = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.roi: Optional[Tuple[int, int, int, int]] = None
        self._static_image: Optional = None

    def start(self):
        if self.running:
            return
        # 支持本地图片路径作为测试/验证用途
        if os.path.isfile(self.rtsp_url):
            img = cv2.imread(self.rtsp_url)
            if img is None:
                raise RuntimeError(f"无法读取图片: {self.rtsp_url}")
            self._static_image = img
            self.running = True
            self.thread = threading.Thread(target=self._static_loop, daemon=True)
            self.thread.start()
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

    def _static_loop(self):
        while self.running:
            with self.lock:
                self.frame = self._static_image.copy()
            time.sleep(0.05)

    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def get_jpeg(self, quality: int = 85) -> Optional[bytes]:
        frame = self.get_frame()
        if frame is None:
            return None
        display = frame.copy()
        if self.roi:
            x, y, w, h = self.roi
            cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 0), 2)
        ok, buf = cv2.imencode(
            ".jpg", display, [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        )
        return buf.tobytes() if ok else None

    def set_roi(self, x: int, y: int, w: int, h: int):
        self.roi = (x, y, w, h)

    def read_qr_codes(self) -> List[str]:
        frame = self.get_frame()
        if frame is None:
            return []
        if self.roi:
            x, y, w, h = self.roi
            h_max, w_max = frame.shape[:2]
            x, y = max(0, x), max(0, y)
            w = min(w, w_max - x)
            h = min(h, h_max - y)
            if w <= 0 or h <= 0:
                return []
            frame = frame[y : y + h, x : x + w]
        decoded = decode(frame)
        return [d.data.decode("utf-8", errors="ignore") for d in decoded]
