"""Extract readable summaries from RSS HTML/plain text."""

import re
from html import unescape

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_DEFAULT_SUMMARY = "（暂无摘要，请点击链接阅读全文）"


def html_to_plain_text(html: str) -> str:
    if not html:
        return ""
    text = unescape(html)
    text = _HTML_TAG_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def make_summary(raw: str, max_len: int = 160) -> str:
    """Turn RSS summary/description into a short plain-text blurb."""
    text = html_to_plain_text(raw)
    if not text:
        return _DEFAULT_SUMMARY
    if len(text) <= max_len:
        return text

    cut = text[:max_len]
    for sep in ("。", "！", "？", ". ", "；", "; ", "，", ", ", " "):
        idx = cut.rfind(sep)
        if idx > max_len // 2:
            return cut[: idx + len(sep)].strip() + "…"
    return cut.rstrip() + "…"
