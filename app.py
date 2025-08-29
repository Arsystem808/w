import os
import streamlit as st
from core_strategy import analyze_ticker

st.set_page_config(page_title="CapinteL-Q — Анализ рынков (Polygon)", page_icon="🧭", layout="centered")

st.markdown("## CapinteL-Q — Анализ рынков\nИсточник данных: Polygon.io • без CSV, без Yahoo")

with st.form("frm"):
    ticker = st.text_input("Тикер:", value="QQQ").strip()
    horizon = st.selectbox(
        "Горизонт:",
        options=[("short", "Трейд (1–5 дней)"),
                 ("mid",   "Среднесрок (1–4 недели)"),
                 ("long",  "Долгосрок (1–6 месяцев)")],
        index=2,  # default long
        format_func=lambda x: x[1]
    )[0]
    run = st.form_submit_button("Проанализировать")

if run:
    if not ticker:
        st.error("Укажи тикер.")
        st.stop()

    try:
        res = analyze_ticker(ticker, horizon)
    except Exception as e:
        st.error(f"Ошибка: {e}")
        st.stop()

    st.markdown(f"### {ticker.upper()} — текущая цена: **${res['price']:.2f}**")
    st.subheader("🧠 Результат:")
    st.markdown(res["text"])
    if res.get("alt_text"):
        st.markdown(res["alt_text"])

st.caption("CapinteL-Q говорит «человеческим» языком и не раскрывает внутренние формулы.")

     
