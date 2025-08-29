from __future__ import annotations
import os, math
import datetime as dt
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Literal

import pandas as pd
import numpy as np

from utils.polygon_client import fetch_daily

# --------- Config / Types

Horizon = Literal["short","mid","long"]

class StrategyError(RuntimeError):
    pass

@dataclass
class Decision:
    stance: Literal["BUY","SHORT","WAIT"]
    entry: Optional[Tuple[float,float]]  # (low, high) zone or None
    target1: Optional[float]
    target2: Optional[float]
    stop: Optional[float]
    meta: Dict

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = np.where(delta > 0, delta, 0.0)
    down = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(up, index=series.index).ewm(alpha=1/period, adjust=False).mean()
    roll_down = pd.Series(down, index=series.index).ewm(alpha=1/period, adjust=False).mean()
    rs = roll_up / (roll_down + 1e-12)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = np.maximum(df["high"]-df["low"], np.maximum(abs(df["high"]-prev_close), abs(df["low"]-prev_close)))
    atr = pd.Series(tr).ewm(alpha=1/period, adjust=False).mean()
    return atr

def _heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    ha = pd.DataFrame(index=df.index)
    ha["close"] = (df["open"] + df["high"] + df["low"] + df["close"]) / 4.0
    ha["open"] = 0.0
    ha.iloc[0, ha.columns.get_loc("open")] = (df["open"].iloc[0] + df["close"].iloc[0]) / 2.0
    for i in range(1, len(ha)):
        ha.iloc[i, ha.columns.get_loc("open")] = (ha["open"].iloc[i-1] + ha["close"].iloc[i-1]) / 2.0
    ha["green"] = ha["close"] > ha["open"]
    return ha

def _macd_hist(close: pd.Series, fast=12, slow=26, signal=9) -> pd.Series:
    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)
    macd = ema_fast - ema_slow
    sig = _ema(macd, signal)
    hist = macd - sig
    return hist

def _streak_bool(series_bool: pd.Series) -> int:
    """Length of the last True/False streak (by sign)."""
    if len(series_bool) == 0:
        return 0
    last = series_bool.iloc[-1]
    cnt = 1
    for val in reversed(series_bool.iloc[:-1]):
        if val == last:
            cnt += 1
        else:
            break
    return cnt if last else -cnt

def _fib_pivots(prev_high: float, prev_low: float, prev_close: float) -> Dict[str,float]:
    rng = prev_high - prev_low
    P = (prev_high + prev_low + prev_close) / 3.0
    R1 = P + 0.382*rng
    R2 = P + 0.618*rng
    R3 = P + 1.000*rng
    S1 = P - 0.382*rng
    S2 = P - 0.618*rng
    S3 = P - 1.000*rng
    return {"P":P,"R1":R1,"R2":R2,"R3":R3,"S1":S1,"S2":S2,"S3":S3}

def _period_bounds(h: Horizon, last_date: pd.Timestamp) -> Tuple[pd.Timestamp, pd.Timestamp, str]:
    # Use previous complete period
    if h == "short":
        # previous ISO week (Mon..Fri range inferred from dailies)
        end = (last_date - pd.Timedelta(days=last_date.weekday()+1))  # last Sunday
        start = end - pd.Timedelta(days=6)
        return pd.Timestamp(start.date()), pd.Timestamp(end.date()), "week"
    if h == "mid":
        first_of_this_month = last_date.replace(day=1)
        end = first_of_this_month - pd.Timedelta(days=1)
        start = end.replace(day=1)
        return pd.Timestamp(start.date()), pd.Timestamp(end.date()), "month"
    # long
    first_of_this_year = last_date.replace(month=1, day=1)
    end = first_of_this_year - pd.Timedelta(days=1)
    start = end.replace(month=1, day=1)
    return pd.Timestamp(start.date()), pd.Timestamp(end.date()), "year"

def analyze_ticker(ticker: str, horizon: Horizon, for_diagnostics: bool=False) -> Dict:
    if not ticker:
        raise StrategyError("Тикер не указан.")
    # fetch recent dailies
    days = 420 if horizon != "long" else 900
    df = fetch_daily(ticker, days=days)
    if df is None or df.empty:
        raise StrategyError("Не удалось загрузить свечи с Polygon.")
    df = df.sort_values("date").reset_index(drop=True)
    last_close = float(df["close"].iloc[-1])
    last_date = pd.to_datetime(df["date"].iloc[-1])

    # indicators
    ha = _heikin_ashi(df)
    ha_streak = _streak_bool(ha["green"])
    macd_h = _macd_hist(df["close"])
    macd_sign = macd_h > 0
    macd_streak = _streak_bool(macd_sign)
    rsi_val = float(_rsi(df["close"]).iloc[-1])
    atr_val = float(_atr(df).iloc[-1])

    # thresholds
    ha_need = {"short":4, "mid":5, "long":6}[horizon]
    macd_need = {"short":4, "mid":6, "long":8}[horizon]
    tol = {"short":0.008, "mid":0.010, "long":0.012}[horizon]

    # pivots by previous period
    start, end, pframe = _period_bounds(horizon, pd.to_datetime(df["date"].iloc[-1]))
    prev = df[(pd.to_datetime(df["date"])>=start)&(pd.to_datetime(df["date"])<=end)]
    if prev.empty:
        # fallback: take last N bars approximating period
        fallback_n = {"week":5,"month":21,"year":252}[pframe]
        prev = df.tail(fallback_n)
    piv = _fib_pivots(prev["high"].max(), prev["low"].min(), prev["close"].iloc[-1])

    # helper for proximity
    def near(level: float) -> bool:
        return abs(last_close - level)/max(1e-6, level) <= tol

    # Overheat near roof (R2/R3) OR Oversold near floor (S2/S3)
    near_R2 = near(piv["R2"]) or last_close > piv["R2"]
    near_R3 = near(piv["R3"]) or last_close > piv["R3"]
    near_S2 = near(piv["S2"]) or last_close < piv["S2"]
    near_S3 = near(piv["S3"]) or last_close < piv["S3"]

    long_zone = (near_S2 or near_S3) and (ha_streak <= -ha_need or macd_streak <= -macd_need)
    short_zone = (near_R2 or near_R3) and (ha_streak >= ha_need or macd_streak >= macd_need)

    meta = {
        "price": last_close,
        "last_date": str(last_date.date()),
        "piv_frame": pframe,
        "ha_streak": int(ha_streak),
        "macd_streak": int(macd_streak),
        "rsi": float(rsi_val),
        "atr": float(atr_val),
        "near_level": "R3" if near_R3 else ("R2" if near_R2 else ("S3" if near_S3 else ("S2" if near_S2 else "None"))),
    }

    # default decision
    stance = "WAIT"
    entry = None
    t1 = t2 = stp = None

    if short_zone:
        if near_R3:
            stance = "SHORT"
            entry = (piv["R3"]*(1-0.003), piv["R3"]*(1+0.003))
            t1 = piv["R2"]
            t2 = piv["P"]
            stp = piv["R3"]*(1+1.2*tol)
        else:
            stance = "SHORT"
            entry = (piv["R2"]*(1-0.004), piv["R2"]*(1+0.004))
            t1 = (piv["P"] + piv["S1"])/2.0
            t2 = piv["S1"]
            stp = piv["R2"]*(1+1.5*tol)

    elif long_zone:
        if near_S3:
            stance = "BUY"
            entry = (piv["S3"]*(1-0.003), piv["S3"]*(1+0.003))
            t1 = piv["S2"]
            t2 = piv["P"]
            stp = piv["S3"]*(1-1.2*tol)
        else:
            stance = "BUY"
            entry = (piv["S2"]*(1-0.004), piv["S2"]*(1+0.004))
            t1 = (piv["P"] + piv["R1"])/2.0
            t2 = piv["R1"]
            stp = piv["S2"]*(1-1.5*tol)
    else:
        stance = "WAIT"
        # optional "alternative" entry near mid supports
        if last_close < piv["P"]:
            entry = (piv["S1"]*(1-0.004), piv["S1"]*(1+0.004))
            t1 = piv["P"]
            t2 = piv["R1"]
            stp = piv["S2"]*(1-1.2*tol)
        else:
            entry = (piv["R1"]*(1-0.004), piv["R1"]*(1+0.004))
            t1 = piv["P"]
            t2 = piv["S1"]
            stp = piv["R2"]*(1+1.2*tol)

    dec = Decision(stance=stance, entry=entry, target1=t1, target2=t2, stop=stp, meta=meta)
    if for_diagnostics:
        return dec.__dict__
    # hide internal numbers from main text (they remain in diagnostics expander)
    return dec.__dict__