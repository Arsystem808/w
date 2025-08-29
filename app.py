import os
import datetime as dt
import pandas as pd
import streamlit as st

from core_strategy import analyze_ticker, Horizon, StrategyError
from narrator import humanize

st.set_page_config(page_title="CapinteL‑Q — Аналитик рынков (Polygon)", page_icon="📈", layout="centered")

st.markdown("# CapinteL‑Q — Анализ рынков\n**Источник данных:** Polygon.io  •  без CSV, без Yahoo\n")

# --- Controls
ticker = st.text_input("Тикер:", placeholder="QQQ, AAPL, X:BTCUSD", value="QQQ").strip().upper()
horizons = {
    "Трейд (1–5 дней)": "short",
    "Среднесрок (1–4 недели)": "mid",
    "Долгосрок (1–6 месяцев)": "long",
}
h_key = st.selectbox("Горизонт:", list(horizons.keys()), index=1)
horizon = horizons[h_key]

if st.button("Проанализировать", use_container_width=True):
    try:
        res = analyze_ticker(ticker, horizon)
        st.markdown(f"### {ticker} — текущая цена: ${res['meta']['price']:.2f}")
        st.markdown("## 🧠 Результат:")
        st.markdown(humanize(ticker, res))

    except StrategyError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Неожиданная ошибка: {e}")

with st.expander("🛠 Диагностика"):
    st.write("Показываем ключевые расчёты для проверки (скрыто от пользователя по умолчанию).")
    try:
        diag = analyze_ticker(ticker or "QQQ", horizon, for_diagnostics=True)
        st.json({
            "horizon": horizon,
            "price": diag["meta"]["price"],
            "last_date": diag["meta"]["last_date"],
            "piv_frame": diag["meta"]["piv_frame"],
            "heikin_streak": diag["meta"]["ha_streak"],
            "macd_streak": diag["meta"]["macd_streak"],
            "rsi": diag["meta"]["rsi"],
            "atr": diag["meta"]["atr"],
            "near_level": diag["meta"]["near_level"],
        })
    except Exception as e:
        st.write(f"Диагностика недоступна: {e}")

st.caption("CapinteL‑Q говорит «человеческим» языком и не раскрывает внутренние формулы.")