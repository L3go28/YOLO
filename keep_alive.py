from flask import Flask
from threading import Thread
import datetime

app = Flask(__name__)

# These variables will be updated from the bot
total_pnl_display = {"pnl": 0.0, "wins": 0, "losses": 0, "trades": 0}
last_updated = "Never"

@app.route('/')
def home():
    is_alive = False
    if last_updated != "Never":
        try:
            last_dt = datetime.datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")
            delta = (datetime.datetime.now() - last_dt).total_seconds()
            is_alive = delta <= 60  # consider alive if updated within last 60s
        except ValueError:
            is_alive = False

    status_html = "✅ Online" if is_alive else "❌ Offline"

    return f'''
    <h2>📊 UpBot Live Stats</h2>
    <p><b>Status:</b> {status_html}</p>
    <p><b>Last Update:</b> {last_updated}</p>
    <p><b>Total PnL:</b> {total_pnl_display["pnl"]:+.4f} USDT</p>
    <p><b>Wins:</b> {total_pnl_display["wins"]} | <b>Losses:</b> {total_pnl_display["losses"]}</p>
    <p><b>Trades Today:</b> {total_pnl_display["trades"]} / 30</p>
    '''

def update_display(pnl, wins, losses, trades):
    global last_updated
    total_pnl_display["pnl"] = pnl
    total_pnl_display["wins"] = wins
    total_pnl_display["losses"] = losses
    total_pnl_display["trades"] = trades
    last_updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
