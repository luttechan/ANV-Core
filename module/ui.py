if __name__ == "__main__":
    print()
    print("[ERROR] module/ui.py is not a standalone program.")
    print("Run AnkiVoice.py instead.")
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass
    raise SystemExit(1)

import os
import random
import re
import shutil
import sys

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
        raise RuntimeError("UI 모듈은 단독 실행할 수 없습니다. AnkiVoice.py에서 불러와야 합니다.")


def safe_print(text=""):
    try:
        text = str(text)

        if text.startswith("\033["):
            print(text)
            return

        if "_paint_ui_line" in globals():
            print(_paint_ui_line(text))
            return

        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe_text = str(text).encode(encoding, errors="replace").decode(encoding, errors="replace")

        try:
            if "_paint_ui_line" in globals():
                print(_paint_ui_line(safe_text))
            else:
                print(safe_text)
        except Exception:
            print(safe_text)


def say(msg=""):
    safe_print(msg)

    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(str(msg) + "\n")
    except Exception:
        pass


def log_only(msg=""):
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(str(msg) + "\n")
    except Exception:
        pass


def say_random(lines, **kwargs):
    say(random.choice(lines).format(**kwargs))



DEFAULT_UI_WIDTH = 100
UI_WIDTH = DEFAULT_UI_WIDTH
CLEAR_SCREEN_ON_PAGE_CHANGE = True

CONSOLE_COLS = 108
CONSOLE_LINES = 42
CONSOLE_BUFFER_LINES = CONSOLE_LINES
CONSOLE_WINDOW_PIXEL_WIDTH = 1030
CONSOLE_WINDOW_PIXEL_HEIGHT = 924

def resize_console_window_pixels(width, height):
    if os.name != "nt":
        return

    try:
        import ctypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = kernel32.GetConsoleWindow()

        if not hwnd:
            return

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        rect = RECT()

        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return

        x = rect.left
        y = rect.top
        user32.MoveWindow(hwnd, x, y, int(width), int(height), True)
    except Exception:
        pass


def resize_console_window(cols, lines, buffer_lines=None, ui_width=None):
    global UI_WIDTH

    cols = int(cols)
    lines = int(lines)
    buffer_lines = int(buffer_lines if buffer_lines is not None else lines)
    UI_WIDTH = int(ui_width if ui_width is not None else max(64, cols - 4))

    if os.name != "nt":
        return

    try:
        os.system(f"mode con: cols={cols} lines={lines} >nul")
    except Exception:
        pass

    try:
        import ctypes

        class COORD(ctypes.Structure):
            _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        ctypes.windll.kernel32.SetConsoleScreenBufferSize(
            handle,
            COORD(cols, max(lines, buffer_lines)),
        )
    except Exception:
        pass


def lock_console_window_size():
    if os.name != "nt":
        return

    try:
        import ctypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = kernel32.GetConsoleWindow()

        if not hwnd:
            return

        GWL_STYLE = -16
        WS_SIZEBOX = 0x00040000
        WS_MAXIMIZEBOX = 0x00010000

        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        style = style & ~WS_SIZEBOX & ~WS_MAXIMIZEBOX
        user32.SetWindowLongW(hwnd, GWL_STYLE, style)
    except Exception:
        pass


def setup_console_window():
    resize_console_window(
        CONSOLE_COLS,
        CONSOLE_LINES,
        buffer_lines=CONSOLE_BUFFER_LINES,
        ui_width=DEFAULT_UI_WIDTH,
    )
    resize_console_window_pixels(
        CONSOLE_WINDOW_PIXEL_WIDTH,
        CONSOLE_WINDOW_PIXEL_HEIGHT,
    )
    lock_console_window_size()

    try:
        apply_screen_mode()
    except Exception:
        pass


def scroll_console_to_top():
    if os.name != "nt":
        return

    try:
        import ctypes

        class COORD(ctypes.Structure):
            _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

        class SMALL_RECT(ctypes.Structure):
            _fields_ = [
                ("Left", ctypes.c_short),
                ("Top", ctypes.c_short),
                ("Right", ctypes.c_short),
                ("Bottom", ctypes.c_short),
            ]

        class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
            _fields_ = [
                ("dwSize", COORD),
                ("dwCursorPosition", COORD),
                ("wAttributes", ctypes.c_ushort),
                ("srWindow", SMALL_RECT),
                ("dwMaximumWindowSize", COORD),
            ]

        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        info = CONSOLE_SCREEN_BUFFER_INFO()

        if not ctypes.windll.kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
            return

        height = info.srWindow.Bottom - info.srWindow.Top
        width = info.srWindow.Right - info.srWindow.Left
        rect = SMALL_RECT(0, 0, width, height)
        ctypes.windll.kernel32.SetConsoleWindowInfo(handle, True, ctypes.byref(rect))
    except Exception:
        pass

    try:
        import ctypes

        class COORD(ctypes.Structure):
            _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        ctypes.windll.kernel32.SetConsoleScreenBufferSize(
            handle,
            COORD(CONSOLE_COLS, max(CONSOLE_BUFFER_LINES, CONSOLE_LINES)),
        )
    except Exception:
        pass



def ui_write(text=""):
    try:
        safe_print(_paint_ui_line(text))
    except Exception:
        safe_print(text)


def ui_write_inline(text=""):
    try:
        sys.stdout.write(str(text))
        sys.stdout.flush()
    except Exception:
        pass


def _screen_mode_ansi_prefix(mode=None):
    return ""


def _console_size():
    try:
        size = shutil.get_terminal_size((CONSOLE_COLS, CONSOLE_LINES))
        return max(64, size.columns), max(10, size.lines)
    except Exception:
        return CONSOLE_COLS, CONSOLE_LINES


def _paint_ui_line(text=""):
    text = str(text)
    return _screen_mode_ansi_prefix() + text


def _paint_console_background():
    return


def ui_clear_screen():
    if not CLEAR_SCREEN_ON_PAGE_CHANGE:
        return

    try:
        apply_screen_mode()
    except Exception:
        pass

    try:
        if os.name == "nt":
            os.system("cls")
        elif os.environ.get("TERM"):
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()
        else:
            print("\n" * 90)
    except Exception:
        print("\n" * 90)

    try:
        apply_screen_mode()
    except Exception:
        pass


def _terminal_width():
    try:
        return max(64, min(UI_WIDTH, shutil.get_terminal_size((UI_WIDTH, 24)).columns - 2))
    except Exception:
        return UI_WIDTH


def _ui_inner_width():
    return max(24, _terminal_width() - 4)


def _char_width(ch):
    import unicodedata

    if unicodedata.combining(ch):
        return 0

    code = ord(ch)

    if code >= 0x1F000:
        return 2

    if unicodedata.east_asian_width(ch) in {"F", "W"}:
        return 2

    return 1


def _display_width(text):
    return sum(_char_width(ch) for ch in str(text))


def _fit_text(text, width=None, align="left"):
    width = width or _ui_inner_width()
    text = str(text)
    out = ""
    used = 0

    for ch in text:
        ch_width = _char_width(ch)

        if used + ch_width > width:
            break

        out += ch
        used += ch_width

    if out != text and width >= 3:
        while out and _display_width(out + "...") > width:
            out = out[:-1]
        out = out.rstrip() + "..."
        used = _display_width(out)

    pad = max(0, width - used)

    if align == "center":
        left = pad // 2
        right = pad - left
        return " " * left + out + " " * right

    if align == "right":
        return " " * pad + out

    return out + " " * pad


def _wrap_display(text, width=None):
    width = width or _ui_inner_width()
    text = str(text)

    if not text:
        return [""]

    result = []

    for raw_line in text.splitlines() or [text]:
        if not raw_line:
            result.append("")
            continue

        words = raw_line.split(" ")
        current = ""

        for word in words:
            candidate = word if not current else current + " " + word

            if _display_width(candidate) <= width:
                current = candidate
                continue

            if current:
                result.append(current)
                current = ""

            chunk = ""
            for ch in word:
                if _display_width(chunk + ch) > width:
                    result.append(chunk)
                    chunk = ch
                else:
                    chunk += ch
            current = chunk

        result.append(current)

    return result


def _line(width=None, char="-"):
    width = width or (_terminal_width() - 4)
    return char * max(8, width)


def ui_line(char="-"):
    ui_write("  " + _line(char=char))


def ui_blank():
    ui_write("")


def ui_gap(lines=1):
    for _ in range(max(1, int(lines))):
        ui_write("")


def ui_title(title, subtitle=None):
    width = _terminal_width() - 4
    ui_gap(1)
    ui_write("  " + _line(width, "="))
    ui_write("  " + _fit_text(str(title), width, align="center").rstrip())

    if subtitle:
        ui_gap(1)
        for line in _wrap_display(subtitle, width):
            ui_write("  " + _fit_text(line, width, align="center").rstrip())

    ui_write("  " + _line(width, "="))
    ui_gap(1)



def ui_section(title):
    # 섹션 제목
    width = _terminal_width() - 4
    title = str(title).strip()
    label = f"[ {title} ]"
    remain = max(8, width - _display_width(label) - 1)

    ui_gap(1)
    ui_write("  " + label + " " + "-" * remain)


def ui_card(title, lines=None):
    # 안내 카드
    lines = lines or []
    width = _terminal_width() - 8

    ui_gap(1)
    ui_write(f"  {title}")
    ui_write("  " + _line(_terminal_width() - 4, "-"))

    for line in lines:
        for wrapped in _wrap_display(line, width):
            ui_write("    " + wrapped if wrapped else "")


def ui_notice(title, lines=None):
    # 고지사항 출력
    lines = lines or []
    width = _terminal_width() - 8

    ui_gap(1)
    ui_write("  " + _line(_terminal_width() - 4, "="))
    ui_write("  " + str(title))
    ui_write("  " + _line(_terminal_width() - 4, "-"))

    previous_blank = False
    for line in lines:
        blank = not str(line).strip()
        if blank:
            if not previous_blank:
                ui_gap(1)
            previous_blank = True
            continue

        previous_blank = False
        for wrapped in _wrap_display(line, width):
            ui_write("    " + wrapped)

    ui_write("  " + _line(_terminal_width() - 4, "="))

def _ui_key(key):
    key = str(key).strip()

    if key.endswith(")") and len(key) <= 4:
        return key[:-1]

    if key.lower() == "enter":
        return "Enter"

    return key



def ui_item(key, label, desc=""):
    # 메뉴 항목
    key_text = _ui_key(key)
    label = str(label)
    key_part = f"[{key_text}]" if key_text else " - "
    ui_write(f"  {key_part:<8} {label}")

    if desc:
        for line in _wrap_display(desc, _terminal_width() - 13):
            ui_write("           " + line)


def ui_kv(key, value, desc=""):
    key = str(key)
    value = str(value)
    key_width = 13
    ui_write(f"  {key:<{key_width}} : {value}")

    if desc:
        for line in _wrap_display(desc, _terminal_width() - 20):
            ui_write(" " * 17 + line)


def ui_hint(text):
    for line in _wrap_display(text, _terminal_width() - 10):
        ui_write("    - " + line)

def ui_prompt(text):
    try:
        apply_screen_mode()
        prefix = _screen_mode_ansi_prefix()
    except Exception:
        prefix = ""

    return input(f"\n{prefix}  > {text}: ")



def ui_completed(message="Completed."):
    ui_gap(1)
    ui_write("  [OK] " + (str(message) if message else ""))


def ui_error(message="Error."):
    ui_gap(1)
    ui_write("  [ERROR]")

    if message:
        for line in _wrap_display(message, _terminal_width() - 14):
            ui_write("    " + line)


def ui_processing(message):
    ui_gap(1)
    ui_write("  [PROCESSING]")
    for line in _wrap_display(message, _terminal_width() - 8):
        ui_write("    " + line)

def format_error_message(message):
    return f"[ERROR] {message}"


def normalize_menu_answer(answer_raw):
    # 전각 숫자, 괄호, ~번 표기를 정규화한다
    import unicodedata

    value = unicodedata.normalize("NFKC", str(answer_raw or "").strip())
    value = re.sub(r"\s+", "", value)

    if value.startswith("[") and value.endswith("]") and len(value) >= 3:
        value = value[1:-1]

    if value.endswith("번"):
        value = value[:-1]

    if len(value) >= 2 and value[-1] in {")", ".", ":"}:
        value = value[:-1]

    return value.upper()


def wait_exit():
    try:
        input("\n종료하려면 Enter를 눌러주세요...")
    except EOFError:
        pass


def wait_return_to_menu():
    try:
        input("\n이전 화면으로 돌아가려면 Enter를 눌러주세요...")
    except EOFError:
        return
    ui_clear_screen()


def wait_back_to_previous(message="이전 화면으로 돌아가려면 Enter를 눌러주세요..."):
    try:
        input(f"\n{message}")
    except EOFError:
        return
    ui_clear_screen()



def ask_action(prompt="계속 진행할까요?", allow_voice_settings=False, language_mode=None):
    while True:
        ui_section("확인")
        ui_item("Enter", "계속 진행")
        ui_item("R)", "계속 진행")

        if allow_voice_settings and language_mode in {"en", "zh"}:
            ui_item("A)", "기본 악센트 변경", "설정 후 돌아옵니다")

        ui_item("B)", "이전 화면")
        ui_item("M)", "메인 메뉴")
        ui_item("S)", "종료")

        answer_raw = ui_prompt(prompt).strip()

        if handle_easter_egg_command(answer_raw):
            continue

        answer = normalize_menu_answer(answer_raw)

        if answer in {"", "R"}:
            say("계속 진행합니다.")
            return "continue"

        if allow_voice_settings and language_mode in {"en", "zh"} and answer == "A":
            return "voice_settings"

        if answer == "B":
            say("이전 화면으로 돌아갑니다.")
            raise BackScreen

        if answer == "M":
            say("메인 메뉴로 돌아갑니다.")
            raise ReturnToMenu

        if answer == "S":
            say("프로그램을 종료합니다.")
            raise ExitProgram

        if allow_voice_settings and language_mode in {"en", "zh"}:
            say("Enter, R, A, B, M, S 중에서 입력해주세요.")
        else:
            say("Enter, R, B, M, S 중에서 입력해주세요.")

def ask_int(prompt, min_value=None, max_value=None, default=None):
    while True:
        if default is None:
            answer = input(f"{prompt} > ").strip()
        else:
            answer = input(f"{prompt} [기본값 {default}] > ").strip()

        if not answer and default is not None:
            return default

        if answer.upper() == "B":
            raise BackScreen

        if answer.upper() == "M":
            raise ReturnToMenu

        if answer.upper() == "S":
            raise ExitProgram

        if not answer.isdigit():
            say("숫자로 입력해주세요.")
            continue

        value = int(answer)

        if min_value is not None and value < min_value:
            say(f"{min_value} 이상으로 입력해주세요.")
            continue

        if max_value is not None and value > max_value:
            say(f"{max_value} 이하로 입력해주세요.")
            continue

        return value



def show_navigation_hint(back_label="이전 화면"):
    ui_section("이동")

    # back_label이 메인 메뉴면 [M]만 표시
    normalized_back_label = normalize_menu_answer(back_label)
    is_back_to_main_menu = normalized_back_label in {"메인메뉴", "메인"}

    if is_back_to_main_menu:
        ui_item("M)", "메인 메뉴")
    else:
        ui_item("B)", back_label)
        ui_item("M)", "메인 메뉴")

    ui_item("S)", "종료")


def read_menu_answer(prompt, valid_answers, allow_back=True, allow_main=True, allow_exit=True):
    valid_answers = {normalize_menu_answer(item) for item in valid_answers}

    while True:
        answer_raw = ui_prompt(prompt).strip()

        if handle_easter_egg_command(answer_raw):
            return None

        answer = normalize_menu_answer(answer_raw)

        if answer in valid_answers:
            return answer

        if allow_back and answer == "B":
            raise BackScreen

        if allow_main and answer == "M":
            raise ReturnToMenu

        if allow_exit and answer == "S":
            raise ExitProgram

        if answer == "0" and "0" in valid_answers:
            return "0"

        say("목록에 있는 번호/문자만 입력해주세요.")




__all__ = [
    "CONSOLE_WINDOW_PIXEL_HEIGHT",
    "CONSOLE_WINDOW_PIXEL_WIDTH",
    "CONSOLE_BUFFER_LINES",
    "CONSOLE_LINES",
    "CONSOLE_COLS",
    "CLEAR_SCREEN_ON_PAGE_CHANGE",
    "UI_WIDTH",
    "DEFAULT_UI_WIDTH",
    "safe_print",
    "say",
    "log_only",
    "say_random",
    "resize_console_window_pixels",
    "resize_console_window",
    "lock_console_window_size",
    "setup_console_window",
    "scroll_console_to_top",
    "ui_write",
    "ui_write_inline",
    "_screen_mode_ansi_prefix",
    "_console_size",
    "_paint_ui_line",
    "_paint_console_background",
    "ui_clear_screen",
    "_terminal_width",
    "_ui_inner_width",
    "_char_width",
    "_display_width",
    "_fit_text",
    "_wrap_display",
    "_line",
    "ui_line",
    "ui_blank",
    "ui_gap",
    "ui_title",
    "ui_section",
    "ui_card",
    "ui_notice",
    "_ui_key",
    "ui_item",
    "ui_kv",
    "ui_hint",
    "ui_prompt",
    "ui_completed",
    "ui_error",
    "ui_processing",
    "format_error_message",
    "normalize_menu_answer",
    "wait_exit",
    "wait_return_to_menu",
    "wait_back_to_previous",
    "ask_action",
    "ask_int",
    "show_navigation_hint",
    "read_menu_answer",
]
