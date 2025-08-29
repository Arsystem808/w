# CapinteL‑Q — Streamlit (Polygon‑only)

Минимальный рабочий MVP под твою стратегию:

- Источник котировок: **Polygon.io** (аггрегированные дневные свечи).
- Без CSV и без Yahoo.
- Пивоты: **Fibonacci**, многопериодные (week/month/year) — используем *прошлый* период по выбранному горизонту.
- Heikin Ashi — оценка серии цвета.
- MACD‑hist — длительность серии.
- RSI (14), ATR (14) — для фильтра/масштабирования.
- Текст «человеческий», без раскрытия внутренних уровней. Технические числа — только в *Диагностике*.

## Быстрый старт (локально)

1) Установи переменную окружения с ключом Polygon:

macOS / Linux
```bash
export POLYGON_API_KEY="ВСТАВЬ_ТУТ_КЛЮЧ"
```

Windows Powershell
```powershell
$env:POLYGON_API_KEY="ВСТАВЬ_ТУТ_КЛЮЧ"
```

2) Установи зависимости и запусти:
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud
Добавь секрет `POLYGON_API_KEY` в **App secrets**, Python 3.11+.