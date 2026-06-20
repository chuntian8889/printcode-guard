#!/usr/bin/env python3
"""实时清晰度检测工具。

用法：
    .venv/bin/python scripts/focus_helper.py rtsp://admin:xxx@192.168.0.x:554/live/ch00_0

把二维码放在摄像头前，慢慢前后移动，观察"清晰度"数值。
数值越大表示越清晰，找到最大值的位置固定下来即可。
"""
import sys
import time
import cv2

url = sys.argv[1] if len(sys.argv) > 1 else "rtsp://admin:TYPOLG@192.168.0.7:554/live/ch00_0"

cap = cv2.VideoCapture(url)
if not cap.isOpened():
    print(f"无法打开: {url}")
    sys.exit(1)

print(f"已连接: {url}")
print("慢慢移动二维码，清晰度数值最大时即为最清楚位置。按 Ctrl+C 停止。\n")

try:
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.05)
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        score = cv2.Laplacian(gray, cv2.CV_64F).var()
        bar = "█" * min(int(score / 50), 40)
        print(f"清晰度: {score:8.1f} {bar}", flush=True)
        time.sleep(0.2)
except KeyboardInterrupt:
    print("\n停止")
finally:
    cap.release()
