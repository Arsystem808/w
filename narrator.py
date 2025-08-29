import random

def _fmt_zone(z):
    if not z: return "—"
    a, b = z
    lo, hi = sorted([a, b])
    return f"{lo:.2f}…{hi:.2f}" if hi - lo >= 0.01 else f"{lo:.2f}"

def _plan_line(tag, plan):
    if plan["stance"] == "WAIT":
        return "✅ Базовый план: **WAIT** — на текущих вход не даёт преимущества. Ждём более выгодной цены или подтверждения."
    icon = "🟢 Покупка" if plan["stance"] == "BUY" else "🔴 Шорт"
    lead = "✅ Базовый план" if tag == "base" else "🧭 Альтернатива"
    entry = _fmt_zone(plan["entry"])
    t1 = f"{plan['t1']:.2f}" if plan["t1"] else "—"
    t2 = f"{plan['t2']:.2f}" if plan["t2"] else "—"
    stop = f"{plan['stop']:.2f}" if plan["stop"] else "—"
    return f"{lead}: **{icon}** → вход: {entry} | цели: {t1} / {t2} | защита/стоп: {stop}"

def humanize(ticker: str, price: float, horizon: str, base, alt):
    horizon_ru = {
        "short": "Трейд (1–5 дней)",
        "mid":   "Среднесрок (1–4 недели)",
        "long":  "Долгосрок (1–6 месяцев)"
    }.get(horizon, horizon)

    head = f"📌 {ticker.upper()} — **{horizon_ru}**\n"
    base_line = _plan_line("base", base)

    alt_line = ""
    if alt and (alt["stance"] != "WAIT" or base["stance"] != alt["stance"]):
        alt_line = _plan_line("alt", alt)

    tails = [
        "Работаем спокойно: если сценарий ломается — быстро выходим и ждём новую формацию.",
        "Без суеты: берём там, где перевес наш. Если нет — ждём.",
        "Ключевое — качество точки входа, не скорость."
    ]
    tail = "⚠️ " + random.choice(tails)

    text = head + base_line
    alt_text = (alt_line + "\n\n" + tail) if alt_line else ("\n\n" + tail)
    return text, alt_text
