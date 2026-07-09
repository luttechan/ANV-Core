from __future__ import annotations

import io
import os
import socket
import sys
import tempfile
import time
import zipfile
from pathlib import Path

try:
    import requests
except Exception:
    requests = None

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:
    Fernet = None
    InvalidToken = Exception

_RUNTIME_BOUND = False

LAMI_PACK_REMOTE_URL = "https://raw.githubusercontent.com/luttechan/AnkiVoice-Developer-Utility/refs/heads/main/lami.lpack"
LAMI_PACK_KEY = b"pU-0_E-7tYlgmw2Bmylyu2GlD5njemWxy_ZwpfdRxBc="
LAMI_PACK_NAME = "lami.lpack"
LAMI_EXPECTED_ENTRY = "lami.py"


def bind_runtime(runtime_module):
    global _RUNTIME_BOUND

    for name in dir(runtime_module):
        if name.startswith("__"):
            continue
        globals()[name] = getattr(runtime_module, name)

    _RUNTIME_BOUND = True
    return True


def _require_runtime():
    if not _RUNTIME_BOUND:
        raise RuntimeError("lami_pack_updater.py is not a standalone program.")


def _safe_call(func_name, *args, default=None, **kwargs):
    func = globals().get(func_name)
    if not callable(func):
        return default
    try:
        return func(*args, **kwargs)
    except Exception:
        return default


def _base_dir() -> Path:
    return Path(globals().get("BASE_DIR", Path(__file__).resolve().parent.parent))


def _setting_dir() -> Path:
    return Path(globals().get("SETTING_DIR", _base_dir() / "setting"))


def _pack_path() -> Path:
    return _setting_dir() / LAMI_PACK_NAME


def _headers() -> dict:
    headers = globals().get("HEADERS")
    if isinstance(headers, dict):
        result = dict(headers)
    else:
        result = {"User-Agent": "AnkiVoice"}
    result.setdefault("User-Agent", "AnkiVoice")
    result.setdefault("Accept", "application/octet-stream,*/*")
    return result


def _terminal_size():
    try:
        import shutil
        size = shutil.get_terminal_size((132, 36))
        return max(100, int(size.columns)), max(30, int(size.lines))
    except Exception:
        return 132, 36


def _enable_virtual_terminal_mode():
    if os.name != "nt":
        return False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def _fit(text, width, align="left"):
    text = str(text)
    if len(text) > width:
        text = text[:max(0, width - 3)] + "..."
    pad = max(0, width - len(text))
    if align == "center":
        left = pad // 2
        return " " * left + text + " " * (pad - left)
    if align == "right":
        return " " * pad + text
    return text + " " * pad


def _blue_line(line=""):
    try:
        sys.stdout.write("\033[44;97m" + str(line) + "\n")
        sys.stdout.flush()
    except Exception:
        print(str(line))


def _rule(width, char="-"):
    return " +" + char * max(8, width - 2) + "+"


def _box(text, width, align="left"):
    inner = max(20, width - 4)
    return " | " + _fit(text, inner, align=align) + " |"


def _clear_blue():
    _enable_virtual_terminal_mode()
    if os.name == "nt":
        try:
            os.system("color 1F")
        except Exception:
            pass
    try:
        sys.stdout.write("\033[44;97m\033[2J\033[H")
        sys.stdout.flush()
    except Exception:
        _safe_call("ui_clear_screen")


def _restore_screen():
    _enable_virtual_terminal_mode()
    try:
        sys.stdout.write("\033[0m")
        sys.stdout.flush()
    except Exception:
        pass
    if os.name == "nt":
        try:
            os.system("color 07")
        except Exception:
            pass
    _safe_call("setup_console_window")
    _safe_call("apply_screen_mode")


def _draw_receipt(stage, status, rows=None, progress=None, footer="PRESS ENTER TO RETURN TO ADMINISTRATIVE PORTAL"):
    cols, lines = _terminal_size()
    width = min(132, max(100, cols - 2))
    body_height = max(12, min(18, lines - 16))
    rows = list(rows or [])

    _clear_blue()
    _blue_line(_rule(width, "="))
    _blue_line(_box("LCD ADMINISTRATIVE DOCUMENT PORTAL", width, "center"))
    _blue_line(_box("ATTACHMENT RECEIPT DESK / AUXILIARY SERVICE IMAGE", width, "center"))
    _blue_line(_rule(width, "-"))
    _blue_line(_box("Document No. SDD-TRN-OBV7-AXR-06-12   Appendix 47   Attachment: A1", width))
    _blue_line(_box("Filing Target: SETTING / SERVICE-IMAGE / LAMI   Classification: INTERNAL ROUTINE", width))
    _blue_line(_rule(width, "="))
    _blue_line(_box(f"Stage : {stage}", width))
    _blue_line(_box(f"Status: {status}", width))

    if progress is not None:
        progress = max(0.0, min(1.0, float(progress)))
        bar_width = 38
        fill = int(round(bar_width * progress))
        bar = "█" * fill + "░" * (bar_width - fill)
        _blue_line(_box(f"Receipt Meter: [{bar}] {progress * 100:5.1f}%", width))
    else:
        _blue_line(_box("Receipt Meter: [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]   0.0%", width))

    _blue_line(_rule(width, "-"))
    shown = rows[:body_height]
    for row in shown:
        _blue_line(_box(row, width))
    for _ in range(max(0, body_height - len(shown))):
        _blue_line(_box("", width))
    _blue_line(_rule(width, "-"))
    _blue_line(_box(footer, width))
    _blue_line(_rule(width, "="))


def _pause():
    try:
        input("\n  > ")
    except EOFError:
        pass


def _network_preflight():
    if requests is None:
        raise RuntimeError("HTTP receipt library unavailable")
    if Fernet is None:
        raise RuntimeError("service image verifier unavailable")

    host = "raw.githubusercontent.com"
    started = time.perf_counter()
    socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    dns_elapsed = time.perf_counter() - started

    started = time.perf_counter()
    sock = socket.create_connection((host, 443), timeout=7)
    sock.close()
    tcp_elapsed = time.perf_counter() - started

    return dns_elapsed, tcp_elapsed


def _download_to_temp():
    setting_dir = _setting_dir()
    setting_dir.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(prefix="lami_receipt_", suffix=".lpack.tmp", dir=str(setting_dir))
    temp_path = Path(temp_name)

    try:
        with requests.get(LAMI_PACK_REMOTE_URL, headers=_headers(), timeout=(5, 30), stream=True) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length") or 0)
            received = 0

            with os.fdopen(fd, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    f.write(chunk)
                    received += len(chunk)
                    if total:
                        _draw_receipt(
                            "ATTACHMENT TRANSFER",
                            "RECEIVING SEALED SERVICE IMAGE",
                            [
                                "Remote shelf acknowledged attachment request.",
                                f"Received: {received:,} / {total:,} bytes",
                                "No document text is displayed during sealed image transfer.",
                            ],
                            progress=min(0.72, received / max(total, 1) * 0.72),
                            footer="TRANSFER IN PROGRESS - DO NOT CLOSE TERMINAL",
                        )

        if received <= 0:
            raise RuntimeError("empty attachment received")

        return temp_path, received

    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        try:
            temp_path.unlink()
        except Exception:
            pass
        raise


def _verify_lami_pack_bytes(encrypted_data: bytes):
    if not encrypted_data:
        raise RuntimeError("attachment body is empty")

    try:
        decrypted_zip = Fernet(LAMI_PACK_KEY).decrypt(encrypted_data)
    except InvalidToken:
        raise RuntimeError("attachment authentication failed")

    with zipfile.ZipFile(io.BytesIO(decrypted_zip), "r") as zf:
        names = zf.namelist()
        if LAMI_EXPECTED_ENTRY not in names:
            raise RuntimeError("service entry point missing")
        lami_source = zf.read(LAMI_EXPECTED_ENTRY).decode("utf-8", errors="replace")

    compile(lami_source, LAMI_EXPECTED_ENTRY, "exec")

    return {
        "entries": len(names),
        "source_size": len(lami_source.encode("utf-8")),
        "zip_size": len(decrypted_zip),
    }


def _file_pack(temp_path: Path):
    target = _pack_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    backup = target.with_suffix(".lpack.bak")
    if target.exists():
        backup.write_bytes(target.read_bytes())

    temp_path.replace(target)
    return target, backup if backup.exists() else None


def retrieve_lami_pack_from_remote_portal(source="appendix_47"):
    _require_runtime()

    rows = [
        "Appendix 47 closeout returned control to the attachment receipt desk.",
        "Attachment A1 is marked as sealed auxiliary service image.",
        "Receipt procedure will verify line availability before filing.",
    ]
    _draw_receipt("RECEIPT PRECHECK", "WAITING FOR REMOTE SHELF LINE", rows, progress=0.05, footer="RECEIPT PRECHECK IN PROGRESS")

    temp_path = None

    try:
        dns_elapsed, tcp_elapsed = _network_preflight()
        rows = [
            "Remote shelf name resolved.",
            f"Directory lookup: {dns_elapsed * 1000:.1f}ms",
            f"Relay line open: {tcp_elapsed * 1000:.1f}ms",
            "Attachment request has been cleared for transfer.",
        ]
        _draw_receipt("LINE CONFIRMATION", "REMOTE SHELF AVAILABLE", rows, progress=0.20, footer="ATTACHMENT TRANSFER WILL BEGIN")
        time.sleep(0.35)

        temp_path, received = _download_to_temp()
        rows = [
            "Sealed service image received into temporary holding area.",
            f"Received body: {received:,} bytes",
            "Authentication probe is being performed before local filing.",
        ]
        _draw_receipt("AUTHENTICATION PROBE", "SEALED IMAGE RECEIVED", rows, progress=0.78, footer="VERIFYING SERVICE IMAGE")
        time.sleep(0.25)

        info = _verify_lami_pack_bytes(temp_path.read_bytes())
        rows = [
            "Package authentication completed.",
            f"Archive members: {info['entries']}",
            f"Decrypted archive size: {info['zip_size']:,} bytes",
            "Entry point inspection completed.",
        ]
        _draw_receipt("IMAGE INSPECTION", "PACKAGE ACCEPTED", rows, progress=0.90, footer="FILING SERVICE IMAGE")
        time.sleep(0.25)

        target, backup = _file_pack(temp_path)
        temp_path = None
        rows = [
            "Attachment A1 has been filed into the local service image shelf.",
            f"Filed name: {target.name}",
            f"Filing shelf: {target.parent}",
            "Previous filing was retained as backup." if backup else "No previous filing was present.",
            "Auxiliary service image is now available for the route handler.",
        ]
        _draw_receipt("RECEIPT CLOSED", "LOCAL FILING COMPLETE", rows, progress=1.0)
        _safe_call("log_only", f"[LCD ATTACHMENT RECEIPT] lami.lpack filed: {target}")
        _pause()
        return True

    except Exception as e:
        rows = [
            "Attachment A1 was not filed.",
            f"Closeout status: {type(e).__name__}",
            str(e),
            "Existing local service image, if any, was not replaced.",
        ]
        _draw_receipt("RECEIPT ABORTED", "LOCAL FILING NOT CHANGED", rows, progress=0.0)
        _safe_call("log_only", f"[LCD ATTACHMENT RECEIPT FAILED] {type(e).__name__}: {e}")
        _pause()
        return False

    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except Exception:
                pass
        _restore_screen()
        _safe_call("ui_clear_screen")


__all__ = [
    "bind_runtime",
    "retrieve_lami_pack_from_remote_portal",
]
