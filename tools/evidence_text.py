"""Small, offline text guards shared by web extraction and citation selection."""
import html
import re

_LINK = re.compile(r'(?P<image>!)?\[(?P<label>[^\[\]]*)\]\((?:[^()\s]|\([^()]*\))*(?:\s+"[^"]*")?\)')
_NAVIGATION = {
    "home", "menu", "navigation", "main navigation", "login", "log in", "sign in", "sign up",
    "subscribe", "subscription", "search", "share", "print", "facebook", "twitter", "instagram",
    "linkedin", "youtube", "privacy", "privacy policy", "terms", "terms of use", "contact", "about",
    "news", "politics", "business", "economy", "markets", "industry", "technology", "tech",
    "culture", "sports", "entertainment", "world", "society", "national", "opinion", "lifestyle",
    "전체메뉴", "메뉴", "홈", "로그인", "회원가입", "검색", "구독", "공유", "인쇄", "기사공유",
    "정치", "경제", "산업", "사회", "국제", "세계", "문화", "스포츠", "연예", "오피니언",
    "라이프", "뉴스", "최신뉴스", "주요뉴스", "많이본뉴스", "관련기사", "이전기사", "다음기사",
    "개인정보처리방침", "이용약관", "고객센터", "회사소개", "제보", "취소", "닫기", "로고", "logo",
}
_FINANCIAL_UNIT = re.compile(r'\d\s*(?:%|원|주|억|조|달러|KRW|USD|EUR|JPY|CNY|billion|million)', re.I)


def _visible_text(text: str) -> str:
    value = text
    for _ in range(4):
        cleaned = _LINK.sub(lambda match: "" if match["image"] else match["label"], value)
        if cleaned == value:
            break
        value = cleaned
    value = re.sub(r'\[([^\]]+)\]\[[^\]]*\]', r'\1', value)
    value = re.sub(r'</?[A-Za-z][^>]*>', '', value)
    return html.unescape(value).strip()


def is_navigation_text(text: str) -> bool:
    """Reject obvious page chrome, while retaining factual inline/link labels."""
    if not isinstance(text, str):
        return True
    visible = _visible_text(text)
    label = re.sub(r'[\W_]+', ' ', visible.casefold()).strip()
    compact = label.replace(' ', '')
    if not visible or not label or re.fullmatch(r'(?:https?://|www\.)\S+', visible, re.I):
        return True
    if label in _NAVIGATION or compact in _NAVIGATION:
        return True
    if re.match(r'^(?:skip(?:to)?(?:main)?(?:content|navigation)|skipnav|본문바로가기|메뉴바로가기|본문으로)', compact):
        return True
    if re.match(r'^(?:[©ⓒ]|copyright\b|all rights reserved|무단\s*(?:전재|복제).{0,30}금지)', visible, re.I):
        return True
    remainder = text
    for _ in range(4):
        remainder = _LINK.sub('', remainder)
    link_only = not remainder.strip(' \t\r\n*_-|[]')
    return bool(link_only and len(visible) < 40 and not _FINANCIAL_UNIT.search(visible)
                and not re.search(r'[.!?。]$', visible))


def clean_article_text(markdown: str) -> str:
    """Remove chrome and URLs; preserve prose, numeric values, and table rows."""
    lines = []
    seen = set()
    for raw in markdown.splitlines():
        if re.match(r'^\s{0,3}#\s|^\s*\[[^\]]+\]:', raw) or is_navigation_text(raw):
            continue
        raw = re.sub(r'^\s{0,3}#{2,6}\s+', '', raw)
        text = re.sub(r'[ \t]+', ' ', _visible_text(raw)).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        lines.append(text)
    return '\n\n'.join(lines)
