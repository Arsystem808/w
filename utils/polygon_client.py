import os, datetime as dt
from typing import Optional
import requests
import pandas as pd

BASE = "https://api.polygon.io"
API_KEY = os.getenv("POLYGON_API_KEY", "").strip()

class PolygonError(RuntimeError):
    pass

def _agg_url(ticker: str) -> str:
    # Crypto pairs must start with X:
    if ":" in ticker:
        return f"{BASE}/v2/aggs/ticker/{ticker}/range/1/day/{{start}}/{{end}}"
    else:
        return f"{BASE}/v2/aggs/ticker/{ticker}/range/1/day/{{start}}/{{end}}"

def fetch_daily(ticker: str, days: int = 420) -> Optional[pd.DataFrame]:
    if not API_KEY:
        raise PolygonError("POLYGON_API_KEY отсутствует в окружении.")
    end = dt.datetime.utcnow().date()
    start = end - dt.timedelta(days=days+5)
    url = _agg_url(ticker).format(start=start.isoformat(), end=end.isoformat())
    params = {"adjusted":"true", "apiKey": API_KEY, "limit": 50000}
    r = requests.get(url, params=params, timeout=30)
    if r.status_code == 429:
        raise PolygonError("Polygon вернул 429 (rate limit). Попробуй через минуту.")
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    if not results:
        raise PolygonError("Polygon не вернул свечи (results пуст).")
    rows = []
    for it in results:
        ts = dt.datetime.utcfromtimestamp(it["t"]/1000).date().isoformat()
        rows.append({
            "date": ts,
            "open": float(it["o"]),
            "high": float(it["h"]),
            "low": float(it["l"]),
            "close": float(it["c"]),
            "volume": float(it.get("v", 0.0)),
        })
    df = pd.DataFrame(rows).drop_duplicates(subset=["date"]).reset_index(drop=True)
    return df
