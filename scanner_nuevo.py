import os
import math
import requests
import numpy as np
import pandas as pd
import yfinance as yf
import xml.etree.ElementTree as ET

from urllib.parse import quote
from datetime import datetime, timezone, timedelta


# ============================================================
# CONFIGURACIÓN
# ============================================================

TICKERS = ["SPY",
    "QQQ",
    "IWM",
    "DIA",
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "XLI",
    "XLP",
    "XLY",
    "XLU",
    "XLB",
    "SMH",
    "SOXX",
    "GLD",
    "SLV",
    "TLT",
    "HYG",
    "EEM",
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","AVGO","TSLA",
    "AMD","NFLX","JPM","V","MA","COST","WMT","LLY","XOM","ORCL",
    "CRM","PLTR","QCOM","MU","INTC","AMAT","UBER","PANW","ADBE"
]

MIN_SCORE = 85
PERIOD = "1y"
INTERVAL = "1d"
NEWS_HOURS = 24
MAX_NEWS = 8

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


COMPANY_NAMES = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA",
    "AMZN": "Amazon", "GOOGL": "Alphabet Google",
    "META": "Meta Platforms Facebook", "AVGO": "Broadcom",
    "TSLA": "Tesla", "AMD": "AMD", "NFLX": "Netflix",
    "JPM": "JPMorgan", "V": "Visa", "MA": "Mastercard",
    "COST": "Costco", "WMT": "Walmart", "LLY": "Eli Lilly",
    "XOM": "Exxon Mobil", "ORCL": "Oracle", "CRM": "Salesforce",
    "PLTR": "Palantir", "QCOM": "Qualcomm", "MU": "Micron",
    "INTC": "Intel", "AMAT": "Applied Materials", "UBER": "Uber",
    "PANW": "Palo Alto Networks", "ADBE": "Adobe"
}


SPECIAL_TOPICS = {
    "XOM": ["oil","crude","brent","wti","opec","iran","hormuz",
            "strait of hormuz","middle east","sanctions","production",
            "refinery","energy"],
    "LLY": ["weight loss","obesity","diabetes","drug approval","fda",
            "clinical trial","pharmaceutical"],
    "NVDA": ["ai","artificial intelligence","chips","semiconductor",
             "china","export restrictions","data center"],
    "AMD": ["ai","artificial intelligence","chips","semiconductor",
            "china","export restrictions"],
    "MU": ["memory","dram","nand","semiconductor","chips","ai"],
    "INTC": ["semiconductor","chips","foundry","china","export restrictions"],
    "AMAT": ["semiconductor","chips","equipment","china","export restrictions"],
    "TSLA": ["electric vehicles","ev","china","tariffs",
             "autonomous driving","robotaxi","regulation"]
}


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period, adjust=False, min_periods=period
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period, adjust=False, min_periods=period
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    return 100 - (100 / (1 + rs))


def analyze(ticker):

    df = yf.download(
        ticker,
        period=PERIOD,
        interval=INTERVAL,
        auto_adjust=True,
        progress=False,
        threads=False
    )

    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    needed = {"Close", "High", "Low", "Volume"}

    if not needed.issubset(df.columns):
        return None

    if len(df) < 210:
        return None

    df = df.dropna(subset=list(needed)).copy()

    close = df["Close"]
    volume = df["Volume"]

    df["SMA20"] = close.rolling(20).mean()
    df["SMA50"] = close.rolling(50).mean()
    df["SMA200"] = close.rolling(200).mean()
    df["RSI"] = rsi(close)
    df["VOL20"] = volume.rolling(20).mean()

    last = df.iloc[-1]

    price = float(last["Close"])
    sma20 = float(last["SMA20"])
    sma50 = float(last["SMA50"])
    sma200 = float(last["SMA200"])
    rsi14 = float(last["RSI"])

    vol_ratio = (
        float(last["Volume"] / last["VOL20"])
        if last["VOL20"] and not pd.isna(last["VOL20"])
        else 0
    )

    support = float(df["Low"].tail(20).min())

    distance_support = (
        (price - support) / price if price else math.inf
    )

    score = 0
    reasons = []

    if price > sma200:
        score += 20
        reasons.append("precio > media 200")

    if sma50 > sma200:
        score += 15
        reasons.append("media 50 > media 200")

    if price > sma50:
        score += 10
        reasons.append("precio > media 50")

    if rsi14 < 30:
        score += 25
        reasons.append("RSI < 30")
    elif 30 <= rsi14 <= 45:
        score += 20
        reasons.append("RSI 30–45")
    elif rsi14 <= 55:
        score += 8

    if vol_ratio >= 1.5:
        score += 15
        reasons.append("volumen >= 1,5x media")
    elif vol_ratio >= 1.15:
        score += 8
        reasons.append("volumen > media")

    if distance_support <= 0.03:
        score += 20
        reasons.append("a <=3% del soporte")
    elif distance_support <= 0.06:
        score += 10
        reasons.append("a <=6% del soporte")

    stop = support * 0.98
    risk = price - stop
    target1 = price + 2 * risk if risk > 0 else np.nan
    target2 = price + 3 * risk if risk > 0 else np.nan

    return {
        "ticker": ticker,
        "price": price,
        "score": score,
        "rsi": rsi14,
        "vol_ratio": vol_ratio,
        "support": support,
        "stop": stop,
        "target1": target1,
        "target2": target2,
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "reasons": reasons
    }


def google_news(query):

    try:
        encoded_query = quote(query)

        url = (
            "https://news.google.com/rss/search?"
            f"q={encoded_query}"
            "&hl=en-US&gl=US&ceid=US:en"
        )

        response = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        response.raise_for_status()
        root = ET.fromstring(response.content)

        news = []
        now = datetime.now(timezone.utc)

        for item in root.findall(".//item"):

            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "").strip()
            source = item.findtext("source", "").strip()

            if not title:
                continue

            try:
                dt = datetime.strptime(
                    pub_date,
                    "%a, %d %b %Y %H:%M:%S %Z"
                ).replace(tzinfo=timezone.utc)
            except Exception:
                dt = now

            age = now - dt

            if age > timedelta(hours=NEWS_HOURS):
                continue

            news.append({
                "title": title,
                "link": link,
                "source": source,
                "date": dt
            })

        return news

    except Exception as e:
        print(f"Error buscando noticias '{query}': {e}")
        return []


def unique_news(news):

    seen = set()
    result = []

    for item in news:

        key = item["title"].lower().strip()

        if key in seen:
            continue

        seen.add(key)
        result.append(item)

    result.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    return result[:MAX_NEWS]


def analyze_news(ticker):

    company = COMPANY_NAMES.get(ticker, ticker)

    queries = [
        f'"{company}" {ticker}',
        f'"{company}" stock',
        f'"{company}" news',
        f'"{ticker}" market risk'
    ]

    topics = SPECIAL_TOPICS.get(ticker, [])

    for topic in topics[:6]:
        queries.append(f'"{company}" {topic}')

    if ticker == "XOM":
        queries.extend([
            "oil price OPEC Iran Hormuz",
            "Brent crude Middle East Iran",
            "Strait of Hormuz oil",
            "United Nations Hormuz oil",
            "OPEC oil production"
        ])

    elif ticker in ["NVDA", "AMD", "MU", "INTC", "AMAT", "AVGO", "QCOM"]:
        queries.extend([
            "semiconductor China export restrictions",
            "AI chips export restrictions",
            "semiconductor tariffs China"
        ])

    else:
        queries.extend([
            "US stock market interest rates Fed inflation",
            "US stocks tariffs regulation"
        ])

    all_news = []

    for query in queries:
        all_news.extend(google_news(query))

    news = unique_news(all_news)

    if not news:
        return {
            "news": [],
            "positive": 0,
            "negative": 0,
            "risk": "SIN DATOS",
            "summary": "No se han encontrado noticias recientes suficientes."
        }

    positive_words = [
        "beats","beat","raises guidance","upgrade","upgraded",
        "strong demand","record revenue","record profit","approval",
        "approved","deal","contract","acquisition","buyback",
        "dividend increase","bullish"
    ]

    negative_words = [
        "miss","misses","cuts guidance","downgrade","downgraded",
        "lawsuit","investigation","probe","ban","banned","sanctions",
        "tariff","tariffs","war","conflict","recession","layoffs",
        "recall","warning","delay","weak demand","decline","falls",
        "drop","crisis"
    ]

    positive = 0
    negative = 0

    for item in news:

        title = item["title"].lower()

        positive += sum(
            1 for word in positive_words if word in title
        )

        negative += sum(
            1 for word in negative_words if word in title
        )

    risk_keywords = [
        "war","conflict","iran","hormuz","sanctions","tariff",
        "tariffs","investigation","lawsuit","regulation","ban",
        "recession","interest rates"
    ]

    risk_hits = []

    for item in news:

        title_lower = item["title"].lower()

        for keyword in risk_keywords:

            if keyword in title_lower and keyword not in risk_hits:
                risk_hits.append(keyword)

    if negative >= positive + 2:
        risk = "NEGATIVO"
    elif positive >= negative + 2:
        risk = "POSITIVO"
    elif risk_hits:
        risk = "RIESGO RELEVANTE"
    else:
        risk = "MIXTO / NEUTRO"

    summary = []

    if positive > 0:
        summary.append(
            f"{positive} indicador(es) positivo(s)"
        )

    if negative > 0:
        summary.append(
            f"{negative} indicador(es) negativo(s)"
        )

    if risk_hits:
        summary.append(
            "Riesgos: " + ", ".join(risk_hits[:5])
        )

    if not summary:
        summary.append(
            "No se detecta un sesgo claro en las noticias."
        )

    return {
        "news": news,
        "positive": positive,
        "negative": negative,
        "risk": risk,
        "summary": " | ".join(summary)
    }


def format_news(news_data):

    news = news_data["news"]

    if not news:
        return "📰 Noticias: no se encontraron datos recientes suficientes."

    lines = [
        f"📰 Noticias analizadas: {len(news)}",
        f"Impacto: {news_data['risk']}",
        news_data["summary"],
        ""
    ]

    for item in news[:5]:

        source = item["source"] or "Fuente"

        lines.append(
            f"• {item['title']}\n"
            f"  Fuente: {source}"
        )

    return "\n".join(lines)


def format_alert(x):

    news_data = x["news_data"]
    news_text = format_news(news_data)

    negative = news_data.get("negative", 0)
    risk = news_data.get("risk", "")

    if risk == "NEGATIVO" and negative >= 2:
        final_signal = "⚠️ SEÑAL FINAL: PRECAUCIÓN — esperar"
    else:
        final_signal = "🟢 SEÑAL FINAL: POSIBLE ENTRADA"

    return (
        f"🔔 POSIBLE ENTRADA — {x['ticker']}\n\n"

        f"💰 Precio actual: ${x['price']:.2f}\n"
        f"📊 Puntuación técnica: {x['score']}/100\n"
        f"📉 RSI: {x['rsi']:.1f}\n"
        f"📍 Soporte: ${x['support']:.2f}\n\n"

        f"🟢 ENTRADA ORIENTATIVA: ${x['price']:.2f}\n"
        f"🛑 STOP: ${x['stop']:.2f}\n"
        f"🎯 OBJETIVO 1: ${x['target1']:.2f}\n"
        f"🎯 OBJETIVO 2: ${x['target2']:.2f}\n\n"

        f"📈 Motivos técnicos:\n"
        f"{', '.join(x['reasons'])}\n\n"

        f"{news_text}\n\n"

        f"{final_signal}\n\n"

        "⚠️ La señal combina análisis técnico y noticias. "
        "Los niveles son orientativos y pueden cambiar."
    )


def send_telegram(message):

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:

        print("\nTelegram no configurado. Resultado:\n")
        print(message)
        return

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    if len(message) > 3900:
        message = message[:3900]

    response = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        },
        timeout=20
    )

    response.raise_for_status()


def main():

    results = []

    print("========================================")
    print("   ESCÁNER DE OPORTUNIDADES DE BOLSA")
    print("========================================")
    print()

    print("Analizando acciones...")

    for ticker in TICKERS:

        try:

            result = analyze(ticker)

            if result:

                results.append(result)

                print(
                    f"{ticker}: "
                    f"{result['score']}/100"
                )

        except Exception as e:

            print(
                f"{ticker}: error técnico ({e})"
            )

    candidates = sorted(
        [
            r for r in results
            if r["score"] >= MIN_SCORE
        ],
        key=lambda x: x["score"],
        reverse=True
    )

    print()
    print(
        f"Candidatas >= {MIN_SCORE}/100: "
        f"{len(candidates)}"
    )

    signals = []

    for candidate in candidates:

        ticker = candidate["ticker"]

        print()
        print(
            f"Analizando noticias de {ticker}..."
        )

        try:

            news_data = analyze_news(ticker)

            candidate["news_data"] = news_data

            print(
                f"{ticker}: "
                f"{news_data['risk']}"
            )

            signals.append(candidate)

        except Exception as e:

            print(
                f"{ticker}: error analizando noticias ({e})"
            )

            candidate["news_data"] = {
                "news": [],
                "positive": 0,
                "negative": 0,
                "risk": "ERROR",
                "summary": "No se pudo completar el análisis de noticias."
            }

            signals.append(candidate)

    if not signals:

        message = (
            "📊 ESCÁNER USA\n\n"
            "No hay oportunidades que cumplan "
            f"el umbral de {MIN_SCORE}/100."
        )

        send_telegram(message)

        print()
        print(message)

        return

    for signal in signals:

        message = format_alert(signal)

        send_telegram(message)

        print()
        print(message)
        print()
        print("========================================")


if __name__ == "__main__":
    main()
