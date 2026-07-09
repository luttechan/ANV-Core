if __name__ == "__main__":
    print()
    print("[ERROR] module/apkg_difficulty_analyzer.py is not a standalone program.")
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
import math
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import textwrap
import threading
import time
import zipfile
from pathlib import Path

_RUNTIME_BOUND = False

__all__ = [
    "analyze_apkg_difficulty",
    "analyze_apkg_difficulty_file",
    "analyze_apkg_difficulty_theory_file",
    "analyze_apkg_difficulty_apkg",
    "analyze_apkg_difficulty_txt",
    "analyze_apkg_difficulty_csv",
    "analyze_apkg_difficulty_plain",
    "analyze_apkg_difficulty_theory",
]

ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
FIELD_SEPARATOR = "\x1f"


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
        raise RuntimeError("APKG Analysis은 단독으로 실행할 수 없습니다. AnkiVoice.py에서 불러와 주세요.")


def _fallback_say(message=""):
    print(message)


def _say(message=""):
    func = globals().get("say")
    if callable(func):
        func(message)
    else:
        _fallback_say(message)


def _log(message):
    func = globals().get("log_only")
    if callable(func):
        try:
            func(message)
            return
        except Exception:
            pass


class _ConsoleSpinner:
    def __init__(self, message):
        self.message = str(message or "처리 중입니다. 프로그램을 종료하지 마세요")
        self._stop = threading.Event()
        self._thread = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False

    def start(self):
        if self._thread is not None:
            return

        def run():
            dots = [".", "..", "..."]
            index = 0
            while not self._stop.is_set():
                text = f"\r{self.message}{dots[index % len(dots)]}   "
                try:
                    print(text, end="", flush=True)
                except Exception:
                    pass
                index += 1
                self._stop.wait(0.45)
            try:
                print("\r" + " " * (len(self.message) + 8) + "\r", end="", flush=True)
            except Exception:
                pass

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None


def _progress_message(task="분석"):
    return f"{task} 중입니다. 프로그램을 끄지 마세요"


def _show_safe_error(title, detail=None):
    ui_clear_screen = globals().get("ui_clear_screen", lambda: None)
    ui_error = globals().get("ui_error", _say)
    ui_hint = globals().get("ui_hint", _say)
    wait = globals().get("wait_back_to_previous")

    try:
        ui_clear_screen()
        ui_error(title)
        if detail:
            for line in str(detail).splitlines():
                if line.strip():
                    ui_hint(line.strip())
    finally:
        if callable(wait):
            wait("메인 메뉴로 돌아가려면 Enter를 눌러 주세요...")
        else:
            try:
                input("\nPress Enter to return...")
            except EOFError:
                pass


def _analysis_dir():
    base = globals().get("ANALYSIS_DIR")
    if base is None:
        base = Path(globals().get("BASE_DIR", Path.cwd())) / "analysis"
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _is_zstd_payload(data):
    return bytes(data or b"").startswith(ZSTD_MAGIC)


def _decompress_zstd_bytes(data):
    runtime_func = globals().get("decompress_zstd_bytes")
    if callable(runtime_func):
        return runtime_func(data)

    try:
        import zstandard as zstd
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(io.BytesIO(data)) as reader:
            return reader.read()
    except ImportError:
        pass

    zstd_exe = shutil.which("zstd")
    if not zstd_exe:
        raise RuntimeError("zstandard가 필요합니다. 다음 명령어로 설치해 주세요: pip install zstandard")

    proc = subprocess.run(
        [zstd_exe, "-q", "-d", "-c"],
        input=bytes(data or b""),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return proc.stdout


def _copy_zip_member_to_file(zip_file, member_name, out_path):
    out_path = Path(out_path)
    with out_path.open("wb") as f:
        f.write(zip_file.read(member_name))
    return out_path


def _extract_anki_database(apkg_path, temp_dir):
    apkg_path = Path(apkg_path)
    temp_dir = Path(temp_dir)

    with zipfile.ZipFile(apkg_path, "r") as z:
        names = set(z.namelist())

        if "collection.anki21b" in names:
            db_path = temp_dir / "collection_for_analysis.sqlite"
            db_path.write_bytes(_decompress_zstd_bytes(z.read("collection.anki21b")))
            return db_path, "collection.anki21b", True

        if "collection.anki21" in names:
            db_path = temp_dir / "collection.anki21"
            _copy_zip_member_to_file(z, "collection.anki21", db_path)
            return db_path, "collection.anki21", False

        if "collection.anki2" in names:
            db_path = temp_dir / "collection.anki2"
            _copy_zip_member_to_file(z, "collection.anki2", db_path)
            return db_path, "collection.anki2", False

    raise RuntimeError("APKG 파일 안에서 collection.anki21b, collection.anki21, collection.anki2를 찾을 수 없습니다.")


def _clean_plain_text(value, max_len=None):
    text = str(value or "")
    text = re.sub(r"\[sound:[^\]]+\]", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if max_len and len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def _clean_word(value):
    runtime_func = globals().get("clean_word")
    if callable(runtime_func):
        try:
            return runtime_func(value)
        except Exception:
            pass
    return _clean_plain_text(value, max_len=200)


def _safe_stem(value, fallback="hard_words"):
    text = str(value or fallback).strip()
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = text.strip("._ ")
    return text or fallback


def _format_number(value, digits=3, blank=""):
    if value is None:
        return blank
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def _parse_card_data(data):
    if not data:
        return {}
    try:
        parsed = json.loads(data)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _calc_retrievability(stability, desired_retention=0.9, decay=0.5, last_review_time=None, now=None):
    try:
        stability = float(stability)
    except Exception:
        return None

    if stability <= 0:
        return None

    if not last_review_time:
        return None

    try:
        last_review_time = float(last_review_time)
    except Exception:
        return None

    now = int(time.time()) if now is None else int(now)
    elapsed_days = max(0.0, (now - last_review_time) / 86400.0)

    try:
        desired_retention = float(desired_retention or 0.9)
        decay = abs(float(decay or 0.5))
        factor = desired_retention ** (-1.0 / decay) - 1.0
        retrievability = (1.0 + factor * elapsed_days / stability) ** (-decay)
        return max(0.0, min(1.0, retrievability))
    except Exception:
        return None


def _low_stability_points(stability):
    if stability is None:
        return 0.0
    try:
        stability = float(stability)
    except Exception:
        return 0.0
    if stability <= 0:
        return 10.0
    return max(0.0, (14.0 - stability) / 14.0 * 10.0)


def _hard_score(difficulty, stability, retrievability, lapses, again_rate):
    d = 0.0 if difficulty is None else max(0.0, min(10.0, float(difficulty)))
    s_points = _low_stability_points(stability)
    r_points = 0.0 if retrievability is None else max(0.0, min(1.0, 1.0 - float(retrievability))) * 20.0
    lapse_points = min(max(int(lapses or 0), 0), 5) * 6.0
    again_points = max(0.0, min(1.0, float(again_rate or 0.0))) * 30.0
    return d * 10.0 + again_points + lapse_points + r_points + s_points


def _build_reason(row):
    reasons = []
    if row.get("difficulty") is not None and row["difficulty"] >= 7.0:
        reasons.append("난이도 높음")
    if row.get("again_rate", 0.0) >= 0.2:
        reasons.append("'Again' 선택 비율 높음")
    if row.get("lapses", 0) >= 1:
        reasons.append("오답 기록 있음")
    if row.get("stability") is not None and row["stability"] <= 7.0:
        reasons.append("기억 유지일수 낮음")
    if row.get("retrievability") is not None and row["retrievability"] <= 0.85:
        reasons.append("현재 기억률 낮음")
    if not reasons:
        reasons.append("우선순위 높음")
    return ", ".join(reasons)


def _load_field_names(cur):
    field_names_by_mid = {}

    try:
        cur.execute("SELECT ntid, ord, name FROM fields ORDER BY ntid, ord")
        for ntid, ord_value, name in cur.fetchall():
            field_names_by_mid.setdefault(int(ntid), {})[int(ord_value)] = str(name or "")
    except Exception:
        pass

    if field_names_by_mid:
        return field_names_by_mid

    try:
        cur.execute("SELECT models FROM col LIMIT 1")
        raw_models = cur.fetchone()[0]
        models = json.loads(raw_models)
        for mid, model in models.items():
            fields = model.get("flds", []) if isinstance(model, dict) else []
            for index, field in enumerate(fields):
                if isinstance(field, dict):
                    field_names_by_mid.setdefault(int(mid), {})[index] = str(field.get("name") or "")
    except Exception:
        pass

    return field_names_by_mid


def _read_note_map(cur):
    field_names_by_mid = _load_field_names(cur)
    notes = {}

    cur.execute("SELECT id, mid, tags, flds FROM notes")
    for note_id, mid, tags, flds in cur.fetchall():
        fields = str(flds or "").split(FIELD_SEPARATOR)
        field_names = field_names_by_mid.get(int(mid), {})
        notes[int(note_id)] = {
            "id": int(note_id),
            "mid": int(mid),
            "tags": str(tags or "").strip(),
            "fields": fields,
            "field_names": field_names,
        }

    return notes


def _read_revlog_stats(cur):
    stats = {}
    cur.execute("SELECT cid, ease, id FROM revlog ORDER BY id")
    for cid, ease, review_id in cur.fetchall():
        cid = int(cid)
        item = stats.setdefault(cid, {
            "review_count": 0,
            "again_count": 0,
            "hard_count": 0,
            "good_count": 0,
            "easy_count": 0,
            "last_review_id": 0,
        })
        item["review_count"] += 1
        if int(ease) == 1:
            item["again_count"] += 1
        elif int(ease) == 2:
            item["hard_count"] += 1
        elif int(ease) == 3:
            item["good_count"] += 1
        elif int(ease) == 4:
            item["easy_count"] += 1
        item["last_review_id"] = max(item["last_review_id"], int(review_id))
    return stats


def _extract_card_rows(db_path, word_field_index=0, meaning_field_index=None, now=None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        cur = conn.cursor()
        notes = _read_note_map(cur)
        rev_stats = _read_revlog_stats(cur)
        rows = []
        now = int(time.time()) if now is None else int(now)

        cur.execute(
            """
            SELECT id, nid, did, ord, type, queue, due, ivl, factor, reps, lapses, data
            FROM cards
            ORDER BY id
            """
        )

        for card in cur.fetchall():
            note = notes.get(int(card["nid"]))
            if not note:
                continue

            fields = note.get("fields", [])
            if word_field_index >= len(fields):
                continue

            raw_word = fields[word_field_index]
            word = _clean_word(raw_word)
            if not word:
                continue

            meaning = ""
            if meaning_field_index is not None and 0 <= meaning_field_index < len(fields):
                meaning = _clean_plain_text(fields[meaning_field_index], max_len=240)

            data = _parse_card_data(card["data"])
            difficulty = data.get("d")
            stability = data.get("s")
            desired_retention = data.get("dr", 0.9)
            decay = data.get("decay", 0.5)
            last_review_time = data.get("lrt") or int(card["mod"] if "mod" in card.keys() else 0)

            try:
                difficulty = float(difficulty) if difficulty is not None else None
            except Exception:
                difficulty = None

            try:
                stability = float(stability) if stability is not None else None
            except Exception:
                stability = None

            stat = rev_stats.get(int(card["id"]), {})
            review_count = int(stat.get("review_count", 0))
            again_count = int(stat.get("again_count", 0))
            again_rate = again_count / review_count if review_count else 0.0
            retrievability = _calc_retrievability(stability, desired_retention, decay, last_review_time, now=now)
            score = _hard_score(difficulty, stability, retrievability, int(card["lapses"]), again_rate)

            row = {
                "card_id": int(card["id"]),
                "note_id": int(card["nid"]),
                "deck_id": int(card["did"]),
                "ord": int(card["ord"]),
                "word": word,
                "meaning": meaning,
                "difficulty": difficulty,
                "stability": stability,
                "retrievability": retrievability,
                "interval": int(card["ivl"]),
                "reps": int(card["reps"]),
                "lapses": int(card["lapses"]),
                "review_count": review_count,
                "again_count": again_count,
                "again_rate": again_rate,
                "hard_count": int(stat.get("hard_count", 0)),
                "good_count": int(stat.get("good_count", 0)),
                "easy_count": int(stat.get("easy_count", 0)),
                "score": score,
                "tags": note.get("tags", ""),
                "has_fsrs": difficulty is not None or stability is not None,
            }
            row["reason"] = _build_reason(row)
            rows.append(row)

        return rows

    finally:
        conn.close()


def _pick_rows(rows, top_n=50, min_reps=3, difficulty_cutoff=None):
    filtered = []
    for row in rows:
        if int(row.get("reps", 0)) < int(min_reps or 0):
            continue
        if difficulty_cutoff is not None:
            difficulty = row.get("difficulty")
            if difficulty is None or float(difficulty) < float(difficulty_cutoff):
                continue
        filtered.append(row)

    filtered.sort(
        key=lambda item: (
            float(item.get("score") or 0.0),
            float(item.get("difficulty") or 0.0),
            float(item.get("again_rate") or 0.0),
            int(item.get("lapses") or 0),
        ),
        reverse=True,
    )

    top_n = int(top_n or 0)
    return filtered[:top_n] if top_n > 0 else filtered


def _default_meaning_field_index(max_cols):
    if max_cols >= 3:
        return 2
    if max_cols >= 2:
        return 1
    return None


def _field_label(note, index):
    field_names = note.get("field_names", {}) if note else {}
    return field_names.get(index) or f"Field {index + 1}"


def _preview_fields(notes, title, hint, max_preview=4):
    ui_clear_screen = globals().get("ui_clear_screen")
    ui_section = globals().get("ui_section")
    ui_hint = globals().get("ui_hint")
    ui_write = globals().get("ui_write")
    _wrap_display = globals().get("_wrap_display")
    _terminal_width = globals().get("_terminal_width")

    if callable(ui_clear_screen):
        ui_clear_screen()
    if callable(ui_section):
        ui_section(title)
    else:
        _say(title)
    if callable(ui_hint):
        ui_hint(hint)

    if not notes:
        return 0

    max_cols = max(len(note.get("fields", [])) for note in notes.values())
    sample_notes = list(notes.values())[:80]

    for col_index in range(max_cols):
        label = ""
        for note in sample_notes:
            label = _field_label(note, col_index)
            if label:
                break

        _say()
        _say(f"  [{col_index + 1}] {label or f'Field {col_index + 1}'}")

        samples = []
        for note in sample_notes:
            fields = note.get("fields", [])
            if col_index < len(fields):
                value = _clean_plain_text(fields[col_index], max_len=110)
                if value:
                    samples.append(value)
            if len(samples) >= max_preview:
                break

        if samples:
            for index, sample in enumerate(samples, start=1):
                if callable(ui_write) and callable(_wrap_display) and callable(_terminal_width):
                    for wrapped in _wrap_display(sample, _terminal_width() - 12):
                        ui_write(f"      {index}. {wrapped}")
                else:
                    _say(f"      {index}. {sample}")
        else:
            _say("      비어 있음")

    _say()
    return max_cols


def _ask_int_local(prompt, minimum, maximum, default=None):
    ask_int = globals().get("ask_int")
    if callable(ask_int):
        return ask_int(prompt, minimum, maximum, default=default)

    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw and default is not None:
            return int(default)
        try:
            value = int(raw)
        except Exception:
            print("숫자를 입력해 주세요.")
            continue
        if minimum <= value <= maximum:
            return value
        print(f"{minimum}~{maximum} 사이로 입력해주세요.")


def _ask_optional_field(prompt, maximum, default=None):
    while True:
        raw = globals().get("ui_prompt")
        normalize = globals().get("normalize_menu_answer")
        if callable(raw):
            value_raw = raw(prompt)
        else:
            value_raw = input(f"{prompt}: ")
        value = normalize(value_raw) if callable(normalize) else str(value_raw or "").strip().upper()

        if value in {"", "D", "DEFAULT"} and default is not None:
            return default
        if value in {"0", "N", "NO", "없음", "SKIP"}:
            return None
        if value in {"B"}:
            raise globals().get("BackScreen", Exception)()
        if value in {"M"}:
            raise globals().get("ReturnToMenu", Exception)()
        if value in {"S"}:
            raise globals().get("ExitProgram", SystemExit)()
        if str(value).isdigit():
            number = int(value)
            if 1 <= number <= maximum:
                return number - 1
        _say(f"1~{maximum}, 0, B, M, S 중에서 입력해주세요.")


def _load_notes_only(db_path):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        return _read_note_map(cur)
    finally:
        conn.close()


def _write_csv(rows, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "rank",
        "word",
        "meaning",
        "hard_score",
        "difficulty",
        "stability_days",
        "retrievability",
        "interval_days",
        "reps",
        "lapses",
        "review_count",
        "again_count",
        "again_rate",
        "reason",
        "tags",
        "card_id",
        "note_id",
    ]

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for rank, row in enumerate(rows, start=1):
            writer.writerow({
                "rank": rank,
                "word": row.get("word", ""),
                "meaning": row.get("meaning", ""),
                "hard_score": _format_number(row.get("score"), 2),
                "difficulty": _format_number(row.get("difficulty"), 3),
                "stability_days": _format_number(row.get("stability"), 3),
                "retrievability": _format_number(row.get("retrievability"), 4),
                "interval_days": row.get("interval", ""),
                "reps": row.get("reps", ""),
                "lapses": row.get("lapses", ""),
                "review_count": row.get("review_count", ""),
                "again_count": row.get("again_count", ""),
                "again_rate": _format_number(row.get("again_rate"), 4),
                "reason": row.get("reason", ""),
                "tags": row.get("tags", ""),
                "card_id": row.get("card_id", ""),
                "note_id": row.get("note_id", ""),
            })
    return output_path


REPORT_WIDTH = 78


def _report_rule(char="─", width=REPORT_WIDTH):
    char = str(char or "─")
    return char * max(10, int(width or REPORT_WIDTH))


def _report_box_title(title, subtitle=None):
    lines = [
        _report_rule("═"),
        f" {title}",
    ]
    if subtitle:
        lines.append(f" {subtitle}")
    lines.append(_report_rule("═"))
    return lines


def _report_section(title, icon="■"):
    return [
        "",
        f"{icon} {title}",
        _report_rule("─"),
    ]


def _wrap_report_text(text, first_prefix="", next_prefix=None, width=REPORT_WIDTH):
    text = str(text or "").strip()
    if not text:
        return []
    if next_prefix is None:
        next_prefix = " " * len(first_prefix)

    wrapped = textwrap.wrap(
        text,
        width=max(24, int(width or REPORT_WIDTH)),
        initial_indent=first_prefix,
        subsequent_indent=next_prefix,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return wrapped if wrapped else [first_prefix.rstrip()]


def _extend_wrapped(lines, label, value, bullet="•", width=REPORT_WIDTH):
    prefix = f"{bullet} {label}: "
    next_prefix = " " * len(prefix)
    lines.extend(_wrap_report_text(value, prefix, next_prefix, width=width))


def _metric_help_lines():
    return [
        "Criteria",
        "  • 난이도 : 카드의 학습 난이도를 나타냅니다. 수치가 높을수록 학습이 어렵습니다. (1~10점)",
        "  • 유지일수 : 현재 시점에서 기억이 유지될 것으로 예상되는 기간입니다.",
        "  • 현재 기억률: 현재 시점의 예상 정답률입니다.",
        "  • Again: '다시(Again)' 버튼을 선택한 비율입니다. 값이 높을수록 오답 빈도가 높습니다.",
    ]


def _score_help_lines():
    return [
        "점수는 카드의 확인 우선 순위를 나타냅니다.",
        "점수 자체보다 점수가 높게 산출된 원인을 확인하는 것이 중요합니다.",
    ]


def _metric_items(row):
    return [
        ("점수", _format_number(row.get("score"), 2, "-")),
        ("난이도", f"{_format_number(row.get('difficulty'), 2, '-')}/10"),
        ("유지일수", f"{_format_number(row.get('stability'), 1, '-')}일"),
        ("현재 기억률", _percent(row.get("retrievability"))),
        ("Again", _percent(row.get("again_rate"))),
        ("복습", f"{row.get('review_count', 0)}회"),
        ("재학습", f"{row.get('lapses', 0)}회"),
    ]


def _format_metric_table(row, indent="  "):
    label_width = 10
    return [
        f"{indent}• {label:<{label_width}} {value}"
        for label, value in _metric_items(row)
    ]


def _format_group_summary_lines(items, indent="  "):
    if not items:
        return [f"{indent}• 카드 수: 0개"]
    avg_d = _mean(r.get("difficulty") for r in items)
    med_s = _median(r.get("stability") for r in items)
    avg_r = _mean(r.get("retrievability") for r in items)
    avg_again = _mean(r.get("again_rate") for r in items)
    return [
        f"{indent}• 카드 수: {len(items)}개",
        f"{indent}• 평균 난이도: {_format_number(avg_d, 2, '-')}/10",
        f"{indent}• 중앙 유지일수: {_format_number(med_s, 1, '-')}일",
        f"{indent}• 평균 현재 기억률: {_percent(avg_r)}",
        f"{indent}• 평균 Again 비율: {_percent(avg_again)}",
    ]


def _word_card_lines(rank, row, width=REPORT_WIDTH):
    group_key = _primary_group_key(row)
    group_title = GROUP_DEFINITIONS.get(group_key, {}).get("title", group_key)
    word = str(row.get("word", "") or "").strip()
    meaning = str(row.get("meaning") or "").strip()
    reason = str(row.get("reason") or "").strip()
    interpretation = _row_number_interpretation(row)
    action = _row_study_action(row).removeprefix("학습법: ").strip()

    lines = []
    lines.append(_report_rule("─", width))
    lines.append(f"#{rank:02d}  {word}")
    lines.append(f"분류  │ {group_title}")
    if reason:
        lines.append(f"이유  │ {reason}")
    if meaning:
        lines.extend(_wrap_report_text(meaning, "뜻    │ ", "      │ ", width=width))

    lines.append("")
    lines.append("수치")
    lines.extend(_format_metric_table(row, indent="  "))

    lines.append("")
    lines.append("해석")
    lines.extend(_wrap_report_text(interpretation, "  • ", "    ", width=width))

    lines.append("")
    lines.append("학습법")
    lines.extend(_wrap_report_text(action, "  • ", "    ", width=width))
    lines.append("")
    return lines


def _word_table_lines(rows, limit=30, width=REPORT_WIDTH):
    shown = rows[:limit]
    lines = []
    lines.append("순위 │ 단어 │ 분류 │ 점수 │ 난이도 │ 유지일수 │ 현재 기억률 │ Again")
    lines.append(_report_rule("─", width))
    for rank, row in enumerate(shown, start=1):
        group_key = _primary_group_key(row)
        group_title = GROUP_DEFINITIONS.get(group_key, {}).get("title", group_key)
        word = str(row.get("word", "") or "").strip()
        lines.append(
            f"{rank:>2} │ {word} │ {group_title} │ "
            f"{_format_number(row.get('score'), 2, '-')} │ "
            f"{_format_number(row.get('difficulty'), 2, '-')}/10 │ "
            f"{_format_number(row.get('stability'), 1, '-')}일 │ "
            f"{_percent(row.get('retrievability'))} │ "
            f"{_percent(row.get('again_rate'))}"
        )
    if len(rows) > limit:
        lines.append(f"... 외 {len(rows) - limit}개")
    return lines


def _console_result_summary(row):
    group_key = _primary_group_key(row)
    group_title = GROUP_DEFINITIONS.get(group_key, {}).get("title", group_key)
    return (
        f"{group_title} · 점수 {_format_number(row.get('score'), 2, '-')} · "
        f"난이도 {_format_number(row.get('difficulty'), 2, '-')}/10 · "
        f"기억률 {_percent(row.get('retrievability'))} · "
        f"Again {_percent(row.get('again_rate'))}"
    )



def _write_txt(rows, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.extend(_report_box_title("Priority Volcabulary", "본 목록은 실력 평가가 아닌 우선적으로 확인이 필요한 카드를 선별하여 표시합니다."))
    lines.append(f"생성 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.extend(_report_section("숫자 읽는 방법", "◆"))
    lines.extend(_metric_help_lines())

    lines.extend(_report_section("단어 요약표", "◆"))
    lines.append("우선순위가 높은 카드부터 표시합니다.")
    lines.append("")
    lines.extend(_word_table_lines(rows, limit=min(len(rows), 50)))

    lines.extend(_report_section("단어별 상세", "◆"))
    for rank, row in enumerate(rows, start=1):
        lines.extend(_word_card_lines(rank, row))

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path

def _load_apkg_media_map(apkg_path):
    try:
        with zipfile.ZipFile(apkg_path, "r") as z:
            if "media" not in z.namelist():
                return {}, False
            raw = z.read("media")

        if _is_zstd_payload(raw):
            try:
                raw = _decompress_zstd_bytes(raw)
            except Exception as e:
                _log(f"APKG media zstd 해제 실패: {Path(apkg_path).name} / 이유: {e}")
                return {}, True

        data = json.loads(raw.decode("utf-8"))
        if isinstance(data, dict):
            return {str(key): str(value) for key, value in data.items()}, False
    except Exception as e:
        _log(f"APKG media map 읽기 실패: {Path(apkg_path).name} / 이유: {e}")

    return {}, False


def _sql_placeholders(values):
    return ",".join("?" for _ in values)


def _filter_database_for_cards(db_path, selected_card_ids, selected_note_ids):
    selected_card_ids = [int(x) for x in selected_card_ids]
    selected_note_ids = [int(x) for x in selected_note_ids]

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        if selected_card_ids:
            cur.execute(
                f"DELETE FROM revlog WHERE cid NOT IN ({_sql_placeholders(selected_card_ids)})",
                selected_card_ids,
            )
            cur.execute(
                f"DELETE FROM cards WHERE id NOT IN ({_sql_placeholders(selected_card_ids)})",
                selected_card_ids,
            )
        else:
            cur.execute("DELETE FROM revlog")
            cur.execute("DELETE FROM cards")

        if selected_note_ids:
            cur.execute(
                f"DELETE FROM notes WHERE id NOT IN ({_sql_placeholders(selected_note_ids)})",
                selected_note_ids,
            )
        else:
            cur.execute("DELETE FROM notes")

        try:
            cur.execute("DELETE FROM graves")
        except Exception:
            pass

        conn.commit()
        try:
            cur.execute("VACUUM")
        except Exception:
            pass
    finally:
        conn.close()


def _write_filtered_apkg(source_apkg, output_apkg, db_path, db_member_name, db_is_zstd, selected_rows):
    output_apkg = Path(output_apkg)
    output_apkg.parent.mkdir(parents=True, exist_ok=True)

    selected_card_ids = [row["card_id"] for row in selected_rows]
    selected_note_ids = sorted({row["note_id"] for row in selected_rows})
    _filter_database_for_cards(db_path, selected_card_ids, selected_note_ids)

    media_map, media_was_zstd = _load_apkg_media_map(source_apkg)
    media_payload = json.dumps(media_map, ensure_ascii=False).encode("utf-8")

    if db_is_zstd:
        output_db_member_name = "collection.anki21"
        skip_names = {"collection.anki21b", "collection.anki21", "collection.anki2", "media", "meta"}
        skip_numeric_media = media_was_zstd and not media_map
    else:
        output_db_member_name = db_member_name
        skip_names = {db_member_name, "media"}
        skip_numeric_media = False

    with zipfile.ZipFile(source_apkg, "r") as zin, zipfile.ZipFile(output_apkg, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename in skip_names:
                continue
            if skip_numeric_media and item.filename.isdigit():
                continue
            zout.writestr(item, zin.read(item.filename))

        zout.writestr(output_db_member_name, Path(db_path).read_bytes())
        zout.writestr("media", media_payload)

    return output_apkg


def _write_apkg_subset(source_apkg, selected_rows, output_path):
    with tempfile.TemporaryDirectory() as temp_name:
        temp_dir = Path(temp_name)
        db_path, db_member_name, db_is_zstd = _extract_anki_database(source_apkg, temp_dir)
        return _write_filtered_apkg(source_apkg, output_path, db_path, db_member_name, db_is_zstd, selected_rows)



def _ask_output_format():
    while True:
        globals().get("ui_clear_screen", lambda: None)()
        globals().get("ui_title", lambda title, subtitle="": _say(title))("출력 형식", "어려운 단어 목록을 어떤 형식으로 저장할지 선택합니다.")
        globals().get("ui_section", lambda title: _say(title))("선택")
        globals().get("ui_item", lambda *args: _say(" ".join(map(str, args))))("1)", "TXT", "설명 포함")
        globals().get("ui_item", lambda *args: _say(" ".join(map(str, args))))("2)", "CSV", "정렬·필터용")
        globals().get("ui_item", lambda *args: _say(" ".join(map(str, args))))("3)", "APKG", "선택한 카드만 APKG로 다시 묶기")
        globals().get("ui_item", lambda *args: _say(" ".join(map(str, args))))("4)", "Plain Text", "단어만 한 줄씩 저장")
        globals().get("ui_item", lambda *args: _say(" ".join(map(str, args))))("5)", "TXT + CSV + APKG")
        globals().get("ui_item", lambda *args: _say(" ".join(map(str, args))))("B)", "이전 화면")
        globals().get("ui_item", lambda *args: _say(" ".join(map(str, args))))("M)", "메인 메뉴")
        globals().get("ui_item", lambda *args: _say(" ".join(map(str, args))))("S)", "종료")

        raw = globals().get("ui_prompt", input)("출력 형식")
        normalize = globals().get("normalize_menu_answer")
        answer = normalize(raw) if callable(normalize) else str(raw or "").strip().upper()
        if answer in {"", "1", "TXT"}:
            return {"txt"}
        if answer in {"2", "CSV"}:
            return {"csv"}
        if answer in {"3", "APKG"}:
            return {"apkg"}
        if answer in {"4", "PLAIN", "PLAINTEXT", "P"}:
            return {"plain"}
        if answer in {"5", "ALL", "A"}:
            return {"txt", "csv", "apkg"}
        if answer == "B":
            raise globals().get("BackScreen", Exception)()
        if answer == "M":
            raise globals().get("ReturnToMenu", Exception)()
        if answer == "S":
            raise globals().get("ExitProgram", SystemExit)()
        _say("1, 2, 3, 4, 5, B, M, S 중에서 입력해 주세요.")


def _ask_analysis_options(max_cols, default_meaning_index, fixed_output_formats=None):
    top_n = _ask_int_local("추출 개수", 1, 5000, default=50)
    min_reps = _ask_int_local("최소 복습 횟수", 0, 100, default=3)

    while True:
        raw = globals().get("ui_prompt", input)("난이도 하한값 D, Enter=적용하지 않음")
        normalize = globals().get("normalize_menu_answer")
        value = str(raw or "").strip()
        upper = normalize(raw) if callable(normalize) else value.upper()
        if upper == "B":
            raise globals().get("BackScreen", Exception)()
        if upper == "M":
            raise globals().get("ReturnToMenu", Exception)()
        if upper == "S":
            raise globals().get("ExitProgram", SystemExit)()
        if not value:
            difficulty_cutoff = None
            break
        try:
            difficulty_cutoff = float(value)
            if 1.0 <= difficulty_cutoff <= 10.0:
                break
        except Exception:
            pass
        _say("1.0~10.0 사이의 숫자 또는 Enter를 입력해 주세요.")

    output_formats = set(fixed_output_formats) if fixed_output_formats is not None else _ask_output_format()
    return {
        "top_n": top_n,
        "min_reps": min_reps,
        "difficulty_cutoff": difficulty_cutoff,
        "output_formats": output_formats,
        "meaning_field_index": default_meaning_index,
    }


def _write_plain(rows, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    words = []
    seen = set()
    for row in rows:
        word = str(row.get("word", "")).strip()
        if not word:
            continue
        key = word.casefold()
        if key in seen:
            continue
        seen.add(key)
        words.append(word)
    output_path.write_text("\n".join(words) + ("\n" if words else ""), encoding="utf-8")
    return output_path


def _mean(values):
    values = [float(v) for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _median(values):
    values = sorted(float(v) for v in values if v is not None)
    if not values:
        return None
    n = len(values)
    mid = n // 2
    if n % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def _percent(value):
    if value is None:
        return "-"
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "-"


def _safe_ratio(n, d):
    try:
        d = float(d)
        if d <= 0:
            return 0.0
        return float(n) / d
    except Exception:
        return 0.0


def _unique_words(rows, limit=8):
    out = []
    seen = set()
    for row in rows:
        word = str(row.get("word", "") or "").strip()
        if not word:
            continue
        key = word.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(word)
        if len(out) >= limit:
            break
    return out


def _share(part, whole):
    try:
        whole = float(whole)
        if whole <= 0:
            return 0.0
        return float(part) / whole
    except Exception:
        return 0.0



def _level_text(value, good=None, warn=None, bad=None, reverse=False):
    if value is None:
        return "자료 없음"
    try:
        v = float(value)
    except Exception:
        return "자료 없음"
    if reverse:
        if bad is not None and v <= bad:
            return "위험"
        if warn is not None and v <= warn:
            return "주의"
        return "양호"
    if bad is not None and v >= bad:
        return "위험"
    if warn is not None and v >= warn:
        return "주의"
    return "양호"



def _metric_help_line():
    return "\n".join(_metric_help_lines())


def _score_help_line():
    return " ".join(_score_help_lines())


def _format_metric_pack(row):
    return (
        f"점수 {_format_number(row.get('score'), 2, '-')}"
        f" · 난이도 {_format_number(row.get('difficulty'), 2, '-')}/10"
        f" · 유지일수 {_format_number(row.get('stability'), 1, '-')}일"
        f" · 현재 기억률 {_percent(row.get('retrievability'))}"
        f" · Again {_percent(row.get('again_rate'))}"
        f" · 복습 {row.get('review_count', 0)}회"
        f" · 재학습 {row.get('lapses', 0)}회"
    )


def _row_number_interpretation(row):
    parts = []
    difficulty = row.get("difficulty")
    stability = row.get("stability")
    retrievability = row.get("retrievability")
    again_rate = float(row.get("again_rate") or 0.0)
    lapses = int(row.get("lapses") or 0)
    review_count = int(row.get("review_count") or 0)

    if difficulty is not None:
        d = float(difficulty)
        if d >= 8.0:
            parts.append("난이도가 매우 높은 카드입니다")
        elif d >= 7.0:
            parts.append("난이도가 다소 높은 편입니다")
        else:
            parts.append("난이도는 비교적 낮은 편입니다")

    if stability is not None:
        s = float(stability)
        if s <= 3.0:
            parts.append("기억 유지일수가 3일 이하입니다.")
            parts.append("조속한 복습을 권장합니다.")
        elif s <= 10.0:
            parts.append("기억 유지일수가 짧습니다")
            parts.append("복습 주기를 짧게 유지하십시오.")
        elif s >= 21.0:
            parts.append("기억 유지일수가 충분히 확보되었습니다.")
            parts.append("단기간 내 추가 복습의 필요성은 낮습니다.")

    if retrievability is not None:
        r = float(retrievability)
        if r <= 0.70:
            parts.append("현재 기억률이 70% 이하임")
            parts.append("금일 추가 복습이 필요합니다.")
        elif r <= 0.85:
            parts.append("현재 기억률이 85% 이하임")
            parts.append("추가 복습이 필요합니다.")

    if review_count >= 3 and again_rate >= 0.20:
        parts.append("Again(다시) 선택 비율이 20% 이상임")
        parts.append("반복적인 오답이 확인되었습니다.")
    if lapses >= 1:
        parts.append("재학습 기록 있음")
        parts.append("기억 유지에 실패하여 Again(다시) 단계로 되돌아간 이력이 있습니다.")

    if not parts:
        parts.append("단일 지표에서 이상이 확인되지 않음")
        parts.append("종합 점수 기준으로는 우선 검토 대상입니다.")

    sentences = []
    for part in parts:
        part = str(part or "").strip().rstrip(".")
        if part:
            sentences.append(part + ".")
    return " ".join(sentences)

def _row_study_action(row):
    key = _primary_group_key(row)
    if key == "front_check":
        return "권장 조치 : 복습량을 늘리기 전에 카드 내용을 수정하십시오. 의미는 간결히 정리하고 Section을 추가하여 예문 또는 혼동어와의 차이를 기재하십시오."
    if key == "due_now":
        return "권장 조치 : 금일 추가 복습이 필요합니다."
    if key == "high_difficulty_short_stability":
        return "권장 조치 : 신규 단어 추가보다는 기존 카드의 기억 단서를 보강한 뒤 다시 학습하십시오."
    if key == "again_heavy":
        return "권장 조치 : 오답 원인을 카드에 기록하십시오. 반복 오답 방지를 위해 혼동 지점을 함께 명시하십시오."
    if key == "stable_hard":
        return "권장 조치 : 카드 수정 불필요. 기존 복습 일정을 유지하십시오."
    if key == "not_enough_data":
        return "권장 조치 : 분석 보류. 추가 학습 데이터가 확보가 필요합니다."
    return "권장 조치 : 우선 검토 대상이 아닙니다. 현재 학습 기조를 유지하십시오."


def _group_interpretation(key, items):
    definition = GROUP_DEFINITIONS.get(key, {})
    return [
        f"의미 : {definition.get('desc', '')}",
        f"판단 근거 : {definition.get('why', '')}",
        f"학습 권장 사항 : {definition.get('action', '')}",
    ]


def _case_block(title, data, words, study, note=""):
    return {
        "title": title,
        "data": data,
        "words": words,
        "study": study,
        "note": note,
    }


GROUP_DEFINITIONS = {
    "front_check": {
        "title": "비정상 카드",
        "desc": "반복 복습에도 불구하고 오답이 지속됨",
        "why": "단어 자체보다는 카드 구성에 문제가 있을 가능성이 높습니다. (뜻의 범위가 너무 넓거나 구별 기준이 모호한 단어)",
        "action": "카드 내용을 수정하십시오. 뜻은 핵심 의미 중심으로 정리, 혼동어와의 구별 기준 및 예문, 품사, 발음, 한자 등 기억 단서 보완이 필요합니다.",
        "criterion": "총 복습 횟수 ≥ 8회, 기억 유지일수 ≤ 7일, Again 비율 ≥ 20% / 재학습 기록 多",
    },
    "due_now": {
        "title": "금일 복습 대상",
        "desc": "현재 기억률이 낮아 추가 복습이 필요함",
        "why": "기억률이 하락했습니다.",
        "action": "금일 한 차례 추가 복습을 권장합니다.",
        "criterion": "현재 기억률 ≤ 85%, 복습 횟수 ≥ 3회",
    },
    "high_difficulty_short_stability": {
        "title": "장기 기억 형성 미흡",
        "desc": "장기 기억 유지가 어려움",
        "why": "난이도 대비 기억 유지 일수가 낮습니다. 현재 카드 구성만으로는 장기 기억 형성이 충분하지 않습니다. (학습 부담이 큰 고난이도 단어)",
        "action": "신규 카드 추가보다 기존 카드 보완을 우선하십시오. 대표 의미, 대표 예문, 혼동어를 중심으로 카드 구성을 단순화하십시오.",
        "criterion": "카드 난이도 ≥ 7.0, 기억 유지일수 ≤ 10일",
    },
    "again_heavy": {
        "title": "반복 오답",
        "desc": "동일한 카드에서 Again 비율이 높음",
        "why": "오답 패턴이 반복적으로 확인됩니다. 동일한 방식의 암기만으로는 오류가 교정되지 않을 수 있습니다.",
        "action": "오답 원인을 카드에 기록하십시오. 혼동한 단어, 품사, 의미, 발음 등 오류 원인을 구체적으로 기재하십시오.",
        "criterion": "실제 복습 횟수 ≥ 3회, Again 비율 ≥ 20%",
    },
    "stable_hard": {
        "title": "안정권 고난도 단어",
        "desc": "고난도 카드이나 기억 유지 상태는 안정적임",
        "why": "고난도 카드이나 학습에는 문제가 확인되지 않습니다.",
        "action": "추가 조치가 필요하지 않습니다. 기존 커리큘럼을 유지하십시오.",
        "criterion": "카드 난이도 ≥ 7.0, 기억 유지일수 ≥ 21일, 현재 기억률 > 85%",
    },
    "not_enough_data": {
        "title": "판단 보류",
        "desc": "복습 기록이 부족하여 분석 신뢰도가 낮음",
        "why": "복습 횟수가 적어 현재 지표만으로는 학습 상태를 판단하기 어렵습니다.",
        "action": "복습 기록을 추가 확보한 뒤 다시 분석하십시오.",
        "criterion": "복습 횟수 < 3회",
    },
    "general_top": {
        "title": "관찰 대상",
        "desc": "개별 지표는 정상 범위이나 종합 우선순위가 높음",
        "why": "단일 지표에서는 이상이 확인되지 않았습니다. 다만 여러 지표가 동시에 반영되어 종합 우선순위가 높게 산출되었습니다.",
        "action": "우선순위는 낮습니다. 필요 시 추가 검토를 권장합니다.",
        "criterion": "종합 우선순위 높음 카드",
    },
}


def _primary_group_key(row):
    reps = int(row.get("reps") or 0)
    review_count = int(row.get("review_count") or 0)
    again_rate = float(row.get("again_rate") or 0.0)
    lapses = int(row.get("lapses") or 0)
    difficulty = row.get("difficulty")
    stability = row.get("stability")
    retrievability = row.get("retrievability")

    d = None if difficulty is None else float(difficulty)
    s = None if stability is None else float(stability)
    r = None if retrievability is None else float(retrievability)

    if reps < 3 and review_count < 3:
        return "not_enough_data"

    if reps >= 8 and s is not None and s <= 7.0 and (again_rate >= 0.20 or lapses >= 1):
        return "front_check"

    if r is not None and r <= 0.85 and review_count >= 3:
        return "due_now"

    if d is not None and d >= 7.0 and s is not None and s <= 10.0:
        return "high_difficulty_short_stability"

    if review_count >= 3 and again_rate >= 0.20:
        return "again_heavy"

    if d is not None and d >= 7.0 and s is not None and s >= 21.0 and (r is None or r > 0.85):
        return "stable_hard"

    return "general_top"


GROUP_ORDER = [
    "front_check",
    "due_now",
    "high_difficulty_short_stability",
    "again_heavy",
    "stable_hard",
    "not_enough_data",
    "general_top",
]

def _split_primary_groups(rows):
    groups = {key: [] for key in GROUP_ORDER}
    for row in rows:
        key = _primary_group_key(row)
        groups.setdefault(key, []).append(row)
    for key in groups:
        groups[key].sort(key=lambda r: float(r.get("score") or 0), reverse=True)
    return groups



def _group_summary(items):
    if not items:
        return "0개"
    avg_d = _mean(r.get("difficulty") for r in items)
    med_s = _median(r.get("stability") for r in items)
    avg_r = _mean(r.get("retrievability") for r in items)
    avg_again = _mean(r.get("again_rate") for r in items)
    return (
        f"{len(items)}개"
        f" · 평균 난이도 {_format_number(avg_d, 2, '-')}/10"
        f" · 중앙 유지일수 {_format_number(med_s, 1, '-')}일"
        f" · 평균 현재 기억률 {_percent(avg_r)}"
        f" · 평균 Again {_percent(avg_again)}"
    )

def _build_case_rows(rows, picked):
    groups = _split_primary_groups(rows)
    picked_ids = {r.get("card_id") for r in picked}
    total_again = sum(int(r.get("again_count") or 0) for r in rows)
    total_reviews = sum(int(r.get("review_count") or 0) for r in rows)
    overall_again = _safe_ratio(total_again, total_reviews)

    cases = []

    for key in GROUP_ORDER:
        items = groups.get(key, [])
        if not items:
            continue

        definition = GROUP_DEFINITIONS.get(key, {})
        title = definition.get("title", key)
        picked_in_group = [r for r in items if r.get("card_id") in picked_ids]
        shown = picked_in_group if picked_in_group else items

        data = _group_summary(items)
        criterion = definition.get("criterion")

        cases.append(_case_block(
            title,
            data,
            _unique_words(shown, 10),
            _group_interpretation(key, items),
            note=criterion or "",
        ))

        if len(cases) >= 6:
            break

    if not cases:
        cases.append(_case_block(
            "특이사항 없음",
            f"전체 Again 비율: {_percent(overall_again)}",
            _unique_words(picked, 10),
            [
                "의미 : 반복 오답 집중군이 확인되지 않음",
                "판단 근거 : 특정 유형의 학습 취약성이 나타나지 않았습니다.",
                "학습 권장 사항 : 기존 복습 일정을 유지하십시오.",
            ],
        ))

    return cases[:6]



def _build_priority_lines(rows, picked):
    groups = _split_primary_groups(rows)
    total_again = sum(int(r.get("again_count") or 0) for r in rows)
    picked_again = sum(int(r.get("again_count") or 0) for r in picked)

    lines = []
    lines.append("동일한 카드는 최우선 분류에만 배정됩니다.")
    lines.append("중복 분류는 적용되지 않습니다.")
    lines.append("")
    lines.extend(_metric_help_lines())

    display_index = 1
    for key in GROUP_ORDER:
        items = groups.get(key, [])
        if not items:
            continue

        definition = GROUP_DEFINITIONS.get(key, {})
        words = ", ".join(_unique_words(items, 8)) or "-"
        lines.append("")
        lines.append(f"{display_index}. {definition.get('title', key)}")
        lines.append(_report_rule("·", 48))
        display_index += 1
        lines.extend(_format_group_summary_lines(items, indent="  "))
        lines.extend(_wrap_report_text(definition.get("desc", ""), "  • 의미: ", "        "))
        lines.extend(_wrap_report_text(definition.get("why", ""), "  • 원인: ", "        "))
        lines.extend(_wrap_report_text(definition.get("action", ""), "  • 조치: ", "        "))
        lines.extend(_wrap_report_text(words, "  • 예시: ", "        "))

    if total_again:
        lines.append("")
        lines.append("Priority Again Rate")
        lines.append(_report_rule("·", 48))
        lines.append(
            f"  • 상위 {len(picked)}개 카드가 전체 Again 발생량의 "
            f"{_percent(_share(picked_again, total_again))}를 차지합니다."
        )
        lines.append("  • 해당 비율이 높을 수록 반복 오답의 편중 정도가 높음을 의미합니다")

    return lines

def _learning_method_block():
    return [
        "1) 난이도는 카드의 상대적 학습 부담을 나타내는 지표입니다.",
        "2) 현재 기억률이 낮은 카드는 우선적인 학습 조치가 요구됩니다.",
        "3) Again 비율이 높은 카드는 학습 단서의 충분성을 점검하십시오.",
        "4) 기억 유지일수가 짧은 카드는 신규 카드 추가보다 학습 단서의 보강을 우선적으로 권장합니다. (예문, 품사, 어원, 반의어 등의 정보 추가 시 기억 유지율 향상 도모 가능)",
        "5) 장기 기억이 형성된 카드는 기존 구성을 유지하는 것을 권장합니다.",
        "6) 복습 기록이 충분하지 않은 카드는 통계적 신뢰도가 낮으므로 해석에 유의하십시오.",
    ]


def _one_line_judgement(rows, picked):
    groups = _split_primary_groups(rows)
    total_again = sum(int(r.get("again_count") or 0) for r in rows)
    picked_again = sum(int(r.get("again_count") or 0) for r in picked)
    group_counts = [(key, len(groups.get(key, []))) for key in GROUP_ORDER]
    group_counts = [(key, count) for key, count in group_counts if count]
    main_key = group_counts[0][0] if group_counts else "general_top"
    main_title = GROUP_DEFINITIONS.get(main_key, {}).get("title", main_key)
    share_text = _percent(_share(picked_again, total_again)) if total_again else "0.0%"
    return (
        f"우선 검토 대상은 '{main_title}'입니다. "
        f"해당 분류의 {len(picked)}개 카드는 전체 Again 발생량의 {share_text}를 차지합니다. "
        f"따라서 해당 카드군은 반복 오답 관리의 우선 대상입니다."
    )



def _build_theory_report(source_apkg, rows, picked, options):
    total = len(rows)
    picked_count = len(picked)
    fsrs_rows = [r for r in rows if r.get("has_fsrs")]
    avg_d = _mean(r.get("difficulty") for r in rows)
    med_d = _median(r.get("difficulty") for r in rows)
    avg_s = _mean(r.get("stability") for r in rows)
    med_s = _median(r.get("stability") for r in rows)
    avg_r = _mean(r.get("retrievability") for r in rows)
    total_reps = sum(int(r.get("reps") or 0) for r in rows)
    total_lapses = sum(int(r.get("lapses") or 0) for r in rows)
    total_again = sum(int(r.get("again_count") or 0) for r in rows)
    total_review_count = sum(int(r.get("review_count") or 0) for r in rows)
    overall_again_rate = _safe_ratio(total_again, total_review_count)

    groups = _split_primary_groups(rows)
    high_again = [
        r for r in rows
        if float(r.get("again_rate") or 0.0) >= 0.2
        and int(r.get("review_count") or 0) >= 3
    ]

    lines = []
    lines.extend(_report_box_title("ANV Difficulty Analysis Report", "점수는 참고 지표이며, 원인 분석과 조치 우선순위를 기준으로 확인하십시오"))
    lines.append(f"작성: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"원본: {Path(source_apkg).name}")

    lines.extend(_report_section("0. Overview", "◆"))
    lines.extend(_wrap_report_text(_one_line_judgement(rows, picked), "• ", "  "))
    lines.extend(_wrap_report_text(
        "본 리포트는 학습 성취도 평가가 아닌 복습 우선순위 설정을 위한 참고 자료입니다. 각 지표는 우선 검토 대상 선정의 근거를 제공합니다.",
        "• ",
        "  ",
    ))

    lines.extend(_report_section("1. 주요 확인 항목", "◆"))
    lines.append("• APKG에 저장된 복습 이력, Again 기록, 재학습 이력 및 FSRS 지표를 기반으로 카드를 분류합니다.")
    lines.append("• FSRS란? : FSRS(Free Spaced Repetition Scheduler)는 카드의 기억률 및 복습 시점을 예측하는 Anki의 알고리즘입니다.")

    lines.extend(_report_section("2. 지표 해석 기준", "◆"))
    lines.extend(_score_help_lines())
    lines.append("")
    lines.extend(_metric_help_lines())
    lines.append("  • 재학습 횟수 : 오답으로 인해 재학습 단계로 전환된 횟수")

    lines.extend(_report_section("3. 전체 상태", "◆"))
    overview = [
        ("전체 카드 수", f"{total}개"),
        ("FSRS 데이터 보유 카드 수", f"{len(fsrs_rows)}개"),
        ("우선 확인 대상 카드 수", f"{picked_count}개"),
        ("전체 복습 횟수", f"{total_reps}회"),
        ("Again 발생 횟수 / 비율", f"{total_again}회 / {_percent(overall_again_rate)}"),
        ("재학습 전환 횟수", f"{total_lapses}회"),
        ("난이도 평균 / 중앙값", f"{_format_number(avg_d, 3, '-')} / {_format_number(med_d, 3, '-')}"),
        ("유지일수 평균 / 중앙값", f"{_format_number(avg_s, 2, '-')}일 / {_format_number(med_s, 2, '-')}일"),
        ("현재 평균 기억률", _percent(avg_r)),
    ]
    for label, value in overview:
        lines.append(f"• {label}: {value}")

    lines.extend(_report_section("4. 우선 검토 대상", "◆"))
    priority_rows = [
        ("1순위", "비정상 카드", len(groups.get("front_check", []))),
        ("2순위", "금일 복습 대상", len(groups.get("due_now", []))),
        ("3순위", "장기 기억 형성 미흡", len(groups.get("high_difficulty_short_stability", []))),
        ("4순위", "반복 오답 발생", len(high_again)),
    ]
    for rank_label, title, count in priority_rows:
        lines.append(f"• {rank_label}: {title} {count}개")
    lines.append("")
    lines.append("처리 순서")
    lines.append("비정상 카드 → 금일 복습 대상 단어 → 장기 기억 형성 미흡 단어 → 참고용 단어")

    lines.extend(_report_section("5. 단어 묶음별 해석", "◆"))
    lines.extend(_build_priority_lines(rows, picked))

    lines.extend(_report_section("6. 사례 분석", "◆"))
    cases = _build_case_rows(rows, picked)
    for idx, case in enumerate(cases, start=1):
        lines.append(f"사례 {idx}. {case['title']}")
        lines.append(_report_rule("·", 48))
        lines.append(f"수치 요약: {case['data']}")
        if case.get("note"):
            lines.append("")
            lines.append(f"분류 기준: {case['note']}")
        if case.get("words"):
            lines.append("")
            lines.append(f"해당 단어 예시: {', '.join(case['words'])}")
            lines.append("")
            lines.append("")
        for item in case.get("study", []):
            lines.extend(_wrap_report_text(item, "• ", "  "))
        lines.append("")

    lines.extend(_report_section("7. 집중 분석 대상 요약표", "◆"))
    lines.append("점수는 참고 지표이므로 분류 결과 및 조치 방향을 우선 확인하십시오")
    lines.append("")
    lines.extend(_word_table_lines(picked, limit=30))

    lines.extend(_report_section("8. 집중 분석 대상 상세 정보", "◆"))
    for rank, row in enumerate(picked[:30], start=1):
        lines.extend(_word_card_lines(rank, row))

    lines.extend(_report_section("9. 권장 학습법", "◆"))
    lines.extend(_learning_method_block())

    lines.extend(_report_section("10. 산정 기준", "◆"))
    lines.append("• APKG의 cards.data와 revlog 데이터를 사용합니다.")
    lines.append("• 산정식 = 카드 난이도 × 10 + Again 비율 × 30 + min(재학습 횟수, 5) × 6 + (1 - 현재 기억률) × 20 + 낮은 기억 유지일수 보정")
    lines.append("• 산정 점수는 정렬 기준으로만 사용됩니다. 학습 성취도 평가가 아닌 학습 방법 교정 및 우선 복습 대상 선정을 위한 기준입니다.")

    lines.extend(_report_section("11. 한계", "◆"))
    lines.append("• 복습 이력이 충분하지 않은 카드는 분석 신뢰도가 낮을 수도 있습니다.")
    lines.append("• 뜻 필드가 올바르게 지정되지 않았거나 카드 앞면에 여러 단어가 포함된 경우, 분석 결과가 왜곡될 수 있습니다.")

    lines.extend(_report_section("12. 참고문헌", "◆"))
    lines.append("• Anki Manual. Deck Options: FSRS 및 Desired Retention 관련 설명.")
    lines.append("• Open Spaced Repetition. FSRS4Anki: Free Spaced Repetition Scheduler for Anki.")
    lines.append("• Cepeda, N. J., et al. (2006). Distributed practice in verbal recall tasks: A review and quantitative synthesis. Psychological Bulletin.")
    lines.append("• Settles, B., & Meeder, B. (2016). A Trainable Spaced Repetition Model for Language Learning. ACL 2016.")
    lines.append("• Roediger, H. L., & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term retention. Psychological Science.")

    return "\n".join(lines)

def _write_theory_report(source_apkg, rows, picked, options):
    analysis_dir = _analysis_dir()
    stamp = time.strftime("%y%m%d_%H%M%S")
    output_path = analysis_dir / f"Report_{stamp}.txt"
    report = _build_theory_report(source_apkg, rows, picked, options)
    output_path.write_text(report, encoding="utf-8")
    return output_path, report

def _write_outputs(source_apkg, rows, output_formats):
    analysis_dir = _analysis_dir()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    stem = _safe_stem(Path(source_apkg).stem)
    base = analysis_dir / f"{stem}_hard_words_{stamp}"
    outputs = {}

    if "csv" in output_formats:
        outputs["csv"] = _write_csv(rows, base.with_suffix(".csv"))
    if "txt" in output_formats:
        outputs["txt"] = _write_txt(rows, base.with_suffix(".txt"))
    if "plain" in output_formats:
        outputs["plain"] = _write_plain(rows, base.with_name(base.name + "_plain.txt"))
    if "apkg" in output_formats:
        outputs["apkg"] = _write_apkg_subset(source_apkg, rows, base.with_suffix(".apkg"))

    return outputs


def _show_extraction_done(rows, picked, outputs, message="Complete!"):
    ui_clear_screen = globals().get("ui_clear_screen", lambda: None)
    ui_completed = globals().get("ui_completed", _say)
    ui_section = globals().get("ui_section", _say)
    ui_item = globals().get("ui_item", lambda *args: _say(" ".join(map(str, args))))
    ui_hint = globals().get("ui_hint", _say)
    wait = globals().get("wait_back_to_previous")

    ui_clear_screen()
    ui_completed(message)
    ui_section("결과")
    ui_item("전체 카드", f"{len(rows)}개")
    ui_item("추출 카드", f"{len(picked)}개")
    for key in ["apkg", "txt", "csv", "plain", "theory"]:
        if key in outputs:
            ui_item(key.upper(), str(outputs[key]))
    ui_hint("원본 APKG는 수정하지 않았습니다.")
    if callable(wait):
        wait("메인 메뉴로 돌아가려면 Enter를 눌러 주세요...")




def _report_console_summary_lines(report, limit=10):
    lines = str(report or "").splitlines()
    output = []
    capture = False

    for raw_line in lines:
        line = raw_line.strip()

        if line == "◆ 6. 사례 분석":
            capture = True
            continue

        if capture and line.startswith("◆ "):
            break

        if not capture or not line:
            continue

        if line.startswith("사례 ") or line.startswith("수치 요약 :") or line.startswith("해당 단어 예시 :") or line.startswith("• "):
            output.append(line)

        if len(output) >= limit:
            break

    if output:
        return output[:limit]

    fallback = []
    for raw_line in lines:
        line = raw_line.strip()
        if line and not set(line) <= {"═", "─", "·"}:
            fallback.append(line)
        if len(fallback) >= limit:
            break
    return fallback

def _run_apkg_difficulty_workflow(fixed_output_formats=None, title="어휘 난이도 분석", subtitle="APKG의 복습 기록과 FSRS 값을 읽어 정렬합니다.", theory=False):
    require_runtime()

    while True:
        ui_clear_screen()
        ui_title(title, subtitle)
        ui_hint("원본 APKG는 수정하지 않습니다.")

        try:
            selected_apkg = select_apkg_file()
        except BackScreen:
            return

        if selected_apkg is None:
            ui_error("apkg 폴더에 선택할 수 있는 APKG 파일이 없습니다.")
            ui_item("확인 폴더", str(APKG_DIR))
            wait_back_to_previous("메인 메뉴로 돌아가려면 Enter를 눌러 주세요...")
            return

        try:
            ui_processing("APKG 내부 데이터베이스를 읽는 중입니다. 프로그램을 종료하지 마세요.")
            with tempfile.TemporaryDirectory() as temp_name:
                temp_dir = Path(temp_name)
                db_path, _db_member_name, _db_is_zstd = _extract_anki_database(selected_apkg, temp_dir)
                notes = _load_notes_only(db_path)

                if not notes:
                    ui_error("APKG에서 읽을 수 있는 노트가 없습니다.")
                    wait_back_to_previous("메인 메뉴로 돌아가려면 Enter를 눌러 주세요...")
                    return

                max_cols = _preview_fields(
                    notes,
                    "필드 선택",
                    "단어 필드와 뜻 필드를 선택합니다. 0 입력 시 생략됩니다.",
                )
                word_field_number = _ask_int_local("단어 필드 번호", 1, max_cols, default=1)
                word_field_index = word_field_number - 1
                default_meaning = _default_meaning_field_index(max_cols)
                default_label = "없음" if default_meaning is None else str(default_meaning + 1)
                ui_hint(f"뜻 필드 기본값: {default_label}")
                meaning_field_index = _ask_optional_field("뜻 필드 번호, 0=생략", max_cols, default=default_meaning)

                with _ConsoleSpinner(_progress_message("카드 복습 기록 분석")):
                    rows = _extract_card_rows(
                        db_path,
                        word_field_index=word_field_index,
                        meaning_field_index=meaning_field_index,
                    )

                if not rows:
                    ui_error("분석할 카드가 없습니다.")
                    wait_back_to_previous("메인 메뉴로 돌아가려면 Enter를 눌러 주세요...")
                    return

                if theory:
                    options = {
                        "top_n": 50,
                        "min_reps": 3,
                        "difficulty_cutoff": None,
                        "output_formats": {"theory"},
                        "meaning_field_index": meaning_field_index,
                    }
                else:
                    options = _ask_analysis_options(max_cols, meaning_field_index, fixed_output_formats=fixed_output_formats)

                with _ConsoleSpinner(_progress_message("어려운 카드 분류")):
                    picked = _pick_rows(
                        rows,
                        top_n=options["top_n"],
                        min_reps=options["min_reps"],
                        difficulty_cutoff=options["difficulty_cutoff"],
                    )

                if not picked:
                    ui_error("조건에 맞는 카드가 없습니다.")
                    wait_back_to_previous("조건 선택으로 돌아가려면 Enter를 눌러 주세요...")
                    continue

                if theory:
                    with _ConsoleSpinner(_progress_message("리포트 작성")):
                        report_path, _report = _write_theory_report(selected_apkg, rows, picked, options)
                    ui_clear_screen()
                    ui_completed("분석이 완료되었습니다.")
                    ui_section("저장 위치")
                    ui_item("폴더", str(report_path.parent))
                    ui_item("파일", report_path.name)
                    ui_hint("리포트는 analysis 폴더에 저장되었습니다.")
                    wait_back_to_previous("메인 메뉴로 돌아가려면 Enter를 눌러 주세요...")
                    return

                ui_clear_screen()
                ui_title("추출 확인", "저장하기 전에 결과를 확인합니다.")
                ui_section("설정")
                ui_item("원본 APKG", selected_apkg.name)
                ui_item("전체 카드", f"{len(rows)}개")
                ui_item("추출 카드", f"{len(picked)}개")
                ui_item("최소 복습", f"{options['min_reps']}회")
                ui_item("난이도 하한", "적용하지 않음" if options["difficulty_cutoff"] is None else options["difficulty_cutoff"])
                ui_item("출력", ", ".join(sorted(options["output_formats"])).upper())

                ui_section("결과")
                for index, row in enumerate(picked[:10], start=1):
                    ui_item(
                        f"{index:02d}.",
                        row.get("word", ""),
                        _console_result_summary(row),
                    )

                ask_action("저장할까요?")
                with _ConsoleSpinner(_progress_message("결과 파일 저장")):
                    outputs = _write_outputs(selected_apkg, picked, options["output_formats"])

            _show_extraction_done(rows, picked, outputs)
            return

        except BackScreen:
            continue
        except Exception as e:
            _log("[APKG Difficulty Analyzer Error]")
            _log(str(e))
            try:
                import traceback
                _log(traceback.format_exc())
            except Exception:
                pass
            _show_safe_error("분석 중 오류가 발생했습니다.", str(e))
            return

def analyze_apkg_difficulty_file(apkg_path, word_field_index=0, meaning_field_index=None, top_n=50, min_reps=3, difficulty_cutoff=None, output_formats=("csv", "txt")):
    apkg_path = Path(apkg_path)
    with tempfile.TemporaryDirectory() as temp_name:
        temp_dir = Path(temp_name)
        db_path, _db_member_name, _db_is_zstd = _extract_anki_database(apkg_path, temp_dir)
        rows = _extract_card_rows(db_path, word_field_index=word_field_index, meaning_field_index=meaning_field_index)
        picked = _pick_rows(rows, top_n=top_n, min_reps=min_reps, difficulty_cutoff=difficulty_cutoff)
        outputs = _write_outputs(apkg_path, picked, set(output_formats))
        return {
            "total_cards": len(rows),
            "selected_cards": len(picked),
            "rows": picked,
            "outputs": outputs,
        }


def analyze_apkg_difficulty_theory_file(apkg_path, word_field_index=0, meaning_field_index=None, top_n=50, min_reps=3):
    apkg_path = Path(apkg_path)
    with tempfile.TemporaryDirectory() as temp_name:
        temp_dir = Path(temp_name)
        db_path, _db_member_name, _db_is_zstd = _extract_anki_database(apkg_path, temp_dir)
        rows = _extract_card_rows(db_path, word_field_index=word_field_index, meaning_field_index=meaning_field_index)
        picked = _pick_rows(rows, top_n=top_n, min_reps=min_reps, difficulty_cutoff=None)
        options = {"top_n": top_n, "min_reps": min_reps, "difficulty_cutoff": None, "output_formats": {"theory"}, "meaning_field_index": meaning_field_index}
        path, report = _write_theory_report(apkg_path, rows, picked, options)
        return {"total_cards": len(rows), "selected_cards": len(picked), "rows": picked, "report": report, "output": path}


def analyze_apkg_difficulty():
    return _run_apkg_difficulty_workflow()


def analyze_apkg_difficulty_apkg():
    return _run_apkg_difficulty_workflow({"apkg"}, title="어휘 난이도 분석", subtitle="어려운 단어만 모아 새 APKG로 만듭니다.")


def analyze_apkg_difficulty_txt():
    return _run_apkg_difficulty_workflow({"txt"}, title="어휘 난이도 분석", subtitle="어려운 단어 목록을 TXT로 저장합니다.")


def analyze_apkg_difficulty_csv():
    return _run_apkg_difficulty_workflow({"csv"}, title="어휘 난이도 분석", subtitle="어려운 단어 목록을 CSV로 저장합니다.")


def analyze_apkg_difficulty_plain():
    return _run_apkg_difficulty_workflow({"plain"}, title="어휘 난이도 분석", subtitle="어려운 단어만 Plain Text로 저장합니다.")


def analyze_apkg_difficulty_theory():
    return _run_apkg_difficulty_workflow({"theory"}, title="어휘 난이도 분석", subtitle="사례별 해석과 학습법을 보고서로 저장합니다.", theory=True)
