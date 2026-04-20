#!/usr/bin/env python3
"""
J.A.R.V.I.S. Trading System v3.0 — Backend Server
===================================================
Flask backend serving 33 API routes for the JARVIS crypto trading dashboard.
Includes: market data proxying, 11 technical indicators, market regime detection,
signal engine, risk engine, dip/top detectors, paper trading, exchange management,
and an Anthropic-powered AI assistant.
"""

import csv
import hashlib
import hmac
import io
import json
import logging
import math
import os
import re
import sqlite3
import subprocess
import time
import threading
from abc import ABC, abstractmethod
from base64 import b64encode, b64decode
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

try:
    from cryptography.fernet import Fernet
    HAS_FERNET = True
except ImportError:
    HAS_FERNET = False

try:
    import ccxt
    HAS_CCXT = True
except ImportError:
    HAS_CCXT = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

APP_VERSION = "3.0.0"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "jarvis.db"
SECRET_KEY_FILE = BASE_DIR / "secret.key"
BINANCE_BASE = "https://api.binance.com"
BINANCE_FAPI = "https://fapi.binance.com"
STOOQ_BASE = "https://stooq.com/q/l/"
ALTERNATIVE_ME = "https://api.alternative.me"
WHALE_ALERT_BASE = "https://api.whale-alert.io/v1"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
WHALE_ALERT_KEY = os.environ.get("WHALE_ALERT_API_KEY", "")

START_TIME = time.time()

SUPPORTED_SYMBOLS = {
    "BTCUSDT": {"base": "BTC", "quote": "USDT", "source": "binance"},
    "ETHUSDT": {"base": "ETH", "quote": "USDT", "source": "binance"},
    "SOLUSDT": {"base": "SOL", "quote": "USDT", "source": "binance"},
    "XRPUSDT": {"base": "XRP", "quote": "USDT", "source": "binance"},
    "DOGEUSDT": {"base": "DOGE", "quote": "USDT", "source": "binance"},
    "GOLD": {"base": "XAU", "quote": "USD", "source": "stooq", "stooq_sym": "xauusd"},
    "SILVER": {"base": "XAG", "quote": "USD", "source": "stooq", "stooq_sym": "xagusd"},
}

INTERVALS = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "8h": "8h",
    "12h": "12h", "1d": "1d", "3d": "3d", "1w": "1w", "1M": "1M",
}

ECONOMIC_CALENDAR = [
    {"event": "FOMC Meeting", "dates": ["2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17", "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16"], "impact": "high"},
    {"event": "CPI Release", "dates": ["2026-01-14", "2026-02-12", "2026-03-12", "2026-04-14", "2026-05-13", "2026-06-10", "2026-07-14", "2026-08-12"], "impact": "high"},
    {"event": "NFP Report", "dates": ["2026-01-09", "2026-02-06", "2026-03-06", "2026-04-03", "2026-05-08", "2026-06-05", "2026-07-02", "2026-08-07"], "impact": "high"},
    {"event": "ECB Decision", "dates": ["2026-01-22", "2026-03-05", "2026-04-16", "2026-06-04", "2026-07-16", "2026-09-10", "2026-10-29", "2026-12-10"], "impact": "medium"},
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("jarvis")

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder=str(BASE_DIR))
CORS(app)

# ---------------------------------------------------------------------------
# Thread-safe cache with TTL
# ---------------------------------------------------------------------------

class Cache:
    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key, ttl=30):
        with self._lock:
            entry = self._store.get(key)
            if entry and (time.time() - entry["ts"]) < ttl:
                return entry["data"]
        return None

    def set(self, key, data):
        with self._lock:
            self._store[key] = {"data": data, "ts": time.time()}

    def invalidate(self, key):
        with self._lock:
            self._store.pop(key, None)


cache = Cache()


# ---------------------------------------------------------------------------
# Database — SQLite WAL
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS exchanges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        exchange_type TEXT NOT NULL,
        api_key_enc TEXT NOT NULL,
        api_secret_enc TEXT NOT NULL,
        passphrase_enc TEXT DEFAULT '',
        is_testnet INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS paper_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        entry_price REAL NOT NULL,
        exit_price REAL,
        quantity REAL NOT NULL,
        leverage INTEGER DEFAULT 1,
        pnl REAL DEFAULT 0,
        status TEXT DEFAULT 'open',
        opened_at TEXT DEFAULT (datetime('now')),
        closed_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS trade_journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        action TEXT NOT NULL,
        reason TEXT,
        signal_score REAL,
        confidence REAL,
        regime TEXT,
        result TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS killswitch (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        active INTEGER DEFAULT 0,
        activated_at TEXT,
        reason TEXT
    )""")
    c.execute("INSERT OR IGNORE INTO killswitch (id, active) VALUES (1, 0)")

    conn.commit()
    conn.close()
    log.info("Database initialized at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Encryption — Fernet for exchange API keys
# ---------------------------------------------------------------------------

_fernet_instance = None


def get_fernet():
    global _fernet_instance
    if _fernet_instance:
        return _fernet_instance
    if not HAS_FERNET:
        return None
    if SECRET_KEY_FILE.exists():
        key = SECRET_KEY_FILE.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        SECRET_KEY_FILE.write_bytes(key)
        os.chmod(str(SECRET_KEY_FILE), 0o600)
        log.info("Generated new encryption key")
    _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_string(plaintext):
    f = get_fernet()
    if not f:
        return b64encode(plaintext.encode()).decode()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_string(ciphertext):
    f = get_fernet()
    if not f:
        return b64decode(ciphertext.encode()).decode()
    return f.decrypt(ciphertext.encode()).decode()


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def get_setting(key, default=None):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_db()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, str(value), str(value)),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Binance API helpers
# ---------------------------------------------------------------------------

def fetch_binance(endpoint, params=None, base=None, ttl=15):
    base = base or BINANCE_BASE
    cache_key = f"binance:{endpoint}:{json.dumps(params or {}, sort_keys=True)}"
    cached = cache.get(cache_key, ttl=ttl)
    if cached is not None:
        return cached
    try:
        resp = requests.get(f"{base}{endpoint}", params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        cache.set(cache_key, data)
        return data
    except requests.RequestException as e:
        log.warning("Binance %s failed: %s", endpoint, e)
        return None


def transform_klines(raw):
    return [
        {
            "time": int(k[0]) // 1000,
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        }
        for k in raw
    ]


# ---------------------------------------------------------------------------
# Gold/Silver via Stooq CSV (no yfinance dependency needed)
# ---------------------------------------------------------------------------

def fetch_stooq_price(symbol_info):
    sym = symbol_info.get("stooq_sym", "")
    if not sym:
        return None
    cache_key = f"stooq:{sym}"
    cached = cache.get(cache_key, ttl=60)
    if cached is not None:
        return cached
    try:
        resp = requests.get(
            STOOQ_BASE,
            params={"s": sym, "f": "sd2t2ohlcv", "h": "", "e": "csv"},
            timeout=5,
        )
        resp.raise_for_status()
        lines = resp.text.strip().split("\n")
        if len(lines) < 2:
            return None
        headers = [h.strip().lower() for h in lines[0].split(",")]
        values = lines[1].split(",")
        row = dict(zip(headers, values))
        data = {
            "symbol": symbol_info["base"] + symbol_info["quote"],
            "price": float(row.get("close", 0)),
            "open": float(row.get("open", 0)),
            "high": float(row.get("high", 0)),
            "low": float(row.get("low", 0)),
            "volume": float(row.get("volume", 0)) if row.get("volume", "N/A") != "N/A" else 0,
            "source": "stooq",
        }
        cache.set(cache_key, data)
        return data
    except Exception as e:
        log.warning("Stooq %s failed: %s", sym, e)
        return None


def generate_gold_silver_candles(symbol_info, limit=100):
    price_data = fetch_stooq_price(symbol_info)
    if not price_data or not price_data["price"]:
        return []
    p = price_data["price"]
    now = int(time.time())
    candles = []
    for i in range(limit):
        t = now - (limit - i) * 3600
        noise = math.sin(i * 0.1) * p * 0.002
        candles.append({
            "time": t,
            "open": round(p + noise, 2),
            "high": round(p + abs(noise) + p * 0.001, 2),
            "low": round(p - abs(noise) - p * 0.001, 2),
            "close": round(p + noise * 0.5, 2),
            "volume": 0,
        })
    return candles


# ---------------------------------------------------------------------------
# Technical Indicators — Part 1 (SMA, EMA, RSI, MACD, Bollinger)
# All pure Python, no numpy/pandas. Operate on lists of floats.
# ---------------------------------------------------------------------------

def calc_sma(data, period):
    if len(data) < period:
        return [None] * len(data)
    out = [None] * (period - 1)
    window_sum = sum(data[:period])
    out.append(window_sum / period)
    for i in range(period, len(data)):
        window_sum += data[i] - data[i - period]
        out.append(window_sum / period)
    return out


def calc_ema(data, period):
    if len(data) < period:
        return [None] * len(data)
    k = 2.0 / (period + 1)
    out = [None] * (period - 1)
    seed = sum(data[:period]) / period
    out.append(seed)
    prev = seed
    for i in range(period, len(data)):
        val = data[i] * k + prev * (1 - k)
        out.append(val)
        prev = val
    return out


def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return [None] * len(closes)
    out = [None] * period
    gains = []
    losses = []
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        out.append(100.0)
    else:
        rs = avg_gain / avg_loss
        out.append(100.0 - 100.0 / (1.0 + rs))
    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = max(delta, 0)
        loss = max(-delta, 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            out.append(100.0)
        else:
            rs = avg_gain / avg_loss
            out.append(100.0 - 100.0 / (1.0 + rs))
    return out


def calc_macd(closes, fast=12, slow=26, signal_period=9):
    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)
    macd_line = []
    for f, s in zip(ema_fast, ema_slow):
        if f is not None and s is not None:
            macd_line.append(f - s)
        else:
            macd_line.append(None)
    valid_macd = [v for v in macd_line if v is not None]
    if len(valid_macd) < signal_period:
        return {
            "line": macd_line,
            "signal": [None] * len(closes),
            "histogram": [None] * len(closes),
        }
    signal_raw = calc_ema(valid_macd, signal_period)
    signal_line = [None] * (len(macd_line) - len(valid_macd))
    signal_line.extend(signal_raw)
    histogram = []
    for m, s in zip(macd_line, signal_line):
        if m is not None and s is not None:
            histogram.append(m - s)
        else:
            histogram.append(None)
    return {"line": macd_line, "signal": signal_line, "histogram": histogram}


def _std_dev(data):
    n = len(data)
    if n < 2:
        return 0.0
    mean = sum(data) / n
    variance = sum((x - mean) ** 2 for x in data) / n
    return math.sqrt(variance)


def calc_bollinger(closes, period=20, num_std=2):
    if len(closes) < period:
        return {"upper": [None] * len(closes), "middle": [None] * len(closes), "lower": [None] * len(closes)}
    middle = calc_sma(closes, period)
    upper = []
    lower = []
    for i in range(len(closes)):
        if middle[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            window = closes[max(0, i - period + 1):i + 1]
            sd = _std_dev(window)
            upper.append(middle[i] + num_std * sd)
            lower.append(middle[i] - num_std * sd)
    return {"upper": upper, "middle": middle, "lower": lower}


# ---------------------------------------------------------------------------
# Technical Indicators — Part 2 (ATR, StochRSI, ADX, OBV, Williams %R)
# ---------------------------------------------------------------------------

def calc_atr(highs, lows, closes, period=14):
    if len(closes) < 2:
        return [None] * len(closes)
    tr_list = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)
    if len(tr_list) < period:
        return [None] * len(closes)
    out = [None] * (period - 1)
    atr = sum(tr_list[:period]) / period
    out.append(atr)
    for i in range(period, len(tr_list)):
        atr = (atr * (period - 1) + tr_list[i]) / period
        out.append(atr)
    return out


def calc_stoch_rsi(closes, rsi_period=14, stoch_period=14, smooth_k=3, smooth_d=3):
    rsi = calc_rsi(closes, rsi_period)
    valid_rsi = [v for v in rsi if v is not None]
    if len(valid_rsi) < stoch_period:
        return {"k": [None] * len(closes), "d": [None] * len(closes)}
    stoch_raw = []
    for i in range(stoch_period - 1, len(valid_rsi)):
        window = valid_rsi[i - stoch_period + 1:i + 1]
        lo = min(window)
        hi = max(window)
        if hi == lo:
            stoch_raw.append(50.0)
        else:
            stoch_raw.append((valid_rsi[i] - lo) / (hi - lo) * 100.0)
    k_raw = calc_sma(stoch_raw, smooth_k)
    k_valid = [v for v in k_raw if v is not None]
    d_raw = calc_sma(k_valid, smooth_d) if k_valid else []
    prefix_len = len(closes) - len(stoch_raw)
    k_out = [None] * prefix_len + k_raw
    d_prefix = len(closes) - len(d_raw) if d_raw else len(closes)
    d_out = [None] * d_prefix + (d_raw if d_raw else [])
    if len(k_out) < len(closes):
        k_out = [None] * (len(closes) - len(k_out)) + k_out
    if len(d_out) < len(closes):
        d_out = [None] * (len(closes) - len(d_out)) + d_out
    return {"k": k_out[:len(closes)], "d": d_out[:len(closes)]}


def calc_adx(highs, lows, closes, period=14):
    n = len(closes)
    if n < period + 1:
        return {"adx": [None] * n, "dmi_plus": [None] * n, "dmi_minus": [None] * n}
    plus_dm = []
    minus_dm = []
    tr_list = []
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)
    def wilder_smooth(data, p):
        if len(data) < p:
            return []
        out = [sum(data[:p])]
        for i in range(p, len(data)):
            out.append(out[-1] - out[-1] / p + data[i])
        return out
    sm_tr = wilder_smooth(tr_list, period)
    sm_plus = wilder_smooth(plus_dm, period)
    sm_minus = wilder_smooth(minus_dm, period)
    if not sm_tr:
        return {"adx": [None] * n, "dmi_plus": [None] * n, "dmi_minus": [None] * n}
    di_plus = []
    di_minus = []
    dx_list = []
    for i in range(len(sm_tr)):
        dp = (sm_plus[i] / sm_tr[i] * 100.0) if sm_tr[i] != 0 else 0.0
        dm = (sm_minus[i] / sm_tr[i] * 100.0) if sm_tr[i] != 0 else 0.0
        di_plus.append(dp)
        di_minus.append(dm)
        total = dp + dm
        dx_list.append(abs(dp - dm) / total * 100.0 if total != 0 else 0.0)
    adx_raw = wilder_smooth(dx_list, period)
    adx_out = [None] * n
    dmi_plus_out = [None] * n
    dmi_minus_out = [None] * n
    offset_di = period
    for i, (dp, dm) in enumerate(zip(di_plus, di_minus)):
        idx = offset_di + i
        if idx < n:
            dmi_plus_out[idx] = dp
            dmi_minus_out[idx] = dm
    offset_adx = offset_di + period - 1
    for i, a in enumerate(adx_raw):
        idx = offset_adx + i
        if idx < n:
            adx_out[idx] = a
    return {"adx": adx_out, "dmi_plus": dmi_plus_out, "dmi_minus": dmi_minus_out}


def calc_obv(closes, volumes):
    if not closes:
        return []
    out = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            out.append(out[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            out.append(out[-1] - volumes[i])
        else:
            out.append(out[-1])
    return out


def calc_williams_r(highs, lows, closes, period=14):
    if len(closes) < period:
        return [None] * len(closes)
    out = [None] * (period - 1)
    for i in range(period - 1, len(closes)):
        hi = max(highs[i - period + 1:i + 1])
        lo = min(lows[i - period + 1:i + 1])
        if hi == lo:
            out.append(-50.0)
        else:
            out.append((hi - closes[i]) / (hi - lo) * -100.0)
    return out


# ---------------------------------------------------------------------------
# Consolidated indicator computation
# ---------------------------------------------------------------------------

def compute_all_indicators(ohlcv):
    closes = [c["close"] for c in ohlcv]
    highs = [c["high"] for c in ohlcv]
    lows = [c["low"] for c in ohlcv]
    volumes = [c["volume"] for c in ohlcv]
    times = [c["time"] for c in ohlcv]

    def ts_pair(values):
        return [
            {"time": t, "value": round(v, 6) if v is not None else None}
            for t, v in zip(times, values)
            if v is not None
        ]

    rsi = calc_rsi(closes)
    macd = calc_macd(closes)
    bb = calc_bollinger(closes)
    atr = calc_atr(highs, lows, closes)
    stoch = calc_stoch_rsi(closes)
    adx = calc_adx(highs, lows, closes)
    obv = calc_obv(closes, volumes)
    wr = calc_williams_r(highs, lows, closes)

    return {
        "rsi": ts_pair(rsi),
        "macd": {
            "line": ts_pair(macd["line"]),
            "signal": ts_pair(macd["signal"]),
            "histogram": ts_pair(macd["histogram"]),
        },
        "bollinger": {
            "upper": ts_pair(bb["upper"]),
            "middle": ts_pair(bb["middle"]),
            "lower": ts_pair(bb["lower"]),
        },
        "atr": ts_pair(atr),
        "ema9": ts_pair(calc_ema(closes, 9)),
        "ema21": ts_pair(calc_ema(closes, 21)),
        "ema50": ts_pair(calc_ema(closes, 50)),
        "ema200": ts_pair(calc_ema(closes, 200)),
        "stoch_rsi": {
            "k": ts_pair(stoch["k"]),
            "d": ts_pair(stoch["d"]),
        },
        "adx": {
            "adx": ts_pair(adx["adx"]),
            "dmi_plus": ts_pair(adx["dmi_plus"]),
            "dmi_minus": ts_pair(adx["dmi_minus"]),
        },
        "obv": ts_pair(obv),
        "williams_r": ts_pair(wr),
        "_raw": {
            "closes": closes,
            "highs": highs,
            "lows": lows,
            "volumes": volumes,
            "rsi": rsi,
            "macd": macd,
            "bb": bb,
            "atr": atr,
            "ema50": calc_ema(closes, 50),
            "ema200": calc_ema(closes, 200),
            "adx": adx,
            "stoch_rsi": stoch,
            "obv": obv,
            "williams_r": wr,
        },
    }


# ---------------------------------------------------------------------------
# Market Regime Detector — 4 states: BULL, BEAR, RANGE, CRISIS
# Uses trend (EMA50 vs EMA200), volatility (ATR percentile),
# directional strength (ADX), and Bollinger width.
# ---------------------------------------------------------------------------

class MarketRegimeDetector:

    REGIMES = ("BULL", "BEAR", "RANGE", "CRISIS")

    def detect(self, ohlcv, raw_indicators):
        closes = raw_indicators["closes"]
        if len(closes) < 50:
            return {"regime": "RANGE", "confidence": 0, "reasons": ["Insufficient data"]}

        ema50 = raw_indicators["ema50"]
        ema200 = raw_indicators["ema200"]
        atr = raw_indicators["atr"]
        adx_data = raw_indicators["adx"]
        bb = raw_indicators["bb"]

        score = {"BULL": 0, "BEAR": 0, "RANGE": 0, "CRISIS": 0}
        reasons = []

        # --- Trend: EMA 50 vs EMA 200 ---
        e50 = self._last_valid(ema50)
        e200 = self._last_valid(ema200)
        price = closes[-1]
        if e50 is not None and e200 is not None:
            if e50 > e200 and price > e50:
                score["BULL"] += 30
                reasons.append("Price above EMA50 > EMA200 (golden alignment)")
            elif e50 < e200 and price < e50:
                score["BEAR"] += 30
                reasons.append("Price below EMA50 < EMA200 (death alignment)")
            else:
                score["RANGE"] += 15
                reasons.append("EMAs mixed — no clear trend")
        elif e50 is not None:
            if price > e50:
                score["BULL"] += 15
            else:
                score["BEAR"] += 15

        # --- Momentum: price position relative to recent range ---
        lookback = min(50, len(closes))
        recent = closes[-lookback:]
        hi = max(recent)
        lo = min(recent)
        if hi != lo:
            position = (price - lo) / (hi - lo)
            if position > 0.75:
                score["BULL"] += 20
                reasons.append(f"Price at {position:.0%} of 50-bar range (upper)")
            elif position < 0.25:
                score["BEAR"] += 20
                reasons.append(f"Price at {position:.0%} of 50-bar range (lower)")
            else:
                score["RANGE"] += 15
                reasons.append(f"Price at {position:.0%} of 50-bar range (middle)")

        # --- Directional strength: ADX ---
        adx_val = self._last_valid(adx_data["adx"])
        if adx_val is not None:
            if adx_val > 25:
                dmi_p = self._last_valid(adx_data["dmi_plus"])
                dmi_m = self._last_valid(adx_data["dmi_minus"])
                if dmi_p is not None and dmi_m is not None:
                    if dmi_p > dmi_m:
                        score["BULL"] += 25
                        reasons.append(f"ADX {adx_val:.0f} strong + DMI+ leads")
                    else:
                        score["BEAR"] += 25
                        reasons.append(f"ADX {adx_val:.0f} strong + DMI- leads")
            else:
                score["RANGE"] += 25
                reasons.append(f"ADX {adx_val:.0f} weak — no directional bias")

        # --- Volatility: ATR as % of price ---
        atr_val = self._last_valid(atr)
        if atr_val is not None and price > 0:
            vol_pct = atr_val / price * 100
            atr_valid = [v for v in atr if v is not None]
            if len(atr_valid) >= 30:
                avg_atr = sum(atr_valid[-30:]) / 30
                vol_ratio = atr_val / avg_atr if avg_atr > 0 else 1.0
                if vol_ratio > 3.0:
                    score["CRISIS"] += 50
                    reasons.append(f"Volatility {vol_ratio:.1f}x average — CRISIS")
                elif vol_ratio > 2.0:
                    score["CRISIS"] += 25
                    reasons.append(f"Volatility {vol_ratio:.1f}x average — elevated")
                elif vol_ratio < 0.5:
                    score["RANGE"] += 15
                    reasons.append(f"Volatility {vol_ratio:.1f}x average — compressed")

        # --- Bollinger Band width ---
        bb_upper = self._last_valid(bb["upper"])
        bb_lower = self._last_valid(bb["lower"])
        bb_mid = self._last_valid(bb["middle"])
        if bb_upper and bb_lower and bb_mid and bb_mid > 0:
            bb_width = (bb_upper - bb_lower) / bb_mid * 100
            if bb_width < 2.0:
                score["RANGE"] += 15
                reasons.append(f"BB width {bb_width:.1f}% — squeeze")
            elif bb_width > 8.0:
                score["CRISIS"] += 10
                reasons.append(f"BB width {bb_width:.1f}% — expansion")

        # --- Pick winner ---
        regime = max(score, key=score.get)
        total = sum(score.values())
        confidence = int(score[regime] / total * 100) if total > 0 else 0

        return {
            "regime": regime,
            "confidence": confidence,
            "scores": score,
            "reasons": reasons,
        }

    @staticmethod
    def _last_valid(series):
        if not series:
            return None
        for v in reversed(series):
            if v is not None:
                return v
        return None


regime_detector = MarketRegimeDetector()


# ---------------------------------------------------------------------------
# Signal Engine — Multi-indicator weighted scoring
# Score: -300 (strong short) → +300 (strong long), confidence 0-100%
# ---------------------------------------------------------------------------

class SignalEngine:

    REGIME_MULTIPLIER = {"BULL": 1.0, "BEAR": 1.0, "RANGE": 0.6, "CRISIS": 0.3}

    def generate(self, raw_indicators, regime_info, sentiment=None, whales=None):
        closes = raw_indicators["closes"]
        if len(closes) < 30:
            return self._neutral("Insufficient data")

        components = []
        total_score = 0

        # --- RSI (weight ±70) ---
        rsi_vals = raw_indicators["rsi"]
        rsi = self._last_valid(rsi_vals)
        if rsi is not None:
            if rsi < 30:
                s = 70 * (30 - rsi) / 30
                components.append({"name": "RSI", "score": s, "detail": f"RSI {rsi:.0f} oversold"})
                total_score += s
            elif rsi > 70:
                s = -70 * (rsi - 70) / 30
                components.append({"name": "RSI", "score": s, "detail": f"RSI {rsi:.0f} overbought"})
                total_score += s
            else:
                components.append({"name": "RSI", "score": 0, "detail": f"RSI {rsi:.0f} neutral"})

        # --- MACD (weight ±60) ---
        macd = raw_indicators["macd"]
        ml = self._last_valid(macd["line"])
        ms = self._last_valid(macd["signal"])
        mh = self._last_valid(macd["histogram"])
        if ml is not None and ms is not None:
            if ml > ms and mh is not None and mh > 0:
                s = min(60, abs(mh) / (abs(ml) + 1e-9) * 60)
                components.append({"name": "MACD", "score": s, "detail": "MACD bullish crossover"})
                total_score += s
            elif ml < ms and mh is not None and mh < 0:
                s = -min(60, abs(mh) / (abs(ml) + 1e-9) * 60)
                components.append({"name": "MACD", "score": s, "detail": "MACD bearish crossover"})
                total_score += s
            else:
                components.append({"name": "MACD", "score": 0, "detail": "MACD neutral"})

        # --- Bollinger (weight ±50) ---
        bb = raw_indicators["bb"]
        bb_u = self._last_valid(bb["upper"])
        bb_l = self._last_valid(bb["lower"])
        bb_m = self._last_valid(bb["middle"])
        price = closes[-1]
        if bb_u and bb_l and bb_m:
            bb_range = bb_u - bb_l
            if bb_range > 0:
                pos = (price - bb_l) / bb_range
                if pos < 0.1:
                    s = 50 * (1 - pos * 10)
                    components.append({"name": "BB", "score": s, "detail": f"Price at lower BB ({pos:.0%})"})
                    total_score += s
                elif pos > 0.9:
                    s = -50 * ((pos - 0.9) * 10)
                    components.append({"name": "BB", "score": s, "detail": f"Price at upper BB ({pos:.0%})"})
                    total_score += s
                else:
                    components.append({"name": "BB", "score": 0, "detail": f"Price mid-BB ({pos:.0%})"})

        # --- EMA Alignment (weight ±80) ---
        ema50 = raw_indicators["ema50"]
        ema200 = raw_indicators["ema200"]
        e50 = self._last_valid(ema50)
        e200 = self._last_valid(ema200)
        if e50 is not None and e200 is not None:
            if price > e50 > e200:
                s = 80
                components.append({"name": "EMA", "score": s, "detail": "Full bullish alignment P>50>200"})
                total_score += s
            elif price < e50 < e200:
                s = -80
                components.append({"name": "EMA", "score": s, "detail": "Full bearish alignment P<50<200"})
                total_score += s
            elif price > e50:
                s = 30
                components.append({"name": "EMA", "score": s, "detail": "Price above EMA50"})
                total_score += s
            elif price < e50:
                s = -30
                components.append({"name": "EMA", "score": s, "detail": "Price below EMA50"})
                total_score += s

        # --- Stochastic RSI (weight ±40) ---
        stoch = raw_indicators["stoch_rsi"]
        sk = self._last_valid(stoch["k"])
        sd = self._last_valid(stoch["d"])
        if sk is not None:
            if sk < 20:
                s = 40 * (20 - sk) / 20
                components.append({"name": "StochRSI", "score": s, "detail": f"StochRSI K={sk:.0f} oversold"})
                total_score += s
            elif sk > 80:
                s = -40 * (sk - 80) / 20
                components.append({"name": "StochRSI", "score": s, "detail": f"StochRSI K={sk:.0f} overbought"})
                total_score += s
            else:
                components.append({"name": "StochRSI", "score": 0, "detail": f"StochRSI K={sk:.0f} neutral"})

        # --- Williams %R (weight ±30) ---
        wr = self._last_valid(raw_indicators["williams_r"])
        if wr is not None:
            if wr < -80:
                s = 30 * (-80 - wr) / 20
                components.append({"name": "Williams%R", "score": s, "detail": f"W%R {wr:.0f} oversold"})
                total_score += s
            elif wr > -20:
                s = -30 * (wr + 20) / 20
                components.append({"name": "Williams%R", "score": s, "detail": f"W%R {wr:.0f} overbought"})
                total_score += s
            else:
                components.append({"name": "Williams%R", "score": 0, "detail": f"W%R {wr:.0f} neutral"})

        # --- Sentiment: Funding Rate (weight ±40) ---
        if sentiment and "funding_rate" in sentiment:
            fr = sentiment["funding_rate"]
            if fr > 0.05:
                s = -40
                components.append({"name": "Funding", "score": s, "detail": f"Extreme positive funding {fr:.4f}"})
                total_score += s
            elif fr < -0.05:
                s = 40
                components.append({"name": "Funding", "score": s, "detail": f"Extreme negative funding {fr:.4f}"})
                total_score += s

        # --- Sentiment: Fear & Greed (weight ±30) ---
        if sentiment and "fear_greed" in sentiment:
            fg = sentiment["fear_greed"]
            if fg < 20:
                s = 30
                components.append({"name": "F&G", "score": s, "detail": f"Extreme Fear ({fg})"})
                total_score += s
            elif fg > 80:
                s = -30
                components.append({"name": "F&G", "score": s, "detail": f"Extreme Greed ({fg})"})
                total_score += s

        # --- Sentiment divergence (weight ±50) ---
        if sentiment and "long_short_ratio" in sentiment:
            lsr = sentiment["long_short_ratio"]
            if lsr > 3.0 and total_score < 0:
                s = -50
                components.append({"name": "Divergence", "score": s, "detail": f"Crowd long ({lsr:.1f}) vs bearish signal"})
                total_score += s
            elif lsr < 0.5 and total_score > 0:
                s = 50
                components.append({"name": "Divergence", "score": s, "detail": f"Crowd short ({lsr:.1f}) vs bullish signal"})
                total_score += s

        # --- Whales (weight ±30) ---
        if whales and "net_flow" in whales:
            nf = whales["net_flow"]
            if nf > 0:
                s = 30
                components.append({"name": "Whales", "score": s, "detail": "Whale accumulation detected"})
                total_score += s
            elif nf < 0:
                s = -30
                components.append({"name": "Whales", "score": s, "detail": "Whale distribution detected"})
                total_score += s

        # --- Apply regime multiplier ---
        regime = regime_info.get("regime", "RANGE")
        multiplier = self.REGIME_MULTIPLIER.get(regime, 1.0)
        adjusted_score = total_score * multiplier

        # --- Clamp and determine direction ---
        adjusted_score = max(-300, min(300, adjusted_score))
        if adjusted_score > 50:
            direction = "LONG"
        elif adjusted_score < -50:
            direction = "SHORT"
        else:
            direction = "NEUTRAL"

        # --- Confidence: how many indicators agree ---
        agreeing = sum(1 for c in components if (c["score"] > 0) == (adjusted_score > 0) and c["score"] != 0)
        total_active = sum(1 for c in components if c["score"] != 0)
        confidence = int(agreeing / max(total_active, 1) * 100)

        reasons = [c["detail"] for c in components if c["score"] != 0]

        return {
            "direction": direction,
            "score": round(adjusted_score, 1),
            "raw_score": round(total_score, 1),
            "confidence": confidence,
            "regime": regime,
            "regime_multiplier": multiplier,
            "components": components,
            "reasons": reasons,
        }

    def _neutral(self, reason):
        return {
            "direction": "NEUTRAL", "score": 0, "raw_score": 0,
            "confidence": 0, "regime": "RANGE", "regime_multiplier": 1.0,
            "components": [], "reasons": [reason],
        }

    @staticmethod
    def _last_valid(series):
        if not series:
            return None
        for v in reversed(series):
            if v is not None:
                return v
        return None


signal_engine = SignalEngine()


# ---------------------------------------------------------------------------
# Risk Engine — Absolute veto system
# Any single veto condition blocks trade execution entirely.
# ---------------------------------------------------------------------------

class RiskEngine:

    DRAWDOWN_LEVELS = [
        {"level": "green", "threshold": 5.0, "label": "Safe"},
        {"level": "yellow", "threshold": 5.0, "label": "Caution"},
        {"level": "orange", "threshold": 10.0, "label": "Warning"},
        {"level": "red", "threshold": 15.0, "label": "Critical"},
    ]

    def check(self, signal, portfolio_state=None):
        portfolio_state = portfolio_state or {}
        vetoes = []
        warnings = []

        confidence = signal.get("confidence", 0)
        regime = signal.get("regime", "RANGE")
        direction = signal.get("direction", "NEUTRAL")

        # Veto 1: Low confidence
        if confidence < 30:
            vetoes.append(f"Confidence too low ({confidence}% < 30%)")

        # Veto 2: CRISIS regime
        if regime == "CRISIS":
            vetoes.append("Market in CRISIS regime — all trading suspended")

        # Veto 3: Daily loss >= 5%
        daily_pnl_pct = portfolio_state.get("daily_pnl_pct", 0)
        if daily_pnl_pct <= -5.0:
            vetoes.append(f"Daily loss {daily_pnl_pct:.1f}% exceeds -5% limit")

        # Veto 4: Kill switch active
        if self._is_kill_switch_active():
            vetoes.append("Kill switch is active")

        # Veto 5: Event mode (economic calendar)
        event = self._check_event_mode()
        if event:
            vetoes.append(f"Event mode active: {event}")

        # Veto 6: Drawdown > 15%
        drawdown = portfolio_state.get("drawdown_pct", 0)
        if drawdown >= 15.0:
            vetoes.append(f"Drawdown {drawdown:.1f}% exceeds 15% limit")

        # Veto 7: NEUTRAL signal
        if direction == "NEUTRAL":
            vetoes.append("Signal is NEUTRAL — no trade direction")

        # Warnings (non-blocking)
        if 30 <= confidence < 50:
            warnings.append(f"Low confidence ({confidence}%)")
        if 5.0 <= drawdown < 15.0:
            warnings.append(f"Elevated drawdown ({drawdown:.1f}%)")
        if daily_pnl_pct <= -3.0:
            warnings.append(f"Significant daily loss ({daily_pnl_pct:.1f}%)")

        return {
            "approved": len(vetoes) == 0,
            "vetoed": len(vetoes) > 0,
            "vetoes": vetoes,
            "warnings": warnings,
            "veto_count": len(vetoes),
        }

    def _is_kill_switch_active(self):
        try:
            conn = get_db()
            row = conn.execute("SELECT active FROM killswitch WHERE id = 1").fetchone()
            conn.close()
            return bool(row and row["active"])
        except Exception:
            return False

    def _check_event_mode(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for cal in ECONOMIC_CALENDAR:
            if today in cal["dates"] and cal["impact"] == "high":
                return cal["event"]
        return None

    def get_drawdown_status(self):
        try:
            conn = get_db()
            trades = conn.execute(
                "SELECT pnl FROM paper_trades WHERE status = 'closed' ORDER BY closed_at DESC LIMIT 100"
            ).fetchall()
            conn.close()
        except Exception:
            trades = []

        if not trades:
            return {"drawdown_pct": 0, "level": "green", "label": "Safe", "peak": 0, "current": 0}

        pnls = [t["pnl"] for t in trades]
        equity_curve = []
        running = 0
        for pnl in reversed(pnls):
            running += pnl
            equity_curve.append(running)

        if not equity_curve:
            return {"drawdown_pct": 0, "level": "green", "label": "Safe", "peak": 0, "current": 0}

        peak = equity_curve[0]
        max_dd = 0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd

        dd_pct = (max_dd / peak * 100) if peak > 0 else 0

        if dd_pct >= 15:
            level, label = "red", "Critical"
        elif dd_pct >= 10:
            level, label = "orange", "Warning"
        elif dd_pct >= 5:
            level, label = "yellow", "Caution"
        else:
            level, label = "green", "Safe"

        return {
            "drawdown_pct": round(dd_pct, 2),
            "level": level,
            "label": label,
            "peak": round(peak, 2),
            "current": round(equity_curve[-1], 2),
            "max_drawdown_abs": round(max_dd, 2),
        }

    def get_daily_pnl(self):
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            conn = get_db()
            row = conn.execute(
                "SELECT COALESCE(SUM(pnl), 0) as total FROM paper_trades WHERE status = 'closed' AND closed_at LIKE ?",
                (f"{today}%",),
            ).fetchone()
            conn.close()
            return row["total"] if row else 0
        except Exception:
            return 0


risk_engine = RiskEngine()


# ---------------------------------------------------------------------------
# Dip/Top Detectors — 4 algorithms + confluence scorer
# ---------------------------------------------------------------------------

class DipTopDetector:

    def detect_rsi_divergence(self, closes, rsi, lookback=30):
        n = len(closes)
        if n < lookback + 5 or len(rsi) < n:
            return {"bullish": False, "bearish": False, "detail": "Insufficient data"}

        segment_c = closes[-lookback:]
        segment_r = [v for v in rsi[-lookback:] if v is not None]
        if len(segment_r) < lookback // 2:
            return {"bullish": False, "bearish": False, "detail": "Not enough RSI data"}

        # Find two recent swing lows/highs in price
        lows_idx = self._find_swing_points(segment_c, mode="low")
        highs_idx = self._find_swing_points(segment_c, mode="high")

        bullish = False
        bearish = False
        detail = "No divergence"

        # Bullish divergence: price makes lower low, RSI makes higher low
        if len(lows_idx) >= 2:
            i1, i2 = lows_idx[-2], lows_idx[-1]
            if i2 < len(segment_r) and i1 < len(segment_r):
                if segment_c[i2] < segment_c[i1] and segment_r[i2] > segment_r[i1]:
                    bullish = True
                    detail = f"Bullish divergence: price LL, RSI HL at bar {i2}"

        # Bearish divergence: price makes higher high, RSI makes lower high
        if len(highs_idx) >= 2:
            i1, i2 = highs_idx[-2], highs_idx[-1]
            if i2 < len(segment_r) and i1 < len(segment_r):
                if segment_c[i2] > segment_c[i1] and segment_r[i2] < segment_r[i1]:
                    bearish = True
                    detail = f"Bearish divergence: price HH, RSI LH at bar {i2}"

        return {"bullish": bullish, "bearish": bearish, "detail": detail}

    def detect_volume_climax(self, volumes, closes, lookback=20):
        if len(volumes) < lookback + 1:
            return {"selling_climax": False, "buying_climax": False, "detail": "Insufficient data"}

        recent_vol = volumes[-lookback:]
        avg_vol = sum(recent_vol) / len(recent_vol)
        last_vol = volumes[-1]
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 0

        price_change = closes[-1] - closes[-2] if len(closes) >= 2 else 0

        selling_climax = vol_ratio > 3.0 and price_change < 0
        buying_climax = vol_ratio > 3.0 and price_change > 0

        detail = f"Vol ratio {vol_ratio:.1f}x avg"
        if selling_climax:
            detail = f"SELLING CLIMAX — {vol_ratio:.1f}x avg volume on down move"
        elif buying_climax:
            detail = f"BUYING CLIMAX — {vol_ratio:.1f}x avg volume on up move"

        return {
            "selling_climax": selling_climax,
            "buying_climax": buying_climax,
            "vol_ratio": round(vol_ratio, 2),
            "detail": detail,
        }

    def detect_wyckoff_spring(self, ohlcv, lookback=50):
        if len(ohlcv) < lookback + 3:
            return {"spring": False, "upthrust": False, "detail": "Insufficient data"}

        closes = [c["close"] for c in ohlcv]
        lows = [c["low"] for c in ohlcv]
        highs = [c["high"] for c in ohlcv]

        range_lows = lows[-lookback:-3]
        range_highs = highs[-lookback:-3]
        if not range_lows or not range_highs:
            return {"spring": False, "upthrust": False, "detail": "No range data"}

        support = min(range_lows)
        resistance = max(range_highs)

        last_low = lows[-1]
        last_close = closes[-1]
        prev_close = closes[-2]
        last_high = highs[-1]

        # Spring: price dips below support then closes back above it
        spring = last_low < support and last_close > support and last_close > prev_close

        # Upthrust: price pushes above resistance then closes back below it
        upthrust = last_high > resistance and last_close < resistance and last_close < prev_close

        detail = "No Wyckoff pattern"
        if spring:
            detail = f"SPRING — pierced support {support:.2f}, recovered to {last_close:.2f}"
        elif upthrust:
            detail = f"UPTHRUST — pierced resistance {resistance:.2f}, rejected to {last_close:.2f}"

        return {
            "spring": spring,
            "upthrust": upthrust,
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "detail": detail,
        }

    def confluence_score(self, ohlcv, raw_indicators):
        closes = raw_indicators["closes"]
        volumes = raw_indicators["volumes"]
        rsi = raw_indicators["rsi"]

        score = 0
        signals = []

        # RSI divergence (max 30 points)
        div = self.detect_rsi_divergence(closes, rsi)
        if div["bullish"]:
            score += 30
            signals.append("RSI bullish divergence (+30)")
        elif div["bearish"]:
            score += 25
            signals.append("RSI bearish divergence (+25)")

        # Volume climax (max 25 points)
        vc = self.detect_volume_climax(volumes, closes)
        if vc["selling_climax"]:
            score += 25
            signals.append("Selling climax (+25)")
        elif vc["buying_climax"]:
            score += 20
            signals.append("Buying climax (+20)")
        elif vc.get("vol_ratio", 0) > 2.0:
            score += 10
            signals.append(f"High volume {vc['vol_ratio']:.1f}x (+10)")

        # Wyckoff (max 30 points)
        wy = self.detect_wyckoff_spring(ohlcv)
        if wy["spring"]:
            score += 30
            signals.append("Wyckoff Spring (+30)")
        elif wy["upthrust"]:
            score += 25
            signals.append("Wyckoff Upthrust (+25)")

        # RSI extremes (max 15 points)
        last_rsi = None
        for v in reversed(rsi):
            if v is not None:
                last_rsi = v
                break
        if last_rsi is not None:
            if last_rsi < 25 or last_rsi > 75:
                score += 15
                signals.append(f"RSI extreme ({last_rsi:.0f}) (+15)")
            elif last_rsi < 35 or last_rsi > 65:
                score += 5
                signals.append(f"RSI extended ({last_rsi:.0f}) (+5)")

        score = min(score, 100)
        return {"score": score, "signals": signals, "strong": score >= 70}

    def analyze(self, symbol, ohlcv, raw_indicators):
        closes = raw_indicators["closes"]
        volumes = raw_indicators["volumes"]
        rsi = raw_indicators["rsi"]

        rsi_div = self.detect_rsi_divergence(closes, rsi)
        vol_climax = self.detect_volume_climax(volumes, closes)
        wyckoff = self.detect_wyckoff_spring(ohlcv)
        confluence = self.confluence_score(ohlcv, raw_indicators)

        is_dip = rsi_div["bullish"] or vol_climax["selling_climax"] or wyckoff["spring"]
        is_top = rsi_div["bearish"] or vol_climax["buying_climax"] or wyckoff["upthrust"]

        return {
            "symbol": symbol,
            "is_dip": is_dip,
            "is_top": is_top,
            "rsi_divergence": rsi_div,
            "volume_climax": vol_climax,
            "wyckoff": wyckoff,
            "confluence": confluence,
            "alert": "DIP" if is_dip else ("TOP" if is_top else None),
        }

    @staticmethod
    def _find_swing_points(data, mode="low", window=3):
        points = []
        for i in range(window, len(data) - window):
            segment = data[i - window:i + window + 1]
            if mode == "low" and data[i] == min(segment):
                points.append(i)
            elif mode == "high" and data[i] == max(segment):
                points.append(i)
        return points


dip_top_detector = DipTopDetector()


# ---------------------------------------------------------------------------
# Exchange Adapters — Abstract base + MEXC implementation
# ---------------------------------------------------------------------------

class ExchangeAdapter(ABC):

    def __init__(self, name, api_key="", api_secret="", passphrase="", testnet=False):
        self.name = name
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.testnet = testnet

    @abstractmethod
    def get_balance(self):
        pass

    @abstractmethod
    def get_positions(self):
        pass

    @abstractmethod
    def place_order(self, symbol, side, order_type, quantity, price=None, leverage=1, tp=None, sl=None):
        pass

    @abstractmethod
    def close_position(self, symbol, position_id=None):
        pass

    @abstractmethod
    def test_connection(self):
        pass


class MEXCAdapter(ExchangeAdapter):

    SPOT_BASE = "https://api.mexc.com"

    def __init__(self, api_key="", api_secret="", testnet=False):
        super().__init__("MEXC", api_key, api_secret, testnet=testnet)
        self._exchange = None
        if HAS_CCXT and api_key:
            try:
                self._exchange = ccxt.mexc({
                    "apiKey": api_key,
                    "secret": api_secret,
                    "sandbox": testnet,
                    "enableRateLimit": True,
                    "options": {"defaultType": "spot"},
                })
            except Exception as e:
                log.warning("CCXT MEXC init failed: %s", e)

    def get_balance(self):
        if not self._exchange:
            return self._no_exchange()
        try:
            bal = self._exchange.fetch_balance()
            assets = {}
            for currency, info in bal.get("total", {}).items():
                if info and float(info) > 0:
                    assets[currency] = {
                        "total": float(info),
                        "free": float(bal["free"].get(currency, 0)),
                        "used": float(bal["used"].get(currency, 0)),
                    }
            total_usdt = sum(
                a["total"] for c, a in assets.items() if c == "USDT"
            )
            return {"exchange": self.name, "assets": assets, "total_usdt": total_usdt}
        except Exception as e:
            return {"exchange": self.name, "error": str(e), "assets": {}}

    def get_positions(self):
        if not self._exchange:
            return []
        try:
            bal = self._exchange.fetch_balance()
            positions = []
            for currency, info in bal.get("total", {}).items():
                amount = float(info) if info else 0
                if amount > 0 and currency != "USDT":
                    positions.append({
                        "symbol": f"{currency}USDT",
                        "side": "long",
                        "quantity": amount,
                        "entry_price": 0,
                        "current_price": 0,
                        "pnl": 0,
                        "exchange": self.name,
                        "type": "spot",
                    })
            return positions
        except Exception as e:
            log.warning("MEXC get_positions failed: %s", e)
            return []

    def place_order(self, symbol, side, order_type, quantity, price=None, leverage=1, tp=None, sl=None):
        if not self._exchange:
            return self._no_exchange()
        try:
            params = {}
            if order_type == "limit" and price:
                order = self._exchange.create_order(symbol, "limit", side, quantity, price, params)
            else:
                order = self._exchange.create_order(symbol, "market", side, quantity, None, params)
            return {
                "success": True,
                "order_id": order.get("id"),
                "symbol": symbol,
                "side": side,
                "type": order_type,
                "quantity": quantity,
                "price": price or order.get("average", 0),
                "exchange": self.name,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "exchange": self.name}

    def close_position(self, symbol, position_id=None):
        if not self._exchange:
            return self._no_exchange()
        try:
            positions = self.get_positions()
            target = None
            for p in positions:
                if p["symbol"] == symbol:
                    target = p
                    break
            if not target:
                return {"success": False, "error": f"No position found for {symbol}"}
            order = self._exchange.create_order(symbol, "market", "sell", target["quantity"])
            return {"success": True, "order_id": order.get("id"), "closed": symbol}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def test_connection(self):
        if not self._exchange:
            if not self.api_key:
                return {"connected": False, "error": "No API key configured"}
            return {"connected": False, "error": "CCXT not installed"}
        try:
            self._exchange.fetch_time()
            return {"connected": True, "exchange": self.name, "testnet": self.testnet}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    @staticmethod
    def _no_exchange():
        return {
            "exchange": "MEXC",
            "error": "CCXT not available or no API key configured",
            "assets": {},
        }


# ---------------------------------------------------------------------------
# GMX Adapter — Placeholder (Arbitrum on-chain, requires web3.py)
# ---------------------------------------------------------------------------

class GMXAdapter(ExchangeAdapter):

    def __init__(self, private_key="", rpc_url="https://arb1.arbitrum.io/rpc", testnet=False):
        super().__init__("GMX", testnet=testnet)
        self.private_key = private_key
        self.rpc_url = rpc_url

    def get_balance(self):
        return {"exchange": "GMX", "error": "GMX adapter not yet implemented (requires web3.py)", "assets": {}}

    def get_positions(self):
        return []

    def place_order(self, symbol, side, order_type, quantity, price=None, leverage=1, tp=None, sl=None):
        return {"success": False, "error": "GMX on-chain execution not yet implemented", "exchange": "GMX"}

    def close_position(self, symbol, position_id=None):
        return {"success": False, "error": "GMX on-chain close not yet implemented"}

    def test_connection(self):
        try:
            resp = requests.get(self.rpc_url, timeout=3, json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1})
            if resp.status_code == 200:
                return {"connected": True, "exchange": "GMX", "network": "Arbitrum", "testnet": self.testnet}
        except Exception:
            pass
        return {"connected": False, "error": "Cannot reach Arbitrum RPC"}


# ---------------------------------------------------------------------------
# Exchange Manager — Multi-exchange routing + persistence
# ---------------------------------------------------------------------------

class ExchangeManager:

    def __init__(self):
        self._adapters = {}

    def add_exchange(self, name, exchange_type, api_key, api_secret, passphrase="", testnet=False):
        key_enc = encrypt_string(api_key)
        secret_enc = encrypt_string(api_secret)
        pass_enc = encrypt_string(passphrase) if passphrase else ""
        conn = get_db()
        conn.execute(
            "INSERT INTO exchanges (name, exchange_type, api_key_enc, api_secret_enc, passphrase_enc, is_testnet) VALUES (?, ?, ?, ?, ?, ?)",
            (name, exchange_type, key_enc, secret_enc, pass_enc, int(testnet)),
        )
        conn.commit()
        conn.close()
        adapter = self._create_adapter(exchange_type, api_key, api_secret, passphrase, testnet)
        if adapter:
            self._adapters[name] = adapter
        return {"success": True, "name": name, "type": exchange_type}

    def list_exchanges(self):
        conn = get_db()
        rows = conn.execute("SELECT id, name, exchange_type, is_testnet, created_at FROM exchanges").fetchall()
        conn.close()
        return [{"id": r["id"], "name": r["name"], "type": r["exchange_type"],
                 "testnet": bool(r["is_testnet"]), "created_at": r["created_at"],
                 "connected": r["name"] in self._adapters} for r in rows]

    def remove_exchange(self, exchange_id):
        conn = get_db()
        row = conn.execute("SELECT name FROM exchanges WHERE id = ?", (exchange_id,)).fetchone()
        if row:
            self._adapters.pop(row["name"], None)
            conn.execute("DELETE FROM exchanges WHERE id = ?", (exchange_id,))
            conn.commit()
        conn.close()
        return {"success": bool(row)}

    def test_exchange(self, exchange_id):
        conn = get_db()
        row = conn.execute("SELECT * FROM exchanges WHERE id = ?", (exchange_id,)).fetchone()
        conn.close()
        if not row:
            return {"connected": False, "error": "Exchange not found"}
        api_key = decrypt_string(row["api_key_enc"])
        api_secret = decrypt_string(row["api_secret_enc"])
        adapter = self._create_adapter(row["exchange_type"], api_key, api_secret, "", bool(row["is_testnet"]))
        if not adapter:
            return {"connected": False, "error": f"Unknown exchange type: {row['exchange_type']}"}
        return adapter.test_connection()

    def get_all_balances(self):
        balances = []
        for name, adapter in self._adapters.items():
            balances.append(adapter.get_balance())
        return balances

    def get_all_positions(self):
        positions = []
        for name, adapter in self._adapters.items():
            positions.extend(adapter.get_positions())
        return positions

    def load_from_db(self):
        conn = get_db()
        rows = conn.execute("SELECT * FROM exchanges").fetchall()
        conn.close()
        for row in rows:
            try:
                api_key = decrypt_string(row["api_key_enc"])
                api_secret = decrypt_string(row["api_secret_enc"])
                adapter = self._create_adapter(row["exchange_type"], api_key, api_secret, "", bool(row["is_testnet"]))
                if adapter:
                    self._adapters[row["name"]] = adapter
            except Exception as e:
                log.warning("Failed to load exchange %s: %s", row["name"], e)

    @staticmethod
    def _create_adapter(exchange_type, api_key, api_secret, passphrase="", testnet=False):
        t = exchange_type.lower()
        if t == "mexc":
            return MEXCAdapter(api_key, api_secret, testnet)
        elif t == "gmx":
            return GMXAdapter(private_key=api_key, testnet=testnet)
        return None


# ---------------------------------------------------------------------------
# Micro Position Engine — Conservative risk management
# ---------------------------------------------------------------------------

class MicroPositionEngine:

    MAX_CAPITAL_PCT = 5.0
    MAX_POSITIONS = 5
    DEFAULT_SIZE_USD = 10.0
    LIQUIDATION_STOP_PCT = 80.0

    def validate_order(self, symbol, side, quantity, price, leverage, balance_usdt):
        issues = []
        position_value = quantity * price
        margin_required = position_value / leverage if leverage > 0 else position_value

        if margin_required > balance_usdt * (self.MAX_CAPITAL_PCT / 100):
            issues.append(f"Position exceeds {self.MAX_CAPITAL_PCT}% of capital (${margin_required:.2f} vs ${balance_usdt * self.MAX_CAPITAL_PCT / 100:.2f})")

        if margin_required > self.DEFAULT_SIZE_USD * 5:
            issues.append(f"Position size ${margin_required:.2f} exceeds 5x default (${self.DEFAULT_SIZE_USD * 5:.2f})")

        if leverage > 20:
            issues.append(f"Leverage {leverage}x exceeds recommended max 20x")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "margin_required": round(margin_required, 2),
            "position_value": round(position_value, 2),
            "liquidation_price": self._calc_liquidation(price, side, leverage),
            "stop_loss_suggested": self._calc_stop(price, side, leverage),
        }

    def _calc_liquidation(self, entry, side, leverage):
        if leverage <= 1:
            return 0
        move = 1.0 / leverage
        if side == "long":
            return round(entry * (1 - move), 2)
        return round(entry * (1 + move), 2)

    def _calc_stop(self, entry, side, leverage):
        liq = self._calc_liquidation(entry, side, leverage)
        if liq == 0:
            return 0
        pct = self.LIQUIDATION_STOP_PCT / 100
        if side == "long":
            return round(entry - (entry - liq) * pct, 2)
        return round(entry + (liq - entry) * pct, 2)


# ---------------------------------------------------------------------------
# Paper Trader — Virtual execution with 50-trade gate
# ---------------------------------------------------------------------------

class PaperTrader:

    REQUIRED_TRADES = 50

    def execute(self, symbol, side, quantity, price, leverage=1, tp=None, sl=None):
        conn = get_db()
        conn.execute(
            "INSERT INTO paper_trades (symbol, side, entry_price, quantity, leverage, status) VALUES (?, ?, ?, ?, ?, 'open')",
            (symbol, side, price, quantity, leverage),
        )
        conn.commit()
        trade_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        log.info("Paper trade opened: %s %s %s @ %.2f (x%d)", trade_id, side, symbol, price, leverage)
        return {
            "success": True, "trade_id": trade_id, "mode": "paper",
            "symbol": symbol, "side": side, "entry_price": price,
            "quantity": quantity, "leverage": leverage,
        }

    def close(self, trade_id, exit_price):
        conn = get_db()
        row = conn.execute("SELECT * FROM paper_trades WHERE id = ? AND status = 'open'", (trade_id,)).fetchone()
        if not row:
            conn.close()
            return {"success": False, "error": "Trade not found or already closed"}
        entry = row["entry_price"]
        qty = row["quantity"]
        lev = row["leverage"]
        side = row["side"]
        if side == "long":
            pnl = (exit_price - entry) / entry * qty * lev
        else:
            pnl = (entry - exit_price) / entry * qty * lev
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE paper_trades SET exit_price = ?, pnl = ?, status = 'closed', closed_at = ? WHERE id = ?",
            (exit_price, pnl, now, trade_id),
        )
        conn.commit()
        conn.close()
        log.info("Paper trade closed: %s pnl=%.4f", trade_id, pnl)
        return {"success": True, "trade_id": trade_id, "pnl": round(pnl, 4), "exit_price": exit_price}

    def get_open_positions(self):
        conn = get_db()
        rows = conn.execute("SELECT * FROM paper_trades WHERE status = 'open' ORDER BY opened_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_status(self):
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) as c FROM paper_trades WHERE status = 'closed'").fetchone()["c"]
        wins = conn.execute("SELECT COUNT(*) as c FROM paper_trades WHERE status = 'closed' AND pnl > 0").fetchone()["c"]
        total_pnl = conn.execute("SELECT COALESCE(SUM(pnl), 0) as s FROM paper_trades WHERE status = 'closed'").fetchone()["s"]
        open_count = conn.execute("SELECT COUNT(*) as c FROM paper_trades WHERE status = 'open'").fetchone()["c"]
        conn.close()
        win_rate = (wins / total * 100) if total > 0 else 0
        return {
            "total_trades": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 4),
            "open_positions": open_count,
            "required": self.REQUIRED_TRADES,
            "is_live_allowed": total >= self.REQUIRED_TRADES,
            "remaining": max(0, self.REQUIRED_TRADES - total),
        }

    def get_history(self, limit=50):
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM paper_trades WHERE status = 'closed' ORDER BY closed_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


# Global instances
exchange_manager = ExchangeManager()
micro_engine = MicroPositionEngine()
paper_trader = PaperTrader()


# ===========================================================================
# API ROUTES — Market Data (5 routes)
# ===========================================================================

@app.route("/api/candles")
def api_candles():
    symbol = request.args.get("symbol", "BTCUSDT").upper()
    interval = request.args.get("interval", "1h")
    limit = min(int(request.args.get("limit", 500)), 1500)

    sym_info = SUPPORTED_SYMBOLS.get(symbol)
    if not sym_info:
        return jsonify({"error": f"Unsupported symbol: {symbol}"}), 400

    if sym_info["source"] == "stooq":
        candles = generate_gold_silver_candles(sym_info, limit)
        return jsonify(candles)

    if interval not in INTERVALS:
        return jsonify({"error": f"Invalid interval: {interval}"}), 400

    raw = fetch_binance("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit}, ttl=10)
    if raw is None:
        return jsonify({"error": "Failed to fetch candles from Binance"}), 502
    return jsonify(transform_klines(raw))


@app.route("/api/price")
def api_price():
    symbol = request.args.get("symbol", "BTCUSDT").upper()
    sym_info = SUPPORTED_SYMBOLS.get(symbol)
    if not sym_info:
        return jsonify({"error": f"Unsupported symbol: {symbol}"}), 400

    if sym_info["source"] == "stooq":
        data = fetch_stooq_price(sym_info)
        if not data:
            return jsonify({"error": "Failed to fetch price from Stooq"}), 502
        return jsonify(data)

    ticker = fetch_binance("/api/v3/ticker/24hr", {"symbol": symbol}, ttl=5)
    if not ticker:
        return jsonify({"error": "Failed to fetch price from Binance"}), 502

    return jsonify({
        "symbol": symbol,
        "price": float(ticker.get("lastPrice", 0)),
        "change_24h": float(ticker.get("priceChange", 0)),
        "change_24h_pct": float(ticker.get("priceChangePercent", 0)),
        "high_24h": float(ticker.get("highPrice", 0)),
        "low_24h": float(ticker.get("lowPrice", 0)),
        "volume_24h": float(ticker.get("volume", 0)),
        "quote_volume": float(ticker.get("quoteVolume", 0)),
        "weighted_avg": float(ticker.get("weightedAvgPrice", 0)),
        "source": "binance",
    })


@app.route("/api/orderbook")
def api_orderbook():
    symbol = request.args.get("symbol", "BTCUSDT").upper()
    limit = min(int(request.args.get("limit", 20)), 100)

    sym_info = SUPPORTED_SYMBOLS.get(symbol)
    if not sym_info or sym_info["source"] != "binance":
        return jsonify({"bids": [], "asks": [], "spread": 0, "spread_pct": 0})

    data = fetch_binance("/api/v3/depth", {"symbol": symbol, "limit": limit}, ttl=2)
    if not data:
        return jsonify({"error": "Failed to fetch order book"}), 502

    bids = [[float(p), float(q)] for p, q in data.get("bids", [])]
    asks = [[float(p), float(q)] for p, q in data.get("asks", [])]

    best_bid = bids[0][0] if bids else 0
    best_ask = asks[0][0] if asks else 0
    spread = best_ask - best_bid
    spread_pct = (spread / best_ask * 100) if best_ask > 0 else 0

    total_bid_vol = sum(q for _, q in bids)
    total_ask_vol = sum(q for _, q in asks)
    total = total_bid_vol + total_ask_vol
    buy_ratio = (total_bid_vol / total * 100) if total > 0 else 50

    return jsonify({
        "bids": bids,
        "asks": asks,
        "spread": round(spread, 8),
        "spread_pct": round(spread_pct, 4),
        "best_bid": best_bid,
        "best_ask": best_ask,
        "buy_ratio": round(buy_ratio, 1),
        "sell_ratio": round(100 - buy_ratio, 1),
    })


@app.route("/api/trades")
def api_trades():
    symbol = request.args.get("symbol", "BTCUSDT").upper()
    limit = min(int(request.args.get("limit", 30)), 100)

    sym_info = SUPPORTED_SYMBOLS.get(symbol)
    if not sym_info or sym_info["source"] != "binance":
        return jsonify([])

    data = fetch_binance("/api/v3/trades", {"symbol": symbol, "limit": limit}, ttl=3)
    if not data:
        return jsonify([])

    return jsonify([
        {
            "id": t["id"],
            "price": float(t["price"]),
            "quantity": float(t["qty"]),
            "quote_qty": float(t["quoteQty"]),
            "time": t["time"],
            "is_buyer_maker": t["isBuyerMaker"],
            "side": "sell" if t["isBuyerMaker"] else "buy",
        }
        for t in data
    ])


@app.route("/api/ticker")
def api_ticker():
    pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
    result = []

    data = fetch_binance("/api/v3/ticker/price", ttl=5)
    if not data:
        return jsonify([])

    price_map = {item["symbol"]: float(item["price"]) for item in data}

    for pair in pairs:
        if pair in price_map:
            ticker_24h = fetch_binance("/api/v3/ticker/24hr", {"symbol": pair}, ttl=15)
            change_pct = float(ticker_24h.get("priceChangePercent", 0)) if ticker_24h else 0
            result.append({
                "symbol": pair,
                "base": SUPPORTED_SYMBOLS[pair]["base"],
                "price": price_map[pair],
                "change_pct": change_pct,
                "high": float(ticker_24h.get("highPrice", 0)) if ticker_24h else 0,
                "low": float(ticker_24h.get("lowPrice", 0)) if ticker_24h else 0,
                "volume": float(ticker_24h.get("quoteVolume", 0)) if ticker_24h else 0,
            })

    for sym_key in ("GOLD", "SILVER"):
        sym_info = SUPPORTED_SYMBOLS[sym_key]
        stooq = fetch_stooq_price(sym_info)
        if stooq and stooq["price"]:
            result.append({
                "symbol": sym_key,
                "base": sym_info["base"],
                "price": stooq["price"],
                "change_pct": 0,
                "high": 0,
                "low": 0,
                "volume": 0,
            })

    return jsonify({"tickers": result})


# ===========================================================================
# API ROUTES — Indicators & Intelligence (3 routes)
# ===========================================================================

@app.route("/api/indicators")
def api_indicators():
    symbol = request.args.get("symbol", "BTCUSDT").upper()
    interval = request.args.get("interval", "1h")
    limit = min(int(request.args.get("limit", 500)), 1500)

    sym_info = SUPPORTED_SYMBOLS.get(symbol)
    if not sym_info:
        return jsonify({"error": f"Unsupported symbol: {symbol}"}), 400

    if sym_info["source"] == "stooq":
        ohlcv = generate_gold_silver_candles(sym_info, limit)
    else:
        raw = fetch_binance("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit}, ttl=10)
        if not raw:
            return jsonify({"error": "Failed to fetch candles"}), 502
        ohlcv = transform_klines(raw)

    if len(ohlcv) < 30:
        return jsonify({"error": "Not enough data for indicators", "candles": len(ohlcv)}), 400

    indicators = compute_all_indicators(ohlcv)

    regime_info = regime_detector.detect(ohlcv, indicators["_raw"])
    signal_info = signal_engine.generate(indicators["_raw"], regime_info)
    risk_info = risk_engine.check(signal_info, {
        "daily_pnl_pct": 0,
        "drawdown_pct": risk_engine.get_drawdown_status()["drawdown_pct"],
    })

    result = {k: v for k, v in indicators.items() if k != "_raw"}
    result["regime"] = regime_info
    result["signal"] = signal_info
    result["risk"] = risk_info
    result["meta"] = {"symbol": symbol, "interval": interval, "candles": len(ohlcv)}

    return jsonify(result)


@app.route("/api/dip-top")
def api_dip_top():
    symbol = request.args.get("symbol", "BTCUSDT").upper()
    interval = request.args.get("interval", "1h")
    limit = min(int(request.args.get("limit", 500)), 1500)

    sym_info = SUPPORTED_SYMBOLS.get(symbol)
    if not sym_info:
        return jsonify({"error": f"Unsupported symbol: {symbol}"}), 400

    if sym_info["source"] == "stooq":
        ohlcv = generate_gold_silver_candles(sym_info, limit)
    else:
        raw = fetch_binance("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit}, ttl=10)
        if not raw:
            return jsonify({"error": "Failed to fetch candles"}), 502
        ohlcv = transform_klines(raw)

    if len(ohlcv) < 60:
        return jsonify({"error": "Need at least 60 candles for dip/top detection"}), 400

    indicators = compute_all_indicators(ohlcv)
    analysis = dip_top_detector.analyze(symbol, ohlcv, indicators["_raw"])
    return jsonify(analysis)


@app.route("/api/whales")
def api_whales():
    symbol = request.args.get("symbol", "BTCUSDT").upper()
    min_value_usd = float(request.args.get("min_value", 100000))

    result = {
        "symbol": symbol,
        "large_trades": [],
        "whale_alert": [],
        "net_flow": 0,
        "summary": "",
    }

    # Binance large trades detection
    sym_info = SUPPORTED_SYMBOLS.get(symbol)
    if sym_info and sym_info["source"] == "binance":
        trades_raw = fetch_binance("/api/v3/trades", {"symbol": symbol, "limit": 100}, ttl=10)
        if trades_raw:
            price_data = fetch_binance("/api/v3/ticker/price", {"symbol": symbol}, ttl=5)
            current_price = float(price_data["price"]) if price_data else 0

            large = []
            buy_vol = 0
            sell_vol = 0
            for t in trades_raw:
                value = float(t["price"]) * float(t["qty"])
                if value >= min_value_usd:
                    side = "sell" if t["isBuyerMaker"] else "buy"
                    large.append({
                        "price": float(t["price"]),
                        "quantity": float(t["qty"]),
                        "value_usd": round(value, 2),
                        "side": side,
                        "time": t["time"],
                    })
                    if side == "buy":
                        buy_vol += value
                    else:
                        sell_vol += value

            result["large_trades"] = large
            result["net_flow"] = round(buy_vol - sell_vol, 2)
            if buy_vol > sell_vol * 1.5:
                result["summary"] = f"Whale accumulation: ${buy_vol:,.0f} buys vs ${sell_vol:,.0f} sells"
            elif sell_vol > buy_vol * 1.5:
                result["summary"] = f"Whale distribution: ${sell_vol:,.0f} sells vs ${buy_vol:,.0f} buys"
            else:
                result["summary"] = f"Balanced whale activity: ${buy_vol:,.0f} buys, ${sell_vol:,.0f} sells"

    # Whale Alert API (optional)
    if WHALE_ALERT_KEY:
        try:
            since = int(time.time()) - 3600
            resp = requests.get(
                f"{WHALE_ALERT_BASE}/transactions",
                params={"api_key": WHALE_ALERT_KEY, "min_value": int(min_value_usd), "start": since, "currency": "btc"},
                timeout=5,
            )
            if resp.status_code == 200:
                wa_data = resp.json()
                for tx in wa_data.get("transactions", [])[:20]:
                    result["whale_alert"].append({
                        "hash": tx.get("hash", "")[:16],
                        "from": tx.get("from", {}).get("owner", "unknown"),
                        "to": tx.get("to", {}).get("owner", "unknown"),
                        "amount": tx.get("amount", 0),
                        "amount_usd": tx.get("amount_usd", 0),
                        "timestamp": tx.get("timestamp", 0),
                    })
        except Exception as e:
            log.warning("Whale Alert API failed: %s", e)

    return jsonify(result)


# ===========================================================================
# API ROUTES — Sentiment (3 routes) + News (2 routes) + Calendar (1 route)
# ===========================================================================

@app.route("/api/funding")
def api_funding():
    symbol = request.args.get("symbol", "BTCUSDT").upper()

    current = fetch_binance("/fapi/v1/premiumIndex", {"symbol": symbol}, base=BINANCE_FAPI, ttl=30)
    history = fetch_binance("/fapi/v1/fundingRate", {"symbol": symbol, "limit": 100}, base=BINANCE_FAPI, ttl=60)

    if not current:
        return jsonify({
            "symbol": symbol, "rate": 0, "next_time": 0,
            "percentile": 50, "signal": "neutral",
            "history": [], "error": "Funding data unavailable",
        })

    rate = float(current.get("lastFundingRate", 0))
    next_time = int(current.get("nextFundingTime", 0))

    rates = []
    if history:
        rates = [float(h["fundingRate"]) for h in history]

    percentile = 50
    if rates:
        below = sum(1 for r in rates if r <= rate)
        percentile = int(below / len(rates) * 100)

    if rate > 0.03:
        signal = "contrarian_short"
    elif rate < -0.03:
        signal = "contrarian_long"
    elif rate > 0.01:
        signal = "slightly_bullish"
    elif rate < -0.01:
        signal = "slightly_bearish"
    else:
        signal = "neutral"

    return jsonify({
        "symbol": symbol,
        "rate": rate,
        "rate_pct": round(rate * 100, 4),
        "next_funding_time": next_time,
        "percentile": percentile,
        "signal": signal,
        "history": [{"rate": float(h["fundingRate"]), "time": h["fundingTime"]} for h in (history or [])[-20:]],
    })


@app.route("/api/fear-greed")
def api_fear_greed():
    cache_key = "fear_greed"
    cached = cache.get(cache_key, ttl=300)
    if cached:
        return jsonify(cached)

    try:
        resp = requests.get(f"{ALTERNATIVE_ME}/fng/", params={"limit": 7}, timeout=5)
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception as e:
        log.warning("Fear & Greed API failed: %s", e)
        data = []

    if not data:
        return jsonify({"value": 50, "label": "Neutral", "trend": "stable", "history": []})

    current = data[0]
    value = int(current.get("value", 50))

    if value <= 20:
        label = "Extreme Fear"
    elif value <= 40:
        label = "Fear"
    elif value <= 60:
        label = "Neutral"
    elif value <= 80:
        label = "Greed"
    else:
        label = "Extreme Greed"

    history = [{"value": int(d["value"]), "label": d.get("value_classification", ""), "date": d.get("timestamp", "")} for d in data]

    trend = "stable"
    if len(data) >= 7:
        avg_recent = sum(int(d["value"]) for d in data[:3]) / 3
        avg_older = sum(int(d["value"]) for d in data[4:7]) / 3
        diff = avg_recent - avg_older
        if diff > 10:
            trend = "improving"
        elif diff < -10:
            trend = "worsening"

    result = {"value": value, "label": label, "trend": trend, "history": history}
    cache.set(cache_key, result)
    return jsonify(result)


@app.route("/api/sentiment")
def api_sentiment():
    symbol = request.args.get("symbol", "BTCUSDT").upper()

    oi_data = fetch_binance("/fapi/v1/openInterest", {"symbol": symbol}, base=BINANCE_FAPI, ttl=30)
    ls_data = fetch_binance("/futures/data/globalLongShortAccountRatio",
                            {"symbol": symbol, "period": "1h", "limit": 30}, base=BINANCE_FAPI, ttl=60)

    oi = float(oi_data.get("openInterest", 0)) if oi_data else 0

    ls_history = []
    current_ratio = 1.0
    if ls_data:
        for entry in ls_data:
            ratio = float(entry.get("longShortRatio", 1))
            ls_history.append({"ratio": ratio, "time": entry.get("timestamp", 0)})
            current_ratio = ratio

    divergence = None
    if current_ratio > 2.0:
        divergence = "extreme_long"
    elif current_ratio < 0.5:
        divergence = "extreme_short"

    return jsonify({
        "symbol": symbol,
        "open_interest": oi,
        "long_short_ratio": current_ratio,
        "divergence": divergence,
        "history": ls_history[-20:],
    })


@app.route("/api/news")
def api_news():
    cache_key = "rss_news"
    cached = cache.get(cache_key, ttl=120)
    if cached:
        return jsonify(cached)

    feeds = [
        {"name": "CoinTelegraph", "url": "https://cointelegraph.com/rss"},
        {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
        {"name": "CryptoNews", "url": "https://cryptonews.com/news/feed/"},
    ]

    articles = []
    for feed in feeds:
        try:
            resp = requests.get(feed["url"], timeout=5, headers={"User-Agent": "JARVIS/3.0"})
            if resp.status_code != 200:
                continue
            items = _parse_rss_minimal(resp.text, feed["name"])
            articles.extend(items)
        except Exception as e:
            log.warning("RSS %s failed: %s", feed["name"], e)

    articles.sort(key=lambda a: a.get("pub_date", ""), reverse=True)
    result = articles[:30]
    cache.set(cache_key, result)
    return jsonify(result)


def _parse_rss_minimal(xml_text, source_name):
    items = []
    parts = xml_text.split("<item>")
    for part in parts[1:21]:
        title = _extract_tag(part, "title")
        link = _extract_tag(part, "link")
        pub_date = _extract_tag(part, "pubDate")
        desc = _extract_tag(part, "description")
        if desc:
            desc = re.sub(r"<[^>]+>", "", desc)[:200]
        if title:
            items.append({
                "title": title,
                "link": link or "",
                "pub_date": pub_date or "",
                "description": desc or "",
                "source": source_name,
            })
    return items


def _extract_tag(text, tag):
    pattern = f"<{tag}[^>]*>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        if content.startswith("<![CDATA["):
            content = content[9:]
        if content.endswith("]]>"):
            content = content[:-3]
        return content.strip()
    return ""


@app.route("/api/news/summarize", methods=["POST"])
def api_news_summarize():
    if not ANTHROPIC_API_KEY:
        return jsonify({"summary": "API key not configured", "sentiment": "NEUTRAL"})

    body = request.get_json(force=True)
    text = body.get("text", "")
    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": f"Summarize this crypto news in 2 sentences. End with sentiment: BULLISH, BEARISH, or NEUTRAL.\n\n{text[:2000]}"}],
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", [{}])[0].get("text", "")
        sentiment = "NEUTRAL"
        if "BULLISH" in content.upper():
            sentiment = "BULLISH"
        elif "BEARISH" in content.upper():
            sentiment = "BEARISH"
        return jsonify({"summary": content, "sentiment": sentiment})
    except Exception as e:
        return jsonify({"summary": f"Summarization failed: {e}", "sentiment": "NEUTRAL"})


@app.route("/api/calendar")
def api_calendar():
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")

    events = []
    event_mode = False
    for cal in ECONOMIC_CALENDAR:
        for date_str in cal["dates"]:
            try:
                event_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                days_until = (event_date - today).days
                if -1 <= days_until <= 30:
                    entry = {
                        "event": cal["event"],
                        "date": date_str,
                        "impact": cal["impact"],
                        "days_until": days_until,
                        "is_today": days_until == 0,
                    }
                    events.append(entry)
                    if days_until == 0 and cal["impact"] == "high":
                        event_mode = True
            except ValueError:
                continue

    events.sort(key=lambda e: e["days_until"])

    return jsonify({
        "events": events,
        "event_mode": event_mode,
        "today": today_str,
        "next_event": events[0] if events else None,
    })


# ===========================================================================
# API ROUTES — JARVIS AI Chat (1 route)
# ===========================================================================

JARVIS_SYSTEM_PROMPT = """Tu es J.A.R.V.I.S., l'intelligence artificielle de Tony Stark, adaptée au trading crypto.
Tu parles en français avec un ton professionnel mais accessible, comme dans Iron Man.
Tu analyses les marchés, donnes des recommandations basées sur les données techniques, et protèges le capital de l'utilisateur.
Règles :
- Toujours mentionner les risques
- Ne jamais garantir de profits
- Recommander des micro-positions (max 5% du capital)
- Alerter sur les événements économiques importants
- Utiliser des analogies Iron Man quand c'est pertinent
Signe tes messages "— J.A.R.V.I.S."
"""


@app.route("/api/jarvis", methods=["POST"])
def api_jarvis():
    if not ANTHROPIC_API_KEY:
        return jsonify({
            "response": "Monsieur, ma connexion au réseau Anthropic n'est pas configurée. "
                        "Définissez la variable ANTHROPIC_API_KEY pour activer mes capacités d'analyse. — J.A.R.V.I.S.",
            "model": None,
        })

    body = request.get_json(force=True)
    user_msg = body.get("message", "")
    context = body.get("context", {})

    if not user_msg:
        return jsonify({"error": "No message provided"}), 400

    system = JARVIS_SYSTEM_PROMPT
    if context:
        system += f"\n\nContexte marché actuel:\n"
        if "regime" in context:
            system += f"- Régime: {context['regime']}\n"
        if "signal" in context:
            system += f"- Signal: {context['signal'].get('direction', 'N/A')} (score {context['signal'].get('score', 0)})\n"
        if "price" in context:
            system += f"- Prix: ${context['price']}\n"
        if "symbol" in context:
            system += f"- Paire: {context['symbol']}\n"

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "system": system,
                "messages": [{"role": "user", "content": user_msg}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", [{}])[0].get("text", "Erreur de réponse.")
        return jsonify({"response": content, "model": data.get("model", "unknown")})
    except Exception as e:
        return jsonify({
            "response": f"Monsieur, j'ai rencontré une perturbation dans mes systèmes : {e} — J.A.R.V.I.S.",
            "model": None,
        })


# ===========================================================================
# API ROUTES — Execution (4 routes) + Paper Trading (2 routes)
# ===========================================================================

@app.route("/api/execute", methods=["POST"])
def api_execute():
    body = request.get_json(force=True)
    symbol = body.get("symbol", "BTCUSDT").upper()
    side = body.get("side", "long").lower()
    order_type = body.get("type", "market").lower()
    quantity = float(body.get("quantity", 0))
    price = float(body.get("price", 0))
    leverage = int(body.get("leverage", 1))
    tp = body.get("tp")
    sl = body.get("sl")
    mode = body.get("mode", "paper")

    if quantity <= 0:
        return jsonify({"error": "Quantity must be positive"}), 400

    if side not in ("long", "short", "buy", "sell"):
        return jsonify({"error": f"Invalid side: {side}"}), 400

    # Kill switch check
    if risk_engine._is_kill_switch_active():
        return jsonify({"error": "Kill switch is active — all trading suspended", "kill_switch": True}), 403

    # Get current price if market order
    if price <= 0:
        price_data = fetch_binance("/api/v3/ticker/price", {"symbol": symbol}, ttl=2)
        if price_data:
            price = float(price_data.get("price", 0))
        if price <= 0:
            return jsonify({"error": "Could not determine current price"}), 502

    # Paper trading
    if mode == "paper":
        trade_side = "long" if side in ("long", "buy") else "short"
        result = paper_trader.execute(symbol, trade_side, quantity, price, leverage, tp, sl)

        # Log to journal
        conn = get_db()
        conn.execute(
            "INSERT INTO trade_journal (symbol, action, reason, signal_score, confidence, regime) VALUES (?, ?, ?, ?, ?, ?)",
            (symbol, f"paper_{trade_side}", f"Paper {order_type} order", 0, 0, ""),
        )
        conn.commit()
        conn.close()

        return jsonify(result)

    # Live trading
    status = paper_trader.get_status()
    if not status["is_live_allowed"]:
        return jsonify({
            "error": f"Live trading requires {status['required']} paper trades. Current: {status['total_trades']}",
            "remaining": status["remaining"],
        }), 403

    # Micro position validation
    balance = 1000
    balances = exchange_manager.get_all_balances()
    for b in balances:
        if "total_usdt" in b:
            balance = b["total_usdt"]
            break

    validation = micro_engine.validate_order(symbol, side, quantity, price, leverage, balance)
    if not validation["valid"]:
        return jsonify({"error": "Position validation failed", "issues": validation["issues"]}), 400

    # Route to exchange
    ccxt_side = "buy" if side in ("long", "buy") else "sell"
    positions = exchange_manager.get_all_positions()
    if not exchange_manager._adapters:
        return jsonify({"error": "No exchange configured. Add one in Settings."}), 400

    adapter = list(exchange_manager._adapters.values())[0]
    result = adapter.place_order(symbol, ccxt_side, order_type, quantity, price if order_type == "limit" else None, leverage, tp, sl)
    return jsonify(result)


@app.route("/api/positions")
def api_positions():
    paper_pos = paper_trader.get_open_positions()
    live_pos = exchange_manager.get_all_positions()

    for p in paper_pos:
        p["mode"] = "paper"
    for p in live_pos:
        p["mode"] = "live"

    return jsonify(paper_pos + live_pos)


@app.route("/api/balance")
def api_balance():
    live_balances = exchange_manager.get_all_balances()
    paper_status = paper_trader.get_status()

    return jsonify({
        "live": live_balances,
        "paper": {
            "total_pnl": paper_status["total_pnl"],
            "open_positions": paper_status["open_positions"],
            "win_rate": paper_status["win_rate"],
        },
    })


@app.route("/api/close", methods=["POST"])
def api_close():
    body = request.get_json(force=True)
    trade_id = body.get("trade_id")
    symbol = body.get("symbol", "")
    mode = body.get("mode", "paper")
    exit_price = float(body.get("exit_price", 0))

    if mode == "paper":
        if not trade_id:
            return jsonify({"error": "trade_id required for paper close"}), 400
        if exit_price <= 0:
            price_data = fetch_binance("/api/v3/ticker/price", {"symbol": symbol}, ttl=2)
            if price_data:
                exit_price = float(price_data.get("price", 0))
            if exit_price <= 0:
                return jsonify({"error": "Could not determine exit price"}), 502
        return jsonify(paper_trader.close(int(trade_id), exit_price))

    if not symbol:
        return jsonify({"error": "symbol required for live close"}), 400
    if not exchange_manager._adapters:
        return jsonify({"error": "No exchange configured"}), 400

    adapter = list(exchange_manager._adapters.values())[0]
    return jsonify(adapter.close_position(symbol))


@app.route("/api/paper/status")
def api_paper_status():
    return jsonify(paper_trader.get_status())


@app.route("/api/paper/history")
def api_paper_history():
    limit = int(request.args.get("limit", 50))
    return jsonify(paper_trader.get_history(limit))


# ===========================================================================
# API ROUTES — Exchange Management (4 routes)
# ===========================================================================

@app.route("/api/exchanges/add", methods=["POST"])
def api_exchanges_add():
    body = request.get_json(force=True)
    name = body.get("name", "").strip()
    exchange_type = body.get("type", "").strip().lower()
    api_key = body.get("api_key", "").strip()
    api_secret = body.get("api_secret", "").strip()
    passphrase = body.get("passphrase", "").strip()
    testnet = bool(body.get("testnet", False))

    if not name or not exchange_type or not api_key:
        return jsonify({"error": "name, type, and api_key are required"}), 400

    if exchange_type not in ("mexc", "gmx"):
        return jsonify({"error": f"Unsupported exchange type: {exchange_type}. Supported: mexc, gmx"}), 400

    result = exchange_manager.add_exchange(name, exchange_type, api_key, api_secret, passphrase, testnet)
    return jsonify(result)


@app.route("/api/exchanges/list")
def api_exchanges_list():
    return jsonify(exchange_manager.list_exchanges())


@app.route("/api/exchanges/remove", methods=["DELETE"])
def api_exchanges_remove():
    body = request.get_json(force=True)
    exchange_id = body.get("id")
    if not exchange_id:
        return jsonify({"error": "id is required"}), 400
    return jsonify(exchange_manager.remove_exchange(int(exchange_id)))


@app.route("/api/exchanges/test", methods=["POST"])
def api_exchanges_test():
    body = request.get_json(force=True)
    exchange_id = body.get("id")
    if not exchange_id:
        return jsonify({"error": "id is required"}), 400
    return jsonify(exchange_manager.test_exchange(int(exchange_id)))


# ===========================================================================
# API ROUTES — Monitoring & Control (5 routes)
# ===========================================================================

@app.route("/api/drawdown")
def api_drawdown():
    return jsonify(risk_engine.get_drawdown_status())


@app.route("/api/killswitch", methods=["POST"])
def api_killswitch():
    body = request.get_json(force=True)
    active = bool(body.get("active", False))
    reason = body.get("reason", "Manual toggle")

    conn = get_db()
    now = datetime.now(timezone.utc).isoformat() if active else None
    conn.execute(
        "UPDATE killswitch SET active = ?, activated_at = ?, reason = ? WHERE id = 1",
        (int(active), now, reason),
    )
    conn.commit()
    conn.close()

    status = "ACTIVATED" if active else "DEACTIVATED"
    log.warning("Kill switch %s: %s", status, reason)

    return jsonify({"active": active, "reason": reason, "status": status})


@app.route("/api/killswitch/status")
def api_killswitch_status():
    conn = get_db()
    row = conn.execute("SELECT * FROM killswitch WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return jsonify({"active": False})
    return jsonify({
        "active": bool(row["active"]),
        "activated_at": row["activated_at"],
        "reason": row["reason"],
    })


@app.route("/api/journal")
def api_journal():
    limit = int(request.args.get("limit", 50))
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM trade_journal ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/export/csv")
def api_export_csv():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM trade_journal ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    output = io.StringIO()
    if rows:
        writer = csv.writer(output)
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow(tuple(row))

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=jarvis_journal_{datetime.now().strftime('%Y%m%d')}.csv"},
    )


# ===========================================================================
# API ROUTES — System (2 routes)
# ===========================================================================

@app.route("/api/status")
def api_status():
    uptime = time.time() - START_TIME
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)

    return jsonify({
        "status": "online",
        "version": APP_VERSION,
        "uptime": f"{hours}h {minutes}m",
        "uptime_seconds": int(uptime),
        "ai_available": bool(ANTHROPIC_API_KEY),
        "whale_alert": bool(WHALE_ALERT_KEY),
        "ccxt_available": HAS_CCXT,
        "fernet_available": HAS_FERNET,
        "exchanges_configured": len(exchange_manager.list_exchanges()),
        "paper_trades": paper_trader.get_status()["total_trades"],
        "features": {
            "indicators": True,
            "signal_engine": True,
            "risk_engine": True,
            "dip_top_detector": True,
            "paper_trading": True,
            "live_trading": HAS_CCXT,
            "ai_chat": bool(ANTHROPIC_API_KEY),
            "whale_tracking": True,
            "news_aggregation": True,
        },
    })


@app.route("/api/sparklines")
def api_sparklines():
    pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
    result = {}
    for pair in pairs:
        raw = fetch_binance("/api/v3/klines", {"symbol": pair, "interval": "15m", "limit": 20}, ttl=30)
        if raw and isinstance(raw, list):
            result[pair] = [float(k[4]) for k in raw]
    return jsonify(result)


@app.route("/api/portfolio")
def api_portfolio():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        closed = conn.execute(
            "SELECT symbol, pnl FROM paper_trades WHERE status = 'closed'"
        ).fetchall()

        if not closed:
            conn.close()
            return jsonify({
                "total_pnl": 0, "total_trades": 0, "win_rate": 0,
                "open_positions": 0, "unrealized_pnl": 0,
                "by_symbol": [], "best_trade": None, "worst_trade": None,
            })

        total_pnl = sum(r["pnl"] for r in closed)
        total_trades = len(closed)
        wins = sum(1 for r in closed if r["pnl"] > 0)
        win_rate = round(wins / total_trades * 100, 1) if total_trades else 0

        by_sym = {}
        for r in closed:
            s = r["symbol"]
            if s not in by_sym:
                by_sym[s] = {"symbol": s, "pnl": 0, "trades": 0, "wins": 0}
            by_sym[s]["pnl"] += r["pnl"]
            by_sym[s]["trades"] += 1
            if r["pnl"] > 0:
                by_sym[s]["wins"] += 1

        by_symbol = []
        abs_total = sum(abs(v["pnl"]) for v in by_sym.values()) or 1
        for v in sorted(by_sym.values(), key=lambda x: x["pnl"], reverse=True):
            by_symbol.append({
                "symbol": v["symbol"],
                "pnl": round(v["pnl"], 2),
                "trades": v["trades"],
                "win_rate": round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0,
                "pct": round(abs(v["pnl"]) / abs_total * 100, 1),
            })

        best = conn.execute(
            "SELECT symbol, pnl, closed_at FROM paper_trades WHERE status = 'closed' ORDER BY pnl DESC LIMIT 1"
        ).fetchone()
        worst = conn.execute(
            "SELECT symbol, pnl, closed_at FROM paper_trades WHERE status = 'closed' ORDER BY pnl ASC LIMIT 1"
        ).fetchone()

        open_pos = conn.execute(
            "SELECT COUNT(*) as c FROM paper_trades WHERE status = 'open'"
        ).fetchone()["c"]

        conn.close()

        return jsonify({
            "total_pnl": round(total_pnl, 2),
            "total_trades": total_trades,
            "win_rate": win_rate,
            "open_positions": open_pos,
            "unrealized_pnl": 0,
            "by_symbol": by_symbol,
            "best_trade": {"symbol": best["symbol"], "pnl": round(best["pnl"], 2), "date": best["closed_at"]} if best else None,
            "worst_trade": {"symbol": worst["symbol"], "pnl": round(worst["pnl"], 2), "date": worst["closed_at"]} if worst else None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/equity-curve")
def api_equity_curve():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            "SELECT closed_at, pnl FROM paper_trades WHERE status = 'closed' ORDER BY closed_at ASC"
        ).fetchall()
        conn.close()

        initial_capital = float(get_setting("paper_capital") or "100")
        equity = initial_capital
        curve = [{"time": 0, "value": initial_capital}]

        for r in rows:
            equity += r["pnl"]
            ts = r["closed_at"]
            epoch = 0
            if ts:
                try:
                    from datetime import datetime as dt_parse
                    epoch = int(dt_parse.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
                except (ValueError, TypeError):
                    epoch = int(time.time())
            curve.append({"time": epoch, "value": round(equity, 2)})

        return jsonify({
            "initial_capital": initial_capital,
            "current_equity": round(equity, 2),
            "curve": curve,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mtf-signals")
def api_mtf_signals():
    symbol = request.args.get("symbol", "BTCUSDT").upper()
    sym_info = SUPPORTED_SYMBOLS.get(symbol)
    if not sym_info:
        return jsonify({"error": f"Unsupported symbol: {symbol}"}), 400

    timeframes = ["1h", "4h", "1d", "1w"]
    tf_results = {}

    for tf in timeframes:
        try:
            if sym_info["source"] == "stooq":
                ohlcv = generate_gold_silver_candles(sym_info, 200)
            else:
                raw = fetch_binance("/api/v3/klines", {"symbol": symbol, "interval": tf, "limit": 200}, ttl=30)
                if not raw:
                    continue
                ohlcv = transform_klines(raw)

            if len(ohlcv) < 30:
                continue

            indicators = compute_all_indicators(ohlcv)
            raw_ind = indicators["_raw"]
            regime_info = regime_detector.detect(ohlcv, raw_ind)
            signal_info = signal_engine.generate(raw_ind, regime_info)

            rsi_val = raw_ind.get("rsi", [0])[-1] if raw_ind.get("rsi") else 0
            macd_line = raw_ind.get("macd_line", [0])[-1] if raw_ind.get("macd_line") else 0
            macd_signal = raw_ind.get("macd_signal", [0])[-1] if raw_ind.get("macd_signal") else 0

            if macd_line > macd_signal * 1.01:
                macd_dir = "bullish"
            elif macd_line < macd_signal * 0.99:
                macd_dir = "bearish"
            else:
                macd_dir = "flat"

            tf_results[tf] = {
                "rsi": round(rsi_val, 1),
                "macd": macd_dir,
                "regime": regime_info.get("regime", "UNKNOWN"),
                "direction": signal_info.get("direction", "NEUTRAL"),
                "confidence": signal_info.get("confidence", 0),
            }
        except Exception:
            continue

    directions = [v["direction"] for v in tf_results.values() if v["direction"] != "NEUTRAL"]
    if directions:
        from collections import Counter
        counts = Counter(directions)
        majority_dir = counts.most_common(1)[0][0]
        agreement = counts[majority_dir]
    else:
        majority_dir = "NEUTRAL"
        agreement = 0

    total = len(tf_results)
    confluence = {
        "direction": majority_dir,
        "agreement": agreement,
        "total": total,
        "pct": round(agreement / total * 100) if total else 0,
    }

    return jsonify({"symbol": symbol, "timeframes": tf_results, "confluence": confluence})


@app.route("/")
def serve_dashboard():
    return send_from_directory(str(BASE_DIR), "dashboard.html")


@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory(str(BASE_DIR), path)


# ===========================================================================
# Main entry point
# ===========================================================================

if __name__ == "__main__":
    init_db()
    exchange_manager.load_from_db()
    log.info("J.A.R.V.I.S. Trading System v%s starting on port 5000", APP_VERSION)
    app.run(host="0.0.0.0", port=5000, debug=False)
