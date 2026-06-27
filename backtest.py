"""
GoldBot Pro — Backtesting Engine
Tests EMA9/150 + Order Block strategy on last 2 weeks
Gives: Win Rate, Profit/Loss, Best/Worst trade, Drawdown
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────
# CONFIG
# ─────────────────────────
TWELVEDATA_API_KEY = "YOUR_TWELVEDATA_API_KEY"  # Get free key at https://twelvedata.com
INTERVAL       = "1h"      # 1h best for 2-week backtest (enough candles)
INTERVAL_YF    = "1h"
INITIAL_BALANCE= 1000      # Starting balance in USD
RISK_PER_TRADE = 0.02      # 2% risk per trade
ATR_MULT_SL    = 1.0
ATR_MULT_TP    = 2.0
BACKTEST_DAYS  = 14        # 2 weeks


# ─────────────────────────
# FETCH HISTORICAL DATA
# ─────────────────────────
def fetch_historical():
    """Fetch 2 weeks of hourly data"""
    print("  📡 Fetching 2 weeks of historical data...")

    # Try Twelve Data
    if TWELVEDATA_API_KEY != "YOUR_TWELVEDATA_API_KEY":
        df = _fetch_td_historical()
        if df is not None and len(df) >= 50:
            print(f"  ✅ Twelve Data: {len(df)} candles loaded")
            return df

    # Fallback: yfinance
    df = _fetch_yf_historical()
    if df is not None and len(df) >= 50:
        print(f"  ✅ Yahoo Finance: {len(df)} candles loaded")
        return df

    print("  ❌ Could not fetch historical data")
    return None


def _fetch_td_historical():
    try:
        r = requests.get("https://api.twelvedata.com/time_series", params={
            "symbol": "XAU/USD", "interval": INTERVAL,
            "outputsize": 500, "apikey": TWELVEDATA_API_KEY,
            "format": "JSON", "order": "ASC"
        }, timeout=20)
        data = r.json()
        if data.get("status") == "error":
            print(f"  ⚠️  TD: {data.get('message')}")
            return None
        vals = data.get("values", [])
        if not vals: return None
        df = pd.DataFrame(vals)
        for col in ["open","high","low","close","volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.sort_values('datetime').reset_index(drop=True)
        # Last 2 weeks
        cutoff = datetime.now() - timedelta(days=BACKTEST_DAYS)
        df = df[df['datetime'] >= cutoff]
        return df.dropna(subset=["open","high","low","close"]).reset_index(drop=True)
    except Exception as e:
        print(f"  ⚠️  TD error: {e}")
        return None


def _fetch_yf_historical():
    try:
        import yfinance as yf
        for sym in ["GC=F", "XAUUSD=X"]:
            try:
                df = yf.download(sym, period="1mo", interval="1h",
                                 progress=False, auto_adjust=True)
                if df.empty or len(df) < 50: continue
                df.columns = [c[0].lower() if isinstance(c,tuple)
                              else c.lower() for c in df.columns]
                df = df[["open","high","low","close","volume"]].dropna()
                df = df.reset_index()
                df = df.rename(columns={"datetime":"datetime","index":"datetime",
                                        "Datetime":"datetime","Date":"datetime"})
                if 'datetime' not in df.columns:
                    df.columns = ['datetime'] + list(df.columns[1:])
                df['datetime'] = pd.to_datetime(df['datetime'])
                cutoff = datetime.now() - timedelta(days=BACKTEST_DAYS)
                # Make cutoff timezone-aware if needed
                if df['datetime'].dt.tz is not None:
                    import pytz
                    cutoff = cutoff.replace(tzinfo=pytz.UTC)
                df = df[df['datetime'] >= cutoff]
                if len(df) >= 50:
                    return df.reset_index(drop=True)
            except Exception as e:
                continue
        return None
    except Exception as e:
        print(f"  ⚠️  yfinance error: {e}")
        return None


# ─────────────────────────
# INDICATORS
# ─────────────────────────
def ema(s, p):
    return s.ewm(span=p, adjust=False).mean()

def atr_calc(h, l, c, p=14):
    tr = pd.concat([
        h-l, (h-c.shift()).abs(), (l-c.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(span=p, adjust=False).mean()


# ─────────────────────────
# ORDER BLOCK DETECTION
# (same as bot.py)
# ─────────────────────────
def find_obs_at(df, idx):
    """Find OBs using only data up to idx (no future peeking)"""
    window = df.iloc[max(0, idx-50):idx].reset_index(drop=True)
    if len(window) < 10:
        return [], []

    o = window['open'].astype(float).values
    h = window['high'].astype(float).values
    l = window['low'].astype(float).values
    c = window['close'].astype(float).values
    n = len(window)

    trs = [max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
           for i in range(1,n)]
    avg_atr = np.mean(trs[-20:]) if len(trs)>=20 else np.mean(trs) if trs else 1

    bull_obs, bear_obs = [], []
    for i in range(2, n-2):
        if c[i] > o[i]:  # green → bearish OB
            drop = c[i] - min(l[i+1], l[min(i+2,n-1)])
            if drop >= avg_atr * 0.8:
                bear_obs.append({
                    "ob_high": round(max(o[i],c[i]),2),
                    "ob_low":  round(min(o[i],c[i]),2),
                    "strength": round(drop/avg_atr,1)
                })
        if c[i] < o[i]:  # red → bullish OB
            rise = max(h[i+1], h[min(i+2,n-1)]) - c[i]
            if rise >= avg_atr * 0.8:
                bull_obs.append({
                    "ob_high": round(max(o[i],c[i]),2),
                    "ob_low":  round(min(o[i],c[i]),2),
                    "strength": round(rise/avg_atr,1)
                })
    return bull_obs[-3:], bear_obs[-3:]


def price_in_ob(price, obs, buf=0.003):
    for ob in reversed(obs):
        buf_val = (ob['ob_high']-ob['ob_low']) * buf * 100
        if (ob['ob_low']-buf_val) <= price <= (ob['ob_high']+buf_val):
            return True, ob
    return False, None


# ─────────────────────────
# GENERATE SIGNAL AT INDEX (Mayank Singh Strategy)
# ─────────────────────────
def ema_slope_degrees(ema_series, lookback=5):
    if len(ema_series) < lookback: return 0.0
    vals = ema_series.tail(lookback).values
    pct  = (vals[-1] - vals[0]) / vals[0] * 100
    return abs(np.degrees(np.arctan(pct * 2)))

def detect_candle_bt(o, h, l, c):
    body = abs(c-o); rng = h-l+1e-10
    uw = h-max(c,o); lw = min(c,o)-l
    bp = body/rng
    if lw>=2*body and lw>uw and bp<0.4: return "PIN_BAR","BULLISH"
    if uw>=2*body and uw>lw and bp<0.4: return "PIN_BAR","BEARISH"
    if bp>=0.70:
        if c>o: return "BIG_BAR","BULLISH"
        if c<o: return "BIG_BAR","BEARISH"
    return "NONE","NONE"

def detect_eng_bt(df, i):
    if i<1: return "NONE","NONE"
    po=float(df["open"].iloc[i-1]); pc=float(df["close"].iloc[i-1])
    co=float(df["open"].iloc[i]);   cc=float(df["close"].iloc[i])
    if pc<po and cc>co and cc>=po and co<=pc: return "ENGULF","BULLISH"
    if pc>po and cc<co and cc<=po and co>=pc: return "ENGULF","BEARISH"
    return "NONE","NONE"

def signal_at(df, idx):
    """Generate signal using only data up to idx — Mayank Singh Strategy"""
    if idx < 20: return None

    window = df.iloc[:idx+1].reset_index(drop=True)
    c = window["close"].astype(float)
    h = window["high"].astype(float)
    l = window["low"].astype(float)
    o = window["open"].astype(float)

    price  = float(c.iloc[-1])
    e9s    = ema(c, 9)
    e15s   = ema(c, 15)
    e9v    = float(e9s.iloc[-1])
    e15v   = float(e15s.iloc[-1])

    slope  = (ema_slope_degrees(e9s)+ema_slope_degrees(e15s))/2
    s_dir  = "UP" if float(e9s.iloc[-1])>float(e9s.iloc[-3]) else "DOWN"

    curr_o=float(o.iloc[-1]); curr_h=float(h.iloc[-1])
    curr_l=float(l.iloc[-1]); curr_c=float(c.iloc[-1])

    p1,d1  = detect_candle_bt(curr_o,curr_h,curr_l,curr_c)
    e1,ed1 = detect_eng_bt(window,-1)
    p2,d2  = detect_candle_bt(float(o.iloc[-2]),float(h.iloc[-2]),float(l.iloc[-2]),float(c.iloc[-2]))
    e2,ed2 = detect_eng_bt(window,len(window)-2)

    cbull = d1=="BULLISH" or ed1=="BULLISH" or d2=="BULLISH" or ed2=="BULLISH"
    cbear = d1=="BEARISH" or ed1=="BEARISH" or d2=="BEARISH" or ed2=="BEARISH"

    if slope < 15: return None  # flat market skip

    ema_bull = e9v > e15v
    ema_bear = e9v < e15v

    bs, ss = 0.0, 0.0

    # BUY scoring — Mayank Singh
    if ema_bull:            bs += 2.0
    if slope>=30 and s_dir=="UP":   bs += 2.0
    elif slope>=20 and s_dir=="UP": bs += 1.0
    if cbull:               bs += 2.0
    if price > e9v:         bs += 0.5

    # SELL scoring — Mayank Singh
    if ema_bear:            ss += 2.0
    if slope>=30 and s_dir=="DOWN":   ss += 2.0
    elif slope>=20 and s_dir=="DOWN": ss += 1.0
    if cbear:               ss += 2.0
    if price < e9v:         ss += 0.5

    if bs > ss:
        sl = round(curr_l, 2)
        sd = round(price - sl, 2)
        return {"signal":"BUY",  "entry":price,
                "sl": sl, "tp": round(price + sd*2, 2),
                "score": bs}
    else:
        sl = round(curr_h, 2)
        sd = round(sl - price, 2)
        return {"signal":"SELL", "entry":price,
                "sl": sl, "tp": round(price - sd*2, 2),
                "score": ss}


# ─────────────────────────
# BACKTEST ENGINE
# ─────────────────────────
def run_backtest(df):
    print(f"\n  🔁 Running backtest on {len(df)} candles ({BACKTEST_DAYS} days)...")

    balance   = INITIAL_BALANCE
    trades    = []
    in_trade  = False
    current   = None
    peak_bal  = INITIAL_BALANCE
    max_dd    = 0.0

    # Scan every candle from index 20 onward
    for i in range(20, len(df)):
        c_price = float(df['close'].iloc[i])
        h_price = float(df['high'].iloc[i])
        l_price = float(df['low'].iloc[i])

        # ── Check if open trade hit TP or SL ──
        if in_trade and current:
            hit_tp, hit_sl = False, False

            if current['signal'] == "BUY":
                if h_price >= current['tp']: hit_tp = True
                elif l_price <= current['sl']: hit_sl = True
            else:  # SELL
                if l_price <= current['tp']: hit_tp = True
                elif h_price >= current['sl']: hit_sl = True

            if hit_tp or hit_sl:
                # Calculate PnL
                risk_amt  = balance * RISK_PER_TRADE
                sl_dist   = abs(current['entry'] - current['sl'])
                tp_dist   = abs(current['entry'] - current['tp'])
                rr        = tp_dist / sl_dist if sl_dist > 0 else 2.0

                if hit_tp:
                    pnl    = risk_amt * rr
                    result = "WIN ✅"
                else:
                    pnl    = -risk_amt
                    result = "LOSS ❌"

                balance += pnl
                if balance > peak_bal: peak_bal = balance
                dd = (peak_bal - balance) / peak_bal * 100
                if dd > max_dd: max_dd = dd

                trades.append({
                    "entry_i":  current['entry_i'],
                    "exit_i":   i,
                    "signal":   current['signal'],
                    "entry":    current['entry'],
                    "sl":       current['sl'],
                    "tp":       current['tp'],
                    "result":   result,
                    "pnl":      round(pnl, 2),
                    "balance":  round(balance, 2),
                    "score":    current['score'],
                })

                in_trade = False
                current  = None

        # ── Only open new trade if not in one ──
        if not in_trade:
            sig = signal_at(df, i)
            if sig and sig['score'] >= 3.0:  # min score to trade
                current  = {**sig, "entry_i": i, "entry": c_price,
                            "sl": c_price - sig['atr'] if sig['signal']=="BUY"
                                  else c_price + sig['atr'],
                            "tp": c_price + sig['atr']*ATR_MULT_TP if sig['signal']=="BUY"
                                  else c_price - sig['atr']*ATR_MULT_TP}
                in_trade = True

    return trades, balance, max_dd


# ─────────────────────────
# RESULTS
# ─────────────────────────
def print_results(trades, final_balance, max_dd, df):
    total   = len(trades)
    if total == 0:
        print("\n  ⚠️  No trades generated. Try longer period.")
        return {}

    wins    = [t for t in trades if "WIN" in t['result']]
    losses  = [t for t in trades if "LOSS" in t['result']]
    win_rate= len(wins)/total*100
    total_pnl = final_balance - INITIAL_BALANCE
    avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0
    avg_loss= abs(np.mean([t['pnl'] for t in losses])) if losses else 0
    rr_ratio= avg_win/avg_loss if avg_loss>0 else 0
    best    = max(trades, key=lambda x: x['pnl'])
    worst   = min(trades, key=lambda x: x['pnl'])
    buy_t   = [t for t in trades if t['signal']=="BUY"]
    sell_t  = [t for t in trades if t['signal']=="SELL"]

    print("\n" + "="*58)
    print("  📊 BACKTEST RESULTS — Last 2 Weeks")
    print("="*58)
    print(f"  📅 Period      : Last {BACKTEST_DAYS} days ({len(df)} candles)")
    print(f"  💰 Start Bal   : ${INITIAL_BALANCE:,.2f}")
    print(f"  💰 Final Bal   : ${final_balance:,.2f}")
    print(f"  {'📈' if total_pnl>0 else '📉'} Total PnL    : ${total_pnl:+,.2f}  ({total_pnl/INITIAL_BALANCE*100:+.1f}%)")
    print(f"  📉 Max Drawdown: {max_dd:.1f}%")
    print(f"\n  🔢 Total Trades: {total}")
    print(f"  ✅ Wins        : {len(wins)}  ({win_rate:.1f}%)")
    print(f"  ❌ Losses      : {len(losses)}")
    print(f"  🎯 Win Rate    : {win_rate:.1f}%")
    print(f"  📊 Avg Win     : ${avg_win:.2f}")
    print(f"  📊 Avg Loss    : ${avg_loss:.2f}")
    print(f"  ⚖️  RR Ratio    : 1:{rr_ratio:.2f}")
    print(f"\n  🟢 BUY trades  : {len(buy_t)}  wins:{len([t for t in buy_t if 'WIN' in t['result']])}")
    print(f"  🔴 SELL trades : {len(sell_t)}  wins:{len([t for t in sell_t if 'WIN' in t['result']])}")
    print(f"\n  🏆 Best Trade  : ${best['pnl']:+.2f}  ({best['signal']} @ {best['entry']:.2f})")
    print(f"  💔 Worst Trade : ${worst['pnl']:+.2f}  ({worst['signal']} @ {worst['entry']:.2f})")
    print("\n  📋 All Trades:")
    print(f"  {'#':<4} {'Signal':<6} {'Entry':>8} {'SL':>8} {'TP':>8} {'PnL':>8} {'Result'}")
    print("  " + "-"*55)
    for i, t in enumerate(trades, 1):
        print(f"  {i:<4} {t['signal']:<6} {t['entry']:>8.2f} "
              f"{t['sl']:>8.2f} {t['tp']:>8.2f} "
              f"${t['pnl']:>+7.2f}  {t['result']}")
    print("="*58)

    return {
        "total": total, "wins": len(wins), "losses": len(losses),
        "win_rate": round(win_rate,1),
        "final_balance": round(final_balance,2),
        "total_pnl": round(total_pnl,2),
        "pnl_pct": round(total_pnl/INITIAL_BALANCE*100,1),
        "max_drawdown": round(max_dd,1),
        "avg_win": round(avg_win,2),
        "avg_loss": round(avg_loss,2),
        "rr_ratio": round(rr_ratio,2),
        "best_trade": best['pnl'],
        "worst_trade": worst['pnl'],
        "trades": trades
    }


# ─────────────────────────
# MAIN
# ─────────────────────────
def main():
    print("\n" + "="*58)
    print("  🥇 GoldBot Pro — BACKTESTING ENGINE")
    print(f"  Strategy: EMA9/150 + Order Block | Last {BACKTEST_DAYS} days")
    print("="*58)

    df = fetch_historical()
    if df is None or len(df) < 50:
        print("  ❌ Not enough data for backtest.")
        return None

    trades, final_bal, max_dd = run_backtest(df)
    results = print_results(trades, final_bal, max_dd, df)
    return results


if __name__ == "__main__":
    main()