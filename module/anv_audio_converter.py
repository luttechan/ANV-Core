import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import webbrowser
import zipfile
from pathlib import Path

_RUNTIME_BOUND = False
_STANDALONE_MODE = False

FFMPEG_DOWNLOAD_URL = "https://www.ffmpeg.org/download.html"
_FFMPEG_DOWNLOAD_OPENED = False

__all__ = [
    "launch_anv_audio_converter",
    "get_saved_ffmpeg_path_label",
]

SUPPORTED_INPUT_EXTENSIONS = {
    "mp3", "wav", "m4a", "aac", "flac", "ogg", "opus", "webm",
    "wma", "aiff", "aif", "alac", "mka", "oga", "weba",
}

SUPPORTED_OUTPUT_EXTENSIONS = {
    "mp3", "wav", "flac", "ogg", "opus", "m4a",
}

AUDIO_EXTENSIONS_FOR_RENAME = SUPPORTED_INPUT_EXTENSIONS | SUPPORTED_OUTPUT_EXTENSIONS

AUDIO_SIGNATURE_EXTENSIONS = {
    "mp3", "wav", "flac", "ogg", "opus", "m4a", "aac", "webm", "wma", "aiff",
}


def _detect_audio_extension(path):
    try:
        with Path(path).open("rb") as f:
            data = f.read(64)
    except Exception:
        return None

    if not data:
        return None
    if data.startswith(b"ID3"):
        return ".mp3"
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return ".mp3"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return ".wav"
    if data.startswith(b"fLaC"):
        return ".flac"
    if data.startswith(b"OggS"):
        if b"OpusHead" in data:
            return ".opus"
        return ".ogg"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return ".m4a"
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xF0) == 0xF0:
        return ".aac"
    if data.startswith(bytes.fromhex("3026B2758E66CF11A6D900AA0062CE6C")):
        return ".wma"
    if data.startswith(bytes.fromhex("1A45DFA3")):
        return ".webm"
    if data.startswith(b"FORM") and data[8:12] in {b"AIFF", b"AIFC"}:
        return ".aiff"
    return None


def _collect_signature_candidates(folder, recursive, mode):
    iterator = Path(folder).rglob("*") if recursive else Path(folder).glob("*")
    result = []
    for path in iterator:
        if not path.is_file():
            continue
        detected = _detect_audio_extension(path)
        if not detected:
            continue

        suffix = path.suffix.lower()

        if mode == "missing" and suffix:
            continue
        if mode == "change" and (not suffix or suffix == detected):
            continue
        if mode == "normalize" and suffix == detected:
            continue
        if mode == "fix" and suffix == detected:
            continue

        result.append((path, detected))
    return sorted(result, key=lambda item: str(item[0]).lower())


OUTPUT_ENCODER_ARGS = {
    "mp3": ["-codec:a", "libmp3lame", "-q:a", "2"],
    "wav": ["-codec:a", "pcm_s16le"],
    "flac": ["-codec:a", "flac"],
    "ogg": ["-codec:a", "libvorbis", "-q:a", "5"],
    "opus": ["-codec:a", "libopus", "-b:a", "96k"],
    "m4a": ["-codec:a", "aac", "-b:a", "192k"],
}


def bind_runtime(runtime_module):
    global _RUNTIME_BOUND
    for name in dir(runtime_module):
        if name.startswith("__"):
            continue
        globals()[name] = getattr(runtime_module, name)
    _RUNTIME_BOUND = True
    return True


def _module_file():
    try:
        return Path(__file__).resolve()
    except Exception:
        return Path.cwd()


def _base_dir():
    if "BASE_DIR" in globals():
        return Path(globals().get("BASE_DIR"))

    current = _module_file()
    if current.parent.name.lower() == "module":
        return current.parent.parent
    return current.parent


def _setting_dir():
    path = Path(globals().get("SETTING_DIR", _base_dir() / "setting"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _audio_dir():
    path = Path(globals().get("AUDIO_DIR", _base_dir() / "audio"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _converter_module_dir():
    """Return the directory that contains this converter module file.

    FFmpeg detection is intentionally anchored here.
    This prevents the converter from climbing to the parent Release folder.
    """
    current = _module_file()
    if current.is_file():
        return current.parent
    return current


def _ffmpeg_root_dir():
    """Return the only allowed FFmpeg working folder.

    Allowed root: <this file's directory>/ffmpeg
    Not allowed: BASE_DIR/ffmpeg, parent folder/ffmpeg, C:\ffmpeg, or system PATH.
    """
    path = _converter_module_dir() / "ffmpeg"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _settings_file():
    return Path(globals().get("SETTINGS_FILE", _setting_dir() / "anki_universal_tool_settings.json"))


def _load_settings():
    func = globals().get("load_settings")
    if callable(func):
        try:
            data = func()
            return data if isinstance(data, dict) else {}
        except Exception:
            pass

    path = _settings_file()
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_settings(settings):
    func = globals().get("save_settings")
    if callable(func):
        return bool(func(settings))

    path = _settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def _norm(value):
    func = globals().get("normalize_menu_answer")
    if callable(func):
        return func(value)
    return str(value or "").strip().upper()


def _say(value=""):
    func = globals().get("say")
    if callable(func):
        func(value)
    else:
        print(value)


def _console_title(title):
    if os.name == "nt":
        try:
            os.system(f"title {title}")
        except Exception:
            pass


def _enable_ansi_support():
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def _set_windows_color(attribute_hex="1F"):
    if os.name != "nt":
        return

    try:
        os.system(f"color {attribute_hex}")
    except Exception:
        pass

    try:
        attr = int(attribute_hex, 16)
        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        ctypes.windll.kernel32.SetConsoleTextAttribute(handle, attr)
    except Exception:
        pass


def _direct_clear():
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        print("\n" * 60)


def _terminal_width():
    try:
        return max(72, min(120, shutil.get_terminal_size((96, 24)).columns))
    except Exception:
        return 96


def _blue_text(text=""):
    return f"\033[44m\033[97m{text}\033[0m"


def _blue_line(text=""):
    width = _terminal_width()
    raw = str(text or "")
    if len(raw) > width:
        raw = raw[: max(0, width - 1)] + "…"
    print(_blue_text(raw.ljust(width)))


def _blue_blank():
    _blue_line("")


def _blue_rule(char="="):
    _blue_line(str(char or "=")[:1] * _terminal_width())


def _enter_converter_screen():
    _console_title("ANV Audio Converter")
    _enable_ansi_support()
    _set_windows_color("1F")
    _direct_clear()
    _set_windows_color("1F")
    _enable_ansi_support()


def _restore_app_screen():
    print("\033[0m", end="")
    func = globals().get("apply_screen_mode")
    if callable(func):
        try:
            func()
        except Exception:
            pass
    elif os.name == "nt":
        _set_windows_color("F0")

    refresh = globals().get("refresh_app_identity")
    if callable(refresh):
        try:
            refresh()
        except Exception:
            pass
    else:
        _console_title("AnkiVoice")


def _clear_app_screen():
    func = globals().get("ui_clear_screen")
    if callable(func):
        func()
    else:
        _direct_clear()


def _title(title, subtitle=""):
    _blue_rule("=")
    _blue_line(f"  {title}")
    if subtitle:
        _blue_line(f"  {subtitle}")
    _blue_rule("=")


def _section(title):
    _blue_blank()
    _blue_line(f"  >> {title}")
    _blue_line("  " + "-" * max(8, _terminal_width() - 5))


def _item(label, text, note=""):
    suffix = f"  :: {note}" if note else ""
    _blue_line(f"    {label:<4} {text}{suffix}")


def _kv(key, value, note=""):
    suffix = f"  ({note})" if note else ""
    _blue_line(f"    {key}: {value}{suffix}")


def _hint(text):
    _blue_line(f"    - {text}")


def _error(text):
    _blue_line(f"    [ERROR] {text}")


def _completed(text):
    _blue_line(f"    [OK] {text}")


def _say(value=""):
    _blue_line(f"    {value}")


def _prompt(label="ANV Audio Converter"):
    _enable_ansi_support()
    _set_windows_color("1F")
    width = _terminal_width()
    prompt = f"  {label} > "
    try:
        return input(_blue_text(prompt.ljust(min(width, max(len(prompt), 16)))))
    finally:
        _set_windows_color("1F")


def _wait(message="Press Enter to continue..."):
    _prompt(message)


def _confirm(message):
    answer = _norm(_prompt(f"{message} [Y/N]"))
    return answer in {"Y", "YES", "1"}


def _clean_path_text(value):
    text = str(value or "").strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    return text


def _to_path(value):
    text = _clean_path_text(value)
    if not text:
        return None
    return Path(text).expanduser()



def _run_tk_dialog(dialog_func):
    """Run a small Tk dialog without making Tk a permanent dependency."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        return dialog_func(filedialog, root)
    except Exception:
        return None
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass


def _open_directory_dialog(title, initialdir=None):
    initial = Path(initialdir or _audio_dir())

    def choose(filedialog, root):
        return filedialog.askdirectory(
            parent=root,
            title=str(title or "Select folder"),
            initialdir=str(initial),
            mustexist=True,
        )

    result = _run_tk_dialog(choose)
    return Path(result).expanduser() if result else None


def _open_file_dialog(title, initialdir=None, multiple=True):
    initial = Path(initialdir or _audio_dir())
    audio_patterns = " ".join(f"*.{ext}" for ext in sorted(AUDIO_EXTENSIONS_FOR_RENAME))

    def choose(filedialog, root):
        kwargs = {
            "parent": root,
            "title": str(title or "Select files"),
            "initialdir": str(initial),
            "filetypes": [
                ("All files", "*.*"),
                ("Audio files", audio_patterns),
            ],
        }
        if multiple:
            return filedialog.askopenfilenames(**kwargs)
        selected = filedialog.askopenfilename(**kwargs)
        return (selected,) if selected else ()

    result = _run_tk_dialog(choose)
    if not result:
        return []
    return [Path(item).expanduser() for item in result if str(item).strip()]


def _manual_file_paths_input():
    _hint("Separate multiple file paths with | .")
    raw = _prompt("File path(s)")
    paths = []
    for part in str(raw or "").split("|"):
        path = _to_path(part)
        if path and path.is_file():
            paths.append(path)
    return paths


def _select_directory(title, initialdir=None):
    _section("Directory selection")
    _hint("A folder selection window will open. Cancel it to type a path manually.")
    folder = _open_directory_dialog(title, initialdir or _audio_dir())
    if folder and folder.exists() and folder.is_dir():
        _kv("Selected folder", folder)
        return folder

    _hint("Folder selection was cancelled or unavailable.")
    raw = _prompt("Directory path")
    folder = _to_path(raw)
    if folder and folder.exists() and folder.is_dir():
        return folder
    return None


def _select_files(title, initialdir=None):
    _section("File selection")
    _hint("A file selection window will open. Cancel it to type file paths manually.")
    files = [path for path in _open_file_dialog(title, initialdir or _audio_dir(), multiple=True) if path.is_file()]
    if files:
        _kv("Selected files", len(files))
        return files

    _hint("File selection was cancelled or unavailable.")
    return _manual_file_paths_input()


def _common_parent_for_files(files):
    files = [Path(path) for path in files if path]
    if not files:
        return _audio_dir()
    try:
        return Path(os.path.commonpath([str(path.parent) for path in files]))
    except Exception:
        return files[0].parent


def _signature_candidate_from_path(path, mode):
    path = Path(path)
    if not path.is_file():
        return None

    detected = _detect_audio_extension(path)
    if not detected:
        return None

    suffix = path.suffix.lower()

    if mode == "missing" and suffix:
        return None
    if mode == "change" and (not suffix or suffix == detected):
        return None
    if mode in {"normalize", "fix"} and suffix == detected:
        return None

    return (path, detected)


def _collect_signature_candidates_from_paths(paths, mode):
    result = []
    for path in paths:
        candidate = _signature_candidate_from_path(path, mode)
        if candidate:
            result.append(candidate)
    return sorted(result, key=lambda item: str(item[0]).lower())


def _choose_asset_scope(title, allow_selected=True):
    while True:
        _section("Asset scope")
        _item("1)", "All assets in a folder", "Open a directory window and process matching files inside it.")
        if allow_selected:
            _item("2)", "Selected files only", "Open a file window and process only the selected files.")
        _item("B)", "Return to ANV Audio Converter")
        _item("M)", "Return to Main Menu")
        _item("S)", "Exit")

        answer = _norm(_prompt(title or "Asset scope"))
        if answer in {"", "1", "A", "ALL", "FOLDER"}:
            return "folder"
        if allow_selected and answer in {"2", "FILE", "FILES", "SELECT", "SELECTED"}:
            return "files"
        if _run_common_navigation(answer):
            return None
        _say("1, 2, B, M, S 중에서 입력해주세요.")


def _select_conversion_assets(default_input_ext="all"):
    scope = _choose_asset_scope("Conversion target")
    if scope is None:
        return None, None, None, None, set()

    if scope == "files":
        selected_files = _select_files("Select source audio files", _audio_dir())
        files = [path for path in selected_files if path.is_file()]
        if not files:
            return "Selected files only", _common_parent_for_files([]), False, [], set()
        return "Selected files only", _common_parent_for_files(files), False, sorted(files, key=lambda p: str(p).lower()), set()

    input_folder = _select_directory("Select source audio folder", _audio_dir())
    if not input_folder:
        return "All assets in folder", None, True, [], set()

    _hint("Input extensions: mp3,wav,m4a,webm or all")
    input_exts = _parse_extensions(_prompt(f"Input extensions [{default_input_ext}]") or default_input_ext, SUPPORTED_INPUT_EXTENSIONS)
    invalid = sorted(input_exts - SUPPORTED_INPUT_EXTENSIONS)
    if invalid:
        _error(f"Unsupported input extensions: {', '.join(invalid)}")
        return "All assets in folder", input_folder, True, [], input_exts

    recursive = _ask_yes_no("Include subfolders", default=True)
    files = _collect_files(input_folder, input_exts, recursive)
    return "All assets in folder", input_folder, recursive, files, input_exts


def _select_signature_assets(mode, title):
    scope = _choose_asset_scope(title)
    if scope is None:
        return None, None, False, []

    if scope == "files":
        selected_files = _select_files("Select target audio asset files", _audio_dir())
        files = _collect_signature_candidates_from_paths(selected_files, mode)
        return "Selected files only", _common_parent_for_files(selected_files), False, files

    folder = _select_directory("Select target audio asset folder", _audio_dir())
    if not folder:
        return "All assets in folder", None, True, []

    recursive = _ask_yes_no("Include subfolders", default=True)
    files = _collect_signature_candidates(folder, recursive, mode=mode)
    return "All assets in folder", folder, recursive, files


def _run_common_navigation(answer):
    if answer == "S":
        raise globals().get("ExitProgram", SystemExit)()
    if answer == "M":
        raise globals().get("ReturnToMenu", SystemExit)()
    if answer == "B":
        return True
    return False


def _get_converter_settings():
    settings = _load_settings()
    converter = settings.get("audio_converter", {})
    return converter if isinstance(converter, dict) else {}


def _set_converter_setting(key, value):
    settings = _load_settings()
    converter = settings.setdefault("audio_converter", {})
    if not isinstance(converter, dict):
        converter = {}
        settings["audio_converter"] = converter
    converter[key] = str(value or "")
    _save_settings(settings)


def _get_saved_ffmpeg_path():
    converter = _get_converter_settings()
    return str(converter.get("ffmpeg_path", "") or "").strip()


def get_saved_ffmpeg_path_label():
    saved = _get_saved_ffmpeg_path()
    if not saved:
        return "Not configured"

    path = Path(saved)
    try:
        if not _source_is_allowed_ffmpeg_exe(path):
            return f"Ignored outside local ffmpeg: {path}"
    except Exception:
        return f"Ignored invalid path: {path}"

    return str(path) if path.exists() else f"Missing: {path}"


def _is_ffmpeg_exe(path):
    if path is None:
        return False
    path = Path(path)
    if not path.is_file():
        return False
    return path.name.lower() in {"ffmpeg.exe", "ffmpeg"}


def _path_is_under(path, parent):
    try:
        path = Path(path).resolve()
        parent = Path(parent).resolve()
        path.relative_to(parent)
        return True
    except Exception:
        return False


def _direct_child_dirs(folder):
    try:
        return sorted(
            [path for path in Path(folder).iterdir() if path.is_dir()],
            key=lambda path: path.name.lower(),
        )
    except Exception:
        return []


def _ffmpeg_exe_candidates_in_exact_folder(folder):
    """Return FFmpeg executable candidates for exactly one folder. No recursion."""
    folder = Path(folder)
    return [
        folder / "ffmpeg.exe",
        folder / "ffmpeg",
        folder / "bin" / "ffmpeg.exe",
        folder / "bin" / "ffmpeg",
    ]


def _find_ffmpeg_in_folder(folder, include_direct_children=True):
    """Find FFmpeg only in the given folder and optionally its direct children.

    This does not search parent folders, system PATH, C:\ffmpeg, saved external paths,
    or unrestricted recursive descendants.
    """
    folder = Path(folder)
    if not folder.exists() or not folder.is_dir():
        return None

    for candidate in _ffmpeg_exe_candidates_in_exact_folder(folder):
        if _is_ffmpeg_exe(candidate):
            return candidate.resolve()

    if include_direct_children:
        for child in _direct_child_dirs(folder):
            for candidate in _ffmpeg_exe_candidates_in_exact_folder(child):
                if _is_ffmpeg_exe(candidate):
                    return candidate.resolve()

    return None


def _zip_candidates_in_folder(folder):
    """Return ZIP candidates only from the given folder and its direct child folders."""
    folder = Path(folder)
    zip_files = []

    try:
        zip_files.extend(sorted(folder.glob("*.zip"), key=lambda path: path.name.lower()))
    except Exception:
        pass

    for child in _direct_child_dirs(folder):
        try:
            zip_files.extend(sorted(child.glob("*.zip"), key=lambda path: path.name.lower()))
        except Exception:
            pass

    return zip_files


def _zip_path_is_in_allowed_scope(zip_path):
    try:
        root = _ffmpeg_root_dir().resolve()
        zip_path = Path(zip_path).resolve()
    except Exception:
        return False

    if zip_path.parent == root:
        return True

    try:
        return zip_path.parent.parent == root
    except Exception:
        return False


def _source_is_allowed_ffmpeg_folder(path):
    """Allow only local ffmpeg root, its bin folder, or its direct child folder."""
    try:
        path = Path(path).resolve()
        root = _ffmpeg_root_dir().resolve()
    except Exception:
        return False

    if path == root:
        return True
    if path == root / "bin":
        return True
    if path.is_dir() and path.parent == root:
        return True
    if path.is_dir() and path.name.lower() == "bin" and path.parent.parent == root:
        return True
    return False


def _source_is_allowed_ffmpeg_exe(path):
    """Allow explicit ffmpeg.exe only under local ffmpeg root/direct child layouts."""
    try:
        path = Path(path).resolve()
        root = _ffmpeg_root_dir().resolve()
    except Exception:
        return False

    allowed = {candidate.resolve() for candidate in _ffmpeg_exe_candidates_in_exact_folder(root)}
    for child in _direct_child_dirs(root):
        allowed.update(candidate.resolve() for candidate in _ffmpeg_exe_candidates_in_exact_folder(child))

    return path in allowed


def _extract_ffmpeg_zip(zip_path):
    zip_path = Path(zip_path)
    if not zip_path.exists() or not zip_path.is_file() or zip_path.suffix.lower() != ".zip":
        return None
    if not _zip_path_is_in_allowed_scope(zip_path):
        return None

    extract_dir = _ffmpeg_root_dir() / zip_path.stem
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    return _find_ffmpeg_in_folder(extract_dir, include_direct_children=True)


def _find_ffmpeg_from_zip_files(folder):
    folder = Path(folder)
    if not folder.exists() or not folder.is_dir():
        return None

    for zip_path in _zip_candidates_in_folder(folder):
        try:
            found = _extract_ffmpeg_zip(zip_path)
            if found:
                return found
        except Exception:
            continue

    return None


def _resolve_ffmpeg_path(source=None):
    """Resolve FFmpeg only from <this module directory>/ffmpeg.

    Deliberately ignored:
      - parent Release folder/ffmpeg
      - BASE_DIR/ffmpeg
      - C:\ffmpeg or any arbitrary external path
      - saved external ffmpeg path
      - system PATH / shutil.which("ffmpeg")
      - unrestricted recursive search
    """
    root = _ffmpeg_root_dir()

    if source:
        path = Path(source).expanduser()

        if _is_ffmpeg_exe(path):
            return path.resolve() if _source_is_allowed_ffmpeg_exe(path) else None

        if path.is_file() and path.suffix.lower() == ".zip":
            return _extract_ffmpeg_zip(path)

        if path.is_dir():
            if not _source_is_allowed_ffmpeg_folder(path):
                return None

            include_children = Path(path).resolve() == root.resolve()
            found = _find_ffmpeg_in_folder(path, include_direct_children=include_children)
            if found:
                return found
            return _find_ffmpeg_from_zip_files(path) if include_children else None

        return None

    saved = _get_saved_ffmpeg_path()
    if saved:
        saved_path = Path(saved)
        if _is_ffmpeg_exe(saved_path) and _source_is_allowed_ffmpeg_exe(saved_path):
            return saved_path.resolve()

    bundled = _find_ffmpeg_in_folder(root, include_direct_children=True)
    if bundled:
        return bundled

    zipped = _find_ffmpeg_from_zip_files(root)
    if zipped:
        return zipped

    return None


def _open_ffmpeg_download_page():
    global _FFMPEG_DOWNLOAD_OPENED
    if _FFMPEG_DOWNLOAD_OPENED:
        return True

    try:
        webbrowser.open(FFMPEG_DOWNLOAD_URL, new=2)
        _FFMPEG_DOWNLOAD_OPENED = True
        return True
    except Exception:
        return False


def _open_ffmpeg_download_when_missing():
    opened = _open_ffmpeg_download_page()
    if opened:
        _hint(f"Opened FFmpeg download page: {FFMPEG_DOWNLOAD_URL}")
    else:
        _hint(f"Open this page manually: {FFMPEG_DOWNLOAD_URL}")


def _set_ffmpeg_path_menu():
    _enter_converter_screen()
    _title("ANV Audio Converter", "FFmpeg setup")

    _section("Accepted input")
    _item("1)", "ffmpeg.exe path", "Example: C:\\ffmpeg\\bin\\ffmpeg.exe")
    _item("2)", "FFmpeg extracted folder", "The converter searches bin/ffmpeg.exe automatically.")
    _item("3)", "FFmpeg ZIP file", "The ZIP is extracted into ANV/ffmpeg automatically.")
    _item("4)", "Blank input", "Auto-scan only this module's local ffmpeg folder.")

    _section("Current status")
    _kv("Saved FFmpeg", get_saved_ffmpeg_path_label())
    _kv("Allowed FFmpeg folder", _ffmpeg_root_dir())

    raw = _prompt("Path or blank")
    source = _to_path(raw)

    try:
        resolved = _resolve_ffmpeg_path(source)
    except Exception as e:
        _error(f"FFmpeg setup failed: {e}")
        _wait("Press Enter to return to ANV Audio Converter...")
        return

    if not resolved:
        _error("ffmpeg.exe was not found.")
        _hint("Put the FFmpeg ZIP or extracted FFmpeg folder into the allowed local ffmpeg folder, then try again.")
        _open_ffmpeg_download_when_missing()
        _wait("Press Enter to return to ANV Audio Converter...")
        return

    _set_converter_setting("ffmpeg_path", resolved)
    _completed("FFmpeg path has been saved.")
    _kv("ffmpeg", resolved)
    _wait("Press Enter to return to ANV Audio Converter...")


def _check_ffmpeg_status():
    _enter_converter_screen()
    _title("ANV Audio Converter", "FFmpeg status")

    ffmpeg = _resolve_ffmpeg_path()
    _section("Status")
    _kv("Saved FFmpeg", get_saved_ffmpeg_path_label())
    _kv("Detected FFmpeg", ffmpeg if ffmpeg else "Not found")

    if not ffmpeg:
        _error("FFmpeg is not available.")
        _hint("Use FFmpeg Setup, or put an FFmpeg ZIP file into the allowed local ffmpeg folder.")
        _open_ffmpeg_download_when_missing()
        _wait("Press Enter to return to ANV Audio Converter...")
        return

    try:
        proc = subprocess.run(
            [str(ffmpeg), "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        first_line = (proc.stdout or proc.stderr or "").splitlines()[0:1]
        _completed("FFmpeg is available.")
        if first_line:
            _kv("Version", first_line[0])
    except Exception as e:
        _error(f"FFmpeg execution failed: {e}")

    _wait("Press Enter to return to ANV Audio Converter...")


def _show_ffmpeg_folder_guide():
    _enter_converter_screen()
    _title("ANV Audio Converter", "FFmpeg folder guide")

    _section("Recommended layout")
    _kv("Converter module folder", _converter_module_dir())
    _kv("Allowed FFmpeg folder", _ffmpeg_root_dir())
    _item("A)", "Paste the downloaded FFmpeg ZIP into the allowed ffmpeg folder")
    _item("B)", "Or extract FFmpeg there manually")
    _item("C)", "The converter searches only this folder and its direct child folders")

    _section("Examples")
    _item("ZIP", str(_ffmpeg_root_dir() / "ffmpeg-release-full.zip"))
    _item("EXE", str(_ffmpeg_root_dir() / "ffmpeg-master-latest-win64-gpl" / "bin" / "ffmpeg.exe"))

    _wait("Press Enter to return to ANV Audio Converter...")


def _parse_extensions(value, allowed):
    text = str(value or "").strip().lower()
    if not text or text in {"all", "*"}:
        return set(allowed)

    result = set()
    for part in text.replace(";", ",").split(","):
        ext = part.strip().lower().lstrip(".")
        if ext:
            result.add(ext)
    return result


def _ask_yes_no(label, default=False):
    suffix = "Y/n" if default else "y/N"
    raw = _norm(_prompt(f"{label} [{suffix}]"))
    if not raw:
        return bool(default)
    return raw in {"Y", "YES", "1", "TRUE"}


def _collect_files(folder, extensions, recursive):
    folder = Path(folder)
    iterator = folder.rglob("*") if recursive else folder.glob("*")
    files = []
    for path in iterator:
        if not path.is_file():
            continue
        ext = path.suffix.lower().lstrip(".")
        if ext in extensions:
            files.append(path)
    return sorted(files, key=lambda p: str(p).lower())


def _progress(current, total, prefix="Progress"):
    total = max(int(total), 1)
    current = max(0, min(int(current), total))
    width = 32
    filled = int(width * current / total)
    bar = "#" * filled + "-" * (width - filled)
    percent = current / total * 100
    line = f"    {prefix}: [{bar}] {current}/{total} {percent:5.1f}%"
    print("\r" + _blue_text(line.ljust(_terminal_width())), end="", flush=True)
    if current >= total:
        print("\033[0m")
        _set_windows_color("1F")


def _build_output_path(input_file, input_folder, output_folder, output_ext):
    input_file = Path(input_file)
    input_folder = Path(input_folder)
    output_folder = Path(output_folder)

    try:
        relative = input_file.relative_to(input_folder)
        parent = output_folder / relative.parent
    except ValueError:
        parent = output_folder

    parent.mkdir(parents=True, exist_ok=True)
    return parent / f"{input_file.stem}.{output_ext}"


def _codec_args_for(output_ext):
    return OUTPUT_ENCODER_ARGS.get(output_ext, [])


def _write_failure_log(entries):
    if not entries:
        return None

    log_path = _setting_dir() / "anv_audio_converter_failed.log"
    with log_path.open("a", encoding="utf-8") as f:
        f.write("\n")
        f.write(f"# ANV Audio Converter failure log / {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for entry in entries:
            f.write(entry.rstrip() + "\n")
    return log_path


def _run_ffmpeg_convert(ffmpeg, input_file, output_file, output_ext, overwrite):
    cmd = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel", "error",
        "-y" if overwrite else "-n",
        "-i", str(input_file),
    ]
    cmd.extend(_codec_args_for(output_ext))
    cmd.append(str(output_file))

    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )



def _audio_conversion_flow(mode="general"):
    _enter_converter_screen()

    if mode == "anki_mp3":
        _title("ANV Audio Converter", "Category 2: Anki MP3 Converter")
        output_ext = "mp3"
        default_output = _audio_dir() / "converted_mp3"
        default_input_ext = "all"
    else:
        _title("ANV Audio Converter", "Category 1: General Audio Format Converter")
        default_output = _audio_dir() / "converted_audio"
        default_input_ext = "all"

        _section("Output formats")
        _hint(", ".join(sorted(SUPPORTED_OUTPUT_EXTENSIONS)))
        output_ext = _prompt("Output format").strip().lower().lstrip(".")
        if output_ext not in SUPPORTED_OUTPUT_EXTENSIONS:
            _error("Unsupported output format.")
            _wait("Press Enter to return to ANV Audio Converter...")
            return

    ffmpeg = _resolve_ffmpeg_path()
    if not ffmpeg:
        _error("FFmpeg is required for this category.")
        _hint("Use FFmpeg Setup, or put the FFmpeg ZIP into the allowed local ffmpeg folder.")
        _open_ffmpeg_download_when_missing()
        _wait("Press Enter to return to ANV Audio Converter...")
        return

    _section("Input target")
    _hint("Choose whether to process every matching asset in a folder or only selected files.")
    scope, input_folder, recursive, files, input_exts = _select_conversion_assets(default_input_ext=default_input_ext)

    if not input_folder:
        _error("Input target was not selected.")
        _wait("Press Enter to return to ANV Audio Converter...")
        return

    _section("Output")
    _hint("A folder selection window will open for the output directory.")
    _hint(f"Cancel the window and press Enter to use: {default_output}")
    output_folder = _open_directory_dialog("Select output folder", default_output)
    if not output_folder:
        output_folder = default_output
    output_folder.mkdir(parents=True, exist_ok=True)

    overwrite = _ask_yes_no("Overwrite existing output files", default=False)
    delete_original = _ask_yes_no("Delete originals after successful conversion", default=False)

    _enter_converter_screen()
    _title("ANV Audio Converter", "Conversion preview")
    _section("Preview")
    _kv("Category", "Anki MP3" if mode == "anki_mp3" else "General")
    _kv("Scope", scope)
    _kv("FFmpeg", ffmpeg)
    _kv("Input base", input_folder)
    _kv("Output folder", output_folder)
    _kv("Output format", output_ext)
    _kv("Files", len(files))
    if input_exts:
        _kv("Input extensions", ", ".join(sorted(input_exts)))
    _kv("Include subfolders", "Yes" if recursive else "No")
    _kv("Overwrite", "Yes" if overwrite else "No")
    _kv("Delete originals", "Yes" if delete_original else "No")

    if files:
        _section("File preview")
        for index, path in enumerate(files[:10], start=1):
            _item(f"{index})", path.name, str(path.parent))
        if len(files) > 10:
            _hint(f"... and {len(files) - 10} more")

    if not files:
        _error("No matching audio files were found.")
        _wait("Press Enter to return to ANV Audio Converter...")
        return

    if not _confirm("Start conversion"):
        return

    _enter_converter_screen()
    _title("ANV Audio Converter", "Converting audio files")

    success = 0
    skipped = 0
    failures = []

    for index, input_file in enumerate(files, start=1):
        _progress(index - 1, len(files), "Converting")
        output_file = _build_output_path(input_file, input_folder, output_folder, output_ext)

        if input_file.resolve() == output_file.resolve():
            skipped += 1
            _progress(index, len(files), "Converting")
            continue

        if output_file.exists() and not overwrite:
            skipped += 1
            _progress(index, len(files), "Converting")
            continue

        try:
            proc = _run_ffmpeg_convert(ffmpeg, input_file, output_file, output_ext, overwrite)
            if proc.returncode == 0 and output_file.exists():
                success += 1
                if delete_original:
                    try:
                        input_file.unlink()
                    except Exception as e:
                        failures.append(f"DELETE_FAIL\t{input_file}\t{e}")
            else:
                detail = (proc.stderr or proc.stdout or "unknown error").strip().replace("\n", " | ")
                failures.append(f"CONVERT_FAIL\t{input_file}\t{output_file}\t{detail}")
        except Exception as e:
            failures.append(f"ERROR\t{input_file}\t{output_file}\t{e}")

        _progress(index, len(files), "Converting")

    log_path = _write_failure_log(failures)

    _section("Result")
    _kv("Success", success)
    _kv("Skipped", skipped)
    _kv("Failed", len(failures))
    _kv("Output folder", output_folder)
    if log_path:
        _kv("Failure log", log_path)

    _wait("Press Enter to return to ANV Audio Converter...")


def _add_detected_extension_flow():
    _enter_converter_screen()
    _title("ANV Audio Converter", "Category 3: Detect File Type -> Add Extension")

    _section("Important")
    _hint("This category reads audio file headers and adds extensions only to files that have no extension.")
    _hint("It does not re-encode audio data.")

    scope, folder, recursive, files = _select_signature_assets("missing", "Extension target")
    if not folder:
        _error("Target was not selected.")
        _wait("Press Enter to return to ANV Audio Converter...")
        return

    overwrite = _ask_yes_no("Overwrite existing files", default=False)

    _enter_converter_screen()
    _title("ANV Audio Converter", "Detected extension add preview")
    _kv("Scope", scope)
    _kv("Target base", folder)
    _kv("Files", len(files))
    _kv("Include subfolders", "Yes" if recursive else "No")

    if files:
        _section("Preview")
        for index, (path, detected) in enumerate(files[:10], start=1):
            _item(f"{index})", path.name, f"-> {path.name + detected}")
        if len(files) > 10:
            _hint(f"... and {len(files) - 10} more")

    if not files:
        _error("No extensionless audio files were detected.")
        _wait("Press Enter to return to ANV Audio Converter...")
        return

    if not _confirm("Add detected extensions"):
        return

    changed = 0
    skipped = 0
    failures = []

    for index, (path, detected) in enumerate(files, start=1):
        _progress(index - 1, len(files), "Fixing")
        target = path.with_name(path.name + detected)
        if target.exists() and not overwrite:
            skipped += 1
            _progress(index, len(files), "Fixing")
            continue
        try:
            if target.exists() and overwrite:
                target.unlink()
            path.rename(target)
            changed += 1
        except Exception as e:
            failures.append(f"EXT_ADD_FAIL\t{path}\t{target}\t{e}")
        _progress(index, len(files), "Fixing")

    log_path = _write_failure_log(failures)
    _section("Result")
    _kv("Changed", changed)
    _kv("Skipped", skipped)
    _kv("Failed", len(failures))
    if log_path:
        _kv("Failure log", log_path)
    _wait("Press Enter to return to ANV Audio Converter...")


def _change_detected_extension_flow():
    _enter_converter_screen()
    _title("ANV Audio Converter", "Category 4: File Type Detector -> Change Wrong Extension")

    _section("Important")
    _hint("This category reads audio file headers and changes only mismatched existing extensions.")
    _hint("Extensionless files are not touched here. Use Add Missing Extension for those files.")
    _hint("It does not convert codecs. Use FFmpeg conversion for real format conversion.")

    scope, folder, recursive, files = _select_signature_assets("change", "Extension target")
    if not folder:
        _error("Target was not selected.")
        _wait("Press Enter to return to ANV Audio Converter...")
        return

    overwrite = _ask_yes_no("Overwrite existing files", default=False)

    _enter_converter_screen()
    _title("ANV Audio Converter", "Wrong extension change preview")
    _kv("Scope", scope)
    _kv("Target base", folder)
    _kv("Files", len(files))
    _kv("Include subfolders", "Yes" if recursive else "No")

    if files:
        _section("Preview")
        for index, (path, detected) in enumerate(files[:10], start=1):
            _item(f"{index})", path.name, f"-> {path.with_suffix(detected).name}")
        if len(files) > 10:
            _hint(f"... and {len(files) - 10} more")

    if not files:
        _completed("No wrong audio extensions were detected.")
        _wait("Press Enter to return to ANV Audio Converter...")
        return

    if not _confirm("Change wrong extensions"):
        return

    changed = 0
    skipped = 0
    failures = []

    for index, (path, detected) in enumerate(files, start=1):
        _progress(index - 1, len(files), "Changing")
        target = path.with_suffix(detected)
        if target.exists() and not overwrite:
            skipped += 1
            _progress(index, len(files), "Changing")
            continue
        try:
            if target.exists() and overwrite:
                target.unlink()
            path.rename(target)
            changed += 1
        except Exception as e:
            failures.append(f"EXT_CHANGE_FAIL\t{path}\t{target}\t{e}")
        _progress(index, len(files), "Changing")

    log_path = _write_failure_log(failures)
    _section("Result")
    _kv("Changed", changed)
    _kv("Skipped", skipped)
    _kv("Failed", len(failures))
    if log_path:
        _kv("Failure log", log_path)
    _wait("Press Enter to return to ANV Audio Converter...")


def _fix_detected_extension_flow():
    _enter_converter_screen()
    _title("ANV Audio Converter", "Category 5: File Type Detector -> Normalize Extension")

    _section("Important")
    _hint("This category reads audio file headers and fixes mismatched or missing extensions.")
    _hint("It does not convert codecs. Use FFmpeg conversion for real format conversion.")

    scope, folder, recursive, files = _select_signature_assets("normalize", "Extension target")
    if not folder:
        _error("Target was not selected.")
        _wait("Press Enter to return to ANV Audio Converter...")
        return

    overwrite = _ask_yes_no("Overwrite existing files", default=False)

    _enter_converter_screen()
    _title("ANV Audio Converter", "Extension normalization preview")
    _kv("Scope", scope)
    _kv("Target base", folder)
    _kv("Files", len(files))
    _kv("Include subfolders", "Yes" if recursive else "No")

    if files:
        _section("Preview")
        for index, (path, detected) in enumerate(files[:10], start=1):
            target_name = path.name + detected if not path.suffix else path.with_suffix(detected).name
            _item(f"{index})", path.name, f"-> {target_name}")
        if len(files) > 10:
            _hint(f"... and {len(files) - 10} more")

    if not files:
        _completed("No mismatched audio extensions were detected.")
        _wait("Press Enter to return to ANV Audio Converter...")
        return

    if not _confirm("Normalize detected extensions"):
        return

    changed = 0
    skipped = 0
    failures = []

    for index, (path, detected) in enumerate(files, start=1):
        _progress(index - 1, len(files), "Fixing")
        target = path.with_name(path.name + detected) if not path.suffix else path.with_suffix(detected)
        if target.exists() and not overwrite:
            skipped += 1
            _progress(index, len(files), "Fixing")
            continue
        try:
            if target.exists() and overwrite:
                target.unlink()
            path.rename(target)
            changed += 1
        except Exception as e:
            failures.append(f"EXT_FIX_FAIL\t{path}\t{target}\t{e}")
        _progress(index, len(files), "Fixing")

    log_path = _write_failure_log(failures)
    _section("Result")
    _kv("Changed", changed)
    _kv("Skipped", skipped)
    _kv("Failed", len(failures))
    if log_path:
        _kv("Failure log", log_path)
    _wait("Press Enter to return to ANV Audio Converter...")



def _startup_ffmpeg_detection_screen():
    """Show a boot-style FFmpeg detector before the converter main menu opens."""
    _enter_converter_screen()
    _title("ANV Audio Converter", "Startup FFmpeg detector")

    _section("Boot sequence")
    _hint("Press Enter to search for FFmpeg before opening the converter.")
    _hint("Search order: valid saved local path -> local ffmpeg folder -> ZIP files.")
    _kv("FFmpeg folder", _ffmpeg_root_dir())
    _wait("Press Enter to start FFmpeg detection...")

    _enter_converter_screen()
    _title("ANV Audio Converter", "Finding FFmpeg")

    _section("Search order")
    _item("1)", "Saved FFmpeg path", get_saved_ffmpeg_path_label())
    _item("2)", "Local ffmpeg folder only", str(_ffmpeg_root_dir()))
    _item("3)", "FFmpeg ZIP in ANV/ffmpeg", "Auto-extract and search bin/ffmpeg.exe")
    _item("4)", "System PATH", "Disabled")

    _section("Detection")
    _hint("Searching...")
    ffmpeg = None
    try:
        ffmpeg = _resolve_ffmpeg_path()
    except Exception as e:
        _error(f"Detection failed: {e}")

    if ffmpeg:
        _set_converter_setting("ffmpeg_path", ffmpeg)
        _completed("Detected!")
        _kv("ffmpeg", ffmpeg)
        time.sleep(0.8)
        return ffmpeg

    _error("FFmpeg was not detected.")
    _hint("FFmpeg-based conversion will be unavailable until setup is completed.")
    _hint("File type detection and extension fixing can still run without FFmpeg.")
    _open_ffmpeg_download_when_missing()
    _wait("Press Enter to continue without FFmpeg...")
    return None


def launch_anv_audio_converter():
    """Run ANV Audio Converter as a separate launcher screen inside or outside AnkiVoice."""
    try:
        _startup_ffmpeg_detection_screen()

        while True:
            _enter_converter_screen()
            _title("ANV Audio Converter", "External audio conversion program for AnkiVoice")

            _section("Audio Conversion")
            _item("1)", "General Audio Format Converter", "FFmpeg-based conversion between supported audio formats.")
            _item("2)", "Anki MP3 Converter", "Batch-convert audio files to MP3 for Anki media workflows.")

            _section("File Type Detector")
            _item("3)", "Add Missing Extension", "Add extensions only to extensionless files after reading audio headers.")
            _item("4)", "Change Wrong Extension", "Change existing wrong extensions based on actual audio headers.")
            _item("5)", "Normalize Extensions", "Add missing extensions and change wrong extensions in one pass.")

            _section("FFmpeg Setup")
            _item("6)", "Set FFmpeg Path", "Use ffmpeg.exe, an extracted folder, or a ZIP file.")
            _item("7)", "Check FFmpeg Status")
            _item("8)", "Show FFmpeg Folder Guide")

            _section("Navigation")
            _item("B)", "Return to MP3 File Manager")
            _item("M)", "Return to Main Menu")
            _item("S)", "Exit")

            _section("Status")
            _kv("FFmpeg", get_saved_ffmpeg_path_label())
            _kv("Working folder", _ffmpeg_root_dir())

            answer = _norm(_prompt("ANV Audio Converter"))

            if _run_common_navigation(answer):
                return
            if answer == "1":
                _audio_conversion_flow(mode="general")
                continue
            if answer == "2":
                _audio_conversion_flow(mode="anki_mp3")
                continue
            if answer == "3":
                _add_detected_extension_flow()
                continue
            if answer == "4":
                _change_detected_extension_flow()
                continue
            if answer == "5":
                _fix_detected_extension_flow()
                continue
            if answer == "6":
                _set_ffmpeg_path_menu()
                continue
            if answer == "7":
                _check_ffmpeg_status()
                continue
            if answer == "8":
                _show_ffmpeg_folder_guide()
                continue

            _say("1, 2, 3, 4, 5, 6, 7, 8, B, M, S 중에서 입력해주세요.")

    except (globals().get("ReturnToMenu", SystemExit), globals().get("ExitProgram", SystemExit)):
        raise
    except Exception as e:
        try:
            log_only("[ANV AUDIO CONVERTER ERROR]")
            log_only(traceback.format_exc())
        except Exception:
            pass
        _enter_converter_screen()
        _title("ANV Audio Converter", "Unexpected error")
        _error(f"Unexpected error: {e}")
        _wait("Press Enter to return to MP3 File Manager...")
    finally:
        _restore_app_screen()

def manage_audio_files_menu():
    """Override Audio File Manager launcher so extension tools live inside ANV Audio Converter."""
    while True:
        _restore_app_screen()
        _clear_app_screen()
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
        _item("6)", "ANV 오디오 컨버터 실행", "FFmpeg 변환과 확장자 보정 실행")

        _section("이동")
        _item("B)", "메인 메뉴")
        _item("S)", "종료")

        answer = _norm(_prompt("MP3 File Manager"))

        if answer == "S":
            raise globals().get("ExitProgram", SystemExit)()
        if answer in {"B", "M"}:
            return None
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
            launch_anv_audio_converter()
            continue

        _say("1~6, B, S 중에서 입력해주세요.")


if __name__ == "__main__":
    _STANDALONE_MODE = True
    try:
        launch_anv_audio_converter()
    except KeyboardInterrupt:
        print()
        print("Interrupted.")
    except SystemExit:
        pass
