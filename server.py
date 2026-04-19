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
# PLACEHOLDER: étapes 5-15 seront ajoutées ici
# ---------------------------------------------------------------------------
