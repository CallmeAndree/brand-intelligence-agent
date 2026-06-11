from urllib.parse import urlparse

# Map domain (đã bỏ tiền tố "www.") -> tên nền tảng hiển thị.
# Suy luận thuần từ URL, không gọi LLM. Mở rộng bằng cách thêm dòng vào dict.
_DOMAIN_TO_PLATFORM: dict[str, str] = {
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "fb.watch": "Facebook",
    "m.facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "tiktok.com": "TikTok",
    "threads.net": "Threads",
    "threads.com": "Threads",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "twitter.com": "X",
    "x.com": "X",
    "linkedin.com": "LinkedIn",
    "t.me": "Telegram",
    "telegram.me": "Telegram",
    "reddit.com": "Reddit",
    "voz.vn": "Voz",
    "tinhte.vn": "Tinh tế",
    "webtretho.com": "Webtretho",
}


def platform_from_url(url: str | None) -> str | None:
    """Suy ra nền tảng mạng xã hội từ URL của mention (Facebook, TikTok, ...).

    Trả về None nếu url rỗng/không hợp lệ hoặc domain chưa được map.
    """
    if not url or not url.strip():
        return None
    host = urlparse(url.strip()).netloc.lower()
    if not host:
        return None
    if ":" in host:  # bỏ cổng nếu có
        host = host.split(":", 1)[0]
    # Khớp cả subdomain (vt.tiktok.com, m.facebook.com, l.instagram.com...) bằng suffix domain.
    for domain, platform in _DOMAIN_TO_PLATFORM.items():
        if host == domain or host.endswith("." + domain):
            return platform
    return None
