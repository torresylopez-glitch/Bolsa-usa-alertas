import os
import math
import json
import hashlib
import requests
import numpy as np
import pandas as pd
import yfinance as yf
import xml.etree.ElementTree as ET

from urllib.parse import quote
from datetime import datetime, timezone, timedelta


# ============================================================
# ESCÁNER DE CHOLLOS PARA DEGIRO
# VERSIÓN DEFINITIVA
# ============================================================


# ============================================================
# UNIVERSO DE ACCIONES
# ============================================================

STOCK_TICKERS = [

    # USA
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META",
    "AVGO", "TSLA", "AMD", "NFLX", "JPM", "V", "MA",
    "COST", "WMT", "LLY", "XOM", "ORCL", "CRM",
    "PLTR", "QCOM", "MU", "INTC", "AMAT", "UBER",
    "PANW", "ADBE",

    # ESPAÑA
    "IBE.MC", "BBVA.MC", "SAN.MC", "ITX.MC",
    "REP.MC", "TEF.MC",

    # ALEMANIA
    "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE",

    # FRANCIA
    "AIR.PA", "SU.PA", "MC.PA", "TTE.PA",

    # PAÍSES BAJOS
    "ASML.AS", "ADYEN.AS",

    # ITALIA
    "RACE.MI", "ENEL.MI", "ISP.MI"
]


# ============================================================
# ETF UCITS EUROPEOS
# ============================================================

ETF_TICKERS = [
    "SXR8.DE",
    "SXRV.DE",
    "ZPDF.DE"
]


TICKERS = STOCK_TICKERS + ETF_TICKERS


ETF_INFO = {

    "SXR8.DE": {
        "name":
            "iShares Core S&P 500 UCITS ETF",
        "isin":
            "IE00B5BMR087",
        "ticker":
            "SXR8"
    },

    "SXRV.DE": {
        "name":
            "iShares NASDAQ 100 UCITS ETF",
        "isin":
            "IE00B53SZB19",
        "ticker":
            "SXRV"
    },

    "ZPDF.DE": {
        "name":
            "SPDR S&P U.S. Financials Select Sector UCITS ETF",
        "isin":
            "IE00BWBXM500",
        "ticker":
            "ZPDF"
    }
}


# ============================================================
# NOMBRES
# ============================================================

COMPANY_NAMES = {

    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "META": "Meta Platforms",
    "AVGO": "Broadcom",
    "TSLA": "Tesla",
    "AMD": "AMD",
    "NFLX": "Netflix",
    "JPM": "JPMorgan",
    "V": "Visa",
    "MA": "Mastercard",
    "COST": "Costco",
    "WMT": "Walmart",
    "LLY": "Eli Lilly",
    "XOM": "Exxon Mobil",
    "ORCL": "Oracle",
    "CRM": "Salesforce",
    "PLTR": "Palantir",
    "QCOM": "Qualcomm",
    "MU": "Micron",
    "INTC": "Intel",
    "AMAT": "Applied Materials",
    "UBER": "Uber",
    "PANW": "Palo Alto Networks",
    "ADBE": "Adobe",

    "IBE.MC": "Iberdrola",
    "BBVA.MC": "BBVA",
    "SAN.MC": "Banco Santander",
    "ITX.MC": "Inditex",
    "REP.MC": "Repsol",
    "TEF.MC": "Telefónica",

    "SAP.DE": "SAP",
    "SIE.DE": "Siemens",
    "ALV.DE": "Allianz",
    "DTE.DE": "Deutsche Telekom",

    "AIR.PA": "Airbus",
    "SU.PA": "Schneider Electric",
    "MC.PA": "LVMH",
    "TTE.PA": "TotalEnergies",

    "ASML.AS": "ASML",
    "ADYEN.AS": "Adyen",

    "RACE.MI": "Ferrari",
    "ENEL.MI": "Enel",
    "ISP.MI": "Intesa Sanpaolo"
}


# ============================================================
# CONFIGURACIÓN TÉCNICA
# ============================================================

MIN_SCORE = 75

MAX_SUPPORT_DISTANCE = 0.03

MAX_RSI = 45

MAX_REBOUND_DISTANCE = 0.015

MIN_VOLUME_CONFIRMATION = 1.15

PERIOD = "1y"

INTERVAL = "1d"

NEWS_HOURS = 24

MAX_NEWS = 8

MARKET_TICKER = "^GSPC"

MARKET_PERIOD = "1y"

EARNINGS_BLACKOUT_DAYS = 3


# ============================================================
# NUEVOS FILTROS
# ============================================================

# Volumen medio diario mínimo en dólares.
# Evita acciones extremadamente ilíquidas.
MIN_AVG_DOLLAR_VOLUME = 5_000_000

# No comprar después de una subida diaria excesiva.
MAX_DAILY_MOVE = 0.08

# No comprar si la acción está demasiado alejada
# del soporte aunque otros criterios sean buenos.
MAX_DISTANCE_FROM_SUPPORT = 0.03


# ============================================================
# GESTIÓN MONETARIA
# ============================================================

CAPITAL_EUR = float(
    os.getenv(
        "CAPITAL_EUR",
        "5000"
    )
)

RISK_PER_TRADE = float(
    os.getenv(
        "RISK_PER_TRADE",
        "0.01"
    )
)


# ============================================================
# TELEGRAM
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    ""
)

TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID",
    ""
)


# ============================================================
# PALABRAS DE NOTICIAS
# ============================================================

POSITIVE_WORDS = [

    "beats",
    "beat estimates",
    "beat expectations",
    "strong results",
    "strong growth",
    "record revenue",
    "record profit",
    "profit rises",
    "revenue rises",
    "raises guidance",
    "raised guidance",
    "upgrade",
    "upgraded",
    "buy rating",
    "strong demand",
    "new contract",
    "major contract",
    "partnership",
    "approval",
    "approved",
    "positive outlook",
    "bullish",
    "surges",
    "jumps",
    "growth",
    "expands",
    "expansion",
    "acquisition",
    "deal",
    "orders rise",
    "sales rise",

    "supera",
    "supera las expectativas",
    "mejores resultados",
    "crecimiento",
    "récord",
    "beneficio aumenta",
    "ingresos aumentan",
    "eleva previsiones",
    "recomendación de compra",
    "contrato",
    "acuerdo",
    "aprobación",
    "perspectivas positivas",
    "sube",
    "aumenta",
    "crece"
]


NEGATIVE_WORDS = [

    "misses",
    "missed estimates",
    "missed expectations",
    "weak results",
    "weak demand",
    "cuts guidance",
    "cut guidance",
    "downgrade",
    "downgraded",
    "sell rating",
    "warning",
    "profit falls",
    "revenue falls",
    "decline",
    "declines",
    "lawsuit",
    "investigation",
    "fraud",
    "recall",
    "layoffs",
    "job cuts",
    "bankruptcy",
    "debt concerns",
    "regulatory concerns",
    "export restrictions",
    "tariffs",
    "sanctions",
    "crisis",
    "bearish",
    "plunges",
    "falls",

    "no cumple",
    "decepciona",
    "resultados débiles",
    "demanda débil",
    "recorta previsiones",
    "rebaja",
    "venta",
    "advertencia",
    "beneficio cae",
    "ingresos caen",
    "caída",
    "demanda cae",
    "demanda baja",
    "demanda débil",
    "investigación",
    "fraude",
    "despidos",
    "quiebra",
    "deuda",
    "aranceles",
    "sanciones",
    "crisis",
    "bajista",
    "se desploma",
    "cae"
]


# ============================================================
# TEMAS ESPECÍFICOS
# ============================================================

SPECIAL_TOPICS = {

    "XOM": [
        "oil",
        "crude",
        "brent",
        "wti",
        "opec",
        "iran",
        "hormuz",
        "middle east",
        "energy"
    ],

    "LLY": [
        "weight loss",
        "obesity",
        "diabetes",
        "drug approval",
        "fda",
        "clinical trial"
    ],

    "NVDA": [
        "ai",
        "artificial intelligence",
        "chips",
        "semiconductor",
        "china",
        "export restrictions",
        "data center"
    ],

    "AMD": [
        "ai",
        "artificial intelligence",
        "chips",
        "semiconductor",
        "china",
        "export restrictions"
    ],

    "MU": [
        "memory",
        "dram",
        "nand",
        "semiconductor",
        "chips",
        "ai"
    ],

    "TSLA": [
        "electric vehicles",
        "ev",
        "china",
        "tariffs",
        "autonomous driving",
        "robotaxi"
    ],

    "ASML.AS": [
        "semiconductor",
        "chips",
        "lithography",
        "china",
        "export restrictions"
    ],

    "AIR.PA": [
        "airbus",
        "aircraft",
        "aviation",
        "defense",
        "orders",
        "supply chain"
    ],

    "REP.MC": [
        "oil",
        "crude",
        "brent",
        "wti",
        "opec",
        "energy"
    ]
}


# ============================================================
# UTILIDADES
# ============================================================

def is_etf(ticker):

    return ticker in ETF_INFO


def display_ticker(ticker):

    if is_etf(ticker):

        return ETF_INFO[ticker]["ticker"]

    return ticker


def display_name(ticker):

    if is_etf(ticker):

        return ETF_INFO[ticker]["name"]

    return COMPANY_NAMES.get(
        ticker,
        ticker
    )


def safe_float(value):

    try:

        return float(value)

    except Exception:

        return np.nan


# ============================================================
# RSI
# ============================================================

def calculate_rsi(
    series,
    period=14
):

    delta = series.diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    rs = (
        avg_gain
        /
        avg_loss.replace(
            0,
            np.nan
        )
    )

    return (
        100
        -
        (
            100
            /
            (1 + rs)
        )
    )


# ============================================================
# DATOS DE MERCADO
# ============================================================

def download_data(
    ticker,
    period=PERIOD,
    interval=INTERVAL
):

    try:

        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=False,
            threads=False
        )

        if df.empty:

            return None

        if isinstance(
            df.columns,
            pd.MultiIndex
        ):

            df.columns = [
                c[0]
                for c in df.columns
            ]

        required = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        if not all(
            c in df.columns
            for c in required
        ):

            return None

        return df.dropna(
            subset=required
        )

    except Exception as e:

        print(
            f"Error descargando "
            f"{ticker}: {e}"
        )

        return None


# ============================================================
# ANÁLISIS TÉCNICO
# ============================================================

def analyze_ticker(ticker):

    df = download_data(
        ticker
    )

    if df is None:

        return None

    if len(df) < 210:

        return None

    close = df["Close"]

    volume = df["Volume"]

    df["SMA50"] = (
        close.rolling(50)
        .mean()
    )

    df["SMA200"] = (
        close.rolling(200)
        .mean()
    )

    df["RSI"] = calculate_rsi(
        close
    )

    df["VOL20"] = (
        volume.rolling(20)
        .mean()
    )

    last = df.iloc[-1]

    previous = df.iloc[-2]

    price = safe_float(
        last["Close"]
    )

    open_price = safe_float(
        last["Open"]
    )

    high = safe_float(
        last["High"]
    )

    low = safe_float(
        last["Low"]
    )

    previous_high = safe_float(
        previous["High"]
    )

    sma50 = safe_float(
        last["SMA50"]
    )

    sma200 = safe_float(
        last["SMA200"]
    )

    rsi_value = safe_float(
        last["RSI"]
    )

    volume_value = safe_float(
        last["Volume"]
    )

    avg_volume = safe_float(
        last["VOL20"]
    )

    if any(
        pd.isna(x)
        for x in [
            price,
            sma50,
            sma200,
            rsi_value,
            avg_volume
        ]
    ):

        return None

    volume_ratio = (
        volume_value
        /
        avg_volume
        if avg_volume > 0
        else 0
    )

    avg_dollar_volume = (
        avg_volume
        * price
    )

    daily_move = (
        (price - safe_float(
            previous["Close"]
        ))
        /
        safe_float(
            previous["Close"]
        )
    )

    # --------------------------------------------------------
    # SOPORTE
    # --------------------------------------------------------

    support = safe_float(
        df["Low"]
        .tail(20)
        .min()
    )

    distance_support = (
        (price - support)
        /
        price
        if price > 0
        else math.inf
    )

    rebound_distance = (
        (low - support)
        /
        support
        if support > 0
        else math.inf
    )

    # --------------------------------------------------------
    # REBOTE
    # --------------------------------------------------------

    bullish_candle = (
        price > open_price
    )

    support_reaction = (
        rebound_distance
        <= MAX_REBOUND_DISTANCE
    )

    volume_confirmation = (
        volume_ratio
        >= MIN_VOLUME_CONFIRMATION
    )

    close_above_previous_high = (
        price > previous_high
    )

    rebound_confirmed = (
        bullish_candle
        and support_reaction
        and volume_confirmation
        and close_above_previous_high
    )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    score = 0

    reasons = []

    if price > sma200:

        score += 20

        reasons.append(
            "Precio > SMA200"
        )

    if sma50 > sma200:

        score += 15

        reasons.append(
            "SMA50 > SMA200"
        )

    if price > sma50:

        score += 10

        reasons.append(
            "Precio > SMA50"
        )

    if rsi_value < 30:

        score += 25

        reasons.append(
            "RSI <30"
        )

    elif rsi_value <= 45:

        score += 20

        reasons.append(
            "RSI 30-45"
        )

    elif rsi_value <= 55:

        score += 8

    if volume_ratio >= 1.5:

        score += 15

        reasons.append(
            "Volumen >=1.5x"
        )

    elif volume_ratio >= 1.15:

        score += 8

        reasons.append(
            "Volumen >=1.15x"
        )

    if distance_support <= 0.03:

        score += 20

        reasons.append(
            "Precio <=3% soporte"
        )

    elif distance_support <= 0.06:

        score += 10

    # --------------------------------------------------------
    # STOP Y OBJETIVOS
    # --------------------------------------------------------

    stop = support * 0.98

    risk_per_share = (
        price - stop
    )

    if risk_per_share > 0:

        target1 = (
            price
            + 2 * risk_per_share
        )

        target2 = (
            price
            + 3 * risk_per_share
        )

        reward_risk = 2.0

    else:

        target1 = np.nan

        target2 = np.nan

        reward_risk = 0

    return {

        "ticker": ticker,

        "price": price,

        "score": score,

        "rsi": rsi_value,

        "volume_ratio": volume_ratio,

        "avg_dollar_volume":
            avg_dollar_volume,

        "daily_move":
            daily_move,

        "support":
            support,

        "distance_support":
            distance_support,

        "rebound_distance":
            rebound_distance,

        "bullish_candle":
            bullish_candle,

        "support_reaction":
            support_reaction,

        "volume_confirmation":
            volume_confirmation,

        "close_above_previous_high":
            close_above_previous_high,

        "rebound_confirmed":
            rebound_confirmed,

        "stop":
            stop,

        "target1":
            target1,

        "target2":
            target2,

        "reward_risk":
            reward_risk,

        "reasons":
            reasons,

        "earnings":
            None,

        "news":
            None,

        "position":
            None
    }


# ============================================================
# MERCADO GENERAL
# ============================================================

def get_market_regime():

    df = download_data(
        MARKET_TICKER,
        MARKET_PERIOD,
        "1d"
    )

    if df is None:

        return {

            "ok": False,

            "status":
                "SIN DATOS"
        }

    close = df["Close"]

    if len(close) < 200:

        return {

            "ok": False,

            "status":
                "SIN DATOS"
        }

    sma50 = (
        close.rolling(50)
        .mean()
        .iloc[-1]
    )

    sma200 = (
        close.rolling(200)
        .mean()
        .iloc[-1]
    )

    price = close.iloc[-1]

    ok = (
        price > sma200
        and sma50 > sma200
    )

    return {

        "ok": bool(ok),

        "status":
            "FAVORABLE"
            if ok
            else
            "DESFAVORABLE",

        "price":
            safe_float(price),

        "sma50":
            safe_float(sma50),

        "sma200":
            safe_float(sma200)
    }


# ============================================================
# RESULTADOS
# ============================================================

def get_earnings_status(ticker):

    if is_etf(ticker):

        return {

            "blocked":
                False,

            "status":
                "NO APLICA",

            "date":
                None,

            "days":
                None
        }

    try:

        dates = (
            yf.Ticker(ticker)
            .get_earnings_dates(
                limit=8
            )
        )

        if dates is None or len(
            dates
        ) == 0:

            return {

                "blocked":
                    False,

                "status":
                    "SIN FECHA",

                "date":
                    None,

                "days":
                    None
            }

        now = pd.Timestamp.now(
            tz="UTC"
        )

        nearest = None

        nearest_abs = None

        for date in dates.index:

            dt = pd.Timestamp(
                date
            )

            if dt.tzinfo is None:

                dt = dt.tz_localize(
                    "UTC"
                )

            else:

                dt = dt.tz_convert(
                    "UTC"
                )

            diff = (
                dt - now
            ).total_seconds() / 86400

            if (
                nearest is None
                or abs(diff)
                < nearest_abs
            ):

                nearest = dt

                nearest_abs = abs(
                    diff
                )

        blocked = (
            nearest_abs
            <= EARNINGS_BLACKOUT_DAYS
        )

        return {

            "blocked":
                blocked,

            "status":
                "BLOQUEADO POR RESULTADOS"
                if blocked
                else
                "FUERA DEL BLOQUEO",

            "date":
                nearest,

            "days":
                nearest_abs
        }

    except Exception:

        return {

            "blocked":
                False,

            "status":
                "SIN DATOS",

            "date":
                None,

            "days":
                None
        }


# ============================================================
# EUR/USD
# ============================================================

def get_eurusd():

    try:

        df = download_data(
            "EURUSD=X",
            "5d",
            "1d"
        )

        if df is None:

            return 1.0

        value = safe_float(
            df["Close"]
            .iloc[-1]
        )

        if value > 0:

            return value

    except Exception:

        pass

    return 1.0


# ============================================================
# GESTIÓN DE POSICIÓN
# ============================================================

def calculate_position(
    ticker,
    entry,
    stop,
    eurusd
):

    max_risk_eur = (
        CAPITAL_EUR
        * RISK_PER_TRADE
    )

    risk_per_share = (
        entry - stop
    )

    if risk_per_share <= 0:

        return {

            "shares": 0,

            "capital_used_eur":
                0,

            "risk_eur":
                0,

            "max_risk_eur":
                max_risk_eur
        }

    if is_etf(ticker):

        entry_eur = entry

        risk_eur_share = (
            risk_per_share
        )

    else:

        entry_eur = (
            entry
            / eurusd
        )

        risk_eur_share = (
            risk_per_share
            / eurusd
        )

    shares_risk = math.floor(
        max_risk_eur
        / risk_eur_share
    )

    shares_capital = math.floor(
        CAPITAL_EUR
        / entry_eur
    )

    shares = max(
        0,
        min(
            shares_risk,
            shares_capital
        )
    )

    capital_used = (
        shares
        * entry_eur
    )

    risk_total = (
        shares
        * risk_eur_share
    )

    return {

        "shares":
            shares,

        "capital_used_eur":
            capital_used,

        "risk_eur":
            risk_total,

        "max_risk_eur":
            max_risk_eur
    }


# ============================================================
# NOTICIAS
# ============================================================

def get_news(
    ticker,
    language="es"
):

    name = display_name(
        ticker
    )

    topics = SPECIAL_TOPICS.get(
        ticker,
        []
    )

    if topics:

        query = (
            f'"{name}" '
            + " ".join(
                topics[:4]
            )
        )

    else:

        query = name

    if language == "en":

        hl = "en-US"
        gl = "US"
        ceid = "US:en"

    else:

        hl = "es-ES"
        gl = "ES"
        ceid = "ES:es"

    url = (
        "https://news.google.com/rss/search?"
        f"q={quote(query)}"
        f"&hl={hl}"
        f"&gl={gl}"
        f"&ceid={ceid}"
    )

    try:

        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent":
                    "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        root = ET.fromstring(
            response.content
        )

        results = []

        now = datetime.now(
            timezone.utc
        )

        for item in root.findall(
            ".//item"
        ):

            title = (
                item.findtext(
                    "title",
                    ""
                )
                .strip()
            )

            link = (
                item.findtext(
                    "link",
                    ""
                )
                .strip()
            )

            source = (
                item.findtext(
                    "source",
                    ""
                )
                .strip()
            )

            pub_date = (
                item.findtext(
                    "pubDate",
                    ""
                )
                .strip()
            )

            if not title:

                continue

            try:

                dt = datetime.strptime(
                    pub_date,
                    "%a, %d %b %Y %H:%M:%S %Z"
                ).replace(
                    tzinfo=timezone.utc
                )

            except Exception:

                dt = now

            if (
                now - dt
                >
                timedelta(
                    hours=NEWS_HOURS
                )
            ):

                continue

            results.append({

                "title":
                    title,

                "link":
                    link,

                "source":
                    source,

                "date":
                    dt,

                "language":
                    language
            })

        return results[:MAX_NEWS]

    except Exception as e:

        print(
            f"Error noticias "
            f"{ticker}: {e}"
        )

        return []


def translate_to_spanish(
    text
):

    if not text:

        return ""

    api_key = os.getenv(
        "GOOGLE_TRANSLATE_API_KEY",
        ""
    )

    # --------------------------------------------------------
    # GOOGLE CLOUD
    # --------------------------------------------------------

    if api_key:

        try:

            url = (
                "https://translation.googleapis.com/"
                "language/translate/v2"
            )

            response = requests.post(
                url,
                params={
                    "key":
                        api_key
                },
                json={
                    "q":
                        text,
                    "target":
                        "es",
                    "format":
                        "text"
                },
                timeout=15
            )

            response.raise_for_status()

            data = response.json()

            translated = (
                data
                .get("data", {})
                .get(
                    "translations",
                    [{}]
                )[0]
                .get(
                    "translatedText"
                )
            )

            if translated:

                return translated

        except Exception:

            pass

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    try:

        url = (
            "https://translate.googleapis.com/"
            "translate_a/single"
        )

        params = {

            "client":
                "gtx",

            "sl":
                "auto",

            "tl":
                "es",

            "dt":
                "t",

            "q":
                text
        }

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        translated = "".join(

            part[0]

            for part in data[0]

            if (
                isinstance(
                    part,
                    list
                )
                and len(part) > 0
            )
        )

        if translated:

            return translated

    except Exception:

        pass

    return text


# ============================================================
# CLASIFICACIÓN DE NOTICIAS
# ============================================================

def classify_news(
    ticker
):

    spanish = get_news(
        ticker,
        "es"
    )

    english = get_news(
        ticker,
        "en"
    )

    all_news = []

    seen = set()

    for item in (
        spanish
        +
        english
    ):

        key = (
            item["title"]
            .lower()
            .strip()
        )

        if key in seen:

            continue

        seen.add(key)

        text = (
            item["title"]
            .lower()
        )

        positive_hits = sum(
            1
            for word
            in POSITIVE_WORDS
            if word.lower()
            in text
        )

        negative_hits = sum(
            1
            for word
            in NEGATIVE_WORDS
            if word.lower()
            in text
        )

        item["positive_hits"] = (
            positive_hits
        )

        item["negative_hits"] = (
            negative_hits
        )

        all_news.append(
            item
        )

    all_news.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    all_news = all_news[
        :MAX_NEWS
    ]

    positive = sum(
        x["positive_hits"]
        for x in all_news
    )

    negative = sum(
        x["negative_hits"]
        for x in all_news
    )

    # --------------------------------------------------------
    # REGLA CONSERVADORA
    # --------------------------------------------------------

    if negative >= positive + 2:

        risk = "NEGATIVO"

    elif positive >= negative + 2:

        risk = "POSITIVO"

    elif negative > positive:

        risk = "NEGATIVO"

    elif positive > negative:

        risk = "POSITIVO"

    else:

        risk = "MIXTO / NEUTRO"

    # --------------------------------------------------------
    # NOTICIA POSITIVA DESTACADA
    # --------------------------------------------------------

    positive_news = [

        x for x in all_news

        if (
            x["positive_hits"]
            >
            x["negative_hits"]
        )
    ]

    featured = None

    if positive_news:

        featured = (
            positive_news[0]
        )

        if (
            featured["language"]
            == "en"
        ):

            featured[
                "translated_title"
            ] = translate_to_spanish(
                featured["title"]
            )

        else:

            featured[
                "translated_title"
            ] = featured["title"]

    return {

        "risk":
            risk,

        "positive":
            positive,

        "negative":
            negative,

        "items":
            all_news,

        "featured":
            featured
    }


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(
    message
):

    if (
        not TELEGRAM_BOT_TOKEN
        or not TELEGRAM_CHAT_ID
    ):

        print(
            "\nTELEGRAM NO CONFIGURADO"
        )

        return False

    url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    try:

        response = requests.post(
            url,
            json={
                "chat_id":
                    TELEGRAM_CHAT_ID,

                "text":
                    message,

                "disable_web_page_preview":
                    True
            },
            timeout=20
        )

        response.raise_for_status()

        return True

    except Exception as e:

        print(
            f"Error Telegram: {e}"
        )

        return False


# ============================================================
# FORMATEAR DINERO
# ============================================================

def money(value):

    if value is None:

        return "N/D"

    if pd.isna(value):

        return "N/D"

    return (
        f"{value:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
        + " €"
    )


def price(value):

    if value is None:

        return "N/D"

    if pd.isna(value):

        return "N/D"

    return (
        f"{value:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


# ============================================================
# DIAGNÓSTICO
# ============================================================

def diagnostic_report(
    candidate
):

    primary = candidate[
        "primary_checks"
    ]

    secondary = candidate[
        "secondary_checks"
    ]

    print(
        "\n"
        + "=" * 70
    )

    print(
        f"🔎 DIAGNÓSTICO: "
        f"{display_ticker(candidate['ticker'])}"
    )

    print(
        f"Empresa: "
        f"{display_name(candidate['ticker'])}"
    )

    print(
        f"Precio: "
        f"{price(candidate['price'])}"
    )

    print(
        f"Score: "
        f"{candidate['score']}/100"
    )

    print(
        f"RSI: "
        f"{candidate['rsi']:.1f}"
    )

    print(
        f"Distancia soporte: "
        f"{candidate['distance_support'] * 100:.2f}%"
    )

    print(
        f"Noticias: "
        f"{candidate['news']['risk']}"
    )

    print(
        f"R/R: "
        f"{candidate['reward_risk']:.1f}:1"
    )

    print()

    p_ok = sum(
        primary.values()
    )

    s_ok = sum(
        secondary.values()
    )

    print(
        f"🟢 PRINCIPALES: "
        f"{p_ok}/5"
    )

    for name, ok in primary.items():

        print(
            f"   "
            f"{'✅' if ok else '❌'} "
            f"{name}"
        )

    print()

    print(
        f"🟡 SECUNDARIOS: "
        f"{s_ok}/5"
    )

    for name, ok in secondary.items():

        print(
            f"   "
            f"{'✅' if ok else '❌'} "
            f"{name}"
        )

    print()

    if (
        p_ok == 5
        and s_ok == 5
    ):

        print(
            "💎 RESULTADO: "
            "CHOLLO CONFIRMADO"
        )

    elif (
        p_ok == 5
        and s_ok == 4
    ):

        print(
            "🟡 RESULTADO: "
            "CHOLLO A VIGILAR"
        )

    else:

        print(
            "⚪ RESULTADO: "
            "NO ENTRA"
        )

    # --------------------------------------------------------
    # DINERO
    # --------------------------------------------------------

    position = candidate.get(
        "position"
    )

    if position:

        print()

        print(
            "💰 GESTIÓN DE DINERO"
        )

        print(
            f"   Acciones: "
            f"{position['shares']}"
        )

        print(
            f"   Capital: "
            f"{money(position['capital_used_eur'])}"
        )

        print(
            f"   Riesgo máximo: "
            f"{money(position['risk_eur'])}"
        )


# ============================================================
# MENSAJE DE UNA OPERACIÓN
# ============================================================

def build_signal_message(
    candidate,
    confirmed=True
):

    ticker = candidate[
        "ticker"
    ]

    name = display_name(
        ticker
    )

    position = candidate[
        "position"
    ]

    news = candidate[
        "news"
    ]

    if confirmed:

        title = (
            "💎 CHOLLO CONFIRMADO"
        )

    else:

        title = (
            "🟡 CHOLLO A VIGILAR"
        )

    message = f"""
{title}

📌 {name} ({display_ticker(ticker)})

💵 Entrada: {price(candidate['price'])}
🛑 Stop: {price(candidate['stop'])}
🎯 Objetivo 1: {price(candidate['target1'])}
🎯 Objetivo 2: {price(candidate['target2'])}

📊 Score: {candidate['score']}/100
📉 RSI: {candidate['rsi']:.1f}
📍 Soporte: {price(candidate['support'])}
📐 Distancia soporte: {candidate['distance_support'] * 100:.2f}%
📈 Volumen: {candidate['volume_ratio']:.2f}x media
⚖️ R/R: {candidate['reward_risk']:.1f}:1

💰 CAPITAL A INVERTIR:
{money(position['capital_used_eur'])}

📦 ACCIONES:
{position['shares']}

🔴 PÉRDIDA MÁXIMA ESTIMADA:
{money(position['risk_eur'])}

📰 Noticias:
{news['risk']}

🌎 Mercado S&P 500:
{candidate['market_status']}

📅 Resultados:
{candidate['earnings_status']}
"""

    featured = news.get(
        "featured"
    )

    if featured:

        message += (
            "\n🇪🇸 NOTICIA POSITIVA DESTACADA\n"
            f"{featured['translated_title']}\n"
            f"Fuente: {featured['source']}\n"
        )

        if featured.get(
            "link"
        ):

            message += (
                f"{featured['link']}\n"
            )

    return message.strip()


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\n"
        + "=" * 70
    )

    print(
        "📊 ESCÁNER DE CHOLLOS PARA DEGIRO"
    )

    print(
        "=" * 70
    )

    print(
        f"\nCapital: "
        f"{money(CAPITAL_EUR)}"
    )

    print(
        f"Riesgo máximo por operación: "
        f"{RISK_PER_TRADE * 100:.1f}%"
    )

    print(
        f"Riesgo máximo: "
        f"{money(CAPITAL_EUR * RISK_PER_TRADE)}"
    )

    # --------------------------------------------------------
    # MERCADO
    # --------------------------------------------------------

    market = get_market_regime()

    print(
        "\n🌎 S&P 500:"
    )

    print(
        f"   Estado: "
        f"{market['status']}"
    )

    # --------------------------------------------------------
    # EUR/USD
    # --------------------------------------------------------

    eurusd = get_eurusd()

    print(
        f"\n💱 EUR/USD: "
        f"{eurusd:.4f}"
    )

    # --------------------------------------------------------
    # ESCANEO
    # --------------------------------------------------------

    candidates = []

    print(
        "\n🔍 Analizando "
        f"{len(TICKERS)} instrumentos..."
    )

    for ticker in TICKERS:

        try:

            result = analyze_ticker(
                ticker
            )

            if result is None:

                continue

            # Solo hacemos diagnóstico
            # detallado a partir de score 75.
            if result["score"] < MIN_SCORE:

                continue

            print(
                f"\n📌 Analizando "
                f"{display_ticker(ticker)}..."
            )

            # ------------------------------------------------
            # NOTICIAS
            # ------------------------------------------------

            news = classify_news(
                ticker
            )

            result[
                "news"
            ] = news

            # ------------------------------------------------
            # RESULTADOS
            # ------------------------------------------------

            earnings = (
                get_earnings_status(
                    ticker
                )
            )

            result[
                "earnings"
            ] = earnings

            # ------------------------------------------------
            # POSICIÓN
            # ------------------------------------------------

            position = (
                calculate_position(
                    ticker,
                    result["price"],
                    result["stop"],
                    eurusd
                )
            )

            result[
                "position"
            ] = position

            # ------------------------------------------------
            # PRINCIPALES
            # ------------------------------------------------

            primary_checks = {

                "Score >= 75":
                    result["score"]
                    >= MIN_SCORE,

                "RSI <= 45":
                    result["rsi"]
                    <= MAX_RSI,

                "Precio <= 3% del soporte":
                    result["distance_support"]
                    <= MAX_SUPPORT_DISTANCE,

                "Noticias no negativas":
                    news["risk"]
                    in (
                        "POSITIVO",
                        "MIXTO / NEUTRO"
                    ),

                "R/R >= 2:1":
                    result["reward_risk"]
                    >= 2.0
            }

            # ------------------------------------------------
            # SECUNDARIOS
            # ------------------------------------------------

            secondary_checks = {

                "Rebote confirmado":
                    result[
                        "rebound_confirmed"
                    ],

                "Volumen >= 1.15x":
                    result[
                        "volume_confirmation"
                    ],

                "Cierre > máximo vela anterior":
                    result[
                        "close_above_previous_high"
                    ],

                "S&P 500 favorable":
                    market["ok"],

                "Sin resultados +/- 3 días":
                    not earnings["blocked"]
            }

            result[
                "primary_checks"
            ] = primary_checks

            result[
                "secondary_checks"
            ] = secondary_checks

            result[
                "market_status"
            ] = market["status"]

            result[
                "earnings_status"
            ] = earnings["status"]

            result[
                "reward_risk"
            ] = result["reward_risk"]

            # ------------------------------------------------
            # DIAGNÓSTICO
            # ------------------------------------------------

            diagnostic_report(
                result
            )

            candidates.append(
                result
            )

        except Exception as e:

            print(
                f"\n⚠️ Error en "
                f"{ticker}: {e}"
            )

    # ========================================================
    # CLASIFICACIÓN FINAL
    # ========================================================

    confirmed = []

    watchlist = []

    rejected = []

    for candidate in candidates:

        primary_ok = all(
            candidate[
                "primary_checks"
            ].values()
        )

        secondary_count = sum(
            candidate[
                "secondary_checks"
            ].values()
        )

        shares = candidate[
            "position"
        ]["shares"]

        # ----------------------------------------------------
        # CHOLLO CONFIRMADO
        # ----------------------------------------------------

        if (
            primary_ok
            and secondary_count == 5
            and shares >= 1
        ):

            confirmed.append(
                candidate
            )

        # ----------------------------------------------------
        # CHOLLO A VIGILAR
        # Exactamente un secundario falla.
        # ----------------------------------------------------

        elif (
            primary_ok
            and secondary_count == 4
            and shares >= 1
        ):

            watchlist.append(
                candidate
            )

        else:

            rejected.append(
                candidate
            )

    # ========================================================
    # RESUMEN
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "📊 RESULTADO FINAL"
    )

    print(
        "=" * 70
    )

    print(
        f"\n💎 CHOLLOS CONFIRMADOS: "
        f"{len(confirmed)}"
    )

    print(
        f"🟡 CANDIDATAS A VIGILAR: "
        f"{len(watchlist)}"
    )

    print(
        f"⚪ NO ENTRAN: "
        f"{len(rejected)}"
    )

    # ========================================================
    # CONFIRMADOS
    # ========================================================

    telegram_messages = []

    for candidate in confirmed:

        message = build_signal_message(
            candidate,
            True
        )

        print(
            "\n"
            + message
        )

        telegram_messages.append(
            message
        )

    # ========================================================
    # VIGILANCIA
    # ========================================================

    for candidate in watchlist:

        failed_secondary = [

            name

            for name, ok
            in candidate[
                "secondary_checks"
            ].items()

            if not ok
        ]

        message = build_signal_message(
            candidate,
            False
        )

        message += (
            "\n\n⚠️ SECUNDARIO QUE FALLA:\n"
            + "\n".join(
                "❌ " + x
                for x
                in failed_secondary
            )
        )

        print(
            "\n"
            + message
        )

        telegram_messages.append(
            message
        )

    # ========================================================
    # DIAGNÓSTICO FINAL POR TICKER
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "🔎 RESUMEN DE FILTROS"
    )

    print(
        "=" * 70
    )

    for candidate in candidates:

        p = candidate[
            "primary_checks"
        ]

        s = candidate[
            "secondary_checks"
        ]

        primary_ok = sum(
            p.values()
        )

        secondary_ok = sum(
            s.values()
        )

        failed_primary = [

            name

            for name, ok
            in p.items()

            if not ok
        ]

        failed_secondary = [

            name

            for name, ok
            in s.items()

            if not ok
        ]

        print(
            f"\n{display_ticker(candidate['ticker'])} "
            f"- {display_name(candidate['ticker'])}"
        )

        print(
            f"   Principales: "
            f"{primary_ok}/5"
        )

        if failed_primary:

            for item in failed_primary:

                print(
                    f"      ❌ {item}"
                )

        else:

            print(
                "      ✅ Todas"
            )

        print(
            f"   Secundarios: "
            f"{secondary_ok}/5"
        )

        if failed_secondary:

            for item in failed_secondary:

                print(
                    f"      ❌ {item}"
                )

        else:

            print(
                "      ✅ Todos"
            )

        if (
            primary_ok == 5
            and secondary_ok == 5
        ):

            print(
                "   💎 CHOLLO CONFIRMADO"
            )

        elif (
            primary_ok == 5
            and secondary_ok == 4
        ):

            print(
                "   🟡 CHOLLO A VIGILAR"
            )

        else:

            print(
                "   ⚪ NO ENTRA"
            )

    # ========================================================
    # SI NO HAY CONFIRMADOS
    # ========================================================

    if not confirmed:

        print(
            "\n"
            "No hay oportunidades que "
            "cumplan TODOS los filtros "
            "del CHOLLO CONFIRMADO."
        )

    # ========================================================
    # MENSAJE RESUMEN TELEGRAM
    # ========================================================

    summary = f"""
📊 ESCÁNER DE CHOLLOS PARA DEGIRO

💎 CHOLLOS CONFIRMADOS:
{len(confirmed)}

🟡 CANDIDATAS A VIGILAR:
{len(watchlist)}

⚪ NO ENTRAN:
{len(rejected)}

💰 Capital:
{money(CAPITAL_EUR)}

🔴 Riesgo máximo:
{money(CAPITAL_EUR * RISK_PER_TRADE)}

🌎 S&P 500:
{market['status']}

Filtros principales:
• Score >=75
• RSI <=45
• Precio <=3% soporte
• Noticias no negativas
• R/R >=2:1

Filtros secundarios:
• Rebote confirmado
• Volumen >=1.15x
• Cierre > máximo vela anterior
• S&P 500 favorable
• Sin resultados +/-3 días

📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}
""".strip()

    telegram_messages.insert(
        0,
        summary
    )

    # --------------------------------------------------------
    # ENVIAR TELEGRAM
    # --------------------------------------------------------

    for message in telegram_messages:

        send_telegram(
            message
        )

    print(
        "\n"
        + "=" * 70
    )

    print(
        "✅ ESCÁNER TERMINADO"
    )

    print(
        "=" * 70
    )


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    main()
