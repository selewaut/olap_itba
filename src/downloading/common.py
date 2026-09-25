"""HTTP session, GET y grabado de CSV crudo. Compartido por los clientes."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

USER_AGENT = "olap-itba-dw/0.1"
TIMEOUT = 30


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def get(url: str, sess: requests.Session | None = None, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", TIMEOUT)
    if sess is None:
        kwargs.setdefault("headers", {"User-Agent": USER_AGENT})
        r = requests.get(url, **kwargs)
    else:
        r = sess.get(url, **kwargs)
    r.raise_for_status()
    return r


def save_csv(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path
