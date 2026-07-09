# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0

# AnkiVoice
# Developed by Lutte Laurent with assistance from ChatGPT.
# Copyright (c) 2026 Lutte Laurent

# This module is loaded by AnkiVoice.py and receives the main runtime
# through bind_runtime(). It is not intended to be executed directly.

RUNTIME = None

LEGAL_NOTICE_PAGE_SIZE = 14
LEGAL_NOTICE_PAGE_BREAK = "__PAGE_BREAK__"
LEGAL_NOTICE_REQUIRED_PAGE_SECONDS = 0.0


__all__ = [
    "_legal_notice_content_width",
    "_legal_notice_page_height",
    "_legal_notice_line_height",
    "_scroll_notice_view_to_top",
    "get_legal_notice_lines",
    "get_legal_notice_title",
    "get_legal_notice_subtitle",
    "paginate_legal_notice",
    "normalize_notice_key",
    "read_notice_input",
    "read_notice_command",
    "read_notice_command_text_box",
    "read_notice_key",
    "switch_legal_notice_language",
    "keep_page_index_after_language_switch",
    "draw_legal_notice_page",
    "draw_required_legal_notice_scrollable",
    "show_required_legal_notice_scrollable",
    "get_patch_note_lines",
    "get_patch_note_title",
    "get_creator_note_language_order",
    "get_creator_note_language_labels",
    "switch_creator_note_language",
    "get_creator_note_lines",
    "get_creator_note_title",
    "keep_creator_note_page_after_language_switch",
    "show_creator_note",
    "show_patch_notes",
    "show_legal_notice",
    "show_startup_notice_once"
]


def bind_runtime(runtime):
    global RUNTIME
    RUNTIME = runtime
    for key, value in runtime.__dict__.items():
        if not key.startswith("__"):
            globals()[key] = value


def _legal_notice_content_width():
    try:
        return max(40, _terminal_width() - 10)
    except Exception:
        return 70


def _legal_notice_page_height(default=LEGAL_NOTICE_PAGE_SIZE):
    try:
        size = shutil.get_terminal_size((100, 30))
        return max(8, min(int(default), int(size.lines) - 13))
    except Exception:
        return int(default)


def _legal_notice_line_height(line):
    text = str(line or "")

    if not text:
        return 1

    try:
        return max(1, len(_wrap_display(text, _legal_notice_content_width())))
    except Exception:
        width = _legal_notice_content_width()
        return max(1, (len(text) // max(1, width)) + 1)


def _scroll_notice_view_to_top():
    try:
        scroll_console_to_top()
    except Exception:
        pass

def get_legal_notice_lines(language_code):
    return LEGAL_NOTICE_TEXTS.get(language_code, LEGAL_NOTICE_TEXTS["ko"])


def get_legal_notice_title(language_code):
    if language_code == "en":
        return "AnkiVoice Terms of Service"

    return "AnkiVoice 이용약관"


def get_legal_notice_subtitle(language_code, page_index, total_pages):
    label = LEGAL_NOTICE_LANGUAGE_LABELS.get(language_code, language_code)
    numbered_total = max(0, total_pages - 1)

    if language_code == "en":
        if page_index == 0:
            return f"{label} · Overview / {total_pages} pages"
        return f"{label} · Section {page_index} / {numbered_total}"

    if page_index == 0:
        return f"{label} · 개요 / 총 {total_pages}쪽"

    return f"{label} · {page_index}번 / {numbered_total}번"


def paginate_legal_notice(lines, page_size=LEGAL_NOTICE_PAGE_SIZE):
    pages = []
    current = []
    current_height = 0
    max_height = _legal_notice_page_height(page_size)

    def flush_current():
        nonlocal current, current_height
        while current and not str(current[0]).strip():
            current.pop(0)
        while current and not str(current[-1]).strip():
            current.pop()
        if current:
            pages.append(current)
        current = []
        current_height = 0

    for line in lines:
        if str(line).strip() == LEGAL_NOTICE_PAGE_BREAK:
            flush_current()
            continue

        line_height = _legal_notice_line_height(line)

        if current and current_height + line_height > max_height:
            flush_current()

        current.append(line)
        current_height += line_height

    flush_current()

    if not pages:
        pages.append([])

    return pages


def normalize_notice_key(value):
    value = normalize_menu_answer(value)

    aliases = {
        "": "ENTER",
        "ENTER": "ENTER",
        "RETURN": "ENTER",
        "A": "A",
        "AGREE": "A",
        "동의": "A",
        "S": "S",
        "Q": "S",
        "종료": "S",
        "B": "BACK",
        "BACK": "BACK",
        "뒤로": "BACK",
        "M": "MAIN",
        "MAIN": "MAIN",
        "메인": "MAIN",
        "메인메뉴": "MAIN",
        "F8": "F8",
        "LANG": "F8",
        "LANGUAGE": "F8",
        "언어": "F8",
        "LEFT": "LEFT",
        "L": "LEFT",
        "<": "LEFT",
        "←": "LEFT",
        "이전쪽": "LEFT",
        "이전페이지": "LEFT",
        "RIGHT": "RIGHT",
        "R": "RIGHT",
        ">": "RIGHT",
        "→": "RIGHT",
        "다음쪽": "RIGHT",
        "다음페이지": "RIGHT",
        "PGDN": "RIGHT",
        "PAGEDOWN": "RIGHT",
        "PAGE DOWN": "RIGHT",
        "NEXT": "RIGHT",
        "다음": "RIGHT",
        "PGUP": "LEFT",
        "PAGEUP": "LEFT",
        "PAGE UP": "LEFT",
        "PREV": "LEFT",
        "PREVIOUS": "LEFT",
        "이전": "LEFT",
    }

    return aliases.get(value, value)


def read_notice_input(prompt="입력", show_top=False):
    try:
        if show_top:
            safe_print(f"\n  > {prompt}: ")
            scroll_console_to_top()
            return input().strip()

        return input(f"\n  > {prompt}: ").strip()
    except EOFError:
        return ""


def read_notice_command(prompt="키를 눌러주세요"):
    ui_write("")
    ui_write(f"  > {prompt}")

    if not sys.stdin.isatty():
        try:
            raw = input("  > 입력: ").strip()
        except EOFError:
            return "ENTER", ""
        key = normalize_notice_key(raw)
        if key in {"LEFT", "RIGHT", "F8", "ENTER", "BACK", "MAIN", "S"}:
            return key, ""
        return "TEXT", raw

    if os.name == "nt":
        try:
            import msvcrt

            buffer = []

            while True:
                ch = msvcrt.getwch()

                if ch in ("\x00", "\xe0"):
                    code = ord(msvcrt.getwch())
                    key_map = {
                        66: "F8",
                        73: "LEFT",
                        75: "LEFT",
                        77: "RIGHT",
                        81: "RIGHT",
                    }
                    key = key_map.get(code, "")
                    if key:
                        ui_write("")
                        return key, ""
                    continue

                if ch in ("\r", "\n"):
                    ui_write("")
                    raw = "".join(buffer).strip()
                    if not raw:
                        return "ENTER", ""
                    key = normalize_notice_key(raw)
                    if key in {"LEFT", "RIGHT", "F8", "ENTER", "BACK", "MAIN", "S"}:
                        return key, ""
                    return "TEXT", raw

                if ch == "\x08":
                    if buffer:
                        buffer.pop()
                        ui_write_inline("\b \b")
                    continue

                if ch == "\x03":
                    raise KeyboardInterrupt

                buffer.append(ch)
                ui_write_inline(ch)

        except Exception:
            try:
                raw = input("  > 입력: ").strip()
            except EOFError:
                return "ENTER", ""
            key = normalize_notice_key(raw)
            if key in {"LEFT", "RIGHT", "F8", "ENTER", "BACK", "MAIN", "S"}:
                return key, ""
            return "TEXT", raw

    try:
        import termios
        import tty
        import select

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)

        try:
            tty.setraw(fd)
            buffer = []

            while True:
                ch = sys.stdin.read(1)

                if ch == "\x1b":
                    seq = ch
                    while True:
                        ready, _, _ = select.select([sys.stdin], [], [], 0.04)
                        if not ready:
                            break
                        seq += sys.stdin.read(1)
                        if seq.endswith("~") or seq in {"\x1b[D", "\x1b[C"} or len(seq) >= 8:
                            break

                    seq_map = {
                        "\x1b[D": "LEFT",
                        "\x1b[C": "RIGHT",
                        "\x1b[5~": "LEFT",
                        "\x1b[6~": "RIGHT",
                        "\x1b[19~": "F8",
                    }
                    key = seq_map.get(seq, "")
                    if key:
                        safe_print("")
                        return key, ""
                    continue

                if ch in ("\r", "\n"):
                    safe_print("")
                    raw = "".join(buffer).strip()
                    if not raw:
                        return "ENTER", ""
                    key = normalize_notice_key(raw)
                    if key in {"LEFT", "RIGHT", "F8", "ENTER", "BACK", "MAIN", "S"}:
                        return key, ""
                    return "TEXT", raw

                if ch in ("\x7f", "\b"):
                    if buffer:
                        buffer.pop()
                        ui_write_inline("\b \b")
                    continue

                if ch == "\x03":
                    raise KeyboardInterrupt

                buffer.append(ch)
                ui_write_inline(ch)

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    except Exception:
        try:
            raw = input("  > 입력: ").strip()
        except EOFError:
            return "ENTER", ""
        key = normalize_notice_key(raw)
        if key in {"LEFT", "RIGHT", "F8", "ENTER", "BACK", "MAIN", "S"}:
            return key, ""
        return "TEXT", raw


def read_notice_command_text_box(prompt="입력", placeholder=""):
    width = _terminal_width() - 4
    inner_width = max(24, width - 4)
    label = str(prompt or "입력")

    ui_gap(1)
    ui_write("  +" + "-" * max(8, width - 2) + "+")
    ui_write("  | " + _fit_text(label, inner_width) + " |")

    if placeholder:
        ui_write("  | " + _fit_text(placeholder, inner_width) + " |")

    ui_write("  +" + "-" * max(8, width - 2) + "+")

    if not sys.stdin.isatty():
        try:
            raw = input("  | > ").strip()
        except EOFError:
            return "ENTER", ""
        ui_write("  +" + "-" * max(8, width - 2) + "+")
        key = normalize_notice_key(raw)
        if key in {"LEFT", "RIGHT", "F8", "ENTER", "BACK", "MAIN", "S"}:
            return key, ""
        return "TEXT", raw

    if os.name == "nt":
        try:
            import msvcrt

            buffer = []
            prefix = "  | > "
            ui_write_inline(prefix)

            while True:
                ch = msvcrt.getwch()

                if ch in ("\x00", "\xe0"):
                    code = ord(msvcrt.getwch())
                    key_map = {
                        66: "F8",
                        73: "LEFT",
                        75: "LEFT",
                        77: "RIGHT",
                        81: "RIGHT",
                    }
                    key = key_map.get(code, "")
                    if key:
                        raw = "".join(buffer)
                        used = _display_width("> " + raw)
                        pad = max(0, inner_width - used)
                        ui_write_inline(" " * pad + " |\n")
                        ui_write("  +" + "-" * max(8, width - 2) + "+")
                        return key, ""
                    continue

                if ch in ("\r", "\n"):
                    raw = "".join(buffer).strip()
                    used = _display_width("> " + raw)
                    pad = max(0, inner_width - used)
                    ui_write_inline(" " * pad + " |\n")
                    ui_write("  +" + "-" * max(8, width - 2) + "+")

                    if not raw:
                        return "ENTER", ""

                    key = normalize_notice_key(raw)
                    if key in {"LEFT", "RIGHT", "F8", "ENTER", "BACK", "MAIN", "S"}:
                        return key, ""
                    return "TEXT", raw

                if ch == "\x08":
                    if buffer:
                        buffer.pop()
                        ui_write_inline("\b \b")
                    continue

                if ch == "\x03":
                    raise KeyboardInterrupt

                if _display_width("> " + "".join(buffer) + ch) < inner_width:
                    buffer.append(ch)
                    ui_write_inline(ch)

        except Exception:
            pass

    try:
        raw = input("  | > ").strip()
    except EOFError:
        return "ENTER", ""

    ui_write("  +" + "-" * max(8, width - 2) + "+")
    key = normalize_notice_key(raw)
    if key in {"LEFT", "RIGHT", "F8", "ENTER", "BACK", "MAIN", "S"}:
        return key, ""
    return "TEXT", raw


def read_notice_key(prompt="키를 눌러주세요"):
    key, text = read_notice_command(prompt)
    if key == "TEXT":
        return normalize_notice_key(text)
    return key

def switch_legal_notice_language(language_code):
    order = LEGAL_NOTICE_LANGUAGE_ORDER

    if language_code not in order:
        return "ko"

    return order[(order.index(language_code) + 1) % len(order)]


def keep_page_index_after_language_switch(page_index, lines_getter, language_code):
    lines = lines_getter(language_code)
    total_pages = len(paginate_legal_notice(lines))
    return max(0, min(int(page_index), max(0, total_pages - 1)))


def draw_legal_notice_page(
    language_code,
    page_index,
    require_accept=False,
    accept_ready=False,
    page_elapsed=0.0,
):
    lines = get_legal_notice_lines(language_code)
    pages = paginate_legal_notice(lines)
    total_pages = len(pages)
    page_index = max(0, min(page_index, total_pages - 1))

    ui_clear_screen()
    ui_title(
        get_legal_notice_title(language_code),
        get_legal_notice_subtitle(language_code, page_index, total_pages),
    )
    ui_notice(get_legal_notice_title(language_code), pages[page_index])

    ui_section("조작")

    if require_accept:
        remaining = max(0.0, LEGAL_NOTICE_REQUIRED_PAGE_SECONDS - float(page_elapsed or 0.0))

        if page_index < total_pages - 1:
            if remaining > 0:
                ui_item("→", f"다음 페이지 ({remaining:.1f}초 후)")
            else:
                ui_item("→", "다음 페이지")
        else:
            ui_item("→", "마지막 페이지")

        ui_item("←", "이전 페이지")
        ui_item("F8", "언어 전환", "한국어 / English")

        if accept_ready:
            accept_text = LEGAL_NOTICE_ACCEPT_TEXTS.get(language_code, LEGAL_NOTICE_ACCEPT_TEXTS["ko"])
            ui_item("입력", accept_text, "아래 입력칸에 그대로 입력해야 시작할 수 있습니다.")
        else:
            if remaining > 0:
                ui_item("대기", f"이 페이지를 {remaining:.1f}초 더 확인하세요.")
            else:
                ui_item("안내", "마지막 페이지까지 확인하면 동의 입력이 열립니다.")
        return page_index, total_pages

    ui_item("→", "다음 페이지")
    ui_item("←", "이전 페이지")
    ui_item("F8", "언어 전환", "한국어 / English")
    ui_item("Enter", "이전 화면")
    ui_item("M", "메인 메뉴")
    ui_item("S", "종료")

    return page_index, total_pages

def draw_required_legal_notice_scrollable(language_code):
    label = LEGAL_NOTICE_LANGUAGE_LABELS.get(language_code, language_code)
    accept_text = LEGAL_NOTICE_ACCEPT_TEXTS.get(language_code, LEGAL_NOTICE_ACCEPT_TEXTS["ko"])

    ui_clear_screen()
    ui_title(get_legal_notice_title(language_code), f"{label} · 전체 약관")

    ui_section("동의")
    ui_item("입력", accept_text, "위 문구를 그대로 입력해야 시작할 수 있습니다.")
    ui_hint("약관은 페이지 단위로 표시됩니다.")

    ui_notice(get_legal_notice_title(language_code), get_legal_notice_lines(language_code))

    ui_section("동의")
    ui_item("입력", accept_text, "위 문구를 그대로 입력해야 시작할 수 있습니다.")

    if language_code == "en":
        ui_hint("Type 'ko' to switch to Korean.")
    else:
        ui_hint("영어로 보려면 english 또는 en을 입력하세요.")


def show_required_legal_notice_scrollable():
    language_code = "ko"
    page_index = 0
    page_entered_at = time.monotonic()

    while True:
        lines = get_legal_notice_lines(language_code)
        total_pages = len(paginate_legal_notice(lines))
        page_index = max(0, min(page_index, total_pages - 1))
        page_elapsed = time.monotonic() - page_entered_at
        current_page_ready = page_elapsed >= LEGAL_NOTICE_REQUIRED_PAGE_SECONDS
        accept_ready = current_page_ready and page_index == total_pages - 1

        page_index, total_pages = draw_legal_notice_page(
            language_code,
            page_index,
            require_accept=True,
            accept_ready=accept_ready,
            page_elapsed=page_elapsed,
        )
        _scroll_notice_view_to_top()

        accept_text = LEGAL_NOTICE_ACCEPT_TEXTS.get(language_code, LEGAL_NOTICE_ACCEPT_TEXTS["ko"])

        if accept_ready:
            prompt_label = "동의 문구 입력" if language_code == "ko" else "Agreement input"
            placeholder = accept_text
        else:
            prompt_label = "페이지 조작" if language_code == "ko" else "Page control"
            placeholder = "←/→ 페이지 이동 · F8 언어 전환" if language_code == "ko" else "←/→ page · F8 language"

        key, raw = read_notice_command_text_box(prompt_label, placeholder)

        if key == "F8":
            language_code = switch_legal_notice_language(language_code)
            page_index = keep_page_index_after_language_switch(
                page_index,
                get_legal_notice_lines,
                language_code,
            )
            page_entered_at = time.monotonic()
            continue

        if key == "RIGHT":
            elapsed = time.monotonic() - page_entered_at
            if elapsed < LEGAL_NOTICE_REQUIRED_PAGE_SECONDS:
                remaining = max(0.0, LEGAL_NOTICE_REQUIRED_PAGE_SECONDS - elapsed)
                say(f"이 페이지를 {remaining:.1f}초 더 확인한 뒤 넘어갈 수 있습니다.")
                time.sleep(0.8)
                continue

            if page_index < total_pages - 1:
                page_index += 1
                page_entered_at = time.monotonic()
            continue

        if key == "LEFT":
            if page_index > 0:
                page_index -= 1
                page_entered_at = time.monotonic()
            continue

        if key == "TEXT":
            if not accept_ready:
                say("마지막 페이지까지 확인한 뒤 동의할 수 있습니다.")
                time.sleep(0.8)
                continue

            if language_code == "en":
                accepted = raw.strip().lower() == accept_text
            else:
                accepted = raw.strip() == accept_text

            if accepted:
                return "accepted"

        if accept_ready:
            say(f"시작하려면 '{accept_text}'를 정확히 입력해야 합니다.")
        else:
            say("←, →, F8 중에서 입력해주세요.")
        time.sleep(0.8)


def get_patch_note_lines(language_code):
    return PATCH_NOTE_TEXTS.get(language_code, PATCH_NOTE_TEXTS["ko"])


def get_patch_note_title(language_code):
    if language_code == "en":
        return "AnkiVoice Patch Notes"

    return "AnkiVoice 패치 노트"




def get_creator_note_language_order():
    order = globals().get("CREATOR_NOTE_LANGUAGE_ORDER", ["ko", "ja"])

    if not isinstance(order, (list, tuple)) or not order:
        return ["ko", "ja"]

    normalized = []

    for language_code in order:
        code = str(language_code or "").strip().lower()

        if code in {"ko", "ja"} and code not in normalized:
            normalized.append(code)

    return normalized or ["ko", "ja"]


def get_creator_note_language_labels():
    labels = globals().get("CREATOR_NOTE_LANGUAGE_LABELS", {})

    if not isinstance(labels, dict):
        labels = {}

    result = {
        "ko": "한국어",
        "ja": "日本語",
    }
    result.update({str(key): str(value) for key, value in labels.items()})
    return result


def switch_creator_note_language(language_code):
    order = get_creator_note_language_order()

    if language_code not in order:
        return order[0]

    return order[(order.index(language_code) + 1) % len(order)]


def get_creator_note_lines(language_code):
    language_code = str(language_code or "ko").strip().lower()
    texts = globals().get("CREATOR_NOTE_TEXTS", {})

    if not isinstance(texts, dict):
        return []

    if language_code in texts:
        return texts[language_code]

    for fallback_code in get_creator_note_language_order():
        if fallback_code in texts:
            return texts[fallback_code]

    return []


def get_creator_note_title(language_code):
    language_code = str(language_code or "ko").strip().lower()

    if language_code == "ja":
        return "開発者より"

    return "제작자의 말"


def keep_creator_note_page_after_language_switch(page_index, language_code):
    lines = get_creator_note_lines(language_code)
    total_pages = len(paginate_legal_notice(lines))
    return max(0, min(int(page_index), max(0, total_pages - 1)))


def show_creator_note(clear=True):
    language_code = "ko"
    page_index = 0

    while True:
        lines = get_creator_note_lines(language_code)
        pages = paginate_legal_notice(lines)
        total_pages = len(pages)
        page_index = max(0, min(page_index, total_pages - 1))
        labels = get_creator_note_language_labels()
        label = labels.get(language_code, language_code)

        ui_clear_screen()
        ui_title(
            get_creator_note_title(language_code),
            f"{label} · {page_index + 1} / {total_pages}",
        )
        ui_notice(get_creator_note_title(language_code), pages[page_index])

        ui_section("조작")
        ui_item("→", "다음 페이지")
        ui_item("←", "이전 페이지")
        ui_item("F8", "언어 전환", "한국어 / 日本語")
        ui_item("Enter", "설정 화면으로 돌아가기")
        ui_item("M", "메인 메뉴")
        ui_item("S", "종료")

        key = read_notice_key("←/→ 페이지 이동 / F8 언어 전환")

        if key == "F8":
            language_code = switch_creator_note_language(language_code)
            page_index = keep_creator_note_page_after_language_switch(page_index, language_code)
            continue

        if key == "RIGHT":
            if page_index < total_pages - 1:
                page_index += 1
            continue

        if key == "LEFT":
            if page_index > 0:
                page_index -= 1
            continue

        if key in {"ENTER", "BACK"}:
            return "back"

        if key == "MAIN":
            raise ReturnToMenu

        if key == "S":
            raise ExitProgram

        say("←, →, F8, Enter, M, S 중에서 입력해주세요.")
        time.sleep(0.8)

def show_patch_notes(clear=True):
    language_code = "ko"
    page_index = 0

    while True:
        lines = get_patch_note_lines(language_code)
        pages = paginate_legal_notice(lines)
        total_pages = len(pages)
        page_index = max(0, min(page_index, total_pages - 1))
        label = LEGAL_NOTICE_LANGUAGE_LABELS.get(language_code, language_code)

        ui_clear_screen()
        ui_title(
            get_patch_note_title(language_code),
            f"{label} · {page_index + 1} / {total_pages}",
        )
        ui_notice(get_patch_note_title(language_code), pages[page_index])

        ui_section("조작")
        ui_item("→", "다음 페이지")
        ui_item("←", "이전 페이지")
        ui_item("F8", "언어 전환", "한국어 / English")
        ui_item("Enter", "설정 화면으로 돌아가기")
        ui_item("M", "메인 메뉴")
        ui_item("S", "종료")

        key = read_notice_key("←/→ 페이지 이동 / F8 언어 전환")

        if key == "F8":
            language_code = switch_legal_notice_language(language_code)
            page_index = keep_page_index_after_language_switch(
                page_index,
                get_patch_note_lines,
                language_code,
            )
            continue

        if key == "RIGHT":
            if page_index < total_pages - 1:
                page_index += 1
            continue

        if key == "LEFT":
            if page_index > 0:
                page_index -= 1
            continue

        if key in {"ENTER", "BACK"}:
            return "back"

        if key == "MAIN":
            raise ReturnToMenu

        if key == "S":
            raise ExitProgram

        say("←, →, F8, Enter, M, S 중에서 입력해주세요.")
        time.sleep(0.8)

def show_legal_notice(clear=True, require_accept=False):
    if require_accept:
        return show_required_legal_notice_scrollable()

    language_code = "ko"
    page_index = 0

    while True:
        page_index, total_pages = draw_legal_notice_page(
            language_code,
            page_index,
            require_accept=require_accept,
        )

        key = read_notice_key("←/→ 페이지 이동 / F8 언어 전환")

        if key == "F8":
            language_code = switch_legal_notice_language(language_code)
            page_index = keep_page_index_after_language_switch(
                page_index,
                get_legal_notice_lines,
                language_code,
            )
            continue

        if key == "RIGHT":
            if page_index < total_pages - 1:
                page_index += 1
            continue

        if key == "LEFT":
            if page_index > 0:
                page_index -= 1
            continue

        if key in {"ENTER", "BACK"}:
            return "back"

        if key == "MAIN":
            raise ReturnToMenu

        if key == "S":
            raise ExitProgram

        say("←, →, F8, Enter, M, S 중에서 입력해주세요.")
        time.sleep(0.8)

def show_startup_notice_once():
    settings = load_settings()

    if (
        settings.get("legal_notice_accepted") is True
        and settings.get("legal_notice_version") == TERMS_OF_SERVICE_VERSION
        and settings.get("legal_notice_variant") == LEGAL_NOTICE_VARIANT
    ):
        return

    result = show_legal_notice(clear=True, require_accept=True)

    if result == "accepted":
        settings["legal_notice_accepted"] = True
        settings["legal_notice_version"] = TERMS_OF_SERVICE_VERSION
        settings["legal_notice_variant"] = LEGAL_NOTICE_VARIANT
        save_settings(settings)
        return
