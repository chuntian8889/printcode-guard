import fcntl
import glob
import os
import queue
import struct
import threading
from typing import Optional, Set

# evdev EV_IOCGRAB for 64-bit Linux
EVIOCGRAB = 0x40044590

# Linux keycode -> ASCII (US layout, no shift)
KEYMAP = {
    2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7", 9: "8", 10: "9", 11: "0",
    12: "-", 13: "=",
    16: "q", 17: "w", 18: "e", 19: "r", 20: "t", 21: "y", 22: "u", 23: "i", 24: "o", 25: "p",
    26: "[", 27: "]",
    30: "a", 31: "s", 32: "d", 33: "f", 34: "g", 35: "h", 36: "j", 37: "k", 38: "l",
    39: ";", 40: "'", 43: "\\",
    44: "z", 45: "x", 46: "c", 47: "v", 48: "b", 49: "n", 50: "m",
    51: ",", 52: ".", 53: "/", 57: " ",
    79: "1", 80: "2", 81: "3", 82: "4", 83: "5", 84: "6", 85: "7", 86: "8", 87: "9", 88: "0",
}

# Shifted characters
SHIFT_KEYMAP = {
    2: "!", 3: "@", 4: "#", 5: "$", 6: "%", 7: "^", 8: "&", 9: "*", 10: "(", 11: ")",
    12: "_", 13: "+",
    16: "Q", 17: "W", 18: "E", 19: "R", 20: "T", 21: "Y", 22: "U", 23: "I", 24: "O", 25: "P",
    26: "{", 27: "}",
    30: "A", 31: "S", 32: "D", 33: "F", 34: "G", 35: "H", 36: "J", 37: "K", 38: "L",
    39: ":", 40: '"', 43: "|",
    44: "Z", 45: "X", 46: "C", 47: "V", 48: "B", 49: "N", 50: "M",
    51: "<", 52: ">", 53: "?",
}

SHIFT_CODES: Set[int] = {42, 54}  # LEFTSHIFT, RIGHTSHIFT


class ScannerSource:
    """USB HID 键盘式二维码扫描头数据源。"""

    def __init__(self, device_path: Optional[str] = None):
        """
        device_path: 显式指定的 evdev 节点。为空时自动发现 VID/PID 0218:0210。
        """
        self._configured_path = device_path
        self._device_path: Optional[str] = None
        self._fd: Optional[os._fdopen] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._code_queue: queue.Queue[str] = queue.Queue(maxsize=100)
        self._error: Optional[str] = None

    @staticmethod
    def discover_device() -> Optional[str]:
        """通过 /sys 属性匹配 VID=0218 PID=0210。"""
        for event_dir in glob.glob("/sys/class/input/event*"):
            device_dir = os.path.join(event_dir, "device")
            vendor_path = os.path.join(device_dir, "id", "vendor")
            product_path = os.path.join(device_dir, "id", "product")
            if not os.path.isfile(vendor_path):
                continue
            try:
                with open(vendor_path) as f:
                    vendor = f.read().strip().lower()
                with open(product_path) as f:
                    product = f.read().strip().lower()
                if vendor == "0218" and product == "0210":
                    return os.path.join("/dev", "input", os.path.basename(event_dir))
            except Exception:
                continue
        return None

    def start(self) -> None:
        if self._running:
            return

        path = self._configured_path
        if path and os.path.exists(path):
            self._device_path = path
        else:
            self._device_path = self.discover_device()

        if not self._device_path:
            raise RuntimeError("未找到 USB 扫描头设备")

        try:
            self._fd = open(self._device_path, "rb")
            fcntl.ioctl(self._fd, EVIOCGRAB, 1)
        except PermissionError as e:
            raise RuntimeError(
                f"无权限打开扫描头 {self._device_path}，请确认当前用户在 input 组"
            ) from e
        except Exception as e:
            raise RuntimeError(f"无法打开扫描头 {self._device_path}: {e}") from e

        self._running = True
        self._error = None
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._fd:
            try:
                fcntl.ioctl(self._fd, EVIOCGRAB, 0)
            except Exception:
                pass
            try:
                self._fd.close()
            except Exception:
                pass
            self._fd = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    @property
    def device_path(self) -> Optional[str]:
        return self._device_path

    @property
    def is_alive(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    @property
    def error(self) -> Optional[str]:
        return self._error

    def get_code(self, timeout: Optional[float] = None) -> Optional[str]:
        try:
            return self._code_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _read_loop(self) -> None:
        buffer = ""
        shift = False
        try:
            while self._running:
                data = self._fd.read(24)
                if len(data) != 24:
                    continue
                sec, usec, typ, code, val = struct.unpack("qqHHi", data)
                if typ != 1:  # EV_KEY
                    continue
                if code in SHIFT_CODES:
                    shift = val in (1, 2)
                    continue
                if val != 1:  # only key press
                    continue
                if code == 28:  # ENTER
                    if buffer:
                        try:
                            self._code_queue.put(buffer, block=False)
                        except queue.Full:
                            pass
                        buffer = ""
                else:
                    ch = (SHIFT_KEYMAP if shift else KEYMAP).get(code, f"<code:{code}>")
                    buffer += ch
        except Exception as e:
            self._error = str(e)
            self._running = False
