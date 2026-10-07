"""HTTP dùng chung cho mọi fetcher: robots.txt đọc thật, User-Agent bắt buộc, giãn nhịp."""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlsplit


def robots_policy(url: str, user_agent: str, session) -> tuple[bool, float | None, str]:
    """→ (được phép?, crawl-delay nguồn tự khai, lý do). 404 = không hạn chế; lỗi khác = TỪ CHỐI.

    `lý do` luôn nói rõ HTTP status / dòng robots nào — một lần từ chối không lý do
    (lần chạy CI đầu tiên) không phân biệt được 'site cấm' với 'site chặn IP'.
    """
    parts = urlsplit(url)
    robots = f"{parts.scheme}://{parts.netloc}/robots.txt"
    r = session.get(robots, headers={"User-Agent": user_agent}, timeout=20)
    if r.status_code == 404:
        return True, None, f"{robots}: 404 (không tuyên bố hạn chế)"
    if r.status_code != 200:
        return False, None, f"{robots}: HTTP {r.status_code} — không đọc được robots"
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(r.text.splitlines())
    delay = rp.crawl_delay(user_agent)
    ok = rp.can_fetch(user_agent, url)
    why = f"{robots}: 200, can_fetch({urlsplit(url).path})={ok}, crawl-delay={delay}"
    return ok, (float(delay) if delay is not None else None), why


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
