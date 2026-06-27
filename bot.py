"""
GoldBot Pro v6 — XAU/USD
Strategy: Mayank Singh Scalping Method
- EMA 9 + EMA 15
- 30 Degree Slope Filter
- Pin Bar / Big Bar / Engulfing Entry
- SL: Entry candle low/high
- TP: 1:2 Risk to Reward
- Dual Confirmation: EMA alignment
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────
# CONFIG
# ─────────────────────────
TWELVEDATA_API_KEY = "YOUR TWELVEDATA_API_KEY"  # Get free key at https://twelvedata.com
INTERVAL       = "5min"   # 5 minute chart (beginners)
INTERVAL_YF    = "5m"
CANDLES        = 100


# ─────────────────────────
# FETCH DATA
# ─────────────────────────
def fetch_data():
    if TWELVEDATA_API_KEY != "YOUR_TWELVEDATA_API_KEY":
        df = _fetch_twelvedata()
        if df is not None and len(df) >= 30:
            print("  📡 Source: Twelve Data ✅")
            return df
    df = _fetch_yfinance()
    if df is not None and len(df) >= 30:
        print("  📡 Source: Yahoo Finance ✅")
        return df
    print("  ❌ No data")
    return None


def _fetch_twelvedata():
    try:
        r = requests.get("https://api.twelvedata.com/time_series", params={
            "symbol":"XAU/USD", "interval":INTERVAL,
            "outputsize":CANDLES, "apikey":TWELVEDATA_API_KEY,
            "format":"JSON", "order":"ASC"
        }, timeout=15)
        data = r.json()
        if data.get("status") == "error":
            print(f"  ⚠️  {data.get('message')}")
            return None
        vals = data.get("values", [])
        if not vals: return None
        df = pd.DataFrame(vals)
        for col in ["open","high","low","close","volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.dropna(subset=["open","high","low","close"]).reset_index(drop=True)
    except Exception as e:
        print(f"  ⚠️  Twelve Data: {e}")
        return None


def _fetch_yfinance():
    try:
        import yfinance as yf
        for sym, period, ivl in [
            ("GC=F","5d","5m"), ("GC=F","1d","1m"),
            ("GC=F","60d","1h"), ("XAUUSD=X","5d","5m"),
        ]:
            try:
                df = yf.download(sym, period=period, interval=ivl,
                                 progress=False, auto_adjust=True)
                if df.empty or len(df) < 30: continue
                df.columns = [c[0].lower() if isinstance(c,tuple)
                              else c.lower() for c in df.columns]
                df = df[["open","high","low","close","volume"]].dropna()
                if len(df) >= 30:
                    print(f"  ✅ {len(df)} candles from {sym} {ivl}")
                    return df.tail(CANDLES).reset_index(drop=True)
            except: continue
    except Exception as e:
        print(f"  ⚠️  yfinance: {e}")
    return None


# ─────────────────────────
# INDICATORS
# ─────────────────────────
def ema(s, p):
    return s.ewm(span=p, adjust=False).mean()

def atr_calc(h, l, c, p=14):
    tr = pd.concat([
        h-l,
        (h-c.shift()).abs(),
        (l-c.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(span=p, adjust=False).mean()


# ─────────────────────────
# 30 DEGREE SLOPE CHECK
# ─────────────────────────
def ema_slope_degrees(ema_series, lookback=5):
    """
    Calculate EMA slope angle
    30+ degrees = strong trend (valid for trade)
    """
    if len(ema_series) < lookback:
        return 0.0

    vals = ema_series.tail(lookback).values
    # Price change over lookback candles
    price_change = vals[-1] - vals[0]
    # Normalize by price level to get percentage
    pct_change   = (price_change / vals[0]) * 100

    # Convert to approximate degrees
    # 0.1% change per candle ≈ 45 degrees (approximate)
    degrees = np.degrees(np.arctan(pct_change * 2))
    return abs(degrees)


# ─────────────────────────
# CANDLE PATTERN DETECTION
# ─────────────────────────
def detect_candle(o, h, l, c):
    """
    Detect: Pin Bar, Big Bar (Full Body), Engulfing
    Returns: pattern name and direction
    """
    body     = abs(c - o)
    rng      = h - l + 1e-10
    upper_wick = h - max(c, o)
    lower_wick = min(c, o) - l
    body_pct = body / rng

    # ── PIN BAR ──
    # Long wick (at least 2x body), small body
    if lower_wick >= 2 * body and lower_wick > upper_wick and body_pct < 0.4:
        return "PIN_BAR", "BULLISH"   # hammer — bullish
    if upper_wick >= 2 * body and upper_wick > lower_wick and body_pct < 0.4:
        return "PIN_BAR", "BEARISH"   # shooting star — bearish

    # ── BIG BAR (Full Body) ──
    # Body takes up 70%+ of candle range
    if body_pct >= 0.70:
        if c > o: return "BIG_BAR", "BULLISH"
        if c < o: return "BIG_BAR", "BEARISH"

    return "NONE", "NONE"


def detect_engulfing(df, i):
    """
    Check if candle at index i is engulfing previous candle
    """
    if i < 1: return "NONE", "NONE"

    prev_o = float(df['open'].iloc[i-1])
    prev_c = float(df['close'].iloc[i-1])
    curr_o = float(df['open'].iloc[i])
    curr_c = float(df['close'].iloc[i])
    curr_h = float(df['high'].iloc[i])
    curr_l = float(df['low'].iloc[i])

    # Bullish Engulfing: prev bearish, curr bullish, curr body > prev body
    if (prev_c < prev_o and          # prev red
        curr_c > curr_o and          # curr green
        curr_c >= prev_o and         # curr close above prev open
        curr_o <= prev_c):           # curr open below prev close
        return "ENGULFING", "BULLISH"

    # Bearish Engulfing: prev bullish, curr bearish, curr body > prev body
    if (prev_c > prev_o and          # prev green
        curr_c < curr_o and          # curr red
        curr_c <= prev_o and         # curr close below prev open
        curr_o >= prev_c):           # curr open above prev close
        return "ENGULFING", "BEARISH"

    return "NONE", "NONE"


# ─────────────────────────
# EMA TOUCH CHECK
# ─────────────────────────
def candle_touched_ema(o, h, l, c, e9, e15):
    """
    Check if candle touched or crossed EMA zone (between EMA9 and EMA15)
    This is the entry trigger
    """
    ema_high = max(e9, e15)
    ema_low  = min(e9, e15)

    # Candle wick touched EMA zone
    touched = l <= ema_high and h >= ema_low
    # Candle closed above both EMAs (bullish)
    above   = c > ema_high and o < ema_high
    # Candle closed below both EMAs (bearish)
    below   = c < ema_low  and o > ema_low

    return touched or above or below


# ─────────────────────────
# MAIN SIGNAL ENGINE
# ─────────────────────────
def generate_signal(df):
    c  = df['close'].astype(float)
    h  = df['high'].astype(float)
    l  = df['low'].astype(float)
    o  = df['open'].astype(float)

    # ── EMAs ──
    e9_series  = ema(c, 9)
    e15_series = ema(c, 15)
    e9v  = float(e9_series.iloc[-1])
    e15v = float(e15_series.iloc[-1])

    # ── ATR for SL/TP fallback ──
    atrv = float(atr_calc(h, l, c).iloc[-1])

    # ── Current price ──
    price    = float(c.iloc[-1])
    curr_o   = float(o.iloc[-1])
    curr_h   = float(h.iloc[-1])
    curr_l   = float(l.iloc[-1])
    curr_c   = float(c.iloc[-1])

    # ── EMA 9 Slope (30 degree check) ──
    slope9  = ema_slope_degrees(e9_series,  lookback=5)
    slope15 = ema_slope_degrees(e15_series, lookback=5)
    avg_slope = (slope9 + slope15) / 2

    slope_valid = avg_slope >= 30
    slope_dir   = "UP" if float(e9_series.iloc[-1]) > float(e9_series.iloc[-3]) else "DOWN"

    # ── EMA Alignment ──
    ema_bullish = e9v > e15v   # 9 above 15 = uptrend
    ema_bearish = e9v < e15v   # 9 below 15 = downtrend

    # ── Candle Pattern (last 2 candles) ──
    # Check last candle
    pat1, dir1 = detect_candle(curr_o, curr_h, curr_l, curr_c)
    eng1, edir1= detect_engulfing(df, -1)

    # Check second last candle too
    prev_o = float(o.iloc[-2]); prev_h = float(h.iloc[-2])
    prev_l = float(l.iloc[-2]); prev_c = float(c.iloc[-2])
    pat2, dir2 = detect_candle(prev_o, prev_h, prev_l, prev_c)
    eng2, edir2= detect_engulfing(df, len(df)-2)

    # Combine patterns
    candle_bull = (dir1 == "BULLISH" or edir1 == "BULLISH" or
                   dir2 == "BULLISH" or edir2 == "BULLISH")
    candle_bear = (dir1 == "BEARISH" or edir1 == "BEARISH" or
                   dir2 == "BEARISH" or edir2 == "BEARISH")

    # Best pattern name for display
    if pat1 != "NONE":   main_pattern = f"{pat1} ({dir1})"
    elif eng1 != "NONE": main_pattern = f"{eng1} ({edir1})"
    elif pat2 != "NONE": main_pattern = f"{pat2} ({dir2})"
    elif eng2 != "NONE": main_pattern = f"{eng2} ({edir2})"
    else:                main_pattern = "NO PATTERN"

    # ── EMA Touch ──
    touched_ema = candle_touched_ema(curr_o, curr_h, curr_l, curr_c, e9v, e15v)

    # ── SCORING ──
    bs, ss = 0.0, 0.0
    rb, rs = [], []

    # ════ BUY CONDITIONS ════

    # B1: EMA Alignment bullish (9 above 15)
    if ema_bullish:
        bs += 2.0
        rb.append(f"📈 EMA9 ({e9v:.2f}) above EMA15 ({e15v:.2f}) — Uptrend confirmed")

    # B2: Slope >= 30 degrees and pointing up
    if slope_valid and slope_dir == "UP":
        bs += 2.0
        rb.append(f"📐 EMA slope {avg_slope:.0f}° (≥30°) pointing UP — Strong momentum")
    elif avg_slope >= 20 and slope_dir == "UP":
        bs += 1.0
        rb.append(f"📐 EMA slope {avg_slope:.0f}° — Moderate uptrend")

    # B3: Bullish candle pattern
    if candle_bull:
        bs += 2.0
        rb.append(f"🕯️ Bullish pattern: {main_pattern}")

    # B4: Candle touched EMA zone (entry trigger)
    if touched_ema and ema_bullish:
        bs += 1.5
        rb.append(f"🎯 Candle touched EMA zone — Perfect entry trigger")

    # B5: Price above both EMAs
    if price > e9v and price > e15v:
        bs += 0.5
        rb.append(f"✅ Price ({price:.2f}) above both EMAs")

    # ════ SELL CONDITIONS ════

    # S1: EMA Alignment bearish (9 below 15)
    if ema_bearish:
        ss += 2.0
        rs.append(f"📉 EMA9 ({e9v:.2f}) below EMA15 ({e15v:.2f}) — Downtrend confirmed")

    # S2: Slope >= 30 degrees and pointing down
    if slope_valid and slope_dir == "DOWN":
        ss += 2.0
        rs.append(f"📐 EMA slope {avg_slope:.0f}° (≥30°) pointing DOWN — Strong momentum")
    elif avg_slope >= 20 and slope_dir == "DOWN":
        ss += 1.0
        rs.append(f"📐 EMA slope {avg_slope:.0f}° — Moderate downtrend")

    # S3: Bearish candle pattern
    if candle_bear:
        ss += 2.0
        rs.append(f"🕯️ Bearish pattern: {main_pattern}")

    # S4: Candle touched EMA zone
    if touched_ema and ema_bearish:
        ss += 1.5
        rs.append(f"🎯 Candle touched EMA zone — Perfect entry trigger")

    # S5: Price below both EMAs
    if price < e9v and price < e15v:
        ss += 0.5
        rs.append(f"✅ Price ({price:.2f}) below both EMAs")

    # ── FLAT MARKET CHECK ──
    flat_market = avg_slope < 15
    if flat_market:
        return {
            "signal":      "WAIT",
            "reason":      "FLAT MARKET",
            "entry":       round(price, 2),
            "sl":          None,
            "tp":          None,
            "ema9":        round(e9v, 2),
            "ema15":       round(e15v, 2),
            "slope":       round(avg_slope, 1),
            "pattern":     main_pattern,
            "confluence":  "0/8",
            "confidence":  0,
            "buy_score":   round(bs, 1),
            "sell_score":  round(ss, 1),
            "reasons":     [
                f"⛔ Market is FLAT — slope only {avg_slope:.0f}° (need 30°+)",
                "⏳ Wait for a trending market before entering",
                "💡 EMA slope less than 30° = sideways = avoid trading"
            ],
            "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # ── FINAL SIGNAL ──
    # SL = entry candle's low (buy) or high (sell)
    # TP = 1:2 RR

    if bs > ss:
        sig     = "BUY"
        sl      = round(curr_l, 2)          # SL at entry candle LOW
        sl_dist = round(price - sl, 2)
        tp      = round(price + sl_dist * 2, 2)  # 1:2 RR
        conf    = min(int((bs / 8) * 100), 97)
        reasons = rb
        score   = bs
    else:
        sig     = "SELL"
        sl      = round(curr_h, 2)          # SL at entry candle HIGH
        sl_dist = round(sl - price, 2)
        tp      = round(price - sl_dist * 2, 2)  # 1:2 RR
        conf    = min(int((ss / 8) * 100), 97)
        reasons = rs
        score   = ss

    # Weak signal warning
    if score < 3.0:
        reasons.append(f"⚠️ Weak setup ({score:.1f}/8) — wait for stronger signal")

    return {
        "signal":     sig,
        "entry":      round(price, 2),
        "sl":         sl,
        "tp":         tp,
        "sl_dist":    round(abs(price - sl), 2),
        "rr":         "1:2",
        "ema9":       round(e9v, 2),
        "ema15":      round(e15v, 2),
        "slope":      round(avg_slope, 1),
        "slope_dir":  slope_dir,
        "pattern":    main_pattern,
        "touched_ema":touched_ema,
        "confluence": f"{score:.1f}/8",
        "confidence": conf,
        "buy_score":  round(bs, 1),
        "sell_score": round(ss, 1),
        "reasons":    reasons,
        "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ─────────────────────────
# TERMINAL RUN
# ─────────────────────────
def run_once():
    print("\n" + "="*58)
    print("  🥇 GoldBot Pro v6 — Mayank Singh Scalping Strategy")
    print("  📊 EMA 9/15 + 30° Slope + Pin Bar/Engulfing + 1:2 RR")
    print("="*58)
    print(f"  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    df = fetch_data()
    if df is None or len(df) < 30:
        print("  ❌ No data."); return None
    print(f"  ✅ {len(df)} candles | Price: ${float(df['close'].iloc[-1]):.2f}")
    print("-"*58)
    s = generate_signal(df)
    e = "🟢" if s['signal']=="BUY" else "🔴" if s['signal']=="SELL" else "⚪"
    print(f"\n  {e}  SIGNAL     : {s['signal']}")
    if s.get('reason'): print(f"  ⚠️  Reason     : {s['reason']}")
    print(f"  📍 Entry     : ${s['entry']}")
    if s['sl']:
        print(f"  🛑 Stop Loss : ${s['sl']}  (dist: {s.get('sl_dist','?')})")
        print(f"  🎯 Take Prof : ${s['tp']}  (RR: {s.get('rr','1:2')})")
    print(f"  💪 Confidence: {s['confidence']}%  |  {s['confluence']}")
    print(f"  📐 EMA9: {s['ema9']}  EMA15: {s['ema15']}")
    print(f"  📐 Slope: {s['slope']}°  Direction: {s['slope_dir']}")
    print(f"  🕯️  Pattern: {s['pattern']}")
    print(f"\n  Reasons:")
    for r in s['reasons']: print(f"    {r}")
    print("="*58)
    return s


if __name__ == "__main__":
    import time
    print("\n🤖 GoldBot v6 | Mayank Singh Strategy | Ctrl+C stop\n")
    while True:
        try:
            run_once()
            print(f"\n⏳ Next scan in 60s...\n")
            time.sleep(60)
        except KeyboardInterrupt:
            print("\n👋 Bot stopped."); break
        except Exception as e:
            print(f"[ERROR] {e}"); time.sleep(30)
