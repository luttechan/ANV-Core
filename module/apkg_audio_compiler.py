if __name__ == "__main__":
    print()
    print("[ERROR] module/apkg_audio_compiler.py is not a standalone program.")
    print("Run AnkiVoice.py instead.")
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass
    raise SystemExit(1)

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
from pathlib import Path
from urllib.parse import quote, unquote

try:
    from tqdm import tqdm
except Exception:
    tqdm = None

_RUNTIME_BOUND = False


def bind_runtime(runtime_module):
    global _RUNTIME_BOUND

    for name in dir(runtime_module):
        if name.startswith("__"):
            continue
        globals()[name] = getattr(runtime_module, name)

    _RUNTIME_BOUND = True
    return True


def require_runtime():
    if not _RUNTIME_BOUND:
        raise RuntimeError("APKG Audio Compiler는 단독 실행할 수 없습니다. AnkiVoice.py에서 불러와야 합니다.")

# APKG → APKG + Audio

def strip_anki_sound_tags(text):
    # 단어 필드에 이미 [sound:xxx.mp3]가 섞여 있어도 검색어/파일명 기준에서는 제거
    return re.sub(r"\[sound:[^\]]+\]", "", str(text or ""), flags=re.IGNORECASE).strip()


def clean_apkg_audio_word(word):
    return clean_word(strip_anki_sound_tags(word))


def apply_apkg_match_text_policy(word, language_mode="auto"):
    policy_func = globals().get("normalize_word_by_policy")

    if callable(policy_func):
        try:
            return policy_func(word, language_mode=language_mode, purpose="apkg_match")
        except Exception as e:
            try:
                log_only(f"APKG 매칭 정책 적용 실패: {word} / 이유: {e}")
            except Exception:
                pass

    return str(word or "")


def normalize_apkg_audio_word_key(word):
    word = clean_apkg_audio_word(word)
    word = apply_apkg_match_text_policy(word, language_mode="auto")
    return word.casefold()


def preview_notes_for_audio_field_selection(notes, title, hint, max_preview=4):
    rows = notes_to_rows(notes)

    if not rows:
        return 0

    ui_clear_screen()
    max_cols = max(len(row) for row in rows)
    field_name_by_index = {}

    for note in notes:
        for i, name in enumerate(note.get("field_names", [])):
            if name and i not in field_name_by_index:
                field_name_by_index[i] = name

    ui_section(title)
    ui_hint(hint)
    ui_hint("기존 필드에만 삽입합니다. 선택한 필드가 없는 노트는 건너뜁니다.")

    for col_index in range(max_cols):
        label = field_name_by_index.get(col_index, f"Field {col_index + 1}")
        samples = []

        for row in rows:
            if col_index < len(row):
                value = clean_text(row[col_index])

                if value:
                    samples.append(truncate_text(value, 110))

            if len(samples) >= max_preview:
                break

        say()
        say(f"  [{col_index + 1}] {label}")

        if samples:
            for sample_index, sample in enumerate(samples, start=1):
                say(f"      {sample_index}. {sample}")
        else:
            say("      (비어 있음)")

    say()
    ui_hint("첫 번째 필드는 1입니다.")
    return max_cols


def ask_apkg_audio_insert_mode():
    while True:
        ui_clear_screen()
        ui_title("삽입 방식", "선택한 필드에 [sound:파일명.mp3] 태그를 넣습니다.")

        ui_section("삽입 방식")
        ui_item("1)", "필드 뒤에 추가", "기존 내용 뒤에 음성 태그를 붙입니다. 권장")
        ui_item("2)", "필드 앞에 추가", "기존 내용 앞에 음성 태그를 붙입니다.")
        ui_item("3)", "필드 내용 교체", "선택한 필드를 음성 태그만 남기고 교체합니다.")

        ui_section("이동")
        ui_item("B)", "이전 화면")
        ui_item("M)", "메인 메뉴")
        ui_item("S)", "종료")

        answer = normalize_menu_answer(ui_prompt("삽입 방식"))

        if answer in {"", "1", "A", "APPEND"}:
            return "append"

        if answer in {"2", "P", "PREPEND"}:
            return "prepend"

        if answer in {"3", "R", "REPLACE"}:
            return "replace"

        if answer == "B":
            raise BackScreen

        if answer == "M":
            raise ReturnToMenu

        if answer == "S":
            raise ExitProgram

        say("1, 2, 3, B, M, S 중에서 입력해주세요.")


def ask_yes_no(title, message, default=False):
    while True:
        ui_clear_screen()
        ui_title(title)

        for line in _wrap_display(message, _terminal_width() - 8):
            ui_write("    " + line)

        ui_section("선택")
        ui_item("Y)", "예")
        ui_item("N)", "아니오")
        ui_item("B)", "이전 화면")
        ui_item("M)", "메인 메뉴")
        ui_item("S)", "종료")

        answer = normalize_menu_answer(ui_prompt("선택"))

        if not answer:
            return bool(default)

        if answer == "Y":
            return True

        if answer == "N":
            return False

        if answer == "B":
            raise BackScreen

        if answer == "M":
            raise ReturnToMenu

        if answer == "S":
            raise ExitProgram

        say("Y, N, B, M, S 중에서 입력해주세요.")


def normalize_user_path(path_text, base_dir=None):
    require_runtime()
    if base_dir is None:
        base_dir = BASE_DIR

    value = str(path_text or "").strip().strip('"').strip("'")
    value = os.path.expandvars(value)

    if not value:
        return None

    path = Path(value).expanduser()

    if not path.is_absolute():
        path = base_dir / path

    return path.resolve()


def find_case_insensitive_file(directory, filename):
    directory = Path(directory)
    direct_path = directory / filename

    if direct_path.is_file():
        return direct_path

    lowered = filename.lower()

    try:
        for item in directory.iterdir():
            if item.is_file() and item.name.lower() == lowered:
                return item
    except Exception:
        return None

    return None


def find_recursive_audio_file(directory, filename):
    directory = Path(directory)
    found = find_case_insensitive_file(directory, filename)

    if found:
        return found

    lowered = filename.lower()

    try:
        for item in directory.rglob("*.mp3"):
            if item.is_file() and item.name.lower() == lowered:
                return item
    except Exception:
        return None

    return None


def find_existing_audio_for_word(word, media_dir, language_mode, pronunciation_mode):
    filenames = []

    for candidate_word in [word, clean_apkg_audio_word(word)]:
        filename = safe_filename(
            candidate_word,
            pronunciation_mode=pronunciation_mode,
            language_mode=language_mode,
        )
        if filename not in filenames:
            filenames.append(filename)

    for filename in filenames:
        found = find_recursive_audio_file(media_dir, filename)

        if found:
            return found

    return None


def is_path_relative_to(child, parent):
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except Exception:
        return False


def select_directory_with_native_dialog(title="폴더 선택"):
    # Windows 환경에서는 폴더 선택창을 우선 시도한다.
    # tkinter가 없거나 GUI를 열 수 없으면 None을 반환하고 CLI 입력으로 진행한다.
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title=title)
        root.destroy()

        if selected:
            return Path(selected).expanduser().resolve()
    except Exception as e:
        log_only(f"폴더 선택창 호출 실패: {e}")

    return None



def get_saved_collection_media_dir():
    require_runtime()
    settings = load_settings()
    anki_settings = settings.get("anki", {})

    if not isinstance(anki_settings, dict):
        return None

    raw_path = str(anki_settings.get("collection_media_dir", "") or "").strip()

    if not raw_path:
        return None

    return normalize_user_path(raw_path)


def get_saved_collection_media_dir_label():
    require_runtime()
    path = get_saved_collection_media_dir()

    if path is None:
        return "미지정"

    return str(path)


def set_saved_collection_media_dir(path):
    settings = load_settings()
    settings.setdefault("anki", {})["collection_media_dir"] = str(Path(path).expanduser().resolve())
    return save_settings(settings)


def clear_saved_collection_media_dir():
    settings = load_settings()
    settings.setdefault("anki", {})["collection_media_dir"] = ""
    return save_settings(settings)


def ensure_directory_for_user_choice(path, title="폴더 확인"):
    path = Path(path).expanduser()

    if path.exists() and path.is_dir():
        return path.resolve()

    if path.exists() and not path.is_dir():
        ui_error("파일이 아니라 폴더 경로를 선택해야 합니다.")
        wait_back_to_previous("경로 선택으로 돌아가려면 Enter를 눌러주세요...")
        return None

    create_it = ask_yes_no(
        title,
        f"폴더가 없습니다. 생성할까요?\n{path}",
        default=True,
    )

    if not create_it:
        return None

    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def configure_collection_media_dir(return_message="설정 화면으로 돌아가려면 Enter를 눌러주세요..."):
    require_runtime()
    while True:
        ui_clear_screen()
        ui_title("Anki collection.media 경로", "Anki가 실제로 사용하는 미디어 폴더를 지정합니다.")

        current_path = get_saved_collection_media_dir()

        ui_section("현재 설정")
        ui_item("경로", str(current_path) if current_path else "미지정")

        candidates = find_anki_collection_media_dirs()

        ui_section("감지된 폴더")
        if candidates:
            for index, (path, label) in enumerate(candidates, start=1):
                ui_item(f"{index})", label, str(path))
        else:
            ui_hint("감지된 collection.media 폴더가 없습니다. 직접 경로 입력 또는 Windows 폴더 선택창을 사용하세요.")

        ui_section("직접 지정")
        ui_item("W)", "Windows 폴더 선택창", "가능한 경우 탐색기 폴더 선택창을 엽니다.")
        ui_item("C)", "직접 경로 입력", r"예: %APPDATA%\Anki2\프로필명\collection.media")
        ui_item("X)", "저장된 경로 삭제", "collection.media 경로 설정을 비웁니다.")

        ui_section("안내")
        ui_hint("지정한 경로는 설정 파일에 저장되며 다음 실행과 APKG 오디오 삽입 화면에서 다시 사용됩니다.")
        ui_hint("프로필마다 경로가 다를 수 있으므로 본인 Anki 프로필의 collection.media 폴더를 선택하세요.")

        ui_section("이동")
        ui_item("B)", "이전 화면")
        ui_item("M)", "메인 메뉴")
        ui_item("S)", "종료")

        answer_raw = ui_prompt("collection.media 경로")
        answer = normalize_menu_answer(answer_raw)

        selected = None

        if answer.isdigit():
            index = int(answer)
            if 1 <= index <= len(candidates):
                selected = candidates[index - 1][0]
            else:
                say("목록에 있는 번호만 입력해주세요.")
                continue

        elif answer == "W":
            selected = select_directory_with_native_dialog("Anki collection.media 폴더 선택")
            if selected is None:
                ui_error("폴더 선택창을 열지 못했습니다. 직접 경로 입력을 사용해주세요.")
                wait_back_to_previous("경로 설정으로 돌아가려면 Enter를 눌러주세요...")
                continue

        elif answer == "C":
            raw_path = ui_prompt("collection.media 폴더 경로")
            selected = normalize_user_path(raw_path)

            if selected is None:
                say("경로를 입력해주세요.")
                continue

        elif answer == "X":
            clear_saved_collection_media_dir()
            ui_clear_screen()
            ui_completed("저장된 collection.media 경로를 삭제했습니다.")
            wait_back_to_previous(return_message)
            return None

        elif answer == "B":
            raise BackScreen

        elif answer == "M":
            raise ReturnToMenu

        elif answer == "S":
            raise ExitProgram

        else:
            say("번호, W, C, X, B, M, S 중에서 입력해주세요.")
            continue

        selected = ensure_directory_for_user_choice(selected, title="collection.media 폴더 확인")

        if selected is None:
            continue

        set_saved_collection_media_dir(selected)
        ui_clear_screen()
        ui_completed("collection.media 경로를 저장했습니다.")
        ui_item("저장 경로", str(selected))
        ui_item("설정 파일", str(SETTINGS_FILE))
        wait_back_to_previous(return_message)
        return selected

def find_anki_collection_media_dirs():
    candidates = []
    seen = set()

    def add(path, label=None):
        try:
            path = Path(path).expanduser().resolve()
        except Exception:
            return

        key = str(path).lower()
        if key in seen:
            return

        if path.name != "collection.media":
            return

        seen.add(key)
        candidates.append((path, label or "Anki collection.media"))

    appdata = os.environ.get("APPDATA")
    if appdata:
        anki2_dir = Path(appdata) / "Anki2"
        try:
            for profile_dir in sorted(anki2_dir.iterdir(), key=lambda item: item.name.lower()):
                if profile_dir.is_dir():
                    media_dir = profile_dir / "collection.media"
                    if media_dir.exists():
                        add(media_dir, f"Anki collection.media / {profile_dir.name}")
        except Exception:
            pass

    try:
        home = Path.home()
        anki2_dir = home / "AppData" / "Roaming" / "Anki2"
        for profile_dir in sorted(anki2_dir.iterdir(), key=lambda item: item.name.lower()):
            if profile_dir.is_dir():
                media_dir = profile_dir / "collection.media"
                if media_dir.exists():
                    add(media_dir, f"Anki collection.media / {profile_dir.name}")
    except Exception:
        pass

    return candidates


def get_apkg_audio_candidate_dirs(language_mode):
    candidates = []
    seen = set()

    def count_mp3(path, recursive=False):
        try:
            path = Path(path)
            if not path.exists() or not path.is_dir():
                return 0
            pattern = "**/*.mp3" if recursive else "*.mp3"
            return sum(1 for item in path.glob(pattern) if item.is_file())
        except Exception:
            return 0

    def add(path, label, desc=""):
        path = Path(path)
        try:
            key = str(path.resolve()).lower() if path.exists() else str(path).lower()
        except Exception:
            key = str(path).lower()

        if key in seen:
            return

        seen.add(key)
        candidates.append((path, label, desc))

    language_audio_dir = get_language_audio_dir(language_mode)
    add(
        language_audio_dir,
        f"audio/{language_audio_dir.name}",
        f"현재 언어 기본 폴더 / MP3 {count_mp3(language_audio_dir)}개",
    )

    add(
        AUDIO_DIR,
        "audio 전체 재귀 검색",
        f"audio 하위 폴더 전체 검색 / MP3 {count_mp3(AUDIO_DIR, recursive=True)}개",
    )

    try:
        for child in sorted(AUDIO_DIR.iterdir(), key=lambda item: item.name.lower()):
            if child.is_dir():
                add(child, f"audio/{child.name}", f"MP3 {count_mp3(child)}개")
    except Exception:
        pass

    return candidates


def ask_apkg_audio_media_dir(language_mode):
    while True:
        ui_clear_screen()
        ui_title("APKG Compiler MP3 폴더 선택", "audio 폴더의 MP3를 APKG 내부 media에 포장합니다.")

        candidates = get_apkg_audio_candidate_dirs(language_mode)

        ui_section("MP3 검색 폴더")
        for index, (path, label, desc) in enumerate(candidates, start=1):
            ui_item(f"{index})", label, f"{path} / {desc}" if desc else str(path))

        ui_item("W)", "Windows 폴더 선택창", "가능한 경우 탐색기 폴더 선택창을 엽니다.")
        ui_item("C)", "직접 경로 입력", r"예: audio\en 또는 D:\AnkiVoice\audio")

        ui_section("안내")
        ui_hint("기본값은 audio/{language}입니다. 오디오 파일 위치가 확실하지 않다면 전체 검색을 선택하세요.")
        ui_hint("단어와 같은 이름의 MP3 파일을 찾아 연결합니다. 예: benefit → benefit.mp3")
        if language_mode == "ru" and callable(globals().get("get_russian_stress_policy_label")):
            ui_hint(f"러시아어 강세 처리: {get_russian_stress_policy_label()}")
        ui_hint("새로 수집한 MP3는 해당 언어의 오디오 폴더 (audio/{language}에 저장됩니다.")

        ui_section("이동")
        ui_item("B)", "이전 화면")
        ui_item("M)", "메인 메뉴")
        ui_item("S)", "종료")

        answer_raw = ui_prompt("MP3 폴더")
        answer = normalize_menu_answer(answer_raw)

        if answer.isdigit():
            index = int(answer)
            if 1 <= index <= len(candidates):
                selected = ensure_directory_for_user_choice(candidates[index - 1][0], title="MP3 폴더 확인")
                if selected is None:
                    continue
                return selected.resolve()

            say("목록에 있는 번호만 입력해주세요.")
            continue

        if answer == "W":
            selected = select_directory_with_native_dialog("APKG Compiler MP3 폴더 선택")
            if selected is None:
                ui_error("폴더 선택창을 열지 못했습니다. 직접 경로 입력을 사용해주세요.")
                wait_back_to_previous("폴더 선택으로 돌아가려면 Enter를 눌러주세요...")
                continue

            selected = ensure_directory_for_user_choice(selected, title="MP3 폴더 확인")
            if selected is None:
                continue
            return selected

        if answer == "C":
            raw_path = ui_prompt("MP3 폴더 경로")
            selected = normalize_user_path(raw_path)

            if selected is None:
                say("경로를 입력해주세요.")
                continue

            if selected.exists() and not selected.is_dir():
                say("폴더 경로를 입력해주세요.")
                continue

            if not selected.exists():
                create_it = ask_yes_no(
                    "폴더 생성",
                    f"폴더가 없습니다. 생성할까요?\n{selected}",
                    default=True,
                )
                if not create_it:
                    continue

            selected = ensure_directory_for_user_choice(selected, title="MP3 폴더 확인")
            if selected is None:
                continue
            return selected.resolve()

        if answer == "B":
            raise BackScreen

        if answer == "M":
            raise ReturnToMenu

        if answer == "S":
            raise ExitProgram

        say("번호, W, C, B, M, S 중에서 입력해주세요.")


def ask_ankivoice_audio_keep_policy(final_media_dir):
    final_media_dir = Path(final_media_dir)

    if is_path_relative_to(final_media_dir, AUDIO_DIR):
        return True

    while True:
        ui_clear_screen()
        ui_title("AnkiVoice 음성 파일 처리", "collection.media로 옮긴 뒤 AnkiVoice 쪽 MP3를 남길지 정합니다.")

        ui_section("선택")
        ui_item("1)", "옮긴 뒤 삭제", "AnkiVoice audio 폴더에 있던 원본 MP3를 collection.media로 이동합니다. 권장")
        ui_item("2)", "복사하고 남기기", "collection.media에 복사하고 AnkiVoice audio 폴더의 원본도 남깁니다.")

        ui_section("대상")
        ui_item("최종 폴더", str(final_media_dir))
        ui_item("AnkiVoice audio", str(AUDIO_DIR))

        ui_section("이동")
        ui_item("B)", "이전 화면")
        ui_item("M)", "메인 메뉴")
        ui_item("S)", "종료")

        answer = normalize_menu_answer(ui_prompt("AnkiVoice MP3 처리"))

        if answer in {"", "1", "D", "DELETE", "MOVE", "삭제", "이동"}:
            return False

        if answer in {"2", "K", "KEEP", "COPY", "남기기", "보존"}:
            return True

        if answer == "B":
            raise BackScreen

        if answer == "M":
            raise ReturnToMenu

        if answer == "S":
            raise ExitProgram

        say("1, 2, B, M, S 중에서 입력해주세요.")

def ask_download_missing_audio_files():
    while True:
        ui_clear_screen()
        ui_title("누락된 음성 처리", "선택한 폴더에 없는 음성을 어떻게 처리할지 정합니다.")

        ui_section("선택")
        ui_item("1)", "기존 MP3만 사용", "폴더에 이미 있는 MP3만 APKG에 삽입")
        ui_item("2)", "없는 MP3 자동 수집", "없는 단어는 사전에서 받아 선택한 폴더에 저장 후 삽입")

        ui_section("이동")
        ui_item("B)", "이전 화면")
        ui_item("M)", "메인 메뉴")
        ui_item("S)", "종료")

        answer = normalize_menu_answer(ui_prompt("처리 방식"))

        if answer in {"", "1", "N"}:
            return False

        if answer in {"2", "Y"}:
            return True

        if answer == "B":
            raise BackScreen

        if answer == "M":
            raise ReturnToMenu

        if answer == "S":
            raise ExitProgram

        say("1, 2, B, M, S 중에서 입력해주세요.")


def ask_existing_apkg_media_policy(source_apkg):
    media_map = load_apkg_media_map(source_apkg)

    if not media_map:
        return "preserve"

    while True:
        ui_clear_screen()
        ui_title("기존 미디어 처리", "APKG 안에 이미 미디어 파일이 있습니다.")

        ui_section("감지 결과")
        ui_item("기존 미디어", f"{len(media_map)}개")
        ui_hint("이미지, 기존 음성 등 APKG 안의 미디어 파일을 어떻게 처리할지 선택하세요.")

        ui_section("선택")
        ui_item("1)", "보존", "기존 미디어를 유지합니다. 같은 파일명이 있으면 기존 파일을 그대로 사용합니다. 권장")
        ui_item("2)", "덮어쓰기", "기존 미디어는 유지하되, 같은 파일명의 MP3만 새 파일로 교체합니다.")

        ui_section("이동")
        ui_item("B)", "이전 화면")
        ui_item("M)", "메인 메뉴")
        ui_item("S)", "종료")

        answer = normalize_menu_answer(ui_prompt("기존 미디어 처리"))

        if answer in {"", "1", "P", "PRESERVE", "보존"}:
            return "preserve"

        if answer in {"2", "O", "OVERWRITE", "덮어쓰기"}:
            return "overwrite"

        if answer == "B":
            raise BackScreen

        if answer == "M":
            raise ReturnToMenu

        if answer == "S":
            raise ExitProgram

        say("1, 2, B, M, S 중에서 입력해주세요.")


def get_apkg_media_policy_label(media_policy):
    if media_policy == "overwrite":
        return "덮어쓰기 / 같은 파일명 MP3만 교체"

    return "보존 / 같은 파일명은 기존 파일 사용"


def ask_apkg_output_path(source_apkg):
    default_path = APKG_DIR / f"{source_apkg.stem}_with_audio.apkg"
    same_folder_path = source_apkg.parent / f"{source_apkg.stem}_with_audio.apkg"

    while True:
        ui_clear_screen()
        ui_title("새 APKG 저장 경로", "원본 APKG는 수정하지 않고 새 파일로 저장합니다.")

        ui_section("저장 위치")
        ui_item("1)", "기본 저장", str(default_path))
        ui_item("2)", "원본과 같은 폴더", str(same_folder_path))
        ui_item("3)", "직접 폴더 선택", "선택한 폴더에 원본명_with_audio.apkg로 저장")
        ui_item("4)", "직접 파일 경로 입력", "파일명까지 직접 지정")

        ui_section("이동")
        ui_item("B)", "이전 화면")
        ui_item("M)", "메인 메뉴")
        ui_item("S)", "종료")

        answer = normalize_menu_answer(ui_prompt("저장 경로"))

        if answer in {"", "1"}:
            output_path = default_path
        elif answer == "2":
            output_path = same_folder_path
        elif answer == "3":
            raw_dir = ui_prompt("저장할 폴더 경로")
            selected_dir = normalize_user_path(raw_dir)

            if selected_dir is None:
                say("폴더 경로를 입력해주세요.")
                continue

            if selected_dir.exists() and not selected_dir.is_dir():
                say("폴더 경로를 입력해주세요.")
                continue

            selected_dir.mkdir(parents=True, exist_ok=True)
            output_path = selected_dir / f"{source_apkg.stem}_with_audio.apkg"
        elif answer == "4":
            raw_path = ui_prompt("저장할 APKG 파일 경로")
            output_path = normalize_user_path(raw_path)

            if output_path is None:
                say("파일 경로를 입력해주세요.")
                continue

            if output_path.suffix.lower() != ".apkg":
                output_path = output_path.with_suffix(".apkg")
        elif answer == "B":
            raise BackScreen
        elif answer == "M":
            raise ReturnToMenu
        elif answer == "S":
            raise ExitProgram
        else:
            say("1, 2, 3, 4, B, M, S 중에서 입력해주세요.")
            continue

        output_path = output_path.resolve()

        if output_path == source_apkg.resolve():
            ui_error("원본 APKG와 같은 경로에는 저장할 수 없습니다.")
            wait_back_to_previous("저장 경로 선택으로 돌아가려면 Enter를 눌러주세요...")
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)
        duplicate_mode = ask_duplicate_mode([output_path])
        output_path = resolve_output_path(output_path, duplicate_mode)
        return output_path


def choose_language_and_voice_for_apkg_audio():
    while True:
        language_mode = ask_language_mode()

        if not is_language_backend_ready(language_mode):
            show_pending_language_message(language_mode)
            wait_back_to_previous("언어 선택 화면으로 돌아가려면 Enter를 눌러주세요...")
            continue

        pronunciation_mode = None

        if language_mode in {"en", "zh"}:
            try:
                pronunciation_mode = ask_language_voice_setting_after_select(language_mode, purpose="APKG → APKG + Audio")
            except BackScreen:
                continue

        if pronunciation_mode is None:
            pronunciation_mode = get_default_voice_mode(language_mode)

        pronunciation_mode = get_effective_pronunciation_mode(language_mode, pronunciation_mode)
        return language_mode, pronunciation_mode


def get_ankivoice_audio_source_dirs(language_mode):
    dirs = []
    seen = set()

    def add(path):
        path = Path(path)
        try:
            key = str(path.resolve()).lower()
        except Exception:
            key = str(path).lower()

        if key in seen or not path.exists() or not path.is_dir():
            return

        seen.add(key)
        dirs.append(path)

    add(get_language_audio_dir(language_mode))
    add(AUDIO_DIR)

    try:
        for child in sorted(AUDIO_DIR.iterdir(), key=lambda item: item.name.lower()):
            if child.is_dir():
                add(child)
    except Exception:
        pass

    return dirs


def transfer_audio_to_final_media_dir(source_path, final_media_dir, keep_ankivoice_audio=True):
    source_path = Path(source_path).resolve()
    final_media_dir = Path(final_media_dir).resolve()
    final_media_dir.mkdir(parents=True, exist_ok=True)
    target_path = final_media_dir / source_path.name

    if source_path == target_path:
        return target_path, "same"

    source_is_ankivoice_audio = is_path_relative_to(source_path, AUDIO_DIR)

    if target_path.exists():
        if source_is_ankivoice_audio and not keep_ankivoice_audio:
            try:
                source_path.unlink()
                return target_path, "deleted_source"
            except Exception:
                return target_path, "kept_source"
        return target_path, "target_exists"

    if source_is_ankivoice_audio and not keep_ankivoice_audio:
        shutil.move(str(source_path), str(target_path))
        return target_path, "moved"

    shutil.copy2(source_path, target_path)
    return target_path, "copied"


def find_existing_audio_for_word_in_dirs(word, directories, language_mode, pronunciation_mode):
    for directory in directories:
        found = find_existing_audio_for_word(word, directory, language_mode, pronunciation_mode)
        if found:
            return found
    return None


def prepare_apkg_audio_files(words, language_mode, pronunciation_mode, media_dir, download_missing, keep_ankivoice_audio=True):
    media_dir = Path(media_dir).resolve()
    media_dir.mkdir(parents=True, exist_ok=True)

    audio_by_word = {}
    missing_words = []
    failed_words = []
    existing_count = 0
    downloaded_count = 0
    transferred_count = 0
    removed_ankivoice_count = 0
    download_stats = []

    search_dirs = []
    seen_dirs = set()

    def add_search_dir(path):
        path = Path(path).resolve()
        try:
            key = str(path).lower()
        except Exception:
            key = str(path)

        if key in seen_dirs or not path.exists() or not path.is_dir():
            return

        seen_dirs.add(key)
        search_dirs.append(path)

    add_search_dir(media_dir)

    # 선택 폴더가 audio 밖이면 사용자가 이미 모아둔 audio/{language}도 보조로 확인
    for candidate_dir in get_ankivoice_audio_source_dirs(language_mode):
        add_search_dir(candidate_dir)

    for word in words:
        key = normalize_apkg_audio_word_key(word)

        if not key or key in audio_by_word:
            continue

        existing_file = find_existing_audio_for_word_in_dirs(
            word,
            search_dirs,
            language_mode,
            pronunciation_mode,
        )

        if existing_file:
            audio_by_word[key] = Path(existing_file).resolve()
            existing_count += 1
            continue

        missing_words.append(word)

    if not download_missing or not missing_words:
        for word in missing_words:
            failed_words.append({
                "word": word,
                "reason_code": "audio_api_missing",
                "reason": "선택한 MP3 폴더와 AnkiVoice audio 폴더에서 대응 파일을 찾지 못했습니다.",
                "language_mode": language_mode,
                "mode": pronunciation_mode,
            })
        return audio_by_word, existing_count, downloaded_count, failed_words, transferred_count, removed_ankivoice_count

    download_dir = get_language_audio_dir(language_mode)
    download_dir.mkdir(parents=True, exist_ok=True)

    ui_clear_screen()
    ui_processing("없는 MP3를 audio/{language} 폴더에 수집하는 중입니다.")

    with tqdm(
        total=len(missing_words),
        desc="Preparing APKG Audio",
        unit="word",
        dynamic_ncols=True,
        leave=True,
    ) as bar:
        for word in missing_words:
            key = normalize_apkg_audio_word_key(word)
            filename = safe_filename(word, pronunciation_mode=pronunciation_mode, language_mode=language_mode)
            out_path = download_dir / filename
            label = word if pronunciation_mode in {"all", "default", "expert"} else f"{word} / {pronunciation_mode.upper()}"
            bar.set_postfix_str(f"{truncate_text(label, 22)} | 대기 중")

            try:
                audio_result = lookup_mp3_for_word_with_exact_entry_fallback(
                    word,
                    language_mode,
                    pronunciation_mode,
                )

                if audio_result.get("status") != "ok":
                    reason_code = audio_result.get("status") or "error"
                    failed_words.append({
                        "word": word,
                        "reason_code": reason_code,
                        "reason": audio_result.get("reason") or "음성 파일을 찾지 못했습니다.",
                        "language_mode": language_mode,
                        "mode": pronunciation_mode,
                        "available_modes": audio_result.get("available_modes", []),
                    })
                    bar.set_postfix_str(f"{truncate_text(label, 22)} | 실패")
                    bar.update(1)
                    continue

                file_results = audio_result.get("files") or []

                if file_results:
                    first_file = file_results[0]
                    mp3_url = first_file.get("url")
                    filename = first_file.get("filename") or filename
                    out_path = download_dir / filename
                else:
                    mp3_url = audio_result.get("url")

                stat = download_mp3(mp3_url, out_path)
                download_stats.append(stat)
                audio_by_word[key] = out_path
                downloaded_count += 1

                bar.set_postfix_str(f"{truncate_text(label, 22)} | {stat['speed_text']} | {stat['elapsed_text']}")
                log_only(
                    f"APKG 삽입용 MP3 준비 완료: {word} / lang={language_mode} / mode={pronunciation_mode} → {out_path} / "
                    f"size={stat['size_text']} / speed={stat['speed_text']} / elapsed={stat['elapsed_text']}"
                )
                time.sleep(0.35)

            except Exception as e:
                reason_code = classify_exception_reason_code(e, language_mode)
                failed_words.append({
                    "word": word,
                    "reason_code": reason_code,
                    "reason": str(e),
                    "language_mode": language_mode,
                    "mode": pronunciation_mode,
                })
                log_only(f"APKG 삽입용 MP3 준비 실패: {word} / code={reason_code} / 이유: {e}")
                bar.set_postfix_str(f"{truncate_text(label, 22)} | 오류")

            bar.update(1)

    return audio_by_word, existing_count, downloaded_count, failed_words, transferred_count, removed_ankivoice_count

def extract_anki_database_for_edit(apkg_path, temp_dir):
    with zipfile.ZipFile(apkg_path, "r") as z:
        names = set(z.namelist())

        if "collection.anki21b" in names:
            db_path = temp_dir / "collection_for_edit.sqlite"
            decompress_zstd_member_to_file(z, "collection.anki21b", db_path)
            return db_path, "collection.anki21b", True

        if "collection.anki21" in names:
            db_path = temp_dir / "collection.anki21"
            copy_zip_member_to_file(z, "collection.anki21", db_path)
            return db_path, "collection.anki21", False

        if "collection.anki2" in names:
            db_path = temp_dir / "collection.anki2"
            copy_zip_member_to_file(z, "collection.anki2", db_path)
            return db_path, "collection.anki2", False

    raise RuntimeError("APKG 파일에서 collection.anki21b, collection.anki21, collection.anki2를 찾지 못했습니다.")


def load_apkg_media_map(apkg_path):
    try:
        with zipfile.ZipFile(apkg_path, "r") as z:
            if "media" not in z.namelist():
                return {}

            raw = z.read("media")

        if is_zstd_payload(raw):
            try:
                raw = decompress_zstd_bytes(raw)
            except Exception as e:
                log_only(f"APKG media zstd 해제 실패: {apkg_path.name} / 이유: {e}")
                return {}

            if not raw:
                return {}

        data = json.loads(raw.decode("utf-8"))

        if isinstance(data, dict):
            return {str(key): str(value) for key, value in data.items()}

    except Exception as e:
        log_only(f"APKG media map 읽기 실패: {apkg_path.name} / 이유: {e}")

    return {}

def get_next_apkg_media_index(media_map, existing_zip_names):
    used = set(existing_zip_names)

    for key in media_map:
        used.add(str(key))

    numbers = []

    for item in used:
        if str(item).isdigit():
            numbers.append(int(item))

    number = (max(numbers) + 1) if numbers else 0

    while str(number) in used:
        number += 1

    return number


def add_audio_files_to_media_map(apkg_path, media_map, audio_paths, media_policy="preserve"):
    audio_paths = [Path(path) for path in audio_paths if Path(path).is_file()]
    existing_zip_names = set()

    with zipfile.ZipFile(apkg_path, "r") as z:
        existing_zip_names = set(z.namelist())

    filename_to_key = {filename: key for key, filename in media_map.items()}
    new_items = []
    replaced_keys = set()
    next_index = get_next_apkg_media_index(media_map, existing_zip_names)

    for audio_path in audio_paths:
        filename = audio_path.name

        if filename in filename_to_key:
            media_key = str(filename_to_key[filename])

            if media_policy == "overwrite" and media_key not in replaced_keys:
                new_items.append((media_key, audio_path))
                replaced_keys.add(media_key)

            continue

        while str(next_index) in media_map or str(next_index) in existing_zip_names:
            next_index += 1

        media_key = str(next_index)
        media_map[media_key] = filename
        filename_to_key[filename] = media_key
        new_items.append((media_key, audio_path))
        next_index += 1

    return media_map, new_items


def apply_apkg_output_text_policy(word, language_mode="auto"):
    policy_func = globals().get("normalize_word_by_policy")

    if callable(policy_func):
        try:
            return policy_func(word, language_mode=language_mode, purpose="export")
        except Exception as e:
            try:
                log_only(f"APKG 출력 정책 적용 실패: {word} / 이유: {e}")
            except Exception:
                pass

    return str(word or "")


def apply_audio_tags_to_notes(db_path, word_field_index, audio_field_index, insert_mode, audio_by_word, language_mode="auto"):
    conn = sqlite3.connect(db_path)
    changed = 0
    already_tagged = 0
    missing_audio = 0
    field_missing = 0
    blank_word = 0
    stress_stripped = 0
    now = int(time.time())

    try:
        cur = conn.cursor()
        cur.execute("SELECT id, flds FROM notes ORDER BY id")
        rows = cur.fetchall()

        for note_id, flds in rows:
            raw_fields = str(flds or "").split("\x1f")

            if word_field_index >= len(raw_fields) or audio_field_index >= len(raw_fields):
                field_missing += 1
                continue

            original_word_field = raw_fields[word_field_index]
            word = clean_apkg_audio_word(original_word_field)

            if not word:
                blank_word += 1
                continue

            audio_path = audio_by_word.get(normalize_apkg_audio_word_key(word))

            if not audio_path:
                missing_audio += 1
                continue

            filename = Path(audio_path).name
            sound_tag = f"[sound:{filename}]"
            current_value = raw_fields[audio_field_index]
            note_changed = False

            normalized_word_field = apply_apkg_output_text_policy(original_word_field, language_mode=language_mode)
            if normalized_word_field != original_word_field:
                raw_fields[word_field_index] = normalized_word_field
                stress_stripped += 1
                note_changed = True

            if sound_tag in current_value:
                already_tagged += 1
            else:
                if insert_mode == "replace":
                    new_value = sound_tag
                elif insert_mode == "prepend":
                    new_value = sound_tag if not current_value.strip() else sound_tag + " " + current_value.lstrip()
                else:
                    new_value = sound_tag if not current_value.strip() else current_value.rstrip() + " " + sound_tag

                raw_fields[audio_field_index] = new_value
                note_changed = True

            if not note_changed:
                continue

            new_flds = "\x1f".join(raw_fields)
            cur.execute(
                "UPDATE notes SET flds = ?, mod = ?, usn = ? WHERE id = ?",
                (new_flds, now, -1, note_id),
            )
            changed += 1

        conn.commit()

    finally:
        conn.close()

    return {
        "changed": changed,
        "already_tagged": already_tagged,
        "missing_audio": missing_audio,
        "field_missing": field_missing,
        "blank_word": blank_word,
        "stress_stripped": stress_stripped,
    }


def write_modified_apkg(source_apkg, output_apkg, db_path, db_member_name, db_is_zstd, media_map, new_media_items):
    output_apkg = Path(output_apkg)
    output_apkg.parent.mkdir(parents=True, exist_ok=True)

    media_payload = json.dumps(media_map, ensure_ascii=False).encode("utf-8")

    if db_is_zstd:
        output_db_member_name = "collection.anki21"
        db_payload = Path(db_path).read_bytes()
        skip_names = {
            "collection.anki21b",
            "collection.anki21",
            "collection.anki2",
            "media",
            "meta",
        }
        skip_numeric_media = True
    else:
        output_db_member_name = db_member_name
        db_payload = Path(db_path).read_bytes()
        skip_names = {db_member_name, "media"}
        skip_numeric_media = False

    new_media_names = {media_key for media_key, _ in new_media_items}

    with zipfile.ZipFile(source_apkg, "r") as zin, zipfile.ZipFile(output_apkg, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename in skip_names or item.filename in new_media_names:
                continue

            if skip_numeric_media and item.filename.isdigit():
                continue

            zout.writestr(item, zin.read(item.filename))

        zout.writestr(output_db_member_name, db_payload)
        zout.writestr("media", media_payload)

        for media_key, audio_path in new_media_items:
            zout.write(audio_path, arcname=media_key)

    return output_apkg

def build_modified_apkg_with_audio(source_apkg, output_apkg, word_field_index, audio_field_index, insert_mode, audio_by_word, media_policy="preserve", language_mode="auto"):
    with tempfile.TemporaryDirectory() as temp_name:
        temp_dir = Path(temp_name)
        db_path, db_member_name, db_is_zstd = extract_anki_database_for_edit(source_apkg, temp_dir)

        update_stats = apply_audio_tags_to_notes(
            db_path,
            word_field_index,
            audio_field_index,
            insert_mode,
            audio_by_word,
            language_mode=language_mode,
        )

        media_map = load_apkg_media_map(source_apkg)
        media_map, new_media_items = add_audio_files_to_media_map(
            source_apkg,
            media_map,
            list(audio_by_word.values()),
            media_policy=media_policy,
        )

        write_modified_apkg(
            source_apkg,
            output_apkg,
            db_path,
            db_member_name,
            db_is_zstd,
            media_map,
            new_media_items,
        )

    update_stats["new_media"] = len(new_media_items)
    update_stats["media_total"] = len(media_map)
    return update_stats


def inject_audio_into_apkg():
    require_runtime()
    while True:
        ui_clear_screen()
        ui_title("APKG → APKG + Audio", "기존 APKG에 MP3 미디어와 [sound:] 태그를 삽입합니다.")
        ui_hint("원본 APKG는 수정하지 않고 새 APKG를 생성합니다.")

        try:
            selected_apkg = select_apkg_file()
        except BackScreen:
            return

        if selected_apkg is None:
            ui_error("apkg 폴더에 선택할 APKG 파일이 없습니다.")
            ui_item("확인 폴더", str(APKG_DIR))
            wait_back_to_previous("메인 메뉴로 돌아가려면 Enter를 눌러주세요...")
            return

        try:
            ui_processing("APKG 내부 데이터베이스를 읽는 중입니다.")
            notes = extract_notes_from_apkg(selected_apkg)

            if not notes:
                say("APKG에서 읽을 노트가 없습니다.")
                wait_back_to_previous("메인 메뉴로 돌아가려면 Enter를 눌러주세요...")
                return

            max_cols = preview_notes_for_audio_field_selection(
                notes,
                "단어 필드 선택",
                "MP3 파일명과 사전 검색 기준이 될 단어 필드를 선택하세요.",
            )
            word_field_number = ask_int("단어 필드 번호", 1, max_cols, default=1)
            word_field_index = word_field_number - 1

            words = unique_keep_order([
                clean_apkg_audio_word(word)
                for word in extract_words_from_notes(notes, field_index=word_field_index)
                if clean_apkg_audio_word(word)
            ])

            if not words:
                say("수집할 단어가 없습니다.")
                wait_back_to_previous("메인 메뉴로 돌아가려면 Enter를 눌러주세요...")
                return

            max_cols = preview_notes_for_audio_field_selection(
                notes,
                "음성 삽입 필드 선택",
                "[sound:파일명.mp3] 태그를 넣을 기존 필드를 선택하세요.",
            )
            audio_field_number = ask_int("음성을 넣을 필드 번호", 1, max_cols, default=max_cols)
            audio_field_index = audio_field_number - 1

            insert_mode = ask_apkg_audio_insert_mode()
            language_mode, pronunciation_mode = choose_language_and_voice_for_apkg_audio()
            media_dir = ask_apkg_audio_media_dir(language_mode)
            keep_ankivoice_audio = True
            media_policy = ask_existing_apkg_media_policy(selected_apkg)
            download_missing = ask_download_missing_audio_files()
            output_apkg = ask_apkg_output_path(selected_apkg)

            ui_clear_screen()
            ui_title("APKG 오디오 삽입 준비", "설정을 확인하세요.")
            ui_section("대상")
            ui_item("원본 APKG", selected_apkg.name)
            ui_item("새 APKG", str(output_apkg))
            ui_item("단어 필드", f"Field {word_field_number}")
            ui_item("삽입 필드", f"Field {audio_field_number}")
            ui_item("삽입 방식", insert_mode)
            ui_item("언어", get_language_label(language_mode))
            ui_item("음성", get_voice_label(language_mode, pronunciation_mode))
            if language_mode == "ru" and callable(globals().get("get_russian_stress_policy_label")):
                ui_item("강세 처리", get_russian_stress_policy_label())
            ui_item("MP3 검색 폴더", str(media_dir))
            ui_item("다운로드 저장", str(get_language_audio_dir(language_mode)))
            ui_item("기존 APKG 미디어", get_apkg_media_policy_label(media_policy))
            ui_item("없는 MP3", "자동 수집" if download_missing else "기존 파일만 사용")
            ui_item("대상 단어", f"{len(words)}개")
            ui_hint("단어와 같은 이름의 MP3 파일을 찾아 연결합니다. 예: benefit → benefit.mp3")

            ask_action("APKG에 음성을 삽입할까요?")

            audio_by_word, existing_count, downloaded_count, failed_words, transferred_count, removed_ankivoice_count = prepare_apkg_audio_files(
                words,
                language_mode,
                pronunciation_mode,
                media_dir,
                download_missing,
                keep_ankivoice_audio=keep_ankivoice_audio,
            )

            if not audio_by_word:
                ui_clear_screen()
                ui_error("삽입할 MP3를 찾지 못했습니다.")
                show_failed_word_examples(failed_words, limit=20, title="미삽입 단어")
                wait_back_to_previous("메인 메뉴로 돌아가려면 Enter를 눌러주세요...")
                return

            ui_clear_screen()
            ui_processing("새 APKG를 생성하는 중입니다.")

            update_stats = build_modified_apkg_with_audio(
                selected_apkg,
                output_apkg,
                word_field_index,
                audio_field_index,
                insert_mode,
                audio_by_word,
                media_policy=media_policy,
                language_mode=language_mode,
            )

            ui_clear_screen()
            ui_completed("APKG 오디오 삽입이 완료되었습니다.")
            ui_section("결과")
            ui_item("새 APKG", str(output_apkg))
            ui_item("기존 MP3 사용", f"{existing_count}개")
            ui_item("MP3 이동/복사", f"{transferred_count}개")
            ui_item("AnkiVoice 원본 삭제", f"{removed_ankivoice_count}개")
            ui_item("새 MP3 수집", f"{downloaded_count}개")
            ui_item("노트 수정", f"{update_stats.get('changed', 0)}개")
            ui_item("강세 제거", f"{update_stats.get('stress_stripped', 0)}개")
            ui_item("이미 태그 있음", f"{update_stats.get('already_tagged', 0)}개")
            ui_item("APKG 신규 미디어", f"{update_stats.get('new_media', 0)}개")
            ui_item("전체 미디어", f"{update_stats.get('media_total', 0)}개")
            ui_item("필드 없음", f"{update_stats.get('field_missing', 0)}개")
            ui_item("MP3 없음", f"{update_stats.get('missing_audio', 0)}개")

            if failed_words:
                show_failed_word_examples(failed_words, limit=20, title="미삽입 단어")

            wait_back_to_previous("메인 메뉴로 돌아가려면 Enter를 눌러주세요...")
            return

        except BackScreen:
            continue

