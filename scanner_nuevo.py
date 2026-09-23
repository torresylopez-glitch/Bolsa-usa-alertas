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

STOCK_TICKERS = [
    # Estados Unidos
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","AVGO","TSLA",
    "AMD","NFLX","JPM","V","MA","COST","WMT","LLY","XOM","ORCL",
    "CRM","PLTR","QCOM","MU","INTC","AMAT","UBER","PANW","ADBE",

    # Europa
    "IBE.MC","BBVA.MC","SAN.MC","ITX.MC","REP.MC","TEF.MC",
    "SAP.DE","SIE.DE","ALV.DE","DTE.DE",
    "AIR.PA","SU.PA","MC.PA","TTE.PA",
    "ASML.AS","ADYEN.AS",
    "RACE.MI","ENEL.MI","ISP.MI"
]

# ETFs UCITS europeos en Xetra.
ETF_TICKERS = ["SXR8.DE", "SXRV.DE", "ZPDF.DE"]
TICKERS = STOCK_TICKERS + ETF_TICKERS

ETF_INFO = {
    "SXR8.DE": {
        "name": "iShares Core S&P 500 UCITS ETF",
        "isin": "IE00B5BMR087",
        "market": "XETRA",
        "ticker": "SXR8"
    },
    "SXRV.DE": {
        "name": "iShares NASDAQ 100 UCITS ETF",
        "isin": "IE00B53SZB19",
        "market": "XETRA",
        "ticker": "SXRV"
    },
    "ZPDF.DE": {
        "name": "SPDR S&P U.S. Financials Select Sector UCITS ETF",
        "isin": "IE00BWBXM500",
        "market": "XETRA",
        "ticker": "ZPDF"
    }
}

# Filtros
MIN_SCORE = 75
MAX_SUPPORT_DISTANCE = 0.03
MAX_RSI = 45

# Gatillo de confirmación
MAX_REBOUND_DISTANCE = 0.015
MIN_VOLUME_CONFIRMATION = 1.15
REQUIRE_CLOSE_ABOVE_PREVIOUS_HIGH = True

PERIOD = "1y"
INTERVAL = "1d"
NEWS_HOURS = 24
MAX_NEWS = 8

# Traducción de titulares extranjeros.
# Recomendado: añadir GOOGLE_TRANSLATE_API_KEY como Secret de GitHub.
# Si no existe, se intenta el endpoint público de Google Translate como
# respaldo y, si falla, se conserva el titular original y se busca una
# alternativa en español. No se inventa ninguna traducción.
GOOGLE_TRANSLATE_API_KEY = os.getenv("GOOGLE_TRANSLATE_API_KEY", "")
TRANSLATION_TIMEOUT = 15

# Filtro de mercado general
MARKET_TICKER = "^GSPC"
MARKET_PERIOD = "1y"
MARKET_MIN_TREND = True

# Filtro de resultados empresariales
EARNINGS_BLACKOUT_DAYS = 3

# Gestión de riesgo (configurable por variables de entorno)
CAPITAL_EUR = float(os.getenv("CAPITAL_EUR", "5000"))
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.01"))

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
    "PANW": "Palo Alto Networks", "ADBE": "Adobe",

    # Europa
    "IBE.MC": "Iberdrola", "BBVA.MC": "BBVA", "SAN.MC": "Banco Santander",
    "ITX.MC": "Inditex", "REP.MC": "Repsol", "TEF.MC": "Telefonica",
    "SAP.DE": "SAP", "SIE.DE": "Siemens", "ALV.DE": "Allianz",
    "DTE.DE": "Deutsche Telekom", "AIR.PA": "Airbus",
    "SU.PA": "Schneider Electric", "MC.PA": "LVMH",
    "TTE.PA": "TotalEnergies", "ASML.AS": "ASML",
    "ADYEN.AS": "Adyen", "RACE.MI": "Ferrari",
    "ENEL.MI": "Enel", "ISP.MI": "Intesa Sanpaolo"
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
             "autonomous driving","robotaxi","regulation"],

    # Europa
    "IBE.MC": ["electricity","renewable","renewables","power grid","energy",
               "regulation","spain"],
    "BBVA.MC": ["bank","banks","interest rates","turkey","mexico","spain"],
    "SAN.MC": ["bank","banks","interest rates","brazil","mexico","spain"],
    "ITX.MC": ["retail","fashion","consumer","zara","spain"],
    "REP.MC": ["oil","crude","brent","wti","opec","energy","refinery"],
    "TEF.MC": ["telecom","5g","spain","brazil","debt","regulation"],
    "SAP.DE": ["software","cloud","ai","artificial intelligence","enterprise software"],
    "SIE.DE": ["industrial","automation","infrastructure","energy","rail"],
    "ALV.DE": ["insurance","insurer","interest rates","catastrophe"],
    "DTE.DE": ["telecom","5g","germany","fiber","regulation"],
    "AIR.PA": ["airbus","aircraft","aviation","defense","orders","supply chain"],
    "SU.PA": ["schneider","automation","electrification","data center","energy"],
    "MC.PA": ["lvmh","luxury","china","consumer","fashion"],
    "TTE.PA": ["oil","crude","brent","wti","opec","energy","lng"],
    "ASML.AS": ["semiconductor","chips","lithography","china","export restrictions"],
    "ADYEN.AS": ["payments","fintech","ecommerce","consumer"],
    "RACE.MI": ["ferrari","luxury","automotive","cars","china"],
    "ENEL.MI": ["electricity","renewable","renewables","energy","power grid"],
    "ISP.MI": ["bank","banks","interest rates","italy","eurozone"]
}

def is_etf(ticker):
    return ticker in ETF_INFO

def display_ticker(ticker):
    return ETF_INFO[ticker]["ticker"] if is_etf(ticker) else ticker

def display_name(ticker):
    return ETF_INFO[ticker]["name"] if is_etf(ticker) else COMPANY_NAMES.get(ticker, ticker)

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def analyze(ticker):
    df = yf.download(
        ticker, period=PERIOD, interval=INTERVAL,
        auto_adjust=True, progress=False, threads=False
    )

    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    needed = {"Close", "Open", "High", "Low", "Volume"}
    if not needed.issubset(df.columns) or len(df) < 210:
        return None

    df = df.dropna(subset=list(needed)).copy()
    close = df["Close"]
    volume = df["Volume"]

    df["SMA50"] = close.rolling(50).mean()
    df["SMA200"] = close.rolling(200).mean()
    df["RSI"] = rsi(close)
    df["VOL20"] = volume.rolling(20).mean()

    last = df.iloc[-1]
    previous = df.iloc[-2]

    price = float(last["Close"])
    open_price = float(last["Open"])
    last_high = float(last["High"])
    last_low = float(last["Low"])
    previous_high = float(previous["High"])

    sma50 = float(last["SMA50"])
    sma200 = float(last["SMA200"])
    rsi14 = float(last["RSI"])

    vol_ratio = (
        float(last["Volume"] / last["VOL20"])
        if last["VOL20"] and not pd.isna(last["VOL20"]) else 0
    )

    support = float(df["Low"].tail(20).min())
    distance_support = (price - support) / price if price else math.inf

    rebound_distance = (last_low - support) / support if support else math.inf
    bullish_candle = price > open_price
    close_above_previous_high = (
        price > previous_high if REQUIRE_CLOSE_ABOVE_PREVIOUS_HIGH else True
    )
    support_reaction = rebound_distance <= MAX_REBOUND_DISTANCE
    volume_confirmation = vol_ratio >= MIN_VOLUME_CONFIRMATION

    rebound_confirmed = (
        bullish_candle
        and support_reaction
        and volume_confirmation
        and close_above_previous_high
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
        reasons.append("volumen >= 1,15x media")

    if distance_support <= 0.03:
        score += 20
        reasons.append("a <=3% del soporte")
    elif distance_support <= 0.06:
        score += 10
        reasons.append("a <=6% del soporte")

    if rebound_confirmed:
        reasons.append("REBOTE CONFIRMADO")

    stop = support * 0.98
    risk = price - stop
    target1 = price + 2 * risk if risk > 0 else np.nan
    target2 = price + 3 * risk if risk > 0 else np.nan
    reward_risk = (target1 - price) / risk if risk > 0 else 0

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
        "reward_risk": reward_risk,
        "reasons": reasons,
        "distance_support": distance_support,
        "rebound_distance": rebound_distance,
        "bullish_candle": bullish_candle,
        "close_above_previous_high": close_above_previous_high,
        "support_reaction": support_reaction,
        "volume_confirmation": volume_confirmation,
        "rebound_confirmed": rebound_confirmed,
        "earnings": None,
        "position": None
    }

def get_market_regime():
    """Comprueba si el S&P 500 mantiene una tendencia diaria favorable."""
    try:
        df = yf.download(
            MARKET_TICKER, period=MARKET_PERIOD, interval="1d",
            auto_adjust=True, progress=False, threads=False
        )
        if df.empty:
            return {
                "ok": False, "status": "SIN DATOS",
                "price": np.nan, "sma50": np.nan, "sma200": np.nan,
                "reason": "No se pudieron obtener datos del S&P 500."
            }
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        close = df["Close"].dropna()
        if len(close) < 200:
            return {
                "ok": False, "status": "SIN DATOS",
                "price": np.nan, "sma50": np.nan, "sma200": np.nan,
                "reason": "Datos insuficientes del S&P 500."
            }
        sma50 = float(close.rolling(50).mean().iloc[-1])
        sma200 = float(close.rolling(200).mean().iloc[-1])
        price = float(close.iloc[-1])
        ok = price > sma200 and sma50 > sma200
        return {
            "ok": ok, "status": "FAVORABLE" if ok else "DESFAVORABLE",
            "price": price, "sma50": sma50, "sma200": sma200,
            "reason": "Precio > SMA200 y SMA50 > SMA200" if ok
                      else "No se cumplen precio > SMA200 y SMA50 > SMA200"
        }
    except Exception as e:
        return {
            "ok": False, "status": "ERROR",
            "price": np.nan, "sma50": np.nan, "sma200": np.nan,
            "reason": str(e)
        }

def get_earnings_status(ticker):
    """Bloquea acciones alrededor de resultados. Para ETF no aplica."""
    if is_etf(ticker):
        return {"blocked": False, "status": "NO APLICA", "date": None, "days": None}
    try:
        dates = yf.Ticker(ticker).get_earnings_dates(limit=8)
        if dates is None or len(dates) == 0:
            return {"blocked": False, "status": "SIN FECHA", "date": None, "days": None}

        now = pd.Timestamp.now(tz="UTC")
        best = None
        best_abs = None
        for idx in dates.index:
            dt = pd.Timestamp(idx)
            if dt.tzinfo is None:
                dt = dt.tz_localize("UTC")
            else:
                dt = dt.tz_convert("UTC")
            diff_days = (dt - now).total_seconds() / 86400.0
            if best is None or abs(diff_days) < best_abs:
                best = dt
                best_abs = abs(diff_days)

        if best is None:
            return {"blocked": False, "status": "SIN FECHA", "date": None, "days": None}

        blocked = best_abs <= EARNINGS_BLACKOUT_DAYS
        if blocked:
            status = "BLOQUEADO POR RESULTADOS"
        elif best > now:
            status = "RESULTADOS PRÓXIMOS"
        else:
            status = "RESULTADOS PASADOS"
        return {"blocked": blocked, "status": status, "date": best, "days": best_abs}
    except Exception as e:
        # Si el proveedor no entrega calendario, no inventamos una fecha.
        return {"blocked": False, "status": "SIN DATOS", "date": None, "days": None, "error": str(e)}

def get_eurusd():
    """USD por EUR para convertir riesgo/posición de acciones USA a euros."""
    try:
        df = yf.download("EURUSD=X", period="5d", interval="1d",
                         auto_adjust=True, progress=False, threads=False)
        if df.empty:
            return 1.0
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        value = float(df["Close"].dropna().iloc[-1])
        return value if value > 0 else 1.0
    except Exception:
        return 1.0

def position_sizing(entry, stop, ticker, eurusd):
    """Calcula capital asignado y número de títulos respetando riesgo máximo."""
    stop_distance = max(entry - stop, 0)
    if stop_distance <= 0:
        return {"shares": 0, "capital_used_eur": 0, "risk_eur": 0, "currency": "EUR" if is_etf(ticker) else "USD"}

    max_risk_eur = CAPITAL_EUR * RISK_PER_TRADE
    if is_etf(ticker):
        price_eur = entry
        stop_distance_eur = stop_distance
        currency = "EUR"
    else:
        # Yahoo cotiza estas acciones en USD; convertimos a EUR.
        price_eur = entry / eurusd
        stop_distance_eur = stop_distance / eurusd
        currency = "USD"

    shares_by_risk = max_risk_eur / stop_distance_eur
    shares_by_capital = CAPITAL_EUR / price_eur
    shares = max(0, math.floor(min(shares_by_risk, shares_by_capital)))
    capital_used_eur = shares * price_eur
    risk_eur = shares * stop_distance_eur
    return {
        "shares": shares,
        "capital_used_eur": capital_used_eur,
        "risk_eur": risk_eur,
        "currency": currency,
        "max_risk_eur": max_risk_eur
    }

def google_news(query, lang="es"):
    """Obtiene noticias recientes de Google News RSS.
    lang='es' busca en español; lang='en' busca prensa internacional.
    """
    try:
        if lang == "en":
            params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
        else:
            params = {"q": query, "hl": "es-ES", "gl": "ES", "ceid": "ES:es"}

        url = "https://news.google.com/rss/search?" + "&".join(
            f"{quote(str(k))}={quote(str(v))}" for k, v in params.items()
        )
        response = requests.get(
            url, timeout=20, headers={"User-Agent": "Mozilla/5.0"}
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
                    pub_date, "%a, %d %b %Y %H:%M:%S %Z"
                ).replace(tzinfo=timezone.utc)
            except Exception:
                dt = now

            if now - dt > timedelta(hours=NEWS_HOURS):
                continue

            news.append({
                "title": title,
                "link": link,
                "source": source,
                "date": dt,
                "lang": lang,
            })
        return news
    except Exception as e:
        print(f"Error buscando noticias [{lang}] '{query}': {e}")
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
    result.sort(key=lambda x: x["date"], reverse=True)
    return result[:MAX_NEWS]

def looks_spanish(title):
    """Heurística sencilla para evitar traducir dos veces un titular."""
    t = " " + title.lower() + " "
    spanish_markers = [
        " el ", " la ", " los ", " las ", " una ", " un ", " de ",
        " del ", " que ", " por ", " para ", " con ", " y ", " en ",
        " sube ", " baja ", " acciones ", " empresa ", " mercado "
    ]
    return sum(1 for marker in spanish_markers if marker in t) >= 2


def translate_to_spanish(text_to_translate):
    """Traduce un titular al español.

    1) Google Cloud Translation si se ha configurado la API key.
    2) Endpoint público de Google Translate como respaldo.
    3) None si no se puede traducir.
    """
    if not text_to_translate:
        return None

    if looks_spanish(text_to_translate):
        return text_to_translate

    # Opción oficial: Google Cloud Translation API.
    if GOOGLE_TRANSLATE_API_KEY:
        try:
            url = "https://translation.googleapis.com/language/translate/v2"
            response = requests.post(
                url,
                params={"key": GOOGLE_TRANSLATE_API_KEY},
                json={
                    "q": text_to_translate,
                    "target": "es",
                    "format": "text",
                },
                timeout=TRANSLATION_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            translated = (
                data.get("data", {})
                    .get("translations", [{}])[0]
                    .get("translatedText")
            )
            if translated:
                return translated.strip()
        except Exception as e:
            print(f"Google Cloud Translation no disponible: {e}")

    # Respaldo práctico para GitHub Actions sin API key.
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": "es",
            "dt": "t",
            "q": text_to_translate,
        }
        response = requests.get(url, params=params, timeout=TRANSLATION_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        translated = "".join(
            part[0] for part in data[0]
            if isinstance(part, list) and part and part[0]
        )
        if translated:
            return translated.strip()
    except Exception as e:
        print(f"Traducción automática de respaldo no disponible: {e}")

    return None


def enrich_positive_news(news_item):
    """Añade traducción española sin alterar el titular original."""
    item = dict(news_item)
    original = item.get("title", "")
    item["original_title"] = original

    translated = translate_to_spanish(original)
    if translated:
        item["translated_title"] = translated
        item["translation_ok"] = True
    else:
        item["translated_title"] = None
        item["translation_ok"] = False

    return item


def analyze_news(ticker):
    """Analiza noticias en español + prensa internacional reciente."""
    company = display_name(ticker)

    if is_etf(ticker):
        spanish_queries = [
            f'"{company}"',
            f'"{display_ticker(ticker)}" ETF',
            f'"{company}" noticias',
            'mercados EEUU tipos interés Fed inflación'
        ]
        international_queries = [
            f'"{company}" ETF',
            f'"{display_ticker(ticker)}" ETF',
            'US markets Fed interest rates inflation'
        ]
    else:
        spanish_queries = [
            f'"{company}" {ticker}',
            f'"{company}" acciones',
            f'"{company}" noticias',
            f'"{company}" buenas noticias',
            f'"{company}" resultados positivos',
            f'"{company}" mejora previsiones',
            f'"{company}" contrato acuerdo',
            f'"{company}" recomendación positiva'
        ]
        international_queries = [
            f'"{company}" stock',
            f'"{company}" shares',
            f'"{company}" earnings',
            f'"{company}" outlook',
            f'"{company}" guidance',
            f'"{company}" analyst upgrade',
            f'"{company}" contract deal'
        ]

        for topic in SPECIAL_TOPICS.get(ticker, [])[:6]:
            international_queries.append(f'"{company}" {topic}')

    if ticker == "XOM":
        international_queries += [
            "oil price OPEC Iran Hormuz",
            "Brent crude Middle East Iran",
            "Strait of Hormuz oil"
        ]
    elif ticker in ["NVDA", "AMD", "MU", "INTC", "AMAT", "AVGO", "QCOM"]:
        international_queries += [
            "semiconductor China export restrictions",
            "AI chips export restrictions",
            "semiconductor tariffs China"
        ]
    else:
        international_queries += [
            "US stocks Fed interest rates inflation",
            "global markets tariffs regulation"
        ]

    all_news = []

    for query in spanish_queries:
        all_news.extend(google_news(query, lang="es"))

    for query in international_queries:
        all_news.extend(google_news(query, lang="en"))

    news = unique_news(all_news)

    if not news:
        return {
            "news": [], "positive": 0, "negative": 0,
            "positive_news": [], "risk": "SIN DATOS",
            "summary": "No se han encontrado noticias recientes suficientes."
        }

    positive_words = [
        # Inglés
        "beats", "beat", "raises guidance", "upgrade", "upgraded",
        "strong demand", "record revenue", "record profit", "approval",
        "approved", "deal", "contract", "acquisition", "buyback",
        "dividend increase", "bullish", "surges", "rises",
        "positive outlook", "strong results", "better than expected",
        "partnership", "wins order", "order win",
        # Español
        "supera previsiones", "supera las previsiones", "eleva previsiones",
        "mejora previsiones", "mejora sus previsiones", "aumenta previsiones",
        "crece el beneficio", "aumenta el beneficio", "beneficio récord",
        "ingresos récord", "fuerte demanda", "nuevo contrato", "contrato",
        "acuerdo", "adquisición", "recompra de acciones",
        "sube la recomendación", "recomendación de compra",
        "perspectivas positivas", "buenas perspectivas", "aprobación",
        "aprueba", "crecimiento", "alcista", "sube", "supera expectativas"
    ]

    negative_words = [
        # Inglés
        "miss", "misses", "cuts guidance", "downgrade", "downgraded",
        "lawsuit", "investigation", "probe", "ban", "banned", "sanctions",
        "tariff", "tariffs", "war", "conflict", "recession", "layoffs",
        "recall", "warning", "delay", "weak demand", "decline", "falls",
        "drop", "crisis", "cuts outlook", "negative outlook",
        "worse than expected", "regulatory action",
        # Español
        "no cumple previsiones", "recorta previsiones", "rebaja previsiones",
        "rebaja sus previsiones", "recorte", "baja la recomendación",
        "recomendación de venta", "demanda débil", "caída del beneficio",
        "caen los ingresos", "investigación", "demanda judicial", "sanciones",
        "aranceles", "guerra", "recesión", "despidos", "retraso", "crisis",
        "cae", "caída", "baja", "perspectivas negativas"
    ]

    positive = 0
    negative = 0

    for item in news:
        title = item["title"].lower()
        positive += sum(1 for word in positive_words if word in title)
        negative += sum(1 for word in negative_words if word in title)

    risk_keywords = [
        "war", "conflict", "iran", "hormuz", "sanctions", "tariff",
        "tariffs", "investigation", "lawsuit", "regulation", "ban",
        "recession", "interest rates", "inflation",
        "guerra", "conflicto", "sanciones", "aranceles",
        "investigación", "recesión", "inflación"
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

    positive_news = []
    for item in news:
        title_lower = item["title"].lower()
        if any(word in title_lower for word in positive_words):
            positive_news.append(enrich_positive_news(item))

    summary = []
    if positive > 0:
        summary.append(f"{positive} indicador(es) positivo(s)")
    if negative > 0:
        summary.append(f"{negative} indicador(es) negativo(s)")
    if risk_hits:
        summary.append("Riesgos: " + ", ".join(risk_hits[:5]))
    if not summary:
        summary.append("No se detecta un sesgo claro en las noticias.")

    return {
        "news": news,
        "positive": positive,
        "negative": negative,
        "positive_news": positive_news[:3],
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

    positive_news = news_data.get("positive_news", [])
    if positive_news:
        item = positive_news[0]
        source = item["source"] or "Fuente desconocida"
        date_text = item["date"].astimezone().strftime("%d/%m/%Y %H:%M")

        lines.append("🇪🇸 NOTICIA POSITIVA EN ESPAÑOL:")
        if item.get("translation_ok") and item.get("translated_title"):
            lines.append(f"• {item['translated_title']}")
            if item.get("lang") == "en":
                lines.append(f"  Original: {item['original_title']}")
        else:
            lines.append(f"• {item['title']}")
            lines.append("  (No se pudo traducir automáticamente)")
        lines.append(f"  Fuente: {source}")
        lines.append(f"  Fecha: {date_text}")
        if item.get("link"):
            lines.append(f"  Enlace: {item['link']}")
        lines.append("")
    else:
        lines.append(
            "🇪🇸 NOTICIA POSITIVA: no se ha encontrado una "
            "suficientemente clara en las últimas 24 horas."
        )
        lines.append("")

    lines.append("Otras noticias analizadas:")
    for item in news[:5]:
        source = item["source"] or "Fuente desconocida"
        date_text = item["date"].astimezone().strftime("%d/%m %H:%M")
        lines.append(f"• {item['title']}")
        lines.append(f"  Fuente: {source} | {date_text}")

    return "\n".join(lines)

def format_price(value, ticker):
    return f"{'€' if is_etf(ticker) else '$'}{value:.2f}"

def format_alert(x):
    news_text = format_news(x["news_data"])
    extra = ""

    if is_etf(x["ticker"]):
        info = ETF_INFO[x["ticker"]]
        extra = (
            f"📦 UCITS / {info['market']}\n"
            f"🔎 ISIN: {info['isin']}\n"
        )

    return (
        f"💎 CHOLLO CONFIRMADO — {display_ticker(x['ticker'])}\n\n"
        f"{extra}"
        f"💰 Precio actual: {format_price(x['price'], x['ticker'])}\n"
        f"📊 Puntuación técnica: {x['score']}/100\n"
        f"📉 RSI: {x['rsi']:.1f}\n"
        f"📍 Soporte: {format_price(x['support'], x['ticker'])}\n"
        f"📏 Distancia soporte: {x['distance_support']:.1%}\n"
        f"📈 Volumen: {x['vol_ratio']:.2f}x media\n\n"
        f"🟢 ENTRADA CONFIRMADA: {format_price(x['price'], x['ticker'])}\n"
        f"🛑 STOP: {format_price(x['stop'], x['ticker'])}\n"
        f"🎯 OBJETIVO 1: {format_price(x['target1'], x['ticker'])}\n"
        f"🎯 OBJETIVO 2: {format_price(x['target2'], x['ticker'])}\n"
        f"⚖️ Relación beneficio/riesgo: {x['reward_risk']:.1f}:1\n"
        f"💶 Capital aprox.: {x['position']['capital_used_eur']:.2f} €\n"
        f"🧮 Títulos: {x['position']['shares']}\n"
        f"⚠️ Riesgo hasta stop: {x['position']['risk_eur']:.2f} € "
        f"(máx. {x['position']['max_risk_eur']:.2f} €)\n\n"
        f"🔥 CONFIRMACIÓN DE ENTRADA:\n"
        f"• Soporte defendido: {'SÍ' if x['support_reaction'] else 'NO'}\n"
        f"• Vela alcista: {'SÍ' if x['bullish_candle'] else 'NO'}\n"
        f"• Cierre > máximo vela anterior: "
        f"{'SÍ' if x['close_above_previous_high'] else 'NO'}\n"
        f"• Volumen >= {MIN_VOLUME_CONFIRMATION:.2f}x: "
        f"{'SÍ' if x['volume_confirmation'] else 'NO'}\n"
        f"• REBOTE CONFIRMADO: {'SÍ' if x['rebound_confirmed'] else 'NO'}\n"
        f"• Mercado S&P 500: FAVORABLE\n"
        f"• Resultados: {x['earnings']['status']}\n\n"
        f"📈 Motivos técnicos:\n{', '.join(x['reasons'])}\n\n"
        f"{news_text}\n\n"
        "🟢 SEÑAL FINAL: CHOLLO CONFIRMADO\n\n"
        f"⚠️ Filtros: score >= {MIN_SCORE}, RSI <= {MAX_RSI}, "
        f"soporte <= {MAX_SUPPORT_DISTANCE:.0%}, rebote confirmado, "
        "mercado favorable, sin bloqueo de resultados, noticias no negativas "
        "y riesgo de la operación controlado."
    )

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("\nTelegram no configurado. Resultado:\n")
        print(message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    if len(message) > 3900:
        message = message[:3900]

    response = requests.post(
        url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
        timeout=20
    )
    response.raise_for_status()

def main():
    results = []

    print("========================================")
    print("   ESCÁNER DE CHOLLOS PARA DEGIRO")
    print("========================================\n")
    print(
        f"Filtro CHOLLO: score >= {MIN_SCORE}, "
        f"RSI <= {MAX_RSI}, soporte <= {MAX_SUPPORT_DISTANCE:.0%}"
    )
    print(
        "Gatillo: rebote confirmado + volumen "
        f">= {MIN_VOLUME_CONFIRMATION:.2f}x"
    )
    print("Noticias: español + prensa internacional | traducción automática al español")
    print(f"Capital de referencia: {CAPITAL_EUR:.0f} EUR | Riesgo máximo por operación: {RISK_PER_TRADE:.1%}")

    market = get_market_regime()
    print(
        f"S&P 500: {market['status']} | "
        f"precio={market['price']:.2f} | SMA50={market['sma50']:.2f} | SMA200={market['sma200']:.2f}"
        if np.isfinite(market.get("price", np.nan)) else
        f"S&P 500: {market['status']} | {market['reason']}"
    )
    eurusd = get_eurusd()
    print(f"EUR/USD de referencia: {eurusd:.4f}\n")

    for ticker in TICKERS:
        try:
            result = analyze(ticker)
            if result:
                results.append(result)
                print(
                    f"{display_ticker(ticker)}: {result['score']}/100 | "
                    f"rebote={'SÍ' if result['rebound_confirmed'] else 'NO'}"
                )
        except Exception as e:
            print(f"{display_ticker(ticker)}: error técnico ({e})")

    candidates = sorted(
        [r for r in results if r["score"] >= MIN_SCORE],
        key=lambda x: x["score"], reverse=True
    )

    print(f"\nCandidatas >= {MIN_SCORE}/100: {len(candidates)}")
    signals = []

    for candidate in candidates:
        ticker = candidate["ticker"]
        print(f"\nAnalizando noticias de {display_ticker(ticker)}...")

        try:
            news_data = analyze_news(ticker)
            candidate["news_data"] = news_data
            earnings = get_earnings_status(ticker)
            candidate["earnings"] = earnings
            candidate["position"] = position_sizing(
                candidate["price"], candidate["stop"], ticker, eurusd
            )
            print(
                f"{display_ticker(ticker)}: {news_data['risk']} | "
                f"resultados={earnings['status']}"
            )

            distance_support = (
                (candidate["price"] - candidate["support"])
                / candidate["price"]
            )

            # ====================================================
            # FILTRO ESTRICTO DE CHOLLO + GATILLO
            # ====================================================
            chollo = (
                candidate["score"] >= MIN_SCORE
                and distance_support <= MAX_SUPPORT_DISTANCE
                and candidate["rsi"] <= MAX_RSI
                and news_data.get("risk") in ("POSITIVO", "MIXTO / NEUTRO")
                and candidate["rebound_confirmed"]
                and candidate["reward_risk"] >= 2.0
                and market["ok"]
                and not earnings.get("blocked", False)
                and candidate["position"].get("shares", 0) >= 1
            )

            if chollo:
                candidate["chollo"] = True
                signals.append(candidate)

        except Exception as e:
            print(f"{display_ticker(ticker)}: error noticias ({e})")
            candidate["news_data"] = {
                "news": [], "positive": 0, "negative": 0, "positive_news": [],
                "risk": "ERROR",
                "summary": "No se pudo completar el análisis de noticias."
            }

    if not signals:
        message = (
            "📊 ESCÁNER DE CHOLLOS PARA DEGIRO\n\n"
            "No hay oportunidades que cumplan TODOS "
            "los filtros del CHOLLO CONFIRMADO.\n\n"
            f"• Puntuación mínima: {MIN_SCORE}/100\n"
            f"• RSI máximo: {MAX_RSI}\n"
            f"• Distancia al soporte: <= {MAX_SUPPORT_DISTANCE:.0%}\n"
            "• Rebote confirmado: SÍ\n"
            f"• Volumen mínimo: >= {MIN_VOLUME_CONFIRMATION:.2f}x media\n"
            "• Cierre > máximo de la vela anterior: SÍ\n"
            "• Noticias: POSITIVAS o MIXTAS/NEUTRAS\n"
            "• S&P 500: tendencia favorable\n"
            f"• Resultados: bloqueo +/- {EARNINGS_BLACKOUT_DAYS} días\n"
            f"• Riesgo por operación: {RISK_PER_TRADE:.1%} del capital\n"
            "• ETF: UCITS europeos incluidos"
        )
        send_telegram(message)
        print("\n" + message)
        return

    for signal in signals:
        message = format_alert(signal)
        send_telegram(message)
        print("\n" + message + "\n")
        print("========================================")

if __name__ == "__main__":
    main()
