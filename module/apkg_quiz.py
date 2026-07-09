if __name__ == "__main__":
    print()
    print("[ERROR] module/apkg_quiz.py is not a standalone program.")
    print("Run AnkiVoice.py instead.")
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass
    raise SystemExit(1)

import html
import random
import re
import textwrap

_RUNTIME_BOUND = False
__all__ = ["run_apkg_quiz"]


_BR_PATTERN = re.compile(r"(?i)<\s*br\s*/?\s*>")
_BLOCK_END_PATTERN = re.compile(r"(?i)</\s*(?:p|div|li|tr|h[1-6])\s*>")
_BLOCK_START_PATTERN = re.compile(r"(?i)<\s*(?:p|div|li|tr|h[1-6])(?:\s+[^>]*)?>")
_TAG_PATTERN = re.compile(r"<[^>]+>")
_SOUND_PATTERN = re.compile(r"\[sound:[^\]]+\]", re.IGNORECASE)


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
        raise RuntimeError("APKG 단어 퀴즈 모듈은 단독 실행할 수 없습니다. AnkiVoice.py에서 불러와야 합니다.")


def _quiz_clean_value(value, keep_newlines=False):
    """Clean an Anki field for quiz display.

    The extractor's clean_text() removes all HTML tags and collapses whitespace.
    Quiz choices need to preserve <br> as real line breaks, so this module keeps
    its own cleaner instead of modifying extractor.py.
    """
    value = str(value or "")
    value = html.unescape(value)
    value = _SOUND_PATTERN.sub("", value)
    value = _BR_PATTERN.sub("\n", value)
    value = _BLOCK_END_PATTERN.sub("\n", value)
    value = _BLOCK_START_PATTERN.sub("", value)
    value = _TAG_PATTERN.sub("", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")

    lines = []
    for line in value.split("\n"):
        line = re.sub(r"[ \t\f\v]+", " ", line).strip()
        if line:
            lines.append(line)

    if keep_newlines:
        return "\n".join(lines).strip()

    return " / ".join(lines).strip()


def _quiz_plain_key(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _quiz_truncate(value, max_length=160):
    value = str(value or "")

    if len(value) <= max_length:
        return value

    return value[:max_length].rstrip() + "..."


def _quiz_terminal_width(default=100):
    width_func = globals().get("_terminal_width")

    if callable(width_func):
        try:
            return max(60, int(width_func()))
        except Exception:
            pass

    return default


def _quiz_wrap_line(line, width):
    line = str(line or "")

    if not line:
        return [""]

    wrapper = globals().get("_wrap_display")
    if callable(wrapper):
        try:
            wrapped = wrapper(line, width)
            if wrapped:
                return wrapped
        except Exception:
            pass

    return textwrap.wrap(
        line,
        width=max(20, width),
        replace_whitespace=False,
        drop_whitespace=False,
    ) or [line]


def _quiz_write_multiline(text, first_prefix="", continuation_prefix=""):
    text = str(text or "")
    available_width = _quiz_terminal_width() - max(len(first_prefix), len(continuation_prefix)) - 2
    lines = text.splitlines() or [""]
    first_output = True

    for raw_line in lines:
        chunks = _quiz_wrap_line(raw_line, available_width)

        for chunk in chunks:
            if first_output:
                say(first_prefix + chunk)
                first_output = False
            else:
                say(continuation_prefix + chunk)


def _quiz_write_choice(number, text):
    prefix = f"  {number})   "
    continuation = " " * len(prefix)
    _quiz_write_multiline(_quiz_truncate(text, 260), prefix, continuation)


def _quiz_field_names(notes):
    field_name_by_index = {}

    for note in notes:
        for i, name in enumerate(note.get("field_names", [])):
            name = _quiz_clean_value(name)

            if name and i not in field_name_by_index:
                field_name_by_index[i] = name

    return field_name_by_index


def _quiz_select_field(notes, title, hint, default=1, excluded_index=None):
    if not notes:
        return None

    max_cols = max(len(note.get("fields", [])) for note in notes)
    field_name_by_index = _quiz_field_names(notes)

    while True:
        ui_clear_screen()
        ui_title(title, hint)
        ui_section("필드 미리보기")

        for col_index in range(max_cols):
            label = field_name_by_index.get(col_index, f"Field {col_index + 1}")
            samples = []

            for note in notes:
                fields = note.get("fields", [])

                if col_index >= len(fields):
                    continue

                value = _quiz_clean_value(fields[col_index], keep_newlines=False)

                if value:
                    samples.append(_quiz_truncate(value, 110))

                if len(samples) >= 4:
                    break

            say()
            say(f"  [{col_index + 1}] {label}")

            if samples:
                for sample_index, sample in enumerate(samples, start=1):
                    say(f"      {sample_index}. {sample}")
            else:
                say("      (비어 있음)")

        say()
        ui_hint("번호를 입력하세요. B = 이전, M = 메인 메뉴, S = 종료")

        answer = normalize_menu_answer(ui_prompt("필드 번호"))

        if answer == "B":
            raise BackScreen

        if answer == "M":
            raise ReturnToMenu

        if answer == "S":
            raise ExitProgram

        if not answer:
            answer = str(default)

        if not answer.isdigit():
            say("숫자로 입력해주세요.")
            continue

        index = int(answer) - 1

        if not (0 <= index < max_cols):
            say("목록에 있는 번호만 입력해주세요.")
            continue

        if excluded_index is not None and index == excluded_index:
            say("단어 필드와 뜻 필드는 달라야 합니다.")
            continue

        return index


def _build_apkg_quiz_items(notes, word_index, answer_index):
    items = []
    seen_pairs = set()

    for note in notes:
        fields = note.get("fields", [])

        if word_index >= len(fields) or answer_index >= len(fields):
            continue

        word = _quiz_clean_value(fields[word_index], keep_newlines=True)
        answer = _quiz_clean_value(fields[answer_index], keep_newlines=True)

        if not word or not answer:
            continue

        key = (_quiz_plain_key(word), _quiz_plain_key(answer))

        if key in seen_pairs:
            continue

        seen_pairs.add(key)
        items.append({"word": word, "answer": answer})

    return items


def _unique_quiz_answers(items):
    answers = []
    seen = set()

    for item in items:
        answer = item.get("answer", "")
        key = _quiz_plain_key(answer)

        if not answer or key in seen:
            continue

        seen.add(key)
        answers.append(answer)

    return answers


def _quiz_result_message(score):
    if score == 0:
        return "반성하세요."

    if 1 <= score <= 3:
        return "기초부터 다시 점검해보세요."

    if 4 <= score <= 6:
        return "헷갈릴만한 단어를 조금 더 자세히 살펴보세요."

    if 7 <= score <= 9:
        return "좋습니다. 틀린 단어만 다시 복습해보세요."

    return "훌륭합니다."


def _quiz_show_start(selected_apkg, item_count, answer_count):
    ui_clear_screen()
    ui_title("APKG 단어 퀴즈", selected_apkg.name)
    ui_section("출제 방식")
    ui_item("문제 수", "10개")
    ui_item("형식", "5지선다")
    ui_item("정답 위치", "1~5번 랜덤")
    ui_item("오답", "다른 카드의 뜻에서 랜덤 추출")
    ui_section("사용 가능 데이터")
    ui_item("단어-뜻 쌍", f"{item_count}개")
    ui_item("서로 다른 뜻", f"{answer_count}개")
    say()
    ask_action("퀴즈를 시작할까요?")


def _quiz_show_wrong_answer(correct_number, correct_answer):
    ui_error("틀렸습니다.")
    ui_section("정답")
    _quiz_write_choice(correct_number, correct_answer)


def _quiz_show_wrong_items(wrong_items):
    ui_section("틀린 단어")

    if not wrong_items:
        ui_item("없음", "전부 맞혔습니다.")
        return

    for index, item in enumerate(wrong_items, start=1):
        say()
        _quiz_write_multiline(item["word"], f"  {index}. ", "     ")
        _quiz_write_multiline(_quiz_truncate(item["answer"], 220), "     정답: ", "           ")


def run_apkg_quiz():
    require_runtime()

    say()
    say("APKG 단어 퀴즈 모드입니다.")
    say("APKG에서 단어와 뜻을 읽어 5지선다 10문제를 만듭니다.")
    say(f"입력 폴더 → {APKG_DIR}")

    selected_apkg = select_apkg_file()

    if selected_apkg is None:
        return

    ui_processing("APKG 내부 데이터베이스를 읽는 중입니다.")
    notes = extract_notes_from_apkg(selected_apkg)

    if not notes:
        ui_error("APKG에서 읽을 노트가 없습니다.")
        return

    word_index = _quiz_select_field(
        notes,
        "APKG 단어 퀴즈",
        "문제에 표시할 단어 필드를 선택합니다.",
        default=1,
    )

    answer_index = _quiz_select_field(
        notes,
        "APKG 단어 퀴즈",
        "정답으로 사용할 뜻 필드를 선택합니다.",
        default=2,
        excluded_index=word_index,
    )

    items = _build_apkg_quiz_items(notes, word_index, answer_index)
    answer_pool = _unique_quiz_answers(items)

    if len(items) < 10:
        ui_clear_screen()
        ui_error("퀴즈를 만들 수 없습니다.")
        ui_hint("유효한 단어-뜻 쌍이 10개 이상 필요합니다.")
        ui_item("현재 사용 가능", f"{len(items)}개")
        return

    if len(answer_pool) < 5:
        ui_clear_screen()
        ui_error("퀴즈를 만들 수 없습니다.")
        ui_hint("서로 다른 뜻이 5개 이상 필요합니다.")
        ui_item("현재 사용 가능", f"{len(answer_pool)}개")
        return

    _quiz_show_start(selected_apkg, len(items), len(answer_pool))

    random.shuffle(items)
    questions = items[:10]
    score = 0
    wrong_items = []

    for question_number, item in enumerate(questions, start=1):
        correct_answer = item["answer"]
        correct_key = _quiz_plain_key(correct_answer)
        distractors = [
            answer for answer in answer_pool
            if _quiz_plain_key(answer) != correct_key
        ]

        if len(distractors) < 4:
            ui_clear_screen()
            ui_error("선택지를 만들 수 없습니다.")
            ui_hint("정답과 다른 뜻이 4개 이상 필요합니다.")
            return

        choices = random.sample(distractors, 4)
        choices.append(correct_answer)
        random.shuffle(choices)
        correct_number = choices.index(correct_answer) + 1

        while True:
            ui_clear_screen()
            ui_title("APKG 단어 퀴즈", f"문제 {question_number}/10")
            ui_section("단어")
            _quiz_write_multiline(item["word"], "  ", "  ")
            say()
            ui_section("선택지")

            for choice_index, choice_text in enumerate(choices, start=1):
                _quiz_write_choice(choice_index, choice_text)
                if choice_index < len(choices):
                    say("   ")

            say()
            ui_hint("1~5 중에서 입력하세요. B = 중단, M = 메인 메뉴, S = 종료")
            answer = normalize_menu_answer(ui_prompt("정답"))

            if answer == "B":
                return

            if answer == "M":
                raise ReturnToMenu

            if answer == "S":
                raise ExitProgram

            if answer not in {"1", "2", "3", "4", "5"}:
                say("1, 2, 3, 4, 5 중에서 입력해주세요.")
                continue

            selected_number = int(answer)
            break

        say()

        if selected_number == correct_number:
            score += 1
            ui_completed("정답입니다.")
        else:
            _quiz_show_wrong_answer(correct_number, correct_answer)
            wrong_items.append(item)

        wait_back_to_previous("다음 문제로 넘어가려면 Enter를 눌러주세요...")

    ui_clear_screen()
    ui_title("APKG 단어 퀴즈 결과", selected_apkg.name)
    ui_section("점수")
    ui_item("정답", f"{score}/10")
    ui_item("판정", _quiz_result_message(score))
    _quiz_show_wrong_items(wrong_items)
    wait_back_to_previous("메인 메뉴로 돌아가려면 Enter를 눌러주세요...")
