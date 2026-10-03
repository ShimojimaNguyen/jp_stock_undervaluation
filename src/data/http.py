"""HTTP dùng chung cho mọi fetcher: robots.txt đọc thật, User-Agent bắt buộc, giãn nhịp."""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlsplit


def robots_policy(url: str, user_agent: str, session) -> tuple[bool, float | None]:
    """→ (được phép?, crawl-delay nguồn tự khai). 404 = không hạn chế; lỗi khác = TỪ CHỐI."""
    parts = urlsplit(url)
    r = session.get(f"{parts.scheme}://{parts.netloc}/robots.txt",
                    headers={"User-Agent": user_agent}, timeout=20)
    if r.status_code == 404:
        return True, None
    if r.status_code != 200:
        return False, None
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(r.text.splitlines())
    delay = rp.crawl_delay(user_agent)
    return rp.can_fetch(user_agent, url), (float(delay) if delay is not None else None)


class Throttle:
    """Giãn tối thiểu `delay_s` giữa hai request (≥ crawl-delay nguồn tự khai)."""

    def __init__(self, delay_s: float):
        self.delay_s = delay_s
        self._last = 0.0

    def wait(self) -> None:
        gap = time.monotonic() - self._last
        if gap < self.delay_s:
            time.sleep(self.delay_s - gap)
        self._last = time.monotonic()
