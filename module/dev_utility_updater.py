if __name__ == "__main__":
    print()
    print("[ERROR] module/dev_utility_updater.py is not a standalone program.")
    print("Run AnkiVoice.py instead.")
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass
    raise SystemExit(1)

import ast
import os
import socket
import tempfile
import time
from pathlib import Path

try:
    import requests
except Exception:
    requests = None

try:
    from cryptography.fernet import Fernet
except Exception:
    Fernet = None

_RUNTIME_BOUND = False

RAW_DEV_UTILITY_URL = "https://raw.githubusercontent.com/luttechan/AnkiVoice-Developer-Utility/refs/heads/main/Dev_Utility.py"
DEV_UTILITY_PACK_KEY = b"A4ePoFGO7zaBd_HZAdQjipj1uF-xaWQ8GddnUrknVdo="


def bind_runtime(runtime_module):
    global _RUNTIME_BOUND

    for name in dir(runtime_module):
        if name.startswith("__"):
            continue
        globals()[name] = getattr(runtime_module, name)

    _RUNTIME_BOUND = True
    return True


def get_dev_utility_pack_key():
    return DEV_UTILITY_PACK_KEY


def _require_runtime():
    if not _RUNTIME_BOUND:
        raise RuntimeError("Developer Utility Updater는 단독 실행할 수 없습니다. AnkiVoice.py에서 불러와야 합니다.")


def _safe_log(message):
    logger = globals().get("log_only")
    if callable(logger):
        try:
            logger(message)
        except Exception:
            pass


def _pack_path():
    return Path(globals()["BASE_DIR"]) / "module" / "dev_utility.dpack"


def _check_network():
    if requests is None:
        raise RuntimeError("requests 모듈을 사용할 수 없습니다.")

    try:
        socket.getaddrinfo("raw.githubusercontent.com", 443, type=socket.SOCK_STREAM)
    except Exception as e:
        raise RuntimeError(f"DNS 조회 실패: {type(e).__name__}") from e


def _download_to_temp_file():
    _check_network()

    headers = {
        "User-Agent": "AnkiVoice/DeveloperUtilityUpdater",
        "Accept": "text/plain,*/*",
    }

    response = requests.get(
        RAW_DEV_UTILITY_URL,
        headers=headers,
        timeout=(5, 20),
    )
    response.raise_for_status()

    content = response.content
    if not content:
        raise RuntimeError("다운로드된 파일이 비어 있습니다.")

    try:
        source_code = content.decode("utf-8")
    except UnicodeDecodeError as e:
        raise RuntimeError("다운로드된 파일을 UTF-8로 읽을 수 없습니다.") from e

    fd, temp_name = tempfile.mkstemp(prefix="ankivoice_dev_utility_raw_", suffix=".py")
    temp_path = Path(temp_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(source_code)
    except Exception:
        try:
            temp_path.unlink()
        except Exception:
            pass
        raise

    return temp_path


def _extract_app_version(source_code):
    tree = ast.parse(source_code)

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "APP_VERSION":
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return node.value.value

    return None


def _has_function(source_code, function_name):
    tree = ast.parse(source_code)

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return True

    return False


def _validate_source(source_code):
    expected_version = str(globals().get("APP_VERSION", "")).strip()
    downloaded_version = _extract_app_version(source_code)

    if not downloaded_version:
        raise RuntimeError("APP_VERSION을 찾지 못했습니다.")

    if downloaded_version != expected_version:
        raise RuntimeError(f"APP_VERSION 불일치: AnkiVoice={expected_version}, Dev Utility={downloaded_version}")

    compile(source_code, "Dev_Utility.py", "exec")

    if not _has_function(source_code, "bind_runtime"):
        raise RuntimeError("bind_runtime 함수를 찾지 못했습니다.")

    if not _has_function(source_code, "launch_developer_utility"):
        raise RuntimeError("launch_developer_utility 함수를 찾지 못했습니다.")

    return downloaded_version


def _encrypt_and_save(source_code):
    if Fernet is None:
        raise RuntimeError("cryptography.fernet 모듈을 사용할 수 없습니다.")

    encrypted = Fernet(DEV_UTILITY_PACK_KEY).encrypt(source_code.encode("utf-8"))
    pack_path = _pack_path()
    pack_path.parent.mkdir(parents=True, exist_ok=True)

    backup_path = pack_path.with_suffix(".dpack.bak")
    if pack_path.exists():
        backup_path.write_bytes(pack_path.read_bytes())

    fd, temp_name = tempfile.mkstemp(
        prefix="ankivoice_dev_utility_",
        suffix=".dpack.tmp",
        dir=str(pack_path.parent),
    )
    temp_path = Path(temp_name)

    try:
        with os.fdopen(fd, "wb") as f:
            f.write(encrypted)
        temp_path.replace(pack_path)
    except Exception:
        try:
            temp_path.unlink()
        except Exception:
            pass
        raise

    return pack_path, backup_path if backup_path.exists() else None


def update_dev_utility_from_github():
    _require_runtime()

    raw_temp_path = None

    ui_clear_screen()
    ui_title("Developer Utility 업데이트", "GitHub RAW에서 Dev Utility를 다운로드합니다.")
    ui_processing("네트워크 연결을 확인하는 중입니다.")

    try:
        raw_temp_path = _download_to_temp_file()
        source_code = raw_temp_path.read_text(encoding="utf-8")

        ui_processing("다운로드된 파일을 검사하는 중입니다.")
        downloaded_version = _validate_source(source_code)

        ui_processing("Dev Utility를 암호화하여 저장하는 중입니다.")
        started = time.perf_counter()
        pack_path, backup_path = _encrypt_and_save(source_code)
        elapsed = time.perf_counter() - started

        ui_clear_screen()
        ui_completed("Developer Utility 업데이트가 완료되었습니다.")
        ui_item("APP_VERSION", downloaded_version)
        ui_item("RAW 임시 파일", str(raw_temp_path))
        ui_item("저장 위치", str(pack_path))
        ui_item("백업", str(backup_path) if backup_path else "없음")
        ui_item("암호화 시간", f"{elapsed:.3f}s")
        ui_hint("프로그램을 다시 시작하거나 Developer Utility를 다시 실행하면 갱신된 모듈이 적용됩니다.")

    except Exception as e:
        _safe_log(f"Developer Utility update failed: {type(e).__name__}: {e}")
        ui_clear_screen()
        ui_error("Developer Utility 업데이트 실패")
        ui_item("이유", f"{type(e).__name__}: {e}")
        ui_hint("네트워크 연결, GitHub RAW URL, APP_VERSION, 암호화 키를 확인하세요.")

    finally:
        if raw_temp_path is not None:
            try:
                raw_temp_path.unlink()
            except Exception:
                pass

    wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")


__all__ = [
    "bind_runtime",
    "get_dev_utility_pack_key",
    "update_dev_utility_from_github",
]
