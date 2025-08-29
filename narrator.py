from __future__ import annotations
import random

def _fmt_range(rng):
    if not rng: return "—"
    lo, hi = rng
    return f"{lo:.2f}…{hi:.2f}"

def humanize(ticker: str, res: dict) -> str:
    stance = res.get("stance")
    price = res["meta"].get("price")
    parts = [f"📊 {ticker} — текущая цена: **{price:.2f}**."]
    if stance == "BUY":
        parts.append("✅ Базовый план: **LONG** — берём аккуратно у поддержки.")
    elif stance == "SHORT":
        parts.append("✅ Базовый план: **SHORT** — работаем от «крыши», без суеты.")
    else:
        parts.append("✅ Базовый план: **WAIT** — на текущих входа нет, дожидаемся лучшей формации.")
    # keep numbers abstract: show only zones, not pivot names
    if res.get("entry"):
        parts.append(f"🎯 Зона входа: {_fmt_range(res['entry'])}")
    if res.get("target1"):
        parts.append(f"📌 Цели: {res['target1']:.2f}" + (f" / {res['target2']:.2f}" if res.get('target2') else ""))
    if res.get("stop"):
        parts.append(f"🛡 Защита/стоп: {res['stop']:.2f}")
    parts.append("⚠️ Если сценарий ломается — выходим быстро и ждём новую формацию.")
    return "\n".join(parts)