# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0

# AnkiVoice
# Developed by Lutte Laurent with assistance from ChatGPT.

# Copyright (c) 2026 Lutte Laurent

# Licensed under the PolyForm Noncommercial License 1.0.0.
# You may use, modify, and redistribute this software for non-commercial purposes in accordance with the LICENSE file.

# This license applies only to the original AnkiVoice source code.

# It does not apply to third-party content, service data, external resources,
# user-provided materials, third-party libraries, trademarks, logos, or other protected materials.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
# See the LICENSE file for the full license text.


import atexit
import csv
import html
import io
import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import quote, unquote

import requests
from tqdm import tqdm

try:
    import zstandard as zstd
except ImportError:
    zstd = None

# ============================================================
# 기본 경로 설정
# ============================================================

APP_VERSION = "1.5.0"
APP_RELEASE_NAME = "Release"
APP_PRODUCT_NAME = "AnkiVoice"
APP_BUILD_LABEL = f"{APP_PRODUCT_NAME} ({APP_RELEASE_NAME})"
APP_NAME = f"{APP_BUILD_LABEL} v{APP_VERSION}"
APP_SUBTITLE = "CSV Extractor / Plain Text / MP3 Collector / MP3 File Manager / ANV Audio Converter / Anki Analyzer / APKG Quiz"


def set_console_title(title):
    if os.name != "nt":
        return

    try:
        os.system(f"title {title}")
    except Exception:
        pass


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = get_base_dir()

VOCA_DIR = BASE_DIR / "voca"
APKG_DIR = BASE_DIR / "apkg"
CSV_DIR = BASE_DIR / "csv"
AUDIO_DIR = BASE_DIR / "audio"
ANALYSIS_DIR = BASE_DIR / "analysis"
SETTING_DIR = BASE_DIR / "setting"
LOG_FILE = SETTING_DIR / "anki_universal_tool_log.txt"
SETTINGS_FILE = SETTING_DIR / "anki_universal_tool_settings.json"
LEGACY_LOG_FILE = BASE_DIR / "anki_universal_tool_log.txt"
LEGACY_SETTINGS_FILE = BASE_DIR / "anki_universal_tool_settings.json"
DEV_UTILITY_PACK_PATH = BASE_DIR / "module" / "dev_utility.dpack"
LAMI_PACK_PATH = SETTING_DIR / "lami.lpack"
LEGACY_LAMI_PACK_PATH = SETTING_DIR / "lami.pack"

for directory in [VOCA_DIR, APKG_DIR, CSV_DIR, AUDIO_DIR, ANALYSIS_DIR, SETTING_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


def get_optional_package_paths():
    return [
        DEV_UTILITY_PACK_PATH,
        LAMI_PACK_PATH,
    ]


def has_extended_optional_packages():
    return any(path.exists() for path in get_optional_package_paths())


def refresh_app_identity():
    global APP_PRODUCT_NAME, APP_BUILD_LABEL, APP_NAME

    APP_PRODUCT_NAME = "AnkiVoice Extended" if has_extended_optional_packages() else "AnkiVoice"
    APP_BUILD_LABEL = f"{APP_PRODUCT_NAME} ({APP_RELEASE_NAME})"
    APP_NAME = f"{APP_BUILD_LABEL} v{APP_VERSION}"
    set_console_title(APP_NAME)
    return APP_NAME


refresh_app_identity()



def migrate_legacy_setting_files():
    # 구버전 설정/로그 파일을 setting 폴더로 이전
    pairs = [
        (LEGACY_SETTINGS_FILE, SETTINGS_FILE, "settings"),
        (LEGACY_LOG_FILE, LOG_FILE, "log"),
    ]

    for old_path, new_path, kind in pairs:
        try:
            if not old_path.exists() or old_path.resolve() == new_path.resolve():
                continue

            new_path.parent.mkdir(parents=True, exist_ok=True)

            if not new_path.exists():
                shutil.move(str(old_path), str(new_path))
                continue

            if kind == "settings":
                try:
                    old_data = json.loads(old_path.read_text(encoding="utf-8"))
                    new_data = json.loads(new_path.read_text(encoding="utf-8"))

                    if isinstance(old_data, dict) and isinstance(new_data, dict):
                        merged = dict(new_data)

                        old_voice = old_data.get("voice_defaults", {})
                        new_voice = merged.get("voice_defaults", {})

                        if isinstance(old_voice, dict) and isinstance(new_voice, dict):
                            new_voice.update(old_voice)
                            merged["voice_defaults"] = new_voice

                        for key, value in old_data.items():
                            if key not in merged:
                                merged[key] = value

                        new_path.write_text(
                            json.dumps(merged, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                except Exception:
                    pass

            elif kind == "log":
                old_text = old_path.read_text(encoding="utf-8", errors="replace")
                if old_text.strip():
                    with new_path.open("a", encoding="utf-8") as f:
                        f.write("\n")
                        f.write("# ---- migrated legacy log ----\n")
                        f.write(old_text)
                        if not old_text.endswith("\n"):
                            f.write("\n")

            old_path.unlink()

        except Exception:
            # 이전 실패는 무시
            pass


migrate_legacy_setting_files()


HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/html,*/*",
}


ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


def is_zstd_payload(data):
    return bytes(data or b"").startswith(ZSTD_MAGIC)


def decompress_zstd_bytes(data):
    data = bytes(data or b"")

    if zstd is not None:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(io.BytesIO(data)) as reader:
            return reader.read()

    zstd_exe = shutil.which("zstd")

    if zstd_exe:
        proc = subprocess.run(
            [zstd_exe, "-q", "-d", "-c"],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return proc.stdout

    raise RuntimeError("zstandard가 필요합니다. 명령어: pip install zstandard")


def compress_zstd_bytes(data):
    data = bytes(data or b"")

    if zstd is not None:
        cctx = zstd.ZstdCompressor()
        return cctx.compress(data)

    zstd_exe = shutil.which("zstd")

    if zstd_exe:
        proc = subprocess.run(
            [zstd_exe, "-q", "-z", "-c"],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return proc.stdout

    raise RuntimeError("zstandard가 필요합니다. 명령어: pip install zstandard")


def decompress_zstd_member_to_file(zip_file, member_name, out_path):
    raw = zip_file.read(member_name)
    out_path.write_bytes(decompress_zstd_bytes(raw))
    return out_path


START_LINES = [
    APP_NAME,
    "TXT, APKG, CSV 파일에서 학습 자료를 추출하고 정리합니다.",
    "필요 폴더를 확인했습니다.",
]


SEARCH_LINES = [
    "검색 중: {word}",
    "음성 확인 중: {word}",
    "사전 항목 확인 중: {word}",
]

SAVE_LINES = [
    "저장 완료: {word} → {filename}",
    "음성 파일 저장: {word} → {filename}",
]

FAIL_ENTRY_LINES = [
    "사전 항목을 찾지 못했습니다: {word}",
    "사전 항목을 찾지 못했습니다: {word}",
]

FAIL_MP3_LINES = [
    "음성 파일을 찾지 못했습니다: {word}",
    "음성 파일을 찾지 못했습니다: {word}",
]

ERROR_LINES = [
    "처리 실패: {word} / 이유: {error}",
    "오류 발생: {word} / 이유: {error}",
]


# 메뉴 제어용 예외
class ReturnToMenu(Exception):
    pass


class BackScreen(Exception):
    pass


class ExitProgram(Exception):
    pass


# UI module is loaded below.

from cryptography.fernet import Fernet, InvalidToken

LCD_EASTER_EGG_COMMAND = "/connect --lcd scr obv_7 clone_laurent"

LAMI_KEY = b"pU-0_E-7tYlgmw2Bmylyu2GlD5njemWxy_ZwpfdRxBc="


def run_lami_easter_egg():
    if not LAMI_PACK_PATH.exists():
        ui_clear_screen()
        ui_error("PXE SERVICE IMAGE NOT FOUND")
        ui_hint("BOOT DEVICE 07 FAILED TO RESPOND.")
        ui_hint("VERIFY THAT THE AUXILIARY SERVICE IMAGE PACKAGE IS PRESENT.")
        ui_hint("STATUS: NO VALID ENCRYPTED SERVICE IMAGE RECEIVED")
        wait_back_to_previous("PRESS ENTER TO RETURN TO FIRMWARE MENU...")
        return False

    temp_dir = None

    try:
        import importlib.util

        encrypted_data = LAMI_PACK_PATH.read_bytes()

        try:
            decrypted_zip = Fernet(LAMI_KEY).decrypt(encrypted_data)
        except InvalidToken:
            ui_clear_screen()
            ui_error("PXE SERVICE IMAGE AUTHENTICATION FAILED")
            ui_hint("ENCRYPTED SERVICE IMAGE COULD NOT BE VERIFIED.")
            ui_hint("STATUS: PACKAGE SIGNATURE OR DECRYPTION KEY MISMATCH")
            wait_back_to_previous("PRESS ENTER TO RETURN TO FIRMWARE MENU...")
            return False

        temp_dir = Path(tempfile.mkdtemp(prefix="ankivoice_lami_"))

        def cleanup_lami_runtime():
            shutil.rmtree(temp_dir, ignore_errors=True)

        atexit.register(cleanup_lami_runtime)

        with zipfile.ZipFile(io.BytesIO(decrypted_zip), "r") as zf:
            zf.extractall(temp_dir)

        lami_module_path = temp_dir / "lami.py"

        if not lami_module_path.exists():
            raise RuntimeError("NO BOOTABLE SERVICE ENTRY POINT FOUND.")

        os.environ["ANKIVOICE_LAMI_RUNTIME_DIR"] = str(temp_dir)

        spec = importlib.util.spec_from_file_location(
            "ankivoice_lami_module",
            lami_module_path,
        )

        if spec is None or spec.loader is None:
            raise RuntimeError("SERVICE IMAGE HEADER IS INVALID.")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, "run_from_ankivoice"):
            module.run_from_ankivoice(base_dir=BASE_DIR)
            return True

        if hasattr(module, "show_easter_egg_clone"):
            module.show_easter_egg_clone(base_dir=BASE_DIR, launched_from_ankivoice=True)
            return True

        raise RuntimeError("NO BOOTABLE SERVICE ENTRY POINT FOUND.")

    except SystemExit:
        raise

    except Exception as e:
        log_only("[PXE SERVICE BOOT ERROR]")
        log_only(traceback.format_exc())
        ui_clear_screen()
        ui_error("AUXILIARY SERVICE BOOT ABORTED")
        ui_hint("FIRMWARE HANDOFF FAILED.")
        ui_hint(f"STATUS: {e}")
        wait_back_to_previous("PRESS ENTER TO RETURN TO FIRMWARE MENU.")
        return False

    finally:
        try:
            setup_console_window()
            if "apply_screen_mode" in globals():
                apply_screen_mode()
            ui_clear_screen()
        except Exception:
            pass


def show_easter_egg_ping():
    ui_clear_screen()
    ui_title("pong!", "AnkiVoice diagnostic echo")
    ui_write("  ping received.")
    ui_write("  pong!")
    wait_back_to_previous("이전 화면으로 돌아가려면 Enter를 눌러주세요...")


def handle_easter_egg_command(answer_raw):
    command = re.sub(r"\s+", " ", str(answer_raw or "").strip().lower())

    if command == "ping":
        show_easter_egg_ping()
        return True

    if command == LCD_EASTER_EGG_COMMAND:
        run_lami_easter_egg()
        return True

    return False






def fatal_core_module_error(module_path, detail=None):
    print()
    print("FATAL ERROR")
    print("A required core module is missing or unavailable.")
    print("Please reinstall AnkiVoice.")
    print()
    print(f"Missing module: {module_path}")
    if detail:
        print(f"Detail: {detail}")
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass
    raise SystemExit(1)

# UI 모듈 로드
def load_ui_module():
    import importlib.util

    module_path = BASE_DIR / "module" / "ui.py"

    if not module_path.exists():
        fatal_core_module_error(module_path)

    spec = importlib.util.spec_from_file_location("ankivoice_ui", module_path)

    if spec is None or spec.loader is None:
        fatal_core_module_error(module_path, "invalid module specification")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        fatal_core_module_error(module_path, str(e))

    if not hasattr(module, "bind_runtime"):
        fatal_core_module_error(module_path, "bind_runtime is missing")

    module.bind_runtime(sys.modules[__name__])
    return module


UI_MODULE = load_ui_module()

for _ui_export_name in getattr(UI_MODULE, "__all__", []):
    globals()[_ui_export_name] = getattr(UI_MODULE, _ui_export_name)

try:
    del _ui_export_name
except NameError:
    pass


# Optional MP3 Collector compatibility
CORE_DEFAULT_SETTINGS = {
    "voice_defaults": {
        "en": "us",
        "ja": "default",
        "ru": "default",
        "fr": "default",
        "de": "default",
        "es": "default",
        "zh": "expert",
    },
    "french": {
        "save_conjugations": False,
    },
    "ui": {
        "screen_mode": "white",
    },
    "anki": {
        "collection_media_dir": "",
        "collection_media_dirs": [],
    },
    "russian": {
        "stress_policy": "match_only",
    },
    "anv": {
        "first_used_date": "",
        "daily_seed": "",
        "daily_date": "",
        "daily_message": "",
    },
}

MP3_COLLECTOR = None
MP3_COLLECTOR_LOAD_ERROR = ""


def merge_dict_recursive(base, updates):
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge_dict_recursive(base[key], value)
        else:
            base[key] = value
    return base


def load_settings():
    settings = json.loads(json.dumps(CORE_DEFAULT_SETTINGS))

    if not SETTINGS_FILE.exists():
        return settings

    try:
        with SETTINGS_FILE.open("r", encoding="utf-8") as f:
            user_settings = json.load(f)
    except Exception as e:
        try:
            log_only(f"설정 파일 읽기 실패: {e}")
        except Exception:
            pass
        return settings

    if isinstance(user_settings, dict):
        merge_dict_recursive(settings, user_settings)

    return settings


def save_settings(settings):
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with SETTINGS_FILE.open("w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        try:
            ui_error(f"설정 저장에 실패했습니다: {e}")
        except Exception:
            pass
        try:
            log_only(f"설정 저장 실패: {e}")
        except Exception:
            pass
        return False


def is_mp3_collector_available():
    return MP3_COLLECTOR is not None


def get_mp3_collector_module_path():
    return BASE_DIR / "module" / "mp3_collector.py"


def get_mp3_collector_status_label():
    if is_mp3_collector_available():
        return "사용 가능"

    module_path = get_mp3_collector_module_path()

    if not module_path.exists():
        return "미설치"

    return "로드 실패"


def get_feature_profile_label():
    return "mp3" if is_mp3_collector_available() else "core"


def get_feature_profile_name():
    return "MP3 Module Build" if is_mp3_collector_available() else "Core Build"


def get_main_subtitle():
    if is_mp3_collector_available():
        return "Extract / Plain Text + MP3 / File Manager / Analyzer / Quiz"
    return "Extract / Plain Text / File Manager / Analyzer / Quiz"


def get_output_location_summary():
    if is_mp3_collector_available():
        return "결과 저장: csv / audio/{language} / collection.media / apkg / analysis"
    return "결과 저장: csv / audio / collection.media / apkg / analysis"


def show_mp3_collector_unavailable():
    ui_clear_screen()
    ui_title("MP3 Collector", "이 설치에서는 지원하지 않는 기능입니다.")
    ui_error("MP3 Collector 기능을 사용할 수 없습니다.")
    ui_hint("module/mp3_collector.py 파일이 없거나 정상적으로 로드되지 않았습니다.")
    ui_hint("Anki Extractor, Plain Text, APKG Audio, 어려운 단어 분석, 설정 화면은 계속 사용할 수 있습니다.")

    ui_section("상태")
    ui_item("필요 파일", str(get_mp3_collector_module_path()))
    ui_item("현재 상태", get_mp3_collector_status_label())

    if MP3_COLLECTOR_LOAD_ERROR:
        for line in _wrap_display(MP3_COLLECTOR_LOAD_ERROR, _terminal_width() - 10):
            ui_write("      " + line)

    wait_back_to_previous("메인 메뉴로 돌아가려면 Enter를 눌러주세요...")


def require_mp3_collector_or_show_message():
    if is_mp3_collector_available():
        return True

    show_mp3_collector_unavailable()
    return False


def get_screen_mode():
    settings = load_settings()
    mode = str(settings.get("ui", {}).get("screen_mode", "white")).strip().lower()
    return "dark" if mode in {"dark", "black", "d", "다크", "다크모드"} else "white"


def get_screen_mode_label(mode=None):
    mode = get_screen_mode() if mode is None else str(mode or "white").strip().lower()
    return "다크 모드" if mode == "dark" else "화이트 모드"


def set_screen_mode(mode):
    mode = "dark" if str(mode or "").strip().lower() in {"dark", "black", "d", "다크", "다크모드"} else "white"
    settings = load_settings()
    settings.setdefault("ui", {})["screen_mode"] = mode
    return save_settings(settings)


def apply_screen_mode():
    try:
        if os.name == "nt":
            os.system("color 0F" if get_screen_mode() == "dark" else "color F0")
    except Exception:
        pass


def configure_screen_mode():
    while True:
        ui_clear_screen()
        ui_title("화면 모드", "AnkiVoice 화면 색상을 설정합니다.")
        ui_section("현재 설정")
        ui_item("상태", get_screen_mode_label())

        ui_section("선택")
        ui_item("1)", "화이트 모드", "흰 배경과 검은 글자로 표시합니다.")
        ui_item("2)", "다크 모드", "검은 배경과 밝은 글자로 표시합니다.")
        ui_item("B)", "이전 화면")
        ui_item("M)", "메인 메뉴")
        ui_item("S)", "종료")

        answer = normalize_menu_answer(ui_prompt("화면 모드").strip())

        if answer in {"1", "W", "WHITE", "LIGHT", "화이트", "화이트모드"}:
            set_screen_mode("white")
            apply_screen_mode()
            ui_clear_screen()
            ui_completed("화이트 모드로 변경했습니다.")
            wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")
            return

        if answer in {"2", "D", "DARK", "BLACK", "다크", "다크모드"}:
            set_screen_mode("dark")
            apply_screen_mode()
            ui_clear_screen()
            ui_completed("다크 모드로 변경했습니다.")
            wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")
            return

        if answer == "B":
            raise BackScreen

        if answer == "M":
            raise ReturnToMenu

        if answer == "S":
            raise ExitProgram

        say("1, 2, B, M, S 중에서 입력해주세요.")


def get_language_audio_dir(language_mode):
    folder_name = str(language_mode or "misc").strip().lower() or "misc"
    audio_dir = AUDIO_DIR / folder_name
    audio_dir.mkdir(parents=True, exist_ok=True)
    return audio_dir


def get_french_conjugation_setting_label():
    return "지원하지 않음" if not is_mp3_collector_available() else "N / 저장 안 함"


def configure_default_voice_settings():
    show_mp3_collector_unavailable()


def configure_french_conjugation_setting():
    show_mp3_collector_unavailable()


def show_error_code_reference(clear=True):
    if clear:
        ui_clear_screen()

    ui_title("오류 코드표", "MP3 Collector 모듈이 설치되어 있지 않습니다.")
    ui_hint("MP3 수집 오류 코드표는 module/mp3_collector.py가 있을 때 표시됩니다.")
    wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")


# Menu module is loaded below.


# Extractor 모듈 로드
def load_extractor_module():
    import importlib.util

    module_path = BASE_DIR / "module" / "extractor.py"

    if not module_path.exists():
        fatal_core_module_error(module_path)

    spec = importlib.util.spec_from_file_location("ankivoice_extractor", module_path)

    if spec is None or spec.loader is None:
        fatal_core_module_error(module_path, "invalid module specification")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        fatal_core_module_error(module_path, str(e))

    if not hasattr(module, "bind_runtime"):
        fatal_core_module_error(module_path, "bind_runtime is missing")

    module.bind_runtime(sys.modules[__name__])
    return module


EXTRACTOR_MODULE = load_extractor_module()

for _extractor_export_name in getattr(EXTRACTOR_MODULE, "__all__", []):
    globals()[_extractor_export_name] = getattr(EXTRACTOR_MODULE, _extractor_export_name)

try:
    del _extractor_export_name
except NameError:
    pass

# Extractor가 가져온 함수까지 UI 모듈에 다시 바인딩
UI_MODULE.bind_runtime(sys.modules[__name__])


# Pronunciation / MP3 Collector 모듈 로드
def load_mp3_collector_module():
    import importlib.util

    global MP3_COLLECTOR_LOAD_ERROR

    module_path = get_mp3_collector_module_path()

    if not module_path.exists():
        MP3_COLLECTOR_LOAD_ERROR = f"missing optional module: {module_path}"
        try:
            log_only(MP3_COLLECTOR_LOAD_ERROR)
        except Exception:
            pass
        return None

    try:
        spec = importlib.util.spec_from_file_location("ankivoice_mp3_collector", module_path)

        if spec is None or spec.loader is None:
            MP3_COLLECTOR_LOAD_ERROR = "invalid module specification"
            try:
                log_only(f"MP3 Collector load failed: {MP3_COLLECTOR_LOAD_ERROR}")
            except Exception:
                pass
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "bind_runtime"):
            MP3_COLLECTOR_LOAD_ERROR = "bind_runtime is missing"
            try:
                log_only(f"MP3 Collector load failed: {MP3_COLLECTOR_LOAD_ERROR}")
            except Exception:
                pass
            return None

        module.bind_runtime(sys.modules[__name__])
        MP3_COLLECTOR_LOAD_ERROR = ""
        return module

    except Exception as e:
        MP3_COLLECTOR_LOAD_ERROR = str(e)
        try:
            log_only(f"MP3 Collector load failed: {e}")
            log_only(traceback.format_exc())
        except Exception:
            pass
        return None


MP3_COLLECTOR = load_mp3_collector_module()

if MP3_COLLECTOR is not None:
    for _mp3_export_name in getattr(MP3_COLLECTOR, "__all__", []):
        globals()[_mp3_export_name] = getattr(MP3_COLLECTOR, _mp3_export_name)

    try:
        del _mp3_export_name
    except NameError:
        pass

    UI_MODULE.bind_runtime(sys.modules[__name__])



# Text Policy 모듈 로드
def load_text_policy_module():
    import importlib.util

    module_path = BASE_DIR / "module" / "text_policy.py"

    if not module_path.exists():
        fatal_core_module_error(module_path)

    spec = importlib.util.spec_from_file_location("ankivoice_text_policy", module_path)

    if spec is None or spec.loader is None:
        fatal_core_module_error(module_path, "invalid module specification")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        fatal_core_module_error(module_path, str(e))

    if not hasattr(module, "bind_runtime"):
        fatal_core_module_error(module_path, "bind_runtime is missing")

    module.bind_runtime(sys.modules[__name__])
    return module


TEXT_POLICY_MODULE = load_text_policy_module()

for _text_policy_export_name in getattr(TEXT_POLICY_MODULE, "__all__", []):
    globals()[_text_policy_export_name] = getattr(TEXT_POLICY_MODULE, _text_policy_export_name)

try:
    del _text_policy_export_name
except NameError:
    pass

# 새 전역 함수를 참조할 수 있게 다시 바인딩
EXTRACTOR_MODULE.bind_runtime(sys.modules[__name__])
if MP3_COLLECTOR is not None:
    MP3_COLLECTOR.bind_runtime(sys.modules[__name__])
UI_MODULE.bind_runtime(sys.modules[__name__])


# 연속 실행
def run_txt_all_in_one():
    say()
    say("Anki TXT Extract → CSV → MP3 한 번에 진행합니다.")

    word_csv_path = convert_txt_to_csv()

    if word_csv_path is None:
        say("CSV 변환이 완료되지 않아 MP3 수집은 진행하지 않습니다.")
        return

    say()
    ui_clear_screen()
    ui_title("MP3 수집으로 이동", "방금 만든 CSV를 사용해 바로 음성을 수집합니다.")
    ui_item("연결할 CSV", word_csv_path.name)
    ui_hint("이제 MP3 수집 화면으로 이동합니다.")
    ask_action("생성된 CSV로 MP3 수집을 계속 진행할까요?")

    if not require_mp3_collector_or_show_message():
        return

    collect_tts_from_csv(word_csv_path)


def run_apkg_all_in_one():
    say()
    say("APKG → CSV → MP3 한 번에 진행합니다.")

    word_csv_path = convert_apkg_to_csv(save_full=True, save_word=True)

    if word_csv_path is None:
        say("CSV 변환이 완료되지 않아 MP3 수집은 진행하지 않습니다.")
        return

    say()
    ui_clear_screen()
    ui_title("MP3 수집으로 이동", "방금 만든 CSV를 사용해 바로 음성을 수집합니다.")
    ui_item("연결할 CSV", word_csv_path.name)
    ui_hint("이제 MP3 수집 화면으로 이동합니다.")
    ask_action("생성된 CSV로 MP3 수집을 계속 진행할까요?")

    if not require_mp3_collector_or_show_message():
        return

    collect_tts_from_csv(word_csv_path)


# 메인 루프
TERMS_OF_SERVICE_VERSION = f"{APP_VERSION}-legal-notice-pending"


def load_notice_text_module():
    import importlib.util

    module_path = BASE_DIR / "module" / "notice_texts.py"

    if not module_path.exists():
        fatal_core_module_error(module_path)

    spec = importlib.util.spec_from_file_location("ankivoice_notice_texts", module_path)

    if spec is None or spec.loader is None:
        fatal_core_module_error(module_path, "invalid module specification")

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        fatal_core_module_error(module_path, str(e))

    required_names = [
        "LEGAL_NOTICE_LANGUAGE_ORDER",
        "LEGAL_NOTICE_LANGUAGE_LABELS",
        "LEGAL_NOTICE_ACCEPT_TEXTS",
        "LEGAL_NOTICE_TEXTS",
        "PATCH_NOTE_TEXTS",
        "CREATOR_NOTE_TEXTS",
    ]

    for name in required_names:
        if not hasattr(module, name):
            fatal_core_module_error(module_path, f"{name} is missing")

    return module


NOTICE_TEXT_MODULE = load_notice_text_module()

for _notice_export_name in getattr(NOTICE_TEXT_MODULE, "__all__", []):
    globals()[_notice_export_name] = getattr(NOTICE_TEXT_MODULE, _notice_export_name)

try:
    del _notice_export_name
except NameError:
    pass

try:
    LEGAL_NOTICE_VARIANT = NOTICE_TEXT_MODULE.get_legal_notice_variant()
    TERMS_OF_SERVICE_VERSION = NOTICE_TEXT_MODULE.get_legal_notice_version()
    LEGAL_NOTICE_TEXTS = NOTICE_TEXT_MODULE.get_legal_notice_texts()
except Exception:
    LEGAL_NOTICE_VARIANT = get_feature_profile_label()
    TERMS_OF_SERVICE_VERSION = f"{APP_VERSION}-ko-en-formal-paged-{LEGAL_NOTICE_VARIANT}"

LEGAL_NOTICE_PAGE_SIZE = 14
LEGAL_NOTICE_PAGE_BREAK = "__PAGE_BREAK__"
LEGAL_NOTICE_REQUIRED_PAGE_SECONDS = 0.0


# Notice Viewer 모듈 로드
def load_notice_viewer_module():
    import importlib.util

    module_path = BASE_DIR / "module" / "notice_viewer.py"

    if not module_path.exists():
        fatal_core_module_error(module_path)

    spec = importlib.util.spec_from_file_location("ankivoice_notice_viewer", module_path)

    if spec is None or spec.loader is None:
        fatal_core_module_error(module_path, "invalid module specification")

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        fatal_core_module_error(module_path, str(e))

    if not hasattr(module, "bind_runtime"):
        fatal_core_module_error(module_path, "bind_runtime is missing")

    module.bind_runtime(sys.modules[__name__])
    return module


NOTICE_VIEWER_MODULE = load_notice_viewer_module()

for _notice_viewer_export_name in getattr(NOTICE_VIEWER_MODULE, "__all__", []):
    globals()[_notice_viewer_export_name] = getattr(NOTICE_VIEWER_MODULE, _notice_viewer_export_name)

try:
    del _notice_viewer_export_name
except NameError:
    pass


def show_about_info():
    ui_clear_screen()
    ui_title(f"About {APP_BUILD_LABEL}", "Version information and project credits")

    ui_section("Product")
    ui_kv("Name", APP_BUILD_LABEL)
    ui_kv("Version", APP_VERSION)
    ui_kv("Release", APP_RELEASE_NAME)
    ui_kv("Build Profile", get_feature_profile_name())
    ui_kv("Legal Notice", f"{TERMS_OF_SERVICE_VERSION} / {LEGAL_NOTICE_VARIANT}")
    ui_kv("Runtime", f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    ui_kv("Base Dir", BASE_DIR)

    ui_section("Description")
    description_lines = [
        f"{APP_PRODUCT_NAME} is an unofficial study utility for Anki users.",
        "It helps convert Anki decks, exported text files, CSV vocabulary lists, and plain text word lists into reusable study formats.",
    ]

    if is_mp3_collector_available():
        description_lines.append(
            "This build also includes separately installed MP3 collection functionality for personal language-learning workflows."
        )
    else:
        description_lines.append(
            "This public/core build does not include MP3 collection modules."
        )

    description_lines.append(
        "This software is intended only for personal language-learning and educational purposes."
    )

    for line in description_lines:
        for wrapped in _wrap_display(line, _terminal_width() - 8):
            ui_write("    " + wrapped)

    ui_section("Developer")
    ui_kv("Developer", "Lutte Laurent")
    ui_kv("License", "PolyForm Noncommercial License 1.0.0")
    ui_kv("Status", "Unofficial software")

    ui_section("Third-Party Notice")
    notice_lines = [
        f"{APP_PRODUCT_NAME} is not affiliated with, endorsed by, sponsored by, authorized by, or officially connected to Anki, AnkiWeb, or any other third-party service provider.",
        "Third-party content, service data, media assets, metadata, trademarks, user-provided materials, and external libraries are not included in this software license.",
        "Using this software does not grant ownership, redistribution, publication, sublicensing, or commercial usage rights over third-party materials.",
        "The software is provided AS IS and AS AVAILABLE, without warranty of any kind.",
    ]
    for line in notice_lines:
        for wrapped in _wrap_display(line, _terminal_width() - 8):
            ui_write("    " + wrapped)

    ui_section("Special Thanks")
    ui_kv("Clone Laurent", "Special QA / Observation Contributor")
    thanks_lines = [
        "For repeated QA checks, strange failure reproduction, menu-flow inspection, and the discovery of bugs that should not have existed under ordinary conditions.",
    ]
    for line in thanks_lines:
        for wrapped in _wrap_display(line, _terminal_width() - 8):
            ui_write("    " + wrapped)

    ui_section("AI Assistance")
    ai_lines = [
        "ChatGPT was used as an auxiliary tool during code drafting, refactoring, debugging, documentation preparation, and wording cleanup.",
        "AI-generated output was reviewed and revised by the human developer before inclusion in the project.",
        "ChatGPT and OpenAI are not the author, maintainer, sponsor, official distributor, legal representative, or third-party service provider of this project.",
        "",
    ]
    for line in ai_lines:
        for wrapped in _wrap_display(line, _terminal_width() - 8):
            ui_write("    " + wrapped)

    wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")

def show_folder_info():
    ui_card(
        "작업 폴더",
        [
            "입력 파일은 voca / apkg / csv 폴더에 넣습니다.",
            "생성된 CSV는 csv 폴더에 저장되며, APKG 결과물은 apkg 폴더에 저장됩니다.",
            "오디오 작업 자료는 audio 폴더에서 관리합니다.",
            "설정 파일과 로그는 루트가 아니라 setting 폴더에만 저장됩니다.",
            "APKG 난이도 분석 결과는 analysis 폴더에 저장됩니다.",
        ],
    )
    ui_kv("voca", VOCA_DIR)
    ui_kv("apkg", APKG_DIR)
    ui_kv("csv", CSV_DIR)
    ui_kv("audio", AUDIO_DIR)
    ui_kv("analysis", ANALYSIS_DIR, "어려운 단어 추출 결과 저장")
    ui_kv("setting", SETTING_DIR, "설정 파일과 로그 파일 저장")
    ui_kv("audio/en", get_language_audio_dir("en"))
    ui_kv("audio/ja", get_language_audio_dir("ja"))
    ui_kv("audio/zh", get_language_audio_dir("zh"))
    ui_kv("log", LOG_FILE)
    ui_kv("settings", SETTINGS_FILE)




# Cleanup Manager 모듈 로드
def load_cleanup_manager_module():

    import importlib.util

    module_path = BASE_DIR / "module" / "cleanup_manager.py"

    if not module_path.exists():
        fatal_core_module_error(module_path)

    spec = importlib.util.spec_from_file_location("ankivoice_cleanup_manager", module_path)

    if spec is None or spec.loader is None:
        fatal_core_module_error(module_path, "invalid module specification")

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        fatal_core_module_error(module_path, str(e))

    if not hasattr(module, "bind_runtime"):
        fatal_core_module_error(module_path, "bind_runtime is missing")

    module.bind_runtime(sys.modules[__name__])
    return module


CLEANUP_MANAGER_MODULE = load_cleanup_manager_module()

for _cleanup_export_name in getattr(CLEANUP_MANAGER_MODULE, "__all__", []):
    globals()[_cleanup_export_name] = getattr(CLEANUP_MANAGER_MODULE, _cleanup_export_name)

try:
    del _cleanup_export_name
except NameError:
    pass




def show_unexpected_error_and_return_to_menu(error):
    # 예기치 못한 오류는 로그를 남기고 메인 메뉴로 복귀
    error_type = type(error).__name__
    error_text = str(error) or "unknown error"

    log_only("[ERROR] 예상하지 못한 오류가 발생했습니다.")
    log_only(f"[ERROR] type={error_type} / reason={error_text}")
    log_only(traceback.format_exc())

    ui_clear_screen()
    ui_error("오류가 발생했습니다. 메인 메뉴로 돌아갑니다.")
    ui_section("오류 상세")
    ui_item("오류 종류", error_type)
    ui_item("이유", error_text)
    ui_item("로그", str(LOG_FILE))
    wait_back_to_previous("메인 메뉴로 돌아가려면 Enter를 눌러주세요...")



# APKG Audio Compiler 모듈 로드
def load_apkg_audio_compiler_module():
    import importlib.util

    module_path = BASE_DIR / "module" / "apkg_audio_compiler.py"

    if not module_path.exists():
        fatal_core_module_error(module_path)

    spec = importlib.util.spec_from_file_location("ankivoice_apkg_audio_compiler", module_path)

    if spec is None or spec.loader is None:
        fatal_core_module_error(module_path, "invalid module specification")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        fatal_core_module_error(module_path, str(e))

    if not hasattr(module, "bind_runtime"):
        fatal_core_module_error(module_path, "bind_runtime is missing")

    module.bind_runtime(sys.modules[__name__])
    return module


APKG_AUDIO_COMPILER = load_apkg_audio_compiler_module()
inject_audio_into_apkg = APKG_AUDIO_COMPILER.inject_audio_into_apkg
get_saved_collection_media_dir_label = APKG_AUDIO_COMPILER.get_saved_collection_media_dir_label
configure_collection_media_dir = APKG_AUDIO_COMPILER.configure_collection_media_dir


# Audio File Manager 모듈 로드

def load_audio_file_manager_module():
    import importlib.util

    module_path = BASE_DIR / "module" / "audio_file_manager.py"

    if not module_path.exists():
        fatal_core_module_error(module_path)

    spec = importlib.util.spec_from_file_location("ankivoice_audio_file_manager", module_path)

    if spec is None or spec.loader is None:
        fatal_core_module_error(module_path, "invalid module specification")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        fatal_core_module_error(module_path, str(e))

    if not hasattr(module, "bind_runtime"):
        fatal_core_module_error(module_path, "bind_runtime is missing")

    module.bind_runtime(sys.modules[__name__])
    return module


AUDIO_FILE_MANAGER_MODULE = load_audio_file_manager_module()

for _audio_file_manager_export_name in getattr(AUDIO_FILE_MANAGER_MODULE, "__all__", []):
    globals()[_audio_file_manager_export_name] = getattr(AUDIO_FILE_MANAGER_MODULE, _audio_file_manager_export_name)

try:
    del _audio_file_manager_export_name
except NameError:
    pass


# ANV Audio Converter 모듈 로드


def load_anv_audio_converter_module():
    import importlib.util

    module_path = BASE_DIR / "module" / "anv_audio_converter.py"

    if not module_path.exists():
        fatal_core_module_error(module_path)

    spec = importlib.util.spec_from_file_location("ankivoice_anv_audio_converter", module_path)

    if spec is None or spec.loader is None:
        fatal_core_module_error(module_path, "invalid module specification")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        fatal_core_module_error(module_path, str(e))

    if not hasattr(module, "bind_runtime"):
        fatal_core_module_error(module_path, "bind_runtime is missing")

    module.bind_runtime(sys.modules[__name__])
    return module


ANV_AUDIO_CONVERTER_MODULE = load_anv_audio_converter_module()

for _anv_audio_converter_export_name in getattr(ANV_AUDIO_CONVERTER_MODULE, "__all__", []):
    globals()[_anv_audio_converter_export_name] = getattr(ANV_AUDIO_CONVERTER_MODULE, _anv_audio_converter_export_name)

try:
    del _anv_audio_converter_export_name
except NameError:
    pass

# APKG Difficulty Analyzer 모듈 로드

def load_apkg_difficulty_analyzer_module():
    import importlib.util

    module_path = BASE_DIR / "module" / "apkg_difficulty_analyzer.py"

    if not module_path.exists():
        fatal_core_module_error(module_path)

    spec = importlib.util.spec_from_file_location("ankivoice_apkg_difficulty_analyzer", module_path)

    if spec is None or spec.loader is None:
        fatal_core_module_error(module_path, "invalid module specification")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        fatal_core_module_error(module_path, str(e))

    if not hasattr(module, "bind_runtime"):
        fatal_core_module_error(module_path, "bind_runtime is missing")

    module.bind_runtime(sys.modules[__name__])
    return module


APKG_DIFFICULTY_ANALYZER = load_apkg_difficulty_analyzer_module()
analyze_apkg_difficulty = APKG_DIFFICULTY_ANALYZER.analyze_apkg_difficulty
analyze_apkg_difficulty_apkg = APKG_DIFFICULTY_ANALYZER.analyze_apkg_difficulty_apkg
analyze_apkg_difficulty_txt = APKG_DIFFICULTY_ANALYZER.analyze_apkg_difficulty_txt
analyze_apkg_difficulty_csv = APKG_DIFFICULTY_ANALYZER.analyze_apkg_difficulty_csv
analyze_apkg_difficulty_plain = APKG_DIFFICULTY_ANALYZER.analyze_apkg_difficulty_plain
analyze_apkg_difficulty_theory = APKG_DIFFICULTY_ANALYZER.analyze_apkg_difficulty_theory



# APKG Word Quiz 모듈 로드
def load_apkg_quiz_module():
    import importlib.util

    module_path = BASE_DIR / "module" / "apkg_quiz.py"

    if not module_path.exists():
        fatal_core_module_error(module_path)

    spec = importlib.util.spec_from_file_location("ankivoice_apkg_quiz", module_path)

    if spec is None or spec.loader is None:
        fatal_core_module_error(module_path, "invalid module specification")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        fatal_core_module_error(module_path, str(e))

    if not hasattr(module, "bind_runtime"):
        fatal_core_module_error(module_path, "bind_runtime is missing")

    module.bind_runtime(sys.modules[__name__])
    return module


APKG_QUIZ_MODULE = load_apkg_quiz_module()
run_apkg_quiz = APKG_QUIZ_MODULE.run_apkg_quiz


# ANV Daily 모듈 로드
def load_anv_daily_module():
    import importlib.util

    module_path = BASE_DIR / "module" / "anv_daily.py"

    if not module_path.exists():
        fatal_core_module_error(module_path)

    spec = importlib.util.spec_from_file_location("ankivoice_anv_daily", module_path)

    if spec is None or spec.loader is None:
        fatal_core_module_error(module_path, "invalid module specification")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        fatal_core_module_error(module_path, str(e))

    if not hasattr(module, "bind_runtime"):
        fatal_core_module_error(module_path, "bind_runtime is missing")

    module.bind_runtime(sys.modules[__name__])
    return module


ANV_DAILY_MODULE = load_anv_daily_module()
get_anv_daily_status = ANV_DAILY_MODULE.get_anv_daily_status


def run_apkg_tools_menu():
    while True:
        ui_clear_screen()
        ui_title("APKG Tools", "APKG 오디오 삽입과 고난도 단어 분석을 실행합니다.")

        ui_section("선택")
        ui_item("1)", "APKG 오디오 삽입", "기존 APKG에 MP3 미디어와 [sound:] 태그를 삽입")
        ui_item("2)", "고난도 단어 분석", "APKG 복습 기록과 FSRS 값으로 정렬")

        ui_section("이동")
        ui_item("B)", "이전 화면")
        ui_item("M)", "메인 메뉴")
        ui_item("S)", "종료")

        answer = normalize_menu_answer(ui_prompt("APKG Tools"))

        if answer in {"", "1", "AUDIO", "K1"}:
            inject_audio_into_apkg()
            return

        if answer in {"2", "DIFFICULTY", "HARD", "HARDWORDS", "K2"}:
            analyze_apkg_difficulty()
            return

        if answer == "B":
            raise BackScreen

        if answer == "M":
            raise ReturnToMenu

        if answer == "S":
            raise ExitProgram

        say("1, 2, B, M, S 중에서 입력해주세요.")



# Developer Utility 모듈 로드


def load_dev_utility_updater_module():
    import importlib.util

    module_path = BASE_DIR / "module" / "dev_utility_updater.py"

    if not module_path.exists():
        try:
            log_only("Developer Utility updater module not found.")
        except Exception:
            pass
        return None

    try:
        spec = importlib.util.spec_from_file_location("ankivoice_dev_utility_updater", module_path)

        if spec is None or spec.loader is None:
            try:
                log_only("Developer Utility updater spec is invalid.")
            except Exception:
                pass
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "bind_runtime"):
            try:
                log_only("Developer Utility updater bind_runtime is missing.")
            except Exception:
                pass
            return None

        module.bind_runtime(sys.modules[__name__])
        return module

    except Exception as e:
        try:
            log_only(f"Developer Utility updater load failed: {e}")
        except Exception:
            pass
        return None


def load_dev_utility_module():
    import types

    module_path = DEV_UTILITY_PACK_PATH

    if not module_path.exists():
        try:
            log_only("Developer Utility pack not found.")
        except Exception:
            pass
        return None

    if DEV_UTILITY_UPDATER is None or not hasattr(DEV_UTILITY_UPDATER, "get_dev_utility_pack_key"):
        try:
            log_only("Developer Utility key provider is unavailable.")
        except Exception:
            pass
        return None

    try:
        encrypted_data = module_path.read_bytes()
        dev_utility_key = DEV_UTILITY_UPDATER.get_dev_utility_pack_key()
        source_code = Fernet(dev_utility_key).decrypt(encrypted_data)
    except InvalidToken as e:
        try:
            log_only(f"Developer Utility decryption failed: {e}")
        except Exception:
            pass
        return None
    except Exception as e:
        try:
            log_only(f"Developer Utility load failed: {e}")
        except Exception:
            pass
        return None

    module = types.ModuleType("ankivoice_dev_utility")
    module.__file__ = str(module_path)
    module.__package__ = ""
    sys.modules["ankivoice_dev_utility"] = module

    try:
        exec(compile(source_code, str(module_path), "exec"), module.__dict__, module.__dict__)
    except Exception as e:
        try:
            log_only(f"Developer Utility compile failed: {e}")
        except Exception:
            pass
        return None

    if not hasattr(module, "bind_runtime"):
        try:
            log_only("Developer Utility bind_runtime is missing.")
        except Exception:
            pass
        return None

    module.bind_runtime(sys.modules[__name__])
    return module


def run_developer_utility():
    global DEV_UTILITY_MODULE

    if DEV_UTILITY_MODULE is None:
        DEV_UTILITY_MODULE = load_dev_utility_module()

    if DEV_UTILITY_MODULE is None:
        ui_clear_screen()
        ui_error("Developer Utility가 설치되어 있지 않습니다.")
        ui_hint("설정 / 정보 2페이지에서 Developer Utility 다운로드 / 업데이트를 먼저 실행하세요.")
        wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")
        return

    if not hasattr(DEV_UTILITY_MODULE, "launch_developer_utility"):
        ui_clear_screen()
        ui_error("Developer Utility 실행 함수를 찾지 못했습니다.")
        ui_hint("Developer Utility 다운로드 / 업데이트를 다시 실행하세요.")
        wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")
        return

    DEV_UTILITY_MODULE.launch_developer_utility()


def update_developer_utility_from_github():
    global DEV_UTILITY_MODULE

    if DEV_UTILITY_UPDATER is None:
        ui_clear_screen()
        ui_error("Developer Utility Updater를 찾지 못했습니다.")
        ui_hint("module/dev_utility_updater.py 파일을 확인하세요.")
        wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")
        return

    if not hasattr(DEV_UTILITY_UPDATER, "update_dev_utility_from_github"):
        ui_clear_screen()
        ui_error("Developer Utility Updater 실행 함수를 찾지 못했습니다.")
        ui_hint("module/dev_utility_updater.py 파일을 다시 확인하세요.")
        wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")
        return

    DEV_UTILITY_UPDATER.update_dev_utility_from_github()
    DEV_UTILITY_MODULE = load_dev_utility_module()
    refresh_app_identity()




# LAMI Service Image 원격 첨부파일 접수 모듈
def load_lami_pack_updater_module():
    import importlib.util

    module_path = BASE_DIR / "module" / "lami_pack_updater.py"

    if not module_path.exists():
        try:
            log_only("LAMI pack updater module not found.")
        except Exception:
            pass
        return None

    try:
        spec = importlib.util.spec_from_file_location("ankivoice_lami_pack_updater", module_path)

        if spec is None or spec.loader is None:
            try:
                log_only("LAMI pack updater spec is invalid.")
            except Exception:
                pass
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "bind_runtime"):
            try:
                log_only("LAMI pack updater bind_runtime is missing.")
            except Exception:
                pass
            return None

        module.bind_runtime(sys.modules[__name__])
        return module

    except Exception as e:
        try:
            log_only(f"LAMI pack updater load failed: {e}")
        except Exception:
            pass
        return None


def update_lami_pack_from_github(source="appendix_47"):
    if LAMI_PACK_UPDATER is None:
        ui_clear_screen()
        ui_error("AUXILIARY SERVICE IMAGE RECEIPT HANDLER NOT FOUND")
        ui_hint("LOCAL RECEIPT HANDLER IS NOT INSTALLED.")
        ui_hint("REQUIRED MODULE: module/lami_pack_updater.py")
        wait_back_to_previous("PRESS ENTER TO RETURN TO ADMINISTRATIVE PORTAL...")
        return False

    if not hasattr(LAMI_PACK_UPDATER, "retrieve_lami_pack_from_remote_portal"):
        ui_clear_screen()
        ui_error("AUXILIARY SERVICE IMAGE RECEIPT HANDLER IS INVALID")
        ui_hint("RECEIPT ENTRY POINT IS MISSING.")
        ui_hint("REQUIRED FUNCTION: retrieve_lami_pack_from_remote_portal")
        wait_back_to_previous("PRESS ENTER TO RETURN TO ADMINISTRATIVE PORTAL...")
        return False

    result = bool(LAMI_PACK_UPDATER.retrieve_lami_pack_from_remote_portal(source=source))
    if result:
        refresh_app_identity()
    return result


LAMI_PACK_UPDATER = load_lami_pack_updater_module()

DEV_UTILITY_UPDATER = load_dev_utility_updater_module()
DEV_UTILITY_MODULE = load_dev_utility_module()



# Menu 모듈 로드

def load_menu_module():
    import importlib.util

    module_path = BASE_DIR / "module" / "menu.py"

    if not module_path.exists():
        fatal_core_module_error(module_path)

    spec = importlib.util.spec_from_file_location("ankivoice_menu", module_path)

    if spec is None or spec.loader is None:
        fatal_core_module_error(module_path, "invalid module specification")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        fatal_core_module_error(module_path, str(e))

    if not hasattr(module, "bind_runtime"):
        fatal_core_module_error(module_path, "bind_runtime is missing")

    module.bind_runtime(sys.modules[__name__])
    return module


MENU_MODULE = load_menu_module()

for _menu_export_name in getattr(MENU_MODULE, "__all__", []):
    globals()[_menu_export_name] = getattr(MENU_MODULE, _menu_export_name)

try:
    del _menu_export_name
except NameError:
    pass

UI_MODULE.bind_runtime(sys.modules[__name__])
EXTRACTOR_MODULE.bind_runtime(sys.modules[__name__])
if MP3_COLLECTOR is not None:
    MP3_COLLECTOR.bind_runtime(sys.modules[__name__])
TEXT_POLICY_MODULE.bind_runtime(sys.modules[__name__])
APKG_AUDIO_COMPILER.bind_runtime(sys.modules[__name__])
AUDIO_FILE_MANAGER_MODULE.bind_runtime(sys.modules[__name__])
ANV_AUDIO_CONVERTER_MODULE.bind_runtime(sys.modules[__name__])
APKG_DIFFICULTY_ANALYZER.bind_runtime(sys.modules[__name__])
APKG_QUIZ_MODULE.bind_runtime(sys.modules[__name__])
ANV_DAILY_MODULE.bind_runtime(sys.modules[__name__])
NOTICE_VIEWER_MODULE.bind_runtime(sys.modules[__name__])
CLEANUP_MANAGER_MODULE.bind_runtime(sys.modules[__name__])
MENU_MODULE.bind_runtime(sys.modules[__name__])

def main():
    while True:
        try:
            show_startup_notice_once()
            break
        except ExitProgram:
            raise
        except KeyboardInterrupt:
            raise
        except Exception as e:
            show_unexpected_error_and_return_to_menu(e)

    while True:
        try:
            choice = ask_main_menu()

            if choice == "A1":
                convert_txt_to_csv()
                wait_return_to_menu()

            elif choice == "A2":
                convert_apkg_to_csv(save_full=False, save_word=True)
                wait_return_to_menu()

            elif choice == "A3":
                convert_apkg_to_csv(save_full=True, save_word=True)
                wait_return_to_menu()

            elif choice == "A4":
                run_txt_all_in_one()
                wait_return_to_menu()

            elif choice == "A5":
                run_apkg_all_in_one()
                wait_return_to_menu()

            elif choice == "P1":
                convert_anki_txt_to_plain_txt()
                wait_return_to_menu()

            elif choice == "P2":
                convert_apkg_to_plain_txt()
                wait_return_to_menu()

            elif choice == "P3":
                convert_csv_to_plain_txt()
                wait_return_to_menu()

            elif choice == "C1":
                if require_mp3_collector_or_show_message():
                    collect_tts_from_csv()

            elif choice == "C2":
                if require_mp3_collector_or_show_message():
                    collect_tts_from_plain_txt()

            elif choice == "C3":
                if require_mp3_collector_or_show_message():
                    collect_tts_from_anki_txt_extract()

            elif choice == "C4":
                if require_mp3_collector_or_show_message():
                    collect_tts_from_apkg()

            elif choice == "C5":
                if require_mp3_collector_or_show_message():
                    collect_single_tts_from_search()

            elif choice == "C6":
                if require_mp3_collector_or_show_message():
                    move_audio_mp3_to_collection_media()

            elif choice == "F1":
                move_audio_mp3_to_collection_media_managed()

            elif choice == "F2":
                add_language_prefix_to_audio_files()

            elif choice == "F3":
                remove_language_prefix_from_audio_files()

            elif choice in {"F4", "F5", "F6"}:
                # Extension add/change/repair is integrated into ANV Audio Converter.
                launch_anv_audio_converter()

            elif choice == "F7":
                replace_underscores_with_spaces_in_audio_files()

            elif choice == "K1":
                inject_audio_into_apkg()

            elif choice == "D1":
                analyze_apkg_difficulty_apkg()

            elif choice == "D2":
                analyze_apkg_difficulty_txt()

            elif choice == "D3":
                analyze_apkg_difficulty_csv()

            elif choice == "D4":
                analyze_apkg_difficulty_plain()

            elif choice == "D5":
                analyze_apkg_difficulty_theory()

            elif choice == "Q1":
                run_apkg_quiz()
                wait_return_to_menu()

            elif choice == "S1":
                configure_default_voice_settings()

            elif choice == "S2":
                configure_french_conjugation_setting()

            elif choice == "S3":
                configure_screen_mode()

            elif choice == "S4":
                configure_collection_media_dir()

            elif choice == "S5":
                configure_russian_stress_policy()

            elif choice == "S6":
                ui_clear_screen()
                ui_title("작업 폴더", "필요 파일을 넣고 결과를 확인할 위치입니다.")
                show_folder_info()
                wait_return_to_menu()

            elif choice == "S7":
                show_error_code_reference(clear=True)
                wait_return_to_menu()

            elif choice == "S8":
                show_legal_notice(clear=True)

            elif choice == "S9":
                show_about_info()

            elif choice == "S10":
                show_patch_notes(clear=True)

            elif choice == "S11":
                show_creator_note(clear=True)

            elif choice == "S12":
                delete_asset_folder_contents()

            elif choice == "S13":
                run_developer_utility()

            elif choice == "S14":
                update_developer_utility_from_github()

            elif choice == "S15":
                delete_optional_package_files()

            elif choice == "0":
                say("프로그램을 종료합니다.")
                break

        except BackScreen:
            continue

        except ReturnToMenu:
            continue

        except ExitProgram:
            raise

        except KeyboardInterrupt:
            raise

        except Exception as e:
            show_unexpected_error_and_return_to_menu(e)
            continue


if __name__ == "__main__":
    try:
        setup_console_window()
        apply_screen_mode()
        main()

    except ExitProgram:
        say()
        say("프로그램을 종료합니다.")

    except KeyboardInterrupt:
        say()
        say("키보드 입력으로 중단되었습니다.")
        say("확인 후 종료해주세요.")

    except Exception as e:
        # main() 바깥 최후 예외 처리
        try:
            log_only("[FATAL] main outside exception")
            log_only(traceback.format_exc())
        except Exception:
            pass
        say()
        say("[ERROR] 복구하지 못한 오류가 발생했습니다.")
        say(f"[ERROR] 이유: {e}")
        say("확인 후 종료해주세요.")

    finally:
        wait_exit()
