from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from bot import fetch_data, generate_signal
from tracker import save_signal, check_open_trades, get_stats, reset_tracker
from datetime import datetime
import numpy as np

app = Flask(__name__, static_folder=".")
CORS(app)

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/tracker.html")
def tracker_page():
    return send_from_directory(".", "tracker.html")

@app.route("/backtest.html")
def backtest_page():
    return send_from_directory(".", "backtest.html")

# ── LIVE SIGNAL ──
@app.route("/signal")
def signal():
    df = fetch_data()
    if df is None or len(df) < 30:
        return jsonify({"error": "Failed to fetch market data."}), 500

    sig = generate_signal(df)

    # Auto-check open trades with latest price
    if df is not None:
        try:
            h = float(df['high'].iloc[-1])
            l = float(df['low'].iloc[-1])
            p = float(df['close'].iloc[-1])
            check_open_trades(h, l, p)
        except: pass

    return jsonify(sig)

# ── SAVE SIGNAL TO TRACKER ──
@app.route("/save_signal", methods=["POST"])
def save_sig():
    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400
    # Only save BUY/SELL — not WAIT
    if data.get("signal") == "WAIT":
        return jsonify({"message": "WAIT signal not saved"}), 200
    trade = save_signal(data)
    return jsonify({"message": "Signal saved!", "trade": trade})

# ── GET TRACKER STATS ──
@app.route("/stats")
def stats():
    return jsonify(get_stats())

# ── UPDATE OPEN TRADES (manual price check) ──
@app.route("/update_trades")
def update_trades():
    df = fetch_data()
    if df is None:
        return jsonify({"error": "No data"}), 500
    h = float(df['high'].iloc[-1])
    l = float(df['low'].iloc[-1])
    p = float(df['close'].iloc[-1])
    closed = check_open_trades(h, l, p)
    return jsonify({
        "closed_now": len(closed),
        "trades": closed,
        "current_price": p
    })

# ── RESET TRACKER ──
@app.route("/reset_tracker", methods=["POST"])
def reset():
    return jsonify(reset_tracker())

# ── BACKTEST ──
@app.route("/backtest")
def backtest():
    try:
        from backtest import fetch_historical, run_backtest
        df = fetch_historical()
        if df is None or len(df) < 50:
            return jsonify({"error": "Not enough historical data."}), 500
        trades, final_bal, max_dd = run_backtest(df)
        if not trades:
            return jsonify({"error": "No trades generated."}), 500
        wins      = [t for t in trades if "WIN"  in t['result']]
        losses    = [t for t in trades if "LOSS" in t['result']]
        avg_win   = float(np.mean([t['pnl'] for t in wins]))         if wins   else 0
        avg_loss  = float(abs(np.mean([t['pnl'] for t in losses])))  if losses else 0
        buy_t     = [t for t in trades if t['signal']=="BUY"]
        sell_t    = [t for t in trades if t['signal']=="SELL"]
        return jsonify({
            "total":         len(trades),
            "wins":          len(wins),
            "losses":        len(losses),
            "win_rate":      round(len(wins)/len(trades)*100, 1),
            "final_balance": round(final_bal, 2),
            "total_pnl":     round(final_bal-1000, 2),
            "pnl_pct":       round((final_bal-1000)/1000*100, 1),
            "max_drawdown":  round(max_dd, 1),
            "avg_win":       round(avg_win, 2),
            "avg_loss":      round(avg_loss, 2),
            "rr_ratio":      round(avg_win/avg_loss,2) if avg_loss>0 else 0,
            "buy_trades":    len(buy_t),
            "sell_trades":   len(sell_t),
            "buy_wins":      len([t for t in buy_t  if "WIN" in t['result']]),
            "sell_wins":     len([t for t in sell_t if "WIN" in t['result']]),
            "trades":        trades
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"status":"online","time":datetime.now().strftime("%H:%M:%S")})

if __name__ == "__main__":
    app.run(debug=True, port=5000)