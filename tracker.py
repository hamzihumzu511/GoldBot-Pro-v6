"""
GoldBot Pro — Real-Time Signal Tracker
Har signal JSON file mein save hota hai
TP/SL hit check karta hai automatically
Win rate, PnL sab track karta hai
"""

import json
import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

TRACKER_FILE = "signals_history.json"
INITIAL_BALANCE = 1000.0


# ─────────────────────────
# LOAD / SAVE
# ─────────────────────────
def load_history():
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, "r") as f:
            return json.load(f)
    return {"balance": INITIAL_BALANCE, "trades": []}


def save_history(data):
    with open(TRACKER_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ─────────────────────────
# SAVE NEW SIGNAL
# ─────────────────────────
def save_signal(signal_data):
    history = load_history()
    trade = {
        "id":        len(history["trades"]) + 1,
        "signal":    signal_data["signal"],
        "entry":     signal_data["entry"],
        "sl":        signal_data["sl"],
        "tp":        signal_data["tp"],
        "ema9":      signal_data.get("ema9", 0),
        "ema150":    signal_data.get("ema150", 0),
        "confidence":signal_data.get("confidence", 0),
        "confluence":signal_data.get("confluence", "0/7"),
        "timestamp": signal_data["timestamp"],
        "status":    "OPEN",      # OPEN → WIN / LOSS
        "close_time": None,
        "pnl":        None,
        "balance_after": None,
    }
    history["trades"].append(trade)
    save_history(history)
    return trade


# ─────────────────────────
# CHECK OPEN TRADES
# ─────────────────────────
def check_open_trades(current_high, current_low, current_price):
    """
    Check if any open trade hit TP or SL
    Call this every time new price comes in
    """
    history = load_history()
    closed = []

    for trade in history["trades"]:
        if trade["status"] != "OPEN":
            continue
        if trade["sl"] is None or trade["tp"] is None:
            continue

        hit_tp = False
        hit_sl = False

        if trade["signal"] == "BUY":
            if current_high >= trade["tp"]:  hit_tp = True
            elif current_low <= trade["sl"]: hit_sl = True
        else:  # SELL
            if current_low <= trade["tp"]:   hit_tp = True
            elif current_high >= trade["sl"]:hit_sl = True

        if hit_tp or hit_sl:
            risk_amt = history["balance"] * 0.02  # 2% risk
            sl_dist  = abs(trade["entry"] - trade["sl"])
            tp_dist  = abs(trade["entry"] - trade["tp"])
            rr       = tp_dist / sl_dist if sl_dist > 0 else 2.0

            if hit_tp:
                pnl    = round(risk_amt * rr, 2)
                result = "WIN"
            else:
                pnl    = round(-risk_amt, 2)
                result = "LOSS"

            history["balance"] = round(history["balance"] + pnl, 2)
            trade["status"]       = result
            trade["pnl"]          = pnl
            trade["balance_after"]= history["balance"]
            trade["close_time"]   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            closed.append(trade)

    save_history(history)
    return closed


# ─────────────────────────
# GET STATS
# ─────────────────────────
def get_stats():
    history = load_history()
    trades  = history["trades"]
    closed  = [t for t in trades if t["status"] in ("WIN","LOSS")]
    open_t  = [t for t in trades if t["status"] == "OPEN"]
    wins    = [t for t in closed if t["status"] == "WIN"]
    losses  = [t for t in closed if t["status"] == "LOSS"]

    win_rate = round(len(wins)/len(closed)*100, 1) if closed else 0
    avg_win  = round(float(np.mean([t["pnl"] for t in wins])), 2)   if wins   else 0
    avg_loss = round(float(abs(np.mean([t["pnl"] for t in losses]))),2) if losses else 0
    total_pnl= round(history["balance"] - INITIAL_BALANCE, 2)
    buy_t    = [t for t in closed if t["signal"]=="BUY"]
    sell_t   = [t for t in closed if t["signal"]=="SELL"]

    return {
        "balance":       history["balance"],
        "total_pnl":     total_pnl,
        "pnl_pct":       round(total_pnl/INITIAL_BALANCE*100, 1),
        "total_signals": len(trades),
        "closed":        len(closed),
        "open":          len(open_t),
        "wins":          len(wins),
        "losses":        len(losses),
        "win_rate":      win_rate,
        "avg_win":       avg_win,
        "avg_loss":      avg_loss,
        "rr_ratio":      round(avg_win/avg_loss, 2) if avg_loss > 0 else 0,
        "buy_trades":    len(buy_t),
        "sell_trades":   len(sell_t),
        "buy_wins":      len([t for t in buy_t  if t["status"]=="WIN"]),
        "sell_wins":     len([t for t in sell_t if t["status"]=="WIN"]),
        "trades":        list(reversed(trades)),  # newest first
        "open_trades":   open_t,
    }


# ─────────────────────────
# RESET TRACKER
# ─────────────────────────
def reset_tracker():
    save_history({"balance": INITIAL_BALANCE, "trades": []})
    return {"message": "Tracker reset. Starting fresh!"}
