import os
import math
import requests
import numpy as np
import pandas as pd
import yfinance as yf

TICKERS = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","AVGO","TSLA",
    "AMD","NFLX","JPM","V","MA","COST","WMT","LLY","XOM","ORCL",
    "CRM","PLTR","QCOM","MU","INTC","AMAT","UBER","PANW","ADBE"
]

MIN_SCORE = 75
PERIOD = "1y"
INTERVAL = "1d"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def analyze(ticker):
    df = yf.download(ticker, period=PERIOD, interval=INTERVAL,
                     auto_adjust=True, progress=False, threads=False)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    needed = {"Close", "High", "Low", "Volume"}
    if not needed.issubset(df.columns) or len(df) < 210:
        return None
    df = df.dropna(subset=list(needed)).copy()
    close, volume = df["Close"], df["Volume"]
    df["SMA20"] = close.rolling(20).mean()
    df["SMA50"] = close.rolling(50).mean()
    df["SMA200"] = close.rolling(200).mean()
    df["RSI"] = rsi(close)
    df["VOL20"] = volume.rolling(20).mean()
    last = df.iloc[-1]
    price = float(last["Close"])
    sma50, sma200 = float(last["SMA50"]), float(last["SMA200"])
    rsi14 = float(last["RSI"])
    vol_ratio = float(last["Volume"] / last["VOL20"]) if last["VOL20"] else 0
    support = float(df["Low"].tail(20).min())
    distance_support = (price - support) / price if price else math.inf

    score = 0
    reasons = []
    if price > sma200:
        score += 20; reasons.append("precio > media 200")
    if sma50 > sma200:
        score += 15; reasons.append("media 50 > media 200")
    if price > sma50:
        score += 10; reasons.append("precio > media 50")
    if rsi14 < 30:
        score += 25; reasons.append("RSI < 30")
    elif 30 <= rsi14 <= 45:
        score += 20; reasons.append("RSI 30–45")
    elif rsi14 <= 55:
        score += 8
    if vol_ratio >= 1.5:
        score += 15; reasons.append("volumen >= 1,5x media")
    elif vol_ratio >= 1.15:
        score += 8; reasons.append("volumen > media")
    if distance_support <= .03:
        score += 20; reasons.append("a <=3% del soporte")
    elif distance_support <= .06:
        score += 10; reasons.append("a <=6% del soporte")

    stop = support * .98
    risk = price - stop
    target1 = price + 2*risk if risk > 0 else np.nan
    target2 = price + 3*risk if risk > 0 else np.nan

    return {
        "ticker": ticker, "price": price, "score": score, "rsi": rsi14,
        "vol_ratio": vol_ratio, "support": support, "stop": stop,
        "target1": target1, "target2": target2, "reasons": reasons
    }

def format_alert(x):
    return (
        f"🔔 POSIBLE ENTRADA — {x['ticker']}\n\n"
        f"Precio: ${x['price']:.2f}\n"
        f"Señal: {x['score']}/100\n"
        f"RSI: {x['rsi']:.1f}\n"
        f"Soporte: ${x['support']:.2f}\n"
        f"Entrada orientativa: ${x['price']:.2f}\n"
        f"Stop orientativo: ${x['stop']:.2f}\n"
        f"Objetivo 1: ${x['target1']:.2f}\n"
        f"Objetivo 2: ${x['target2']:.2f}\n\n"
        f"Motivos: {', '.join(x['reasons'])}\n\n"
        "⚠️ Señal técnica, no garantía de subida."
    )

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("\nTelegram no configurado. Resultado:\n")
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=20)
    r.raise_for_status()

def main():
    results = []
    print("Analizando acciones...")
    for ticker in TICKERS:
        try:
            result = analyze(ticker)
            if result:
                results.append(result)
                print(f"{ticker}: {result['score']}/100")
        except Exception as e:
            print(f"{ticker}: error ({e})")

    signals = sorted(
        [r for r in results if r["score"] >= MIN_SCORE],
        key=lambda x: x["score"], reverse=True
    )

    if not signals:
        send_telegram("📊 ESCÁNER USA\n\nNo hay oportunidades que cumplan el umbral de 75/100.")
        print("\nNo hay señales >= 75/100.")
        return

    for signal in signals:
        send_telegram(format_alert(signal))
        print("\n" + format_alert(signal))

if __name__ == "__main__":
    main()
