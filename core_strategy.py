import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
from polygon_client import fetch_daily
from narrator import humanize

# ---------- утилиты теханализа ----------

def heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    ha = pd.DataFrame(index=df.index, columns=["ha_open","ha_high","ha_low","ha_close"], dtype=float)
    ha["ha_close"] = (df["open"] + df["high"] + df["low"] + df["close"]) / 4.0
    ha["ha_open"] = np.nan
    # старт
    ha.iloc[0, ha.columns.get_loc("ha_open")] = (df["open"].iloc[0] + df["close"].iloc[0]) / 2.0
    # рекурсия
    for i in range(1, len(df)):
        ha.iat[i, 0] = (ha.iat[i-1, 0] + ha.iat[i-1, 3]) / 2.0  # ha_open
    ha["ha_high"] = df[["high", "open", "close"]].max(axis=1)
    ha["ha_low"]  = df[["low",  "open", "close"]].min(axis=1)
    return ha

def macd_hist(close: pd.Series, fast=12, slow=26, signal=9) -> pd.Series:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal, adjust=False).mean()
    return macd - sig

def atr(df: pd.DataFrame, n=14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low).abs(),
                    (high - prev_close).abs(),
                    (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

# ---------- пивоты (Fibonacci) с прошлого периода ----------
def fib_pivots(h, l, c) -> Dict[str, float]:
    p = (h + l + c) / 3.0
    rng = (h - l)
    r1 = p + 0.382 * rng
    r2 = p + 0.618 * rng
    r3 = p + 1.000 * rng
    s1 = p - 0.382 * rng
    s2 = p - 0.618 * rng
    s3 = p - 1.000 * rng
    return {"P": p, "R1": r1, "R2": r2, "R3": r3, "S1": s1, "S2": s2, "S3": s3}

def previous_period_pivots(df: pd.DataFrame, horizon: str) -> Dict[str,float]:
    last = df.index.max()
    if horizon == "short":
        # прошлая календарная неделя
        wk = (last - pd.offsets.Week(weekday=0)).normalize()  # понедельник текущей
        prev_week_end = wk - pd.Timedelta(days=1)
        prev_week_start = prev_week_end - pd.Timedelta(days=6)
        seg = df.loc[(df.index.date >= prev_week_start.date()) & (df.index.date <= prev_week_end.date())]
    elif horizon == "mid":
        # прошлый календарный месяц
        first_cur = last.replace(day=1)
        prev_end = first_cur - pd.Timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        seg = df.loc[(df.index.date >= prev_start.date()) & (df.index.date <= prev_end.date())]
    else:
        # прошлый календарный год
        prev_year = (last.year - 1)
        seg = df[df.index.year == prev_year]

    if seg.empty:
        # fallback: возьмём последние 20 дней
        seg = df.tail(20)
    h, l, c = seg["high"].max(), seg["low"].min(), seg["close"].iloc[-1]
    return fib_pivots(h, l, c)

# ---------- решение по стратегии ----------
def decide(price: float, piv: Dict[str,float], ctx: Dict, horizon: str) -> Tuple[Dict, Dict]:
    """
    Возвращает (base, alt) — каждый: dict(stence, entry:(lo,hi), t1, t2, stop)
    Логика:
      • У крыши (>=R2) при «усталости» — базово WAIT; альтернатива SHORT от R2/R3.
      • У дна (<=S2) — базово BUY от S2/S3.
      • В середине — WAIT, альтернатива малым объёмом к P/R1 или P/S1.
    """
    # контекст
    fatigue = ctx["fatigue"]       # True/False по MACD/HA
    a = ctx["atr"]
    tol = {"short":0.006, "mid":0.010, "long":0.012}[horizon]  # допуск ~0.6%…1.2%

    def plan(stance, entry=None, t1=None, t2=None, stop=None):
        return {"stance": stance, "entry": entry, "t1": t1, "t2": t2, "stop": stop}

    # 1) Верхняя зона
    if price >= piv["R2"]*(1 - tol):
        if fatigue:
            # альт: шорт от R2/R3
            entry_lo = max(price, piv["R2"]*0.999)
            entry_hi = max(entry_lo, piv["R3"])
            alt = plan("SHORT", (entry_lo, entry_hi), t1=piv["R2"], t2=piv["P"], stop=piv["R3"] + 0.8*a)
            base = plan("WAIT")
            return base, alt
        else:
            # импульс свежий — ничего не ловим
            return plan("WAIT"), plan("SHORT", (piv["R2"], piv["R3"]), t1=piv["R2"], t2=piv["P"], stop=piv["R3"] + 0.8*a)

    # 2) Нижняя зона
    if price <= piv["S2"]*(1 + tol):
        entry_hi = min(price, piv["S2"]*1.001)
        entry_lo = min(entry_hi, piv["S3"])
        base = plan("BUY", (entry_lo, entry_hi), t1=piv["P"], t2=piv["R1"], stop=piv["S3"] - 0.8*a)
        alt = plan("WAIT")
        return base, alt

    # 3) Середина — предпочтение WAIT, можно аккуратно от P
    base = plan("WAIT")
    if price < piv["P"]:
        # вверх к R1
        alt = plan("BUY", (min(price, piv["P"]), piv["R1"]), t1=piv["R1"], t2=piv["R2"], stop=piv["S1"] - 0.8*a)
    else:
        # вниз к S1
        alt = plan("SHORT", (max(price, piv["P"]), piv["S1"]), t1=piv["P"], t2=piv["S1"], stop=piv["R1"] + 0.8*a)
    return base, alt

def _context(df: pd.DataFrame) -> Dict:
    # последние 120 баров для индикаторов
    tail = df.tail(120).copy()
    ha = heikin_ashi(tail)
    hist = macd_hist(tail["close"])
    atr14 = atr(tail)
    # «усталость»: длинная серия HA и/или затухание гистограммы
    ha_green = (ha["ha_close"].diff() > 0).astype(int)
    ha_red   = (ha["ha_close"].diff() < 0).astype(int)
    # макс длина последних одноцветных
    def max_streak(bs):
        s, best = 0, 0
        for v in bs[::-1]:
            if v: s += 1; best = max(best, s)
            else: break
        return best
    green_streak = max_streak(list(ha_green.values))
    red_streak   = max_streak(list(ha_red.values))
    # замедление MACD: последние 4 бара по модулю уменьшаются
    h = hist.dropna().tail(6).values
    slowing_up = len(h)>=4 and all(abs(h[-i]) < abs(h[-i-1]) for i in range(1,4))
    fatigue = (green_streak >= 5 or red_streak >= 5) or slowing_up

    return {
        "fatigue": bool(fatigue),
        "atr": float(atr14.dropna().iloc[-1])
    }

def analyze_ticker(ticker: str, horizon: str) -> Dict:
    df = fetch_daily(ticker, days=560)
    df = df.dropna().copy()

    piv = previous_period_pivots(df, horizon)
    price = float(df["close"].iloc[-1])
    ctx = _context(df)

    base, alt = decide(price, piv, ctx, horizon)

    # человеко-читаемый текст
    text, alt_text = humanize(ticker, price, horizon, base, alt)

    return {
        "price": price,
        "horizon": horizon,
        "base": base,
        "alt": alt,
        "text": text,
        "alt_text": alt_text
    }
