# Extractor module for AnkiVoice.
# This module is loaded by AnkiVoice.py and is not a standalone entry point.

if __name__ == "__main__":
    print()
    print("[ERROR] module/extractor.py is not a standalone program.")
    print("Run AnkiVoice.py instead.")
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass
    raise SystemExit(1)

import csv
import json
import re
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

_RUNTIME_BOUND = False


def bind_runtime(runtime_module):
    # AnkiVoice.py의 함수, 설정, 경로, 예외 클래스를 이 모듈의 전역 이름공간에 연결한다.
    # 기존 단일 파일의 호출 구조를 유지하기 위한 런타임 바인딩이다.
    global _RUNTIME_BOUND

    for name in dir(runtime_module):
        if name.startswith("__"):
            continue
        globals()[name] = getattr(runtime_module, name)

    _RUNTIME_BOUND = True
    return True


def require_runtime():
    if not _RUNTIME_BOUND:
        raise RuntimeError("Extractor 모듈은 단독 실행할 수 없습니다. AnkiVoice.py에서 불러와야 합니다.")

# ============================================================
# 파일 선택 / 중복 처리
# ============================================================

def select_file_from_list(files, title, auto_select=True):
    if not files:
        return None

    ui_clear_screen()

    if len(files) == 1 and auto_select:
        selected = files[0]
        ui_section(f"{title} 파일")
        ui_item("OK", selected.name, "자동 선택")
        return selected

    ui_section(f"{title} 파일 선택")

    for i, file in enumerate(files, start=1):
        ui_item(f"{i})", file.name)

    say()
    ui_hint("번호를 입력하세요. B = 이전, M = 메인 메뉴, S = 종료")

    while True:
        answer = normalize_menu_answer(ui_prompt("파일 번호"))

        if answer == "B":
            raise BackScreen

        if answer == "M":
            raise ReturnToMenu

        if answer == "S":
            raise ExitProgram

        if not answer.isdigit():
            say("숫자로 입력해주세요.")
            continue

        index = int(answer)

        if 1 <= index <= len(files):
            selected = files[index - 1]
            say(f"선택한 파일 → {selected.name}")
            return selected

        say("목록에 있는 번호만 입력해주세요.")


def find_txt_files():
    txt_files = sorted(VOCA_DIR.glob("*.txt"))

    if not txt_files:
        say("voca 폴더에 txt 파일이 없습니다.")
        say(f"확인할 폴더 → {VOCA_DIR}")
        return []

    return txt_files


def find_apkg_files():
    apkg_files = sorted(APKG_DIR.glob("*.apkg"))

    if not apkg_files:
        say("apkg 폴더에 apkg 파일이 없습니다.")
        say(f"확인할 폴더 → {APKG_DIR}")
        return []

    return apkg_files


def find_csv_files():
    csv_files = sorted(CSV_DIR.glob("*.csv"))

    if not csv_files:
        say("csv 폴더에 csv 파일이 없습니다.")
        say("먼저 TXT/APKG를 CSV로 변환하거나 CSV 파일을 csv 폴더에 넣어주세요.")
        say(f"확인할 폴더 → {CSV_DIR}")
        return []

    return csv_files


def select_txt_file():
    return select_file_from_list(find_txt_files(), "TXT")


def select_apkg_file():
    return select_file_from_list(find_apkg_files(), "APKG")


def select_csv_file(auto_select=True):
    return select_file_from_list(find_csv_files(), "CSV", auto_select=auto_select)


def make_numbered_path(path):
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    number = 1

    while True:
        new_path = parent / f"{stem} ({number}){suffix}"

        if not new_path.exists():
            return new_path

        number += 1


def ask_duplicate_mode(target_paths):
    existing = [path for path in target_paths if path.exists()]

    if not existing:
        return "normal"

    ui_clear_screen()
    ui_section("같은 이름의 파일이 있습니다")

    for path in existing:
        ui_item("•", path.name)

    ui_section("저장 방식")
    ui_item("O)", "덮어쓰기", "기존 파일 교체")
    ui_item("N)", "새 이름 저장", "파일명에 번호 추가")
    ui_item("B)", "이전 화면")
    ui_item("M)", "메인 메뉴")
    ui_item("S)", "종료")

    while True:
        answer = normalize_menu_answer(ui_prompt("저장 방식"))

        if answer == "O":
            say("기존 파일을 덮어씁니다.")
            return "overwrite"

        if answer == "N":
            say("새 이름으로 저장합니다.")
            return "numbering"

        if answer == "B":
            raise BackScreen

        if answer == "M":
            raise ReturnToMenu

        if answer == "S":
            raise ExitProgram

        say("O, N, B, M, S 중에서 입력해주세요.")


def resolve_output_path(path, duplicate_mode):
    if duplicate_mode == "numbering":
        return make_numbered_path(path)

    return path


# ============================================================
# 텍스트 정리
# ============================================================

def clean_text(text):
    text = str(text).strip()

    if not text:
        return ""

    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    return text


def clean_word(word):
    return clean_text(word)


def apply_export_text_policy(word):
    policy_func = globals().get("normalize_word_by_policy")

    if callable(policy_func):
        try:
            return policy_func(word, language_mode="auto", purpose="export")
        except Exception as e:
            try:
                log_only(f"CSV/TXT 출력 정책 적용 실패: {word} / 이유: {e}")
            except Exception:
                pass

    return str(word or "")


def truncate_text(text, max_length=80):
    text = str(text)

    if len(text) <= max_length:
        return text

    return text[:max_length].rstrip() + "..."


def unique_keep_order(items):
    result = []
    seen = set()

    for item in items:
        key = item.strip().lower()

        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result


# ============================================================
# TXT → CSV 변환
# ============================================================

def read_anki_txt(path):
    say()
    say("TXT 파일을 읽습니다.")
    say(f"읽는 파일 → {path.name}")

    rows = []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter="\t", quotechar='"')

        for row in reader:
            if not row:
                continue

            first = row[0].strip()

            if not first:
                continue

            if first.startswith("#"):
                continue

            rows.append(row)

    say(f"읽은 노트 수 → {len(rows)}개")
    return rows


def extract_words_from_rows(rows, field_index=0):
    words = []

    for row in rows:
        if field_index >= len(row):
            continue

        word = clean_word(row[field_index])

        if not word:
            continue

        if word.lower() in {"word", "field 1", "field_1"}:
            continue

        words.append(word)

    return unique_keep_order(words)


def save_word_csv_from_words(words, output_path):
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Field 1"])

        for word in words:
            word = apply_export_text_policy(word)
            writer.writerow([word])

    say()
    say(f"단어 CSV 저장 완료 → {output_path}")
    say(f"단어 수 → {len(words)}개")

    return output_path


def save_full_csv(rows, output_path):
    if not rows:
        say("전체 CSV로 저장할 노트가 없습니다.")
        return 0

    max_cols = max(len(row) for row in rows)
    headers = [f"Field {i + 1}" for i in range(max_cols)]

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for row in rows:
            fixed_row = row + [""] * (max_cols - len(row))
            fixed_row = [apply_export_text_policy(cell) for cell in fixed_row]
            writer.writerow(fixed_row)

    say()
    say(f"전체 노트 CSV 저장 완료 → {output_path}")
    say(f"필드 수 → {max_cols}개")

    return max_cols


def preview_rows_for_field_selection(rows, max_preview=4):
    if not rows:
        return 0

    ui_clear_screen()
    max_cols = max(len(row) for row in rows)

    ui_section("필드 미리보기")
    ui_hint("단어가 들어 있는 필드 번호를 선택하세요.")

    for col_index in range(max_cols):
        samples = []

        for row in rows:
            if col_index < len(row):
                value = clean_text(row[col_index])

                if value:
                    samples.append(truncate_text(value, 110))

            if len(samples) >= max_preview:
                break

        say()
        say(f"  [{col_index + 1}] Field {col_index + 1}")

        if samples:
            for sample_index, sample in enumerate(samples, start=1):
                say(f"      {sample_index}. {sample}")
        else:
            say("      (비어 있음)")

    say()
    ui_hint("첫 번째 필드는 1입니다.")
    return max_cols


def convert_txt_to_csv():
    say()
    say("TXT → CSV 변환 모드입니다.")
    say(f"입력 폴더 → {VOCA_DIR}")
    say(f"결과 폴더 → {CSV_DIR}")

    selected_txt = select_txt_file()

    if selected_txt is None:
        return None

    rows = read_anki_txt(selected_txt)

    if not rows:
        say("변환할 노트가 없습니다.")
        return None

    max_cols = preview_rows_for_field_selection(rows)
    field_number = ask_int("단어 필드 번호", 1, max_cols, default=1)
    field_index = field_number - 1

    full_csv_path = CSV_DIR / f"{selected_txt.stem}_full.csv"
    word_csv_path = CSV_DIR / f"{selected_txt.stem}_field{field_number}_word_list.csv"

    duplicate_mode = ask_duplicate_mode([full_csv_path, word_csv_path])

    full_csv_path = resolve_output_path(full_csv_path, duplicate_mode)
    word_csv_path = resolve_output_path(word_csv_path, duplicate_mode)

    say()
    say("이번 변환 결과")
    say(f"전체 노트 CSV → {full_csv_path.name}")
    say(f"선택 필드 CSV → {word_csv_path.name}")

    ask_action("TXT → CSV 변환을 계속 진행할까요?")

    ui_processing("TXT에서 선택 필드를 추출하고 CSV로 저장하는 중입니다.")

    words = extract_words_from_rows(rows, field_index=field_index)

    save_word_csv_from_words(words, word_csv_path)
    save_full_csv(rows, full_csv_path)

    ui_completed("TXT → CSV 변환이 완료되었습니다.")

    say()
    say("TXT → CSV 변환 완료")
    say(f"선택한 TXT → {selected_txt.name}")
    say(f"추출한 단어 수 → {len(words)}개")

    return word_csv_path


# ============================================================
# APKG → CSV 변환
# ============================================================

def copy_zip_member_to_file(zip_file, member_name, out_path):
    with zip_file.open(member_name, "r") as src, out_path.open("wb") as dst:
        shutil.copyfileobj(src, dst)


def extract_anki_database_from_apkg(apkg_path, temp_dir):
    # APKG 내부 DB 선택 순서: collection.anki21b → collection.anki21 → collection.anki2
    with zipfile.ZipFile(apkg_path, "r") as z:
        names = set(z.namelist())

        if "collection.anki21b" in names:
            db_path = temp_dir / "collection_from_anki21b.sqlite"
            decompress_zstd_member_to_file(z, "collection.anki21b", db_path)
            return db_path, "collection.anki21b"

        if "collection.anki21" in names:
            db_path = temp_dir / "collection.anki21"
            copy_zip_member_to_file(z, "collection.anki21", db_path)
            return db_path, "collection.anki21"

        if "collection.anki2" in names:
            db_path = temp_dir / "collection.anki2"
            copy_zip_member_to_file(z, "collection.anki2", db_path)
            return db_path, "collection.anki2"

    raise RuntimeError("APKG 파일에서 collection.anki21b, collection.anki21, collection.anki2를 찾지 못했습니다.")


def load_model_map(conn):
    # 노트 타입과 필드명 로드 // 구형 col.models와 신형 fields/notetypes 테이블을 모두 지원
    model_map = {}

    try:
        cur = conn.cursor()
        cur.execute("SELECT models FROM col LIMIT 1")
        row = cur.fetchone()

        if row and row[0]:
            models = json.loads(row[0])

            if isinstance(models, dict):
                for mid, model in models.items():
                    if not isinstance(model, dict):
                        continue

                    field_names = []

                    for field in model.get("flds", []) or []:
                        if isinstance(field, dict):
                            field_names.append(field.get("name", ""))

                    model_map[str(mid)] = {
                        "name": model.get("name", ""),
                        "fields": field_names,
                    }
    except Exception:
        pass

    if model_map:
        return model_map

    # 최신 Anki DB는 col.models가 비어 있고 notetypes / fields 테이블을 사용한다.
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM notetypes ORDER BY id")
        notetypes = cur.fetchall()

        for ntid, name in notetypes:
            cur.execute("SELECT name FROM fields WHERE ntid = ? ORDER BY ord", (ntid,))
            field_names = [str(row[0]) for row in cur.fetchall()]
            model_map[str(ntid)] = {
                "name": str(name or ""),
                "fields": field_names,
            }
    except Exception:
        return {}

    return model_map


def read_notes_from_anki_db(db_path):
    conn = sqlite3.connect(db_path)

    try:
        model_map = load_model_map(conn)

        cur = conn.cursor()
        cur.execute("SELECT id, mid, flds FROM notes ORDER BY id")
        rows = cur.fetchall()

        notes = []

        for note_id, mid, flds in rows:
            fields = str(flds or "").split("\x1f")
            fields = [clean_text(field) for field in fields]

            model_info = model_map.get(str(mid), {})
            model_name = model_info.get("name", "")
            field_names = model_info.get("fields", [])

            notes.append({
                "note_id": note_id,
                "mid": str(mid),
                "model_name": model_name,
                "field_names": field_names,
                "fields": fields,
            })

        return notes

    finally:
        conn.close()


def is_compatibility_warning_only(notes):
    if len(notes) > 3:
        return False

    joined = " ".join(
        " ".join(note.get("fields", []))
        for note in notes
    )

    warning_patterns = [
        "최신 Anki",
        "업데이트한 후",
        "다시 가져오세요",
        "Please update to the latest Anki",
        "newer Anki version",
    ]

    return any(pattern in joined for pattern in warning_patterns)


def extract_notes_from_apkg(apkg_path):
    say()
    say("APKG 파일을 읽습니다.")
    say(f"읽는 파일 → {apkg_path.name}")

    with tempfile.TemporaryDirectory() as temp_name:
        temp_dir = Path(temp_name)
        db_path, db_source = extract_anki_database_from_apkg(apkg_path, temp_dir)

        say(f"사용한 내부 DB → {db_source}")

        notes = read_notes_from_anki_db(db_path)

    if is_compatibility_warning_only(notes):
        raise RuntimeError(
            "이 APKG에서 실제 학습 카드를 찾지 못했습니다. "
            "지원되지 않는 APKG일 수 있습니다."
        )

    say(f"읽은 노트 수 → {len(notes)}개")
    return notes


def notes_to_rows(notes):
    return [note["fields"] for note in notes]


def preview_notes_for_field_selection(notes, max_preview=4):
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

    ui_section("필드 미리보기")
    ui_hint("단어가 들어 있는 필드 번호를 선택하세요.")

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


def extract_words_from_notes(notes, field_index=0):
    words = []

    for note in notes:
        fields = note.get("fields", [])

        if field_index >= len(fields):
            continue

        word = clean_word(fields[field_index])

        if not word:
            continue

        if word.lower() in {"word", "field 1", "field_1"}:
            continue

        words.append(word)

    return unique_keep_order(words)


def save_full_csv_from_notes(notes, output_path):
    rows = notes_to_rows(notes)

    if not rows:
        say("전체 CSV로 저장할 노트가 없습니다.")
        return 0

    max_cols = max(len(row) for row in rows)

    headers = []
    field_name_by_index = {}

    for note in notes:
        for i, name in enumerate(note.get("field_names", [])):
            if name and i not in field_name_by_index:
                field_name_by_index[i] = name

    for i in range(max_cols):
        headers.append(field_name_by_index.get(i, f"Field {i + 1}"))

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for row in rows:
            fixed_row = row + [""] * (max_cols - len(row))
            fixed_row = [apply_export_text_policy(cell) for cell in fixed_row]
            writer.writerow(fixed_row)

    say()
    say(f"전체 필드 CSV 저장 완료 → {output_path}")
    say(f"필드 수 → {max_cols}개")

    return max_cols


def convert_apkg_to_csv(save_full=True, save_word=True):
    say()
    say("APKG → CSV 변환 모드입니다.")
    say(f"입력 폴더 → {APKG_DIR}")
    say(f"결과 폴더 → {CSV_DIR}")

    selected_apkg = select_apkg_file()

    if selected_apkg is None:
        return None

    ui_processing("APKG 내부 데이터베이스를 읽는 중입니다.")

    notes = extract_notes_from_apkg(selected_apkg)

    if not notes:
        say("APKG에서 읽을 노트가 없습니다.")
        return None

    max_cols = preview_notes_for_field_selection(notes)
    field_number = ask_int("단어 필드 번호", 1, max_cols, default=1)
    field_index = field_number - 1

    target_paths = []

    full_csv_path = CSV_DIR / f"{selected_apkg.stem}_full.csv"
    word_csv_path = CSV_DIR / f"{selected_apkg.stem}_field{field_number}_word_list.csv"

    if save_full:
        target_paths.append(full_csv_path)

    if save_word:
        target_paths.append(word_csv_path)

    duplicate_mode = ask_duplicate_mode(target_paths)

    full_csv_path = resolve_output_path(full_csv_path, duplicate_mode)
    word_csv_path = resolve_output_path(word_csv_path, duplicate_mode)

    say()
    say("이번 변환 결과")

    if save_full:
        say(f"전체 필드 CSV → {full_csv_path.name}")

    if save_word:
        say(f"선택 필드 CSV → {word_csv_path.name}")

    ask_action("APKG → CSV 변환을 계속 진행할까요?")

    ui_processing("APKG에서 선택 필드를 추출하고 CSV로 저장하는 중입니다.")

    if save_full:
        save_full_csv_from_notes(notes, full_csv_path)

    if save_word:
        words = extract_words_from_notes(notes, field_index=field_index)
        save_word_csv_from_words(words, word_csv_path)
    else:
        words = []

    ui_completed("APKG → CSV 변환이 완료되었습니다.")

    say()
    say("APKG → CSV 변환 완료")
    say(f"선택한 APKG → {selected_apkg.name}")

    if save_word:
        say(f"추출한 단어 수 → {len(words)}개")
        return word_csv_path

    return full_csv_path if save_full else None


# ============================================================
# CSV에서 단어 읽기
# ============================================================

def normalize_header_name(text):
    return str(text).strip().lower().replace("_", " ")


def find_word_column(rows):
    # CSV 단어열 찾기
    #
    # 우선순위
    # 1. Field 1
    # 2. word
    # 3. 단어
    # 4. vocab
    # 5. vocabulary
    # 6. 못 찾으면 첫 번째 열
    header_candidates = {
        "field 1",
        "word",
        "단어",
        "vocab",
        "vocabulary",
    }

    for row_index, row in enumerate(rows[:30]):
        normalized = [normalize_header_name(cell) for cell in row]

        for col_index, name in enumerate(normalized):
            if name in header_candidates:
                return row_index, col_index, row[col_index]

    return None, 0, None


def load_words_from_csv(csv_path):
    say()
    say("CSV 파일을 읽습니다.")
    say(f"읽는 파일 → {csv_path.name}")

    rows = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)

        for row in reader:
            if not row:
                continue

            if row[0].strip().startswith("#"):
                continue

            rows.append(row)

    if not rows:
        say("CSV 안에 읽을 행이 없습니다.")
        return []

    header_row_index, word_col_index, header_name = find_word_column(rows)

    if header_name is not None:
        say(f"단어 열 발견 → {header_name}")
        data_rows = rows[header_row_index + 1:]
    else:
        say("단어 열을 찾지 못해 첫 번째 열을 사용합니다.")
        data_rows = rows

    words = []

    for row in data_rows:
        if word_col_index >= len(row):
            continue

        word = clean_word(row[word_col_index])

        if not word:
            continue

        lowered = word.lower()

        if lowered in {"word", "field 1", "field_1"}:
            continue

        words.append(word)

    words = unique_keep_order(words)

    say(f"수집 대상 단어 수 → {len(words)}개")
    return words


__all__ = [
    "select_file_from_list",
    "find_txt_files",
    "find_apkg_files",
    "find_csv_files",
    "select_txt_file",
    "select_apkg_file",
    "select_csv_file",
    "make_numbered_path",
    "ask_duplicate_mode",
    "resolve_output_path",
    "clean_text",
    "clean_word",
    "apply_export_text_policy",
    "truncate_text",
    "unique_keep_order",
    "read_anki_txt",
    "extract_words_from_rows",
    "save_word_csv_from_words",
    "save_full_csv",
    "preview_rows_for_field_selection",
    "convert_txt_to_csv",
    "copy_zip_member_to_file",
    "extract_anki_database_from_apkg",
    "load_model_map",
    "read_notes_from_anki_db",
    "is_compatibility_warning_only",
    "extract_notes_from_apkg",
    "notes_to_rows",
    "preview_notes_for_field_selection",
    "extract_words_from_notes",
    "save_full_csv_from_notes",
    "convert_apkg_to_csv",
    "normalize_header_name",
    "find_word_column",
    "load_words_from_csv",
]
