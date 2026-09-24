import os
import json
import math
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import yfinance as yf

# ============================================================
# ESCÁNER DE PATRONES HISTÓRICOS — 49 VALORES
# Aprende de movimientos >= +10% desde 01/01/2025
# y busca analogías actuales.
# ============================================================

START_DATE = "2025-01-01"

WIN_THRESHOLD = 0.10
FORWARD_DAYS = 20
EVENT_SEPARATION_DAYS = 20

# ------------------------------------------------------------
# SENSIBILIDAD DEL MODELO
# ------------------------------------------------------------

# Número mínimo de casos históricos parecidos.
MIN_ANALOGS = 5

# Similitud mínima con los casos ganadores históricos.
MIN_SIMILARITY = 0.62

# Máximo de oportunidades que puede enviar en un día.
MAX_DAILY_ALERTS = 4

# Máximo de analogías utilizadas para calcular la previsión.
MAX_ANALOGS_FOR_FORECAST = 30

# ------------------------------------------------------------
# TELEGRAM
# ------------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Estado diario para no repetir oportunidades.
STATE_FILE = Path("alert_state.json")


# ============================================================
# UNIVERSO DE 49 VALORES
# ============================================================

TICKERS = [

    # ---------------- USA ----------------

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

    # ---------------- ESPAÑA ----------------

    "IBE.MC",
    "BBVA.MC",
    "SAN.MC",
    "ITX.MC",
    "REP.MC",
    "TEF.MC",

    # ---------------- ALEMANIA ----------------

    "SAP.DE",
    "SIE.DE",
    "ALV.DE",
    "DTE.DE",

    # ---------------- FRANCIA ----------------

    "AIR.PA",
    "SU.PA",
    "MC.PA",
    "TTE.PA",

    # ---------------- PAÍSES BAJOS ----------------

    "ASML.AS",
    "ADYEN.AS",

    # ---------------- ITALIA ----------------

    "RACE.MI",
    "ENEL.MI",
    "ISP.MI",

    # ---------------- ETFs ----------------

    "SXR8.DE",
    "SXRV.DE",
    "ZPDF.DE",
]


# ============================================================
# NOMBRES
# ============================================================

NAMES = {

    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "META": "Meta",
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

    "SXR8.DE": "iShares Core S&P 500",
    "SXRV.DE": "iShares NASDAQ 100",
    "ZPDF.DE": "SPDR U.S. Financials",
}


# ============================================================
# ÍNDICES DE MERCADO
# ============================================================

MARKETS = [
    "^GSPC",
    "^IXIC",
    "^DJI",
    "^VIX",
]


# ============================================================
# UTILIDADES
# ============================================================

def flatten_columns(df):

    if isinstance(df.columns, pd.MultiIndex):

        df.columns = [
            c[0] if isinstance(c, tuple) else c
            for c in df.columns
        ]

    df.columns = [str(c) for c in df.columns]

    return df


# ============================================================
# DESCARGA DE DATOS
# ============================================================

def download_daily(ticker, start=START_DATE):

    try:

        # End es exclusivo en yfinance.
        # De esta forma utilizamos el último cierre disponible.
        end = datetime.now(timezone.utc).date().isoformat()

        df = yf.download(
            ticker,
            start=start,
            end=end,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )

        if df is None or df.empty:
            return None

        df = flatten_columns(df)

        needed = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        if not all(c in df.columns for c in needed):
            return None

        df = df[needed].copy()

        df = df.dropna(
            subset=[
                "High",
                "Low",
                "Close",
            ]
        )

        df = df[
            ~df.index.duplicated(
                keep="last"
            )
        ]

        return df

    except Exception as e:

        print(
            f"[WARN] {ticker}: {e}"
        )

        return None


# ============================================================
# RSI
# ============================================================

def rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = gain.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False,
    ).mean()

    rs = (
        avg_gain
        /
        avg_loss.replace(
            0,
            np.nan
        )
    )

    result = (
        100
        -
        (
            100
            /
            (1 + rs)
        )
    )

    return result


# ============================================================
# ATR
# ============================================================

def atr(df, period=14):

    prev_close = df["Close"].shift(1)

    tr = pd.concat(
        [
            df["High"] - df["Low"],

            (
                df["High"]
                -
                prev_close
            ).abs(),

            (
                df["Low"]
                -
                prev_close
            ).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.rolling(
        period
    ).mean()


# ============================================================
# FEATURES
# ============================================================

def add_features(df):

    x = df.copy()

    close = x["Close"]

    volume = (
        x["Volume"]
        .replace(
            0,
            np.nan
        )
    )

    # Medias
    x["sma20"] = (
        close.rolling(20).mean()
    )

    x["sma50"] = (
        close.rolling(50).mean()
    )

    x["sma100"] = (
        close.rolling(100).mean()
    )

    x["sma200"] = (
        close.rolling(200).mean()
    )

    # RSI
    x["rsi14"] = rsi(close)

    # ATR
    x["atr14"] = atr(x)

    x["atr_pct"] = (
        x["atr14"]
        /
        close
    )

    # Rentabilidades
    for n in [
        1,
        3,
        5,
        10,
        20,
        40,
        60,
    ]:

        x[f"ret{n}"] = (
            close.pct_change(n)
        )

    # Precio frente a medias

    x["price_sma20"] = (
        close / x["sma20"]
        - 1
    )

    x["price_sma50"] = (
        close / x["sma50"]
        - 1
    )

    x["price_sma100"] = (
        close / x["sma100"]
        - 1
    )

    x["price_sma200"] = (
        close / x["sma200"]
        - 1
    )

    # Relaciones de medias

    x["sma20_sma50"] = (
        x["sma20"]
        /
        x["sma50"]
        - 1
    )

    x["sma50_sma200"] = (
        x["sma50"]
        /
        x["sma200"]
        - 1
    )

    # Pendientes

    x["sma20_slope10"] = (
        x["sma20"].pct_change(10)
    )

    x["sma50_slope20"] = (
        x["sma50"].pct_change(20)
    )

    # Volumen

    x["vol_ratio5_20"] = (
        volume.rolling(5).mean()
        /
        volume.rolling(20).mean()
    )

    # Volatilidad

    x["volatility20"] = (
        close.pct_change()
        .rolling(20)
        .std()
    )

    x["volatility60"] = (
        close.pct_change()
        .rolling(60)
        .std()
    )

    # Máximos / mínimos

    high20 = (
        x["High"]
        .rolling(20)
        .max()
    )

    high60 = (
        x["High"]
        .rolling(60)
        .max()
    )

    low20 = (
        x["Low"]
        .rolling(20)
        .min()
    )

    low60 = (
        x["Low"]
        .rolling(60)
        .min()
    )

    x["dist_high20"] = (
        close / high20 - 1
    )

    x["dist_high60"] = (
        close / high60 - 1
    )

    x["dist_low20"] = (
        close / low20 - 1
    )

    x["dist_low60"] = (
        close / low60 - 1
    )

    # Posición dentro del rango

    x["range20_pos"] = (
        (close - low20)
        /
        (high20 - low20)
        .replace(0, np.nan)
    )

    x["range60_pos"] = (
        (close - low60)
        /
        (high60 - low60)
        .replace(0, np.nan)
    )

    # Rupturas

    x["breakout20"] = (
        close
        /
        high20.shift(1)
        - 1
    )

    x["breakout60"] = (
        close
        /
        high60.shift(1)
        - 1
    )

    # Drawdown

    max60 = (
        close
        .rolling(60)
        .max()
    )

    min60 = (
        close
        .rolling(60)
        .min()
    )

    x["drawdown60"] = (
        close / max60 - 1
    )

    x["recovery60"] = (
        close / min60 - 1
    )

    return x


# ============================================================
# VARIABLES QUE EL MODELO ESTUDIA
# ============================================================

FEATURES = [

    "rsi14",
    "atr_pct",

    "ret1",
    "ret3",
    "ret5",
    "ret10",
    "ret20",
    "ret40",
    "ret60",

    "price_sma20",
    "price_sma50",
    "price_sma100",
    "price_sma200",

    "sma20_sma50",
    "sma50_sma200",

    "sma20_slope10",
    "sma50_slope20",

    "vol_ratio5_20",

    "volatility20",
    "volatility60",

    "dist_high20",
    "dist_high60",

    "dist_low20",
    "dist_low60",

    "range20_pos",
    "range60_pos",

    "breakout20",
    "breakout60",

    "drawdown60",
    "recovery60",
]


# ============================================================
# MERCADO GENERAL
# ============================================================

def build_market_features():

    market = {}

    for ticker in MARKETS:

        df = download_daily(
            ticker
        )

        if df is None or len(df) < 80:
            continue

        f = add_features(df)

        prefix = {

            "^GSPC": "sp",
            "^IXIC": "nd",
            "^DJI": "dj",
            "^VIX": "vix",

        }[ticker]

        cols = [

            "Close",
            "ret1",
            "ret5",
            "ret20",
            "sma20",
            "sma50",
            "sma200",

        ]

        m = f[cols].copy()

        m.columns = [
            f"{prefix}_{c}"
            for c in cols
        ]

        market[prefix] = m

    if not market:
        return None

    combined = pd.concat(
        list(market.values()),
        axis=1
    ).sort_index()

    for prefix in [
        "sp",
        "nd",
        "dj",
    ]:

        close_col = (
            f"{prefix}_Close"
        )

        if close_col in combined:

            combined[
                f"{prefix}_price_sma50"
            ] = (
                combined[close_col]
                /
                combined[
                    f"{prefix}_sma50"
                ]
                - 1
            )

            combined[
                f"{prefix}_price_sma200"
            ] = (
                combined[close_col]
                /
                combined[
                    f"{prefix}_sma200"
                ]
                - 1
            )

    return combined


# ============================================================
# RENTABILIDAD FUTURA
# ============================================================

def future_max_return(
    close,
    position,
    days=FORWARD_DAYS
):

    if position >= len(close) - 1:
        return np.nan, np.nan

    future = close.iloc[
        position + 1:
        position + 1 + days
    ]

    if future.empty:
        return np.nan, np.nan

    base = close.iloc[position]

    returns = (
        future / base - 1
    )

    idx = returns.idxmax()

    return (
        float(returns.max()),
        idx
    )


# ============================================================
# DETECCIÓN DE EVENTOS
# ============================================================

def find_events(df):

    close = df["Close"]

    candidates = []

    for i in range(
        200,
        len(df) - FORWARD_DAYS
    ):

        max_ret, future_date = (
            future_max_return(
                close,
                i
            )
        )

        if (
            pd.notna(max_ret)
            and
            max_ret >= WIN_THRESHOLD
        ):

            candidates.append(
                {
                    "date": df.index[i],

                    "future_date":
                        future_date,

                    "future_return":
                        max_ret,
                }
            )

    if not candidates:
        return []

    selected = []

    last_date = None

    for event in candidates:

        current_date = pd.Timestamp(
            event["date"]
        )

        if last_date is None:

            selected.append(event)

            last_date = (
                current_date
            )

            continue

        if (
            current_date
            -
            last_date
        ).days >= EVENT_SEPARATION_DAYS:

            selected.append(event)

            last_date = (
                current_date
            )

    return selected


# ============================================================
# CONSTRUCCIÓN DEL DATASET
# ============================================================

def make_dataset(
    all_features,
    market_features
):

    winners = []

    non_winners = []

    for ticker, df in all_features.items():

        if df is None or len(df) < 250:
            continue

        events = find_events(df)

        winning_dates = set()

        # ---------------- GANADORES ----------------

        for e in events:

            d = pd.Timestamp(
                e["date"]
            )

            if d not in df.index:
                continue

            row = df.loc[d].copy()

            if (
                market_features is not None
                and
                d in market_features.index
            ):

                row = pd.concat(
                    [
                        row,
                        market_features.loc[d],
                    ]
                )

            row["ticker"] = ticker

            row["event_date"] = d

            row["future_return"] = (
                e["future_return"]
            )

            row["future_date"] = (
                e["future_date"]
            )

            winners.append(row)

            winning_dates.add(d)

        # ---------------- CONTROLES ----------------

        eligible = [

            d

            for d in df.index[
                200:-FORWARD_DAYS
            ]

            if d not in winning_dates

        ]

        # Un control cada 5 sesiones.
        selected_controls = (
            eligible[::5]
        )

        for d in selected_controls:

            row = df.loc[d].copy()

            if (
                market_features is not None
                and
                d in market_features.index
            ):

                row = pd.concat(
                    [
                        row,
                        market_features.loc[d],
                    ]
                )

            row["ticker"] = ticker

            row["event_date"] = (
                pd.Timestamp(d)
            )

            position = (
                df.index.get_loc(d)
            )

            max_ret, future_date = (
                future_max_return(
                    df["Close"],
                    position
                )
            )

            row["future_return"] = (
                max_ret
            )

            row["future_date"] = (
                future_date
            )

            non_winners.append(row)

    winners_df = pd.DataFrame(
        winners
    )

    controls_df = pd.DataFrame(
        non_winners
    )

    return (
        winners_df,
        controls_df
    )


# ============================================================
# DESCUBRIMIENTO DE PATRONES
# ============================================================

def feature_separation(
    winners,
    controls,
    feature
):

    if (
        feature not in winners.columns
        or
        feature not in controls.columns
    ):
        return None

    w = pd.to_numeric(
        winners[feature],
        errors="coerce"
    ).dropna()

    c = pd.to_numeric(
        controls[feature],
        errors="coerce"
    ).dropna()

    if len(w) < 5 or len(c) < 10:
        return None

    wm = w.median()
    cm = c.median()

    pooled = math.sqrt(
        max(
            (
                (
                    w.var()
                    *
                    (len(w) - 1)
                )
                +
                (
                    c.var()
                    *
                    (len(c) - 1)
                )
            )
            /
            max(
                len(w)
                +
                len(c)
                - 2,
                1
            ),

            1e-12,
        )
    )

    separation = (
        abs(wm - cm)
        /
        pooled
    )

    direction = (
        "higher"
        if wm > cm
        else "lower"
    )

    return {

        "feature":
            feature,

        "winner_median":
            float(wm),

        "control_median":
            float(cm),

        "separation":
            float(separation),

        "direction":
            direction,

        "winner_n":
            int(len(w)),

        "control_n":
            int(len(c)),
    }


def discover_patterns(
    winners,
    controls
):

    results = []

    for feature in FEATURES:

        r = feature_separation(
            winners,
            controls,
            feature
        )

        if r:
            results.append(r)

    # Variables de mercado

    market_features = [

        c

        for c in winners.columns

        if c.startswith(
            (
                "sp_",
                "nd_",
                "dj_",
                "vix_",
            )
        )

    ]

    for feature in market_features:

        r = feature_separation(
            winners,
            controls,
            feature
        )

        if r:
            results.append(r)

    if not results:
        return pd.DataFrame()

    ranking = pd.DataFrame(
        results
    )

    ranking = ranking.sort_values(
        "separation",
        ascending=False
    )

    return ranking.reset_index(
        drop=True
    )


# ============================================================
# ESCALAS PARA COMPARAR PATRONES
# ============================================================

def build_feature_scales(
    winners,
    ranking
):

    scales = {}

    for feature in ranking[
        "feature"
    ].head(20):

        if feature not in winners.columns:
            continue

        values = pd.to_numeric(
            winners[feature],
            errors="coerce"
        ).dropna()

        if len(values) < 5:
            continue

        median = values.median()

        q25 = values.quantile(
            0.25
        )

        q75 = values.quantile(
            0.75
        )

        scale = (
            q75 - q25
        )

        if (
            not np.isfinite(scale)
            or
            scale <= 1e-9
        ):

            scale = values.std()

        if (
            not np.isfinite(scale)
            or
            scale <= 1e-9
        ):
            continue

        scales[feature] = {

            "median":
                float(median),

            "scale":
                float(scale),
        }

    return scales


# ============================================================
# SIMILITUD
# ============================================================

def similarity(
    current_row,
    historical_row,
    ranking,
    scales
):

    features = []

    for feature in ranking[
        "feature"
    ].head(20):

        if feature not in scales:
            continue

        a = pd.to_numeric(
            current_row.get(
                feature
            ),
            errors="coerce"
        )

        b = pd.to_numeric(
            historical_row.get(
                feature
            ),
            errors="coerce"
        )

        if (
            pd.isna(a)
            or
            pd.isna(b)
        ):
            continue

        scale = scales[
            feature
        ]["scale"]

        distance = (
            abs(
                float(a)
                -
                float(b)
            )
            /
            scale
        )

        sep = float(
            ranking.loc[
                ranking["feature"]
                ==
                feature,
                "separation"
            ].iloc[0]
        )

        weight = max(
            sep,
            0.05
        )

        features.append(
            (
                distance,
                weight
            )
        )

    if len(features) < 5:
        return np.nan

    weighted_distance = (
        sum(
            d * w
            for d, w
            in features
        )
        /
        sum(
            w
            for _, w
            in features
        )
    )

    return float(
        math.exp(
            -weighted_distance
        )
    )


# ============================================================
# BÚSQUEDA DE ANÁLOGOS
# ============================================================

def find_analogues(
    current_row,
    winners,
    ranking,
    scales
):

    candidates = []

    for _, historical in winners.iterrows():

        sim = similarity(
            current_row,
            historical,
            ranking,
            scales
        )

        if pd.isna(sim):
            continue

        if sim >= MIN_SIMILARITY:

            candidates.append(
                {

                    "similarity":
                        sim,

                    "future_return":
                        historical[
                            "future_return"
                        ],

                    "event_date":
                        historical[
                            "event_date"
                        ],

                    "ticker":
                        historical[
                            "ticker"
                        ],
                }
            )

    if not candidates:
        return []

    candidates.sort(
        key=lambda x:
            x["similarity"],
        reverse=True
    )

    return candidates[
        :MAX_ANALOGS_FOR_FORECAST
    ]


# ============================================================
# ENTRADA / STOP / OBJETIVOS
# ============================================================

def calculate_trade_levels(
    current_row,
    analogues
):

    entry = float(
        current_row["Close"]
    )

    atr_pct = float(
        current_row.get(
            "atr_pct",
            np.nan
        )
    )

    returns = np.array(

        [
            a["future_return"]

            for a in analogues

            if pd.notna(
                a["future_return"]
            )

        ],

        dtype=float,
    )

    if len(returns) < MIN_ANALOGS:
        return None

    # Percentiles de los casos
    # históricos más parecidos.

    p25, p50, p75 = np.percentile(
        returns,
        [25, 50, 75]
    )

    # Solo se considera una oportunidad
    # si el escenario inferior conserva
    # al menos +10%.

    p25 = max(
        p25,
        WIN_THRESHOLD
    )

    p50 = max(
        p50,
        p25
    )

    # Objetivos

    target_low = (
        entry
        *
        (1 + p25)
    )

    target_high = (
        entry
        *
        (1 + p75)
    )

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    # Stop basado en volatilidad actual.
    #
    # Se utiliza ATR y se limita entre 2,5% y 8%.
    #
    # Es orientativo, no una garantía de pérdida máxima.

    if (
        np.isfinite(atr_pct)
        and
        atr_pct > 0
    ):

        stop_risk = max(
            1.25 * atr_pct,
            0.025
        )

        stop_risk = min(
            stop_risk,
            0.08
        )

    else:

        stop_risk = 0.05

    stop = (
        entry
        *
        (1 - stop_risk)
    )

    risk_pct = (
        (entry - stop)
        /
        entry
    )

    # Riesgo / beneficio

    rr_low = (
        p25
        /
        risk_pct
    )

    rr_high = (
        p75
        /
        risk_pct
    )

    return {

        "entry":
            entry,

        "target_low":
            target_low,

        "target_high":
            target_high,

        "forecast_low":
            p25,

        "forecast_high":
            p75,

        "stop":
            stop,

        "risk_pct":
            risk_pct,

        "rr_low":
            rr_low,

        "rr_high":
            rr_high,
    }


# ============================================================
# VALIDACIÓN TEMPORAL
# ============================================================

def temporal_validation(
    winners,
    controls
):

    if len(winners) < 12:
        return None

    winners = winners.sort_values(
        "event_date"
    )

    cutoff = int(
        len(winners)
        *
        0.70
    )

    train = winners.iloc[
        :cutoff
    ]

    test = winners.iloc[
        cutoff:
    ]

    if (
        len(train) < 8
        or
        len(test) < 3
    ):
        return None

    min_test_date = (
        test["event_date"].min()
    )

    train_controls = controls[
        controls["event_date"]
        <
        min_test_date
    ]

    ranking = discover_patterns(
        train,
        train_controls
    )

    if ranking.empty:
        return None

    scales = build_feature_scales(
        train,
        ranking
    )

    if not scales:
        return None

    similarities = []

    for _, row in test.iterrows():

        sims = []

        for _, hist in train.iterrows():

            s = similarity(
                row,
                hist,
                ranking,
                scales
            )

            if pd.notna(s):
                sims.append(s)

        if sims:
            similarities.append(
                max(sims)
            )

    if not similarities:
        return None

    return {

        "train_events":
            len(train),

        "test_events":
            len(test),

        "test_mean_best_similarity":
            float(
                np.mean(
                    similarities
                )
            ),

        "test_median_best_similarity":
            float(
                np.median(
                    similarities
                )
            ),
    }


# ============================================================
# ESTADO DIARIO
# ============================================================

def load_state():

    today = (
        datetime.now(
            timezone.utc
        )
        .date()
        .isoformat()
    )

    try:

        if STATE_FILE.exists():

            data = json.loads(
                STATE_FILE.read_text(
                    encoding="utf-8"
                )
            )

            if (
                data.get("date")
                ==
                today
            ):

                return data

    except Exception:
        pass

    return {

        "date":
            today,

        "sent_tickers":
            [],
    }


def save_state(state):

    STATE_FILE.write_text(

        json.dumps(
            state,
            indent=2,
            ensure_ascii=False
        ),

        encoding="utf-8"
    )


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(text):

    if (
        not TELEGRAM_BOT_TOKEN
        or
        not TELEGRAM_CHAT_ID
    ):

        print(
            "[ERROR] Faltan "
            "TELEGRAM_BOT_TOKEN "
            "o "
            "TELEGRAM_CHAT_ID"
        )

        return False

    url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}"
        "/sendMessage"
    )

    try:

        response = requests.post(

            url,

            json={

                "chat_id":
                    TELEGRAM_CHAT_ID,

                "text":
                    text,
            },

            timeout=20,
        )

        if response.ok:
            return True

        print(
            "[ERROR TELEGRAM]",
            response.text
        )

        return False

    except Exception as e:

        print(
            "[ERROR TELEGRAM]",
            e
        )

        return False


# ============================================================
# FORMATO
# ============================================================

def fmt_price(value):

    if value >= 1000:

        return (
            f"{value:,.0f}"
        )

    if value >= 100:

        return (
            f"{value:,.2f}"
        )

    if value >= 10:

        return (
            f"{value:,.2f}"
        )

    return (
        f"{value:,.3f}"
    )


# ============================================================
# MENSAJE TELEGRAM
# ============================================================

def make_alert(
    ticker,
    trade
):

    return (

        "🚨 OPORTUNIDAD\n\n"

        f"{ticker} — "
        f"{NAMES.get(ticker, ticker)}\n\n"

        f"Entrada: "
        f"{fmt_price(trade['entry'])}\n"

        f"Objetivo estimado: "
        f"{fmt_price(trade['target_low'])}"
        "–"
        f"{fmt_price(trade['target_high'])}\n"

        f"Previsión: "
        f"+{trade['forecast_low'] * 100:.0f}%"
        " / "
        f"+{trade['forecast_high'] * 100:.0f}%\n\n"

        f"Stop orientativo: "
        f"{fmt_price(trade['stop'])}\n"

        f"Riesgo: "
        f"-{trade['risk_pct'] * 100:.1f}%\n"

        f"Riesgo/Beneficio: "
        f"1:{trade['rr_low']:.1f}"
        " / "
        f"1:{trade['rr_high']:.1f}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=" * 70
    )

    print(
        "MODELO DE PATRONES HISTÓRICOS"
    )

    print(
        f"Histórico desde: "
        f"{START_DATE}"
    )

    print(
        "Umbral de aprendizaje: "
        f"+{WIN_THRESHOLD * 100:.0f}%"
    )

    print(
        "Máximo de alertas hoy: "
        f"{MAX_DAILY_ALERTS}"
    )

    print(
        "=" * 70
    )

    # --------------------------------------------------------
    # MERCADO
    # --------------------------------------------------------

    market_features = (
        build_market_features()
    )

    # --------------------------------------------------------
    # DESCARGA DE LAS 49
    # --------------------------------------------------------

    all_features = {}

    failed = []

    for ticker in TICKERS:

        print(
            f"Analizando {ticker}..."
        )

        raw = download_daily(
            ticker
        )

        if (
            raw is None
            or
            len(raw) < 250
        ):

            failed.append(
                ticker
            )

            continue

        all_features[
            ticker
        ] = add_features(raw)

    print()

    print(
        f"Valores válidos: "
        f"{len(all_features)}/"
        f"{len(TICKERS)}"
    )

    if len(all_features) < 20:

        print(
            "[ERROR] Demasiados "
            "valores sin datos."
        )

        return

    # --------------------------------------------------------
    # DATASET
    # --------------------------------------------------------

    winners, controls = (
        make_dataset(
            all_features,
            market_features
        )
    )

    print(
        f"Eventos ganadores encontrados: "
        f"{len(winners)}"
    )

    print(
        f"Casos de control: "
        f"{len(controls)}"
    )

    if len(winners) < MIN_ANALOGS:

        print(
            "[INFO] Todavía no hay "
            "suficientes eventos históricos."
        )

        return

    # --------------------------------------------------------
    # DESCUBRIR PATRONES
    # --------------------------------------------------------

    ranking = discover_patterns(
        winners,
        controls
    )

    if ranking.empty:

        print(
            "[INFO] No se han podido "
            "descubrir patrones."
        )

        return

    # --------------------------------------------------------
    # GUARDAR DATOS
    # --------------------------------------------------------

    ranking.to_csv(
        "pattern_feature_ranking.csv",
        index=False
    )

    winners.to_csv(
        "historical_winners.csv",
        index=False
    )

    controls.to_csv(
        "historical_non_winners.csv",
        index=False
    )

    # --------------------------------------------------------
    # MOSTRAR PATRONES
    # --------------------------------------------------------

    print()

    print(
        "TOP PATRONES DETECTADOS:"
    )

    print(

        ranking[
            [
                "feature",
                "separation",
                "direction",
            ]
        ]
        .head(12)
        .to_string(
            index=False
        )

    )

    # --------------------------------------------------------
    # VALIDACIÓN
    # --------------------------------------------------------

    validation = (
        temporal_validation(
            winners,
            controls
        )
    )

    if validation:

        print()

        print(
            "VALIDACIÓN TEMPORAL:"
        )

        print(
            validation
        )

    # --------------------------------------------------------
    # ESCALAS
    # --------------------------------------------------------

    scales = (
        build_feature_scales(
            winners,
            ranking
        )
    )

    if not scales:

        print(
            "[INFO] No hay escalas "
            "suficientes."
        )

        return

    # --------------------------------------------------------
    # ESTADO DIARIO
    # --------------------------------------------------------

    state = load_state()

    sent_today = set(
        state.get(
            "sent_tickers",
            []
        )
    )

    remaining_slots = max(
        0,
        MAX_DAILY_ALERTS
        -
        len(sent_today)
    )

    if remaining_slots == 0:

        print(
            "[INFO] Ya se alcanzó "
            "el máximo diario."
        )

        return

    # --------------------------------------------------------
    # BUSCAR OPORTUNIDADES
    # --------------------------------------------------------

    opportunities = []

    for ticker, df in (
        all_features.items()
    ):

        if ticker in sent_today:
            continue

        current = (
            df.iloc[-1].copy()
        )

        current_date = (
            df.index[-1]
        )

        analogues = (
            find_analogues(
                current,
                winners,
                ranking,
                scales
            )
        )

        if (
            len(analogues)
            <
            MIN_ANALOGS
        ):
            continue

        trade = (
            calculate_trade_levels(
                current,
                analogues
            )
        )

        if trade is None:
            continue

        # El escenario inferior
        # debe seguir siendo >= +10%.

        if (
            trade["forecast_low"]
            <
            WIN_THRESHOLD
        ):
            continue

        median_similarity = float(
            np.median(
                [
                    a["similarity"]
                    for a in analogues
                ]
            )
        )

        # Puntuación interna para decidir
        # cuáles son las 4 coincidencias
        # más fuertes.
        #
        # NO se muestra al usuario.

        score = (

            median_similarity
            * 0.60

            +

            min(
                len(analogues)
                /
                15.0,
                1.0
            )
            * 0.20

            +

            min(
                max(
                    trade[
                        "forecast_low"
                    ],
                    0
                )
                /
                0.20,
                1.0
            )
            * 0.20
        )

        opportunities.append(
            {

                "ticker":
                    ticker,

                "date":
                    current_date,

                "trade":
                    trade,

                "analogues":
                    len(analogues),

                "median_similarity":
                    median_similarity,

                "score":
                    score,
            }
        )

    # --------------------------------------------------------
    # NINGUNA OPORTUNIDAD
    # --------------------------------------------------------

    if not opportunities:

        print()

        print(
            "No hay oportunidades "
            "suficientes en esta ejecución."
        )

        save_state(state)

        return

    # --------------------------------------------------------
    # ORDEN INTERNO
    # --------------------------------------------------------

    opportunities.sort(
        key=lambda x:
            x["score"],
        reverse=True
    )

    selected = opportunities[
        :remaining_slots
    ]

    print()

    print(
        f"Oportunidades encontradas: "
        f"{len(opportunities)}"
    )

    print(
        f"Alertas que se enviarán ahora: "
        f"{len(selected)}"
    )

    # --------------------------------------------------------
    # ENVIAR UNA POR UNA
    # --------------------------------------------------------

    for opportunity in selected:

        ticker = (
            opportunity["ticker"]
        )

        trade = (
            opportunity["trade"]
        )

        message = make_alert(
            ticker,
            trade
        )

        print()

        print(
            message
        )

        ok = send_telegram(
            message
        )

        if ok:

            sent_today.add(
                ticker
            )

            state[
                "sent_tickers"
            ] = sorted(
                sent_today
            )

            save_state(
                state
            )

    print()

    print(
        "Proceso terminado."
    )


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    main()
