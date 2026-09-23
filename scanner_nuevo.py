import os
import re
import math
import requests
import numpy as np
import pandas as pd
import yfinance as yf
import xml.etree.ElementTree as ET

from urllib.parse import quote
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


# ============================================================
# 📊 ESCÁNER DE CHOLLOS PARA DEGIRO
# ============================================================
#
# FUNCIONES PRINCIPALES
# - Acciones USA + Europa
# - ETFs UCITS
# - Análisis técnico
# - Soporte
# - Rebote
# - Volumen
# - Liquidez
# - Noticias recientes
# - Resultados empresariales
# - Régimen del S&P 500
# - Gestión de capital de 5.000 €
# - Riesgo máximo 1% = 50 €
# - Entrada / stop / objetivos
# - Diagnóstico de filtros por ticker
# - SOLO envía a Telegram las señales CONFIRMADAS
#
# IMPORTANTE:
# Los candidatos rechazados se diagnostican internamente,
# pero NO se envían como oportunidades de compra.
# ============================================================


# ============================================================
# 1. CONFIGURACIÓN GENERAL
# ============================================================

MIN_SCORE = 75

MAX_RSI = 45

MAX_SUPPORT_DISTANCE = 0.03

MAX_REBOUND_DISTANCE = 0.015

MIN_VOLUME_CONFIRMATION = 1.15

MIN_AVG_DOLLAR_VOLUME = 5_000_000

MAX_DAILY_MOVE = 0.08

PERIOD = "1y"

INTERVAL = "1d"

NEWS_HOURS = 24

MAX_NEWS = 8

MARKET_TICKER = "^GSPC"

MARKET_PERIOD = "1y"

EARNINGS_BLACKOUT_DAYS = 3

CAPITAL_EUR = 5000.0

RISK_PER_TRADE = 0.01

MAX_RISK_EUR = CAPITAL_EUR * RISK_PER_TRADE

SEND_WATCHLIST_ALERTS = False

REQUIRE_ALL_FILTERS = True


# ============================================================
# 2. TELEGRAM
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


# ============================================================
# 3. UNIVERSO DE ACCIONES USA
# ============================================================

US_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "AVGO",
    "TSLA",
    "AMD",
    "NFLX",
    "JPM",
    "V",
    "MA",
    "COST",
    "WMT",
    "LLY",
    "XOM",
    "ORCL",
    "CRM",
    "PLTR",
    "QCOM",
    "MU",
    "INTC",
    "AMAT",
    "UBER",
    "PANW",
    "ADBE",
]


# ============================================================
# 4. UNIVERSO EUROPA
# ============================================================

SPAIN_TICKERS = [
    "IBE.MC",
    "BBVA.MC",
    "SAN.MC",
    "ITX.MC",
    "REP.MC",
    "TEF.MC",
]

GERMANY_TICKERS = [
    "SAP.DE",
    "SIE.DE",
    "ALV.DE",
    "DTE.DE",
]

FRANCE_TICKERS = [
    "AIR.PA",
    "SU.PA",
    "MC.PA",
    "TTE.PA",
]

NETHERLANDS_TICKERS = [
    "ASML.AS",
    "ADYEN.AS",
]

ITALY_TICKERS = [
    "RACE.MI",
    "ENEL.MI",
    "ISP.MI",
]


# ============================================================
# 5. ETFs UCITS
# ============================================================

ETF_TICKERS = [
    "SXR8.DE",
    "SXRV.DE",
    "ZPDF.DE",
]


# ============================================================
# 6. UNIVERSO COMPLETO
# ============================================================

TICKERS = (
    US_TICKERS
    + SPAIN_TICKERS
    + GERMANY_TICKERS
    + FRANCE_TICKERS
    + NETHERLANDS_TICKERS
    + ITALY_TICKERS
    + ETF_TICKERS
)


# ============================================================
# 7. INFORMACIÓN DE ETFs
# ============================================================

ETF_INFO = {
    "SXR8.DE": {
        "name": "iShares Core S&P 500 UCITS ETF",
        "isin": "IE00B5BMR087",
    },
    "SXRV.DE": {
        "name": "iShares NASDAQ 100 UCITS ETF",
        "isin": "IE00B53SZB19",
    },
    "ZPDF.DE": {
        "name": "SPDR S&P U.S. Financials Select Sector UCITS ETF",
        "isin": "IE00BWBXM500",
    },
}


# ============================================================
# 8. NOMBRES DE EMPRESAS
# ============================================================

COMPANY_NAMES = {

    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet Google",
    "META": "Meta Platforms Facebook",
    "AVGO": "Broadcom",
    "TSLA": "Tesla",
    "AMD": "AMD",
    "NFLX": "Netflix",
    "JPM": "JPMorgan Chase",
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
    "ISP.MI": "Intesa Sanpaolo",

    "SXR8.DE": "iShares Core S&P 500 UCITS ETF",
    "SXRV.DE": "iShares NASDAQ 100 UCITS ETF",
    "ZPDF.DE": "SPDR S&P U.S. Financials Select Sector UCITS ETF",
}


# ============================================================
# 9. TEMAS ESPECIALES DE NOTICIAS
# ============================================================

GENERAL_RISK_TERMS = [
    "war",
    "conflict",
    "iran",
    "israel",
    "russia",
    "ukraine",
    "china",
    "taiwan",
    "sanctions",
    "tariff",
    "tariffs",
    "fed",
    "interest rates",
    "inflation",
    "recession",
    "oil",
    "crude",
    "opec",
    "hormuz",
    "united nations",
    "antitrust",
    "regulation",
    "regulatory",
    "export restrictions",
    "export ban",
    "ban",
]


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
        "sanctions",
        "production",
        "refinery",
        "energy",
    ],

    "LLY": [
        "obesity",
        "diabetes",
        "fda",
        "clinical trial",
        "clinical trials",
        "drug",
        "approval",
    ],

    "NVDA": [
        "chips",
        "semiconductor",
        "china",
        "export restrictions",
        "export controls",
        "ai",
        "artificial intelligence",
    ],

    "AMD": [
        "chips",
        "semiconductor",
        "china",
        "export restrictions",
        "export controls",
        "ai",
        "artificial intelligence",
    ],

    "MU": [
        "chips",
        "semiconductor",
        "memory",
        "china",
        "export restrictions",
        "export controls",
    ],

    "INTC": [
        "chips",
        "semiconductor",
        "china",
        "export restrictions",
        "export controls",
    ],

    "AMAT": [
        "chips",
        "semiconductor",
        "china",
        "export restrictions",
        "export controls",
    ],

    "AVGO": [
        "chips",
        "semiconductor",
        "china",
        "export restrictions",
        "ai",
        "artificial intelligence",
    ],

    "QCOM": [
        "chips",
        "semiconductor",
        "china",
        "export restrictions",
        "smartphone",
    ],

    "TSLA": [
        "ev",
        "electric vehicle",
        "china",
        "tariffs",
        "autonomous",
        "robotaxi",
        "regulation",
        "self driving",
    ],
}


# ============================================================
# 10. PALABRAS DE NOTICIAS
# ============================================================

POSITIVE_NEWS_TERMS = [
    "beats",
    "beat",
    "upgrade",
    "upgraded",
    "approval",
    "approved",
    "deal",
    "contract",
    "partnership",
    "buyback",
    "repurchase",
    "raises guidance",
    "raised guidance",
    "strong demand",
    "record revenue",
    "record sales",
    "profit growth",
    "revenue growth",
    "growth",
    "positive",
    "expands",
    "expansion",
    "new order",
    "orders",
    "wins contract",
    "investment",
]


NEGATIVE_NEWS_TERMS = [
    "miss",
    "misses",
    "missed",
    "loss",
    "losses",
    "downgrade",
    "downgraded",
    "cuts guidance",
    "cut guidance",
    "lower guidance",
    "lawsuit",
    "investigation",
    "probe",
    "fraud",
    "ban",
    "banned",
    "sanctions",
    "tariff",
    "tariffs",
    "war",
    "recession",
    "layoffs",
    "layoff",
    "recall",
    "warning",
    "weak demand",
    "weak sales",
    "decline",
    "falls",
    "fall",
    "plunge",
    "plunges",
    "slump",
    "slumps",
    "cuts",
    "cut",
    "negative",
    "charges",
]


RISK_NEWS_TERMS = [
    "war",
    "conflict",
    "iran",
    "israel",
    "russia",
    "ukraine",
    "china",
    "taiwan",
    "sanctions",
    "tariff",
    "tariffs",
    "interest rates",
    "inflation",
    "recession",
    "oil",
    "crude",
    "opec",
    "hormuz",
    "united nations",
    "antitrust",
    "investigation",
    "lawsuit",
    "regulation",
    "regulatory",
    "ban",
    "export restrictions",
    "export controls",
]


# ============================================================
# 11. UTILIDADES
# ============================================================

def safe_float(value):
    """
    Convierte un valor a float de forma segura.
    """

    try:
        if value is None:
            return None

        if isinstance(value, pd.Series):
            if value.empty:
                return None
            value = value.iloc[-1]

        if isinstance(value, pd.DataFrame):
            if value.empty:
                return None
            value = value.iloc[-1, -1]

        if pd.isna(value):
            return None

        return float(value)

    except Exception:
        return None


def normalize_text(text):
    """
    Normaliza texto para análisis de noticias.
    """

    if text is None:
        return ""

    text = str(text).lower()

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def contains_term(text, term):
    """
    Busca palabras/frases evitando falsos positivos
    por coincidencias dentro de otras palabras.
    """

    text = normalize_text(text)
    term = normalize_text(term)

    if not text or not term:
        return False

    pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"

    return re.search(pattern, text) is not None


def count_terms(text, terms):
    """
    Cuenta cuántos términos diferentes aparecen.
    """

    count = 0

    for term in terms:
        if contains_term(text, term):
            count += 1

    return count


def is_us_ticker(ticker):
    return ticker in US_TICKERS


def is_etf(ticker):
    return ticker in ETF_TICKERS


def get_company_name(ticker):
    return COMPANY_NAMES.get(ticker, ticker)


def get_timezone_now():
    """
    Hora de Madrid para los mensajes.
    """

    try:
        if ZoneInfo is not None:
            return datetime.now(ZoneInfo("Europe/Madrid"))

    except Exception:
        pass

    return datetime.now()


def format_price(value):
    value = safe_float(value)

    if value is None:
        return "N/D"

    return f"{value:,.2f}"


def format_percent(value):
    value = safe_float(value)

    if value is None:
        return "N/D"

    return f"{value:.2f}%"


def format_number(value):
    value = safe_float(value)

    if value is None:
        return "N/D"

    return f"{value:,.2f}"


# ============================================================
# 12. DESCARGA DE DATOS
# ============================================================

def download_data(ticker, period=PERIOD, interval=INTERVAL):

    try:

        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=False,
            threads=False,
        )

        if df is None or df.empty:
            return None

        # Manejo de columnas MultiIndex de yfinance
        if isinstance(df.columns, pd.MultiIndex):

            try:
                df.columns = df.columns.get_level_values(0)
            except Exception:
                df.columns = [
                    str(col[0]) if isinstance(col, tuple) else str(col)
                    for col in df.columns
                ]

        required = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        for column in required:

            if column not in df.columns:
                return None

        df = df[required].copy()

        for column in required:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        df.dropna(
            subset=[
                "Open",
                "High",
                "Low",
                "Close",
            ],
            inplace=True,
        )

        if len(df) < 210:
            return None

        return df

    except Exception:
        return None


# ============================================================
# 13. RSI
# ============================================================

def calculate_rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()

    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi


# ============================================================
# 14. INDICADORES TÉCNICOS
# ============================================================

def add_indicators(df):

    df = df.copy()

    df["SMA20"] = df["Close"].rolling(20).mean()

    df["SMA50"] = df["Close"].rolling(50).mean()

    df["SMA200"] = df["Close"].rolling(200).mean()

    df["RSI"] = calculate_rsi(
        df["Close"],
        14,
    )

    df["VOL20"] = df["Volume"].rolling(20).mean()

    return df


# ============================================================
# 15. EUR/USD
# ============================================================

def get_eurusd():

    try:

        df = yf.download(
            "EURUSD=X",
            period="5d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )

        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):

            try:
                df.columns = df.columns.get_level_values(0)
            except Exception:
                pass

        if "Close" not in df.columns:
            return None

        value = safe_float(df["Close"].dropna().iloc[-1])

        if value is None or value <= 0:
            return None

        return value

    except Exception:
        return None


# ============================================================
# 16. RÉGIMEN DEL MERCADO
# ============================================================

def get_market_regime():

    try:

        df = download_data(
            MARKET_TICKER,
            MARKET_PERIOD,
            INTERVAL,
        )

        if df is None:
            return {
                "available": False,
                "favorable": False,
                "price": None,
                "sma50": None,
                "sma200": None,
            }

        df = add_indicators(df)

        if len(df) < 202:
            return {
                "available": False,
                "favorable": False,
                "price": None,
                "sma50": None,
                "sma200": None,
            }

        # Usamos la última vela COMPLETADA
        row = df.iloc[-2]

        price = safe_float(row["Close"])

        sma50 = safe_float(row["SMA50"])

        sma200 = safe_float(row["SMA200"])

        if (
            price is None
            or sma50 is None
            or sma200 is None
        ):
            return {
                "available": False,
                "favorable": False,
                "price": price,
                "sma50": sma50,
                "sma200": sma200,
            }

        favorable = (
            price > sma200
            and sma50 > sma200
        )

        return {
            "available": True,
            "favorable": favorable,
            "price": price,
            "sma50": sma50,
            "sma200": sma200,
        }

    except Exception:

        return {
            "available": False,
            "favorable": False,
            "price": None,
            "sma50": None,
            "sma200": None,
        }


# ============================================================
# 17. NOTICIAS GOOGLE NEWS
# ============================================================

def fetch_google_news(query, hours=NEWS_HOURS):

    url = (
        "https://news.google.com/rss/search?"
        f"q={quote(query)}"
        "&hl=en-US"
        "&gl=US"
        "&ceid=US:en"
    )

    results = []

    try:

        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; StockScanner/1.0)"
                )
            },
        )

        response.raise_for_status()

        root = ET.fromstring(
            response.content
        )

        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(hours=hours)
        )

        for item in root.findall(".//item"):

            title_el = item.find("title")

            link_el = item.find("link")

            pub_el = item.find("pubDate")

            source_el = item.find("source")

            title = (
                title_el.text.strip()
                if title_el is not None
                and title_el.text
                else ""
            )

            link = (
                link_el.text.strip()
                if link_el is not None
                and link_el.text
                else ""
            )

            pub_text = (
                pub_el.text.strip()
                if pub_el is not None
                and pub_el.text
                else ""
            )

            source = (
                source_el.text.strip()
                if source_el is not None
                and source_el.text
                else ""
            )

            if not title:
                continue

            pub_date = None

            if pub_text:

                try:

                    from email.utils import parsedate_to_datetime

                    pub_date = parsedate_to_datetime(
                        pub_text
                    )

                    if pub_date.tzinfo is None:
                        pub_date = pub_date.replace(
                            tzinfo=timezone.utc
                        )

                except Exception:
                    pub_date = None

            if pub_date is not None:

                if pub_date < cutoff:
                    continue

            results.append(
                {
                    "title": title,
                    "link": link,
                    "date": pub_date,
                    "source": source,
                }
            )

    except Exception:
        return []

    return results


# ============================================================
# 18. OBTENER TODAS LAS NOTICIAS RELEVANTES
# ============================================================

def get_news(ticker):

    company = get_company_name(ticker)

    queries = []

    # Consulta principal
    queries.append(
        f'"{company}" {ticker}'
    )

    # Consultas por temas especiales
    special_topics = SPECIAL_TOPICS.get(
        ticker,
        [],
    )

    for topic in special_topics[:8]:

        queries.append(
            f'"{company}" {ticker} {topic}'
        )

    # Temas generales
    for topic in GENERAL_RISK_TERMS[:8]:

        queries.append(
            f'"{company}" {ticker} {topic}'
        )

    all_news = []

    seen_titles = set()

    for query in queries:

        news = fetch_google_news(
            query,
            NEWS_HOURS,
        )

        for item in news:

            title_key = normalize_text(
                item.get("title", "")
            )

            if not title_key:
                continue

            if title_key in seen_titles:
                continue

            seen_titles.add(title_key)

            all_news.append(item)

    # Ordenar por fecha
    all_news.sort(
        key=lambda x: (
            x.get("date")
            if x.get("date") is not None
            else datetime.min.replace(
                tzinfo=timezone.utc
            )
        ),
        reverse=True,
    )

    return all_news[:MAX_NEWS]


# ============================================================
# 19. CLASIFICAR NOTICIAS
# ============================================================

def classify_news(news):

    if not news:

        return {
            "available": True,
            "count": 0,
            "impact": "SIN NOTICIAS",
            "negative_hits": 0,
            "positive_hits": 0,
            "risk_hits": 0,
            "risk_terms": [],
        }

    negative_hits = 0

    positive_hits = 0

    risk_hits = 0

    detected_risks = set()

    for item in news:

        title = normalize_text(
            item.get("title", "")
        )

        negative_hits += count_terms(
            title,
            NEGATIVE_NEWS_TERMS,
        )

        positive_hits += count_terms(
            title,
            POSITIVE_NEWS_TERMS,
        )

        for term in RISK_NEWS_TERMS:

            if contains_term(title, term):

                risk_hits += 1

                detected_risks.add(term)

    if negative_hits >= positive_hits + 2:

        impact = "NEGATIVO"

    elif positive_hits >= negative_hits + 2:

        impact = "POSITIVO"

    elif risk_hits > 0:

        impact = "MIXTO / RIESGO"

    else:

        impact = "NEUTRO"

    return {
        "available": True,
        "count": len(news),
        "impact": impact,
        "negative_hits": negative_hits,
        "positive_hits": positive_hits,
        "risk_hits": risk_hits,
        "risk_terms": sorted(
            detected_risks
        ),
    }


# ============================================================
# 20. RESULTADOS EMPRESARIALES
# ============================================================

def get_earnings_status(ticker):

    # Los ETFs no tienen resultados empresariales
    if is_etf(ticker):

        return {
            "available": True,
            "blocked": False,
            "status": "ETF — no aplica",
            "date": None,
        }

    try:

        ticker_obj = yf.Ticker(ticker)

        earnings = ticker_obj.get_earnings_dates(
            limit=8
        )

        if earnings is None or earnings.empty:

            return {
                "available": False,
                "blocked": True,
                "status": "No disponible — bloqueado",
                "date": None,
            }

        now = datetime.now(
            timezone.utc
        )

        dates = []

        for index in earnings.index:

            try:

                dt = pd.Timestamp(index)

                if dt.tzinfo is None:
                    dt = dt.tz_localize(
                        timezone.utc
                    )
                else:
                    dt = dt.tz_convert(
                        timezone.utc
                    )

                dates.append(dt.to_pydatetime())

            except Exception:
                continue

        if not dates:

            return {
                "available": False,
                "blocked": True,
                "status": "No disponible — bloqueado",
                "date": None,
            }

        nearest = min(
            dates,
            key=lambda x: abs(
                (x - now).total_seconds()
            ),
        )

        blackout = timedelta(
            days=EARNINGS_BLACKOUT_DAYS
        )

        blocked = (
            abs(nearest - now)
            <= blackout
        )

        return {
            "available": True,
            "blocked": blocked,
            "status": (
                "BLOQUEADO — resultados cercanos"
                if blocked
                else "Resultados fuera de ventana"
            ),
            "date": nearest,
        }

    except Exception:

        # Si no podemos verificar resultados,
        # no permitimos confirmar la operación.
        return {
            "available": False,
            "blocked": True,
            "status": "No disponible — bloqueado",
            "date": None,
        }


# ============================================================
# 21. ANÁLISIS TÉCNICO PRINCIPAL
# ============================================================

def analyze_ticker(ticker):

    result = {
        "ticker": ticker,
        "company": get_company_name(ticker),
        "valid_data": False,
        "score": 0,
        "price": None,
        "previous_close": None,
        "open": None,
        "high": None,
        "low": None,
        "sma20": None,
        "sma50": None,
        "sma200": None,
        "rsi": None,
        "support": None,
        "support_distance": None,
        "volume_ratio": None,
        "avg_volume_value": None,
        "avg_volume_value_eur": None,
        "daily_move": None,
        "bullish_candle": False,
        "close_above_previous_high": False,
        "rebound_confirmed": False,
        "entry": None,
        "stop": None,
        "target1": None,
        "target2": None,
        "risk_per_share": None,
        "reward_risk": None,
        "news": [],
        "news_info": None,
        "earnings": None,
        "position": None,
        "primary_filters": {},
        "secondary_filters": {},
        "safety_filters": {},
        "confirmed": False,
        "watch": False,
        "diagnosis": [],
        "error": None,
    }

    # --------------------------------------------------------
    # DATOS
    # --------------------------------------------------------

    df = download_data(ticker)

    if df is None:

        result["error"] = (
            "Datos insuficientes o no disponibles"
        )

        result["diagnosis"].append(
            "DATOS: ❌ insuficientes/no disponibles"
        )

        return result

    df = add_indicators(df)

    if len(df) < 210:

        result["error"] = (
            "Menos de 210 sesiones disponibles"
        )

        result["diagnosis"].append(
            "DATOS: ❌ menos de 210 sesiones"
        )

        return result

    # --------------------------------------------------------
    # ÚLTIMA VELA
    # --------------------------------------------------------

    current = df.iloc[-1]

    # La vela anterior se considera completada.
    previous = df.iloc[-2]

    price = safe_float(
        current["Close"]
    )

    previous_close = safe_float(
        previous["Close"]
    )

    current_open = safe_float(
        current["Open"]
    )

    current_high = safe_float(
        current["High"]
    )

    current_low = safe_float(
        current["Low"]
    )

    previous_high = safe_float(
        previous["High"]
    )

    if (
        price is None
        or previous_close is None
    ):

        result["error"] = (
            "Precio no disponible"
        )

        result["diagnosis"].append(
            "PRECIO: ❌ no disponible"
        )

        return result

    # --------------------------------------------------------
    # INDICADORES DE LA ÚLTIMA VELA COMPLETADA
    # --------------------------------------------------------

    analysis_row = df.iloc[-2]

    sma20 = safe_float(
        analysis_row["SMA20"]
    )

    sma50 = safe_float(
        analysis_row["SMA50"]
    )

    sma200 = safe_float(
        analysis_row["SMA200"]
    )

    rsi = safe_float(
        analysis_row["RSI"]
    )

    if (
        sma20 is None
        or sma50 is None
        or sma200 is None
        or rsi is None
    ):

        result["error"] = (
            "Indicadores incompletos"
        )

        result["diagnosis"].append(
            "INDICADORES: ❌ incompletos"
        )

        return result

    # --------------------------------------------------------
    # SOPORTE
    # --------------------------------------------------------
    #
    # Usamos las 20 velas COMPLETADAS anteriores.
    # Evita que la vela intradía cambie artificialmente
    # el soporte durante la sesión.
    # --------------------------------------------------------

    completed_lows = (
        df["Low"]
        .iloc[-22:-2]
        .dropna()
    )

    if completed_lows.empty:

        result["error"] = (
            "No se pudo calcular soporte"
        )

        result["diagnosis"].append(
            "SOPORTE: ❌ no calculable"
        )

        return result

    support = safe_float(
        completed_lows.min()
    )

    if support is None or support <= 0:

        result["error"] = (
            "Soporte inválido"
        )

        result["diagnosis"].append(
            "SOPORTE: ❌ inválido"
        )

        return result

    # --------------------------------------------------------
    # DISTANCIA AL SOPORTE
    # --------------------------------------------------------

    support_distance = (
        (price - support)
        / price
    )

    # --------------------------------------------------------
    # VOLUMEN
    # --------------------------------------------------------
    #
    # Para evitar usar volumen parcial intradía:
    # volumen de la última vela completada /
    # promedio de las 20 anteriores.
    # --------------------------------------------------------

    previous_volume = safe_float(
        previous["Volume"]
    )

    previous_20_volumes = (
        df["Volume"]
        .iloc[-22:-2]
        .dropna()
    )

    avg_volume = (
        safe_float(
            previous_20_volumes.mean()
        )
        if not previous_20_volumes.empty
        else None
    )

    if (
        previous_volume is not None
        and avg_volume is not None
        and avg_volume > 0
    ):

        volume_ratio = (
            previous_volume
            / avg_volume
        )

    else:

        volume_ratio = None

    # --------------------------------------------------------
    # LIQUIDEZ
    # --------------------------------------------------------

    if (
        avg_volume is not None
        and sma50 is not None
    ):

        avg_volume_value = (
            avg_volume * sma50
        )

    else:

        avg_volume_value = None

    eurusd = None

    if is_us_ticker(ticker):

        eurusd = get_eurusd()

        if (
            avg_volume_value is not None
            and eurusd is not None
            and eurusd > 0
        ):

            avg_volume_value_eur = (
                avg_volume_value
                / eurusd
            )

        else:

            avg_volume_value_eur = None

    else:

        avg_volume_value_eur = (
            avg_volume_value
        )

    # --------------------------------------------------------
    # MOVIMIENTO DIARIO
    # --------------------------------------------------------

    daily_move = abs(
        price - previous_close
    ) / previous_close

    # --------------------------------------------------------
    # VELA ALCISTA
    # --------------------------------------------------------

    bullish_candle = False

    if (
        current_open is not None
        and price is not None
    ):

        bullish_candle = (
            price > current_open
        )

    # --------------------------------------------------------
    # SUPERA MÁXIMO PREVIO
    # --------------------------------------------------------

    close_above_previous_high = False

    if previous_high is not None:

        close_above_previous_high = (
            price > previous_high
        )

    # --------------------------------------------------------
    # REBOTE
    # --------------------------------------------------------
    #
    # El precio debe estar cerca del soporte y demostrar
    # comportamiento alcista.
    # --------------------------------------------------------

    rebound_distance = (
        (price - support)
        / support
    )

    rebound_confirmed = (
        rebound_distance
        <= MAX_REBOUND_DISTANCE
        and bullish_candle
        and price >= support
    )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    score = 0

    # Precio sobre SMA200
    if price > sma200:
        score += 20

    # Tendencia SMA50 > SMA200
    if sma50 > sma200:
        score += 15

    # Precio sobre SMA50
    if price > sma50:
        score += 10

    # RSI
    if rsi < 30:
        score += 25

    elif rsi <= 45:
        score += 20

    elif rsi <= 55:
        score += 8

    # Volumen
    if volume_ratio is not None:

        if volume_ratio >= 1.50:
            score += 15

        elif volume_ratio >= 1.15:
            score += 8

    # Cercanía al soporte
    if support_distance <= 0.03:
        score += 20

    elif support_distance <= 0.06:
        score += 10

    score = min(
        score,
        100,
    )

    # --------------------------------------------------------
    # ENTRADA
    # --------------------------------------------------------

    entry = price

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    stop = support * 0.98

    risk_per_share = (
        entry - stop
    )

    if risk_per_share <= 0:

        result["error"] = (
            "Riesgo por acción inválido"
        )

        result["diagnosis"].append(
            "RIESGO: ❌ inválido"
        )

        return result

    # --------------------------------------------------------
    # RESISTENCIA PARA OBJETIVO REAL
    # --------------------------------------------------------
    #
    # En lugar de fabricar un R/R de 2:1 artificial,
    # usamos una resistencia real reciente.
    # --------------------------------------------------------

    resistance_window = (
        df["High"]
        .iloc[-62:-2]
        .dropna()
    )

    resistance = None

    if not resistance_window.empty:

        resistance = safe_float(
            resistance_window.max()
        )

    # Objetivo mínimo matemático de 2R
    minimum_target_1 = (
        entry + 2 * risk_per_share
    )

    # Objetivo 2 = 3R
    target2 = (
        entry + 3 * risk_per_share
    )

    if (
        resistance is not None
        and resistance > entry
    ):

        if resistance >= minimum_target_1:

            target1 = resistance

        else:

            target1 = resistance

    else:

        target1 = minimum_target_1

    reward = (
        target1 - entry
    )

    reward_risk = (
        reward / risk_per_share
    )

    # --------------------------------------------------------
    # RESULTADO DATOS
    # --------------------------------------------------------

    result["valid_data"] = True

    result["price"] = price

    result["previous_close"] = previous_close

    result["open"] = current_open

    result["high"] = current_high

    result["low"] = current_low

    result["sma20"] = sma20

    result["sma50"] = sma50

    result["sma200"] = sma200

    result["rsi"] = rsi

    result["support"] = support

    result["support_distance"] = support_distance

    result["volume_ratio"] = volume_ratio

    result["avg_volume_value"] = avg_volume_value

    result["avg_volume_value_eur"] = (
        avg_volume_value_eur
    )

    result["daily_move"] = daily_move

    result["bullish_candle"] = (
        bullish_candle
    )

    result["close_above_previous_high"] = (
        close_above_previous_high
    )

    result["rebound_confirmed"] = (
        rebound_confirmed
    )

    result["entry"] = entry

    result["stop"] = stop

    result["target1"] = target1

    result["target2"] = target2

    result["risk_per_share"] = (
        risk_per_share
    )

    result["reward_risk"] = (
        reward_risk
    )

    result["score"] = score

    # ========================================================
    # 22. FILTROS PRIMARIOS
    # ========================================================

    primary = {}

    primary["Score mínimo"] = (
        score >= MIN_SCORE
    )

    primary["RSI <= 45"] = (
        rsi <= MAX_RSI
    )

    primary["Precio cerca del soporte"] = (
        support_distance
        <= MAX_SUPPORT_DISTANCE
    )

    primary["R/R >= 2"] = (
        reward_risk >= 2.0
    )

    result["primary_filters"] = primary

    # ========================================================
    # 23. NOTICIAS
    # ========================================================

    # Solo buscamos noticias si técnicamente ya supera
    # el filtro inicial.
    if all(primary.values()):

        news = get_news(ticker)

        news_info = classify_news(
            news
        )

    else:

        news = []

        news_info = {
            "available": True,
            "count": 0,
            "impact": "NO ANALIZADAS — filtro técnico",
            "negative_hits": 0,
            "positive_hits": 0,
            "risk_hits": 0,
            "risk_terms": [],
        }

    result["news"] = news

    result["news_info"] = news_info

    # Añadir noticias como filtro primario
    primary["Noticias no negativas"] = (
        news_info["impact"]
        != "NEGATIVO"
    )

    result["primary_filters"] = primary

    # ========================================================
    # 24. RÉGIMEN DE MERCADO
    # ========================================================

    market = get_market_regime()

    market_favorable = (
        market["available"]
        and market["favorable"]
    )

    # ========================================================
    # 25. RESULTADOS
    # ========================================================

    earnings = get_earnings_status(
        ticker
    )

    result["earnings"] = earnings

    # ========================================================
    # 26. FILTROS SECUNDARIOS
    # ========================================================

    secondary = {}

    secondary["Rebote confirmado"] = (
        rebound_confirmed
    )

    secondary["Volumen >= 1.15x"] = (
        volume_ratio is not None
        and volume_ratio
        >= MIN_VOLUME_CONFIRMATION
    )

    secondary["Precio supera máximo previo"] = (
        close_above_previous_high
    )

    secondary["S&P 500 favorable"] = (
        market_favorable
    )

    secondary["Sin resultados cercanos"] = (
        earnings["available"]
        and not earnings["blocked"]
    )

    result["secondary_filters"] = (
        secondary
    )

    # ========================================================
    # 27. FILTROS DE SEGURIDAD
    # ========================================================

    safety = {}

    safety["Liquidez suficiente"] = (
        avg_volume_value_eur is not None
        and avg_volume_value_eur
        >= MIN_AVG_DOLLAR_VOLUME
    )

    safety["Movimiento diario <= 8%"] = (
        daily_move <= MAX_DAILY_MOVE
    )

    safety["Datos válidos"] = (
        result["valid_data"]
    )

    safety["Resultados verificables"] = (
        earnings["available"]
    )

    safety["Noticias disponibles"] = (
        news_info["available"]
    )

    safety["Mercado favorable"] = (
        market_favorable
    )

    safety["Sin noticia negativa"] = (
        news_info["impact"]
        != "NEGATIVO"
    )

    result["safety_filters"] = safety

    # ========================================================
    # 28. GESTIÓN DE CAPITAL
    # ========================================================

    position = calculate_position(
        ticker=ticker,
        entry=entry,
        stop=stop,
        eurusd=eurusd,
    )

    result["position"] = position

    # ========================================================
    # 29. CONFIRMACIÓN FINAL
    # ========================================================

    all_primary = all(
        primary.values()
    )

    all_secondary = all(
        secondary.values()
    )

    all_safety = all(
        safety.values()
    )

    position_valid = (
        position is not None
        and position.get(
            "shares",
            0
        ) >= 1
    )

    confirmed = (
        all_primary
        and all_secondary
        and all_safety
        and position_valid
    )

    # Una noticia NEGATIVA siempre anula la señal.
    if news_info["impact"] == "NEGATIVO":

        confirmed = False

    # Si no podemos comprobar resultados,
    # nunca confirmamos.
    if not earnings["available"]:

        confirmed = False

    # Si falta FX para una acción USA,
    # nunca confirmamos.
    if is_us_ticker(ticker):

        if eurusd is None:

            confirmed = False

    # REQUERIR TODOS LOS FILTROS
    if REQUIRE_ALL_FILTERS:

        confirmed = (
            all_primary
            and all_secondary
            and all_safety
            and position_valid
        )

    result["confirmed"] = confirmed

    # ========================================================
    # 30. WATCHLIST INTERNA
    # ========================================================

    secondary_pass_count = sum(
        1
        for value in secondary.values()
        if value
    )

    watch = (
        all_primary
        and secondary_pass_count >= 4
        and all_safety
        and news_info["impact"]
        != "NEGATIVO"
        and not confirmed
    )

    result["watch"] = watch

    # ========================================================
    # 31. DIAGNÓSTICO DE FILTROS
    # ========================================================

    diagnosis = []

    for name, passed in primary.items():

        diagnosis.append(
            f"PRIMARIO {'✅' if passed else '❌'} {name}"
        )

    for name, passed in secondary.items():

        diagnosis.append(
            f"SECUNDARIO {'✅' if passed else '❌'} {name}"
        )

    for name, passed in safety.items():

        diagnosis.append(
            f"SEGURIDAD {'✅' if passed else '❌'} {name}"
        )

    if position_valid:

        diagnosis.append(
            "POSICIÓN ✅ capital/riesgo válido"
        )

    else:

        diagnosis.append(
            "POSICIÓN ❌ no se puede abrir con 5.000 € / riesgo 1%"
        )

    if news_info["impact"] == "NEGATIVO":

        diagnosis.append(
            "NOTICIAS ❌ NEGATIVO — señal anulada"
        )

    if confirmed:

        diagnosis.append(
            "RESULTADO FINAL: ✅ CONFIRMADA"
        )

    else:

        diagnosis.append(
            "RESULTADO FINAL: ❌ NO CONFIRMADA"
        )

    result["diagnosis"] = diagnosis

    return result


# ============================================================
# 32. CÁLCULO DE POSICIÓN
# ============================================================

def calculate_position(
    ticker,
    entry,
    stop,
    eurusd,
):

    try:

        if entry is None or stop is None:
            return None

        if entry <= 0 or stop <= 0:
            return None

        risk_per_share_local = (
            entry - stop
        )

        if risk_per_share_local <= 0:
            return None

        # ----------------------------------------------------
        # ACCIONES USA
        # ----------------------------------------------------

        if is_us_ticker(ticker):

            if (
                eurusd is None
                or eurusd <= 0
            ):

                return None

            risk_per_share_eur = (
                risk_per_share_local
                / eurusd
            )

            price_eur = (
                entry
                / eurusd
            )

        # ----------------------------------------------------
        # ACCIONES EUROPEAS / ETFs
        # ----------------------------------------------------

        else:

            risk_per_share_eur = (
                risk_per_share_local
            )

            price_eur = entry

        if (
            risk_per_share_eur <= 0
            or price_eur <= 0
        ):

            return None

        # Número de acciones por riesgo
        shares_by_risk = math.floor(
            MAX_RISK_EUR
            / risk_per_share_eur
        )

        # Número máximo por capital
        shares_by_capital = math.floor(
            CAPITAL_EUR
            / price_eur
        )

        shares = min(
            shares_by_risk,
            shares_by_capital,
        )

        if shares < 1:

            return {
                "shares": 0,
                "capital_used_eur": 0,
                "risk_eur": 0,
                "price_eur": price_eur,
                "risk_per_share_eur": (
                    risk_per_share_eur
                ),
            }

        capital_used_eur = (
            shares
            * price_eur
        )

        risk_eur = (
            shares
            * risk_per_share_eur
        )

        return {
            "shares": shares,
            "capital_used_eur": capital_used_eur,
            "risk_eur": risk_eur,
            "price_eur": price_eur,
            "risk_per_share_eur": (
                risk_per_share_eur
            ),
        }

    except Exception:

        return None


# ============================================================
# 33. FORMATEAR DIAGNÓSTICO
# ============================================================

def build_diagnostic(result):

    ticker = result["ticker"]

    company = result["company"]

    lines = []

    lines.append(
        f"🔎 {ticker} — {company}"
    )

    lines.append(
        f"Score: {result.get('score', 0)}/100"
    )

    if result.get("rsi") is not None:

        lines.append(
            f"RSI: {format_number(result['rsi'])}"
        )

    if result.get("price") is not None:

        lines.append(
            f"Precio: {format_price(result['price'])}"
        )

    if result.get("support") is not None:

        lines.append(
            f"Soporte: {format_price(result['support'])}"
        )

    news_info = result.get(
        "news_info"
    )

    if news_info:

        lines.append(
            f"Noticias analizadas: "
            f"{news_info.get('count', 0)}"
        )

        lines.append(
            f"Impacto: "
            f"{news_info.get('impact', 'N/D')}"
        )

        risks = news_info.get(
            "risk_terms",
            []
        )

        if risks:

            lines.append(
                "Riesgos: "
                + ", ".join(risks[:8])
            )

    lines.append("")

    for item in result.get(
        "diagnosis",
        []
    ):

        lines.append(
            "• " + item
        )

    return "\n".join(lines)


# ============================================================
# 34. CONSTRUIR ALERTA CONFIRMADA
# ============================================================

def build_confirmed_alert(
    result,
    market,
):

    ticker = result["ticker"]

    company = result["company"]

    entry = result["entry"]

    stop = result["stop"]

    target1 = result["target1"]

    target2 = result["target2"]

    position = result["position"]

    news_info = result["news_info"]

    earnings = result["earnings"]

    lines = []

    lines.append(
        "🚨🚨 SEÑAL CONFIRMADA 🚨🚨"
    )

    lines.append("")

    lines.append(
        f"📌 {ticker} — {company}"
    )

    lines.append(
        "🇺🇸 USA"
        if is_us_ticker(ticker)
        else "🇪🇺 EUROPA / ETF"
    )

    lines.append("")

    lines.append(
        f"⭐ SCORE: {result['score']}/100"
    )

    lines.append(
        f"💵 Entrada: {format_price(entry)}"
    )

    lines.append(
        f"🛑 Stop: {format_price(stop)}"
    )

    lines.append(
        f"🎯 Objetivo 1: {format_price(target1)}"
    )

    lines.append(
        f"🎯 Objetivo 2: {format_price(target2)}"
    )

    lines.append(
        f"📐 R/R: "
        f"{result['reward_risk']:.2f}:1"
    )

    lines.append("")

    if position:

        lines.append(
            f"💶 Capital usado: "
            f"{position['capital_used_eur']:.2f} €"
        )

        lines.append(
            f"📦 Acciones: "
            f"{position['shares']}"
        )

        lines.append(
            f"⚠️ Riesgo: "
            f"{position['risk_eur']:.2f} €"
        )

    lines.append("")

    lines.append(
        f"📊 RSI: "
        f"{result['rsi']:.1f}"
    )

    lines.append(
        f"📍 Soporte: "
        f"{format_price(result['support'])}"
    )

    if result["volume_ratio"] is not None:

        lines.append(
            f"📈 Volumen: "
            f"{result['volume_ratio']:.2f}x"
        )

    lines.append("")

    # Noticias
    lines.append(
        f"📰 Noticias analizadas: "
        f"{news_info['count']}"
    )

    lines.append(
        f"Impacto: "
        f"{news_info['impact']}"
    )

    if news_info["risk_terms"]:

        lines.append(
            "⚠️ Riesgos detectados: "
            + ", ".join(
                news_info["risk_terms"][:8]
            )
        )

    lines.append("")

    # Mercado
    if market["available"]:

        if market["favorable"]:

            lines.append(
                "🌎 Mercado: FAVORABLE"
            )

        else:

            lines.append(
                "🌎 Mercado: NO FAVORABLE"
            )

    # Resultados
    if earnings["date"] is not None:

        date_text = earnings[
            "date"
        ].strftime(
            "%d/%m/%Y"
        )

        lines.append(
            f"📅 Próximos resultados: "
            f"{date_text}"
        )

    lines.append("")

    lines.append(
        "🟢 TODOS LOS FILTROS CONFIRMADOS"
    )

    lines.append(
        "SEÑAL FINAL: COMPRAR"
    )

    return "\n".join(lines)


# ============================================================
# 35. MENSAJE DE PRECAUCIÓN
# ============================================================

def build_caution_message(
    result
):

    ticker = result["ticker"]

    company = result["company"]

    news_info = result.get(
        "news_info",
        {}
    )

    lines = []

    lines.append(
        f"⚠️ {ticker} — {company}"
    )

    lines.append("")

    lines.append(
        f"Noticias analizadas: "
        f"{news_info.get('count', 0)}"
    )

    lines.append(
        f"Impacto: "
        f"{news_info.get('impact', 'N/D')}"
    )

    risks = news_info.get(
        "risk_terms",
        []
    )

    if risks:

        lines.append(
            "Riesgos: "
            + ", ".join(risks[:8])
        )

    lines.append("")

    lines.append(
        "SEÑAL FINAL: PRECAUCIÓN — esperar"
    )

    return "\n".join(lines)


# ============================================================
# 36. TELEGRAM
# ============================================================

def send_telegram(message):

    if (
        not TELEGRAM_BOT_TOKEN
        or not TELEGRAM_CHAT_ID
    ):

        print(
            "Telegram no configurado."
        )

        return False

    url = (
        "https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    # Telegram permite 4096 caracteres.
    # Dejamos margen.
    if len(message) > 3900:

        message = (
            message[:3850]
            + "\n\n...[mensaje recortado]"
        )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=20,
        )

        response.raise_for_status()

        return True

    except Exception as e:

        print(
            "Error enviando Telegram:",
            e,
        )

        return False


# ============================================================
# 37. RESUMEN DEL ESCÁNER
# ============================================================

def build_summary(
    results,
    market,
):

    confirmed = [
        r
        for r in results
        if r.get("confirmed")
    ]

    watch = [
        r
        for r in results
        if r.get("watch")
    ]

    evaluated = [
        r
        for r in results
        if r.get("valid_data")
    ]

    now = get_timezone_now()

    lines = []

    lines.append(
        "📊 ESCÁNER DE CHOLLOS DEGIRO"
    )

    lines.append("")

    lines.append(
        "🕐 "
        + now.strftime(
            "%d/%m/%Y %H:%M"
        )
        + " — hora España"
    )

    lines.append("")

    lines.append(
        f"💰 Capital: {CAPITAL_EUR:.0f} €"
    )

    lines.append(
        f"⚠️ Riesgo máximo por operación: "
        f"{MAX_RISK_EUR:.0f} €"
    )

    lines.append("")

    lines.append(
        f"🔎 Tickers analizados: "
        f"{len(results)}"
    )

    lines.append(
        f"📊 Con datos válidos: "
        f"{len(evaluated)}"
    )

    lines.append(
        f"🚨 Señales confirmadas: "
        f"{len(confirmed)}"
    )

    lines.append(
        f"👀 Watchlist interna: "
        f"{len(watch)}"
    )

    lines.append("")

    if market["available"]:

        if market["favorable"]:

            lines.append(
                "🌎 S&P 500: FAVORABLE"
            )

        else:

            lines.append(
                "🌎 S&P 500: NO FAVORABLE"
            )

    else:

        lines.append(
            "🌎 S&P 500: DATOS NO DISPONIBLES"
        )

    lines.append("")

    if confirmed:

        lines.append(
            "🚨 SEÑALES:"
        )

        for r in confirmed:

            lines.append(
                f"• {r['ticker']} "
                f"Score {r['score']}/100 "
                f"Entrada {format_price(r['entry'])}"
            )

    else:

        lines.append(
            "ℹ️ No hay ninguna señal que cumpla "
            "TODOS los filtros."
        )

    return "\n".join(lines)


# ============================================================
# 38. EJECUCIÓN PRINCIPAL
# ============================================================

def main():

    print("=" * 70)

    print(
        "📊 INICIANDO ESCÁNER DE CHOLLOS"
    )

    print("=" * 70)

    print(
        f"Tickers: {len(TICKERS)}"
    )

    print(
        f"Capital: {CAPITAL_EUR:.2f} €"
    )

    print(
        f"Riesgo máximo: {MAX_RISK_EUR:.2f} €"
    )

    print("")

    # --------------------------------------------------------
    # MERCADO
    # --------------------------------------------------------

    market = get_market_regime()

    if market["available"]:

        print(
            "S&P 500:",
            "FAVORABLE"
            if market["favorable"]
            else "NO FAVORABLE",
        )

    else:

        print(
            "S&P 500: DATOS NO DISPONIBLES"
        )

    print("")

    # --------------------------------------------------------
    # ANALIZAR TICKERS
    # --------------------------------------------------------

    results = []

    confirmed_results = []

    caution_results = []

    for index, ticker in enumerate(
        TICKERS,
        start=1,
    ):

        print(
            f"[{index}/{len(TICKERS)}] "
            f"Analizando {ticker}..."
        )

        try:

            result = analyze_ticker(
                ticker
            )

            results.append(result)

            # ----------------------------------------------
            # CONFIRMADA
            # ----------------------------------------------

            if result.get("confirmed"):

                confirmed_results.append(
                    result
                )

                print(
                    f"  🚨 CONFIRMADA "
                    f"Score {result['score']}"
                )

            # ----------------------------------------------
            # NOTICIA NEGATIVA
            # ----------------------------------------------

            elif (
                result.get(
                    "news_info"
                )
                and result[
                    "news_info"
                ].get(
                    "impact"
                )
                == "NEGATIVO"
            ):

                caution_results.append(
                    result
                )

                print(
                    "  ⚠️ PRECAUCIÓN — "
                    "noticia negativa"
                )

            # ----------------------------------------------
            # NO CONFIRMADA
            # ----------------------------------------------

            else:

                print(
                    f"  ❌ No confirmada "
                    f"Score {result.get('score', 0)}"
                )

        except Exception as e:

            print(
                f"  ❌ Error analizando "
                f"{ticker}: {e}"
            )

            results.append(
                {
                    "ticker": ticker,
                    "company": get_company_name(
                        ticker
                    ),
                    "valid_data": False,
                    "score": 0,
                    "confirmed": False,
                    "watch": False,
                    "error": str(e),
                    "diagnosis": [
                        f"ERROR: {e}"
                    ],
                    "news_info": {
                        "available": False,
                        "count": 0,
                        "impact": "NO DISPONIBLE",
                        "risk_terms": [],
                    },
                }
            )

    print("")

    print("=" * 70)

    print(
        "ANÁLISIS TERMINADO"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # TELEGRAM: SOLO SEÑALES CONFIRMADAS
    # --------------------------------------------------------

    for result in confirmed_results:

        try:

            message = build_confirmed_alert(
                result,
                market,
            )

            send_telegram(
                message
            )

        except Exception as e:

            print(
                "Error creando señal Telegram:",
                e,
            )

    # --------------------------------------------------------
    # IMPORTANTE:
    #
    # NO enviamos todos los candidatos.
    #
    # Tampoco enviamos automáticamente las señales
    # negativas como alertas independientes.
    #
    # La noticia negativa solo sirve para bloquear.
    #
    # Esto evita llenar Telegram de ruido.
    # --------------------------------------------------------

    # --------------------------------------------------------
    # RESUMEN
    # --------------------------------------------------------

    summary = build_summary(
        results,
        market,
    )

    send_telegram(
        summary
    )

    # --------------------------------------------------------
    # DIAGNÓSTICO EN CONSOLA
    # --------------------------------------------------------

    print("")

    print(
        "========== DIAGNÓSTICO =========="
    )

    for result in results:

        ticker = result.get(
            "ticker",
            "N/D",
        )

        score = result.get(
            "score",
            0,
        )

        confirmed = result.get(
            "confirmed",
            False,
        )

        print("")

        print(
            f"{ticker} | "
            f"Score {score} | "
            f"{'CONFIRMADA' if confirmed else 'NO CONFIRMADA'}"
        )

        for line in result.get(
            "diagnosis",
            [],
        ):

            print(
                " ",
                line,
            )

    print("")

    print(
        "=================================="
    )

    print(
        f"Señales confirmadas: "
        f"{len(confirmed_results)}"
    )

    print(
        "=================================="
    )


# ============================================================
# 39. ARRANQUE
# ============================================================

if __name__ == "__main__":

    main()
