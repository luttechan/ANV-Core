if __name__ == "__main__":
    print()
    print("[ERROR] module/anv_daily.py is not a standalone program.")
    print("Run AnkiVoice.py instead.")
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass
    raise SystemExit(1)

import html
import re
from datetime import date

import requests

_RUNTIME_BOUND = False

__all__ = [
    "get_anv_daily_status",
    "fetch_anv_quote_from_quotations_page",
]

ANV_QUOTE_URL = "https://www.quotationspage.com/random.php"

ANV_FALLBACK_QUOTE = {
    "quote": "인터넷 연결 상태를 확인하십시오.",
    "author": "AnkiVoice",
    "years": "",
}


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
        raise RuntimeError("The ANV Daily module cannot be run independently. It must be launched from AnkiVoice.py.")


def _today_key():
    return date.today().isoformat()


def _parse_date(value):
    try:
        return date.fromisoformat(str(value or "").strip())
    except Exception:
        return None


def _day_count(first_used_date, today_key):
    first_day = _parse_date(first_used_date)
    today = _parse_date(today_key)

    if first_day is None or today is None or first_day > today:
        return 1

    return (today - first_day).days + 1


def _clean_html_fragment(value):
    value = html.unescape(str(value or ""))
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = value.replace("\xa0", " ")

    cleaned_lines = []

    for line in value.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def _split_author_years(author_text):
    author_text = re.sub(r"\s+", " ", str(author_text or "")).strip()

    match = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", author_text)

    if not match:
        return author_text, ""

    author = match.group(1).strip()
    years = match.group(2).strip()

    return author, years


def _extract_first_quote_pair(page):
    pair_match = re.search(
        r'<dt\s+class=["\']quote["\'][^>]*>(.*?)</dt>\s*<dd\s+class=["\']author["\'][^>]*>(.*?)</dd>',
        page,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not pair_match:
        raise RuntimeError("Could not find the first quotation on the Quotations page.")

    return pair_match.group(1), pair_match.group(2)


def _extract_quote_text(quote_block):
    link_match = re.search(
        r"<a[^>]*>(.*?)</a>",
        quote_block,
        flags=re.IGNORECASE | re.DOTALL,
    )

    source = link_match.group(1) if link_match else quote_block
    quote = _clean_html_fragment(source)

    if not quote:
        raise RuntimeError("The quotation is empty.")

    return quote


def _extract_author(author_block):
    bold_match = re.search(
        r"<b[^>]*>(.*?)</b>",
        author_block,
        flags=re.IGNORECASE | re.DOTALL,
    )

    source = bold_match.group(1) if bold_match else author_block
    author_raw = _clean_html_fragment(source)
    author, years = _split_author_years(author_raw)

    return author, years


def fetch_anv_quote_from_quotations_page(timeout=10):
    response = requests.get(
        ANV_QUOTE_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,*/*",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "iso-8859-1"

    quote_block, author_block = _extract_first_quote_pair(response.text)
    quote = _extract_quote_text(quote_block)
    author, years = _extract_author(author_block)

    return {
        "quote": quote,
        "author": author,
        "years": years,
    }


def _get_settings_func(name):
    func = globals().get(name)
    if not callable(func):
        raise RuntimeError(f"{name} could not be found.")
    return func


def _safe_log(message):
    func = globals().get("log_only")
    if callable(func):
        try:
            func(message)
        except Exception:
            pass


def get_anv_daily_status():
    require_runtime()

    today_key = _today_key()

    try:
        load_settings = _get_settings_func("load_settings")
        save_settings = _get_settings_func("save_settings")

        settings = load_settings()
        anv = settings.setdefault("anv", {})

        changed = False

        if not anv.get("first_used_date"):
            anv["first_used_date"] = today_key
            changed = True

        if anv.get("quote_date") != today_key or not anv.get("quote"):
            try:
                quote_data = fetch_anv_quote_from_quotations_page()
            except Exception as e:
                _safe_log(f"ANV quote fetch failed: {e}")
                quote_data = dict(ANV_FALLBACK_QUOTE)

            anv["quote_date"] = today_key
            anv["quote"] = quote_data.get("quote", ANV_FALLBACK_QUOTE["quote"])
            anv["quote_author"] = quote_data.get("author", ANV_FALLBACK_QUOTE["author"])
            anv["quote_years"] = quote_data.get("years", ANV_FALLBACK_QUOTE["years"])
            changed = True

        if changed:
            save_settings(settings)

        return {
            "days": _day_count(anv.get("first_used_date"), today_key),
            "date": today_key,
            "quote": anv.get("quote", ANV_FALLBACK_QUOTE["quote"]),
            "author": anv.get("quote_author", ANV_FALLBACK_QUOTE["author"]),
            "years": anv.get("quote_years", ANV_FALLBACK_QUOTE["years"]),
        }

    except Exception as e:
        _safe_log(f"ANV daily status failed: {e}")

    return {
        "days": 1,
        "date": today_key,
        "quote": ANV_FALLBACK_QUOTE["quote"],
        "author": ANV_FALLBACK_QUOTE["author"],
        "years": ANV_FALLBACK_QUOTE["years"],
    }
