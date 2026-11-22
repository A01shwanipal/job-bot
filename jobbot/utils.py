import functools
import html
import logging
import re
import time
from datetime import datetime, timezone

import requests
from dateutil import parser as dtparser

log = logging.getLogger(__name__)
UA = "PersonalJobSearchBot/1.0 (single-user job search; polite rate)"


class NotFound(Exception):
    pass


def retry(times: int = 3, backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """Retry with exponential backoff (2s, 4s, ...)."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            for attempt in range(1, times + 1):
                try:
                    return fn(*a, **kw)
                except exceptions as e:
                    if attempt == times:
                        raise
                    wait = backoff ** attempt
                    log.warning("%s failed (%s); retrying in %.0fs (%d/%d)", fn.__name__, e, wait, attempt, times - 1)
                    time.sleep(wait)
        return wrapper
    return deco


@retry(times=3, backoff=2, exceptions=(requests.RequestException,))
def get_json(url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 25):
    r = requests.get(url, params=params, headers={"User-Agent": UA, **(headers or {})}, timeout=timeout)
    if r.status_code == 404:
        raise NotFound(url)
    r.raise_for_status()
    return r.json()


def parse_dt(v) -> datetime | None:
    if v in (None, ""):
        return None
    try:
        if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
            n = float(v)
            n = n / 1000 if n > 1e11 else n
            return datetime.fromtimestamp(n, tz=timezone.utc)
        d = dtparser.parse(str(v))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def iso(d: datetime | None) -> str | None:
    return d.isoformat(timespec="seconds") if d else None


def clean_html(s: str) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"<(script|style).*?>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()
