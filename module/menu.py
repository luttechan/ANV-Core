# AnkiVoice menu module.
# This module is loaded by AnkiVoice.py and is not a standalone entry point.

if __name__ == "__main__":
    print()
    print("[ERROR] module/menu.py is not a standalone program.")
    print("Run AnkiVoice.py instead.")
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass
    raise SystemExit(1)

_RUNTIME_BOUND = False
__all__ = ["ask_main_menu"]


def bind_runtime(runtime_module):
    global _RUNTIME_BOUND
    for name in dir(runtime_module):
        if name.startswith("__"):
            continue
        globals()[name] = getattr(runtime_module, name)
    _RUNTIME_BOUND = True
    return True


def _norm(value):
    func = globals().get("normalize_menu_answer")
    if callable(func):
        return func(value)
    return str(value or "").strip().upper()


def _prompt(label="메뉴"):
    func = globals().get("ui_prompt")
    if callable(func):
        return func(label)
    return input(f"{label}: ")


def _handle_common(answer):
    if answer == "S":
        raise globals().get("ExitProgram", SystemExit)()
    if answer in {"M", "B"}:
        return "BACK"
    return None


def _show_header(title, subtitle=""):
    globals().get("ui_clear_screen", lambda: None)()
    globals().get("ui_title", print)(title, subtitle)


def _main_title():
    name = globals().get("APP_NAME", "AnkiVoice")
    subtitle_func = globals().get("get_main_subtitle")
    subtitle = subtitle_func() if callable(subtitle_func) else ""
    return name, subtitle


def _ask_extractor_menu():
    while True:
        _show_header("CSV Extractor", "TXT, APKG, CSV에서 학습 자료를 추출합니다.")
        ui_section("선택")
        ui_item("1)", "TXT Lines → CSV")
        ui_item("2)", "APKG → Word CSV")
        ui_item("3)", "APKG → Full CSV + Word CSV")
        ui_item("4)", "TXT → CSV → MP3", "CSV 생성 후 MP3 Collector로 연결")
        ui_item("5)", "APKG → CSV → MP3", "CSV 생성 후 MP3 Collector로 연결")
        ui_section("이동")
        ui_item("B)", "메인 메뉴")
        ui_item("S)", "종료")
        answer = _norm(_prompt("CSV Extractor"))
        common = _handle_common(answer)
        if common == "BACK":
            return None
        if answer == "1": return "A1"
        if answer == "2": return "A2"
        if answer == "3": return "A3"
        if answer == "4": return "A4"
        if answer == "5": return "A5"
        say("1, 2, 3, 4, 5, B, S 중에서 입력해주세요.")


def _ask_plain_text_menu():
    while True:
        _show_header("Plain Text Extractor", "TXT, APKG, CSV에서 단어만 뽑아 Plain Text로 저장합니다.")
        ui_section("Plain Text")
        ui_item("1)", "Anki TXT Extract → Plain Text")
        ui_item("2)", "APKG → Plain Text")
        ui_item("3)", "CSV → Plain Text")
        ui_section("이동")
        ui_item("B)", "메인 메뉴")
        ui_item("S)", "종료")
        answer = _norm(_prompt("Plain Text Extractor"))
        common = _handle_common(answer)
        if common == "BACK":
            return None
        if answer == "1": return "P1"
        if answer == "2": return "P2"
        if answer == "3": return "P3"
        say("1, 2, 3, B, S 중에서 입력해주세요.")


def _ask_mp3_collector_menu():
    while True:
        _show_header("MP3 Collector", "CSV, TXT, APKG, 검색어에서 음성 파일을 수집합니다.")
        ui_section("MP3 수집")
        ui_item("1)", "CSV → MP3")
        ui_item("2)", "Plain Text → MP3")
        ui_item("3)", "Anki TXT Extract → MP3")
        ui_item("4)", "APKG → MP3")
        ui_item("5)", "단어 직접 검색")
        ui_section("이동")
        ui_item("B)", "메인 메뉴")
        ui_item("S)", "종료")
        answer = _norm(_prompt("MP3 Collector"))
        common = _handle_common(answer)
        if common == "BACK":
            return None
        if answer == "1": return "C1"
        if answer == "2": return "C2"
        if answer == "3": return "C3"
        if answer == "4": return "C4"
        if answer == "5": return "C5"
        say("1, 2, 3, 4, 5, B, S 중에서 입력해주세요.")

def _ask_mp3_file_manager_menu():
    manager = globals().get("manage_audio_files_menu")
    if callable(manager):
        return manager()

    while True:
        _show_header("MP3 File Manager", "audio 파일명 정리와 collection.media 이동을 처리합니다.")
        ui_section("Anki 미디어 이동")
        ui_item("1)", "audio MP3 → collection.media 이동")
        ui_section("언어 prefix 정리")
        ui_item("2)", "언어 prefix 추가", "audio/{language} → language_단어.mp3")
        ui_item("3)", "언어 prefix 제거", "language_단어.mp3 → 단어.mp3")
        ui_section("파일명 정리")
        ui_item("4)", "언더바 → 반각 공백", "word_name.mp3 → word name.mp3")
        ui_section("APKG 오디오")
        ui_item("5)", "APKG 오디오 컴파일러")
        ui_section("별도 프로그램")
        ui_item("6)", "ANV 오디오 컨버터 실행", "FFmpeg 변환과 확장자 보정은 여기에서 실행")
        ui_section("이동")
        ui_item("B)", "메인 메뉴")
        ui_item("S)", "종료")
        answer = _norm(_prompt("MP3 File Manager"))
        common = _handle_common(answer)
        if common == "BACK":
            return None
        if answer == "1": return "F1"
        if answer == "2": return "F2"
        if answer == "3": return "F3"
        if answer == "4": return "F7"
        if answer == "5": return "K1"
        if answer == "6":
            launcher = globals().get("launch_anv_audio_converter")
            if callable(launcher):
                launcher()
                continue
            say("ANV Audio Converter module is not loaded.")
            continue
        say("1~6, B, S 중에서 입력해주세요.")


def _ask_anki_analyzer_menu():
    while True:
        _show_header("Anki 학습 Analyzer", "APKG 복습 기록에서 못 외우는 단어를 골라냅니다.")
        ui_section("선택")
        ui_item("1)", "고난도 단어 APKG 제작", "선택된 카드만 새 APKG로 저장")
        ui_item("2)", "고난도 단어 TXT 추출", "뜻, 점수, 다시 비율 포함")
        ui_item("3)", "고난도 단어 CSV 추출", "표로 정리해 확인")
        ui_item("4)", "고난도 단어 Plain Text 추출", "단어만 한 줄씩 저장")
        ui_item("5)", "학습 보고서 작성", "Case별 해석과 권장 학습법 포함")
        ui_section("이동")
        ui_item("B)", "메인 메뉴")
        ui_item("S)", "종료")
        answer = _norm(_prompt("Anki 학습 Analyzer"))
        common = _handle_common(answer)
        if common == "BACK":
            return None
        if answer == "1": return "D1"
        if answer == "2": return "D2"
        if answer == "3": return "D3"
        if answer == "4": return "D4"
        if answer == "5": return "D5"
        say("1, 2, 3, 4, 5, B, S 중에서 입력해주세요.")


def _ask_settings_menu():
    while True:
        _show_header("설정 / 정보", "AnkiVoice 설정과 안내 문서를 확인합니다.")
        ui_section("설정")
        ui_item("1)", "기본 음성 설정")
        ui_item("2)", "프랑스어 활용형 설정")
        ui_item("3)", "화면 모드")
        ui_item("4)", "Anki collection.media 경로")
        ui_item("5)", "러시아어 강세 처리")
        ui_item("6)", "작업 폴더 확인")
        ui_item("7)", "오류 코드표")
        ui_section("정보")
        ui_item("8)", "이용약관")
        ui_item("9)", "About")
        ui_item("10)", "패치 노트")
        ui_item("11)", "제작자의 말")
        ui_item("12)", "작업 자료 삭제")
        ui_section("Extended")
        ui_item("13)", "Developer Utility")
        ui_item("14)", "Developer Utility 다운로드 / 업데이트")
        ui_item("15)", "선택 패키지 삭제")
        ui_section("이동")
        ui_item("B)", "메인 메뉴")
        ui_item("S)", "종료")
        answer = _norm(_prompt("설정 / 정보"))
        common = _handle_common(answer)
        if common == "BACK":
            return None
        if answer.isdigit() and 1 <= int(answer) <= 15:
            return f"S{int(answer)}"
        say("1~15, B, S 중에서 입력해주세요.")


def _show_anv_daily_section():
    ui_section("Welcome to AnkiVoice")

    daily_func = globals().get("get_anv_daily_status")

    if not callable(daily_func):
        return

    daily = daily_func()

    ui_item("With ANV", f"함께한 지 {daily.get('days', 1)}일째")

    quote = str(daily.get("quote") or "").strip()
    author = str(daily.get("author") or "").strip()
    years = str(daily.get("years") or "").strip()

    if quote:
        quote_lines = [line.strip() for line in quote.splitlines() if line.strip()]

        if quote_lines:
            ui_item("Daily Quote", quote_lines[0])

            for line in quote_lines[1:]:
                ui_item("", line)

    if author and years:
        ui_item("Author", f"{author} ({years})")
    elif author:
        ui_item("Author", author)


def ask_main_menu():
    while True:
        refresh = globals().get("refresh_app_identity")
        if callable(refresh):
            refresh()
        name, subtitle = _main_title()
        _show_header(name, subtitle)

        ui_section("자료 추출 / 변환")
        ui_item("1)", "CSV Extractor", "TXT, APKG, CSV에서 CSV 학습 자료 생성")
        ui_item("2)", "Plain Text Extractor", "TXT, APKG, CSV에서 단어 Plain Text 추출")

        ui_section("음성 파일 / Anki 미디어")
        ui_item("3)", "MP3 Collector", "CSV/TXT/APKG/검색어에서 음성 파일 수집")
        ui_item("4)", "MP3 File Manager", "audio 파일명 정리, 언어 prefix, collection.media 이동")

        ui_section("학습 분석 / 퀴즈")
        ui_item("5)", "Anki 학습 Analyzer", "APKG 복습 기록 기반 고난도 단어 분석")
        ui_item("6)", "APKG 단어 퀴즈", "APKG에서 단어 퀴즈 실행")

        ui_section("시스템")
        ui_item("7)", "설정 / 정보")
        ui_item("0)", "종료")

        _show_anv_daily_section()

        ui_section("상태")
        if callable(globals().get("get_mp3_collector_status_label")):
            ui_item("MP3 Collector", get_mp3_collector_status_label())
        if callable(globals().get("get_output_location_summary")):
            ui_item("출력", get_output_location_summary())
        ui_section("입력")
        ui_hint("메뉴 번호를 입력하세요.")

        raw = _prompt("메인 메뉴")
        if callable(globals().get("handle_easter_egg_command")) and handle_easter_egg_command(raw):
            continue
        answer = _norm(raw)
        if answer == "1":
            choice = _ask_extractor_menu()
            if choice: return choice
            continue
        if answer == "2":
            choice = _ask_plain_text_menu()
            if choice: return choice
            continue
        if answer == "3":
            choice = _ask_mp3_collector_menu()
            if choice: return choice
            continue
        if answer == "4":
            choice = _ask_mp3_file_manager_menu()
            if choice: return choice
            continue
        if answer == "5":
            choice = _ask_anki_analyzer_menu()
            if choice: return choice
            continue
        if answer == "6":
            return "Q1"
        if answer == "7":
            choice = _ask_settings_menu()
            if choice: return choice
            continue
        if answer == "0":
            return "0"
        say("0~7 중에서 입력해주세요.")
