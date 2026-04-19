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
# PLACEHOLDER: étapes 3-15 seront ajoutées ici
# ---------------------------------------------------------------------------
