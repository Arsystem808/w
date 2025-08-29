import os
import datetime as dt
import requests
import pandas as pd

API = os.getenv("POLYGON_API_KEY", "").strip()
BASE = "https://api.polygon.io"

def _normalize_ticker(t: str) -> str:
    t = t.upper().strip()
    # поддержка «BTCUSD» как «X:BTCUSD»
    if t.endswith("USD") and not t.startswith("X:") and len(t) > 3:
        return "X:" + t
    return t

def fetch_daily(ticker: str, days: int = 520) -> pd.DataFrame:
    if not API:
        raise RuntimeError("POLYGON_API_KEY отсутствует (задай в Secrets/ENV).")
    t = _normalize_ticker(ticker)
    end = dt.date.today()
    start = end - dt.timedelta(days=days + 10)

    url = f"{BASE}/v2/aggs/ticker/{t}/range/1/day/{start}/{end}"
    params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": API}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    js = r.json()
    if not js or "results" not in js or not js["results"]:
        raise RuntimeError("Polygon не вернул данные.")

    rows = []
    for o in js["results"]:
        rows.append(
            {
                "date": dt.datetime.utcfromtimestamp(o["t"]/1000).date(),
                "open": float(o["o"]),
                "high": float(o["h"]),
                "low":  float(o["l"]),
                "close":float(o["c"]),
                "volume": float(o.get("v", 0.0)),
            }
        )
    df = pd.DataFrame(rows).sort_values("date")
    df = df.set_index(pd.to_datetime(df["date"]))
    df = df.drop(columns=["date"])
    return df
