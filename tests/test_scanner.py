import struct
import threading
import time
from printcode_guard.scanner import ScannerSource


def pack_key_event(code, value):
    """构造一个 evdev input_event (24 bytes)。"""
    return struct.pack("qqHHi", 0, 0, 1, code, value)


def make_code_events(text):
    """把字符串转成按下/释放的 key 事件序列。"""
    events = b""
    keymap = {
        "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
        "A": (30, True), "B": (48, True), "C": (46, True), "D": (32, True), "E": (18, True),
        "F": (33, True), "G": (34, True), "H": (35, True), "I": (23, True), "J": (36, True),
        "K": (37, True), "L": (38, True), "M": (50, True), "N": (49, True), "O": (24, True),
        "P": (25, True), "Q": (16, True), "R": (19, True), "S": (31, True), "T": (20, True),
        "U": (22, True), "V": (47, True), "W": (17, True), "X": (45, True), "Y": (21, True),
        "Z": (44, True),
        "a": 30, "b": 48, "c": 46, "d": 32, "e": 18, "f": 33, "g": 34, "h": 35, "i": 23,
        "j": 36, "k": 37, "l": 38, "m": 50, "n": 49, "o": 24, "p": 25, "q": 16, "r": 19,
        "s": 31, "t": 20, "u": 22, "v": 47, "w": 17, "x": 45, "y": 21, "z": 44,
        ":": (39, True), "/": (53, False),
    }
    for ch in text:
        mapping = keymap.get(ch)
        if mapping is None:
            continue
        if isinstance(mapping, tuple):
            code, shift = mapping
            if shift:
                events += pack_key_event(42, 1)
                events += pack_key_event(code, 1)
                events += pack_key_event(code, 0)
                events += pack_key_event(42, 0)
            else:
                events += pack_key_event(code, 1)
                events += pack_key_event(code, 0)
        else:
            events += pack_key_event(mapping, 1)
            events += pack_key_event(mapping, 0)
    events += pack_key_event(28, 1)
    events += pack_key_event(28, 0)
    return events


class FakeFd:
    def __init__(self, events):
        self._data = events
        self._pos = 0
        self._closed = False

    def read(self, n):
        if self._pos >= len(self._data):
            time.sleep(0.01)
            return b""
        chunk = self._data[self._pos : self._pos + n]
        self._pos += len(chunk)
        return chunk

    def close(self):
        self._closed = True


def test_scanner_source_assembles_barcode():
    scanner = ScannerSource(device_path="/dev/null")
    events = make_code_events("ABC:123")
    scanner._fd = FakeFd(events)
    scanner._running = True
    scanner._device_path = "/dev/null"

    t = threading.Thread(target=scanner._read_loop)
    t.start()
    code = scanner.get_code(timeout=1.0)
    scanner.stop()
    assert code == "ABC:123"


def test_scanner_source_returns_none_when_empty():
    scanner = ScannerSource(device_path="/dev/null")
    scanner._fd = FakeFd(b"")
    scanner._running = True
    scanner._device_path = "/dev/null"

    t = threading.Thread(target=scanner._read_loop)
    t.start()
    code = scanner.get_code(timeout=0.2)
    scanner.stop()
    assert code is None
