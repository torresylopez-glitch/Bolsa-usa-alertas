import os
import json
import math
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import yfinance as yf


# ============================================================
# CONFIGURACIÓN
# ============================================================

START_DATE = "2025-01-01"

WIN_THRESHOLD = 0.10          # +10%
FORWARD_DAYS = 20              # ventana para comprobar subida
EVENT_SEPARATION_DAYS = 20     # evita contar el mismo movimiento varias veces

MIN_ANALOGS = 5
MIN_SIMILARITY = 0.62

MAX_DAILY_ALERTS = 4
MAX_ANALOGS_FOR_FORECAST = 30

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

STATE_FILE = Path("alert_state.json")

# Zona horaria para determinar qué significa "hoy"
LOCAL_TZ = ZoneInfo("Europe/Madrid")


# ============================================================
# UNIVERSO DE 49 VALORES
# ============================================================

TICKERS = [
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

    # ETFs
    "SXR8.DE", "SXRV.DE", "ZPDF.DE",
]


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
    "ISP.MI": "Intesa Sanpaolo",

    "SXR8.DE": "iShares Core S&P 500 UCITS ETF",
    "SXRV.DE": "iShares NASDAQ 100 UCITS ETF",
    "ZPDF.DE": "SPDR S&P U.S. Financials Select Sector UCITS ETF",
}


MARKET_TICKERS = [
    "^GSPC",
    "^IXIC",
    "^DJI",
    "^VIX",
]


# ============================================================
# UTILIDADES
# ============================================================

def safe_float(value):
    try:
        value = float(value)
        if math.isfinite(value):
            return value
    except Exception:
        pass
    return np.nan


def fmt_price(value):
    return f"{value:.3f}"


def fmt_percent(value):
    return f"{value * 100:.1f}%"


# ============================================================
# ESTADO DE ALERTAS
# ============================================================

def load_state():
    """
    Lee el estado persistente.

    Formato:

    {
        "date": "2026-09-24",
        "sent_tickers": ["BBVA.MC", "ISP.MI"],
        "sent_at": {
            "BBVA.MC": "...",
            "ISP.MI": "..."
        }
    }
    """

    if not STATE_FILE.exists():
        return {
            "date": "",
            "sent_tickers": [],
            "sent_at": {}
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        if not isinstance(state, dict):
            raise ValueError("Estado inválido")

    except Exception:
        return {
            "date": "",
            "sent_tickers": [],
            "sent_at": {}
        }

    state.setdefault("date", "")
    state.setdefault("sent_tickers", [])
    state.setdefault("sent_at", {})

    return state


def save_state(state):
    """
    Guarda el estado de forma segura.
    """

    temp_file = Path("alert_state.tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            state,
            f,
            indent=2,
            ensure_ascii=False
        )

    temp_file.replace(STATE_FILE)


def prepare_today_state(state):
    """
    Si ha cambiado el día, se eliminan los tickers enviados
    del día anterior.

    El histórico permanece en el repositorio.
    """

    today = datetime.now(LOCAL_TZ).date().isoformat()

    if state.get("date") != today:
        state["date"] = today
        state["sent_tickers"] = []
        state["sent_at"] = {}

    return state


def ticker_already_sent_today(state, ticker):
    return ticker in set(state.get("sent_tickers", []))


def register_sent_ticker(state, ticker):
    if ticker not in state["sent_tickers"]:
        state["sent_tickers"].append(ticker)

    state["sent_at"][ticker] = datetime.now(
        LOCAL_TZ
    ).isoformat()


# ============================================================
# DESCARGA DE DATOS
# ============================================================

def download_ticker(ticker):
    try:
        df = yf.download(
            ticker,
            start=START_DATE,
            end=datetime.now(LOCAL_TZ).date().isoformat(),
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False
        )

        if df is None or df.empty:
            return None

        # yfinance puede devolver MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            try:
                df.columns = df.columns.get_level_values(0)
            except Exception:
                return None

        required = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        for col in required:
            if col not in df.columns:
                return None

        df = df[required].copy()

        for col in required:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

        df.dropna(subset=["Close", "High", "Low"], inplace=True)

        if len(df) < 210:
            return None

        return df

    except Exception as e:
        print(f"[ERROR DATOS] {ticker}: {e}")
        return None


# ============================================================
# INDICADORES
# ============================================================

def calculate_rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(
        period,
        min_periods=period
    ).mean()

    avg_loss = loss.rolling(
        period,
        min_periods=period
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_atr(df, period=14):
    prev_close = df["Close"].shift(1)

    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - prev_close).abs()
    tr3 = (df["Low"] - prev_close).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    return true_range.rolling(
        period,
        min_periods=period
    ).mean()


# ============================================================
# FEATURES
# ============================================================

def build_features(df):
    x = df.copy()

    close = x["Close"]
    high = x["High"]
    low = x["Low"]
    volume = x["Volume"]

    # Medias
    x["SMA20"] = close.rolling(20).mean()
    x["SMA50"] = close.rolling(50).mean()
    x["SMA100"] = close.rolling(100).mean()
    x["SMA200"] = close.rolling(200).mean()

    # RSI
    x["RSI14"] = calculate_rsi(close)

    # ATR
    x["ATR14"] = calculate_atr(x)
    x["ATR_PCT"] = x["ATR14"] / close

    # Momentum
    for n in [1, 3, 5, 10, 20, 40, 60]:
        x[f"RET{n}"] = close.pct_change(n)

    # Precio frente a medias
    x["PRICE_SMA20"] = close / x["SMA20"] - 1
    x["PRICE_SMA50"] = close / x["SMA50"] - 1
    x["PRICE_SMA100"] = close / x["SMA100"] - 1
    x["PRICE_SMA200"] = close / x["SMA200"] - 1

    # Relaciones de medias
    x["SMA20_SMA50"] = x["SMA20"] / x["SMA50"] - 1
    x["SMA50_SMA200"] = x["SMA50"] / x["SMA200"] - 1

    # Pendientes
    x["SMA20_SLOPE"] = x["SMA20"].pct_change(10)
    x["SMA50_SLOPE"] = x["SMA50"].pct_change(20)
    x["SMA200_SLOPE"] = x["SMA200"].pct_change(40)

    # Volumen
    x["VOL5"] = volume.rolling(5).mean()
    x["VOL20"] = volume.rolling(20).mean()

    x["VOL_RATIO_5_20"] = (
        x["VOL5"] /
        x["VOL20"].replace(0, np.nan)
    )

    # Volatilidad
    x["VOLATILITY20"] = (
        close.pct_change()
        .rolling(20)
        .std()
    )

    x["VOLATILITY60"] = (
        close.pct_change()
        .rolling(60)
        .std()
    )

    # Máximos y mínimos
    x["HIGH20"] = high.rolling(20).max()
    x["HIGH60"] = high.rolling(60).max()

    x["LOW20"] = low.rolling(20).min()
    x["LOW60"] = low.rolling(60).min()

    x["DIST_HIGH20"] = close / x["HIGH20"] - 1
    x["DIST_HIGH60"] = close / x["HIGH60"] - 1

    x["DIST_LOW20"] = close / x["LOW20"] - 1
    x["DIST_LOW60"] = close / x["LOW60"] - 1

    # Breakouts
    previous_high20 = x["HIGH20"].shift(1)
    previous_high60 = x["HIGH60"].shift(1)

    x["BREAKOUT20"] = close / previous_high20 - 1
    x["BREAKOUT60"] = close / previous_high60 - 1

    # Posición dentro del rango
    range20 = (
        x["HIGH20"] -
        x["LOW20"]
    ).replace(0, np.nan)

    x["RANGE_POSITION20"] = (
        close - x["LOW20"]
    ) / range20

    # Drawdown / recuperación
    rolling_high60 = close.rolling(60).max()

    x["DRAWDOWN60"] = (
        close / rolling_high60 - 1
    )

    rolling_low60 = close.rolling(60).min()

    x["RECOVERY60"] = (
        close / rolling_low60 - 1
    )

    return x


# ============================================================
# DATOS DEL MERCADO
# ============================================================

def build_market_features():
    market = {}

    for ticker in MARKET_TICKERS:
        df = download_ticker(ticker)

        if df is None:
            continue

        f = build_features(df)

        prefix = ticker.replace("^", "MKT_")

        market[f"{prefix}_RET5"] = f["RET5"]
        market[f"{prefix}_RET20"] = f["RET20"]
        market[f"{prefix}_PRICE_SMA50"] = f["PRICE_SMA50"]
        market[f"{prefix}_PRICE_SMA200"] = f["PRICE_SMA200"]

    if not market:
        return pd.DataFrame()

    result = pd.DataFrame(market)

    return result


# ============================================================
# MOVIMIENTO FUTURO
# ============================================================

def future_max_return(close, position, forward_days):
    end = min(
        position + forward_days,
        len(close) - 1
    )

    if end <= position:
        return np.nan

    current = close.iloc[position]

    future = close.iloc[
        position + 1:
        end + 1
    ]

    if current <= 0:
        return np.nan

    return (
        future.max() / current
    ) - 1


# ============================================================
# DETECCIÓN DE MOVIMIENTOS GANADORES
# ============================================================

def find_events(features):
    close = features["Close"]

    candidates = []

    for i in range(len(features)):
        future_return = future_max_return(
            close,
            i,
            FORWARD_DAYS
        )

        if pd.notna(future_return):
            if future_return >= WIN_THRESHOLD:
                candidates.append({
                    "position": i,
                    "date": features.index[i],
                    "future_return": future_return
                })

    if not candidates:
        return []

    selected = []

    last_position = -10_000

    for event in candidates:

        if (
            event["position"] -
            last_position
            >= EVENT_SEPARATION_DAYS
        ):
            selected.append(event)
            last_position = event["position"]

    return selected


# ============================================================
# VARIABLES UTILIZADAS PARA COMPARAR PATRONES
# ============================================================

FEATURE_COLUMNS = [
    "RSI14",
    "ATR_PCT",

    "RET1",
    "RET3",
    "RET5",
    "RET10",
    "RET20",
    "RET40",
    "RET60",

    "PRICE_SMA20",
    "PRICE_SMA50",
    "PRICE_SMA100",
    "PRICE_SMA200",

    "SMA20_SMA50",
    "SMA50_SMA200",

    "SMA20_SLOPE",
    "SMA50_SLOPE",
    "SMA200_SLOPE",

    "VOL_RATIO_5_20",

    "VOLATILITY20",
    "VOLATILITY60",

    "DIST_HIGH20",
    "DIST_HIGH60",

    "DIST_LOW20",
    "DIST_LOW60",

    "BREAKOUT20",
    "BREAKOUT60",

    "RANGE_POSITION20",

    "DRAWDOWN60",
    "RECOVERY60",
]


# ============================================================
# CONSTRUCCIÓN DE DATASET
# ============================================================

def build_dataset(all_data):
    winners = []
    controls = []

    for ticker, features in all_data.items():

        events = find_events(features)

        event_positions = {
            e["position"]
            for e in events
        }

        # ----------------------------
        # GANADORAS
        # ----------------------------

        for event in events:

            pos = event["position"]

            row = features.iloc[pos]

            record = {
                "ticker": ticker,
                "date": str(
                    features.index[pos].date()
                ),
                "future_return": event[
                    "future_return"
                ],
                "label": 1,
            }

            for col in FEATURE_COLUMNS:
                record[col] = safe_float(row.get(col))

            winners.append(record)

        # ----------------------------
        # CONTROLES
        # ----------------------------

        # Solo usamos una observación cada
        # cinco sesiones para evitar que una
        # misma fase de mercado domine el dataset.

        for pos in range(
            210,
            len(features) - FORWARD_DAYS,
            5
        ):

            if pos in event_positions:
                continue

            future_return = future_max_return(
                features["Close"],
                pos,
                FORWARD_DAYS
            )

            if pd.isna(future_return):
                continue

            if future_return >= WIN_THRESHOLD:
                continue

            row = features.iloc[pos]

            record = {
                "ticker": ticker,
                "date": str(
                    features.index[pos].date()
                ),
                "future_return": future_return,
                "label": 0,
            }

            for col in FEATURE_COLUMNS:
                record[col] = safe_float(row.get(col))

            controls.append(record)

    return (
        pd.DataFrame(winners),
        pd.DataFrame(controls)
    )


# ============================================================
# DESCUBRIMIENTO DE PATRONES
# ============================================================

def discover_patterns(winners, controls):

    ranking = []

    if winners.empty or controls.empty:
        return pd.DataFrame()

    for feature in FEATURE_COLUMNS:

        w = pd.to_numeric(
            winners[feature],
            errors="coerce"
        ).dropna()

        c = pd.to_numeric(
            controls[feature],
            errors="coerce"
        ).dropna()

        if len(w) < 5 or len(c) < 5:
            continue

        w_median = w.median()
        c_median = c.median()

        pooled_std = np.sqrt(
            (
                w.var() +
                c.var()
            ) / 2
        )

        if not np.isfinite(pooled_std):
            continue

        if pooled_std == 0:
            separation = 0
        else:
            separation = abs(
                w_median -
                c_median
            ) / pooled_std

        direction = (
            "higher"
            if w_median > c_median
            else "lower"
        )

        ranking.append({
            "feature": feature,
            "winner_median": w_median,
            "control_median": c_median,
            "separation": separation,
            "direction": direction,
        })

    ranking_df = pd.DataFrame(ranking)

    if ranking_df.empty:
        return ranking_df

    ranking_df.sort_values(
        "separation",
        ascending=False,
        inplace=True
    )

    ranking_df.reset_index(
        drop=True,
        inplace=True
    )

    return ranking_df


# ============================================================
# SIMILITUD ENTRE PATRONES
# ============================================================

def calculate_similarity(
    current_row,
    historical_row,
    ranking
):
    """
    Compara una situación actual con una
    situación histórica ganadora.

    Cuanto más cerca de 1, más parecido.
    """

    if ranking.empty:
        return np.nan

    top_features = ranking.head(20)

    distances = []
    weights = []

    for _, r in top_features.iterrows():

        feature = r["feature"]

        current = safe_float(
            current_row.get(feature)
        )

        historical = safe_float(
            historical_row.get(feature)
        )

        if pd.isna(current) or pd.isna(historical):
            continue

        separation = safe_float(
            r["separation"]
        )

        if pd.isna(separation):
            continue

        # La escala depende del tamaño de la
        # diferencia histórica.
        scale = max(
            abs(
                safe_float(
                    r["winner_median"]
                ) -
                safe_float(
                    r["control_median"]
                )
            ),
            1e-6
        )

        distance = abs(
            current - historical
        ) / scale

        weight = max(
            separation,
            0.01
        )

        distances.append(distance)
        weights.append(weight)

    if not distances:
        return np.nan

    weighted_distance = np.average(
        distances,
        weights=weights
    )

    # Conversión de distancia a similitud.
    similarity = 1 / (
        1 + weighted_distance
    )

    return float(similarity)


# ============================================================
# ANÁLOGOS HISTÓRICOS
# ============================================================

def find_analogs(
    current_row,
    winners,
    ranking
):

    analogs = []

    if winners.empty:
        return analogs

    for _, historical in winners.iterrows():

        similarity = calculate_similarity(
            current_row,
            historical,
            ranking
        )

        if pd.isna(similarity):
            continue

        if similarity >= MIN_SIMILARITY:

            analogs.append({
                "ticker": historical["ticker"],
                "date": historical["date"],
                "future_return": historical[
                    "future_return"
                ],
                "similarity": similarity,
            })

    if not analogs:
        return []

    analogs.sort(
        key=lambda x: x["similarity"],
        reverse=True
    )

    return analogs[
        :MAX_ANALOGS_FOR_FORECAST
    ]


# ============================================================
# PREVISIÓN BASADA EN ANÁLOGOS
# ============================================================

def calculate_forecast(
    entry,
    analogs,
    current_row
):

    if len(analogs) < MIN_ANALOGS:
        return None

    returns = np.array([
        a["future_return"]
        for a in analogs
        if pd.notna(a["future_return"])
    ])

    returns = returns[
        np.isfinite(returns)
    ]

    if len(returns) < MIN_ANALOGS:
        return None

    # Percentiles de los casos históricos
    # comparables.
    lower_forecast = np.percentile(
        returns,
        25
    )

    upper_forecast = np.percentile(
        returns,
        75
    )

    # Para que una señal tenga sentido como
    # oportunidad, el extremo inferior
    # también debe ser positivo.
    if lower_forecast <= 0:
        return None

    # El modelo de stop usa volatilidad
    # histórica del propio valor.
    atr_pct = safe_float(
        current_row.get("ATR_PCT")
    )

    if pd.isna(atr_pct) or atr_pct <= 0:
        atr_pct = 0.025

    stop_risk = max(
        atr_pct * 1.25,
        0.025
    )

    # Nunca más del 8% de riesgo.
    stop_risk = min(
        stop_risk,
        0.08
    )

    stop = entry * (
        1 - stop_risk
    )

    target_low = entry * (
        1 + lower_forecast
    )

    target_high = entry * (
        1 + upper_forecast
    )

    risk_reward_low = (
        lower_forecast /
        stop_risk
    )

    risk_reward_high = (
        upper_forecast /
        stop_risk
    )

    return {
        "entry": entry,
        "target_low": target_low,
        "target_high": target_high,
        "forecast_low": lower_forecast,
        "forecast_high": upper_forecast,
        "stop": stop,
        "risk_pct": stop_risk,
        "rr_low": risk_reward_low,
        "rr_high": risk_reward_high,
        "analogs_count": len(analogs),
        "median_similarity": float(
            np.median([
                a["similarity"]
                for a in analogs
            ])
        ),
    }


# ============================================================
# AUDITORÍA DE ANÁLOGOS
# ============================================================

def save_analogs_audit(
    ticker,
    analogs,
    forecast
):

    if not analogs:
        return

    rows = []

    for a in analogs:
        rows.append({
            "current_ticker": ticker,
            "historical_ticker": a["ticker"],
            "historical_date": a["date"],
            "historical_future_return":
                a["future_return"],
            "similarity": a["similarity"],
            "current_forecast_low":
                forecast["forecast_low"],
            "current_forecast_high":
                forecast["forecast_high"],
        })

    path = Path(
        "historical_analogs.csv"
    )

    df_new = pd.DataFrame(rows)

    if path.exists():
        try:
            df_old = pd.read_csv(path)
            df = pd.concat(
                [df_old, df_new],
                ignore_index=True
            )
        except Exception:
            df = df_new
    else:
        df = df_new

    # Evita duplicados exactos.
    df.drop_duplicates(
        subset=[
            "current_ticker",
            "historical_ticker",
            "historical_date"
        ],
        inplace=True
    )

    df.to_csv(
        path,
        index=False
    )


# ============================================================
# VALIDACIÓN TEMPORAL
# ============================================================

def temporal_validation(winners, ranking):
    """
    Validación sencilla de que los patrones
    históricos también aparecen en periodos
    posteriores.

    No se utiliza para generar directamente
    las alertas.
    """

    if winners.empty or len(winners) < 10:
        return {
            "train": 0,
            "test": 0,
            "median_similarity": np.nan
        }

    winners = winners.copy()

    winners["date_dt"] = pd.to_datetime(
        winners["date"]
    )

    winners.sort_values(
        "date_dt",
        inplace=True
    )

    split = int(
        len(winners) * 0.70
    )

    train = winners.iloc[
        :split
    ].copy()

    test = winners.iloc[
        split:
    ].copy()

    if train.empty or test.empty:
        return {
            "train": len(train),
            "test": len(test),
            "median_similarity": np.nan
        }

    similarities = []

    for _, row in test.iterrows():

        sims = []

        for _, historical in train.iterrows():

            similarity = calculate_similarity(
                row,
                historical,
                ranking
            )

            if pd.notna(similarity):
                sims.append(similarity)

        if sims:
            similarities.append(
                max(sims)
            )

    return {
        "train": len(train),
        "test": len(test),
        "median_similarity": (
            float(np.median(similarities))
            if similarities
            else np.nan
        )
    }


# ============================================================
# ENVÍO TELEGRAM
# ============================================================

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN:
        print(
            "[TELEGRAM] Falta TELEGRAM_BOT_TOKEN"
        )
        return False

    if not TELEGRAM_CHAT_ID:
        print(
            "[TELEGRAM] Falta TELEGRAM_CHAT_ID"
        )
        return False

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
            timeout=20
        )

        if response.status_code != 200:
            print(
                "[TELEGRAM ERROR]",
                response.text
            )
            return False

        return True

    except Exception as e:
        print(
            "[TELEGRAM ERROR]",
            e
        )
        return False


# ============================================================
# FORMATO DE ALERTA
# ============================================================

def build_alert(
    ticker,
    forecast
):

    name = COMPANY_NAMES.get(
        ticker,
        ticker
    )

    return (
        "🚨 OPORTUNIDAD\n\n"
        f"{ticker} — {name}\n\n"
        f"Entrada: "
        f"{fmt_price(forecast['entry'])}\n"
        f"Objetivo estimado: "
        f"{fmt_price(forecast['target_low'])}"
        f"–"
        f"{fmt_price(forecast['target_high'])}\n"
        f"Previsión: "
        f"+{forecast['forecast_low'] * 100:.0f}%"
        f" / "
        f"+{forecast['forecast_high'] * 100:.0f}%\n\n"
        f"Stop orientativo: "
        f"{fmt_price(forecast['stop'])}\n"
        f"Riesgo: "
        f"-{forecast['risk_pct'] * 100:.1f}%\n"
        f"Riesgo/Beneficio: "
        f"1:{forecast['rr_low']:.1f}"
        f" / "
        f"1:{forecast['rr_high']:.1f}"
    )


# ============================================================
# ANÁLISIS DE TODAS LAS ACCIONES
# ============================================================

def build_all_data():

    all_data = {}

    print(
        "\n=============================="
    )
    print(
        "DESCARGANDO DATOS HISTÓRICOS"
    )
    print(
        "=============================="
    )

    for ticker in TICKERS:

        print(
            f"Analizando {ticker}..."
        )

        df = download_ticker(
            ticker
        )

        if df is None:
            print(
                f"  -> Sin datos suficientes"
            )
            continue

        features = build_features(
            df
        )

        all_data[ticker] = features

        print(
            f"  -> {len(features)} sesiones"
        )

    return all_data


# ============================================================
# PROCESO PRINCIPAL
# ============================================================

def main():

    print(
        "\n=========================================="
    )
    print(
        " MODELO DE PATRONES HISTÓRICOS — 49 VALORES"
    )
    print(
        "=========================================="
    )

    print(
        f"Periodo histórico: "
        f"{START_DATE} → hoy"
    )

    print(
        f"Umbral ganador: "
        f"+{WIN_THRESHOLD * 100:.0f}%"
    )

    print(
        f"Máximo alertas diarias: "
        f"{MAX_DAILY_ALERTS}"
    )

    # --------------------------------------------------------
    # ESTADO
    # --------------------------------------------------------

    state = load_state()

    state = prepare_today_state(
        state
    )

    print(
        "\nFecha del estado:",
        state["date"]
    )

    print(
        "Alertas ya enviadas hoy:",
        state["sent_tickers"]
    )

    save_state(state)

    # --------------------------------------------------------
    # DATOS
    # --------------------------------------------------------

    all_data = build_all_data()

    if len(all_data) == 0:
        print(
            "No se han podido obtener datos."
        )
        return

    # --------------------------------------------------------
    # DATASET
    # --------------------------------------------------------

    print(
        "\n=============================="
    )
    print(
        "CONSTRUYENDO DATASET"
    )
    print(
        "=============================="
    )

    winners, controls = build_dataset(
        all_data
    )

    print(
        f"Casos ganadores: "
        f"{len(winners)}"
    )

    print(
        f"Casos no ganadores: "
        f"{len(controls)}"
    )

    if winners.empty:
        print(
            "No hay suficientes movimientos "
            "ganadores."
        )
        return

    if controls.empty:
        print(
            "No hay suficientes controles."
        )
        return

    # --------------------------------------------------------
    # GUARDAR DATASETS
    # --------------------------------------------------------

    winners.to_csv(
        "historical_winners.csv",
        index=False
    )

    controls.to_csv(
        "historical_non_winners.csv",
        index=False
    )

    # --------------------------------------------------------
    # DESCUBRIR PATRONES
    # --------------------------------------------------------

    print(
        "\n=============================="
    )
    print(
        "DESCUBRIENDO PATRONES"
    )
    print(
        "=============================="
    )

    ranking = discover_patterns(
        winners,
        controls
    )

    if ranking.empty:
        print(
            "No se han podido descubrir "
            "patrones suficientes."
        )
        return

    ranking.to_csv(
        "pattern_feature_ranking.csv",
        index=False
    )

    print(
        "\nPrincipales variables:"
    )

    print(
        ranking.head(15).to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # VALIDACIÓN
    # --------------------------------------------------------

    validation = temporal_validation(
        winners,
        ranking
    )

    print(
        "\nValidación temporal:"
    )

    print(
        f"Train: {validation['train']}"
    )

    print(
        f"Test: {validation['test']}"
    )

    if pd.notna(
        validation["median_similarity"]
    ):
        print(
            "Similitud mediana test:",
            round(
                validation[
                    "median_similarity"
                ],
                3
            )
        )

    # --------------------------------------------------------
    # EVALUAR ACTUALMENTE LAS 49
    # --------------------------------------------------------

    opportunities = []

    print(
        "\n=============================="
    )
    print(
        "BUSCANDO OPORTUNIDADES ACTUALES"
    )
    print(
        "=============================="
    )

    for ticker, features in all_data.items():

        # MUY IMPORTANTE:
        # si ya se envió hoy, no se vuelve
        # a mandar aunque siga cumpliendo.
        if ticker_already_sent_today(
            state,
            ticker
        ):
            print(
                f"{ticker}: "
                f"YA ENVIADA HOY → OMITIDA"
            )
            continue

        if len(features) < 210:
            continue

        current_row = features.iloc[-1]

        entry = safe_float(
            current_row["Close"]
        )

        if pd.isna(entry) or entry <= 0:
            continue

        analogs = find_analogs(
            current_row,
            winners,
            ranking
        )

        if len(analogs) < MIN_ANALOGS:

            print(
                f"{ticker}: "
                f"{len(analogs)} análogos "
                f"→ insuficientes"
            )

            continue

        forecast = calculate_forecast(
            entry,
            analogs,
            current_row
        )

        if forecast is None:

            print(
                f"{ticker}: "
                f"análogos encontrados, "
                f"pero sin previsión válida"
            )

            continue

        # ----------------------------------------------------
        # SCORE INTERNO
        # ----------------------------------------------------
        # NO se muestra al usuario.
        # Solo sirve para decidir qué 4
        # oportunidades tienen mayor
        # similitud histórica.

        similarity_score = (
            forecast["median_similarity"]
        )

        analog_score = min(
            forecast["analogs_count"] / 15,
            1.0
        )

        forecast_score = min(
            forecast["forecast_low"] / 0.20,
            1.0
        )

        internal_score = (
            similarity_score * 0.60
            +
            analog_score * 0.20
            +
            forecast_score * 0.20
        )

        opportunity = {
            "ticker": ticker,
            "forecast": forecast,
            "analogs": analogs,
            "score": internal_score,
        }

        opportunities.append(
            opportunity
        )

        print(
            f"{ticker}: "
            f"OPORTUNIDAD | "
            f"análogos={len(analogs)} | "
            f"similitud="
            f"{forecast['median_similarity']:.3f} | "
            f"previsión="
            f"{forecast['forecast_low'] * 100:.1f}%"
            f"–"
            f"{forecast['forecast_high'] * 100:.1f}%"
        )

    # --------------------------------------------------------
    # ORDENAR OPORTUNIDADES
    # --------------------------------------------------------

    opportunities.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    # --------------------------------------------------------
    # MÁXIMO 4 AL DÍA
    # --------------------------------------------------------

    available_slots = (
        MAX_DAILY_ALERTS -
        len(state["sent_tickers"])
    )

    if available_slots <= 0:

        print(
            "\nLímite diario alcanzado."
        )

        save_state(state)

        return

    selected = opportunities[
        :available_slots
    ]

    # --------------------------------------------------------
    # ENVIAR TELEGRAM
    # --------------------------------------------------------

    print(
        "\n=============================="
    )
    print(
        "ENVÍO TELEGRAM"
    )
    print(
        "=============================="
    )

    for opportunity in selected:

        ticker = opportunity[
            "ticker"
        ]

        forecast = opportunity[
            "forecast"
        ]

        analogs = opportunity[
            "analogs"
        ]

        message = build_alert(
            ticker,
            forecast
        )

        print(
            "\nEnviando:",
            ticker
        )

        success = send_telegram(
            message
        )

        if success:

            print(
                f"{ticker}: "
                f"Telegram enviado correctamente"
            )

            # SOLO se marca como enviado
            # si Telegram confirmó el envío.
            register_sent_ticker(
                state,
                ticker
            )

            save_analogs_audit(
                ticker,
                analogs,
                forecast
            )

            # Guardar inmediatamente.
            # Así, incluso si posteriormente
            # falla otra parte del proceso,
            # este ticker ya queda registrado.
            save_state(state)

        else:

            print(
                f"{ticker}: "
                f"ERROR enviando Telegram"
            )

    # --------------------------------------------------------
    # ESTADO FINAL
    # --------------------------------------------------------

    save_state(state)

    print(
        "\n=============================="
    )
    print(
        "PROCESO TERMINADO"
    )
    print(
        "=============================="
    )

    print(
        "Alertas enviadas hoy:",
        state["sent_tickers"]
    )

    print(
        "Total hoy:",
        len(state["sent_tickers"])
    )


if __name__ == "__main__":
    main()
