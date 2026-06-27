# 🥇 GoldBot Pro v6 — XAU/USD Scalping Bot

Strategy: Mayank Singh Scalping Method
EMA 9/15 + 30° Slope + Pin Bar/Engulfing + 1:2 RR

---

## 📁 Files

```
gold-scalping-bot/
├── bot.py           # Signal engine (main strategy)
├── app.py           # Flask server
├── backtest.py      # Historical backtest engine
├── tracker.py       # Real-time signal tracker
├── index.html       # Live signal dashboard
├── backtest.html    # Backtest dashboard
├── tracker.html     # Tracker dashboard
├── requirements.txt
└── README.md
```

---

## 🧠 Strategy — Mayank Singh Method

| Layer | Rule |
|---|---|
| EMA 9 + 15 | 9 above 15 = uptrend, 9 below 15 = downtrend |
| 30° Slope | EMA slope must be 30°+ — flat market skip |
| Candle Pattern | Pin Bar / Big Bar / Engulfing only |
| Entry Trigger | Candle touches EMA zone |
| Stop Loss | Entry candle Low (buy) or High (sell) |
| Take Profit | 1:2 Risk to Reward — fixed |
| Flat Market | Auto detect — WAIT signal |

---

## 🚀 Setup

```bash
# Step 1 — Venv
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# Step 2 — Install
pip install -r requirements.txt

# Step 3 — API Key (bot.py + backtest.py line 16/17)
TWELVEDATA_API_KEY = "your_key_here"

# Step 4 — Run
python app.py
```

---

## 🌐 Pages

| Page | URL |
|---|---|
| 📡 Live Signals | http://localhost:5000 |
| 📈 Tracker | http://localhost:5000/tracker.html |
| 📊 Backtest | http://localhost:5000/backtest.html |

---

## 📊 Signal Types

| Signal | Matlab |
|---|---|
| 🟢 BUY | EMA9>EMA15 + slope UP + bullish candle |
| 🔴 SELL | EMA9<EMA15 + slope DOWN + bearish candle |
| ⚪ WAIT | Flat market — slope <15° |

---

## 🔑 API Keys

| File | Line | Key |
|---|---|---|
| bot.py | 16 | Twelve Data |
| backtest.py | 17 | Twelve Data |

Free key: twelvedata.com → 800 req/day
Fallback: Yahoo Finance automatic (no key)

---

## ⏰ Intervals

| Code | Twelve Data | Yahoo Finance |
|---|---|---|
| 1 min | `"1min"` | `"1m"` |
| 5 min | `"5min"` | `"5m"` |
| 15 min | `"15min"` | `"15m"` |
| 1 hour | `"1h"` | `"1h"` |

---

## ⚠️ Risk Warning

```
Bot signal deta hai — trade manually lagao Exness par
Stop Loss HAMESHA lagao
2% se zyada risk mat lo per trade
News time par bot band rakho
Pehle demo account par test karo
```

---

## 🐛 Troubleshooting

| Problem | Fix |
|---|---|
| Cannot connect | python app.py chal raha hai? |
| Always WAIT | Flat market hai — normal |
| API error | Twelve Data key check karo |
| Port busy | port=5001 karo app.py mein |

---

Built with Python + Flask + Yahoo Finance + Twelve Data