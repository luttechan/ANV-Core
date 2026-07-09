if __name__ == "__main__":
    print()
    print("[ERROR] module/audio_file_manager.py is not a standalone program.")
    print("Run AnkiVoice.py instead.")
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass
    raise SystemExit(1)

import os
import re
import shutil
import time
from pathlib import Path

_RUNTIME_BOUND = False

__all__ = [
    "manage_audio_files_menu",
    "move_audio_mp3_to_collection_media_managed",
    "add_language_prefix_to_audio_files",
    "remove_language_prefix_from_audio_files",
    "add_extension_to_audio_files",
    "remove_extension_from_audio_files",
    "change_audio_file_extension",
    "replace_underscores_with_spaces_in_audio_files",
]

DEFAULT_LANGUAGE_CONFIGS = {
    "en": {"menu": "1", "label": "영어", "native_label": "English", "folder": "en"},
    "ja": {"menu": "2", "label": "일본어", "native_label": "日本語", "folder": "ja"},
    "zh": {"menu": "3", "label": "중국어", "native_label": "中文", "folder": "zh"},
    "ru": {"menu": "4", "label": "러시아어", "native_label": "Русский", "folder": "ru"},
    "fr": {"menu": "5", "label": "프랑스어", "native_label": "Français", "folder": "fr"},
    "de": {"menu": "6", "label": "독일어", "native_label": "Deutsch", "folder": "de"},
    "es": {"menu": "7", "label": "스페인어", "native_label": "Español", "folder": "es"},
}

KNOWN_LANGUAGE_PREFIXES = tuple(f"{code}_" for code in DEFAULT_LANGUAGE_CONFIGS)


def bind_runtime(runtime_module):
    global _RUNTIME_BOUND
    for name in dir(runtime_module):
        if name.startswith("__"):
            continue
        globals()[name] = getattr(runtime_module, name)
    _RUNTIME_BOUND = True
    return True


def _runtime_name(name, default=None):
    return globals().get(name, default)


def _say(text=""):
    func = _runtime_name("say")
    if callable(func):
        return func(text)
    print(text)


def _norm(value):
    func = _runtime_name("normalize_menu_answer")
    if callable(func):
        return func(value)
    return str(value or "").strip().upper()


def _prompt(label="입력"):
    func = _runtime_name("ui_prompt")
    if callable(func):
        return func(label)
    return input(f"{label}: ")


def _clear():
    func = _runtime_name("ui_clear_screen")
    if callable(func):
        func()


def _title(title, subtitle=""):
    _clear()
    func = _runtime_name("ui_title")
    if callable(func):
        func(title, subtitle)
    else:
        print(title)
        if subtitle:
            print(subtitle)


def _section(text):
    func = _runtime_name("ui_section")
    if callable(func):
        func(text)
    else:
        print(f"\n[{text}]")


def _item(label, value, desc=""):
    func = _runtime_name("ui_item")
    if callable(func):
        func(label, value, desc)
    else:
        if desc:
            print(f"  {label} {value} - {desc}")
        else:
            print(f"  {label} {value}")


def _hint(text):
    func = _runtime_name("ui_hint")
    if callable(func):
        func(text)
    else:
        print(f"  {text}")


def _error(text):
    func = _runtime_name("ui_error")
    if callable(func):
        func(text)
    else:
        print(f"[ERROR] {text}")


def _completed(text):
    func = _runtime_name("ui_completed")
    if callable(func):
        func(text)
    else:
        print(f"[OK] {text}")


def _wait(message="MP3 File Manager 메뉴로 돌아가려면 Enter를 눌러주세요..."):
    func = _runtime_name("wait_back_to_previous")
    if callable(func):
        return func(message)
    try:
        input(message)
    except EOFError:
        pass


def _handle_easter_egg(answer_raw):
    func = _runtime_name("handle_easter_egg_command")
    return bool(callable(func) and func(answer_raw))


def _raise_back():
    exc = _runtime_name("BackScreen", Exception)
    raise exc()


def _raise_menu():
    exc = _runtime_name("ReturnToMenu", Exception)
    raise exc()


def _raise_exit():
    exc = _runtime_name("ExitProgram", SystemExit)
    raise exc()


def _audio_root():
    root = _runtime_name("AUDIO_DIR")
    if root is not None:
        return Path(root)
    base_dir = Path(_runtime_name("BASE_DIR", Path.cwd()))
    return base_dir / "audio"


def _language_configs():
    configs = _runtime_name("LANGUAGE_CONFIGS")
    if isinstance(configs, dict) and configs:
        return configs
    return DEFAULT_LANGUAGE_CONFIGS


def _language_folder(code):
    func = _runtime_name("get_language_audio_dir")
    if callable(func):
        try:
            return Path(func(code))
        except Exception:
            pass

    config = _language_configs().get(code, {})
    folder = config.get("folder", code)
    path = _audio_root() / str(folder)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _language_label(code):
    config = _language_configs().get(code, {})
    label = config.get("label", code)
    native = config.get("native_label", "")
    return f"{label} / {native}" if native else label


def _language_prefix_for_dir(path):
    audio_dir = _audio_root()
    path = Path(path)

    for code, config in _language_configs().items():
        folder = str(config.get("folder", code))
        try:
            if path.resolve() == (audio_dir / folder).resolve():
                return f"{code}_"
        except Exception:
            pass

    raw = re.sub(r"[^0-9A-Za-z_-]+", "_", path.name.strip().lower()).strip("_")
    return f"{raw}_" if raw else "audio_"


def _iter_known_and_existing_audio_dirs():
    audio_dir = _audio_root()
    audio_dir.mkdir(parents=True, exist_ok=True)

    result = []
    seen = set()

    for code, config in sorted(_language_configs().items(), key=lambda pair: int(str(pair[1].get("menu", 999)))):
        path = _language_folder(code)
        key = str(path.resolve()).lower()
        if key not in seen:
            seen.add(key)
            result.append((code, path))

    try:
        for path in sorted(audio_dir.iterdir(), key=lambda p: p.name.lower()):
            if not path.is_dir():
                continue
            key = str(path.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            result.append((path.name, path))
    except Exception as e:
        _log(f"audio 폴더 목록 확인 실패: {audio_dir} / 이유: {e}")

    return result


def _count_files(directory, suffix=None, no_extension_only=False):
    count = 0
    try:
        for path in Path(directory).iterdir():
            if not path.is_file():
                continue
            if no_extension_only and path.suffix:
                continue
            if suffix and path.suffix.lower() != suffix.lower():
                continue
            count += 1
    except Exception:
        pass
    return count


def _select_audio_dirs(title="audio 폴더 선택", subtitle="작업할 audio 폴더를 선택합니다.", suffix=None, no_extension_only=False):
    while True:
        _title(title, subtitle)
        _section("대상 폴더")

        entries = _iter_known_and_existing_audio_dirs()
        menu_to_dirs = {}

        for index, (code, path) in enumerate(entries, start=1):
            count = _count_files(path, suffix=suffix, no_extension_only=no_extension_only)
            label = _language_label(code) if code in _language_configs() else code
            _item(f"{index})", label, f"{count}개 · {path}")
            menu_to_dirs[str(index)] = [path]

        all_dirs = [path for _, path in entries]
        all_count = sum(_count_files(path, suffix=suffix, no_extension_only=no_extension_only) for path in all_dirs)
        _item("A)", "모든 audio 하위 폴더", f"총 {all_count}개")

        _section("이동")
        _item("B)", "이전 화면")
        _item("M)", "메인 메뉴")
        _item("S)", "종료")

        answer_raw = _prompt("대상")
        if _handle_easter_egg(answer_raw):
            continue

        answer = _norm(answer_raw)
        if answer in menu_to_dirs:
            return menu_to_dirs[answer]
        if answer in {"A", "ALL", "전체", "모든언어", "모든폴더"}:
            return all_dirs
        if answer == "B":
            _raise_back()
        if answer == "M":
            _raise_menu()
        if answer == "S":
            _raise_exit()

        _say("목록에 있는 번호, A, B, M, S 중에서 입력해주세요.")
        time.sleep(0.8)


def _log(message):
    func = _runtime_name("log_only")
    if callable(func):
        try:
            func(message)
        except Exception:
            pass


def _normalize_extension(value, default=".mp3"):
    text = str(value or "").strip()
    if not text:
        text = default
    if not text.startswith("."):
        text = "." + text
    text = re.sub(r"\s+", "", text)
    return text.lower()


def _strip_known_language_prefix(stem):
    text = str(stem or "")
    lowered = text.lower()

    prefixes = set(KNOWN_LANGUAGE_PREFIXES)
    for code in _language_configs():
        prefixes.add(f"{str(code).lower()}_")

    for prefix in sorted(prefixes, key=len, reverse=True):
        if lowered.startswith(prefix):
            return text[len(prefix):]

    return text


def _build_prefix_add_operations(dirs):
    operations = []

    for directory in dirs:
        directory = Path(directory)
        prefix = _language_prefix_for_dir(directory)

        try:
            files = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except Exception as e:
            operations.append({"source": directory, "target": None, "status": "failed", "reason": str(e)})
            continue

        for path in files:
            if not path.is_file() or path.suffix.lower() != ".mp3":
                continue

            stem = _strip_known_language_prefix(path.stem)
            target = path.with_name(prefix + stem + ".mp3")
            operations.append(_make_rename_operation(path, target))

    return operations


def _build_prefix_remove_operations(dirs):
    operations = []

    for directory in dirs:
        directory = Path(directory)
        try:
            files = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except Exception as e:
            operations.append({"source": directory, "target": None, "status": "failed", "reason": str(e)})
            continue

        for path in files:
            if not path.is_file() or path.suffix.lower() != ".mp3":
                continue

            stripped = _strip_known_language_prefix(path.stem)
            if stripped == path.stem:
                operations.append({"source": path, "target": path, "status": "skip_same", "reason": "언어 prefix 없음"})
                continue

            target = path.with_name(stripped + ".mp3")
            operations.append(_make_rename_operation(path, target))

    return operations


def _build_extension_add_operations(dirs, extension):
    operations = []
    extension = _normalize_extension(extension)

    for directory in dirs:
        directory = Path(directory)
        try:
            files = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except Exception as e:
            operations.append({"source": directory, "target": None, "status": "failed", "reason": str(e)})
            continue

        for path in files:
            if not path.is_file() or path.suffix:
                continue
            target = path.with_name(path.name + extension)
            operations.append(_make_rename_operation(path, target))

    return operations


def _build_extension_remove_operations(dirs, extension):
    operations = []
    extension = _normalize_extension(extension)

    for directory in dirs:
        directory = Path(directory)
        try:
            files = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except Exception as e:
            operations.append({"source": directory, "target": None, "status": "failed", "reason": str(e)})
            continue

        for path in files:
            if not path.is_file() or path.suffix.lower() != extension:
                continue
            target = path.with_name(path.stem)
            operations.append(_make_rename_operation(path, target))

    return operations


def _build_extension_change_operations(dirs, old_extension, new_extension):
    operations = []
    old_extension = _normalize_extension(old_extension)
    new_extension = _normalize_extension(new_extension)

    for directory in dirs:
        directory = Path(directory)
        try:
            files = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except Exception as e:
            operations.append({"source": directory, "target": None, "status": "failed", "reason": str(e)})
            continue

        for path in files:
            if not path.is_file() or path.suffix.lower() != old_extension:
                continue
            target = path.with_suffix(new_extension)
            operations.append(_make_rename_operation(path, target))

    return operations


def _build_underscore_to_space_operations(dirs):
    operations = []

    for directory in dirs:
        directory = Path(directory)
        try:
            files = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except Exception as e:
            operations.append({"source": directory, "target": None, "status": "failed", "reason": str(e)})
            continue

        for path in files:
            if not path.is_file():
                continue
            if "_" not in path.stem:
                operations.append({"source": path, "target": path, "status": "skip_same", "reason": "언더바 없음"})
                continue

            target = path.with_name(path.stem.replace("_", " ") + path.suffix)
            operations.append(_make_rename_operation(path, target))

    return operations


def _make_rename_operation(source, target):
    source = Path(source)
    target = Path(target)

    try:
        if source.resolve() == target.resolve():
            return {"source": source, "target": target, "status": "skip_same", "reason": "이미 목표 파일명"}
    except Exception:
        if source == target:
            return {"source": source, "target": target, "status": "skip_same", "reason": "이미 목표 파일명"}

    if target.exists():
        return {"source": source, "target": target, "status": "conflict", "reason": "대상 파일명 존재"}

    return {"source": source, "target": target, "status": "rename", "reason": ""}


def _summarize_operations(operations):
    counts = {"rename": 0, "conflict": 0, "skip_same": 0, "failed": 0}

    for op in operations:
        status = op.get("status", "failed")
        counts[status] = counts.get(status, 0) + 1

    return counts


def _confirm_rename_operations(title, subtitle, operations, extra_notice=None):
    counts = _summarize_operations(operations)
    _title(title, subtitle)

    _section("변경 요약")
    _item("변경 예정", f"{counts.get('rename', 0)}개")
    _item("충돌 PASS", f"{counts.get('conflict', 0)}개")
    _item("이미 처리됨", f"{counts.get('skip_same', 0)}개")
    _item("확인 실패", f"{counts.get('failed', 0)}개")

    if extra_notice:
        _section("주의")
        for line in str(extra_notice).splitlines():
            if line.strip():
                _hint(line.strip())

    renames = [op for op in operations if op.get("status") == "rename"]
    conflicts = [op for op in operations if op.get("status") == "conflict"]

    if renames:
        _section("변경 예시")
        for index, op in enumerate(renames[:10], start=1):
            _item(f"{index})", op["source"].name, f"→ {op['target'].name}")
        if len(renames) > 10:
            _hint(f"... 외 {len(renames) - 10}개")

    if conflicts:
        _section("충돌 예시")
        for index, op in enumerate(conflicts[:5], start=1):
            _item(f"{index})", op["source"].name, f"대상 존재: {op['target'].name}")
        if len(conflicts) > 5:
            _hint(f"... 외 {len(conflicts) - 5}개")

    if counts.get("rename", 0) <= 0:
        _completed("변경할 파일이 없습니다.")
        _wait()
        return False

    _section("최종 확인")
    _hint("모든 파일이 위 규칙에 따라 이름이 변경됩니다.")
    _hint("해당 명령은 철회할 수 없습니다. 계속 하시겠습니까?")
    _item("Y)", "계속")
    _item("N)", "취소")

    while True:
        answer_raw = _prompt("Y / N")
        if _handle_easter_egg(answer_raw):
            continue
        answer = _norm(answer_raw)

        if answer == "Y":
            return True
        if answer in {"N", ""}:
            return False
        if answer == "M":
            _raise_menu()
        if answer == "S":
            _raise_exit()

        _say("Y 또는 N으로 입력해주세요.")


def _execute_rename_operations(operations, title="파일명 변경"):
    changed = []
    failed = []

    for op in operations:
        if op.get("status") != "rename":
            continue

        source = Path(op["source"])
        target = Path(op["target"])

        try:
            if target.exists():
                failed.append((source, target, "대상 파일명 존재"))
                continue
            source.rename(target)
            changed.append((source, target))
        except Exception as e:
            failed.append((source, target, str(e)))
            _log(f"파일명 변경 실패: {source} → {target} / 이유: {e}")

    _title(title, "변경 완료")

    if failed:
        _error("일부 파일 이름을 변경하지 못했습니다.")
    else:
        _completed("변경 완료")

    _section("결과")
    _item("변경 완료", f"{len(changed)}개")
    _item("실패", f"{len(failed)}개")

    if changed:
        _section("변경 완료 예시")
        for index, (source, target) in enumerate(changed[:10], start=1):
            _item(f"{index})", source.name, f"→ {target.name}")
        if len(changed) > 10:
            _hint(f"... 외 {len(changed) - 10}개")

    if failed:
        _section("실패 예시")
        for index, (source, target, reason) in enumerate(failed[:8], start=1):
            _item(f"{index})", source.name, f"→ {target.name}")
            _hint(reason)
        if len(failed) > 8:
            _hint(f"... 외 {len(failed) - 8}개")

    _wait()


def _ask_extension(prompt_label, default=".mp3"):
    _hint(f"확장자를 입력하세요. 예: mp3 또는 .mp3 / Enter = {default}")
    value = _prompt(prompt_label).strip()
    return _normalize_extension(value, default=default)


def add_language_prefix_to_audio_files():
    dirs = _select_audio_dirs(
        title="언어 prefix 추가",
        subtitle="audio/{language} 안의 MP3를 language_단어.mp3 형식으로 정리합니다.",
        suffix=".mp3",
    )
    operations = _build_prefix_add_operations(dirs)
    notice = "파일을 구분하기 쉽도록 en_, ja_, zh_와 같은 언어별 표시가 파일명 앞에 붙습니다."
    if _confirm_rename_operations("언어 prefix 추가", "파일명을 변경하기 전 최종 확인합니다.", operations, notice):
        _execute_rename_operations(operations, title="언어 prefix 추가")


def remove_language_prefix_from_audio_files():
    dirs = _select_audio_dirs(
        title="언어 prefix 제거",
        subtitle="audio/{language} 안의 MP3에서 en_, ja_, zh_ 같은 언어 표시를 제거합니다.",
        suffix=".mp3",
    )
    operations = _build_prefix_remove_operations(dirs)
    if _confirm_rename_operations("언어 prefix 제거", "파일명을 변경하기 전 최종 확인합니다.", operations):
        _execute_rename_operations(operations, title="언어 prefix 제거")


def add_extension_to_audio_files():
    dirs = _select_audio_dirs(
        title="확장자 추가",
        subtitle="확장자가 없는 파일에 지정한 확장자를 붙입니다.",
        no_extension_only=True,
    )
    _title("확장자 추가", "붙일 확장자를 입력합니다.")
    extension = _ask_extension("추가할 확장자", default=".mp3")
    operations = _build_extension_add_operations(dirs, extension)
    if _confirm_rename_operations("확장자 추가", "파일명을 변경하기 전 최종 확인합니다.", operations):
        _execute_rename_operations(operations, title="확장자 추가")


def remove_extension_from_audio_files():
    dirs = _select_audio_dirs(
        title="확장자 제거",
        subtitle="지정한 확장자를 파일명에서 제거합니다.",
    )
    _title("확장자 제거", "제거할 확장자를 입력합니다.")
    extension = _ask_extension("제거할 확장자", default=".mp3")
    operations = _build_extension_remove_operations(dirs, extension)
    notice = "확장자를 제거하면 Anki와 OS에서 파일 형식을 자동 인식하지 못할 수 있습니다."
    if _confirm_rename_operations("확장자 제거", "파일명을 변경하기 전 최종 확인합니다.", operations, notice):
        _execute_rename_operations(operations, title="확장자 제거")


def change_audio_file_extension():
    dirs = _select_audio_dirs(
        title="확장자 변경",
        subtitle="파일명 확장자만 변경합니다. 오디오 인코딩을 변환하지는 않습니다.",
    )
    _title("확장자 변경", "변경할 확장자를 입력합니다.")
    old_extension = _ask_extension("기존 확장자", default=".wav")
    new_extension = _ask_extension("새 확장자", default=".mp3")
    operations = _build_extension_change_operations(dirs, old_extension, new_extension)
    notice = "이 기능은 파일명만 바꿉니다. wav를 mp3로 실제 변환하는 기능이 아닙니다."
    if _confirm_rename_operations("확장자 변경", "파일명을 변경하기 전 최종 확인합니다.", operations, notice):
        _execute_rename_operations(operations, title="확장자 변경")


def replace_underscores_with_spaces_in_audio_files():
    dirs = _select_audio_dirs(
        title="언더바 → 반각 공백",
        subtitle="audio 폴더 안의 파일명에서 _ 를 반각 공백으로 바꿉니다.",
    )
    operations = _build_underscore_to_space_operations(dirs)
    notice = "파일명 본문에 있는 언더바만 반각 공백으로 바꿉니다.\nen_word.mp3 같은 파일은 en word.mp3로 변경됩니다.\n확장자는 그대로 유지됩니다."
    if _confirm_rename_operations("언더바 → 반각 공백", "파일명을 변경하기 전 최종 확인합니다.", operations, notice):
        _execute_rename_operations(operations, title="언더바 → 반각 공백")


def _append_collection_media_path_candidates(result, value):
    if value is None:
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _append_collection_media_path_candidates(result, item)
        return
    if isinstance(value, dict):
        for item in value.values():
            _append_collection_media_path_candidates(result, item)
        return

    text = str(value or "").strip()
    if text:
        result.append(text)


def _collect_collection_media_path_values_from_settings(settings):
    values = []

    def walk(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_text = str(key or "").lower()
                if (
                    "collection" in key_text
                    and "media" in key_text
                    and any(marker in key_text for marker in ["dir", "dirs", "path", "paths", "folder", "folders"])
                ):
                    _append_collection_media_path_candidates(values, value)
                walk(value)
        elif isinstance(obj, (list, tuple, set)):
            for item in obj:
                walk(item)

    walk(settings)
    return values


def _normalize_existing_collection_media_dir(path):
    try:
        candidate = Path(os.path.expandvars(os.path.expanduser(str(path or "").strip())))
    except Exception:
        return []

    result = []

    try:
        if candidate.is_dir() and candidate.name == "collection.media":
            result.append(candidate.resolve())
            return result

        child = candidate / "collection.media"
        if child.is_dir():
            result.append(child.resolve())
            return result

        if candidate.is_dir():
            for child in candidate.glob("*/collection.media"):
                if child.is_dir():
                    result.append(child.resolve())
    except Exception as e:
        _log(f"collection.media 경로 확인 실패: {candidate} / 이유: {e}")

    return result


def _default_anki2_roots():
    roots = []
    try:
        appdata = os.environ.get("APPDATA")
        if appdata:
            roots.append(Path(appdata) / "Anki2")
    except Exception:
        pass

    try:
        home = Path.home()
        roots.extend([
            home / "AppData" / "Roaming" / "Anki2",
            home / "Library" / "Application Support" / "Anki2",
            home / ".local" / "share" / "Anki2",
            home / ".anki2",
        ])
    except Exception:
        pass

    return roots


def _collection_media_dirs():
    settings = {}
    load_func = _runtime_name("load_settings")
    if callable(load_func):
        try:
            settings = load_func()
        except Exception as e:
            _log(f"설정 로드 실패: {e}")

    path_values = _collect_collection_media_path_values_from_settings(settings if isinstance(settings, dict) else {})
    for root in _default_anki2_roots():
        path_values.append(str(root))

    result = []
    seen = set()
    for value in path_values:
        for media_dir in _normalize_existing_collection_media_dir(value):
            key = str(media_dir).lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(media_dir)

    return result


def _existing_mp3_names(directory):
    names = set()
    try:
        for path in Path(directory).iterdir():
            if path.is_file() and path.suffix.lower() == ".mp3":
                names.add(path.name.lower())
    except Exception:
        pass
    return names


def _select_collection_media_dir():
    media_dirs = _collection_media_dirs()

    if not media_dirs:
        _title("MP3 → collection.media", "이동할 collection.media 폴더가 필요합니다.")
        _error("감지되었거나 설정된 collection.media 폴더가 없습니다.")
        _hint("설정 / 정보 → Anki collection.media 경로에서 먼저 경로를 지정하세요.")
        _wait()
        return None

    if len(media_dirs) == 1:
        return media_dirs[0]

    while True:
        _title("MP3 → collection.media", "이동할 대상 폴더를 선택합니다.")
        _section("감지된 collection.media")
        for index, media_dir in enumerate(media_dirs, start=1):
            _item(f"{index})", str(media_dir), f"기존 MP3 {_count_files(media_dir, suffix='.mp3')}개")

        _section("이동")
        _item("B)", "이전 화면")
        _item("M)", "메인 메뉴")
        _item("S)", "종료")

        answer_raw = _prompt("대상 번호")
        if _handle_easter_egg(answer_raw):
            continue
        answer = _norm(answer_raw)

        if answer.isdigit():
            index = int(answer)
            if 1 <= index <= len(media_dirs):
                return media_dirs[index - 1]
            _say("목록에 있는 번호만 입력해주세요.")
            time.sleep(0.8)
            continue

        if answer == "B":
            _raise_back()
        if answer == "M":
            _raise_menu()
        if answer == "S":
            _raise_exit()

        _say("목록에 있는 번호, B, M, S 중에서 입력해주세요.")
        time.sleep(0.8)


def _collect_mp3_files(dirs):
    files = []
    for directory in dirs:
        try:
            for path in sorted(Path(directory).iterdir(), key=lambda p: p.name.lower()):
                if path.is_file() and path.suffix.lower() == ".mp3":
                    files.append(path)
        except Exception as e:
            _log(f"MP3 목록 확인 실패: {directory} / 이유: {e}")
    return files


def _move_mp3_files(source_dirs, destination_dir):
    destination_dir = Path(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)

    moved = []
    skipped_duplicate = []
    skipped_same_dir = []
    failed = []
    destination_names = _existing_mp3_names(destination_dir)

    for source_path in _collect_mp3_files(source_dirs):
        try:
            if source_path.parent.resolve() == destination_dir.resolve():
                skipped_same_dir.append(source_path)
                continue

            target_path = destination_dir / source_path.name
            if source_path.name.lower() in destination_names or target_path.exists():
                skipped_duplicate.append(source_path)
                continue

            shutil.move(str(source_path), str(target_path))
            destination_names.add(target_path.name.lower())
            moved.append((source_path, target_path))
        except Exception as e:
            failed.append((source_path, str(e)))
            _log(f"collection.media 이동 실패: {source_path} → {destination_dir} / 이유: {e}")

    return {
        "moved": moved,
        "skipped_duplicate": skipped_duplicate,
        "skipped_same_dir": skipped_same_dir,
        "failed": failed,
    }


def move_audio_mp3_to_collection_media_managed():
    source_dirs = _select_audio_dirs(
        title="MP3 → collection.media",
        subtitle="이동할 audio 폴더를 선택합니다.",
        suffix=".mp3",
    )
    mp3_files = _collect_mp3_files(source_dirs)

    if not mp3_files:
        _title("MP3 → collection.media", "이동할 MP3가 없습니다.")
        _error("선택한 audio 폴더에 MP3 파일이 없습니다.")
        for source_dir in source_dirs:
            _item("확인 폴더", str(source_dir))
        _wait()
        return

    destination_dir = _select_collection_media_dir()
    if destination_dir is None:
        return

    destination_names = _existing_mp3_names(destination_dir)
    duplicate_count = sum(1 for path in mp3_files if path.name.lower() in destination_names)
    movable_count = len(mp3_files) - duplicate_count

    _title("MP3 → collection.media", "audio 폴더의 MP3를 Anki 미디어 폴더로 이동합니다.")
    _section("이동 경로")
    _item("원본", " | ".join(str(path) for path in source_dirs[:4]) + (f" | 외 {len(source_dirs) - 4}개" if len(source_dirs) > 4 else ""))
    _item("대상", str(destination_dir))

    _section("이동 요약")
    _item("확인한 MP3", f"{len(mp3_files)}개")
    _item("이동 예정", f"{movable_count}개")
    _item("중복 PASS", f"{duplicate_count}개")
    _hint("대상 collection.media에 같은 이름의 MP3가 있으면 덮어쓰지 않고 건너뜁니다.")
    _hint("이동 완료된 파일은 audio 폴더에서 제거됩니다.")

    if movable_count <= 0:
        _completed("새로 이동할 MP3가 없습니다.")
        _wait()
        return

    _section("최종 확인")
    _item("Y)", "이 설정으로 이동")
    _item("N)", "취소")

    while True:
        answer_raw = _prompt("Y / N")
        if _handle_easter_egg(answer_raw):
            continue
        answer = _norm(answer_raw)
        if answer == "Y":
            break
        if answer in {"N", ""}:
            return
        if answer == "M":
            _raise_menu()
        if answer == "S":
            _raise_exit()
        _say("Y 또는 N으로 입력해주세요.")

    result = _move_mp3_files(source_dirs, destination_dir)
    _title("MP3 → collection.media", "이동 완료")

    if result["failed"]:
        _error("일부 MP3를 이동하지 못했습니다.")
    else:
        _completed("MP3 이동이 끝났습니다.")

    _section("이동 결과")
    _item("대상 폴더", str(destination_dir))
    _item("이동 완료", f"{len(result['moved'])}개")
    _item("중복 PASS", f"{len(result['skipped_duplicate'])}개")
    _item("대상 폴더 내부", f"{len(result['skipped_same_dir'])}개 PASS")
    _item("실패", f"{len(result['failed'])}개")

    if result["moved"]:
        _section("이동 완료 예시")
        for index, (source, target) in enumerate(result["moved"][:8], start=1):
            _item(f"{index})", source.name, f"→ {target}")
        if len(result["moved"]) > 8:
            _hint(f"... 외 {len(result['moved']) - 8}개")

    if result["failed"]:
        _section("실패 예시")
        for index, (source, reason) in enumerate(result["failed"][:8], start=1):
            _item(f"{index})", str(source), reason)
        if len(result["failed"]) > 8:
            _hint(f"... 외 {len(result['failed']) - 8}개")

    _wait()


def manage_audio_files_menu():
    while True:
        _title("MP3 File Manager", "audio 파일명 정리와 collection.media 이동을 처리합니다.")

        _section("Anki 미디어 이동")
        _item("1)", "audio MP3 → collection.media 이동", "수집한 MP3를 Anki 미디어 폴더로 이동")

        _section("언어 prefix 정리")
        _item("2)", "언어 prefix 추가", "audio/{language} → language_단어.mp3")
        _item("3)", "언어 prefix 제거", "language_단어.mp3 → 단어.mp3")

        _section("파일명 정리")
        _item("4)", "언더바 → 반각 공백", "word_name.mp3 → word name.mp3")

        _section("APKG 오디오")
        _item("5)", "APKG 오디오 컴파일러", "APKG에 오디오 참조/미디어 삽입")

        _section("별도 프로그램")
        _item("6)", "ANV 오디오 컨버터 실행", "FFmpeg 변환과 확장자 추가/변경/보정")

        _section("이동")
        _item("B)", "메인 메뉴")
        _item("S)", "종료")

        answer_raw = _prompt("MP3 File Manager")
        if _handle_easter_egg(answer_raw):
            continue
        answer = _norm(answer_raw)

        if answer == "1":
            return "F1"
        if answer == "2":
            return "F2"
        if answer == "3":
            return "F3"
        if answer == "4":
            return "F7"
        if answer == "5":
            return "K1"
        if answer == "6":
            launcher = _runtime_name("launch_anv_audio_converter")
            if callable(launcher):
                launcher()
                continue
            _error("ANV 오디오 컨버터 모듈을 찾지 못했습니다.")
            _hint("module/anv_audio_converter.py 파일과 AnkiVoice.py의 모듈 로더를 확인하세요.")
            _wait()
            continue
        if answer in {"B", "M"}:
            return None
        if answer == "S":
            _raise_exit()

        _say("1, 2, 3, 4, 5, 6, B, S 중에서 입력해주세요.")
