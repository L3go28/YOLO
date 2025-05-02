# ==============================
#       ADAPTIVE SL UPBOT + BNB FEE CHECK + LIVE WEB PROFIT
# ==============================

# === [IMPORTS & SETUP] ===
import os
import time
import math
import logging
import pandas as pd
import pandas_ta as ta
import requests
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL
from rich.console import Console
from keep_alive import keep_alive, update_display

# === [API KEY SETUP] ===
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
client = Client(API_KEY, API_SECRET)

# === [CONFIGURATION] ===
symbol = 'DOGEUSDT'
timeframe = '1m'
console = Console()
fee_rate = 0.00075  # 0.075% with BNB discount

logging.basicConfig(level=logging.INFO)

# === [TRADE STATS CLASS] ===
class TradeStats:
    def __init__(self):
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0
        self.trades_today = 0
        self.signals_detected = 0
        self.in_position = False
        self.position_entry_price = 0.0
        self.position_size = 0.0

trade_stats = TradeStats()

# === [BALANCE & POSITION HELPERS] ===
def get_balance(asset="USDT"):
    try:
        balance_info = client.get_asset_balance(asset=asset)
        return float(balance_info['free']) if balance_info and 'free' in balance_info else 0.0
    except Exception as e:
        logging.error(f"Error fetching balance: {e}")
        return 0.0

def check_bnb_fee_balance(threshold=0.01):
    try:
        bnb_balance = get_balance("BNB")
        if bnb_balance < threshold:
            console.print(f"\n⚠️ [bold yellow]Low BNB Balance:[/bold yellow] {bnb_balance:.5f} — You may lose your 25% fee discount!\n")
    except Exception as e:
        logging.error(f"BNB balance check failed: {e}")

def check_existing_position():
    try:
        balances = client.get_account()['balances']
        doge = next((b for b in balances if b['asset'] == 'DOGE'), None)
        if doge:
            free_amount = float(doge['free'])
            if free_amount >= 6:
                trades = client.get_my_trades(symbol=symbol, limit=10)
                last_buy = next((t for t in reversed(trades) if t['isBuyer']), None)
                if last_buy:
                    trade_stats.in_position = True
                    trade_stats.position_size = free_amount
                    trade_stats.position_entry_price = float(last_buy['price'])
                    return True
        trade_stats.in_position = False
        return False
    except Exception as e:
        logging.error(f"Position check error: {e}")
        trade_stats.in_position = False
        return False

def calculate_trade_amount(entry_price):
    try:
        available = get_balance("USDT")
        if available < 1.5:
            return 0
        risk_amount = available * 0.01
        stop_loss_pct = 0.01
        position_size = risk_amount / (entry_price * stop_loss_pct)
        max_pos_size = (available * 0.2) / entry_price
        size = min(position_size, max_pos_size)
        min_value = 1.02402
        min_qty = 6
        min_by_value = math.ceil(min_value / entry_price)
        min_required = max(min_qty, min_by_value)
        return max(size, min_required)
    except Exception as e:
        logging.error(f"Trade amount calculation error: {e}")
        return 0

# === [MARKET INDICATORS] ===
def get_indicators():
    try:
        klines = client.get_historical_klines(symbol, timeframe, "1 day ago UTC")
        if not klines or len(klines) < 26:
            logging.error(f"Not enough data: {len(klines) if klines else 0}")
            return None
        df = pd.DataFrame(klines, columns=[
            "timestamp","open","high","low","close","volume",
            "close_time","quote_asset_volume","number_of_trades",
            "taker_buy_base_asset_volume","taker_buy_quote_asset_volume","ignore"
        ])
        for col in ['open','high','low','close','volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['basis'] = ta.sma(df['close'], length=20)
        df['dev'] = ta.stdev(df['close'], length=20)
        df['upper'] = df['basis'] + 2 * df['dev']
        df['lower'] = df['basis'] - 2 * df['dev']
        df['rsi'] = ta.rsi(df['close'], length=14)
        macd = ta.macd(df['close'])
        if isinstance(macd, pd.DataFrame):
            df = pd.concat([df, macd], axis=1)
        df['ema5'] = ta.ema(df['close'], length=5)
        df['vol_sma'] = ta.sma(df['volume'], length=20)
        df['vol_cond'] = df['volume'] > df['vol_sma']
        return df.dropna().reset_index(drop=True)
    except Exception as e:
        logging.error(f"Indicator fetching error: {e}")
        return None

# === [ADAPTIVE RISK LOGIC] ===
def adjust_dynamic_risk(cur, prev):
    rsi_drop = cur['rsi'] < prev['rsi'] and cur['rsi'] < 50
    macd_cross = cur['MACD_12_26_9'] < cur['MACDs_12_26_9']
    price_trend_down = cur['close'] < prev['close'] and cur['close'] < cur['ema5']

    if rsi_drop and macd_cross and price_trend_down:
        return 0.004
    elif rsi_drop or macd_cross:
        return 0.006
    else:
        return 0.01

# === [STATUS DISPLAY] ===
def update_overall_status(df):
    try:
        check_existing_position()
        bal = get_balance()
        check_bnb_fee_balance()

        update_display(
            pnl=trade_stats.total_pnl,
            wins=trade_stats.wins,
            losses=trade_stats.losses,
            trades=trade_stats.trades_today
        )

        console.clear()
        total = trade_stats.wins + trade_stats.losses
        win_rate = (trade_stats.wins / total * 100) if total else 0
        console.print("\n💰 [bold cyan]Overall Status[/bold cyan]")
        console.print("─" * 72)
        console.print(f"🟢 [bold]Balance:[/bold] {bal:.2f} USDT")
        console.print(f"📊 [bold]Total PnL:[/bold] {trade_stats.total_pnl:+.4f} USDT | 📈 Wins: {trade_stats.wins} | 📉 Losses: {trade_stats.losses} | 🏆 Win Rate: {win_rate:.2f}%")
        console.print(f"🕒 [bold]Trades Today:[/bold] {trade_stats.trades_today} / 30")
        console.print("─" * 72)

        if df is not None and not df.empty:
            cur = df.iloc[-1]
            console.print("\n📊 [bold yellow]Indicators[/bold yellow]")
            console.print("─" * 72)
            console.print(f"📉 [bold]Live Price:[/bold] {cur['close']:.5f}")
            console.print(f"📐 MACD: {cur['MACD_12_26_9']:.5f} | Signal: {cur['MACDs_12_26_9']:.5f} | Histogram: {cur['MACDh_12_26_9']:+.5f}")
            console.print(f"📉 RSI: {cur['rsi']:.2f} | EMA(5): {cur['ema5']:.5f}")
            trend = "📈 Bullish" if cur['close'] > cur['basis'] else "📉 Bearish"
            vol_spike = "✅" if cur['vol_cond'] else "❌"
            console.print(f"📊 [bold]Trend:[/bold] {trend} | Volume Spike: {vol_spike}")
            console.print("─" * 72)

        if trade_stats.in_position:
            cur = df.iloc[-1]
            prev = df.iloc[-2]
            dynamic_risk = adjust_dynamic_risk(cur, prev)
            sl_price = trade_stats.position_entry_price * (1 - dynamic_risk)
            tp_dyn = trade_stats.position_entry_price * 1.005
            tp_bb = cur['upper']
            console.print("\n📊 [bold green]OPEN Position Detected![/bold green]")
            console.print(f"🐶 Pair: {symbol} | ⏱ Timeframe: {timeframe}")
            console.print(f"📌 Entry: {trade_stats.position_entry_price:.8f}")
            console.print(f"🎯 Target (TP Range): {tp_dyn:.5f} – {tp_bb:.5f} | 🛑 SL: {sl_price:.5f}")
            console.print(f"📊 Size: {trade_stats.position_size:.2f} DOGE | Risk: {dynamic_risk * 100:.2f}% | Type: Long")
            console.print("─" * 72)
        else:
            console.print(f"⏳ Waiting for entry signal... | ⌛ {trade_stats.signals_detected} signals detected")
            console.print("─" * 72)
    except Exception as e:
        logging.error(f"Status update error: {e}")

# === [TRADING LOGIC & EXIT] ===
def execute_trade():
    try:
        df = get_indicators()
        if df is None or len(df) < 2:
            return
        cur, prev = df.iloc[-1], df.iloc[-2]

        # === Filtered Bollinger Band Buy ===
        bb_buy = (
            cur['close'] < cur['lower'] and
            cur['vol_cond'] and
            cur['close'] > cur['basis'] and           # avoid if below middle BB (bearish trend)
            cur['rsi'] > 45 and                        # only if RSI is healthy
            cur['MACD_12_26_9'] > cur['MACDs_12_26_9'] # no bearish MACD crossover
        )
        mom_buy = (
            cur['close'] > prev['high'] and cur['close'] > cur['ema5'] and
            cur['close'] < cur['upper'] and cur['MACD_12_26_9'] > cur['MACDs_12_26_9'] and
            cur['rsi'] > 50 and cur['rsi'] > prev['rsi'] and cur['vol_cond'] and
            not trade_stats.in_position
        )
        # === Oversold RSI Reversal Buy ===
        rsi_reversal_buy = (
            cur['rsi'] <= 30 and
            cur['rsi'] > prev['rsi'] and
            cur['MACDh_12_26_9'] > prev['MACDh_12_26_9'] and
            cur['vol_cond'] and
            not trade_stats.in_position
        )
        if (bb_buy or mom_buy or rsi_reversal_buy) and not trade_stats.in_position:
            amt = calculate_trade_amount(cur['close'])
            trade_stats.signals_detected += 1
            if amt >= 6:
                order = client.order_market_buy(symbol=symbol, quantity=int(amt))
                if order.get('status') == 'FILLED':
                    fill = order['fills'][0]
                    trade_stats.in_position = True
                    trade_stats.position_entry_price = float(fill['price'])
                    trade_stats.position_size = float(fill['qty'])
        elif trade_stats.in_position:
            # Exit logic inlined for brevity
            take_profit_logic(get_indicators())

        time.sleep(5)
    except Exception as e:
        logging.error(f"Trade execution error: {e}")

# === [EXIT LOGIC WITH DYNAMIC SL] ===
def take_profit_logic(df):
    try:
        cur, prev = df.iloc[-1], df.iloc[-2]
        entry = trade_stats.position_entry_price
        price = cur['close']
        size = trade_stats.position_size

        buy_fee = entry * size * fee_rate
        sell_fee = price * size * fee_rate
        pnl = (price - entry) * size - (buy_fee + sell_fee)

        dynamic_risk = adjust_dynamic_risk(cur, prev)
        sl_price = entry * (1 - dynamic_risk)
        min_profit = entry * size * 0.002

        if price <= sl_price:
            sell = client.order_market_sell(symbol=symbol, quantity=int(size))
            if sell.get('status') == 'FILLED':
                trade_stats.in_position = False
                trade_stats.losses += 1
                trade_stats.total_pnl += pnl
                trade_stats.trades_today += 1
            return

        upper_bb = cur['upper']
        if price > upper_bb and pnl > min_profit:
            sell = client.order_market_sell(symbol=symbol, quantity=int(size))
            if sell.get('status') == 'FILLED':
                trade_stats.in_position = False
                trade_stats.wins += 1
                trade_stats.total_pnl += pnl
                trade_stats.trades_today += 1
            return
    except Exception as e:
        logging.error(f"Exit logic error: {e}")

# === [MAIN LOOP] ===
def main():
    try:
        keep_alive()
        console.print("🔄 Connecting to Binance...")
        client.get_account()
        console.print("✅ Connected to Binance API")
        check_existing_position()
        console.print("🤖 Bot is starting...")
        while True:
            execute_trade()
            update_overall_status(get_indicators())
    except KeyboardInterrupt:
        console.print("\n👋 Bot stopped by user")
    except Exception as e:
        console.print(f"\n❌ Fatal error: {e}")

if __name__ == "__main__":
    main()
