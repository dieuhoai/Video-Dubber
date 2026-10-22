"""Dịch/viết lại copy quảng cáo. Miễn phí: tạo prompt để dán sang Claude. Có API key: gọi Claude API trực tiếp."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from .langs import get_lang
from .models import Template

API_URL = "https://api.anthropic.com/v1/messages"


def build_prompt(tpl: Template, langs: list[str], hooks_per_lang: int = 1) -> str:
    """Prompt yêu cầu transcreation (viết lại cho hay), giới hạn độ dài để voice khớp thời lượng."""
    caps = [{"start": c.start, "end": c.end, "text": c.text} for c in tpl.captions]
    voice = [{"start": v.start, "end": v.end, "seconds": round(v.end - v.start, 1), "text": v.text} for v in tpl.voice]
    names = ", ".join(f"{c} ({get_lang(c).name})" for c in langs)
    keep = ", ".join(tpl.glossary) or "(không có)"
    return f"""Bạn là copywriter quảng cáo app mobile. Hãy transcreate (viết lại tự nhiên, giữ độ "cuốn" của hook,
không dịch sát từng chữ) nội dung video quảng cáo dưới đây sang: {names}.

Caption trên video (ngôn ngữ gốc: {tpl.source_lang}):
{json.dumps(caps, ensure_ascii=False, indent=1)}

Lời thoại (voice), mỗi câu phải đọc vừa trong số giây cho sẵn, không dài hơn bản gốc quá 10%:
{json.dumps(voice, ensure_ascii=False, indent=1)}

Yêu cầu:
- Mỗi ngôn ngữ viết {hooks_per_lang} phương án caption hook khác nhau (để A/B test); caption ngắn, tối đa ~45 ký tự/câu.
- Giữ nguyên không dịch: {keep}.
- Không thêm claim tuyệt đối ("tốt nhất", "miễn phí 100%") nếu bản gốc không có.
- CHỈ trả về JSON đúng dạng sau, không giải thích:
{{"<mã ngôn ngữ>": {{"hooks": [["<caption 1>", ...], ...], "voice": ["<câu thoại 1>", ...]}}}}
Mỗi phần tử của "hooks" là một phương án, gồm {len(caps)} caption theo đúng thứ tự; "voice" có đúng {len(voice)} câu."""


def parse_reply(text: str) -> dict[str, dict]:
    """Lấy khối JSON đầu tiên trong câu trả lời (Claude đôi khi bọc trong ```json)."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("Không thấy JSON trong nội dung dán vào — hãy dán nguyên câu trả lời của Claude.")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON bị lỗi ở dòng {e.lineno}: {e.msg}") from e
    if not isinstance(data, dict):
        raise ValueError("JSON phải là object theo mã ngôn ngữ")
    out: dict[str, dict] = {}
    for code, v in data.items():
        get_lang(code)
        hooks = v.get("hooks") or []
        hooks = [[h] if isinstance(h, str) else list(h) for h in hooks]
        out[code] = {"hooks": [[str(x) for x in h] for h in hooks], "voice": [str(x) for x in v.get("voice") or []]}
    return out


def api_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def translate_with_api(prompt: str) -> str:
    """Gọi Claude API (chỉ khi máy chủ đặt ANTHROPIC_API_KEY). Trả về văn bản trả lời."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("Máy chủ chưa cấu hình ANTHROPIC_API_KEY — dùng cách dán prompt sang Claude.")
    body = json.dumps({"model": os.environ.get("VIDEODUBBER_CLAUDE_MODEL", "claude-sonnet-4-5"), "max_tokens": 4000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 — URL cố định https
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ValueError(f"Claude API báo lỗi {e.code} — kiểm tra API key/hạn mức.") from e
    except urllib.error.URLError as e:
        raise ValueError(f"Không gọi được Claude API: {e.reason}") from e
    return "".join(b.get("text", "") for b in data.get("content", []))
