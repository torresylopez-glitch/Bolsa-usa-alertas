import os
import math
import time
import re
import requests
import numpy as np
import pandas as pd
import yfinance as yf
import xml.etree.ElementTree as ET

from urllib.parse import quote
from datetime import datetime, timezone, timedelta


# ============================================================
# 📊 ESCÁNER DE CHOLLOS PARA DEGIRO
# VERSIÓN DEFINITIVA
# ============================================================


# ============================================================
# 1. UNIVERSO
# ============================================================

STOCK_TICKERS = [
    # USA
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO",
    "TSLA", "AMD", "NFLX", "JPM", "V", "MA", "COST", "WMT",
    "LLY", "XOM", "ORCL", "CRM", "PLTR", "QCOM", "MU", "INTC",
    "AMAT", "UBER", "PANW", "ADBE",

    # ESPAÑA
    "IBE.MC", "BBVA.MC", "SAN.MC", "ITX.MC", "REP.MC", "TEF.MC",

    # ALEMANIA
    "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE",

    # FRANCIA
    "AIR.PA", "SU.PA", "MC.PA", "TTE.PA",

    # PAÍSES BAJOS
    "ASML.AS", "ADYEN.AS",

    # ITALIA
    "RACE.MI", "ENEL.MI", "ISP.MI",
]

ETF_TICKERS = [
    "SXR8.DE",
    "SXRV.DE",
    "ZPDF.DE",
]

TICKERS = STOCK_TICKERS + ETF_TICKERS


ETF_INFO = {
    "SXR8.DE": {
        "name": "iShares Core S&P 500 UCITS ETF",
        "isin": "IE00B5BMR087",
        "ticker": "SXR8",
    },
    "SXRV.DE": {
        "name": "iShares NASDAQ 100 UCITS ETF",
        "isin": "IE00B53SZB19",
        "ticker": "SXRV",
    },
    "ZPDF.DE": {
        "name": "SPDR S&P U.S. Financials Select Sector UCITS ETF",
        "isin": "IE00BWBXM500",
        "ticker": "ZPDF",
    },
}


COMPANY_NAMES = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet Google",
    "META": "Meta Platforms",
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
    "MU": "Micron Technology",
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
}


# ============================================================
# 2. CONFIGURACIÓN
# ============================================================

# Filtro principal
MIN_SCORE = 75
MAX_RSI = 45
MAX_SUPPORT_DISTANCE = 0.03

# Confirmación técnica
MAX_REBOUND_DISTANCE = 0.015
MIN_VOLUME_CONFIRMATION = 1.15

# Liquidez
MIN_AVG_DOLLAR_VOLUME = 5_000_000

# Evitar entradas después de movimientos demasiado violentos
MAX_DAILY_MOVE = 0.08

# Datos
PERIOD = "1y"
INTERVAL = "1d"

# Noticias
NEWS_HOURS = 24
MAX_NEWS = 8

# Mercado
MARKET_TICKER = "^GSPC"
MARKET_PERIOD = "1y"

# Resultados
EARNINGS_BLACKOUT_DAYS = 3

# Capital
CAPITAL_EUR = float(os.getenv("CAPITAL_EUR", "5000"))
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.01"))

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# IMPORTANTE:
# Solo se envían a Telegram señales CONFIRMADAS.
SEND_WATCHLIST_ALERTS = False

# Solo enviar alerta si hay al menos esta cantidad de filtros
# técnicos/mercado y noticias completamente válidos.
REQUIRE_ALL_FILTERS = True


# ============================================================
# 3. PALABRAS DE NOTICIAS
# ============================================================

POSITIVE_WORDS = [
    "beat",
    "beats",
    "beating",
    "surpasses",
    "surprise",
    "upgrade",
    "upgraded",
    "raises guidance",
    "raised guidance",
    "strong guidance",
    "record revenue",
    "record profit",
    "profit rises",
    "revenue rises",
    "growth",
    "grows",
    "approval",
    "approved",
    "deal",
    "contract",
    "partnership",
    "buyback",
    "dividend increase",
    "acquisition",
    "acquires",
    "positive",
    "outlook raised",
    "guidance raised",
    "expands",
    "orders increase",
    "orders rise",
    "new contract",
    "new orders",

    "supera",
    "supera las previsiones",
    "mejora",
    "mejora previsiones",
    "eleva previsiones",
    "beneficio aumenta",
    "ingresos aumentan",
    "crecimiento",
    "aprobado",
    "aprobación",
    "contrato",
    "acuerdo",
    "alianza",
    "recompra",
    "dividendo aumenta",
    "adquisición",
    "positivo",
]


NEGATIVE_WORDS = [
    "miss",
    "misses",
    "missed",
    "warning",
    "profit warning",
    "cuts guidance",
    "cut guidance",
    "lowers guidance",
    "lower guidance",
    "downgrade",
    "downgraded",
    "lawsuit",
    "investigation",
    "investigated",
    "fraud",
    "ban",
    "banned",
    "sanctions",
    "tariff",
    "tariffs",
    "layoffs",
    "layoff",
    "recall",
    "recalls",
    "failure",
    "fails",
    "failed",
    "weak demand",
    "demand falls",
    "sales fall",
    "revenue falls",
    "profit falls",
    "loss",
    "losses",
    "decline",
    "falls",
    "falling",
    "drops",
    "drop",
    "plunges",
    "plunge",
    "cuts",
    "cut",
    "recession",
    "crisis",
    "default",
    "bankruptcy",
    "delay",
    "delays",
    "rejected",
    "rejection",
    "negative",
    "adverse",
    "disappointing",
    "disappoints",

    "incumple",
    "rebaja previsiones",
    "recorta previsiones",
    "investigación",
    "investigado",
    "demanda",
    "sanciones",
    "aranceles",
    "despidos",
    "retirada",
    "fallo",
    "fracaso",
    "caída",
    "cae",
    "baja",
    "pérdidas",
    "recesión",
    "crisis",
    "retraso",
    "rechazado",
    "negativo",
    "adverso",
    "decepcionante",
]


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
    "sanction",
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
    "middle east",
    "un",
    "antitrust",
    "regulation",
    "regulatory",
    "export restrictions",
    "export controls",

    "guerra",
    "conflicto",
    "iran",
    "israel",
    "rusia",
    "ucrania",
    "china",
    "taiwan",
    "sanciones",
    "aranceles",
    "tipos de interés",
    "inflación",
    "recesión",
    "petróleo",
    "crudo",
    "estrecho de hormuz",
    "oriente medio",
    "regulación",
]


SPECIAL_TOPICS = {
    "XOM": [
        "oil", "crude", "brent", "wti", "opec", "iran",
        "hormuz", "middle east", "energy", "sanctions",
        "production", "refinery",
    ],

    "REP.MC": [
        "oil", "crude", "brent", "wti", "opec",
        "iran", "hormuz", "energy",
    ],

    "LLY": [
        "weight loss", "obesity", "diabetes", "fda",
        "drug approval", "clinical trial", "clinical trials",
    ],

    "NVDA": [
        "ai", "chips", "semiconductor", "china",
        "export restrictions", "export controls", "data center",
    ],

    "AMD": [
        "ai", "chips", "semiconductor", "china",
        "export restrictions", "export controls",
    ],

    "MU": [
        "memory", "dram", "nand", "semiconductor",
        "chips", "ai", "china",
    ],

    "INTC": [
        "semiconductor", "chips", "china",
        "foundry", "export restrictions",
    ],

    "AMAT": [
        "semiconductor", "chips", "china",
        "export restrictions", "equipment",
    ],

    "AVGO": [
        "ai", "chips", "semiconductor", "data center",
    ],

    "QCOM": [
        "chips", "semiconductor", "china",
        "smartphone", "export restrictions",
    ],

    "TSLA": [
        "ev", "electric vehicle", "china", "tariffs",
        "autonomous", "robotaxi", "regulation", "recall",
    ],

    "ASML.AS": [
        "semiconductor", "chips", "lithography",
        "china", "export restrictions", "export controls",
    ],

    "AIR.PA": [
        "airbus", "aircraft", "aviation", "defense",
        "orders", "supply chain",
    ],
}


# ============================================================
# 4. UTILIDADES
# ============================================================

def is_etf(ticker):
    return ticker in ETF_TICKERS


def is_eur_asset(ticker):
    """
    Estos instrumentos cotizan en EUR.
    """
    if is_etf(ticker):
        return True

    return ticker.endswith((
        ".MC",
        ".DE",
        ".PA",
        ".AS",
        ".MI",
    ))


def currency_for(ticker):
    return "EUR" if is_eur_asset(ticker) else "USD"


def currency_symbol(ticker):
    return "€" if currency_for(ticker) == "EUR" else "$"


def display_ticker(ticker):
    if is_etf(ticker):
        return ETF_INFO[ticker]["ticker"]

    return ticker.replace(".MC", "").replace(
        ".DE", ""
    ).replace(
        ".PA", ""
    ).replace(
        ".AS", ""
    ).replace(
        ".MI", ""
    )


def display_name(ticker):
    if is_etf(ticker):
        return ETF_INFO[ticker]["name"]

    return COMPANY_NAMES.get(ticker, ticker)


def safe_float(value, default=None):
    try:
        if value is None:
            return default

        if isinstance(value, (pd.Series, pd.DataFrame)):
            value = value.iloc[-1]

        value = float(value)

        if not np.isfinite(value):
            return default

        return value

    except Exception:
        return default


def fmt_number(value, decimals=2):
    value = safe_float(value)

    if value is None:
        return "N/D"

    text = f"{value:,.{decimals}f}"

    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_price(ticker, value):
    symbol = currency_symbol(ticker)

    return f"{symbol}{fmt_number(value)}"


def fmt_eur(value):
    return f"{fmt_number(value)} €"


def normalize_text(text):
    if not text:
        return ""

    text = str(text).lower()

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# 5. RSI
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
# 6. DESCARGA DE DATOS
# ============================================================

def download_data(ticker, period=PERIOD, interval=INTERVAL):

    for attempt in range(3):

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
                time.sleep(1)
                continue

            # Manejo de MultiIndex de yfinance
            if isinstance(df.columns, pd.MultiIndex):

                try:
                    df.columns = df.columns.get_level_values(0)
                except Exception:
                    pass

            required = [
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
            ]

            missing = [
                col for col in required
                if col not in df.columns
            ]

            if missing:
                return None

            df = df[required].copy()

            for col in required:
                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce",
                )

            df = df.dropna()

            if len(df) < 210:
                return None

            return df

        except Exception:

            time.sleep(1)

    return None


# ============================================================
# 7. ANÁLISIS TÉCNICO
# ============================================================

def analyze_ticker(ticker):

    result = {
        "ticker": ticker,
        "name": display_name(ticker),
        "valid_data": False,
        "error": None,
    }

    df = download_data(ticker)

    if df is None or len(df) < 210:

        result["error"] = "Datos insuficientes"

        return result

    try:

        df["SMA20"] = df["Close"].rolling(20).mean()
        df["SMA50"] = df["Close"].rolling(50).mean()
        df["SMA200"] = df["Close"].rolling(200).mean()
        df["RSI"] = calculate_rsi(df["Close"], 14)
        df["VOL20"] = df["Volume"].rolling(20).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]

        price = safe_float(last["Close"])
        open_price = safe_float(last["Open"])
        high = safe_float(last["High"])
        low = safe_float(last["Low"])

        previous_close = safe_float(prev["Close"])
        previous_high = safe_float(prev["High"])

        sma20 = safe_float(last["SMA20"])
        sma50 = safe_float(last["SMA50"])
        sma200 = safe_float(last["SMA200"])
        rsi = safe_float(last["RSI"])

        volume = safe_float(last["Volume"], 0)
        avg_volume = safe_float(last["VOL20"], 0)

        if any(
            value is None
            for value in [
                price,
                open_price,
                high,
                low,
                previous_close,
                previous_high,
                sma50,
                sma200,
                rsi,
            ]
        ):
            result["error"] = "Indicadores incompletos"
            return result

        if avg_volume is None or avg_volume <= 0:
            result["error"] = "Volumen no disponible"
            return result

        volume_ratio = volume / avg_volume

        avg_dollar_volume = (
            avg_volume * price
        )

        daily_move = (
            (price - previous_close)
            / previous_close
        )

        support = safe_float(
            df["Low"].tail(20).min()
        )

        if support is None or support <= 0:
            result["error"] = "Soporte no disponible"
            return result

        distance_support = (
            price - support
        ) / price

        rebound_distance = (
            low - support
        ) / support

        bullish_candle = price > open_price

        support_reaction = (
            rebound_distance <= MAX_REBOUND_DISTANCE
        )

        volume_confirmation = (
            volume_ratio >= MIN_VOLUME_CONFIRMATION
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

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        score = 0

        if price > sma200:
            score += 20

        if sma50 > sma200:
            score += 15

        if price > sma50:
            score += 10

        if rsi < 30:
            score += 25
        elif rsi <= 45:
            score += 20
        elif rsi <= 55:
            score += 8

        if volume_ratio >= 1.5:
            score += 15
        elif volume_ratio >= 1.15:
            score += 8

        if distance_support <= 0.03:
            score += 20
        elif distance_support <= 0.06:
            score += 10

        # Nunca mostrar más de 100.
        score = min(score, 100)

        # ----------------------------------------------------
        # STOP Y OBJETIVOS
        # ----------------------------------------------------

        stop = support * 0.98

        risk_per_share = price - stop

        if risk_per_share <= 0:
            target1 = None
            target2 = None
            reward_risk = 0
        else:
            target1 = price + (
                2 * risk_per_share
            )

            target2 = price + (
                3 * risk_per_share
            )

            reward_risk = (
                (target1 - price)
                / risk_per_share
            )

        # ----------------------------------------------------
        # FILTROS DE SEGURIDAD
        # ----------------------------------------------------

        liquidity_ok = (
            avg_dollar_volume
            >= MIN_AVG_DOLLAR_VOLUME
        )

        daily_move_ok = (
            abs(daily_move)
            <= MAX_DAILY_MOVE
        )

        support_ok = (
            distance_support
            <= MAX_SUPPORT_DISTANCE
        )

        result.update({

            "valid_data": True,

            "price": price,
            "open": open_price,
            "high": high,
            "low": low,
            "previous_close": previous_close,
            "previous_high": previous_high,

            "sma20": sma20,
            "sma50": sma50,
            "sma200": sma200,

            "rsi": rsi,

            "volume": volume,
            "avg_volume": avg_volume,
            "volume_ratio": volume_ratio,
            "avg_dollar_volume": avg_dollar_volume,

            "daily_move": daily_move,

            "support": support,
            "distance_support": distance_support,
            "rebound_distance": rebound_distance,

            "bullish_candle": bullish_candle,
            "support_reaction": support_reaction,
            "volume_confirmation": volume_confirmation,
            "close_above_previous_high":
                close_above_previous_high,
            "rebound_confirmed":
                rebound_confirmed,

            "score": score,

            "stop": stop,
            "risk_per_share": risk_per_share,
            "target1": target1,
            "target2": target2,
            "reward_risk": reward_risk,

            "liquidity_ok": liquidity_ok,
            "daily_move_ok": daily_move_ok,
            "support_ok": support_ok,

            "currency": currency_for(ticker),

            "news": [],
            "news_count": 0,
            "news_impact": "NO EVALUADO",
            "news_risk_topics": [],

            "earnings_blocked": False,
            "earnings_status": "NO EVALUADO",

            "eurusd": 1.0,

            "shares": 0,
            "capital_used_eur": 0,
            "risk_eur": 0,
            "max_risk_eur":
                CAPITAL_EUR * RISK_PER_TRADE,

        })

        return result

    except Exception as e:

        result["error"] = str(e)

        return result


# ============================================================
# 8. MERCADO
# ============================================================

def get_market_regime():

    df = download_data(
        MARKET_TICKER,
        MARKET_PERIOD,
        "1d",
    )

    if df is None or len(df) < 210:

        return {
            "favorable": False,
            "status": "NO DISPONIBLE",
            "price": None,
        }

    df["SMA50"] = df["Close"].rolling(50).mean()
    df["SMA200"] = df["Close"].rolling(200).mean()

    price = safe_float(df["Close"].iloc[-1])
    sma50 = safe_float(df["SMA50"].iloc[-1])
    sma200 = safe_float(df["SMA200"].iloc[-1])

    if None in [price, sma50, sma200]:

        return {
            "favorable": False,
            "status": "NO DISPONIBLE",
            "price": price,
        }

    favorable = (
        price > sma200
        and sma50 > sma200
    )

    return {
        "favorable": favorable,
        "status":
            "FAVORABLE"
            if favorable
            else "DESFAVORABLE",
        "price": price,
        "sma50": sma50,
        "sma200": sma200,
    }


# ============================================================
# 9. RESULTADOS
# ============================================================

def get_earnings_status(ticker):

    if is_etf(ticker):

        return {
            "blocked": False,
            "status": "ETF — no aplica",
            "date": None,
            "days": None,
        }

    try:

        stock = yf.Ticker(ticker)

        dates = stock.get_earnings_dates(
            limit=8
        )

        if dates is None or dates.empty:

            return {
                "blocked": False,
                "status": "No disponible",
                "date": None,
                "days": None,
            }

        now = datetime.now(timezone.utc)

        candidates = []

        for index in dates.index:

            try:

                if hasattr(index, "to_pydatetime"):
                    dt = index.to_pydatetime()
                else:
                    dt = pd.Timestamp(index).to_pydatetime()

                if dt.tzinfo is None:
                    dt = dt.replace(
                        tzinfo=timezone.utc
                    )
                else:
                    dt = dt.astimezone(
                        timezone.utc
                    )

                candidates.append(dt)

            except Exception:
                continue

        if not candidates:

            return {
                "blocked": False,
                "status": "No disponible",
                "date": None,
                "days": None,
            }

        future = [
            dt for dt in candidates
            if dt >= now - timedelta(days=1)
        ]

        if future:
            nearest = min(
                future,
                key=lambda x: abs(
                    (x - now).total_seconds()
                ),
            )
        else:
            nearest = min(
                candidates,
                key=lambda x: abs(
                    (x - now).total_seconds()
                ),
            )

        days = (
            nearest.date()
            - now.date()
        ).days

        blocked = (
            abs(days)
            <= EARNINGS_BLACKOUT_DAYS
        )

        if blocked:

            status = (
                f"RESULTADOS "
                f"{days:+d} días"
            )

        else:

            status = (
                f"Sin resultados "
                f"±{EARNINGS_BLACKOUT_DAYS} días"
            )

        return {
            "blocked": blocked,
            "status": status,
            "date": nearest,
            "days": days,
        }

    except Exception:

        return {
            "blocked": False,
            "status": "No disponible",
            "date": None,
            "days": None,
        }


# ============================================================
# 10. EUR/USD
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
            return 1.0

        if isinstance(df.columns, pd.MultiIndex):

            df.columns = df.columns.get_level_values(0)

        value = safe_float(
            df["Close"].dropna().iloc[-1]
        )

        if value and value > 0:

            return value

    except Exception:
        pass

    return 1.0


# ============================================================
# 11. POSICIÓN
# ============================================================

def calculate_position(
    ticker,
    entry,
    stop,
    eurusd,
):

    max_risk_eur = (
        CAPITAL_EUR
        * RISK_PER_TRADE
    )

    if entry is None or stop is None:
        return {
            "shares": 0,
            "capital_used_eur": 0,
            "risk_eur": 0,
            "max_risk_eur": max_risk_eur,
        }

    risk_per_share = entry - stop

    if risk_per_share <= 0:

        return {
            "shares": 0,
            "capital_used_eur": 0,
            "risk_eur": 0,
            "max_risk_eur": max_risk_eur,
        }

    # --------------------------------------------------------
    # EUROPA / ETF
    # --------------------------------------------------------

    if is_eur_asset(ticker):

        entry_eur = entry
        risk_share_eur = risk_per_share

    # --------------------------------------------------------
    # USA
    # --------------------------------------------------------

    else:

        if eurusd <= 0:
            eurusd = 1.0

        entry_eur = entry / eurusd
        risk_share_eur = (
            risk_per_share / eurusd
        )

    shares_risk = math.floor(
        max_risk_eur
        / risk_share_eur
    )

    shares_capital = math.floor(
        CAPITAL_EUR
        / entry_eur
    )

    shares = min(
        shares_risk,
        shares_capital,
    )

    capital_used_eur = (
        shares * entry_eur
    )

    risk_eur = (
        shares * risk_share_eur
    )

    return {
        "shares": shares,
        "capital_used_eur":
            capital_used_eur,
        "risk_eur":
            risk_eur,
        "max_risk_eur":
            max_risk_eur,
    }


# ============================================================
# 12. NOTICIAS
# ============================================================

def get_news(ticker):

    name = display_name(ticker)

    topics = SPECIAL_TOPICS.get(
        ticker,
        []
    )

    query_parts = [
        f'"{name}"',
        ticker,
    ]

    query_parts.extend(
        topics[:5]
    )

    query = " ".join(query_parts)

    url = (
        "https://news.google.com/rss/search?"
        f"q={quote(query)}"
        "&hl=en-US"
        "&gl=US"
        "&ceid=US:en"
    )

    try:

        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent":
                    "Mozilla/5.0"
            },
        )

        response.raise_for_status()

        root = ET.fromstring(
            response.content
        )

    except Exception:

        return []

    now = datetime.now(timezone.utc)

    items = []

    for item in root.findall(".//item"):

        title_el = item.find("title")
        link_el = item.find("link")
        date_el = item.find("pubDate")
        source_el = item.find("source")

        if title_el is None:
            continue

        title = (
            title_el.text or ""
        ).strip()

        link = (
            link_el.text or ""
        ).strip()
        if link_el is not None
        else ""

        date_text = (
            date_el.text or ""
        ).strip()
        if date_el is not None
        else ""

        source = (
            source_el.text or ""
        ).strip()
        if source_el is not None
        else ""

        published = None

        try:

            published = pd.to_datetime(
                date_text,
                utc=True,
            ).to_pydatetime()

        except Exception:
            pass

        if published is None:
            continue

        age_hours = (
            now - published
        ).total_seconds() / 3600

        if age_hours < 0:
            age_hours = 0

        if age_hours > NEWS_HOURS:
            continue

        items.append({
            "title": title,
            "link": link,
            "source": source,
            "published": published,
        })

    # --------------------------------------------------------
    # DEDUPLICACIÓN
    # --------------------------------------------------------

    unique = {}

    for item in items:

        key = normalize_text(
            item["title"]
        )

        key = re.sub(
            r"[^a-z0-9áéíóúüñ ]",
            "",
            key,
        )

        if key not in unique:
            unique[key] = item

    items = list(unique.values())

    items.sort(
        key=lambda x: x["published"],
        reverse=True,
    )

    return items[:MAX_NEWS]


# ============================================================
# 13. CLASIFICACIÓN DE NOTICIAS
# ============================================================

def classify_news(ticker):

    articles = get_news(ticker)

    if not articles:

        return {
            "articles": [],
            "count": 0,
            "impact": "SIN DATOS",
            "risk_topics": [],
            "positive_count": 0,
            "negative_count": 0,
            "risk_count": 0,
        }

    positive_count = 0
    negative_count = 0
    risk_count = 0

    risk_topics = []

    processed = []

    special_topics = SPECIAL_TOPICS.get(
        ticker,
        []
    )

    # Palabras especialmente negativas por sector.
    bearish_special = {

        "XOM": [
            "oil falls",
            "oil prices fall",
            "oil price falls",
            "crude falls",
            "crude prices fall",
            "brent falls",
            "opec increases production",
            "opec output increase",
            "hormuz reopening",
            "hormuz reopens",
        ],

        "REP.MC": [
            "oil falls",
            "crude falls",
            "brent falls",
            "opec increases production",
            "hormuz reopening",
        ],

        "LLY": [
            "fda rejection",
            "trial failure",
            "clinical trial failure",
            "adverse events",
            "safety concerns",
        ],

        "NVDA": [
            "china export restrictions",
            "export ban",
            "chip restrictions",
            "export controls",
            "sales restrictions",
        ],

        "AMD": [
            "china export restrictions",
            "export ban",
            "chip restrictions",
            "export controls",
        ],

        "MU": [
            "china export restrictions",
            "memory demand falls",
            "chip demand falls",
        ],

        "ASML.AS": [
            "china export restrictions",
            "export controls",
            "china ban",
        ],

        "TSLA": [
            "recall",
            "autonomous crash",
            "regulatory investigation",
            "china sales fall",
            "ev demand falls",
        ],
    }

    bearish_terms = bearish_special.get(
        ticker,
        [],
    )

    for article in articles:

        title = article["title"]

        text_lower = normalize_text(
            title
        )

        pos_hits = 0
        neg_hits = 0
        risk_hits = 0

        for word in POSITIVE_WORDS:

            if normalize_text(word) in text_lower:
                pos_hits += 1

        for word in NEGATIVE_WORDS:

            if normalize_text(word) in text_lower:
                neg_hits += 1

        for word in GENERAL_RISK_TERMS:

            if normalize_text(word) in text_lower:
                risk_hits += 1

                if word not in risk_topics:
                    risk_topics.append(word)

        for word in special_topics:

            if normalize_text(word) in text_lower:
                risk_hits += 1

                if word not in risk_topics:
                    risk_topics.append(word)

        # Riesgo especial por empresa.
        for word in bearish_terms:

            if normalize_text(word) in text_lower:
                neg_hits += 3

        positive_count += pos_hits
        negative_count += neg_hits
        risk_count += risk_hits

        processed.append({
            **article,
            "positive_hits": pos_hits,
            "negative_hits": neg_hits,
            "risk_hits": risk_hits,
        })

    # --------------------------------------------------------
    # CLASIFICACIÓN CONSERVADORA
    # --------------------------------------------------------

    if negative_count >= positive_count + 2:

        impact = "NEGATIVO"

    elif negative_count > positive_count:

        impact = "NEGATIVO"

    elif positive_count >= negative_count + 2:

        impact = "POSITIVO"

    elif positive_count > negative_count:

        impact = "POSITIVO"

    elif risk_count > 0:

        impact = "MIXTO / RIESGO"

    else:

        impact = "NEUTRO"

    return {
        "articles": processed,
        "count": len(processed),
        "impact": impact,
        "risk_topics": risk_topics[:10],
        "positive_count": positive_count,
        "negative_count": negative_count,
        "risk_count": risk_count,
    }


# ============================================================
# 14. FILTROS
# ============================================================

def evaluate_filters(
    result,
    market,
):

    primary = {}
    secondary = {}
    safety = {}

    # --------------------------------------------------------
    # PRINCIPALES
    # --------------------------------------------------------

    primary["Score >= 75"] = (
        result["score"] >= MIN_SCORE
    )

    primary["RSI <= 45"] = (
        result["rsi"] <= MAX_RSI
    )

    primary["Precio <= 3% soporte"] = (
        result["distance_support"]
        <= MAX_SUPPORT_DISTANCE
    )

    primary["Noticias no negativas"] = (
        result["news_impact"]
        in ["POSITIVO", "NEUTRO", "MIXTO / RIESGO"]
    )

    # Si no hay datos de noticias, NO se permite entrada.
    if result["news_count"] == 0:
        primary["Noticias no negativas"] = False

    primary["R/R >= 2:1"] = (
        result["reward_risk"] >= 2
    )

    # --------------------------------------------------------
    # SECUNDARIOS
    # --------------------------------------------------------

    secondary["Rebote confirmado"] = (
        result["rebound_confirmed"]
    )

    secondary["Volumen >= 1.15x"] = (
        result["volume_ratio"]
        >= MIN_VOLUME_CONFIRMATION
    )

    secondary["Cierre > máximo vela anterior"] = (
        result["close_above_previous_high"]
    )

    secondary["S&P 500 favorable"] = (
        market["favorable"]
    )

    secondary["Sin resultados +/- 3 días"] = (
        not result["earnings_blocked"]
    )

    # --------------------------------------------------------
    # SEGURIDAD
    # --------------------------------------------------------

    safety["Liquidez suficiente"] = (
        result["liquidity_ok"]
    )

    safety["Movimiento diario <= 8%"] = (
        result["daily_move_ok"]
    )

    safety["Datos válidos"] = (
        result["valid_data"]
    )

    safety["Resultados no bloqueados"] = (
        not result["earnings_blocked"]
    )

    # Noticias sin datos = bloqueo absoluto.
    safety["Noticias disponibles"] = (
        result["news_count"] > 0
    )

    # Noticias negativas = bloqueo absoluto.
    safety["Sin noticia negativa"] = (
        result["news_impact"]
        != "NEGATIVO"
    )

    # Riesgo de mercado.
    safety["Mercado favorable"] = (
        market["favorable"]
    )

    result["primary_checks"] = primary
    result["secondary_checks"] = secondary
    result["safety_checks"] = safety

    primary_pass = sum(
        primary.values()
    )

    secondary_pass = sum(
        secondary.values()
    )

    safety_pass = sum(
        safety.values()
    )

    result["primary_pass"] = primary_pass
    result["secondary_pass"] = secondary_pass
    result["safety_pass"] = safety_pass

    # --------------------------------------------------------
    # CONFIRMACIÓN
    # --------------------------------------------------------

    all_primary = (
        primary_pass == len(primary)
    )

    all_secondary = (
        secondary_pass == len(secondary)
    )

    all_safety = (
        safety_pass == len(safety)
    )

    confirmed = (
        all_primary
        and all_secondary
        and all_safety
    )

    # Noticias negativas SIEMPRE bloquean.
    if result["news_impact"] == "NEGATIVO":
        confirmed = False

    # Datos inexistentes SIEMPRE bloquean.
    if result["news_count"] == 0:
        confirmed = False

    # Sin acciones posibles, no hay señal.
    if result.get("shares", 0) < 1:
        confirmed = False

    result["confirmed"] = confirmed

    # Watchlist interna.
    # No se envía a Telegram por defecto.
    watch = (
        all_primary
        and not confirmed
        and secondary_pass >= 4
        and all_safety
    )

    if result["news_impact"] == "NEGATIVO":
        watch = False

    result["watch"] = watch

    if confirmed:
        result["classification"] = "CONFIRMADA"
    elif watch:
        result["classification"] = "VIGILAR"
    else:
        result["classification"] = "NO ENTRA"

    # --------------------------------------------------------
    # SEÑAL FINAL
    # --------------------------------------------------------

    if result["news_impact"] == "NEGATIVO":

        result["final_signal"] = (
            "SEÑAL FINAL: "
            "PRECAUCIÓN — esperar"
        )

    elif confirmed:

        result["final_signal"] = (
            "SEÑAL FINAL: "
            "ENTRADA CONFIRMADA"
        )

    elif watch:

        result["final_signal"] = (
            "SEÑAL FINAL: "
            "VIGILAR — todavía no entrar"
        )

    else:

        result["final_signal"] = (
            "SEÑAL FINAL: "
            "NO ENTRAR"
        )

    return result


# ============================================================
# 15. DIAGNÓSTICO
# ============================================================

def diagnostic_report(
    result,
    market,
):

    ticker = result["ticker"]

    lines = []

    lines.append(
        f"🔎 {display_ticker(ticker)} — "
        f"{result['name']}"
    )

    if not result["valid_data"]:

        lines.append("")
        lines.append(
            f"❌ {result['error']}"
        )
        lines.append(
            "⚪ NO ENTRA"
        )

        return "\n".join(lines)

    lines.append("")

    lines.append(
        f"💵 Precio: "
        f"{fmt_price(ticker, result['price'])}"
    )

    lines.append(
        f"📊 Score: "
        f"{result['score']}/100"
    )

    lines.append(
        f"📉 RSI: "
        f"{fmt_number(result['rsi'], 1)}"
    )

    lines.append(
        f"📍 Soporte: "
        f"{fmt_price(ticker, result['support'])}"
    )

    lines.append(
        f"📐 Distancia soporte: "
        f"{fmt_number(result['distance_support'] * 100, 2)}%"
    )

    lines.append(
        f"📈 Volumen: "
        f"{fmt_number(result['volume_ratio'], 2)}x"
    )

    lines.append(
        f"⚖️ R/R: "
        f"{fmt_number(result['reward_risk'], 1)}:1"
    )

    lines.append(
        f"💧 Liquidez media: "
        f"{fmt_eur(result['avg_dollar_volume'] / result['eurusd'])}"
        if result.get("eurusd", 1) > 0
        else
        f"💧 Liquidez media: "
        f"{fmt_number(result['avg_dollar_volume'])}"
    )

    lines.append(
        f"📰 Noticias analizadas: "
        f"{result['news_count']}"
    )

    lines.append(
        f"📰 Impacto: "
        f"{result['news_impact']}"
    )

    if result["news_risk_topics"]:

        lines.append(
            "⚠️ Riesgos detectados: "
            + ", ".join(
                result["news_risk_topics"][:6]
            )
        )

    lines.append("")

    lines.append(
        f"🟢 PRINCIPALES: "
        f"{result['primary_pass']}/5"
    )

    for name, passed in result[
        "primary_checks"
    ].items():

        lines.append(
            f"{'✅' if passed else '❌'} {name}"
        )

    lines.append("")

    lines.append(
        f"🟡 SECUNDARIOS: "
        f"{result['secondary_pass']}/5"
    )

    for name, passed in result[
        "secondary_checks"
    ].items():

        lines.append(
            f"{'✅' if passed else '❌'} {name}"
        )

    lines.append("")

    lines.append(
        f"🛡️ SEGURIDAD: "
        f"{result['safety_pass']}/"
        f"{len(result['safety_checks'])}"
    )

    for name, passed in result[
        "safety_checks"
    ].items():

        lines.append(
            f"{'✅' if passed else '❌'} {name}"
        )

    lines.append("")

    if result["classification"] == "CONFIRMADA":

        lines.append(
            "💎 CHOLLO CONFIRMADO"
        )

    elif result["classification"] == "VIGILAR":

        lines.append(
            "🟡 CANDIDATA A VIGILAR"
        )

    else:

        lines.append(
            "⚪ NO ENTRA"
        )

    # Principales que falla
    primary_failures = [
        name
        for name, passed
        in result["primary_checks"].items()
        if not passed
    ]

    if primary_failures:

        lines.append("")
        lines.append(
            "❌ PRINCIPALES QUE FALLA:"
        )

        for failure in primary_failures:

            lines.append(
                f"• {failure}"
            )

    # Secundarios que falla
    secondary_failures = [
        name
        for name, passed
        in result["secondary_checks"].items()
        if not passed
    ]

    if secondary_failures:

        lines.append("")
        lines.append(
            "⚠️ SECUNDARIOS QUE FALLA:"
        )

        for failure in secondary_failures:

            lines.append(
                f"• {failure}"
            )

    lines.append("")
    lines.append(
        f"🚨 {result['final_signal']}"
    )

    return "\n".join(lines)


# ============================================================
# 16. MENSAJE DE SEÑAL CONFIRMADA
# ============================================================

def build_signal_message(result):

    ticker = result["ticker"]

    lines = []

    lines.append(
        "💎💎💎 "
        "CHOLLO CONFIRMADO"
    )

    lines.append("")

    lines.append(
        f"🏢 {result['name']}"
    )

    lines.append(
        f"📌 {display_ticker(ticker)}"
    )

    lines.append("")

    lines.append(
        f"💵 Entrada: "
        f"{fmt_price(ticker, result['price'])}"
    )

    lines.append(
        f"🛑 Stop: "
        f"{fmt_price(ticker, result['stop'])}"
    )

    lines.append(
        f"🎯 Objetivo 1: "
        f"{fmt_price(ticker, result['target1'])}"
    )

    lines.append(
        f"🎯 Objetivo 2: "
        f"{fmt_price(ticker, result['target2'])}"
    )

    lines.append("")

    lines.append(
        f"📊 Score: "
        f"{result['score']}/100"
    )

    lines.append(
        f"📉 RSI: "
        f"{fmt_number(result['rsi'], 1)}"
    )

    lines.append(
        f"📍 Soporte: "
        f"{fmt_price(ticker, result['support'])}"
    )

    lines.append(
        f"📐 Distancia soporte: "
        f"{fmt_number(result['distance_support'] * 100, 2)}%"
    )

    lines.append(
        f"📈 Volumen: "
        f"{fmt_number(result['volume_ratio'], 2)}x"
    )

    lines.append(
        f"⚖️ R/R: "
        f"{fmt_number(result['reward_risk'], 1)}:1"
    )

    lines.append("")

    lines.append(
        f"💰 Capital utilizado: "
        f"{fmt_eur(result['capital_used_eur'])}"
    )

    lines.append(
        f"📦 Acciones: "
        f"{result['shares']}"
    )

    lines.append(
        f"🔴 Riesgo estimado: "
        f"{fmt_eur(result['risk_eur'])}"
    )

    lines.append(
        f"🔴 Riesgo máximo permitido: "
        f"{fmt_eur(result['max_risk_eur'])}"
    )

    lines.append("")

    lines.append(
        f"📰 Noticias analizadas: "
        f"{result['news_count']}"
    )

    lines.append(
        f"📰 Impacto: "
        f"{result['news_impact']}"
    )

    if result["news_risk_topics"]:

        lines.append(
            "⚠️ Temas de riesgo: "
            + ", ".join(
                result["news_risk_topics"][:6]
            )
        )

    lines.append("")

    lines.append(
        f"🌎 S&P 500: "
        f"{'FAVORABLE' if result['market_favorable'] else 'DESFAVORABLE'}"
    )

    lines.append(
        f"📅 Resultados: "
        f"{result['earnings_status']}"
    )

    lines.append("")

    # Mostrar una noticia relevante.
    articles = result.get(
        "news",
        [],
    )

    if articles:

        lines.append(
            "📰 NOTICIA RELEVANTE:"
        )

        featured = articles[0]

        lines.append(
            f"• {featured['title']}"
        )

        if featured.get("source"):

            lines.append(
                f"Fuente: "
                f"{featured['source']}"
            )

        lines.append("")

    lines.append(
        "🚨 SEÑAL FINAL: "
        "ENTRADA CONFIRMADA"
    )

    lines.append(
        "⚠️ Ejecutar siempre respetando "
        "el stop indicado."
    )

    return "\n".join(lines)


# ============================================================
# 17. TELEGRAM
# ============================================================

def send_telegram(message):

    if not TELEGRAM_BOT_TOKEN:
        print(
            "⚠️ TELEGRAM_BOT_TOKEN no configurado."
        )
        return False

    if not TELEGRAM_CHAT_ID:
        print(
            "⚠️ TELEGRAM_CHAT_ID no configurado."
        )
        return False

    # Telegram admite 4096 caracteres.
    # Dejamos margen de seguridad.
    if len(message) > 3900:

        message = (
            message[:3850]
            + "\n\n[Mensaje truncado]"
        )

    url = (
        "https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}"
        "/sendMessage"
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

        if response.ok:
            return True

        print(
            "❌ Error Telegram:",
            response.text[:500],
        )

        return False

    except Exception as e:

        print(
            "❌ Error enviando Telegram:",
            e,
        )

        return False


# ============================================================
# 18. RESUMEN FINAL
# ============================================================

def build_summary(
    results,
    market,
):

    confirmed = [
        r for r in results
        if r["classification"]
        == "CONFIRMADA"
    ]

    watch = [
        r for r in results
        if r["classification"]
        == "VIGILAR"
    ]

    rejected = [
        r for r in results
        if r["classification"]
        == "NO ENTRA"
    ]

    lines = []

    lines.append(
        "📊 ESCÁNER DE CHOLLOS PARA DEGIRO"
    )

    lines.append("")

    lines.append(
        f"💎 CHOLLOS CONFIRMADOS: "
        f"{len(confirmed)}"
    )

    lines.append(
        f"🟡 CANDIDATAS A VIGILAR: "
        f"{len(watch)}"
    )

    lines.append(
        f"⚪ NO ENTRAN: "
        f"{len(rejected)}"
    )

    lines.append("")

    lines.append(
        f"🔎 Instrumentos analizados: "
        f"{len(results)}"
    )

    lines.append(
        f"💰 Capital: "
        f"{fmt_eur(CAPITAL_EUR)}"
    )

    lines.append(
        f"🔴 Riesgo máximo: "
        f"{fmt_eur(CAPITAL_EUR * RISK_PER_TRADE)}"
    )

    lines.append("")

    lines.append(
        "🌎 S&P 500: "
        f"{market['status']}"
    )

    lines.append("")

    lines.append(
        "🛡️ SOLO SE ENVÍAN ALERTAS "
        "DE ENTRADA CONFIRMADA"
    )

    lines.append("")

    if confirmed:

        lines.append(
            "💎 SEÑALES CONFIRMADAS:"
        )

        for result in confirmed:

            lines.append(
                f"• {display_ticker(result['ticker'])} "
                f"— {result['name']} "
                f"— Score {result['score']}/100"
            )

    else:

        lines.append(
            "💎 SEÑALES CONFIRMADAS:"
        )

        lines.append(
            "• Ninguna"
        )

    lines.append("")

    if watch:

        lines.append(
            f"🟡 {len(watch)} "
            "candidatas cumplen los principales "
            "pero no reciben alerta."
        )

    lines.append("")

    now = datetime.now()

    lines.append(
        f"📅 {now.strftime('%d/%m/%Y %H:%M')}"
    )

    return "\n".join(lines)


# ============================================================
# 19. MOTIVOS ESTADÍSTICOS DE DESCARTE
# ============================================================

def build_rejection_statistics(results):

    counters = {}

    for result in results:

        if not result["valid_data"]:

            key = "Datos insuficientes"
            counters[key] = (
                counters.get(key, 0) + 1
            )

            continue

        for name, passed in result[
            "primary_checks"
        ].items():

            if not passed:

                counters[name] = (
                    counters.get(name, 0)
                    + 1
                )

        for name, passed in result[
            "secondary_checks"
        ].items():

            if not passed:

                counters[name] = (
                    counters.get(name, 0)
                    + 1
                )

        for name, passed in result[
            "safety_checks"
        ].items():

            if not passed:

                counters[name] = (
                    counters.get(name, 0)
                    + 1
                )

    return counters


# ============================================================
# 20. MAIN
# ============================================================

def main():

    print("")
    print(
        "=================================================="
    )
    print(
        "📊 ESCÁNER DE CHOLLOS PARA DEGIRO"
    )
    print(
        "=================================================="
    )
    print("")

    print(
        f"💰 Capital: {fmt_eur(CAPITAL_EUR)}"
    )

    print(
        f"🔴 Riesgo máximo: "
        f"{fmt_eur(CAPITAL_EUR * RISK_PER_TRADE)}"
    )

    print(
        f"🔎 Instrumentos: {len(TICKERS)}"
    )

    print("")

    # --------------------------------------------------------
    # MERCADO
    # --------------------------------------------------------

    print(
        "🌎 Analizando S&P 500..."
    )

    market = get_market_regime()

    print(
        f"🌎 S&P 500: "
        f"{market['status']}"
    )

    # --------------------------------------------------------
    # EURUSD
    # --------------------------------------------------------

    print(
        "💱 Obteniendo EUR/USD..."
    )

    eurusd = get_eurusd()

    print(
        f"💱 EUR/USD: "
        f"{fmt_number(eurusd, 4)}"
    )

    print("")

    # --------------------------------------------------------
    # ANÁLISIS DE TODOS
    # --------------------------------------------------------

    results = []

    for index, ticker in enumerate(
        TICKERS,
        start=1,
    ):

        print(
            f"[{index}/{len(TICKERS)}] "
            f"Analizando {ticker}..."
        )

        result = analyze_ticker(
            ticker
        )

        if not result["valid_data"]:

            results.append(result)

            continue

        result["eurusd"] = eurusd

        # ----------------------------------------------------
        # NOTICIAS
        #
        # Solo necesitamos noticias para instrumentos
        # que tienen posibilidades reales de superar el
        # Score mínimo.
        #
        # Si no llegan al Score, ya quedan descartados,
        # pero siguen apareciendo en el diagnóstico.
        # ----------------------------------------------------

        if result["score"] >= MIN_SCORE:

            print(
                f"   📰 Analizando noticias..."
            )

            news_data = classify_news(
                ticker
            )

            result["news"] = (
                news_data["articles"]
            )

            result["news_count"] = (
                news_data["count"]
            )

            result["news_impact"] = (
                news_data["impact"]
            )

            result["news_risk_topics"] = (
                news_data["risk_topics"]
            )

            # ----------------------------------------------
            # RESULTADOS
            # ----------------------------------------------

            print(
                f"   📅 Comprobando resultados..."
            )

            earnings = get_earnings_status(
                ticker
            )

            result["earnings_blocked"] = (
                earnings["blocked"]
            )

            result["earnings_status"] = (
                earnings["status"]
            )

        else:

            result["news"] = []
            result["news_count"] = 0
            result["news_impact"] = (
                "NO EVALUADO — score insuficiente"
            )

            result["earnings_blocked"] = False
            result["earnings_status"] = (
                "NO EVALUADO — score insuficiente"
            )

        # ----------------------------------------------------
        # POSICIÓN
        # ----------------------------------------------------

        position = calculate_position(
            ticker,
            result.get("price"),
            result.get("stop"),
            eurusd,
        )

        result.update(position)

        # ----------------------------------------------------
        # FILTROS
        # ----------------------------------------------------

        # El mercado se añade al resultado.
        result["market_favorable"] = (
            market["favorable"]
        )

        evaluate_filters(
            result,
            market,
        )

        results.append(result)

    # --------------------------------------------------------
    # DIAGNÓSTICO LOCAL
    # --------------------------------------------------------

    print("")
    print(
        "=================================================="
    )
    print(
        "🔎 DIAGNÓSTICO DETALLADO"
    )
    print(
        "=================================================="
    )
    print("")

    for result in results:

        print(
            diagnostic_report(
                result,
                market,
            )
        )

        print("")
        print(
            "--------------------------------------------------"
        )
        print("")

    # --------------------------------------------------------
    # RESUMEN
    # --------------------------------------------------------

    summary = build_summary(
        results,
        market,
    )

    print(summary)

    # --------------------------------------------------------
    # ESTADÍSTICAS
    # --------------------------------------------------------

    stats = build_rejection_statistics(
        results
    )

    print("")
    print(
        "📊 PRINCIPALES MOTIVOS DE DESCARTE:"
    )

    sorted_stats = sorted(
        stats.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    for reason, count in sorted_stats[:15]:

        print(
            f"• {reason}: {count}"
        )

    # --------------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------------

    print("")
    print(
        "📲 Preparando alertas Telegram..."
    )

    confirmed = [
        r for r in results
        if r["classification"]
        == "CONFIRMADA"
    ]

    # --------------------------------------------------------
    # SOLO CONFIRMADAS
    # --------------------------------------------------------

    if confirmed:

        for result in confirmed:

            message = build_signal_message(
                result
            )

            print(
                f"📲 Enviando señal: "
                f"{display_ticker(result['ticker'])}"
            )

            send_telegram(
                message
            )

            time.sleep(1)

    else:

        print(
            "ℹ️ No hay ninguna entrada "
            "confirmada. No se envía alerta de compra."
        )

    # --------------------------------------------------------
    # RESUMEN
    #
    # Se envía aunque no haya señales para que puedas
    # comprobar que el bot sigue funcionando.
    # --------------------------------------------------------

    send_telegram(
        summary
    )

    print("")
    print(
        "=================================================="
    )
    print(
        "✅ ESCÁNER FINALIZADO"
    )
    print(
        "=================================================="
    )


# ============================================================
# 21. EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    main()
