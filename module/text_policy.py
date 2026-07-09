if __name__ == "__main__":
    print()
    print("[ERROR] module/text_policy.py is not a standalone program.")
    print("Run AnkiVoice.py instead.")
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass
    raise SystemExit(1)

import re
import unicodedata

_RUNTIME_BOUND = False

RUSSIAN_STRESS_POLICY_DEFAULT = "preserve"

RUSSIAN_STRESS_POLICY_LABELS = {
    "preserve": "강세 기호 보존",
    "match_only": "매칭/파일명에서만 제거",
    "strip_all": "전부 제거",
}

RUSSIAN_STRESS_POLICY_DESCRIPTIONS = {
    "preserve": (
        "CSV/TXT 출력, 검색어, 파일명, APKG 매칭에서 강세 기호를 유지합니다.",
        "원본 학습 데이터를 보존하므로 권장됩니다.",
    ),
    "match_only": (
        "CSV/TXT 출력은 보존하고, MP3 검색, 파일명, APKG 매칭에서만 강세 기호를 제거합니다.",
        "파일명 또는 APKG 매칭 문제가 있을 때에만 사용하세요.",
    ),
    "strip_all": (
        "CSV/TXT 출력까지 포함해 러시아어 강세 기호를 전부 제거합니다.",
        "원본 강세 데이터가 사라질 수 있으므로 주의가 필요합니다.",
    ),
}


RUSSIAN_MATCH_PURPOSES = {
    "lookup",
    "filename",
    "apkg_match",
    "media_match",
    "download",
}

CYRILLIC_PATTERN = re.compile(r"[\u0400-\u04FF]")
RUSSIAN_STRESS_MARKS = {"\u0301", "\u0341"}


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
        raise RuntimeError("Text policy module은 단독 실행할 수 없습니다. AnkiVoice.py에서 불러와야 합니다.")


def is_cyrillic_text(text):
    return bool(CYRILLIC_PATTERN.search(str(text or "")))


def strip_russian_stress(text):
    text = str(text or "")
    if not text:
        return ""

    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if ch not in RUSSIAN_STRESS_MARKS)
    return unicodedata.normalize("NFC", stripped)


def normalize_russian_stress_policy(policy):
    value = str(policy or "").strip().lower()

    aliases = {
        "": RUSSIAN_STRESS_POLICY_DEFAULT,
        "default": RUSSIAN_STRESS_POLICY_DEFAULT,
        "recommended": "preserve",
        "match": "match_only",
        "match-only": "match_only",
        "match_only": "match_only",
        "filename": "match_only",
        "file": "match_only",
        "lookup": "match_only",
        "2": "match_only",
        "preserve": "preserve",
        "keep": "preserve",
        "off": "preserve",
        "none": "preserve",
        "1": "preserve",
        "strip": "strip_all",
        "strip_all": "strip_all",
        "all": "strip_all",
        "remove": "strip_all",
        "on": "strip_all",
        "3": "strip_all",
    }

    return aliases.get(value, value if value in RUSSIAN_STRESS_POLICY_LABELS else RUSSIAN_STRESS_POLICY_DEFAULT)


def get_russian_stress_policy():
    require_runtime()

    try:
        settings = load_settings()
        russian_settings = settings.get("russian", {})
        if isinstance(russian_settings, dict):
            return normalize_russian_stress_policy(russian_settings.get("stress_policy"))
    except Exception as e:
        try:
            log_only(f"러시아어 강세 설정 읽기 실패: {e}")
        except Exception:
            pass

    return RUSSIAN_STRESS_POLICY_DEFAULT


def set_russian_stress_policy(policy):
    require_runtime()
    policy = normalize_russian_stress_policy(policy)
    settings = load_settings()
    settings.setdefault("russian", {})["stress_policy"] = policy
    return save_settings(settings)


def get_russian_stress_policy_label(policy=None):
    policy = get_russian_stress_policy() if policy is None else normalize_russian_stress_policy(policy)
    return RUSSIAN_STRESS_POLICY_LABELS.get(policy, RUSSIAN_STRESS_POLICY_LABELS[RUSSIAN_STRESS_POLICY_DEFAULT])


def get_russian_stress_policy_description(policy=None):
    policy = get_russian_stress_policy() if policy is None else normalize_russian_stress_policy(policy)
    description = RUSSIAN_STRESS_POLICY_DESCRIPTIONS.get(policy)

    if not description:
        description = RUSSIAN_STRESS_POLICY_DESCRIPTIONS[RUSSIAN_STRESS_POLICY_DEFAULT]

    if isinstance(description, (tuple, list)):
        return "\n".join(f"- {line}" for line in description if line)

    return str(description)


def should_strip_russian_stress(language_mode=None, purpose="display", text=None):
    policy = get_russian_stress_policy()

    if policy == "preserve":
        return False

    if str(language_mode or "").lower() == "ru":
        is_russian = True
    elif str(language_mode or "").lower() in {"auto", "", "none"}:
        is_russian = is_cyrillic_text(text)
    else:
        is_russian = False

    if not is_russian:
        return False

    if policy == "strip_all":
        return True

    return str(purpose or "display").lower() in RUSSIAN_MATCH_PURPOSES


def normalize_word_by_policy(word, language_mode=None, purpose="display"):
    text = str(word or "")

    if should_strip_russian_stress(language_mode=language_mode, purpose=purpose, text=text):
        return strip_russian_stress(text)

    return text


def normalize_word_for_export(word, language_mode="auto"):
    return normalize_word_by_policy(word, language_mode=language_mode, purpose="export")


def normalize_word_for_lookup(word, language_mode=None):
    return normalize_word_by_policy(word, language_mode=language_mode, purpose="lookup")


def normalize_word_for_filename(word, language_mode=None):
    return normalize_word_by_policy(word, language_mode=language_mode, purpose="filename")


def normalize_word_for_apkg_match(word, language_mode="auto"):
    return normalize_word_by_policy(word, language_mode=language_mode, purpose="apkg_match")


def configure_russian_stress_policy():
    require_runtime()

    while True:
        ui_clear_screen()
        ui_title("러시아어 강세 처리", "러시아어 강세 기호를 어느 단계에서 제거할지 설정합니다.")

        current_policy = get_russian_stress_policy()

        ui_section("현재 설정")
        ui_item(
            "상태",
            get_russian_stress_policy_label(current_policy),
            get_russian_stress_policy_description(current_policy),
        )

        ui_section("선택")
        ui_item(
            "1)",
            get_russian_stress_policy_label("preserve"),
            get_russian_stress_policy_description("preserve"),
        )
        ui_item(
            "2)",
            get_russian_stress_policy_label("match_only"),
            get_russian_stress_policy_description("match_only"),
        )
        ui_item(
            "3)",
            get_russian_stress_policy_label("strip_all"),
            get_russian_stress_policy_description("strip_all"),
        )

        ui_section("예시")
        sample = "молоко́"
        ui_item("원본", sample)
        ui_item("제거", strip_russian_stress(sample))
        ui_hint("2번은 학습용 CSV/TXT에는 강세를 남기고, MP3 검색·파일명·APKG 매칭에서만 제거합니다.")

        ui_section("이동")
        ui_item("B)", "이전 화면")
        ui_item("M)", "메인 메뉴")
        ui_item("S)", "종료")

        answer = normalize_menu_answer(ui_prompt("러시아어 강세 처리"))

        if answer in {"", "2", "MATCH", "MATCH_ONLY"}:
            selected_policy = "match_only"
        elif answer in {"1", "P", "PRESERVE", "KEEP"}:
            selected_policy = "preserve"
        elif answer in {"3", "A", "ALL", "STRIP", "STRIP_ALL"}:
            selected_policy = "strip_all"
        elif answer == "B":
            raise BackScreen
        elif answer == "M":
            raise ReturnToMenu
        elif answer == "S":
            raise ExitProgram
        else:
            say("1, 2, 3, B, M, S 중에서 입력해주세요.")
            continue

        set_russian_stress_policy(selected_policy)
        ui_clear_screen()
        ui_completed("러시아어 강세 처리 방식을 변경했습니다.")
        ui_item("현재 설정", get_russian_stress_policy_label())
        wait_back_to_previous("설정 화면으로 돌아가려면 Enter를 눌러주세요...")
        return


__all__ = [
    "RUSSIAN_STRESS_POLICY_DEFAULT",
    "RUSSIAN_STRESS_POLICY_LABELS",
    "RUSSIAN_STRESS_POLICY_DESCRIPTIONS",
    "strip_russian_stress",
    "normalize_russian_stress_policy",
    "get_russian_stress_policy",
    "set_russian_stress_policy",
    "get_russian_stress_policy_label",
    "get_russian_stress_policy_description",
    "should_strip_russian_stress",
    "normalize_word_by_policy",
    "normalize_word_for_export",
    "normalize_word_for_lookup",
    "normalize_word_for_filename",
    "normalize_word_for_apkg_match",
    "configure_russian_stress_policy",
]
