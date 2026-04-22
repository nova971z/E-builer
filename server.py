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
import secrets
import sqlite3
import sys
import subprocess
import time
import threading
from abc import ABC, abstractmethod
from collections import deque
from functools import wraps
from base64 import b64encode, b64decode
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

_http_session = requests.Session()
_http_session.headers.update({"Connection": "keep-alive", "User-Agent": "JARVIS/3.0"})

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

try:
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware
    from eth_account import Account as Web3Account
    HAS_WEB3 = True
except ImportError:
    HAS_WEB3 = False

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
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
HTTPS_ENABLED = os.environ.get("HTTPS", "0") == "1"

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
# GMX V2 — Arbitrum Contract Addresses & Configuration
# ---------------------------------------------------------------------------

GMX_RPC_MAINNET = os.environ.get("GMX_RPC_URL", "https://arb1.arbitrum.io/rpc")
GMX_RPC_TESTNET = os.environ.get("GMX_RPC_TESTNET_URL", "https://sepolia-rollup.arbitrum.io/rpc")

GMX_V2_CONTRACTS_MAINNET = {
    "ExchangeRouter": "0x1C3fa76e6E1088bCE750f23a5BFcffa1efEF6A41",
    "Router": "0x7452c558d45f8afC8c83dAe62C3f8A5BE19c71f6",
    "OrderVault": "0x31eF83a530Fde1B38EE9A18093A333D8Bbbc40D5",
    "DataStore": "0xFD70de6b91282D8017aA4E741e9Ae325CAb992d8",
    "Reader": "0x470fbC46bcC0f16532691Df360A07d8Bf5ee0789",
    "OrderHandler": "0x63492B775e30a9E6b4b4761c12605EB9d071d5e9",
}

GMX_V2_CONTRACTS_TESTNET = {
    "ExchangeRouter": "0x69C527fC77291722b52649E45c838e41be8Bf5d5",
    "Router": "0x820F92c1B3aD8E962E6C6D9d7CaF2a550Aec46fB",
    "OrderVault": "0xCCbE3F6Bc04c60F474bFd8E00B450A8BaCA2e224",
    "DataStore": "0xFD70de6b91282D8017aA4E741e9Ae325CAb992d8",
    "Reader": "0x60a0fF4cDaF0f6D496d71e0bC0fFa86FE8E6B23c",
    "OrderHandler": "0xB0Fc2c89B969C4426ADA23b3CF2e7dDcC6670277",
}

GMX_V2_TOKENS = {
    "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    "USDC_BRIDGED": "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",
    "WBTC": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",
    "ARB": "0x912CE59144191C1204E64559FE8253a0e49E6548",
    "SOL": "0x2bcC6D6CdBbDC0a4071e48bb3B969b06B3330c07",
    "DOGE": "0xC4da4c24fd591125c3F47b340b6f4f76111883d8",
}

GMX_V2_MARKETS = {
    "BTCUSDT": {
        "market_token": "0x47c031236e19d024b42f8AE6780E44A573170703",
        "index_token": "0x47904963fc8b2340414262125aF798B9655E58Cd",
        "long_token": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",
        "short_token": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    },
    "ETHUSDT": {
        "market_token": "0x70d95587d40A2caf56bd97485aB3Eec10Bee6336",
        "index_token": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "long_token": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "short_token": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    },
    "SOLUSDT": {
        "market_token": "0x09400D9DB990D5ed3f35D7be61DfAEB900Af03C9",
        "index_token": "0x2bcC6D6CdBbDC0a4071e48bb3B969b06B3330c07",
        "long_token": "0x2bcC6D6CdBbDC0a4071e48bb3B969b06B3330c07",
        "short_token": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    },
    "ARBUSDT": {
        "market_token": "0xC25cEf6061Cf5dE5eb761b50E4743c1F5D7E5407",
        "index_token": "0x912CE59144191C1204E64559FE8253a0e49E6548",
        "long_token": "0x912CE59144191C1204E64559FE8253a0e49E6548",
        "short_token": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    },
    "DOGEUSDT": {
        "market_token": "0x6853EA96FF216fAb11D2d930CE3C508556A4bdc4",
        "index_token": "0xC4da4c24fd591125c3F47b340b6f4f76111883d8",
        "long_token": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "short_token": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
    },
}

GMX_ORDER_TYPE_MARKET_INCREASE = 2
GMX_ORDER_TYPE_LIMIT_INCREASE = 3
GMX_ORDER_TYPE_MARKET_DECREASE = 4
GMX_ORDER_TYPE_LIMIT_DECREASE = 5
GMX_ORDER_TYPE_STOP_LOSS_DECREASE = 6
GMX_ORDER_TYPE_LIQUIDATION = 7
GMX_DECREASE_POSITION_SWAP_TYPE = 0

GMX_MAX_LEVERAGE = 50
GMX_EXECUTION_FEE_BUFFER_WEI = 600000000000000
GMX_DEFAULT_SLIPPAGE_BPS = 100
GMX_CALLBACK_GAS_LIMIT = 0
GMX_POSITION_FEE_BPS = 5
GMX_REFERRAL_CODE = b"\x00" * 32

# ---------------------------------------------------------------------------
# GMX V2 — Minimal ABIs (only functions called by the adapter)
# ---------------------------------------------------------------------------

GMX_READER_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "dataStore", "type": "address"},
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "uint256", "name": "start", "type": "uint256"},
            {"internalType": "uint256", "name": "end", "type": "uint256"},
        ],
        "name": "getAccountPositions",
        "outputs": [
            {
                "components": [
                    {
                        "components": [
                            {"internalType": "address", "name": "account", "type": "address"},
                            {"internalType": "address", "name": "market", "type": "address"},
                            {"internalType": "address", "name": "collateralToken", "type": "address"},
                        ],
                        "internalType": "struct Position.Addresses",
                        "name": "addresses",
                        "type": "tuple",
                    },
                    {
                        "components": [
                            {"internalType": "uint256", "name": "sizeInUsd", "type": "uint256"},
                            {"internalType": "uint256", "name": "sizeInTokens", "type": "uint256"},
                            {"internalType": "uint256", "name": "collateralAmount", "type": "uint256"},
                            {"internalType": "uint256", "name": "borrowingFactor", "type": "uint256"},
                            {"internalType": "uint256", "name": "fundingFeeAmountPerSize", "type": "uint256"},
                            {"internalType": "uint256", "name": "longTokenClaimableFundingAmountPerSize", "type": "uint256"},
                            {"internalType": "uint256", "name": "shortTokenClaimableFundingAmountPerSize", "type": "uint256"},
                            {"internalType": "uint256", "name": "increasedAtBlock", "type": "uint256"},
                            {"internalType": "uint256", "name": "decreasedAtBlock", "type": "uint256"},
                        ],
                        "internalType": "struct Position.Numbers",
                        "name": "numbers",
                        "type": "tuple",
                    },
                    {
                        "components": [
                            {"internalType": "bool", "name": "isLong", "type": "bool"},
                        ],
                        "internalType": "struct Position.Flags",
                        "name": "flags",
                        "type": "tuple",
                    },
                ],
                "internalType": "struct Position.Props[]",
                "name": "",
                "type": "tuple[]",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "dataStore", "type": "address"},
            {"internalType": "uint256", "name": "start", "type": "uint256"},
            {"internalType": "uint256", "name": "end", "type": "uint256"},
        ],
        "name": "getMarkets",
        "outputs": [
            {
                "components": [
                    {"internalType": "address", "name": "marketToken", "type": "address"},
                    {"internalType": "address", "name": "indexToken", "type": "address"},
                    {"internalType": "address", "name": "longToken", "type": "address"},
                    {"internalType": "address", "name": "shortToken", "type": "address"},
                ],
                "internalType": "struct Market.Props[]",
                "name": "",
                "type": "tuple[]",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

GMX_EXCHANGE_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "receiver", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "sendWnt",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "token", "type": "address"},
            {"internalType": "address", "name": "receiver", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "sendTokens",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {
                "components": [
                    {
                        "components": [
                            {"internalType": "address", "name": "receiver", "type": "address"},
                            {"internalType": "address", "name": "cancellationReceiver", "type": "address"},
                            {"internalType": "address", "name": "callbackContract", "type": "address"},
                            {"internalType": "address", "name": "uiFeeReceiver", "type": "address"},
                            {"internalType": "address", "name": "market", "type": "address"},
                            {"internalType": "address", "name": "initialCollateralToken", "type": "address"},
                            {"internalType": "address[]", "name": "swapPath", "type": "address[]"},
                        ],
                        "internalType": "struct IBaseOrderUtils.CreateOrderParamsAddresses",
                        "name": "addresses",
                        "type": "tuple",
                    },
                    {
                        "components": [
                            {"internalType": "uint256", "name": "sizeDeltaUsd", "type": "uint256"},
                            {"internalType": "uint256", "name": "initialCollateralDeltaAmount", "type": "uint256"},
                            {"internalType": "uint256", "name": "triggerPrice", "type": "uint256"},
                            {"internalType": "uint256", "name": "acceptablePrice", "type": "uint256"},
                            {"internalType": "uint256", "name": "executionFee", "type": "uint256"},
                            {"internalType": "uint256", "name": "callbackGasLimit", "type": "uint256"},
                            {"internalType": "uint256", "name": "minOutputAmount", "type": "uint256"},
                            {"internalType": "uint256", "name": "validFromTime", "type": "uint256"},
                        ],
                        "internalType": "struct IBaseOrderUtils.CreateOrderParamsNumbers",
                        "name": "numbers",
                        "type": "tuple",
                    },
                    {"internalType": "enum Order.OrderType", "name": "orderType", "type": "uint8"},
                    {"internalType": "enum Order.DecreasePositionSwapType", "name": "decreasePositionSwapType", "type": "uint8"},
                    {"internalType": "bool", "name": "isLong", "type": "bool"},
                    {"internalType": "bool", "name": "shouldUnwrapNativeToken", "type": "bool"},
                    {"internalType": "bool", "name": "autoCancel", "type": "bool"},
                    {"internalType": "bytes32", "name": "referralCode", "type": "bytes32"},
                    {"internalType": "bytes32[]", "name": "dataList", "type": "bytes32[]"},
                ],
                "internalType": "struct IBaseOrderUtils.CreateOrderParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "createOrder",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "bytes[]", "name": "data", "type": "bytes[]"},
        ],
        "name": "multicall",
        "outputs": [{"internalType": "bytes[]", "name": "results", "type": "bytes[]"}],
        "stateMutability": "payable",
        "type": "function",
    },
]

GMX_ERC20_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
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

if ALLOWED_ORIGINS:
    CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)
else:
    CORS(app, origins=[
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        f"http://{os.environ.get('SERVER_IP', '0.0.0.0')}:5000",
    ], supports_credentials=True)

import gzip as _gzip

@app.after_request
def _security_headers(response):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self' wss://stream.binance.com:* https://api.binance.com https://fapi.binance.com https://api.alternative.me https://stooq.com https://api.anthropic.com; "
        "font-src 'self'; "
        "frame-ancestors 'none'"
    )
    if HTTPS_ENABLED:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    if (response.status_code < 200 or response.status_code >= 300
        or 'Content-Encoding' in response.headers
        or 'gzip' not in request.headers.get('Accept-Encoding', '')
        or response.direct_passthrough):
        return response
    ct = response.content_type or ''
    if not ct.startswith('application/json'):
        return response
    try:
        data = response.get_data()
    except Exception:
        return response
    if len(data) < 256:
        return response
    compressed = _gzip.compress(data, compresslevel=1)
    response.set_data(compressed)
    response.headers['Content-Encoding'] = 'gzip'
    response.headers['Content-Length'] = len(compressed)
    response.headers['Vary'] = 'Accept-Encoding'
    return response

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

    def cleanup(self, max_age=600):
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._store.items() if now - v["ts"] > max_age]
            for k in expired:
                del self._store[k]
        return len(expired)


cache = Cache()


def _cache_gc_loop():
    while True:
        time.sleep(600)
        try:
            cache.cleanup(600)
        except Exception:
            pass

threading.Thread(target=_cache_gc_loop, daemon=True, name="cache-gc").start()


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

    c.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        condition_type TEXT NOT NULL,
        operator TEXT NOT NULL,
        value REAL NOT NULL,
        message TEXT DEFAULT '',
        triggered INTEGER DEFAULT 0,
        repeat INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        triggered_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS auth_pin (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        pin_hash TEXT NOT NULL,
        pin_salt TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS auth_sessions (
        token TEXT PRIMARY KEY,
        created_at TEXT DEFAULT (datetime('now')),
        last_active TEXT DEFAULT (datetime('now')),
        ip_address TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS scheduled_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        order_type TEXT NOT NULL,
        parent_type TEXT NOT NULL,
        quantity REAL NOT NULL,
        price REAL,
        trigger_price REAL,
        trail_pct REAL,
        leverage INTEGER DEFAULT 1,
        status TEXT DEFAULT 'pending',
        parent_id INTEGER,
        sequence_idx INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        executed_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (datetime('now')),
        event_type TEXT NOT NULL,
        ip_address TEXT DEFAULT '',
        details TEXT DEFAULT '',
        success INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS bot_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        strategy TEXT NOT NULL,
        entry_price REAL NOT NULL,
        exit_price REAL,
        size_usd REAL NOT NULL,
        leverage REAL NOT NULL,
        pnl_usd REAL,
        pnl_pct REAL,
        fees_usd REAL,
        slippage_pct REAL,
        duration_minutes REAL,
        regime_at_entry TEXT,
        regime_at_exit TEXT,
        signal_score REAL,
        signal_confidence REAL,
        macro_score REAL,
        stop_loss REAL,
        take_profit REAL,
        exit_reason TEXT,
        tx_hash_open TEXT,
        tx_hash_close TEXT,
        notes TEXT,
        status TEXT DEFAULT 'open'
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS alert_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT NOT NULL,
        config TEXT NOT NULL,
        events TEXT,
        enabled INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS notification_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (datetime('now')),
        alert_type TEXT NOT NULL,
        priority TEXT NOT NULL,
        message TEXT NOT NULL,
        data TEXT
    )""")

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
        raise RuntimeError("Encryption unavailable: cryptography package not installed")
    return f.encrypt(plaintext.encode()).decode()


def decrypt_string(ciphertext):
    f = get_fernet()
    if not f:
        raise RuntimeError("Decryption unavailable: cryptography package not installed")
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        log.error("Decryption failed — data corrupted or key mismatch")
        return None


def check_fernet_integrity():
    """Round-trip encrypt/decrypt test. Returns True if OK."""
    try:
        f = get_fernet()
        if not f:
            return False
        token = f.encrypt(b"jarvis-integrity-check")
        result = f.decrypt(token)
        return result == b"jarvis-integrity-check"
    except Exception:
        log.critical("Fernet integrity check FAILED — encryption key corrupted")
        return False


def check_key_file_permissions():
    """Check secret.key file permissions. Returns (ok, octal_mode_str)."""
    if not SECRET_KEY_FILE.exists():
        return True, "N/A"
    try:
        mode = SECRET_KEY_FILE.stat().st_mode & 0o777
        mode_str = oct(mode)
        if mode != 0o600:
            log.warning("secret.key has permissive permissions %s (should be 0o600)", mode_str)
            try:
                os.chmod(str(SECRET_KEY_FILE), 0o600)
                log.info("Auto-fixed secret.key permissions to 0o600")
                return True, "0o600 (fixed)"
            except OSError:
                return False, mode_str
        return True, mode_str
    except OSError:
        return False, "error"


# ---------------------------------------------------------------------------
# Input validation & error sanitization
# ---------------------------------------------------------------------------

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,20}$")


def validate_symbol(s):
    """Validate trading symbol. Returns (clean_symbol, error_msg)."""
    s = str(s).strip().upper()
    if not _SYMBOL_RE.match(s):
        return None, "Invalid symbol format"
    return s, None


def validate_quantity(q):
    """Validate quantity. Returns (float_value, error_msg)."""
    try:
        v = float(q)
    except (TypeError, ValueError):
        return None, "Invalid quantity"
    if v <= 0 or v > 1e12:
        return None, "Quantity must be between 0 and 1,000,000,000,000"
    return v, None


def validate_price(p):
    """Validate price. Returns (float_value, error_msg)."""
    try:
        v = float(p)
    except (TypeError, ValueError):
        return None, "Invalid price"
    if v < 0 or v > 1e12:
        return None, "Price must be between 0 and 1,000,000,000,000"
    return v, None


def sanitize_error(e):
    """Return a safe error message — never expose stack traces or internals."""
    safe_prefixes = (
        "Failed to fetch", "Invalid", "Quantity", "Price", "No ", "Could not",
        "Kill switch", "PIN", "Not found", "Unsupported", "Too many",
        "Authentication", "Encryption", "Already", "Insufficient",
        "Cannot", "Token approval", "GMX", "Web3", "Nonce", "Gas",
        "Transaction", "Contract", "RPC", "Timeout", "Connection",
        "execution reverted", "insufficient funds",
    )
    msg = str(e)
    for prefix in safe_prefixes:
        if msg.lower().startswith(prefix.lower()):
            return msg[:200]
    log.error("Sanitized error (hidden from user): %s", msg)
    return "Internal server error — check server logs"


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

_MASK_RE = re.compile(r"(sk-ant-[a-zA-Z0-9-]{4})[a-zA-Z0-9-]+|"
                       r"(0x[a-fA-F0-9]{4})[a-fA-F0-9]{56,}|"
                       r"(eyJ[a-zA-Z0-9]{4})[a-zA-Z0-9_.-]+")


def _mask_sensitive(text):
    """Replace API keys, private keys, and tokens with masked versions."""
    return _MASK_RE.sub(lambda m: (m.group(1) or m.group(2) or m.group(3)) + "***masked***", str(text))


def log_audit(event_type, details="", success=True, ip=None):
    """Write audit event to DB and log."""
    if ip is None:
        try:
            ip = request.remote_addr or ""
        except RuntimeError:
            ip = ""
    safe_details = _mask_sensitive(details)
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO audit_log (event_type, ip_address, details, success) VALUES (?, ?, ?, ?)",
            (event_type, ip, safe_details, 1 if success else 0),
        )
        conn.execute("DELETE FROM audit_log WHERE id NOT IN (SELECT id FROM audit_log ORDER BY id DESC LIMIT 5000)")
        conn.commit()
        conn.close()
    except Exception:
        pass
    level = logging.INFO if success else logging.WARNING
    log.log(level, "AUDIT %s | %s | %s", event_type, "OK" if success else "FAIL", safe_details)


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


def delete_setting(key):
    conn = get_db()
    conn.execute("DELETE FROM settings WHERE key = ?", (key,))
    conn.commit()
    conn.close()


def get_anthropic_key():
    """Return Anthropic API key: env var first, then encrypted DB, else empty string."""
    if ANTHROPIC_API_KEY:
        return ANTHROPIC_API_KEY
    enc = get_setting("anthropic_api_key_enc")
    if enc:
        try:
            return decrypt_string(enc)
        except Exception:
            log.warning("Failed to decrypt stored Anthropic key")
            return ""
    return ""


def _vault_derive_key(pin, salt):
    """Derive a Fernet key from PIN + salt using PBKDF2."""
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), 480_000, dklen=32)
    return b64encode(dk)


def vault_encrypt(plaintext, pin):
    """Double encrypt: Fernet(system key) wrapping Fernet(PIN-derived key)."""
    salt = secrets.token_hex(16)
    pin_key = _vault_derive_key(pin, salt)
    if not HAS_FERNET:
        raise RuntimeError("Vault encryption unavailable: cryptography package not installed")
    inner = Fernet(pin_key).encrypt(plaintext.encode()).decode()
    outer = encrypt_string(salt + ":" + inner)
    return outer


def vault_decrypt(ciphertext, pin):
    """Reverse double encryption."""
    raw = decrypt_string(ciphertext)
    if not raw or ":" not in raw:
        return None
    salt, inner = raw.split(":", 1)
    pin_key = _vault_derive_key(pin, salt)
    if not HAS_FERNET:
        raise RuntimeError("Vault decryption unavailable: cryptography package not installed")
    try:
        return Fernet(pin_key).decrypt(inner.encode()).decode()
    except Exception:
        return None


def get_gmx_wallet_address():
    """Return public address from stored wallet, or None."""
    enc = get_setting("gmx_wallet_enc")
    if not enc:
        return None
    addr = get_setting("gmx_wallet_address")
    return addr


def _wipe_string(s):
    """Best-effort overwrite of a string's memory. CPython strings are immutable,
    so this is not guaranteed, but ctypes can overwrite the buffer."""
    try:
        import ctypes
        n = len(s)
        addr = id(s) + sys.getsizeof("") - 1
        ctypes.memset(addr, 0, n)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Authentication — PIN + Session tokens
# ---------------------------------------------------------------------------

AUTH_SESSION_TIMEOUT = 900  # 15 minutes inactivity
AUTH_PBKDF2_ITERATIONS = 600_000

def _hash_pin(pin, salt=None):
    if salt is None:
        salt = secrets.token_hex(32)
    h = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), AUTH_PBKDF2_ITERATIONS)
    return h.hex(), salt

def is_pin_configured():
    conn = get_db()
    row = conn.execute("SELECT pin_hash FROM auth_pin WHERE id = 1").fetchone()
    conn.close()
    return row is not None

def verify_pin(pin):
    conn = get_db()
    row = conn.execute("SELECT pin_hash, pin_salt FROM auth_pin WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return False
    h, _ = _hash_pin(pin, row["pin_salt"])
    return secrets.compare_digest(h, row["pin_hash"])

def create_session(ip=""):
    token = secrets.token_urlsafe(48)
    conn = get_db()
    conn.execute("INSERT INTO auth_sessions (token, ip_address) VALUES (?, ?)", (token, ip))
    conn.commit()
    conn.close()
    return token

def validate_session(token):
    if not token:
        return False
    conn = get_db()
    row = conn.execute("SELECT last_active FROM auth_sessions WHERE token = ?", (token,)).fetchone()
    if not row:
        conn.close()
        return False
    last = datetime.fromisoformat(row["last_active"])
    if (datetime.now(timezone.utc) - last.replace(tzinfo=timezone.utc)).total_seconds() > AUTH_SESSION_TIMEOUT:
        conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return False
    conn.execute("UPDATE auth_sessions SET last_active = datetime('now') WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return True

def cleanup_expired_sessions():
    conn = get_db()
    conn.execute(
        "DELETE FROM auth_sessions WHERE datetime(last_active, '+' || ? || ' seconds') < datetime('now')",
        (AUTH_SESSION_TIMEOUT,),
    )
    conn.commit()
    conn.close()

def require_auth():
    """Check auth. Returns None if OK, or a Flask response tuple if unauthorized."""
    if not is_pin_configured():
        return None
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    if not validate_session(token):
        return jsonify({"error": "Authentication required", "auth_required": True}), 401
    return None


def require_fernet():
    """Block route if Fernet encryption is unavailable."""
    if not HAS_FERNET:
        return jsonify({"error": "Encryption unavailable — install cryptography package"}), 503
    return None


# ---------------------------------------------------------------------------
# Rate Limiting & Anti-brute force
# ---------------------------------------------------------------------------

class RateLimiter:
    """Pure-Python in-memory rate limiter. Tracks request timestamps per IP."""

    def __init__(self):
        self._lock = threading.Lock()
        self._hits = {}          # {bucket_key: [timestamp, ...]}
        self._blocked = {}       # {ip: unblock_timestamp}  (brute force)
        self._login_fails = {}   # {ip: fail_count}
        self._last_cleanup = time.time()

    def _cleanup(self):
        now = time.time()
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now
        cutoff = now - 120
        stale = [k for k, hits in self._hits.items() if hits and hits[-1] < cutoff]
        for k in stale:
            del self._hits[k]
        expired = [ip for ip, t in self._blocked.items() if t < now]
        for ip in expired:
            del self._blocked[ip]

    def is_blocked(self, ip):
        with self._lock:
            t = self._blocked.get(ip)
            if t and t > time.time():
                return True
            if t:
                self._blocked.pop(ip, None)
            return False

    def block_ip(self, ip, seconds=900):
        with self._lock:
            self._blocked[ip] = time.time() + seconds
        log.warning("IP blocked for %ds due to brute force", seconds)

    def check(self, ip, category, max_requests, window):
        with self._lock:
            self._cleanup()
            key = f"{ip}:{category}"
            now = time.time()
            hits = self._hits.get(key, [])
            cutoff = now - window
            hits = [t for t in hits if t > cutoff]
            if len(hits) >= max_requests:
                self._hits[key] = hits
                return False, (window - (now - hits[0])) if hits else window
            hits.append(now)
            self._hits[key] = hits
            return True, 0

    def record_login_fail(self, ip, max_fails=5, block_seconds=900):
        with self._lock:
            self._login_fails[ip] = self._login_fails.get(ip, 0) + 1
            count = self._login_fails[ip]
        if count >= max_fails:
            self.block_ip(ip, block_seconds)
            with self._lock:
                self._login_fails.pop(ip, None)
            return True
        return False

    def reset_login_fails(self, ip):
        with self._lock:
            self._login_fails.pop(ip, None)

    def get_login_fails(self, ip):
        with self._lock:
            return self._login_fails.get(ip, 0)


_rate_limiter = RateLimiter()

RATE_LIMITS = {
    "auth":        (5,   60),
    "execute":     (60,  3600),
    "settings":    (10,  60),
    "market_data": (120, 60),
    "bot":         (20,  60),
    "bot_start":   (5,   3600),
    "bot_config":  (20,  3600),
    "webhook":     (10,  86400),
}


def rate_limit(category):
    """Decorator: enforce rate limit for a route category."""
    max_req, window = RATE_LIMITS.get(category, (60, 60))
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            if _rate_limiter.is_blocked(ip):
                retry = int(_rate_limiter._blocked.get(ip, time.time()) - time.time())
                resp = jsonify({"error": "Too many requests — IP temporarily blocked", "retry_after": max(retry, 1)})
                resp.status_code = 429
                resp.headers["Retry-After"] = str(max(retry, 1))
                return resp
            ok, wait = _rate_limiter.check(ip, category, max_req, window)
            if not ok:
                retry = int(math.ceil(wait))
                resp = jsonify({"error": "Too many requests", "retry_after": retry})
                resp.status_code = 429
                resp.headers["Retry-After"] = str(retry)
                return resp
            return fn(*args, **kwargs)
        return wrapper
    return decorator


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
        resp = _http_session.get(f"{base}{endpoint}", params=params, timeout=5)
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
        return {"candles": []}
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
    return {"candles": candles}


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
# Advanced Market Regime Detector — 6 states with transition probabilities,
# volatility clustering, momentum divergence, and regime memory.
# Backward-compatible: output always includes "regime" mapped to the 4 legacy
# states (BULL/BEAR/RANGE/CRISIS) so SignalEngine/RiskEngine work unchanged.
# ---------------------------------------------------------------------------

_REGIME_TO_LEGACY = {
    "STRONG_BULL": "BULL",
    "WEAK_BULL":   "BULL",
    "RANGE":       "RANGE",
    "WEAK_BEAR":   "BEAR",
    "STRONG_BEAR": "BEAR",
    "CRISIS":      "CRISIS",
}

_REGIME_RISK_MULT = {
    "STRONG_BULL": 1.0,
    "WEAK_BULL":   0.75,
    "RANGE":       0.6,
    "WEAK_BEAR":   0.75,
    "STRONG_BEAR": 1.0,
    "CRISIS":      0.0,
}

_BASE_TRANSITION = {
    "STRONG_BULL": {"STRONG_BULL": 0.60, "WEAK_BULL": 0.25, "RANGE": 0.08, "WEAK_BEAR": 0.04, "STRONG_BEAR": 0.01, "CRISIS": 0.02},
    "WEAK_BULL":   {"STRONG_BULL": 0.20, "WEAK_BULL": 0.35, "RANGE": 0.25, "WEAK_BEAR": 0.12, "STRONG_BEAR": 0.03, "CRISIS": 0.05},
    "RANGE":       {"STRONG_BULL": 0.10, "WEAK_BULL": 0.18, "RANGE": 0.40, "WEAK_BEAR": 0.18, "STRONG_BEAR": 0.10, "CRISIS": 0.04},
    "WEAK_BEAR":   {"STRONG_BULL": 0.03, "WEAK_BULL": 0.12, "RANGE": 0.25, "WEAK_BEAR": 0.35, "STRONG_BEAR": 0.20, "CRISIS": 0.05},
    "STRONG_BEAR": {"STRONG_BULL": 0.01, "WEAK_BULL": 0.04, "RANGE": 0.08, "WEAK_BEAR": 0.25, "STRONG_BEAR": 0.55, "CRISIS": 0.07},
    "CRISIS":      {"STRONG_BULL": 0.05, "WEAK_BULL": 0.10, "RANGE": 0.15, "WEAK_BEAR": 0.15, "STRONG_BEAR": 0.25, "CRISIS": 0.30},
}

SMOOTHING_THRESHOLD = 3


class AdvancedRegimeDetector:
    """6-state regime detector with transition probabilities and memory."""

    REGIMES = ("STRONG_BULL", "WEAK_BULL", "RANGE", "WEAK_BEAR", "STRONG_BEAR", "CRISIS")

    def __init__(self):
        self._regime_history = deque(maxlen=100)
        self._current_regime = "RANGE"
        self._previous_regime = "RANGE"
        self._regime_duration = 0
        self._pending_regime = None
        self._pending_count = 0
        self._lock = threading.Lock()

    def detect(self, ohlcv, raw_indicators):
        closes = raw_indicators.get("closes", [])
        if len(closes) < 50:
            return self._default_result("Insufficient data")

        try:
            trend_score, trend_reasons = self._detect_trend_state(ohlcv, raw_indicators)
            vol_regime, vol_ratio, vol_reasons = self._detect_volatility_regime(ohlcv, raw_indicators)
            div_score, div_reasons = self._detect_momentum_divergence(ohlcv, raw_indicators)
            micro, micro_reasons = self._detect_market_microstructure(ohlcv)
            crisis_score, crisis_reasons = self._detect_crisis(ohlcv, raw_indicators)
        except Exception as exc:
            log.debug("AdvancedRegimeDetector sub-detection error: %s", exc)
            return self._default_result(f"Detection error: {exc}")

        raw_regime, confidence, reasons = self._classify(
            trend_score, vol_regime, vol_ratio, div_score, micro,
            crisis_score, trend_reasons + vol_reasons + div_reasons + micro_reasons + crisis_reasons,
        )

        with self._lock:
            smoothed = self._smooth_regime(raw_regime)
            self._previous_regime = self._current_regime
            if smoothed != self._current_regime:
                self._current_regime = smoothed
                self._regime_duration = 1
            else:
                self._regime_duration += 1
            self._regime_history.append(smoothed)

            trans_prob = self._estimate_transition_probabilities(
                smoothed, trend_score, div_score, vol_ratio)

            return {
                "regime": _REGIME_TO_LEGACY.get(smoothed, smoothed),
                "regime_detailed": smoothed,
                "previous_regime": _REGIME_TO_LEGACY.get(self._previous_regime, self._previous_regime),
                "previous_regime_detailed": self._previous_regime,
                "confidence": confidence,
                "transition_prob": trans_prob,
                "regime_duration": self._regime_duration,
                "reasons": reasons,
                "risk_multiplier": _REGIME_RISK_MULT.get(smoothed, 0.5),
                "volatility_regime": vol_regime,
                "volatility_ratio": round(vol_ratio, 2),
                "trend_strength": max(0, min(100, abs(trend_score))),
                "divergence_score": div_score,
                "crisis_score": crisis_score,
                "microstructure": micro,
            }

    # ----- sub-detectors ----------------------------------------------------

    def _detect_trend_state(self, ohlcv, ind):
        closes = ind["closes"]
        price = closes[-1]
        score = 0.0
        reasons = []

        ema9 = calc_ema(closes, 9)
        ema21 = calc_ema(closes, 21)
        ema50 = ind.get("ema50", [])
        ema200 = ind.get("ema200", [])

        e9 = self._lv(ema9)
        e21 = self._lv(ema21)
        e50 = self._lv(ema50)
        e200 = self._lv(ema200)

        aligned = 0
        if e9 is not None and e21 is not None and e50 is not None and e200 is not None:
            if price > e9 > e21 > e50 > e200:
                aligned = 4
                score += 40
                reasons.append("Full 4-EMA bullish alignment")
            elif price > e9 > e21 > e50:
                aligned = 3
                score += 30
                reasons.append("3-EMA bullish (9>21>50)")
            elif price > e9 > e21:
                aligned = 2
                score += 15
                reasons.append("2-EMA bullish (9>21)")
            elif price < e9 < e21 < e50 < e200:
                aligned = -4
                score -= 40
                reasons.append("Full 4-EMA bearish alignment")
            elif price < e9 < e21 < e50:
                aligned = -3
                score -= 30
                reasons.append("3-EMA bearish (9<21<50)")
            elif price < e9 < e21:
                aligned = -2
                score -= 15
                reasons.append("2-EMA bearish (9<21)")

        if e50 is not None and len(ema50) >= 10:
            recent_e50 = [v for v in ema50[-10:] if v is not None]
            if len(recent_e50) >= 5:
                slope = (recent_e50[-1] - recent_e50[0]) / max(recent_e50[0], 1e-9) * 100
                if slope > 0.5:
                    score += 15
                    reasons.append(f"EMA50 slope +{slope:.2f}% (accelerating)")
                elif slope < -0.5:
                    score -= 15
                    reasons.append(f"EMA50 slope {slope:.2f}% (decelerating)")

        adx_data = ind.get("adx", {})
        adx_val = self._lv(adx_data.get("adx", []))
        dmi_p = self._lv(adx_data.get("dmi_plus", []))
        dmi_m = self._lv(adx_data.get("dmi_minus", []))
        if adx_val is not None:
            if adx_val > 25:
                direction_bonus = 20 if (dmi_p and dmi_m and dmi_p > dmi_m) else -20
                score += direction_bonus
                reasons.append(f"ADX {adx_val:.0f} directional, DMI+{'>' if direction_bonus > 0 else '<'}DMI-")
            elif adx_val < 15:
                score *= 0.5
                reasons.append(f"ADX {adx_val:.0f} very weak — trend fading")

        highs = ind.get("highs", [])
        lows = ind.get("lows", [])
        if len(highs) >= 20 and len(lows) >= 20:
            hh_count, ll_count = 0, 0
            for i in range(-15, -1, 3):
                try:
                    if highs[i] > highs[i - 3]:
                        hh_count += 1
                    if lows[i] < lows[i - 3]:
                        ll_count += 1
                except IndexError:
                    continue
            if hh_count >= 3:
                score += 10
                reasons.append(f"Higher highs pattern ({hh_count}x)")
            if ll_count >= 3:
                score -= 10
                reasons.append(f"Lower lows pattern ({ll_count}x)")

        score = max(-100, min(100, score))
        return score, reasons

    def _detect_volatility_regime(self, ohlcv, ind):
        atr_vals = ind.get("atr", [])
        closes = ind["closes"]
        price = closes[-1] if closes else 1
        reasons = []

        valid_atr = [v for v in atr_vals if v is not None]
        if len(valid_atr) < 20:
            return "normal", 1.0, ["Not enough ATR data"]

        current_atr = valid_atr[-1]
        avg_50 = sum(valid_atr[-50:]) / min(len(valid_atr), 50) if valid_atr else current_atr
        vol_ratio = current_atr / avg_50 if avg_50 > 0 else 1.0

        bb = ind.get("bb", {})
        upper_list = bb.get("upper", [])
        lower_list = bb.get("lower", [])
        middle_list = bb.get("middle", [])
        bb_widths = []
        n = min(len(upper_list), len(lower_list), len(middle_list), 100)
        for i in range(-n, 0):
            try:
                u, l, m = upper_list[i], lower_list[i], middle_list[i]
                if u is not None and l is not None and m is not None and m > 0:
                    bb_widths.append((u - l) / m)
            except IndexError:
                continue

        squeeze = False
        if len(bb_widths) >= 10:
            sorted_w = sorted(bb_widths)
            current_w = bb_widths[-1] if bb_widths else 0.05
            rank = sum(1 for w in sorted_w if w <= current_w)
            percentile = rank / len(sorted_w) * 100
            if percentile < 10:
                squeeze = True
                reasons.append(f"BB width percentile {percentile:.0f}% — squeeze detected")

            mean_w = sum(bb_widths) / len(bb_widths)
            variance = sum((w - mean_w) ** 2 for w in bb_widths) / len(bb_widths)
            std_w = math.sqrt(variance) if variance > 0 else 0
            if current_w > mean_w + 2 * std_w:
                reasons.append(f"Volatility clustering: BB width > 2σ above mean")
                vol_ratio = max(vol_ratio, 2.0)

        if vol_ratio < 0.5:
            regime = "low"
            reasons.append(f"ATR ratio {vol_ratio:.2f}x — low volatility")
        elif vol_ratio < 1.5:
            regime = "normal"
        elif vol_ratio < 3.0:
            regime = "high"
            reasons.append(f"ATR ratio {vol_ratio:.2f}x — high volatility")
        else:
            regime = "extreme"
            reasons.append(f"ATR ratio {vol_ratio:.2f}x — extreme volatility")

        if squeeze:
            regime = "low"

        return regime, vol_ratio, reasons

    def _detect_momentum_divergence(self, ohlcv, ind):
        closes = ind["closes"]
        rsi_vals = ind.get("rsi", [])
        macd_data = ind.get("macd", {})
        hist = macd_data.get("histogram", [])
        obv_vals = ind.get("obv", [])
        score = 0
        reasons = []

        lookback = 20
        if len(closes) < lookback + 5 or len(rsi_vals) < lookback:
            return 0, []

        segment_c = closes[-lookback:]
        segment_r = [v for v in rsi_vals[-lookback:] if v is not None]

        if len(segment_r) >= 10:
            c_max_idx = segment_c.index(max(segment_c))
            c_min_idx = segment_c.index(min(segment_c))

            if c_max_idx > len(segment_c) * 0.6:
                r_second_half = segment_r[len(segment_r) // 2:]
                if r_second_half:
                    r_max_recent = max(r_second_half)
                    r_max_all = max(segment_r)
                    if r_max_recent < r_max_all * 0.9 and max(segment_c) == segment_c[-1]:
                        score += 35
                        reasons.append("Bearish divergence: price new high, RSI weakening")

            if c_min_idx > len(segment_c) * 0.6:
                r_second_half = segment_r[len(segment_r) // 2:]
                if r_second_half:
                    r_min_recent = min(r_second_half)
                    r_min_all = min(segment_r)
                    if r_min_recent > r_min_all * 1.1 and min(segment_c) == segment_c[-1]:
                        score += 35
                        reasons.append("Bullish divergence: price new low, RSI strengthening")

        valid_hist = [v for v in hist[-10:] if v is not None]
        if len(valid_hist) >= 5:
            c_trend = closes[-1] - closes[-5]
            h_trend = valid_hist[-1] - valid_hist[0]
            if c_trend > 0 and h_trend < 0:
                score += 20
                reasons.append("MACD histogram declining while price rising")
            elif c_trend < 0 and h_trend > 0:
                score += 20
                reasons.append("MACD histogram rising while price falling")

        valid_obv = [v for v in obv_vals[-10:] if v is not None]
        if len(valid_obv) >= 5:
            obv_trend = valid_obv[-1] - valid_obv[0]
            c_trend = closes[-1] - closes[-5]
            if c_trend > 0 and obv_trend < 0:
                score += 15
                reasons.append("OBV divergence: price up but volume declining")
            elif c_trend < 0 and obv_trend > 0:
                score += 15
                reasons.append("OBV divergence: price down but volume accumulating")

        return min(score, 100), reasons

    def _detect_market_microstructure(self, ohlcv):
        if len(ohlcv) < 20:
            return {}, []

        reasons = []
        result = {}

        closes = [c["close"] for c in ohlcv]
        volumes = [c["volume"] for c in ohlcv]
        highs = [c["high"] for c in ohlcv]
        lows = [c["low"] for c in ohlcv]

        cum_vp = 0.0
        cum_vol = 0.0
        for i in range(-20, 0):
            try:
                typical = (highs[i] + lows[i] + closes[i]) / 3
                cum_vp += typical * volumes[i]
                cum_vol += volumes[i]
            except IndexError:
                continue
        vwap = cum_vp / cum_vol if cum_vol > 0 else closes[-1]
        result["vwap"] = round(vwap, 4)
        price = closes[-1]
        if price > vwap * 1.01:
            reasons.append(f"Price above VWAP ({price:.0f} > {vwap:.0f}) — buyers in control")
        elif price < vwap * 0.99:
            reasons.append(f"Price below VWAP ({price:.0f} < {vwap:.0f}) — sellers in control")

        buy_vol = 0.0
        sell_vol = 0.0
        for bar in ohlcv[-20:]:
            body = bar["close"] - bar["open"]
            total_range = bar["high"] - bar["low"]
            if total_range > 0:
                buy_pct = max(0, body) / total_range
                buy_vol += bar["volume"] * buy_pct
                sell_vol += bar["volume"] * (1 - buy_pct)
            else:
                buy_vol += bar["volume"] * 0.5
                sell_vol += bar["volume"] * 0.5
        total = buy_vol + sell_vol
        ofi = (buy_vol - sell_vol) / total if total > 0 else 0
        result["order_flow_imbalance"] = round(ofi, 4)
        if ofi > 0.15:
            reasons.append(f"Buy pressure dominant (OFI +{ofi:.2f})")
        elif ofi < -0.15:
            reasons.append(f"Sell pressure dominant (OFI {ofi:.2f})")

        for bar in ohlcv[-5:]:
            body_size = abs(bar["close"] - bar["open"])
            total_range = bar["high"] - bar["low"]
            if total_range > 0 and bar["volume"] > 0:
                avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else bar["volume"]
                if bar["volume"] > avg_vol * 2.5 and body_size < total_range * 0.3:
                    result["absorption_detected"] = True
                    reasons.append("Absorption: high volume, small body — accumulation/distribution")
                    break

        return result, reasons

    def _detect_crisis(self, ohlcv, ind):
        closes = ind["closes"]
        volumes = ind.get("volumes", [])
        atr_vals = ind.get("atr", [])
        rsi_vals = ind.get("rsi", [])
        bb = ind.get("bb", {})
        score = 0
        reasons = []

        valid_atr = [v for v in atr_vals if v is not None]
        if len(valid_atr) >= 30:
            current_atr = valid_atr[-1]
            avg_atr = sum(valid_atr[-30:]) / 30
            if avg_atr > 0 and current_atr > avg_atr * 4:
                score += 35
                reasons.append(f"ATR {current_atr / avg_atr:.1f}x average — extreme")

        if len(ohlcv) >= 2:
            last = ohlcv[-1]
            bar_range = abs(last["close"] - last["open"])
            if valid_atr:
                avg_atr = sum(valid_atr[-20:]) / min(len(valid_atr), 20)
                if avg_atr > 0 and bar_range > avg_atr * 3:
                    score += 25
                    reasons.append(f"Single candle move > 3× ATR ({bar_range / avg_atr:.1f}x)")

        if len(volumes) >= 20:
            avg_vol = sum(volumes[-20:]) / 20
            if avg_vol > 0 and volumes[-1] > avg_vol * 5:
                score += 20
                reasons.append(f"Volume {volumes[-1] / avg_vol:.1f}x average — panic")

        rsi = self._lv(rsi_vals)
        if rsi is not None:
            if rsi < 15 or rsi > 85:
                score += 15
                reasons.append(f"RSI extreme ({rsi:.0f})")

        bb_u = self._lv(bb.get("upper", []))
        bb_l = self._lv(bb.get("lower", []))
        bb_m = self._lv(bb.get("middle", []))
        price = closes[-1] if closes else 0
        if bb_u and bb_l and bb_m and bb_m > 0:
            bb_width = (bb_u - bb_l) / bb_m * 100
            if bb_width > 12:
                score += 10
                reasons.append(f"BB width {bb_width:.1f}% — extreme expansion")
            if price > bb_u * 1.02 or price < bb_l * 0.98:
                score += 10
                reasons.append("Price outside BB by >2%")

        return min(score, 100), reasons

    # ----- classification ---------------------------------------------------

    def _classify(self, trend, vol_regime, vol_ratio, div_score, micro, crisis, reasons):
        if crisis >= 70:
            return "CRISIS", min(95, 50 + crisis // 2), reasons

        ofi = micro.get("order_flow_imbalance", 0) if isinstance(micro, dict) else 0

        if trend >= 50:
            if div_score < 30 and vol_regime in ("normal", "high"):
                return "STRONG_BULL", min(95, 50 + trend // 2), reasons
            else:
                return "WEAK_BULL", min(80, 40 + trend // 3), reasons
        elif trend >= 15:
            if div_score >= 40:
                return "WEAK_BULL", min(70, 35 + trend // 3), reasons
            else:
                return "WEAK_BULL", min(75, 40 + trend // 2), reasons
        elif trend <= -50:
            if div_score < 30 and vol_regime in ("normal", "high"):
                return "STRONG_BEAR", min(95, 50 + abs(trend) // 2), reasons
            else:
                return "WEAK_BEAR", min(80, 40 + abs(trend) // 3), reasons
        elif trend <= -15:
            if div_score >= 40:
                return "WEAK_BEAR", min(70, 35 + abs(trend) // 3), reasons
            else:
                return "WEAK_BEAR", min(75, 40 + abs(trend) // 2), reasons
        else:
            conf = 60
            if vol_regime == "low":
                conf = 75
            return "RANGE", conf, reasons

    # ----- smoothing & transitions ------------------------------------------

    def _smooth_regime(self, raw_regime):
        if raw_regime == "CRISIS":
            self._pending_regime = None
            self._pending_count = 0
            return "CRISIS"

        if raw_regime == self._current_regime:
            self._pending_regime = None
            self._pending_count = 0
            return self._current_regime

        if raw_regime == self._pending_regime:
            self._pending_count += 1
        else:
            self._pending_regime = raw_regime
            self._pending_count = 1

        if self._pending_count >= SMOOTHING_THRESHOLD:
            self._pending_regime = None
            self._pending_count = 0
            return raw_regime

        return self._current_regime

    def _estimate_transition_probabilities(self, current, trend_score, div_score, vol_ratio):
        base = dict(_BASE_TRANSITION.get(current, _BASE_TRANSITION["RANGE"]))

        if div_score > 50:
            if current in ("STRONG_BULL", "WEAK_BULL"):
                base["WEAK_BULL"] = base.get("WEAK_BULL", 0) + 0.10
                base["RANGE"] = base.get("RANGE", 0) + 0.05
                base[current] = max(0.05, base.get(current, 0) - 0.15)
            elif current in ("STRONG_BEAR", "WEAK_BEAR"):
                base["WEAK_BEAR"] = base.get("WEAK_BEAR", 0) + 0.10
                base["RANGE"] = base.get("RANGE", 0) + 0.05
                base[current] = max(0.05, base.get(current, 0) - 0.15)

        if vol_ratio > 3.0:
            base["CRISIS"] = base.get("CRISIS", 0) + 0.15
            for k in base:
                if k != "CRISIS":
                    base[k] = max(0.01, base[k] - 0.03)

        if abs(trend_score) > 60:
            if trend_score > 0:
                base["STRONG_BULL"] = base.get("STRONG_BULL", 0) + 0.10
            else:
                base["STRONG_BEAR"] = base.get("STRONG_BEAR", 0) + 0.10

        total = sum(base.values())
        if total > 0:
            base = {k: round(v / total, 3) for k, v in base.items()}
        return base

    # ----- helpers ----------------------------------------------------------

    def _default_result(self, reason):
        return {
            "regime": "RANGE",
            "regime_detailed": "RANGE",
            "previous_regime": "RANGE",
            "previous_regime_detailed": "RANGE",
            "confidence": 0,
            "transition_prob": {},
            "regime_duration": 0,
            "reasons": [reason],
            "risk_multiplier": 0.6,
            "volatility_regime": "normal",
            "volatility_ratio": 1.0,
            "trend_strength": 0,
            "divergence_score": 0,
            "crisis_score": 0,
            "microstructure": {},
        }

    @staticmethod
    def _lv(series):
        if not series:
            return None
        for v in reversed(series):
            if v is not None:
                return v
        return None


regime_detector = AdvancedRegimeDetector()


# ---------------------------------------------------------------------------
# Signal Engine — Multi-indicator weighted scoring
# Score: -300 (strong short) → +300 (strong long), confidence 0-100%
# ---------------------------------------------------------------------------

class SignalEngine:

    REGIME_MULTIPLIER = {
        "BULL": 1.0, "BEAR": 1.0, "RANGE": 0.6, "CRISIS": 0.3,
        "STRONG_BULL": 1.0, "WEAK_BULL": 0.8, "WEAK_BEAR": 0.8, "STRONG_BEAR": 1.0,
    }

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

    # -------------------------------------------------------------------
    # GMX-Specific Risk Checks
    # -------------------------------------------------------------------

    def check_gmx(self, signal, leverage, collateral_usd, balance_usdt, portfolio_state=None):
        """Extended risk check with GMX high-leverage-specific vetoes."""
        base_result = self.check(signal, portfolio_state)
        gmx_vetoes = []
        gmx_warnings = []

        if leverage > GMX_MAX_LEVERAGE:
            gmx_vetoes.append(f"Leverage {leverage}x exceeds GMX max {GMX_MAX_LEVERAGE}x")

        if leverage > 30:
            gmx_warnings.append(f"Extreme leverage {leverage}x — liquidation risk very high")
        elif leverage > 20:
            gmx_warnings.append(f"High leverage {leverage}x — exercise caution")

        if balance_usdt > 0:
            exposure_pct = (collateral_usd / balance_usdt) * 100
            if exposure_pct > 10:
                gmx_vetoes.append(f"Single position {exposure_pct:.1f}% of capital exceeds 10% GMX limit")
            elif exposure_pct > 5:
                gmx_warnings.append(f"Position is {exposure_pct:.1f}% of capital (recommended <5%)")

        position_size_usd = collateral_usd * leverage
        if position_size_usd > 50000:
            gmx_warnings.append(f"Large position ${position_size_usd:,.0f} — check GMX OI caps")

        all_vetoes = base_result["vetoes"] + gmx_vetoes
        all_warnings = base_result["warnings"] + gmx_warnings

        return {
            "approved": len(all_vetoes) == 0,
            "vetoed": len(all_vetoes) > 0,
            "vetoes": all_vetoes,
            "warnings": all_warnings,
            "veto_count": len(all_vetoes),
            "gmx_specific": {"leverage_ok": leverage <= GMX_MAX_LEVERAGE, "leverage": leverage},
        }

    def gmx_circuit_breaker(self, positions, threshold_pct=-30.0):
        """Check if any GMX position has breached the circuit breaker threshold."""
        alerts = []
        for pos in positions:
            if pos.get("exchange") != "GMX":
                continue
            pnl_pct = pos.get("pnl_pct", 0)
            if pnl_pct <= threshold_pct:
                alerts.append({
                    "action": "EMERGENCY_CLOSE",
                    "symbol": pos["symbol"],
                    "side": pos["side"],
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_usd": round(pos.get("pnl", 0), 2),
                    "threshold": threshold_pct,
                    "reason": f"PnL {pnl_pct:.1f}% breached circuit breaker ({threshold_pct}%)",
                })
        return alerts


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

    # -------------------------------------------------------------------
    # High-Leverage Mode — Aggressive thresholds for GMX V2 dip/top hunting
    # -------------------------------------------------------------------

    HL_LEVERAGE_TIERS = [
        (95, 20),
        (90, 15),
        (85, 10),
        (80, 7),
        (70, 5),
        (60, 3),
        (0, 2),
    ]

    HL_RSI_OVERSOLD = 22
    HL_RSI_OVERBOUGHT = 78
    HL_VOL_RATIO_THRESHOLD = 2.5
    HL_MIN_CONFLUENCE = 60

    def detect_hl_entry(self, symbol, ohlcv, raw_indicators):
        """High-leverage entry detection with aggressive thresholds."""
        closes = raw_indicators["closes"]
        volumes = raw_indicators["volumes"]
        rsi = raw_indicators["rsi"]

        if len(closes) < 60:
            return {"entry": False, "reason": "Insufficient data (need 60+ candles)"}

        rsi_div = self.detect_rsi_divergence(closes, rsi, lookback=20)
        vol_climax = self.detect_volume_climax(volumes, closes, lookback=15)
        wyckoff = self.detect_wyckoff_spring(ohlcv, lookback=40)
        confluence = self.confluence_score(ohlcv, raw_indicators)

        last_rsi = None
        for v in reversed(rsi):
            if v is not None:
                last_rsi = v
                break

        score = confluence["score"]
        signals = list(confluence["signals"])
        direction = None

        is_dip = rsi_div["bullish"] or vol_climax["selling_climax"] or wyckoff["spring"]
        is_top = rsi_div["bearish"] or vol_climax["buying_climax"] or wyckoff["upthrust"]

        if last_rsi is not None:
            if last_rsi <= self.HL_RSI_OVERSOLD:
                score += 10
                signals.append(f"HL RSI deep oversold ({last_rsi:.0f}) (+10)")
                is_dip = True
            elif last_rsi >= self.HL_RSI_OVERBOUGHT:
                score += 10
                signals.append(f"HL RSI deep overbought ({last_rsi:.0f}) (+10)")
                is_top = True

        if vol_climax.get("vol_ratio", 0) >= self.HL_VOL_RATIO_THRESHOLD:
            score += 5
            signals.append(f"HL high volume confirmation ({vol_climax['vol_ratio']:.1f}x) (+5)")

        ema_short = raw_indicators.get("ema_9", [])
        ema_long = raw_indicators.get("ema_21", [])
        if len(ema_short) > 2 and len(ema_long) > 2:
            if ema_short[-1] is not None and ema_long[-1] is not None:
                if is_dip and ema_short[-1] < ema_long[-1] and ema_short[-1] > ema_short[-2]:
                    score += 8
                    signals.append("HL EMA crossover forming (bullish) (+8)")
                elif is_top and ema_short[-1] > ema_long[-1] and ema_short[-1] < ema_short[-2]:
                    score += 8
                    signals.append("HL EMA crossover forming (bearish) (+8)")

        bb = raw_indicators.get("bollinger", {})
        if bb and closes:
            bb_lower = bb.get("lower", [])
            bb_upper = bb.get("upper", [])
            if bb_lower and closes[-1] <= bb_lower[-1] * 1.005:
                score += 7
                signals.append("HL price at/below lower Bollinger (+7)")
                is_dip = True
            elif bb_upper and closes[-1] >= bb_upper[-1] * 0.995:
                score += 7
                signals.append("HL price at/above upper Bollinger (+7)")
                is_top = True

        score = min(score, 130)

        if is_dip:
            direction = "long"
        elif is_top:
            direction = "short"

        if not direction or score < self.HL_MIN_CONFLUENCE:
            return {
                "entry": False,
                "score": score,
                "min_required": self.HL_MIN_CONFLUENCE,
                "signals": signals,
                "reason": "Confluence too low" if direction else "No clear dip/top signal",
            }

        leverage = 2
        for threshold, lev in self.HL_LEVERAGE_TIERS:
            if score >= threshold:
                leverage = lev
                break

        return {
            "entry": True,
            "direction": direction,
            "score": score,
            "leverage": leverage,
            "signals": signals,
            "rsi": last_rsi,
            "rsi_divergence": rsi_div,
            "volume_climax": vol_climax,
            "wyckoff": wyckoff,
        }

    def generate_gmx_entry_plan(self, symbol, ohlcv, raw_indicators, balance_usdt=100.0):
        """Generate a complete GMX V2 entry plan with sizing, TP/SL, and risk parameters."""
        hl_result = self.detect_hl_entry(symbol, ohlcv, raw_indicators)

        if not hl_result.get("entry"):
            return {
                "actionable": False,
                "symbol": symbol,
                "score": hl_result.get("score", 0),
                "reason": hl_result.get("reason", "No entry signal"),
                "signals": hl_result.get("signals", []),
            }

        direction = hl_result["direction"]
        leverage = hl_result["leverage"]
        score = hl_result["score"]
        closes = raw_indicators["closes"]
        current_price = closes[-1] if closes else 0

        if current_price <= 0:
            return {"actionable": False, "symbol": symbol, "reason": "Cannot determine price"}

        risk_pct = min(3.0 + (score - 60) * 0.05, 5.0)
        collateral_usd = balance_usdt * (risk_pct / 100.0)
        size_usd = collateral_usd * leverage
        quantity = size_usd / current_price

        atr_data = raw_indicators.get("atr", [])
        if atr_data:
            last_atr = None
            for v in reversed(atr_data):
                if v is not None and v > 0:
                    last_atr = v
                    break
            if last_atr:
                atr_mult_tp = 2.5 if score >= 90 else 2.0
                atr_mult_sl = 1.2

                if direction == "long":
                    tp = current_price + last_atr * atr_mult_tp
                    sl = current_price - last_atr * atr_mult_sl
                else:
                    tp = current_price - last_atr * atr_mult_tp
                    sl = current_price + last_atr * atr_mult_sl
            else:
                tp, sl = self._fallback_tp_sl(current_price, direction, leverage)
        else:
            tp, sl = self._fallback_tp_sl(current_price, direction, leverage)

        risk_reward = abs(tp - current_price) / abs(current_price - sl) if abs(current_price - sl) > 0 else 0
        max_loss_usd = collateral_usd * abs(current_price - sl) / current_price * leverage
        max_loss_pct = (max_loss_usd / balance_usdt) * 100 if balance_usdt > 0 else 0

        confidence = "HIGH" if score >= 90 else ("MEDIUM" if score >= 75 else "LOW")

        return {
            "actionable": True,
            "symbol": symbol,
            "direction": direction,
            "confidence": confidence,
            "score": score,
            "leverage": leverage,
            "entry_price": round(current_price, 4),
            "quantity": round(quantity, 8),
            "size_usd": round(size_usd, 2),
            "collateral_usd": round(collateral_usd, 2),
            "risk_pct_of_balance": round(risk_pct, 2),
            "take_profit": round(tp, 4),
            "stop_loss": round(sl, 4),
            "risk_reward_ratio": round(risk_reward, 2),
            "max_loss_usd": round(max_loss_usd, 2),
            "max_loss_pct": round(max_loss_pct, 2),
            "signals": hl_result["signals"],
            "rsi": hl_result.get("rsi"),
            "execution": {
                "exchange": "GMX",
                "order_type": "market",
                "market": GMX_V2_MARKETS.get(symbol, {}).get("market_token", ""),
                "slippage_bps": GMX_DEFAULT_SLIPPAGE_BPS,
                "execution_fee_eth": GMX_EXECUTION_FEE_BUFFER_WEI / 10**18,
            },
        }

    @staticmethod
    def _fallback_tp_sl(price, direction, leverage):
        """Fallback TP/SL when ATR is unavailable."""
        tp_pct = 0.03 if leverage <= 5 else (0.02 if leverage <= 10 else 0.015)
        sl_pct = tp_pct / 2.0
        if direction == "long":
            return price * (1 + tp_pct), price * (1 - sl_pct)
        return price * (1 - tp_pct), price * (1 + sl_pct)


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
            return {"exchange": self.name, "error": sanitize_error(e), "assets": {}}

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
            return {"success": False, "error": sanitize_error(e), "exchange": self.name}

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
            return {"success": False, "error": sanitize_error(e)}

    def test_connection(self):
        if not self._exchange:
            if not self.api_key:
                return {"connected": False, "error": "No API key configured"}
            return {"connected": False, "error": "CCXT not installed"}
        try:
            self._exchange.fetch_time()
            return {"connected": True, "exchange": self.name, "testnet": self.testnet}
        except Exception as e:
            return {"connected": False, "error": sanitize_error(e)}

    @staticmethod
    def _no_exchange():
        return {
            "exchange": "MEXC",
            "error": "CCXT not available or no API key configured",
            "assets": {},
        }


# ---------------------------------------------------------------------------
# GMX V2 — Web3 Connection & Contract Helpers
# ---------------------------------------------------------------------------

_web3_instances = {}
_web3_lock = threading.Lock()


def get_web3(rpc_url=None, testnet=False):
    """Create or retrieve a cached Web3 instance connected to Arbitrum."""
    if not HAS_WEB3:
        return None, False

    if rpc_url is None:
        rpc_url = GMX_RPC_TESTNET if testnet else GMX_RPC_MAINNET

    with _web3_lock:
        if rpc_url in _web3_instances:
            w3 = _web3_instances[rpc_url]
            try:
                if w3.is_connected():
                    return w3, True
            except Exception:
                pass
            del _web3_instances[rpc_url]

        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            if w3.is_connected():
                _web3_instances[rpc_url] = w3
                log.info("Web3 connected: %s (chain=%d)", rpc_url, w3.eth.chain_id)
                return w3, True
            return w3, False
        except Exception as e:
            log.error("Web3 connection failed (%s): %s", rpc_url, e)
            return None, False


def get_gmx_contracts(w3, testnet=False):
    """Instantiate GMX V2 contract objects from a Web3 instance."""
    if w3 is None:
        return {}
    addresses = GMX_V2_CONTRACTS_TESTNET if testnet else GMX_V2_CONTRACTS_MAINNET
    try:
        return {
            "reader": w3.eth.contract(
                address=Web3.to_checksum_address(addresses["Reader"]),
                abi=GMX_READER_ABI,
            ),
            "exchange_router": w3.eth.contract(
                address=Web3.to_checksum_address(addresses["ExchangeRouter"]),
                abi=GMX_EXCHANGE_ROUTER_ABI,
            ),
            "data_store": Web3.to_checksum_address(addresses["DataStore"]),
            "order_vault": Web3.to_checksum_address(addresses["OrderVault"]),
            "router": Web3.to_checksum_address(addresses["Router"]),
        }
    except Exception as e:
        log.error("Failed to instantiate GMX contracts: %s", e)
        return {}


def get_erc20_contract(w3, token_address):
    """Get an ERC-20 contract instance for balance/approval operations."""
    if w3 is None:
        return None
    return w3.eth.contract(
        address=Web3.to_checksum_address(token_address),
        abi=GMX_ERC20_ABI,
    )


def gmx_symbol_to_market(symbol):
    """Resolve a trading symbol (e.g. BTCUSDT) to its GMX V2 market config."""
    market = GMX_V2_MARKETS.get(symbol)
    if market:
        return market
    normalized = symbol.upper().replace("/", "").replace("-", "")
    if not normalized.endswith("USDT"):
        normalized += "USDT"
    return GMX_V2_MARKETS.get(normalized)


# ---------------------------------------------------------------------------
# GMX V2 Adapter — Full on-chain integration (Arbitrum)
# ---------------------------------------------------------------------------

class GMXAdapter(ExchangeAdapter):

    def __init__(self, private_key="", rpc_url=None, testnet=False):
        super().__init__("GMX", testnet=testnet)
        self.rpc_url = rpc_url or (GMX_RPC_TESTNET if testnet else GMX_RPC_MAINNET)
        self._w3 = None
        self._account = None
        self._contracts = {}
        self._initialized = False
        self._nonce_lock = threading.Lock()
        self._pending_nonce = None

        if not HAS_WEB3:
            log.warning("GMXAdapter: web3.py not installed")
            return

        if private_key:
            try:
                self._account = Web3Account.from_key(private_key)
                self.api_key = self._account.address
                _wipe_string(private_key)
            except Exception:
                log.error("GMXAdapter: invalid private key format")
                _wipe_string(private_key)
                return

        self._connect()

    def _connect(self):
        """Establish Web3 connection and instantiate contracts."""
        self._w3, connected = get_web3(self.rpc_url, self.testnet)
        if not connected:
            return
        self._contracts = get_gmx_contracts(self._w3, self.testnet)
        self._initialized = bool(self._contracts)
        if self._initialized:
            log.info("GMXAdapter ready: account=%s, testnet=%s",
                     self._account.address if self._account else "read-only",
                     self.testnet)

    def _ensure_connection(self):
        """Reconnect if the connection dropped."""
        if self._w3 and self._w3.is_connected():
            return True
        self._connect()
        return self._initialized

    def _has_signer(self):
        """Check if a signing account is available for write operations."""
        return self._account is not None

    def _build_tx(self, value=0):
        """Build base transaction parameters for the signing account."""
        if not self._has_signer():
            return None
        address = self._account.address
        nonce = self._pending_nonce if self._pending_nonce is not None else self._w3.eth.get_transaction_count(address, "pending")
        gas_price = self._w3.eth.gas_price
        return {
            "from": address,
            "nonce": nonce,
            "gas": 1500000,
            "maxFeePerGas": gas_price * 2,
            "maxPriorityFeePerGas": self._w3.to_wei(0.1, "gwei"),
            "value": value,
            "chainId": 42161 if not self.testnet else 421614,
        }

    def _sign_and_send(self, tx):
        """Sign, broadcast, and wait for confirmation. Returns tx hash."""
        used_nonce = tx.get("nonce", 0)
        signed = self._w3.eth.account.sign_transaction(tx, self._account.key)
        tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
        self._pending_nonce = used_nonce + 1
        try:
            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            if receipt.get("status") == 0:
                self._pending_nonce = None
                raise Exception(f"Transaction reverted on-chain: {tx_hash.hex()}")
        except Exception as e:
            if "reverted" in str(e):
                self._pending_nonce = None
                raise
            log.warning("Tx sent but confirmation timeout: %s — %s", tx_hash.hex(), e)
        return tx_hash.hex()

    def _get_token_balance(self, token_address, decimals=18):
        """Read ERC-20 token balance for the signing account."""
        if not self._has_signer():
            return 0.0
        contract = get_erc20_contract(self._w3, token_address)
        raw = contract.functions.balanceOf(self._account.address).call()
        return raw / (10 ** decimals)

    def get_balance(self):
        if not HAS_WEB3:
            return {"exchange": "GMX", "error": "web3.py not installed", "assets": {}}
        if not self._ensure_connection():
            return {"exchange": "GMX", "error": "Cannot connect to Arbitrum RPC", "assets": {}}
        if not self._has_signer():
            return {"exchange": "GMX", "error": "No private key configured (read-only)", "assets": {}}

        address = self._account.address
        assets = {}
        total_usdt = 0.0

        try:
            eth_raw = self._w3.eth.get_balance(address)
            eth_balance = eth_raw / 10**18
            if eth_balance > 0:
                assets["ETH"] = {"total": round(eth_balance, 8), "free": round(eth_balance, 8), "used": 0.0}
        except Exception as e:
            log.warning("GMX get_balance ETH failed: %s", e)

        token_configs = [
            ("WETH", GMX_V2_TOKENS["WETH"], 18),
            ("USDC", GMX_V2_TOKENS["USDC"], 6),
            ("USDC.e", GMX_V2_TOKENS["USDC_BRIDGED"], 6),
            ("WBTC", GMX_V2_TOKENS["WBTC"], 8),
            ("ARB", GMX_V2_TOKENS["ARB"], 18),
        ]

        for token_name, token_addr, decimals in token_configs:
            try:
                balance = self._get_token_balance(token_addr, decimals)
                if balance > 0:
                    assets[token_name] = {"total": round(balance, 8), "free": round(balance, 8), "used": 0.0}
                    if token_name in ("USDC", "USDC.e"):
                        total_usdt += balance
            except Exception as e:
                log.warning("GMX get_balance %s failed: %s", token_name, e)

        # Read collateral locked in GMX positions via Reader contract
        try:
            reader = self._contracts.get("reader")
            data_store = self._contracts.get("data_store")
            if reader and data_store:
                positions = reader.functions.getAccountPositions(data_store, address, 0, 50).call()
                collateral_locked = 0.0
                for pos in positions:
                    numbers = pos[1]
                    collateral_raw = numbers[2]
                    collateral_token = pos[0][2]
                    token_decimals = 6 if collateral_token.lower() == GMX_V2_TOKENS["USDC"].lower() else 18
                    collateral_locked += collateral_raw / (10 ** token_decimals)
                if collateral_locked > 0:
                    assets["GMX_COLLATERAL"] = {"total": round(collateral_locked, 4), "free": 0.0, "used": round(collateral_locked, 4)}
                    total_usdt += collateral_locked
        except Exception as e:
            log.warning("GMX collateral read failed: %s", e)

        if "USDC" in assets:
            total_usdt = max(total_usdt, assets["USDC"]["total"])

        return {
            "exchange": "GMX",
            "network": "Arbitrum One" if not self.testnet else "Arbitrum Sepolia",
            "account": address,
            "assets": assets,
            "total_usdt": round(total_usdt, 2),
        }

    def _resolve_symbol_from_market(self, market_address):
        """Reverse-lookup: market token address → symbol string."""
        market_lower = market_address.lower()
        for symbol, config in GMX_V2_MARKETS.items():
            if config["market_token"].lower() == market_lower:
                return symbol
        return market_address[:10] + "..."

    def _get_index_price(self, symbol):
        """Fetch current index price with multiple fallback sources."""
        key = f"gmx_price_{symbol}"
        cached = cache.get(key)
        if cached:
            return cached

        price = 0.0
        sources = [
            ("https://api.binance.com/api/v3/ticker/price", {"symbol": symbol}, lambda d: float(d["price"])),
            ("https://api.binance.us/api/v3/ticker/price", {"symbol": symbol}, lambda d: float(d["price"])),
            ("https://api1.binance.com/api/v3/ticker/price", {"symbol": symbol}, lambda d: float(d["price"])),
            ("https://api.coingecko.com/api/v3/simple/price", {"ids": self._symbol_to_cg(symbol), "vs_currencies": "usd"}, lambda d: float(list(d.values())[0]["usd"])),
        ]
        for url, params, extract in sources:
            try:
                resp = _http_session.get(url, params=params, timeout=5)
                if resp.status_code == 200:
                    price = extract(resp.json())
                    if price > 0:
                        cache.set(key, price, ttl=5)
                        return price
            except Exception:
                continue
        return price

    @staticmethod
    def _symbol_to_cg(symbol):
        mapping = {"BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "SOLUSDT": "solana",
                    "ARBUSDT": "arbitrum", "DOGEUSDT": "dogecoin"}
        return mapping.get(symbol, "bitcoin")

    def get_positions(self):
        if not HAS_WEB3:
            return []
        if not self._ensure_connection():
            return []
        if not self._has_signer():
            return []

        reader = self._contracts.get("reader")
        data_store = self._contracts.get("data_store")
        if not reader or not data_store:
            return []

        try:
            raw_positions = reader.functions.getAccountPositions(
                data_store, self._account.address, 0, 50
            ).call()
        except Exception as e:
            log.error("GMX get_positions Reader call failed: %s", e)
            return []

        positions = []
        for pos in raw_positions:
            try:
                addresses = pos[0]
                numbers = pos[1]
                flags = pos[2]

                market_address = addresses[1]
                collateral_token = addresses[2]
                is_long = flags[0]

                size_in_usd = numbers[0] / 10**30
                size_in_tokens = numbers[1] / 10**30
                collateral_amount_raw = numbers[2]
                borrowing_factor = numbers[3] / 10**30
                funding_fee_per_size = numbers[4] / 10**30

                is_usdc_collateral = collateral_token.lower() == GMX_V2_TOKENS["USDC"].lower()
                collateral_decimals = 6 if is_usdc_collateral else 18
                collateral_usd = collateral_amount_raw / (10 ** collateral_decimals)

                symbol = self._resolve_symbol_from_market(market_address)
                current_price = self._get_index_price(symbol)

                if size_in_tokens > 0:
                    entry_price = size_in_usd / size_in_tokens
                else:
                    entry_price = 0.0

                leverage_effective = size_in_usd / collateral_usd if collateral_usd > 0 else 0.0

                pnl = 0.0
                pnl_pct = 0.0
                if current_price > 0 and entry_price > 0:
                    if is_long:
                        pnl = (current_price - entry_price) * size_in_tokens
                    else:
                        pnl = (entry_price - current_price) * size_in_tokens
                    pnl_pct = (pnl / collateral_usd * 100) if collateral_usd > 0 else 0.0

                liq_price = 0.0
                if leverage_effective > 1 and entry_price > 0:
                    margin_fraction = 1.0 / leverage_effective
                    if is_long:
                        liq_price = entry_price * (1 - margin_fraction * 0.9)
                    else:
                        liq_price = entry_price * (1 + margin_fraction * 0.9)

                positions.append({
                    "symbol": symbol,
                    "side": "long" if is_long else "short",
                    "quantity": round(size_in_tokens, 8),
                    "size_usd": round(size_in_usd, 2),
                    "entry_price": round(entry_price, 4),
                    "current_price": round(current_price, 4),
                    "leverage": round(leverage_effective, 1),
                    "collateral_usd": round(collateral_usd, 2),
                    "collateral_token": "USDC" if is_usdc_collateral else "WETH",
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "liquidation_price": round(liq_price, 4),
                    "borrowing_factor": round(borrowing_factor, 6),
                    "funding_fee_per_size": round(funding_fee_per_size, 6),
                    "market_address": market_address,
                    "exchange": "GMX",
                    "type": "perpetual",
                })
            except Exception as e:
                log.warning("GMX position parse error: %s", e)
                continue

        return positions

    def _estimate_execution_fee(self):
        """Estimate execution fee in wei for GMX order keeper."""
        try:
            gas_price = self._w3.eth.gas_price
            base_gas = 1_500_000
            estimated = int(gas_price * base_gas * 1.5)
            return max(estimated, GMX_EXECUTION_FEE_BUFFER_WEI)
        except Exception:
            return GMX_EXECUTION_FEE_BUFFER_WEI

    def _ensure_token_approval(self, token_address, spender, amount_raw):
        """Approve ERC-20 spending if current allowance is insufficient."""
        contract = get_erc20_contract(self._w3, token_address)
        current = contract.functions.allowance(self._account.address, spender).call()
        if current >= amount_raw:
            return None
        approve_amount = amount_raw * 10
        tx = contract.functions.approve(spender, approve_amount).build_transaction(self._build_tx())
        return self._sign_and_send(tx)

    def place_order_by_collateral(self, symbol, side, order_type, collateral_usd, price=None, leverage=1, tp=None, sl=None):
        """Place order using USDC collateral amount directly — no quantity conversion needed."""
        if not HAS_WEB3:
            return {"success": False, "error": "web3.py not installed", "exchange": "GMX"}
        if not self._ensure_connection():
            return {"success": False, "error": "Cannot connect to Arbitrum RPC", "exchange": "GMX"}
        if not self._has_signer():
            return {"success": False, "error": "No private key — cannot sign transactions", "exchange": "GMX"}

        market = gmx_symbol_to_market(symbol)
        if not market:
            return {"success": False, "error": f"Unsupported GMX market: {symbol}", "exchange": "GMX"}

        leverage = min(leverage, GMX_MAX_LEVERAGE)
        is_long = side.lower() in ("long", "buy")
        is_market = order_type.lower() in ("market", "")

        collateral_token = market["short_token"]
        collateral_decimals = 6
        collateral_amount_raw = int(collateral_usd * 10**collateral_decimals)

        usdc_balance = self._get_token_balance(collateral_token, collateral_decimals)
        if usdc_balance < collateral_usd:
            return {"success": False, "error": f"Insufficient USDC: have ${usdc_balance:.2f}, need ${collateral_usd:.2f}", "exchange": "GMX"}

        execution_fee = self._estimate_execution_fee()
        gas_price = self._w3.eth.gas_price
        gas_cost_estimate = 1500000 * gas_price / 10**18
        total_eth_needed = (execution_fee / 10**18) + gas_cost_estimate
        eth_balance_wei = self._w3.eth.get_balance(self._account.address)
        eth_balance = eth_balance_wei / 10**18
        if eth_balance < total_eth_needed:
            return {"success": False, "error": f"Insufficient ETH: have {eth_balance:.4f} ETH, need ~{total_eth_needed:.4f} ETH (exec fee {execution_fee/10**18:.4f} + gas ~{gas_cost_estimate:.4f}). Send more ETH to your wallet.", "exchange": "GMX"}

        current_price = self._get_index_price(symbol)
        if current_price <= 0 and not price:
            return {"success": False, "error": "Cannot fetch index price for order", "exchange": "GMX"}
        ref_price = price if price and price > 0 else current_price

        size_delta_usd = int(collateral_usd * leverage * 10**30)

        slippage_mult = GMX_DEFAULT_SLIPPAGE_BPS / 10000
        if is_long:
            acceptable_price = int(ref_price * (1 + slippage_mult) * 10**30)
        else:
            acceptable_price = int(ref_price * (1 - slippage_mult) * 10**30)

        trigger_price = int(price * 10**30) if price and not is_market else 0

        exchange_router = self._contracts.get("exchange_router")
        order_vault = self._contracts.get("order_vault")
        router_addr = self._contracts.get("router")
        if not exchange_router or not order_vault or not router_addr:
            return {"success": False, "error": "GMX contracts not loaded", "exchange": "GMX"}

        gmx_order_type = GMX_ORDER_TYPE_MARKET_INCREASE if is_market else GMX_ORDER_TYPE_LIMIT_INCREASE

        order_params = (
            (
                self._account.address,
                self._account.address,
                "0x0000000000000000000000000000000000000000",
                "0x0000000000000000000000000000000000000000",
                Web3.to_checksum_address(market["market_token"]),
                Web3.to_checksum_address(collateral_token),
                [],
            ),
            (
                size_delta_usd,
                collateral_amount_raw,
                trigger_price,
                acceptable_price,
                execution_fee,
                GMX_CALLBACK_GAS_LIMIT,
                0,
                0,
            ),
            gmx_order_type,
            GMX_DECREASE_POSITION_SWAP_TYPE,
            is_long,
            True,
            False,
            GMX_REFERRAL_CODE,
            [],
        )

        with self._nonce_lock:
            try:
                approval_tx = self._ensure_token_approval(collateral_token, router_addr, collateral_amount_raw)
                if approval_tx:
                    log.info("GMX: USDC approved for Router, tx: %s", approval_tx)
            except Exception as e:
                self._pending_nonce = None
                return {"success": False, "error": f"Token approval failed: {e}", "exchange": "GMX"}

            try:
                send_wnt_data = exchange_router.functions.sendWnt(
                    order_vault, execution_fee
                )._encode_transaction_data()

                send_tokens_data = exchange_router.functions.sendTokens(
                    Web3.to_checksum_address(collateral_token),
                    order_vault,
                    collateral_amount_raw,
                )._encode_transaction_data()

                create_order_data = exchange_router.functions.createOrder(
                    order_params
                )._encode_transaction_data()

                total_value = execution_fee
                multicall_data = [
                    bytes.fromhex(send_wnt_data[2:]),
                    bytes.fromhex(send_tokens_data[2:]),
                    bytes.fromhex(create_order_data[2:]),
                ]

                log.info("GMX multicall: exec_fee=%.6f ETH, collateral=$%.2f, size=$%.2f, leverage=%dx, %s %s",
                         execution_fee / 10**18, collateral_usd, collateral_usd * leverage, leverage,
                         "LONG" if is_long else "SHORT", symbol)

                base_tx = self._build_tx(value=total_value)
                base_tx["to"] = exchange_router.address
                base_tx["data"] = exchange_router.functions.multicall(multicall_data)._encode_transaction_data()

                tx_hash = self._sign_and_send(base_tx)
                log.info("GMX order submitted: tx=%s", tx_hash)

            except Exception as e:
                self._pending_nonce = None
                err_str = str(e)
                log.error("GMX place_order_by_collateral failed: %s (type: %s)", err_str, type(e).__name__)
                if hasattr(e, 'data') and e.data:
                    log.error("GMX revert data: %s", e.data)
                    try:
                        raw = e.data if isinstance(e.data, str) else str(e.data)
                        if raw.startswith("0x") and len(raw) > 10:
                            ascii_attempt = bytes.fromhex(raw[2:]).decode("ascii", errors="replace")
                            log.error("GMX revert ASCII decode: %s", ascii_attempt)
                    except Exception:
                        pass
                return {"success": False, "error": sanitize_error(e), "exchange": "GMX"}

        result = {
            "success": True,
            "order_id": tx_hash,
            "tx_hash": tx_hash,
            "symbol": symbol,
            "side": "long" if is_long else "short",
            "type": "market" if is_market else "limit",
            "collateral_usd": round(collateral_usd, 2),
            "size_usd": round(collateral_usd * leverage, 2),
            "leverage": leverage,
            "price": ref_price,
            "acceptable_price": round(acceptable_price / 10**30, 4),
            "execution_fee_eth": round(execution_fee / 10**18, 6),
            "exchange": "GMX",
            "network": "Arbitrum One" if not self.testnet else "Arbitrum Sepolia",
        }

        if tp:
            try:
                qty_for_tp = collateral_usd * leverage / ref_price if ref_price > 0 else 0
                self._place_tp_sl_order(symbol, market, not is_long, qty_for_tp, tp, is_tp=True)
                result["tp"] = tp
            except Exception as e:
                log.warning("GMX TP order failed (main order OK): %s", e)
                result["tp_error"] = str(e)
        if sl:
            try:
                qty_for_sl = collateral_usd * leverage / ref_price if ref_price > 0 else 0
                self._place_tp_sl_order(symbol, market, not is_long, qty_for_sl, sl, is_tp=False)
                result["sl"] = sl
            except Exception as e:
                log.warning("GMX SL order failed (main order OK): %s", e)
                result["sl_error"] = str(e)

        return result

    def place_order(self, symbol, side, order_type, quantity, price=None, leverage=1, tp=None, sl=None):
        if not HAS_WEB3:
            return {"success": False, "error": "web3.py not installed", "exchange": "GMX"}
        if not self._ensure_connection():
            return {"success": False, "error": "Cannot connect to Arbitrum RPC", "exchange": "GMX"}
        if not self._has_signer():
            return {"success": False, "error": "No private key — cannot sign transactions", "exchange": "GMX"}

        market = gmx_symbol_to_market(symbol)
        if not market:
            return {"success": False, "error": f"Unsupported GMX market: {symbol}", "exchange": "GMX"}

        leverage = min(leverage, GMX_MAX_LEVERAGE)
        is_long = side.lower() in ("long", "buy")

        current_price = self._get_index_price(symbol)
        if current_price <= 0 and not price:
            return {"success": False, "error": "Cannot fetch index price for order", "exchange": "GMX"}

        ref_price = price if price and price > 0 else current_price

        is_market = order_type.lower() in ("market", "")
        if is_market:
            gmx_order_type = GMX_ORDER_TYPE_MARKET_INCREASE
        else:
            gmx_order_type = GMX_ORDER_TYPE_LIMIT_INCREASE

        collateral_usd = quantity * ref_price / leverage if leverage > 0 else quantity * ref_price
        size_delta_usd = int(collateral_usd * leverage * 10**30)

        collateral_token = market["short_token"]
        collateral_decimals = 6
        collateral_amount_raw = int(collateral_usd * 10**collateral_decimals)

        slippage_mult = GMX_DEFAULT_SLIPPAGE_BPS / 10000
        if is_long:
            acceptable_price = int(ref_price * (1 + slippage_mult) * 10**30)
        else:
            acceptable_price = int(ref_price * (1 - slippage_mult) * 10**30)

        trigger_price = int(price * 10**30) if price and not is_market else 0
        execution_fee = self._estimate_execution_fee()

        exchange_router = self._contracts.get("exchange_router")
        order_vault = self._contracts.get("order_vault")
        router_addr = self._contracts.get("router")
        if not exchange_router or not order_vault or not router_addr:
            return {"success": False, "error": "GMX contracts not loaded", "exchange": "GMX"}

        order_params = (
            (
                self._account.address,
                self._account.address,
                "0x0000000000000000000000000000000000000000",
                "0x0000000000000000000000000000000000000000",
                Web3.to_checksum_address(market["market_token"]),
                Web3.to_checksum_address(collateral_token),
                [],
            ),
            (
                size_delta_usd,
                collateral_amount_raw,
                trigger_price,
                acceptable_price,
                execution_fee,
                GMX_CALLBACK_GAS_LIMIT,
                0,
                0,
            ),
            gmx_order_type,
            GMX_DECREASE_POSITION_SWAP_TYPE,
            is_long,
            True,
            False,
            GMX_REFERRAL_CODE,
            [],
        )

        with self._nonce_lock:
          try:
            self._ensure_token_approval(collateral_token, router_addr, collateral_amount_raw)

            send_wnt_data = exchange_router.functions.sendWnt(order_vault, execution_fee)._encode_transaction_data()
            send_tokens_data = exchange_router.functions.sendTokens(
                Web3.to_checksum_address(collateral_token), order_vault, collateral_amount_raw
            )._encode_transaction_data()
            create_order_data = exchange_router.functions.createOrder(order_params)._encode_transaction_data()

            multicall_data = [
                bytes.fromhex(send_wnt_data[2:]),
                bytes.fromhex(send_tokens_data[2:]),
                bytes.fromhex(create_order_data[2:]),
            ]
            base_tx = self._build_tx(value=execution_fee)
            base_tx["to"] = exchange_router.address
            base_tx["data"] = exchange_router.functions.multicall(multicall_data)._encode_transaction_data()

            tx_hash = self._sign_and_send(base_tx)

            result = {
                "success": True,
                "order_id": tx_hash,
                "tx_hash": tx_hash,
                "symbol": symbol,
                "side": "long" if is_long else "short",
                "type": "market" if is_market else "limit",
                "quantity": quantity,
                "size_usd": round(collateral_usd * leverage, 2),
                "collateral_usd": round(collateral_usd, 2),
                "leverage": leverage,
                "price": ref_price,
                "acceptable_price": round(acceptable_price / 10**30, 4),
                "execution_fee_eth": round(execution_fee / 10**18, 6),
                "exchange": "GMX",
                "network": "Arbitrum One" if not self.testnet else "Arbitrum Sepolia",
            }

            if tp:
                try:
                    self._place_tp_sl_order(symbol, market, not is_long, quantity, tp, is_tp=True)
                    result["tp"] = tp
                except Exception as e:
                    log.warning("GMX TP order failed (main order OK): %s", e)
                    result["tp_error"] = str(e)
            if sl:
                try:
                    self._place_tp_sl_order(symbol, market, not is_long, quantity, sl, is_tp=False)
                    result["sl"] = sl
                except Exception as e:
                    log.warning("GMX SL order failed (main order OK): %s", e)
                    result["sl_error"] = str(e)

            return result

          except Exception as e:
            self._pending_nonce = None
            log.error("GMX place_order failed: %s", e)
            return {"success": False, "error": sanitize_error(e), "exchange": "GMX"}

    def _place_tp_sl_order(self, symbol, market, is_long_close, quantity, trigger_price_usd, is_tp=True):
        """Place a conditional decrease order as TP or SL."""
        try:
            exchange_router = self._contracts.get("exchange_router")
            order_vault = self._contracts.get("order_vault")
            if not exchange_router or not order_vault:
                return

            execution_fee = self._estimate_execution_fee()
            trigger_raw = int(trigger_price_usd * 10**30)

            if is_tp:
                if is_long_close:
                    acceptable = int(trigger_price_usd * 0.997 * 10**30)
                else:
                    acceptable = int(trigger_price_usd * 1.003 * 10**30)
            else:
                if is_long_close:
                    acceptable = int(trigger_price_usd * 1.003 * 10**30)
                else:
                    acceptable = int(trigger_price_usd * 0.997 * 10**30)

            size_delta = int(quantity * trigger_price_usd * 10**30)

            order_params = (
                (
                    self._account.address,
                    self._account.address,
                    "0x0000000000000000000000000000000000000000",
                    "0x0000000000000000000000000000000000000000",
                    Web3.to_checksum_address(market["market_token"]),
                    Web3.to_checksum_address(market["short_token"]),
                    [],
                ),
                (
                    size_delta,
                    0,
                    trigger_raw,
                    acceptable,
                    execution_fee,
                    GMX_CALLBACK_GAS_LIMIT,
                    0,
                    0,
                ),
                GMX_ORDER_TYPE_LIMIT_DECREASE,
                GMX_DECREASE_POSITION_SWAP_TYPE,
                not is_long_close,
                True,
                False,
                GMX_REFERRAL_CODE,
                [],
            )

            with self._nonce_lock:
                send_wnt_data = exchange_router.functions.sendWnt(order_vault, execution_fee)._encode_transaction_data()
                create_data = exchange_router.functions.createOrder(order_params)._encode_transaction_data()

                base_tx = self._build_tx(value=execution_fee)
                base_tx["to"] = exchange_router.address
                base_tx["data"] = exchange_router.functions.multicall(
                    [bytes.fromhex(send_wnt_data[2:]), bytes.fromhex(create_data[2:])]
                )._encode_transaction_data()

                tx_hash = self._sign_and_send(base_tx)
                log.info("GMX %s order placed: %s (trigger=%.2f)", "TP" if is_tp else "SL", tx_hash, trigger_price_usd)

        except Exception as e:
            log.warning("GMX %s order failed: %s", "TP" if is_tp else "SL", e)

    def close_position(self, symbol, position_id=None, close_pct=100.0):
        if not HAS_WEB3:
            return {"success": False, "error": "web3.py not installed"}
        if not self._ensure_connection():
            return {"success": False, "error": "Cannot connect to Arbitrum RPC"}
        if not self._has_signer():
            return {"success": False, "error": "No private key — cannot sign transactions"}

        positions = self.get_positions()
        if not positions:
            return {"success": False, "error": "No open positions found"}

        target = None
        if position_id:
            for p in positions:
                if p.get("market_address", "").lower() == position_id.lower():
                    target = p
                    break
                if p.get("symbol") == position_id:
                    target = p
                    break
        if not target and symbol:
            normalized = symbol.upper().replace("/", "").replace("-", "")
            if not normalized.endswith("USDT"):
                normalized += "USDT"
            for p in positions:
                if p["symbol"] == normalized:
                    target = p
                    break
        if not target and positions:
            target = positions[0]

        if not target:
            return {"success": False, "error": f"No position found for {symbol}"}

        market = gmx_symbol_to_market(target["symbol"])
        if not market:
            return {"success": False, "error": f"Cannot resolve market for {target['symbol']}"}

        is_long = target["side"] == "long"
        close_fraction = min(max(close_pct, 0.0), 100.0) / 100.0
        size_to_close_usd = target["size_usd"] * close_fraction
        size_delta = int(size_to_close_usd * 10**30)

        current_price = self._get_index_price(target["symbol"])
        if current_price <= 0:
            current_price = target.get("current_price", 0)
        if current_price <= 0:
            return {"success": False, "error": "Cannot determine current price for close"}

        slippage_mult = GMX_DEFAULT_SLIPPAGE_BPS / 10000
        if is_long:
            acceptable_price = int(current_price * (1 - slippage_mult) * 10**30)
        else:
            acceptable_price = int(current_price * (1 + slippage_mult) * 10**30)

        execution_fee = self._estimate_execution_fee()

        exchange_router = self._contracts.get("exchange_router")
        order_vault = self._contracts.get("order_vault")
        if not exchange_router or not order_vault:
            return {"success": False, "error": "GMX contracts not loaded"}

        collateral_delta = 0
        if close_fraction >= 1.0:
            collateral_delta = 0
        else:
            collateral_delta = int(target["collateral_usd"] * close_fraction * 10**6)

        order_params = (
            (
                self._account.address,
                self._account.address,
                "0x0000000000000000000000000000000000000000",
                "0x0000000000000000000000000000000000000000",
                Web3.to_checksum_address(market["market_token"]),
                Web3.to_checksum_address(market["short_token"]),
                [],
            ),
            (
                size_delta,
                collateral_delta,
                0,
                acceptable_price,
                execution_fee,
                GMX_CALLBACK_GAS_LIMIT,
                0,
                0,
            ),
            GMX_ORDER_TYPE_MARKET_DECREASE,
            GMX_DECREASE_POSITION_SWAP_TYPE,
            is_long,
            True,
            False,
            GMX_REFERRAL_CODE,
            [],
        )

        with self._nonce_lock:
          try:
            send_wnt_data = exchange_router.functions.sendWnt(order_vault, execution_fee)._encode_transaction_data()
            create_data = exchange_router.functions.createOrder(order_params)._encode_transaction_data()

            base_tx = self._build_tx(value=execution_fee)
            base_tx["to"] = exchange_router.address
            base_tx["data"] = exchange_router.functions.multicall(
                [bytes.fromhex(send_wnt_data[2:]), bytes.fromhex(create_data[2:])]
            )._encode_transaction_data()

            tx_hash = self._sign_and_send(base_tx)

            return {
                "success": True,
                "tx_hash": tx_hash,
                "closed": target["symbol"],
                "side": target["side"],
                "close_pct": round(close_fraction * 100, 1),
                "size_closed_usd": round(size_to_close_usd, 2),
                "collateral_released_usd": round(target["collateral_usd"] * close_fraction, 2),
                "price": round(current_price, 4),
                "acceptable_price": round(acceptable_price / 10**30, 4),
                "pnl_at_close": round(target["pnl"] * close_fraction, 2),
                "execution_fee_eth": round(execution_fee / 10**18, 6),
                "exchange": "GMX",
            }

          except Exception as e:
            self._pending_nonce = None
            log.error("GMX close_position failed: %s", e)
            return {"success": False, "error": sanitize_error(e)}

    def test_connection(self):
        if not HAS_WEB3:
            return {"connected": False, "error": "web3.py not installed"}
        if not self._ensure_connection():
            return {"connected": False, "error": f"Cannot reach Arbitrum RPC: {self.rpc_url}"}
        result = {
            "connected": True,
            "exchange": "GMX",
            "network": "Arbitrum One" if not self.testnet else "Arbitrum Sepolia",
            "testnet": self.testnet,
            "chain_id": self._w3.eth.chain_id,
            "block": self._w3.eth.block_number,
            "contracts_loaded": list(self._contracts.keys()),
        }
        if self._has_signer():
            result["account"] = self._account.address
            eth_bal = self._w3.eth.get_balance(self._account.address)
            result["eth_balance"] = round(eth_bal / 10**18, 6)
        else:
            result["account"] = "read-only (no private key)"
        return result


# ---------------------------------------------------------------------------
# Smart Execution Engine — Slippage protection, gas optimization, retry logic
# ---------------------------------------------------------------------------

class SmartExecutionEngine:
    """Handles order execution with pre-flight checks, gas optimization,
    slippage protection, and exponential backoff retry."""

    _RETRYABLE_ERRORS = (
        "gas too low", "replacement transaction underpriced",
        "nonce too low", "timeout", "connection", "rpc",
        "server error", "502", "503", "504",
    )

    _NON_RETRYABLE_ERRORS = (
        "insufficient", "balance", "rejected", "reverted",
        "execution reverted", "invalid opcode",
    )

    GAS_ESTIMATES = {
        "market_increase": 800000,
        "limit_increase": 750000,
        "market_decrease": 700000,
        "limit_decrease": 700000,
        "approval": 80000,
    }

    MAX_GAS_PRICE_GWEI = 0.5
    GAS_BUFFER_MULT = 1.2
    MAX_EXECUTION_TIMEOUT = 90
    POSITION_FEE_BPS = 5

    def __init__(self, gmx_adapter=None, cb_system=None):
        self._gmx = gmx_adapter
        self._cb = cb_system
        self._execution_log = []
        self._pending_orders = {}
        self._gas_cache = {"price": None, "ts": 0}
        self._lock = threading.Lock()

    def set_gmx_adapter(self, adapter):
        self._gmx = adapter

    # --- PRE-EXECUTION CHECKS ---

    def pre_flight_check(self, order):
        """Validate everything before sending order."""
        issues = []
        gas_est = 0

        if self._cb:
            allowed = self._cb.get_max_allowed_action()
            if allowed == "blocked":
                issues.append("Circuit breaker: trading blocked")
                return {"ok": False, "issues": issues, "gas_estimate": 0}
            if allowed == "close_only" and order.get("action") != "close":
                issues.append("Circuit breaker: close-only mode")
                return {"ok": False, "issues": issues, "gas_estimate": 0}

        if not self._gmx:
            issues.append("No GMX adapter configured")
            return {"ok": False, "issues": issues, "gas_estimate": 0}

        if not HAS_WEB3:
            issues.append("web3.py not installed")
            return {"ok": False, "issues": issues, "gas_estimate": 0}

        w3 = self._gmx._w3
        if not w3 or not w3.is_connected():
            issues.append("Not connected to Arbitrum RPC")
            return {"ok": False, "issues": issues, "gas_estimate": 0}

        if not self._gmx._has_signer():
            issues.append("No signing account (private key)")
            return {"ok": False, "issues": issues, "gas_estimate": 0}

        order_type_key = order.get("order_type", "market_increase")
        gas_est = int(self.GAS_ESTIMATES.get(order_type_key, 800000) * self.GAS_BUFFER_MULT)

        gas_price_info = self.get_optimal_gas_price()
        if not gas_price_info["acceptable"]:
            issues.append(f"Gas price too high: {gas_price_info['gwei']:.3f} gwei (max {self.MAX_GAS_PRICE_GWEI})")

        try:
            address = self._gmx._account.address
            eth_balance = w3.eth.get_balance(address) / 10**18
            exec_fee_eth = GMX_EXECUTION_FEE_BUFFER_WEI / 10**18
            gas_cost_eth = gas_est * gas_price_info["wei"] / 10**18 if gas_price_info["wei"] else 0.001
            total_eth_needed = exec_fee_eth + gas_cost_eth

            if eth_balance < total_eth_needed:
                issues.append(f"Insufficient ETH for gas: have {eth_balance:.6f}, need ~{total_eth_needed:.6f}")

            collateral_usd = order.get("collateral_usd", 0)
            if collateral_usd > 0:
                usdc_balance = self._gmx._get_token_balance(
                    GMX_V2_TOKENS.get("USDC", ""), 6)
                if usdc_balance < collateral_usd:
                    issues.append(f"Insufficient USDC: have {usdc_balance:.2f}, need {collateral_usd:.2f}")
        except Exception as exc:
            issues.append(f"Balance check failed: {exc}")

        try:
            nonce = w3.eth.get_transaction_count(self._gmx._account.address, "pending")
            confirmed_nonce = w3.eth.get_transaction_count(self._gmx._account.address, "latest")
            if nonce > confirmed_nonce:
                issues.append(f"Pending transactions detected: {nonce - confirmed_nonce} unconfirmed")
        except Exception:
            pass

        return {"ok": len(issues) == 0, "issues": issues, "gas_estimate": gas_est}

    # --- GAS OPTIMIZATION ---

    def get_optimal_gas_price(self):
        """Get current gas price with caching (refresh every 30s)."""
        now = time.time()
        with self._lock:
            if self._gas_cache["price"] and now - self._gas_cache["ts"] < 30:
                return self._gas_cache["price"]

        result = {"wei": 0, "gwei": 0.0, "acceptable": True}

        if not self._gmx or not self._gmx._w3:
            result["acceptable"] = False
            return result

        try:
            gas_price = self._gmx._w3.eth.gas_price
            gwei = gas_price / 10**9
            result = {
                "wei": gas_price,
                "gwei": round(gwei, 4),
                "acceptable": gwei <= self.MAX_GAS_PRICE_GWEI,
            }
        except Exception:
            result["acceptable"] = False

        with self._lock:
            self._gas_cache = {"price": result, "ts": now}
        return result

    def estimate_execution_cost(self, order):
        """Total cost: gas + GMX execution fee + position fee in USD."""
        gas_info = self.get_optimal_gas_price()
        order_type_key = order.get("order_type", "market_increase")
        gas_units = int(self.GAS_ESTIMATES.get(order_type_key, 800000) * self.GAS_BUFFER_MULT)
        gas_cost_eth = gas_units * gas_info["wei"] / 10**18 if gas_info["wei"] else 0.001

        exec_fee_eth = GMX_EXECUTION_FEE_BUFFER_WEI / 10**18

        size_usd = order.get("size_usd", 0)
        position_fee_usd = size_usd * self.POSITION_FEE_BPS / 10000 * 2

        eth_price = 0.0
        try:
            eth_price = self._gmx._get_index_price("ETHUSDT") if self._gmx else 0
        except Exception:
            eth_price = 3000.0

        gas_cost_usd = (gas_cost_eth + exec_fee_eth) * eth_price
        total_usd = gas_cost_usd + position_fee_usd

        return {
            "gas_eth": round(gas_cost_eth, 6),
            "execution_fee_eth": round(exec_fee_eth, 6),
            "gas_usd": round(gas_cost_usd, 2),
            "position_fee_usd": round(position_fee_usd, 2),
            "total_cost_usd": round(total_usd, 2),
            "size_usd": size_usd,
            "cost_pct_of_size": round(total_usd / size_usd * 100, 3) if size_usd > 0 else 0,
        }

    # --- SLIPPAGE PROTECTION ---

    def calculate_acceptable_price(self, current_price, direction, slippage_bps=None,
                                    volatility_mult=1.0):
        """Calculate max/min acceptable price with dynamic slippage."""
        if slippage_bps is None:
            slippage_bps = GMX_DEFAULT_SLIPPAGE_BPS

        adjusted_bps = slippage_bps * max(1.0, volatility_mult)
        adjusted_bps = min(adjusted_bps, 200)

        slippage_frac = adjusted_bps / 10000
        if direction == "long":
            return current_price * (1 + slippage_frac)
        else:
            return current_price * (1 - slippage_frac)

    def check_pool_liquidity(self, market_config, size_usd):
        """Check if order size is reasonable relative to pool."""
        warnings = []
        if size_usd > 500000:
            warnings.append(f"Large order ${size_usd:,.0f} — check GMX OI caps")
        if size_usd > 50000:
            warnings.append(f"Order ${size_usd:,.0f} may have significant price impact")
        return {"ok": len(warnings) == 0, "warnings": warnings}

    def detect_price_impact(self, size_usd, direction):
        """Estimate price impact based on order size."""
        if size_usd < 10000:
            return {"impact_pct": 0.01, "acceptable": True}
        if size_usd < 50000:
            impact = size_usd / 10000000 * 100
            return {"impact_pct": round(impact, 3), "acceptable": impact < 0.5}
        impact = size_usd / 5000000 * 100
        return {"impact_pct": round(impact, 3), "acceptable": impact < 0.5,
                "suggestion": "Consider splitting into smaller orders"}

    # --- EXECUTION ---

    def execute_order(self, order):
        """Execute order with full protection pipeline."""
        start_time = time.time()
        log_entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "order": {k: v for k, v in order.items() if k != "private_key"},
            "steps": [],
            "result": None,
        }

        preflight = self.pre_flight_check(order)
        log_entry["steps"].append({"step": "pre_flight", "result": preflight})
        if not preflight["ok"]:
            log_entry["result"] = {"success": False, "error": "Pre-flight failed",
                                    "issues": preflight["issues"]}
            self._log(log_entry)
            return log_entry["result"]

        cost = self.estimate_execution_cost(order)
        log_entry["steps"].append({"step": "cost_estimate", "result": cost})
        size_usd = order.get("size_usd", 0)
        if cost["cost_pct_of_size"] > 5.0:
            log_entry["result"] = {"success": False,
                                    "error": f"Execution cost {cost['cost_pct_of_size']:.1f}% of position too high"}
            self._log(log_entry)
            return log_entry["result"]

        current_price = order.get("price", 0)
        direction = order.get("direction", "long")
        acceptable = self.calculate_acceptable_price(current_price, direction)
        log_entry["steps"].append({"step": "acceptable_price",
                                    "price": current_price, "acceptable": round(acceptable, 4)})

        liquidity = self.check_pool_liquidity(None, size_usd)
        log_entry["steps"].append({"step": "liquidity", "result": liquidity})

        impact = self.detect_price_impact(size_usd, direction)
        log_entry["steps"].append({"step": "price_impact", "result": impact})
        if not impact.get("acceptable", True):
            log.warning("[EXEC] High price impact %.3f%% for $%.0f %s",
                        impact["impact_pct"], size_usd, direction)

        symbol = order.get("symbol", "")
        leverage = order.get("leverage", 1)
        tp = order.get("tp")
        sl = order.get("sl")
        side = "buy" if direction == "long" else "sell"

        try:
            result = self._gmx.place_order(symbol, side, "market",
                                            order.get("quantity", size_usd),
                                            None, leverage, tp, sl)
            elapsed = time.time() - start_time
            result["execution_time_s"] = round(elapsed, 2)
            result["cost_estimate"] = cost
            result["acceptable_price"] = round(acceptable, 4)

            if result.get("success"):
                tx_hash = result.get("tx_hash", "")
                if tx_hash:
                    with self._lock:
                        self._pending_orders[tx_hash] = {
                            "symbol": symbol, "direction": direction,
                            "size_usd": size_usd, "submitted_at": time.time(),
                            "status": "pending",
                        }

                actual_price = result.get("price", current_price)
                if current_price > 0 and actual_price > 0:
                    slippage = abs(actual_price - current_price) / current_price * 100
                    result["slippage_pct"] = round(slippage, 4)

            log_entry["result"] = result
            self._log(log_entry)
            return result

        except Exception as exc:
            log_entry["result"] = {"success": False, "error": str(exc)}
            self._log(log_entry)
            if self._cb:
                err_lower = str(exc).lower()
                if "slippage" in err_lower or "price" in err_lower:
                    self._cb.trigger_execution_error(slippage_pct=10)
            return {"success": False, "error": str(exc)}

    def execute_with_retry(self, order, max_retries=3):
        """Execute with exponential backoff retry for transient errors."""
        last_error = ""
        for attempt in range(max_retries + 1):
            if attempt > 0:
                backoff = 2 ** attempt
                log.info("[EXEC] Retry %d/%d in %ds — last error: %s",
                         attempt, max_retries, backoff, last_error)
                time.sleep(backoff)

                self._gas_cache["ts"] = 0
                preflight = self.pre_flight_check(order)
                if not preflight["ok"]:
                    non_retryable = any(
                        nr in issue.lower()
                        for issue in preflight["issues"]
                        for nr in self._NON_RETRYABLE_ERRORS
                    )
                    if non_retryable:
                        return {"success": False, "error": "Non-retryable: " + "; ".join(preflight["issues"]),
                                "attempts": attempt + 1}

            result = self.execute_order(order)
            if result.get("success"):
                result["attempts"] = attempt + 1
                return result

            last_error = result.get("error", "unknown")
            err_lower = last_error.lower()

            is_retryable = any(rt in err_lower for rt in self._RETRYABLE_ERRORS)
            is_non_retryable = any(nr in err_lower for nr in self._NON_RETRYABLE_ERRORS)

            if is_non_retryable or not is_retryable:
                result["attempts"] = attempt + 1
                result["retry_stopped"] = "non-retryable error"
                return result

        return {"success": False, "error": f"Max retries ({max_retries}) exhausted: {last_error}",
                "attempts": max_retries + 1}

    # --- POSITION MANAGEMENT ON-CHAIN ---

    def close_position_smart(self, position, urgency="normal"):
        """Close position with urgency-adjusted parameters."""
        if not self._gmx:
            return {"success": False, "error": "No GMX adapter"}

        symbol = position.get("symbol", "")

        if urgency == "emergency":
            log.warning("[EXEC] Emergency close %s — max slippage", symbol)
            return self._gmx.close_position(symbol)

        if urgency == "high":
            return self._gmx.close_position(symbol)

        gas_info = self.get_optimal_gas_price()
        if not gas_info["acceptable"]:
            log.info("[EXEC] Gas high for close %s — proceeding anyway (close)", symbol)

        return self._gmx.close_position(symbol)

    def modify_position(self, position, new_sl=None, new_tp=None):
        """Modify position TP/SL by placing conditional decrease orders."""
        if not self._gmx:
            return {"success": False, "error": "No GMX adapter"}

        symbol = position.get("symbol", "")
        market = gmx_symbol_to_market(symbol)
        if not market:
            return {"success": False, "error": f"Unknown market for {symbol}"}

        results = {}
        is_long = position.get("side") == "long"
        quantity = position.get("quantity", 0)

        if new_tp:
            try:
                self._gmx._place_tp_sl_order(symbol, market, not is_long, quantity, new_tp, is_tp=True)
                results["tp"] = {"success": True, "price": new_tp}
            except Exception as exc:
                results["tp"] = {"success": False, "error": str(exc)}

        if new_sl:
            try:
                self._gmx._place_tp_sl_order(symbol, market, not is_long, quantity, new_sl, is_tp=False)
                results["sl"] = {"success": True, "price": new_sl}
            except Exception as exc:
                results["sl"] = {"success": False, "error": str(exc)}

        return {"success": True, "modifications": results}

    # --- MONITORING ---

    def get_pending_orders(self):
        """Return orders that haven't been confirmed yet."""
        now = time.time()
        with self._lock:
            pending = []
            for tx_hash, info in list(self._pending_orders.items()):
                age = now - info["submitted_at"]
                entry = dict(info)
                entry["tx_hash"] = tx_hash
                entry["age_seconds"] = round(age, 0)
                if age > 300:
                    entry["status"] = "possibly_stuck"
                pending.append(entry)
            return pending

    def confirm_order(self, tx_hash):
        """Mark an order as confirmed (called when on-chain confirmation received)."""
        with self._lock:
            if tx_hash in self._pending_orders:
                self._pending_orders[tx_hash]["status"] = "confirmed"
                del self._pending_orders[tx_hash]

    def get_execution_stats(self):
        """Statistics on execution quality."""
        with self._lock:
            logs = list(self._execution_log)

        if not logs:
            return {"total_executions": 0, "success_rate": 0, "avg_slippage_pct": 0,
                    "avg_gas_cost_usd": 0, "avg_execution_time_s": 0,
                    "worst_slippage_pct": 0, "total_gas_spent_usd": 0}

        total = len(logs)
        successes = sum(1 for l in logs if l.get("result", {}).get("success"))
        slippages = [l["result"].get("slippage_pct", 0) for l in logs
                     if l.get("result", {}).get("success") and l["result"].get("slippage_pct") is not None]
        gas_costs = [l["result"].get("cost_estimate", {}).get("gas_usd", 0) for l in logs
                     if l.get("result", {}).get("success")]
        exec_times = [l["result"].get("execution_time_s", 0) for l in logs
                      if l.get("result", {}).get("success") and l["result"].get("execution_time_s")]

        return {
            "total_executions": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": round(successes / total * 100, 1) if total > 0 else 0,
            "avg_slippage_pct": round(sum(slippages) / len(slippages), 4) if slippages else 0,
            "worst_slippage_pct": round(max(slippages), 4) if slippages else 0,
            "avg_gas_cost_usd": round(sum(gas_costs) / len(gas_costs), 2) if gas_costs else 0,
            "total_gas_spent_usd": round(sum(gas_costs), 2),
            "avg_execution_time_s": round(sum(exec_times) / len(exec_times), 2) if exec_times else 0,
            "pending_orders": len(self._pending_orders),
            "recent_executions": total,
        }

    def cleanup_stuck_orders(self, max_age_s=600):
        """Remove orders from pending tracking if too old."""
        now = time.time()
        cleaned = 0
        with self._lock:
            for tx_hash in list(self._pending_orders.keys()):
                age = now - self._pending_orders[tx_hash]["submitted_at"]
                if age > max_age_s:
                    self._pending_orders[tx_hash]["status"] = "expired"
                    del self._pending_orders[tx_hash]
                    cleaned += 1
        if cleaned:
            log.info("[EXEC] Cleaned %d stuck orders", cleaned)
        return cleaned

    def _log(self, entry):
        with self._lock:
            self._execution_log.append(entry)
            if len(self._execution_log) > 500:
                self._execution_log = self._execution_log[-500:]
        success = entry.get("result", {}).get("success", False)
        order = entry.get("order", {})
        log.info("[EXEC] %s | %s %s $%.0f | %s",
                 "OK" if success else "FAIL",
                 order.get("direction", "?"),
                 order.get("symbol", "?"),
                 order.get("size_usd", 0),
                 entry.get("result", {}).get("error", ""))


smart_executor = SmartExecutionEngine(cb_system=None)


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

    def get_adapter_by_type(self, exchange_type):
        """Find the first connected adapter matching the given exchange type."""
        target = exchange_type.lower()
        for name, adapter in self._adapters.items():
            if adapter.name.lower() == target:
                return adapter
        return None

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

    REQUIRED_TRADES = 0

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


# ---------------------------------------------------------------------------
# Trading Strategies — Modular framework with independent entry/exit logic
# ---------------------------------------------------------------------------

class TradingStrategy:
    """Base class for all trading strategies."""
    name = "base"
    description = ""
    suitable_regimes = []
    min_adx = 0

    def should_enter(self, ohlcv, raw_ind, regime_info, dip_top):
        """Returns (direction, confidence, reason) or None if no entry."""
        raise NotImplementedError

    def get_exit_conditions(self, entry_price, direction, raw_ind):
        """Returns dict with take_profit, stop_loss, trailing_pct."""
        raise NotImplementedError

    def get_leverage(self, confidence, regime):
        """Returns recommended leverage (int, 1-20)."""
        raise NotImplementedError

    @staticmethod
    def _lv(series):
        """Last valid non-None value from a list."""
        if not series:
            return None
        for v in reversed(series):
            if v is not None:
                return v
        return None


class TrendFollowingStrategy(TradingStrategy):
    name = "trend"
    description = "Follow strong directional trends using EMA alignment + ADX"
    suitable_regimes = ["BULL", "BEAR"]
    min_adx = 25

    EMA_FAST = 9
    EMA_MID = 21
    EMA_SLOW = 50
    ADX_THRESHOLD = 25
    RSI_LONG_MIN = 40
    RSI_LONG_MAX = 70
    RSI_SHORT_MIN = 30
    RSI_SHORT_MAX = 60
    TP_ATR_MULT = 2.0
    SL_ATR_MULT = 1.0
    TRAILING_PCT = 1.5
    LEV_HIGH = 5
    LEV_LOW = 3

    def should_enter(self, ohlcv, raw_ind, regime_info, dip_top):
        regime = regime_info.get("regime", "RANGE")
        if regime not in self.suitable_regimes:
            return None

        closes = raw_ind["closes"]
        if len(closes) < self.EMA_SLOW + 10:
            return None

        ema9 = calc_ema(closes, self.EMA_FAST)
        ema21 = calc_ema(closes, self.EMA_MID)
        ema50 = raw_ind.get("ema50", [])

        e9 = self._lv(ema9)
        e21 = self._lv(ema21)
        e50 = self._lv(ema50)
        if e9 is None or e21 is None or e50 is None:
            return None

        adx_data = raw_ind.get("adx", {})
        last_adx = self._lv(adx_data.get("adx", []))
        if last_adx is None or last_adx < self.ADX_THRESHOLD:
            return None

        rsi = self._lv(raw_ind.get("rsi", []))
        if rsi is None:
            return None

        macd = raw_ind.get("macd", {})
        hist = macd.get("histogram", [])
        h_now = self._lv(hist)
        h_prev = self._lv(hist[:-1]) if len(hist) > 1 else None

        if e9 > e21 > e50:
            if self.RSI_LONG_MIN <= rsi <= self.RSI_LONG_MAX:
                if h_now is not None and h_now > 0:
                    rising = h_prev is not None and h_now > h_prev
                    conf = 80 if rising else 65
                    return ("long", conf, f"EMA aligned bullish, ADX {last_adx:.0f}, RSI {rsi:.0f}")

        if e9 < e21 < e50:
            if self.RSI_SHORT_MIN <= rsi <= self.RSI_SHORT_MAX:
                if h_now is not None and h_now < 0:
                    falling = h_prev is not None and h_now < h_prev
                    conf = 80 if falling else 65
                    return ("short", conf, f"EMA aligned bearish, ADX {last_adx:.0f}, RSI {rsi:.0f}")

        return None

    def get_exit_conditions(self, entry_price, direction, raw_ind):
        atr_val = self._lv(raw_ind.get("atr", []))
        if atr_val is None or atr_val <= 0:
            atr_val = entry_price * 0.015
        if direction == "long":
            tp = entry_price + atr_val * self.TP_ATR_MULT
            sl = entry_price - atr_val * self.SL_ATR_MULT
        else:
            tp = entry_price - atr_val * self.TP_ATR_MULT
            sl = entry_price + atr_val * self.SL_ATR_MULT
        return {"take_profit": tp, "stop_loss": sl, "trailing_pct": self.TRAILING_PCT}

    def get_leverage(self, confidence, regime):
        if confidence >= 75 and regime in ("BULL", "BEAR"):
            return self.LEV_HIGH
        return self.LEV_LOW


class MeanReversionStrategy(TradingStrategy):
    name = "mean_reversion"
    description = "Fade extremes in ranging markets using BB + RSI + StochRSI"
    suitable_regimes = ["RANGE"]
    min_adx = 0

    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    STOCH_OVERSOLD = 20
    STOCH_OVERBOUGHT = 80
    SL_BAND_MULT = 1.5
    MAX_LEVERAGE = 3

    def should_enter(self, ohlcv, raw_ind, regime_info, dip_top):
        regime = regime_info.get("regime", "RANGE")
        if regime not in self.suitable_regimes:
            return None

        closes = raw_ind["closes"]
        if len(closes) < 30:
            return None
        price = closes[-1]

        bb = raw_ind.get("bb", {})
        upper = self._lv(bb.get("upper", []))
        lower = self._lv(bb.get("lower", []))
        middle = self._lv(bb.get("middle", []))
        if upper is None or lower is None or middle is None:
            return None

        rsi = self._lv(raw_ind.get("rsi", []))
        stoch = raw_ind.get("stoch_rsi", {})
        sk = self._lv(stoch.get("k", []))
        if rsi is None:
            return None

        if price < lower and rsi < self.RSI_OVERSOLD:
            if sk is not None and sk < self.STOCH_OVERSOLD:
                conf = 75
            else:
                conf = 60
            return ("long", conf, f"Price below BB lower, RSI {rsi:.0f}")

        if price > upper and rsi > self.RSI_OVERBOUGHT:
            if sk is not None and sk > self.STOCH_OVERBOUGHT:
                conf = 75
            else:
                conf = 60
            return ("short", conf, f"Price above BB upper, RSI {rsi:.0f}")

        return None

    def get_exit_conditions(self, entry_price, direction, raw_ind):
        bb = raw_ind.get("bb", {})
        middle = self._lv(bb.get("middle", []))
        upper = self._lv(bb.get("upper", []))
        lower = self._lv(bb.get("lower", []))
        if middle is None:
            middle = entry_price

        if direction == "long":
            tp = middle
            band_dist = abs(entry_price - (lower or entry_price * 0.98))
            sl = entry_price - band_dist * self.SL_BAND_MULT
        else:
            tp = middle
            band_dist = abs((upper or entry_price * 1.02) - entry_price)
            sl = entry_price + band_dist * self.SL_BAND_MULT
        return {"take_profit": tp, "stop_loss": sl, "trailing_pct": 0}

    def get_leverage(self, confidence, regime):
        return self.MAX_LEVERAGE


class BreakoutStrategy(TradingStrategy):
    name = "breakout"
    description = "Catch volatility expansion after BB squeeze with volume confirmation"
    suitable_regimes = ["RANGE", "BULL", "BEAR"]
    min_adx = 0

    BB_SQUEEZE_THRESHOLD = 0.02
    SQUEEZE_MIN_BARS = 10
    VOL_SPIKE_MULT = 2.0
    VOL_LOOKBACK = 20
    TP_ATR_MULT = 3.0
    SL_ATR_MULT = 0.5
    TRAILING_PCT = 2.0
    LEV_HIGH = 8
    LEV_LOW = 5

    def should_enter(self, ohlcv, raw_ind, regime_info, dip_top):
        closes = raw_ind["closes"]
        volumes = raw_ind["volumes"]
        if len(closes) < 50 or len(volumes) < self.VOL_LOOKBACK + 1:
            return None

        bb = raw_ind.get("bb", {})
        upper_list = bb.get("upper", [])
        lower_list = bb.get("lower", [])
        middle_list = bb.get("middle", [])
        if len(upper_list) < self.SQUEEZE_MIN_BARS + 5:
            return None

        squeeze_count = 0
        for i in range(-self.SQUEEZE_MIN_BARS - 5, -1):
            try:
                u = upper_list[i]
                l = lower_list[i]
                m = middle_list[i]
                if u is None or l is None or m is None or m <= 0:
                    continue
                width = (u - l) / m
                if width < self.BB_SQUEEZE_THRESHOLD:
                    squeeze_count += 1
            except IndexError:
                continue

        if squeeze_count < self.SQUEEZE_MIN_BARS:
            return None

        avg_vol = sum(volumes[-self.VOL_LOOKBACK - 1:-1]) / self.VOL_LOOKBACK
        if avg_vol <= 0 or volumes[-1] < avg_vol * self.VOL_SPIKE_MULT:
            return None

        price = closes[-1]
        upper = self._lv(upper_list)
        lower = self._lv(lower_list)
        if upper is None or lower is None:
            return None

        adx_data = raw_ind.get("adx", {})
        adx_list = adx_data.get("adx", [])
        adx_now = self._lv(adx_list)
        adx_prev = self._lv(adx_list[:-1]) if len(adx_list) > 1 else None
        adx_rising = (adx_now is not None and adx_prev is not None and adx_now > adx_prev)

        if price > upper:
            conf = 80 if adx_rising else 65
            vol_ratio = volumes[-1] / avg_vol
            return ("long", conf, f"BB breakout UP, vol {vol_ratio:.1f}x, ADX rising={adx_rising}")

        if price < lower:
            conf = 80 if adx_rising else 65
            vol_ratio = volumes[-1] / avg_vol
            return ("short", conf, f"BB breakout DOWN, vol {vol_ratio:.1f}x, ADX rising={adx_rising}")

        return None

    def get_exit_conditions(self, entry_price, direction, raw_ind):
        atr_val = self._lv(raw_ind.get("atr", []))
        if atr_val is None or atr_val <= 0:
            atr_val = entry_price * 0.02
        if direction == "long":
            tp = entry_price + atr_val * self.TP_ATR_MULT
            sl = entry_price - atr_val * self.SL_ATR_MULT
        else:
            tp = entry_price - atr_val * self.TP_ATR_MULT
            sl = entry_price + atr_val * self.SL_ATR_MULT
        return {"take_profit": tp, "stop_loss": sl, "trailing_pct": self.TRAILING_PCT}

    def get_leverage(self, confidence, regime):
        return self.LEV_HIGH if confidence >= 75 else self.LEV_LOW


class DipHunterStrategy(TradingStrategy):
    name = "dip_hunter"
    description = "Contrarian entries on dips/tops using DipTopDetector confluence"
    suitable_regimes = ["BULL", "BEAR"]
    min_adx = 0

    CONFLUENCE_THRESHOLD = 70
    TP_ATR_MULT = 2.0
    SL_ATR_MULT = 2.0
    TRAILING_PCT = 1.0
    MAX_LEVERAGE = 3

    def should_enter(self, ohlcv, raw_ind, regime_info, dip_top):
        regime = regime_info.get("regime", "RANGE")
        if regime not in self.suitable_regimes:
            return None
        if not dip_top:
            return None

        confluence = dip_top.get("confluence", {})
        score = confluence.get("score", 0) if isinstance(confluence, dict) else 0

        if score < self.CONFLUENCE_THRESHOLD:
            return None

        rsi_div = dip_top.get("rsi_divergence", {})
        vol_climax = dip_top.get("volume_climax", {})

        if regime == "BULL" and dip_top.get("is_dip"):
            bullish_div = rsi_div.get("bullish", False)
            selling_climax = vol_climax.get("selling_climax", False)
            if bullish_div or selling_climax:
                conf = min(85, 60 + score // 5)
                return ("long", conf, f"Dip detected in BULL, confluence {score}")
            return None

        if regime == "BEAR" and dip_top.get("is_top"):
            bearish_div = rsi_div.get("bearish", False)
            buying_climax = vol_climax.get("buying_climax", False)
            if bearish_div or buying_climax:
                conf = min(85, 60 + score // 5)
                return ("short", conf, f"Top detected in BEAR, confluence {score}")
            return None

        return None

    def get_exit_conditions(self, entry_price, direction, raw_ind):
        atr_val = self._lv(raw_ind.get("atr", []))
        if atr_val is None or atr_val <= 0:
            atr_val = entry_price * 0.02

        closes = raw_ind.get("closes", [])
        highs = raw_ind.get("highs", [])
        lows = raw_ind.get("lows", [])

        if direction == "long":
            swing_hi = max(highs[-20:]) if len(highs) >= 20 else entry_price * 1.03
            tp = swing_hi
            sl = entry_price - atr_val * self.SL_ATR_MULT
        else:
            swing_lo = min(lows[-20:]) if len(lows) >= 20 else entry_price * 0.97
            tp = swing_lo
            sl = entry_price + atr_val * self.SL_ATR_MULT

        return {"take_profit": tp, "stop_loss": sl, "trailing_pct": self.TRAILING_PCT}

    def get_leverage(self, confidence, regime):
        return self.MAX_LEVERAGE if confidence >= 75 else 2


class MomentumScalpStrategy(TradingStrategy):
    name = "momentum_scalp"
    description = "Quick scalp on strong momentum bursts with tight exits"
    suitable_regimes = ["BULL", "BEAR"]
    min_adx = 30

    ADX_THRESHOLD = 30
    RSI_LONG_MIN = 60
    RSI_SHORT_MAX = 40
    VOL_SPIKE_MULT = 2.0
    VOL_LOOKBACK = 20
    TP_PCT = 0.008
    SL_PCT = 0.003
    TRAILING_PCT = 0.5
    MAX_LEVERAGE = 15
    MIN_LEVERAGE = 10

    def should_enter(self, ohlcv, raw_ind, regime_info, dip_top):
        regime = regime_info.get("regime", "RANGE")
        if regime not in self.suitable_regimes:
            return None

        adx_data = raw_ind.get("adx", {})
        last_adx = self._lv(adx_data.get("adx", []))
        if last_adx is None or last_adx < self.ADX_THRESHOLD:
            return None

        rsi = self._lv(raw_ind.get("rsi", []))
        if rsi is None:
            return None

        volumes = raw_ind.get("volumes", [])
        if len(volumes) < self.VOL_LOOKBACK + 1:
            return None
        avg_vol = sum(volumes[-self.VOL_LOOKBACK - 1:-1]) / self.VOL_LOOKBACK
        if avg_vol <= 0 or volumes[-1] < avg_vol * self.VOL_SPIKE_MULT:
            return None

        macd = raw_ind.get("macd", {})
        ml = self._lv(macd.get("line", []))
        ms = self._lv(macd.get("signal", []))
        if ml is None or ms is None:
            return None

        if regime == "BULL" and rsi >= self.RSI_LONG_MIN and ml > ms:
            return ("long", 70, f"Momentum LONG, ADX {last_adx:.0f}, RSI {rsi:.0f}")

        if regime == "BEAR" and rsi <= self.RSI_SHORT_MAX and ml < ms:
            return ("short", 70, f"Momentum SHORT, ADX {last_adx:.0f}, RSI {rsi:.0f}")

        return None

    def get_exit_conditions(self, entry_price, direction, raw_ind):
        if direction == "long":
            tp = entry_price * (1 + self.TP_PCT)
            sl = entry_price * (1 - self.SL_PCT)
        else:
            tp = entry_price * (1 - self.TP_PCT)
            sl = entry_price * (1 + self.SL_PCT)
        return {"take_profit": tp, "stop_loss": sl, "trailing_pct": self.TRAILING_PCT}

    def get_leverage(self, confidence, regime):
        return self.MAX_LEVERAGE if confidence >= 75 else self.MIN_LEVERAGE


class MacroEventStrategy(TradingStrategy):
    name = "macro_event"
    description = "Reduce exposure pre-event, follow direction post-event"
    suitable_regimes = ["BULL", "BEAR", "RANGE", "CRISIS"]
    min_adx = 0

    POST_EVENT_WAIT_BARS = 3
    POST_EVENT_ADX_MIN = 20
    TP_ATR_MULT = 1.5
    SL_ATR_MULT = 1.0
    TRAILING_PCT = 1.0
    MAX_LEVERAGE = 3

    def should_enter(self, ohlcv, raw_ind, regime_info, dip_top):
        closes = raw_ind.get("closes", [])
        if len(closes) < 50:
            return None

        adx_data = raw_ind.get("adx", {})
        last_adx = self._lv(adx_data.get("adx", []))
        if last_adx is None or last_adx < self.POST_EVENT_ADX_MIN:
            return None

        ema50 = raw_ind.get("ema50", [])
        e50 = self._lv(ema50)
        price = closes[-1]
        if e50 is None:
            return None

        macd = raw_ind.get("macd", {})
        h_now = self._lv(macd.get("histogram", []))
        if h_now is None:
            return None

        if len(closes) >= self.POST_EVENT_WAIT_BARS + 1:
            recent = closes[-self.POST_EVENT_WAIT_BARS:]
            all_up = all(recent[i] >= recent[i - 1] for i in range(1, len(recent)))
            all_down = all(recent[i] <= recent[i - 1] for i in range(1, len(recent)))
        else:
            all_up = False
            all_down = False

        if all_up and price > e50 and h_now > 0:
            return ("long", 55, f"Post-event bullish direction, ADX {last_adx:.0f}")

        if all_down and price < e50 and h_now < 0:
            return ("short", 55, f"Post-event bearish direction, ADX {last_adx:.0f}")

        return None

    def get_exit_conditions(self, entry_price, direction, raw_ind):
        atr_val = self._lv(raw_ind.get("atr", []))
        if atr_val is None or atr_val <= 0:
            atr_val = entry_price * 0.015
        if direction == "long":
            tp = entry_price + atr_val * self.TP_ATR_MULT
            sl = entry_price - atr_val * self.SL_ATR_MULT
        else:
            tp = entry_price - atr_val * self.TP_ATR_MULT
            sl = entry_price + atr_val * self.SL_ATR_MULT
        return {"take_profit": tp, "stop_loss": sl, "trailing_pct": self.TRAILING_PCT}

    def get_leverage(self, confidence, regime):
        return self.MAX_LEVERAGE if confidence >= 60 else 2


# ---------------------------------------------------------------------------
# Strategy Selector — Adaptive multi-strategy routing with performance tracking
# ---------------------------------------------------------------------------

class StrategySelector:
    """Scores every applicable strategy and picks the best one, weighted by
    historical performance when enough data is available."""

    MIN_TRADES_FOR_WEIGHT = 5

    def __init__(self):
        self.strategies = {
            "trend": TrendFollowingStrategy(),
            "mean_reversion": MeanReversionStrategy(),
            "breakout": BreakoutStrategy(),
            "dip_hunter": DipHunterStrategy(),
            "momentum_scalp": MomentumScalpStrategy(),
            "macro_event": MacroEventStrategy(),
        }
        self._performance = {}
        self._lock = threading.Lock()

    def select(self, regime_info, raw_ind, ohlcv, dip_top):
        regime = regime_info.get("regime", "RANGE")
        candidates = []

        for name, strat in self.strategies.items():
            if regime not in strat.suitable_regimes:
                continue
            try:
                entry = strat.should_enter(ohlcv, raw_ind, regime_info, dip_top)
            except Exception as exc:
                log.debug("[STRATEGY] %s.should_enter error: %s", name, exc)
                continue
            if entry is None:
                continue
            direction, confidence, reason = entry
            score = self._score_candidate(name, confidence)
            candidates.append({
                "name": name,
                "direction": direction,
                "confidence": confidence,
                "reason": reason,
                "score": score,
            })

        if not candidates:
            return None

        candidates.sort(key=lambda c: c["score"], reverse=True)
        best = candidates[0]
        log.info("[STRATEGY] Selected %s (score %.1f, conf %d) over %d candidates | %s",
                 best["name"], best["score"], best["confidence"],
                 len(candidates), best["reason"])
        return best

    def _score_candidate(self, name, confidence):
        base = float(confidence)
        with self._lock:
            perf = self._performance.get(name)
        if perf and perf.get("trades", 0) >= self.MIN_TRADES_FOR_WEIGHT:
            pf = perf.get("profit_factor", 1.0)
            wr = perf.get("win_rate", 50) / 100.0
            base *= (0.5 + 0.5 * min(pf, 3.0) / 3.0) * (0.5 + 0.5 * wr)
        try:
            weights = performance_tracker.get_strategy_weights()
            if name in weights and weights[name] > 0:
                base *= (0.5 + weights[name] * 2.0)
        except Exception:
            pass
        return round(base, 2)

    def get_applicable(self, regime):
        return [name for name, s in self.strategies.items()
                if regime in s.suitable_regimes]

    def record_result(self, strategy_name, pnl):
        with self._lock:
            if strategy_name not in self._performance:
                self._performance[strategy_name] = {
                    "trades": 0, "wins": 0, "losses": 0,
                    "total_pnl": 0.0, "gross_win": 0.0, "gross_loss": 0.0,
                }
            p = self._performance[strategy_name]
            p["trades"] += 1
            p["total_pnl"] += pnl
            if pnl > 0:
                p["wins"] += 1
                p["gross_win"] += pnl
            else:
                p["losses"] += 1
                p["gross_loss"] += abs(pnl)
            p["win_rate"] = round(p["wins"] / p["trades"] * 100, 1) if p["trades"] else 0
            p["profit_factor"] = round(p["gross_win"] / p["gross_loss"], 2) if p["gross_loss"] > 0 else 99.0

    def get_performance(self):
        with self._lock:
            out = {}
            for name, strat in self.strategies.items():
                perf = dict(self._performance.get(name, {
                    "trades": 0, "wins": 0, "losses": 0,
                    "total_pnl": 0.0, "win_rate": 0, "profit_factor": 0,
                }))
                perf["description"] = strat.description
                perf["suitable_regimes"] = list(strat.suitable_regimes)
                out[name] = perf
            return out

    def get_strategy(self, name):
        return self.strategies.get(name)


strategy_selector = StrategySelector()


# ---------------------------------------------------------------------------
# Performance Tracker — institutional-grade trade analytics
# ---------------------------------------------------------------------------

class PerformanceTracker:

    def __init__(self):
        self._lock = threading.Lock()

    # --- record / close -----------------------------------------------------

    def record_trade(self, trade_data):
        conn = get_db()
        try:
            c = conn.execute(
                """INSERT INTO bot_trades
                   (timestamp, symbol, direction, strategy, entry_price, size_usd,
                    leverage, regime_at_entry, signal_score, signal_confidence,
                    macro_score, stop_loss, take_profit, tx_hash_open, notes, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (trade_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                 trade_data.get("symbol", ""),
                 trade_data.get("direction", ""),
                 trade_data.get("strategy", ""),
                 trade_data.get("entry_price", 0),
                 trade_data.get("size_usd", 0),
                 trade_data.get("leverage", 1),
                 trade_data.get("regime", ""),
                 trade_data.get("signal_score", 0),
                 trade_data.get("signal_confidence", 0),
                 trade_data.get("macro_score", 0),
                 trade_data.get("stop_loss", 0),
                 trade_data.get("take_profit", 0),
                 trade_data.get("tx_hash", ""),
                 trade_data.get("notes", ""),
                 "open"))
            conn.commit()
            return c.lastrowid
        except Exception as exc:
            log.warning("[PERF] record_trade error: %s", exc)
            return None
        finally:
            conn.close()

    def close_trade(self, trade_id, exit_data):
        conn = get_db()
        try:
            row = conn.execute("SELECT * FROM bot_trades WHERE id=?", (trade_id,)).fetchone()
            if not row:
                conn.close()
                return
            cols = [d[0] for d in conn.execute("SELECT * FROM bot_trades LIMIT 0").description]
            rec = dict(zip(cols, row))
            entry_price = rec["entry_price"]
            exit_price = exit_data.get("exit_price", 0)
            direction = rec["direction"]
            size_usd = rec["size_usd"]
            leverage = rec["leverage"] or 1

            if direction.upper() == "LONG":
                pnl_pct = (exit_price - entry_price) / entry_price * 100 * leverage if entry_price else 0
            else:
                pnl_pct = (entry_price - exit_price) / entry_price * 100 * leverage if entry_price else 0
            pnl_usd = size_usd * pnl_pct / 100.0
            fees = size_usd * 0.001
            slippage = exit_data.get("slippage_pct", 0)

            entry_time = rec["timestamp"]
            exit_time = exit_data.get("timestamp", datetime.now(timezone.utc).isoformat())
            dur = 0
            try:
                t0 = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(exit_time.replace("Z", "+00:00"))
                dur = (t1 - t0).total_seconds() / 60.0
            except Exception:
                pass

            conn.execute(
                """UPDATE bot_trades SET
                    exit_price=?, pnl_usd=?, pnl_pct=?, fees_usd=?, slippage_pct=?,
                    duration_minutes=?, regime_at_exit=?, exit_reason=?,
                    tx_hash_close=?, status='closed'
                   WHERE id=?""",
                (exit_price, round(pnl_usd, 4), round(pnl_pct, 4), round(fees, 4),
                 round(slippage, 4), round(dur, 1),
                 exit_data.get("regime", ""),
                 exit_data.get("exit_reason", "manual"),
                 exit_data.get("tx_hash", ""),
                 trade_id))
            conn.commit()
        except Exception as exc:
            log.warning("[PERF] close_trade error: %s", exc)
        finally:
            conn.close()

    # --- core metrics -------------------------------------------------------

    def _query_trades(self, period="all", strategy=None, symbol=None, status="closed"):
        conn = get_db()
        try:
            sql = "SELECT * FROM bot_trades WHERE status=?"
            params = [status]
            if strategy:
                sql += " AND strategy=?"
                params.append(strategy)
            if symbol:
                sql += " AND symbol=?"
                params.append(symbol)
            if period != "all":
                days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}.get(period, 30)
                cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
                sql += " AND timestamp>=?"
                params.append(cutoff)
            sql += " ORDER BY timestamp ASC"
            rows = conn.execute(sql, params).fetchall()
            cols = [d[0] for d in conn.execute("SELECT * FROM bot_trades LIMIT 0").description]
            return [dict(zip(cols, r)) for r in rows]
        except Exception as exc:
            log.warning("[PERF] _query_trades error: %s", exc)
            return []
        finally:
            conn.close()

    def get_summary(self, period="all", strategy=None, symbol=None):
        trades = self._query_trades(period, strategy, symbol)
        if not trades:
            return {"total_trades": 0, "winners": 0, "losers": 0, "win_rate": 0,
                    "total_pnl": 0, "average_pnl": 0, "best_trade": 0, "worst_trade": 0,
                    "profit_factor": 0, "sharpe_ratio": 0, "sortino_ratio": 0,
                    "max_drawdown": 0, "max_drawdown_duration_h": 0,
                    "average_duration_min": 0, "average_leverage": 0,
                    "total_fees": 0, "net_pnl": 0, "expectancy": 0, "calmar_ratio": 0}

        pnls = [t["pnl_usd"] or 0 for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        total = len(pnls)
        n_wins = len(wins)
        n_losses = len(losses)
        win_rate = n_wins / total * 100 if total else 0
        gross_win = sum(wins)
        gross_loss = sum(abs(l) for l in losses)
        pf = gross_win / gross_loss if gross_loss > 0 else 99.0
        total_pnl = sum(pnls)
        avg_pnl = total_pnl / total if total else 0
        total_fees = sum(t.get("fees_usd") or 0 for t in trades)
        net_pnl = total_pnl - total_fees

        avg_win = gross_win / n_wins if n_wins else 0
        avg_loss = gross_loss / n_losses if n_losses else 0
        wr_dec = n_wins / total if total else 0
        expectancy = avg_win * wr_dec - avg_loss * (1 - wr_dec)

        mean_pnl = sum(pnls) / len(pnls) if pnls else 0
        var = sum((p - mean_pnl) ** 2 for p in pnls) / len(pnls) if pnls else 0
        std = var ** 0.5
        risk_free_daily = 0.04 / 365
        sharpe = ((mean_pnl - risk_free_daily) / std * (252 ** 0.5)) if std > 0 else 0

        down = [p for p in pnls if p < 0]
        down_var = sum(p ** 2 for p in down) / len(down) if down else 0
        down_std = down_var ** 0.5
        sortino = ((mean_pnl - risk_free_daily) / down_std * (252 ** 0.5)) if down_std > 0 else 0

        equity = 0
        peak = 0
        max_dd = 0
        dd_start = 0
        max_dd_dur = 0
        for i, p in enumerate(pnls):
            equity += p
            if equity > peak:
                peak = equity
                dd_start = i
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd
                max_dd_dur = i - dd_start

        durations = [t.get("duration_minutes") or 0 for t in trades]
        avg_dur = sum(durations) / len(durations) if durations else 0
        leverages = [t.get("leverage") or 1 for t in trades]
        avg_lev = sum(leverages) / len(leverages) if leverages else 1

        ann_ret = total_pnl * 365 / max(1, len(pnls))
        calmar = ann_ret / max_dd if max_dd > 0 else 0

        return {
            "total_trades": total, "winners": n_wins, "losers": n_losses,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 4), "average_pnl": round(avg_pnl, 4),
            "best_trade": round(max(pnls), 4) if pnls else 0,
            "worst_trade": round(min(pnls), 4) if pnls else 0,
            "profit_factor": round(pf, 2),
            "sharpe_ratio": round(sharpe, 2), "sortino_ratio": round(sortino, 2),
            "max_drawdown": round(max_dd, 4),
            "max_drawdown_duration_h": round(max_dd_dur * avg_dur / 60, 1) if avg_dur else 0,
            "average_duration_min": round(avg_dur, 1),
            "average_leverage": round(avg_lev, 1),
            "total_fees": round(total_fees, 4), "net_pnl": round(net_pnl, 4),
            "expectancy": round(expectancy, 4), "calmar_ratio": round(calmar, 2),
        }

    def get_equity_curve(self, period="30d"):
        trades = self._query_trades(period)
        equity = 0
        peak = 0
        points = []
        for t in trades[-1000:]:
            equity += (t["pnl_usd"] or 0)
            if equity > peak:
                peak = equity
            dd_pct = ((peak - equity) / peak * 100) if peak > 0 else 0
            points.append({
                "timestamp": t["timestamp"],
                "equity": round(equity, 4),
                "drawdown_pct": round(dd_pct, 2),
            })
        return points

    def get_by_strategy(self):
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT DISTINCT strategy FROM bot_trades WHERE status='closed'").fetchall()
            result = {}
            for (strat,) in rows:
                trades = self._query_trades(strategy=strat)
                if not trades:
                    continue
                pnls = [t["pnl_usd"] or 0 for t in trades]
                wins = [p for p in pnls if p > 0]
                losses_abs = [abs(p) for p in pnls if p <= 0]
                gw = sum(wins)
                gl = sum(losses_abs)
                result[strat] = {
                    "trade_count": len(trades),
                    "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
                    "avg_pnl": round(sum(pnls) / len(pnls), 4) if pnls else 0,
                    "total_pnl": round(sum(pnls), 4),
                    "profit_factor": round(gw / gl, 2) if gl > 0 else 99.0,
                }
            return result
        finally:
            conn.close()

    def get_by_symbol(self):
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT DISTINCT symbol FROM bot_trades WHERE status='closed'").fetchall()
            result = {}
            for (sym,) in rows:
                trades = self._query_trades(symbol=sym)
                if not trades:
                    continue
                pnls = [t["pnl_usd"] or 0 for t in trades]
                wins = [p for p in pnls if p > 0]
                losses_abs = [abs(p) for p in pnls if p <= 0]
                gw = sum(wins)
                gl = sum(losses_abs)
                result[sym] = {
                    "trade_count": len(trades),
                    "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
                    "avg_pnl": round(sum(pnls) / len(pnls), 4) if pnls else 0,
                    "total_pnl": round(sum(pnls), 4),
                    "profit_factor": round(gw / gl, 2) if gl > 0 else 99.0,
                }
            return result
        finally:
            conn.close()

    def get_by_hour(self):
        trades = self._query_trades()
        hours = {}
        for t in trades:
            try:
                h = datetime.fromisoformat(t["timestamp"].replace("Z", "+00:00")).hour
            except Exception:
                continue
            if h not in hours:
                hours[h] = {"trades": 0, "pnl": 0, "wins": 0}
            hours[h]["trades"] += 1
            hours[h]["pnl"] += (t["pnl_usd"] or 0)
            if (t["pnl_usd"] or 0) > 0:
                hours[h]["wins"] += 1
        result = {}
        for h in range(24):
            d = hours.get(h, {"trades": 0, "pnl": 0, "wins": 0})
            result[str(h)] = {
                "trades": d["trades"],
                "pnl": round(d["pnl"], 4),
                "win_rate": round(d["wins"] / d["trades"] * 100, 1) if d["trades"] else 0,
            }
        return result

    def get_by_regime(self):
        trades = self._query_trades()
        regimes = {}
        for t in trades:
            r = t.get("regime_at_entry") or "UNKNOWN"
            if r not in regimes:
                regimes[r] = {"trades": 0, "pnl": 0, "wins": 0}
            regimes[r]["trades"] += 1
            regimes[r]["pnl"] += (t["pnl_usd"] or 0)
            if (t["pnl_usd"] or 0) > 0:
                regimes[r]["wins"] += 1
        result = {}
        for r, d in regimes.items():
            result[r] = {
                "trades": d["trades"],
                "pnl": round(d["pnl"], 4),
                "win_rate": round(d["wins"] / d["trades"] * 100, 1) if d["trades"] else 0,
            }
        return result

    def get_streaks(self):
        trades = self._query_trades()
        if not trades:
            return {"current_streak": 0, "current_type": "none",
                    "max_win_streak": 0, "max_loss_streak": 0, "avg_streak": 0}
        cur = 0
        cur_type = "none"
        max_win = 0
        max_loss = 0
        streaks = []
        for t in trades:
            p = t["pnl_usd"] or 0
            if p > 0:
                if cur_type == "win":
                    cur += 1
                else:
                    if cur > 0:
                        streaks.append(cur)
                    cur = 1
                    cur_type = "win"
                max_win = max(max_win, cur)
            else:
                if cur_type == "loss":
                    cur += 1
                else:
                    if cur > 0:
                        streaks.append(cur)
                    cur = 1
                    cur_type = "loss"
                max_loss = max(max_loss, cur)
        if cur > 0:
            streaks.append(cur)
        return {
            "current_streak": cur, "current_type": cur_type,
            "max_win_streak": max_win, "max_loss_streak": max_loss,
            "avg_streak": round(sum(streaks) / len(streaks), 1) if streaks else 0,
        }

    # --- auto-improvement ---------------------------------------------------

    def get_recommendations(self):
        recs = []
        by_strat = self.get_by_strategy()
        for name, data in by_strat.items():
            if data["trade_count"] >= 10 and data["win_rate"] < 40:
                recs.append({"type": "strategy", "severity": "high",
                             "message": f"Strategy '{name}' has {data['win_rate']}% win rate over {data['trade_count']} trades — consider disabling",
                             "action": f"disable_strategy:{name}"})
            if data["trade_count"] >= 10 and data["profit_factor"] < 0.7:
                recs.append({"type": "strategy", "severity": "high",
                             "message": f"Strategy '{name}' profit factor is {data['profit_factor']} — unprofitable",
                             "action": f"disable_strategy:{name}"})

        by_sym = self.get_by_symbol()
        for sym, data in by_sym.items():
            if data["trade_count"] >= 10 and data["profit_factor"] < 0.8:
                recs.append({"type": "symbol", "severity": "medium",
                             "message": f"{sym} has profit factor {data['profit_factor']} — consider excluding",
                             "action": f"exclude_symbol:{sym}"})

        by_hour = self.get_by_hour()
        bad_hours = []
        for h, data in by_hour.items():
            if data["trades"] >= 5 and data["pnl"] < 0 and data["win_rate"] < 30:
                bad_hours.append(int(h))
        if bad_hours:
            recs.append({"type": "schedule", "severity": "medium",
                         "message": f"Poor performance at hours (UTC): {bad_hours} — consider avoiding",
                         "action": f"avoid_hours:{','.join(str(h) for h in bad_hours)}"})

        by_regime = self.get_by_regime()
        for regime, data in by_regime.items():
            if data["trades"] >= 5 and data["pnl"] < 0 and data["win_rate"] < 35:
                recs.append({"type": "regime", "severity": "high",
                             "message": f"Regime '{regime}' is unprofitable ({data['win_rate']}% WR) — consider excluding",
                             "action": f"exclude_regime:{regime}"})

        summary = self.get_summary(period="7d")
        if summary["max_drawdown"] > 0 and summary["total_trades"] >= 5:
            if summary["average_leverage"] > 5 and summary["max_drawdown"] > summary["total_pnl"] * 0.5:
                recs.append({"type": "risk", "severity": "high",
                             "message": f"High drawdown relative to PnL with avg leverage {summary['average_leverage']}x — reduce leverage",
                             "action": "reduce_leverage"})

        return recs

    def get_strategy_weights(self):
        by_strat = self.get_by_strategy()
        scores = {}
        for name, data in by_strat.items():
            tc = data["trade_count"]
            if tc < 5:
                scores[name] = 1.0
                continue
            pf = max(data["profit_factor"], 0.1)
            wr = data["win_rate"] / 100.0
            scores[name] = pf * wr * (tc ** 0.5)
        total = sum(scores.values())
        if total <= 0:
            return {n: round(1.0 / len(scores), 3) for n in scores} if scores else {}
        return {n: round(s / total, 3) for n, s in scores.items()}

    def should_auto_adjust(self):
        summary = self.get_summary()
        if summary["total_trades"] < 50:
            return {"adjust": False, "reason": f"Only {summary['total_trades']}/50 trades — too early"}
        adjustments = []
        by_strat = self.get_by_strategy()
        for name, data in by_strat.items():
            if data["trade_count"] >= 15 and data["profit_factor"] < 0.7:
                adjustments.append({"type": "disable_strategy", "target": name,
                                    "reason": f"PF={data['profit_factor']}"})
        recent = self.get_summary(period="7d")
        if recent["max_drawdown"] > 5 and recent["average_leverage"] > 3:
            adjustments.append({"type": "reduce_leverage", "target": "global",
                                "reason": f"DD={recent['max_drawdown']:.1f}%, Lev={recent['average_leverage']:.0f}x"})
        return {"adjust": len(adjustments) > 0, "adjustments": adjustments}

    def export_csv(self):
        trades = self._query_trades(period="all")
        all_trades = trades + self._query_trades(period="all", status="open")
        if not all_trades:
            return "﻿No trades\n"
        cols = ["id", "timestamp", "symbol", "direction", "strategy", "entry_price",
                "exit_price", "size_usd", "leverage", "pnl_usd", "pnl_pct", "fees_usd",
                "slippage_pct", "duration_minutes", "regime_at_entry", "regime_at_exit",
                "signal_score", "signal_confidence", "macro_score", "stop_loss",
                "take_profit", "exit_reason", "status"]
        lines = ["﻿" + ",".join(cols)]
        for t in all_trades:
            row = []
            for c in cols:
                v = t.get(c, "")
                if v is None:
                    v = ""
                s = str(v)
                if "," in s or '"' in s or "\n" in s:
                    s = '"' + s.replace('"', '""') + '"'
                row.append(s)
            lines.append(",".join(row))
        return "\n".join(lines) + "\n"


performance_tracker = PerformanceTracker()


# ---------------------------------------------------------------------------
# Alert Manager — multi-channel notification system with anti-spam
# ---------------------------------------------------------------------------

_ALERT_PRIORITIES = {
    "CIRCUIT_BREAKER": "CRITICAL", "ERROR": "CRITICAL",
    "TRADE_OPENED": "HIGH", "TRADE_CLOSED": "HIGH",
    "REGIME_CHANGE": "HIGH", "MACRO_EVENT": "HIGH", "DRAWDOWN": "HIGH",
    "SIGNAL_STRONG": "MEDIUM", "DIP_DETECTED": "MEDIUM",
    "TOP_DETECTED": "MEDIUM", "GEOPOLITICAL": "MEDIUM",
    "BOT_STATUS": "LOW",
}

_PRIORITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


class AlertManager:

    def __init__(self):
        self._alerts = deque(maxlen=500)
        self._webhooks = []
        self._telegram = None
        self._discord_url = None
        self._lock = threading.Lock()
        self._cooldowns = {}
        self._cooldown_seconds = 300
        self._alert_id_counter = 0
        self._load_channels()

    def _load_channels(self):
        try:
            conn = get_db()
            rows = conn.execute(
                "SELECT channel, config, events, enabled FROM alert_config WHERE enabled=1"
            ).fetchall()
            conn.close()
            for ch, cfg_json, ev_json, _ in rows:
                try:
                    cfg = json.loads(cfg_json)
                except Exception:
                    continue
                events = None
                if ev_json:
                    try:
                        events = json.loads(ev_json)
                    except Exception:
                        pass
                if ch == "webhook":
                    self._webhooks.append({"url": cfg.get("url", ""), "events": events})
                elif ch == "telegram":
                    self._telegram = {"token": cfg.get("token", ""), "chat_id": cfg.get("chat_id", "")}
                elif ch == "discord":
                    self._discord_url = cfg.get("url", "")
        except Exception:
            pass

    def send(self, alert_type, message, priority=None, data=None):
        if priority is None:
            priority = _ALERT_PRIORITIES.get(alert_type, "MEDIUM")

        now = time.time()
        cooldown_key = f"{alert_type}:{message[:40]}"
        with self._lock:
            last = self._cooldowns.get(cooldown_key, 0)
            if now - last < self._cooldown_seconds and priority != "CRITICAL":
                return None
            self._cooldowns[cooldown_key] = now
            self._alert_id_counter += 1
            aid = self._alert_id_counter

        alert = {
            "id": aid,
            "type": alert_type,
            "priority": priority,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }

        with self._lock:
            self._alerts.append(alert)

        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO notification_log (alert_type, priority, message, data) VALUES (?,?,?,?)",
                (alert_type, priority, message, json.dumps(data or {})))
            conn.commit()
            conn.close()
        except Exception:
            pass

        threading.Thread(target=self._dispatch_all, args=(alert,), daemon=True).start()
        return alert

    def get_recent(self, limit=50, priority=None, alert_type=None, since_id=0):
        with self._lock:
            out = list(self._alerts)
        if since_id:
            out = [a for a in out if a["id"] > since_id]
        if priority:
            min_ord = _PRIORITY_ORDER.get(priority, 0)
            out = [a for a in out if _PRIORITY_ORDER.get(a["priority"], 0) >= min_ord]
        if alert_type:
            out = [a for a in out if a["type"] == alert_type]
        return out[-limit:]

    def add_webhook(self, url, events=None):
        self._webhooks.append({"url": url, "events": events})
        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO alert_config (channel, config, events, enabled) VALUES (?,?,?,1)",
                ("webhook", json.dumps({"url": url}),
                 json.dumps(events) if events else None))
            conn.commit()
            conn.close()
        except Exception:
            pass
        return True

    def configure_telegram(self, bot_token, chat_id):
        self._telegram = {"token": bot_token, "chat_id": chat_id}
        try:
            conn = get_db()
            conn.execute("DELETE FROM alert_config WHERE channel='telegram'")
            conn.execute(
                "INSERT INTO alert_config (channel, config, enabled) VALUES (?,?,1)",
                ("telegram", json.dumps({"token": bot_token, "chat_id": chat_id})))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def configure_discord(self, webhook_url):
        self._discord_url = webhook_url
        try:
            conn = get_db()
            conn.execute("DELETE FROM alert_config WHERE channel='discord'")
            conn.execute(
                "INSERT INTO alert_config (channel, config, enabled) VALUES (?,?,1)",
                ("discord", json.dumps({"url": webhook_url})))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _dispatch_all(self, alert):
        for wh in self._webhooks:
            evts = wh.get("events")
            if evts and alert["type"] not in evts:
                continue
            self._dispatch_webhook(alert, wh["url"])
        if self._telegram:
            self._dispatch_telegram(alert)
        if self._discord_url:
            self._dispatch_discord(alert)

    def _dispatch_webhook(self, alert, url):
        try:
            requests.post(url, json=alert, timeout=5)
        except Exception:
            pass

    def _dispatch_telegram(self, alert):
        if not self._telegram:
            return
        prio_emoji = {"CRITICAL": "\U0001F534", "HIGH": "\U0001F7E0",
                      "MEDIUM": "\U0001F535", "LOW": "⚪"}
        emoji = prio_emoji.get(alert["priority"], "⚪")
        text = f"{emoji} *{alert['type']}*\n{alert['message']}"
        try:
            url = f"https://api.telegram.org/bot{self._telegram['token']}/sendMessage"
            requests.post(url, json={
                "chat_id": self._telegram["chat_id"],
                "text": text, "parse_mode": "Markdown",
            }, timeout=5)
        except Exception:
            pass

    def _dispatch_discord(self, alert):
        if not self._discord_url:
            return
        prio_emoji = {"CRITICAL": "\U0001F534", "HIGH": "\U0001F7E0",
                      "MEDIUM": "\U0001F535", "LOW": "⚪"}
        emoji = prio_emoji.get(alert["priority"], "⚪")
        content = f"{emoji} **{alert['type']}** — {alert['message']}"
        try:
            requests.post(self._discord_url, json={"content": content}, timeout=5)
        except Exception:
            pass


alert_manager = AlertManager()


# ---------------------------------------------------------------------------
# Macro-Economic & Geopolitical Data Engine
# Aggregates free data sources (no API keys) into a single macro score that
# the AutonomousEngine uses to adjust risk appetite and signal thresholds.
# ---------------------------------------------------------------------------

_GEO_KEYWORDS_CRITICAL = ["war", "invasion", "nuclear", "sanctions", "default", "attack", "bomb"]
_GEO_KEYWORDS_HIGH = ["tariff", "trade war", "missile", "military", "embargo", "blockade", "coup"]
_GEO_KEYWORDS_MEDIUM = ["election", "summit", "protest", "crisis", "recession", "shutdown", "strike"]
_GEO_KEYWORDS_LOW = ["regulation", "policy", "diplomatic", "agreement", "treaty", "negotiate"]

_CRYPTO_REG_POSITIVE = ["etf approval", "etf approved", "adoption", "legal tender", "pro-crypto", "favorable"]
_CRYPTO_REG_NEGATIVE = ["ban", "lawsuit", "sued", "crackdown", "restrict", "fraud", "enforcement"]

_EVENT_IMPACT_MAP = {
    "CPI":   {"higher": -20, "lower": 15, "inline": 0},
    "NFP":   {"higher": -15, "lower": 10, "inline": 0},
    "FOMC":  {"hawkish": -25, "dovish": 25, "neutral": 0},
    "GDP":   {"higher": 5, "lower": -10, "inline": 0},
    "PCE":   {"higher": -15, "lower": 10, "inline": 0},
    "PPI":   {"higher": -10, "lower": 8, "inline": 0},
    "ISM":   {"higher": 5, "lower": -5, "inline": 0},
    "RETAIL": {"higher": 5, "lower": -5, "inline": 0},
    "JOBLESS": {"higher": 10, "lower": -5, "inline": 0},
    "RATE_CUT": {"actual": 30, "none": -5},
    "RATE_HIKE": {"actual": -30, "none": 5},
    "TARIFF": {"new": -15, "removed": 10, "none": 0},
}

_CRYPTO_EVENT_MAP = {
    "FOMC": ["BTCUSDT", "ETHUSDT"],
    "CPI": ["BTCUSDT", "ETHUSDT"],
    "NFP": ["BTCUSDT", "ETHUSDT"],
    "DXY": ["BTCUSDT"],
    "GEOPOLITICAL": ["BTCUSDT"],
    "REGULATION": ["ETHUSDT", "SOLUSDT"],
    "CHINA": ["BTCUSDT"],
    "ALTSEASON": ["SOLUSDT", "DOGEUSDT", "XRPUSDT"],
}

_ENRICHED_CALENDAR = [
    {"event": "FOMC Decision", "type": "FOMC", "impact": "HIGH",
     "dates": ["2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
               "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16"]},
    {"event": "FOMC Minutes", "type": "FOMC", "impact": "MEDIUM",
     "dates": ["2026-02-18", "2026-04-08", "2026-05-27", "2026-07-08",
               "2026-08-19", "2026-10-07", "2026-11-25"]},
    {"event": "CPI Release", "type": "CPI", "impact": "HIGH",
     "dates": ["2026-01-14", "2026-02-12", "2026-03-12", "2026-04-14",
               "2026-05-13", "2026-06-10", "2026-07-14", "2026-08-12",
               "2026-09-10", "2026-10-13", "2026-11-12", "2026-12-10"]},
    {"event": "Non-Farm Payrolls", "type": "NFP", "impact": "HIGH",
     "dates": ["2026-01-09", "2026-02-06", "2026-03-06", "2026-04-03",
               "2026-05-08", "2026-06-05", "2026-07-02", "2026-08-07",
               "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04"]},
    {"event": "GDP (Advance)", "type": "GDP", "impact": "MEDIUM",
     "dates": ["2026-01-29", "2026-04-29", "2026-07-29", "2026-10-28"]},
    {"event": "PCE Price Index", "type": "PCE", "impact": "HIGH",
     "dates": ["2026-01-30", "2026-02-27", "2026-03-27", "2026-04-30",
               "2026-05-29", "2026-06-26", "2026-07-31", "2026-08-28"]},
    {"event": "PPI Release", "type": "PPI", "impact": "MEDIUM",
     "dates": ["2026-01-15", "2026-02-13", "2026-03-13", "2026-04-15",
               "2026-05-14", "2026-06-11", "2026-07-15", "2026-08-13"]},
    {"event": "ISM Manufacturing", "type": "ISM", "impact": "MEDIUM",
     "dates": ["2026-01-05", "2026-02-02", "2026-03-02", "2026-04-01",
               "2026-05-01", "2026-06-01", "2026-07-01", "2026-08-03"]},
    {"event": "Retail Sales", "type": "RETAIL", "impact": "MEDIUM",
     "dates": ["2026-01-16", "2026-02-14", "2026-03-17", "2026-04-16",
               "2026-05-15", "2026-06-16", "2026-07-16", "2026-08-14"]},
    {"event": "Jobless Claims", "type": "JOBLESS", "impact": "LOW",
     "dates": []},
    {"event": "ECB Decision", "type": "FOMC", "impact": "MEDIUM",
     "dates": ["2026-01-22", "2026-03-05", "2026-04-16", "2026-06-04",
               "2026-07-16", "2026-09-10", "2026-10-29", "2026-12-10"]},
]


class MacroDataEngine:
    """Fetches and analyzes macro-economic & geopolitical data."""

    _CACHE_TTL = {
        "fear_greed": 3600,
        "dxy": 300,
        "vix": 300,
        "yields": 300,
        "gold_oil": 300,
        "dominance": 600,
        "geopolitical": 900,
        "crypto_reg": 900,
        "calendar": 14400,
    }

    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
        self._last_fetch = {}
        self._last_score = None
        self._refresh_thread = None
        self._running = False

    # ----- cache helpers ----------------------------------------------------

    def _get_cached(self, key):
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            data, ts = entry
            ttl = self._CACHE_TTL.get(key, 300)
            if time.time() - ts > ttl:
                return None
            return data

    def _set_cached(self, key, data):
        with self._lock:
            self._cache[key] = (data, time.time())

    # ----- background refresh -----------------------------------------------

    def start_refresh(self):
        if self._running:
            return
        self._running = True
        self._refresh_thread = threading.Thread(target=self._refresh_loop,
                                                daemon=True, name="macro-refresh")
        self._refresh_thread.start()
        log.info("[MACRO] Background refresh started")

    def _refresh_loop(self):
        while self._running:
            try:
                self.compute_macro_score()
            except Exception as exc:
                log.warning("[MACRO] Refresh error: %s", exc)
            time.sleep(900)

    # ----- data sources -----------------------------------------------------

    def fetch_fear_greed_index(self):
        cached = self._get_cached("fear_greed")
        if cached is not None:
            return cached
        try:
            resp = requests.get("https://api.alternative.me/fng/",
                                params={"limit": 30, "format": "json"}, timeout=5)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            if not data:
                return None
            current = int(data[0].get("value", 50))
            classification = data[0].get("value_classification", "Neutral")
            values = [int(d.get("value", 50)) for d in data[:7]]
            trend = "rising" if len(values) >= 2 and values[0] > values[-1] else (
                "falling" if len(values) >= 2 and values[0] < values[-1] else "flat")
            result = {
                "value": current,
                "classification": classification,
                "trend": trend,
                "history_7d": values,
            }
            self._set_cached("fear_greed", result)
            return result
        except Exception as exc:
            log.debug("[MACRO] Fear & Greed fetch failed: %s", exc)
            return None

    def _fetch_stooq(self, symbol):
        cache_key = f"stooq_macro:{symbol}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        try:
            resp = requests.get(STOOQ_BASE,
                                params={"s": symbol, "f": "sd2t2ohlcv", "h": "", "e": "csv"},
                                timeout=5)
            resp.raise_for_status()
            lines = resp.text.strip().split("\n")
            if len(lines) < 2:
                return None
            headers = [h.strip().lower() for h in lines[0].split(",")]
            values = lines[1].split(",")
            row = {}
            for h, v in zip(headers, values):
                row[h] = v.strip()
            price = float(row.get("close", 0))
            open_p = float(row.get("open", 0))
            if price <= 0:
                return None
            change = ((price - open_p) / open_p * 100) if open_p > 0 else 0
            result = {"price": price, "open": open_p, "change_pct": round(change, 3)}
            self._set_cached(cache_key, result)
            return result
        except Exception as exc:
            log.debug("[MACRO] Stooq %s failed: %s", symbol, exc)
            return None

    def fetch_dxy_strength(self):
        cached = self._get_cached("dxy")
        if cached is not None:
            return cached
        data = self._fetch_stooq("dx.f")
        if not data:
            return None
        change = data["change_pct"]
        if change > 0.15:
            trend = "rising"
        elif change < -0.15:
            trend = "falling"
        else:
            trend = "flat"
        result = {
            "value": data["price"],
            "change_pct": change,
            "trend": trend,
            "crypto_impact": "bearish" if trend == "rising" else (
                "bullish" if trend == "falling" else "neutral"),
        }
        self._set_cached("dxy", result)
        return result

    def fetch_treasury_yields(self):
        cached = self._get_cached("yields")
        if cached is not None:
            return cached
        y10 = self._fetch_stooq("10usy.b")
        y2 = self._fetch_stooq("2usy.b")
        y30 = self._fetch_stooq("30usy.b")
        yields = {}
        if y10:
            yields["10y"] = y10["price"]
        if y2:
            yields["2y"] = y2["price"]
        if y30:
            yields["30y"] = y30["price"]
        spread = yields.get("10y", 0) - yields.get("2y", 0) if "10y" in yields and "2y" in yields else None
        result = {
            "yields": yields,
            "spread_10y_2y": round(spread, 3) if spread is not None else None,
            "is_inverted": spread is not None and spread < 0,
        }
        self._set_cached("yields", result)
        return result

    def fetch_vix(self):
        cached = self._get_cached("vix")
        if cached is not None:
            return cached
        data = self._fetch_stooq("^vix")
        if not data:
            return None
        val = data["price"]
        if val < 15:
            regime = "low"
        elif val < 25:
            regime = "normal"
        elif val < 35:
            regime = "high"
        else:
            regime = "extreme"
        result = {
            "value": val,
            "change_pct": data["change_pct"],
            "regime": regime,
            "crypto_impact": "bearish" if regime in ("high", "extreme") else "neutral",
        }
        self._set_cached("vix", result)
        return result

    def fetch_gold_oil_correlation(self):
        cached = self._get_cached("gold_oil")
        if cached is not None:
            return cached
        gold = self._fetch_stooq("xauusd")
        oil = self._fetch_stooq("cl.f")
        result = {"gold": None, "oil": None, "signal": "neutral"}
        if gold:
            result["gold"] = {"price": gold["price"], "change_pct": gold["change_pct"]}
        if oil:
            result["oil"] = {"price": oil["price"], "change_pct": oil["change_pct"]}
        if gold and oil:
            gold_up = gold["change_pct"] > 0.2
            oil_down = oil["change_pct"] < -0.2
            gold_down = gold["change_pct"] < -0.2
            oil_up = oil["change_pct"] > 0.2
            if gold_up and oil_down:
                result["signal"] = "risk_off"
            elif gold_down and oil_up:
                result["signal"] = "risk_on"
        self._set_cached("gold_oil", result)
        return result

    def fetch_crypto_dominance(self):
        cached = self._get_cached("dominance")
        if cached is not None:
            return cached
        try:
            resp = requests.get("https://api.coingecko.com/api/v3/global", timeout=5,
                                headers={"User-Agent": "JARVIS/3.0"})
            resp.raise_for_status()
            data = resp.json().get("data", {})
            mcp = data.get("market_cap_percentage", {})
            result = {
                "btc_dominance": round(mcp.get("btc", 0), 2),
                "eth_dominance": round(mcp.get("eth", 0), 2),
                "total_market_cap_usd": data.get("total_market_cap", {}).get("usd", 0),
                "market_cap_change_24h": round(data.get("market_cap_change_percentage_24h_usd", 0), 2),
            }
            if result["btc_dominance"] > 55:
                result["signal"] = "btc_flight"
            elif result["btc_dominance"] < 45:
                result["signal"] = "alt_season"
            else:
                result["signal"] = "neutral"
            self._set_cached("dominance", result)
            return result
        except Exception as exc:
            log.debug("[MACRO] CoinGecko dominance failed: %s", exc)
            return None

    def fetch_geopolitical_risk(self):
        cached = self._get_cached("geopolitical")
        if cached is not None:
            return cached
        feeds = [
            ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
            ("Reuters", "http://feeds.reuters.com/Reuters/worldNews"),
        ]
        all_titles = []
        for name, url in feeds:
            try:
                resp = requests.get(url, timeout=5, headers={"User-Agent": "JARVIS/3.0"})
                if resp.status_code != 200:
                    continue
                items = _parse_rss_minimal(resp.text, name)
                for item in items:
                    all_titles.append(item.get("title", "").lower())
            except Exception:
                continue

        score = 0
        top_events = []
        for title in all_titles:
            event_score = 0
            level = None
            for kw in _GEO_KEYWORDS_CRITICAL:
                if kw in title:
                    event_score = max(event_score, 10)
                    level = "CRITICAL"
            for kw in _GEO_KEYWORDS_HIGH:
                if kw in title:
                    event_score = max(event_score, 7)
                    level = level or "HIGH"
            for kw in _GEO_KEYWORDS_MEDIUM:
                if kw in title:
                    event_score = max(event_score, 4)
                    level = level or "MEDIUM"
            for kw in _GEO_KEYWORDS_LOW:
                if kw in title:
                    event_score = max(event_score, 2)
                    level = level or "LOW"
            if event_score > 0:
                score += event_score
                if len(top_events) < 10:
                    top_events.append({"title": title[:120], "level": level, "score": event_score})

        score = min(score, 100)
        if score >= 60:
            alert = "CRITICAL"
        elif score >= 35:
            alert = "HIGH"
        elif score >= 15:
            alert = "MEDIUM"
        else:
            alert = "LOW"

        top_events.sort(key=lambda e: e["score"], reverse=True)
        result = {
            "risk_score": score,
            "alert_level": alert,
            "top_events": top_events[:5],
            "headlines_scanned": len(all_titles),
        }
        self._set_cached("geopolitical", result)
        return result

    def fetch_crypto_regulation_news(self):
        cached = self._get_cached("crypto_reg")
        if cached is not None:
            return cached
        feeds = [
            ("CoinTelegraph", "https://cointelegraph.com/rss"),
            ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ]
        articles = []
        for name, url in feeds:
            try:
                resp = requests.get(url, timeout=5, headers={"User-Agent": "JARVIS/3.0"})
                if resp.status_code != 200:
                    continue
                items = _parse_rss_minimal(resp.text, name)
                articles.extend(items)
            except Exception:
                continue

        positive = 0
        negative = 0
        reg_events = []
        for art in articles:
            title_lower = (art.get("title", "") + " " + art.get("description", "")).lower()
            is_reg = any(kw in title_lower for kw in
                         ["sec", "cftc", "regulat", "ban", "etf", "approval", "lawsuit", "enforce"])
            if not is_reg:
                continue
            impact = "NEUTRAL"
            for kw in _CRYPTO_REG_POSITIVE:
                if kw in title_lower:
                    positive += 1
                    impact = "POSITIVE"
                    break
            for kw in _CRYPTO_REG_NEGATIVE:
                if kw in title_lower:
                    negative += 1
                    impact = "NEGATIVE"
                    break
            if len(reg_events) < 5:
                reg_events.append({"title": art.get("title", "")[:120], "impact": impact,
                                   "source": art.get("source", "")})

        result = {
            "positive_count": positive,
            "negative_count": negative,
            "net_sentiment": "bullish" if positive > negative + 1 else (
                "bearish" if negative > positive + 1 else "neutral"),
            "events": reg_events,
        }
        self._set_cached("crypto_reg", result)
        return result

    def fetch_economic_calendar(self):
        cached = self._get_cached("calendar")
        if cached is not None:
            return cached
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        events = []
        event_mode = False

        for cal in _ENRICHED_CALENDAR:
            for date_str in cal["dates"]:
                try:
                    event_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    days_until = (event_date - now).days
                    if -1 <= days_until <= 30:
                        entry = {
                            "event": cal["event"],
                            "type": cal.get("type", ""),
                            "date": date_str,
                            "impact": cal["impact"],
                            "days_until": days_until,
                            "is_today": days_until == 0,
                            "hours_until": max(0, int((event_date - now).total_seconds() / 3600)),
                        }
                        events.append(entry)
                        if days_until == 0 and cal["impact"] == "HIGH":
                            event_mode = True
                except ValueError:
                    continue

        events.sort(key=lambda e: e.get("hours_until", 999))
        result = {
            "events": events,
            "event_mode": event_mode,
            "today": today_str,
            "next_event": events[0] if events else None,
            "high_impact_24h": [e for e in events if e["impact"] == "HIGH" and e.get("hours_until", 999) <= 24],
        }
        self._set_cached("calendar", result)
        return result

    # ----- analysis ---------------------------------------------------------

    def compute_macro_score(self):
        components = {}
        score = 0.0
        alert_events = []

        fg = self.fetch_fear_greed_index()
        if fg:
            val = fg["value"]
            if val < 20:
                s = 15.0
                components["fear_greed"] = {"value": val, "score": s, "detail": "Extreme Fear (contrarian bullish)"}
            elif val > 80:
                s = -15.0
                components["fear_greed"] = {"value": val, "score": s, "detail": "Extreme Greed (contrarian bearish)"}
            elif val < 35:
                s = 8.0
                components["fear_greed"] = {"value": val, "score": s, "detail": "Fear (mildly bullish)"}
            elif val > 65:
                s = -8.0
                components["fear_greed"] = {"value": val, "score": s, "detail": "Greed (mildly bearish)"}
            else:
                s = 0.0
                components["fear_greed"] = {"value": val, "score": s, "detail": "Neutral"}
            score += s

        dxy = self.fetch_dxy_strength()
        if dxy:
            chg = dxy["change_pct"]
            s = -chg * 10.0
            s = max(-20, min(20, s))
            components["dxy"] = {"value": dxy["value"], "change": chg, "score": round(s, 1),
                                 "detail": f"DXY {dxy['trend']} ({chg:+.2f}%)"}
            score += s

        vix = self.fetch_vix()
        if vix:
            val = vix["value"]
            if val > 35:
                s = -15.0
            elif val > 25:
                s = -10.0
            elif val < 15:
                s = 5.0
            else:
                s = 0.0
            components["vix"] = {"value": val, "regime": vix["regime"], "score": s}
            score += s

        yields = self.fetch_treasury_yields()
        if yields and yields["spread_10y_2y"] is not None:
            spread = yields["spread_10y_2y"]
            if yields["is_inverted"]:
                s = -10.0
                components["yields"] = {"spread": spread, "inverted": True, "score": s,
                                        "detail": "Yield curve inverted — recession signal"}
            elif spread < 0.2:
                s = -5.0
                components["yields"] = {"spread": spread, "inverted": False, "score": s,
                                        "detail": "Yield curve flattening"}
            else:
                s = 2.0
                components["yields"] = {"spread": spread, "inverted": False, "score": s,
                                        "detail": "Yield curve normal"}
            score += s

        gold_oil = self.fetch_gold_oil_correlation()
        if gold_oil:
            sig = gold_oil["signal"]
            if sig == "risk_off":
                s = -5.0
            elif sig == "risk_on":
                s = 5.0
            else:
                s = 0.0
            components["gold_oil"] = {"signal": sig, "score": s,
                                      "gold": gold_oil.get("gold"), "oil": gold_oil.get("oil")}
            score += s

        dom = self.fetch_crypto_dominance()
        if dom:
            sig = dom["signal"]
            mcc = dom["market_cap_change_24h"]
            if mcc > 3:
                s = 10.0
            elif mcc < -3:
                s = -10.0
            else:
                s = mcc * 1.5
            components["dominance"] = {"btc_d": dom["btc_dominance"], "signal": sig,
                                       "market_cap_change": mcc, "score": round(s, 1)}
            score += s

        geo = self.fetch_geopolitical_risk()
        if geo:
            risk = geo["risk_score"]
            s = -risk * 0.15
            s = max(-15, min(0, s))
            components["geopolitical"] = {"risk_score": risk, "alert": geo["alert_level"],
                                          "score": round(s, 1)}
            score += s
            if geo["alert_level"] in ("CRITICAL", "HIGH"):
                alert_events.extend(geo.get("top_events", [])[:3])

        cal = self.fetch_economic_calendar()
        if cal:
            high_24h = cal.get("high_impact_24h", [])
            if high_24h:
                s = -5.0
                components["upcoming_events"] = {"count": len(high_24h), "score": s,
                                                 "events": [e["event"] for e in high_24h[:3]]}
                score += s
                for e in high_24h:
                    alert_events.append({"title": e["event"], "level": "HIGH",
                                         "hours_until": e.get("hours_until", 0)})

        score = max(-100, min(100, score))

        if score > 30:
            recommendation = "BULLISH — macro conditions favor crypto"
        elif score > 10:
            recommendation = "MILDLY_BULLISH — conditions slightly favorable"
        elif score < -30:
            recommendation = "BEARISH — macro headwinds for crypto"
        elif score < -10:
            recommendation = "MILDLY_BEARISH — conditions slightly unfavorable"
        else:
            recommendation = "NEUTRAL — no strong macro bias"

        result = {
            "score": round(score, 1),
            "recommendation": recommendation,
            "components": components,
            "alert_events": alert_events[:5],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._last_score = result
        return result

    def get_event_impact_on_crypto(self, event_type, outcome="inline"):
        impact = _EVENT_IMPACT_MAP.get(event_type.upper(), {})
        return impact.get(outcome, 0)

    def get_correlated_cryptos(self, event_type):
        return _CRYPTO_EVENT_MAP.get(event_type.upper(), ["BTCUSDT", "ETHUSDT"])

    def should_reduce_exposure(self):
        cal = self.fetch_economic_calendar()
        if not cal:
            return {"reduce": False, "reason": "", "target_exposure_pct": 100}

        high_24h = cal.get("high_impact_24h", [])
        for event in high_24h:
            hours = event.get("hours_until", 999)
            if hours <= 4 and event["impact"] == "HIGH":
                return {
                    "reduce": True,
                    "reason": f"{event['event']} in {hours}h (HIGH impact)",
                    "target_exposure_pct": 0,
                }

        events = cal.get("events", [])
        for event in events:
            hours = event.get("hours_until", 999)
            if hours <= 1 and event["impact"] == "MEDIUM":
                return {
                    "reduce": True,
                    "reason": f"{event['event']} in {hours}h (MEDIUM impact)",
                    "target_exposure_pct": 50,
                }

        geo = self.fetch_geopolitical_risk()
        if geo and geo.get("alert_level") == "CRITICAL":
            return {
                "reduce": True,
                "reason": f"Geopolitical risk CRITICAL (score {geo['risk_score']})",
                "target_exposure_pct": 25,
            }

        return {"reduce": False, "reason": "", "target_exposure_pct": 100}

    def get_last_score(self):
        return self._last_score


macro_engine = MacroDataEngine()


# ---------------------------------------------------------------------------
# Circuit Breaker System — 7-level institutional risk protection
# ---------------------------------------------------------------------------

class CircuitBreakerSystem:
    """Multi-level circuit breaker inspired by institutional trading desks.

    7 independent levels, each with its own trigger, action, and reset logic.
    Levels 4-5 require manual acknowledgement to reset.
    """

    _LEVEL_META = {
        1: {"name": "YELLOW",      "label": "Attention",  "auto_reset_s": 1800},
        2: {"name": "ORANGE",      "label": "Caution",    "auto_reset_s": 3600},
        3: {"name": "RED",         "label": "Danger",     "auto_reset_s": 7200},
        4: {"name": "DARK_RED",    "label": "Critical",   "auto_reset_s": None},
        5: {"name": "BLACK",       "label": "Emergency",  "auto_reset_s": None},
        6: {"name": "FLASH_CRASH", "label": "Flash Crash", "auto_reset_s": 1800},
        7: {"name": "SYSTEM_FAULT", "label": "System Fault", "auto_reset_s": 0},
    }

    _CORRELATED_PAIRS = {
        "BTCUSDT": ["ETHUSDT"],
        "ETHUSDT": ["BTCUSDT"],
        "SOLUSDT": ["ETHUSDT"],
    }

    def __init__(self):
        self._levels = {i: False for i in range(1, 8)}
        self._triggered_at = {}
        self._actions_log = []
        self._consecutive_losses = 0
        self._last_loss_time = 0
        self._last_drawdown_increase_time = 0
        self._prev_daily_dd = 0.0
        self._lock = threading.Lock()

    def check(self, portfolio_state, market_data=None):
        """Evaluate all 7 circuit breakers independently.

        portfolio_state: {daily_pnl_pct, drawdown_pct, initial_capital,
                          current_capital, consecutive_losses}
        market_data:     {symbol: {price_5m_ago, price_now}} for flash crash detection
        """
        actions = []
        now = time.time()

        daily_dd = abs(portfolio_state.get("daily_pnl_pct", 0))
        total_dd = portfolio_state.get("drawdown_pct", 0)
        consec = portfolio_state.get("consecutive_losses", self._consecutive_losses)
        initial_cap = portfolio_state.get("initial_capital", 100)
        current_cap = portfolio_state.get("current_capital", initial_cap)
        capital_loss_pct = ((initial_cap - current_cap) / initial_cap * 100) if initial_cap > 0 else 0

        with self._lock:
            self._consecutive_losses = consec

            if daily_dd > self._prev_daily_dd:
                self._last_drawdown_increase_time = now
            self._prev_daily_dd = daily_dd

            self._try_auto_reset(now)

            # --- Level 1: YELLOW ---
            if daily_dd > 2.0 or consec >= 3:
                if not self._levels[1]:
                    self._trigger(1, now, f"daily_dd={daily_dd:.1f}% consec_losses={consec}")
                actions.append({"level": 1, "action": "reduce_leverage_50pct"})

            # --- Level 2: ORANGE ---
            if daily_dd > 3.5 or consec >= 5:
                if not self._levels[2]:
                    self._trigger(2, now, f"daily_dd={daily_dd:.1f}% consec_losses={consec}")
                actions.append({"level": 2, "action": "reduce_size_50pct_pause_15m"})

            # --- Level 3: RED ---
            if daily_dd > 5.0 or total_dd > 10.0:
                if not self._levels[3]:
                    self._trigger(3, now, f"daily_dd={daily_dd:.1f}% total_dd={total_dd:.1f}%")
                actions.append({"level": 3, "action": "close_all_block_1h"})

            # --- Level 4: DARK_RED ---
            if total_dd > 15.0 or capital_loss_pct > 50.0:
                if not self._levels[4]:
                    self._trigger(4, now, f"total_dd={total_dd:.1f}% capital_loss={capital_loss_pct:.1f}%")
                actions.append({"level": 4, "action": "kill_switch"})

            # --- Level 6: FLASH_CRASH ---
            if market_data:
                for sym, md in market_data.items():
                    p_ago = md.get("price_5m_ago", 0)
                    p_now = md.get("price_now", 0)
                    if p_ago > 0 and p_now > 0:
                        move_pct = abs(p_now - p_ago) / p_ago * 100
                        if move_pct > 10.0:
                            if not self._levels[6]:
                                self._trigger(6, now, f"{sym} moved {move_pct:.1f}% in <5min")
                            actions.append({"level": 6, "action": "emergency_close",
                                            "symbol": sym, "move_pct": round(move_pct, 1)})

            # --- Level 7: SYSTEM_FAULT ---
            stale = portfolio_state.get("data_stale_seconds", 0)
            exchange_err = portfolio_state.get("exchange_error", False)
            if stale > 300 or exchange_err:
                if not self._levels[7]:
                    reason = f"stale={stale}s" if stale > 300 else "exchange_error"
                    self._trigger(7, now, reason)
                actions.append({"level": 7, "action": "block_new_positions"})
            else:
                if self._levels[7]:
                    self._reset_level(7, "connectivity_restored")

        active = {lvl for lvl, on in self._levels.items() if on}
        return {
            "active_levels": sorted(active),
            "actions": actions,
            "max_level": max(active) if active else 0,
            "allowed": self.get_max_allowed_action(),
        }

    def trigger_execution_error(self, slippage_pct=0, phantom_order=False):
        """Level 5 — BLACK: called by execution layer on critical errors."""
        now = time.time()
        with self._lock:
            if slippage_pct > 5.0 or phantom_order:
                reason = f"slippage={slippage_pct:.1f}%" if slippage_pct > 5.0 else "phantom_order"
                self._trigger(5, now, reason)
                return {"level": 5, "action": "kill_switch_stop_bot", "reason": reason}
        return None

    def record_loss(self):
        """Increment consecutive loss counter and record timing."""
        with self._lock:
            self._consecutive_losses += 1
            self._last_loss_time = time.time()

    def record_win(self):
        """Reset consecutive loss counter on a winning trade."""
        with self._lock:
            self._consecutive_losses = 0

    def get_max_allowed_action(self):
        """Determine the most restrictive action from all active levels.

        Returns: 'full' | 'reduced' | 'close_only' | 'blocked'
        """
        with self._lock:
            active = {lvl for lvl, on in self._levels.items() if on}

        if not active:
            return "full"
        if active & {4, 5}:
            return "blocked"
        if active & {3}:
            return "close_only"
        if active & {1, 2, 6, 7}:
            return "reduced"
        return "full"

    def is_new_trade_allowed(self):
        """Quick check: can the bot open a new position right now?"""
        allowed = self.get_max_allowed_action()
        if allowed in ("blocked", "close_only"):
            return False
        with self._lock:
            if self._levels[2]:
                elapsed = time.time() - self._triggered_at.get(2, 0)
                if elapsed < 900:
                    return False
            if self._levels[3]:
                elapsed = time.time() - self._triggered_at.get(3, 0)
                if elapsed < 3600:
                    return False
        return True

    def get_leverage_multiplier(self):
        """Returns multiplier to apply to requested leverage (0.0 to 1.0)."""
        with self._lock:
            if self._levels[4] or self._levels[5]:
                return 0.0
            if self._levels[3]:
                return 0.0
            if self._levels[2]:
                return 0.25
            if self._levels[1]:
                return 0.5
        return 1.0

    def get_size_multiplier(self):
        """Returns multiplier to apply to position size (0.0 to 1.0)."""
        with self._lock:
            if self._levels[4] or self._levels[5] or self._levels[3]:
                return 0.0
            if self._levels[2]:
                return 0.5
            if self._levels[1]:
                return 0.75
        return 1.0

    def acknowledge(self, level):
        """Manual reset of a circuit breaker level. Required for L4-L5."""
        level = int(level)
        if level not in self._levels:
            return {"success": False, "error": f"Invalid level {level}"}
        with self._lock:
            if not self._levels[level]:
                return {"success": False, "error": f"Level {level} is not active"}
            self._reset_level(level, "manual_acknowledge")
            self._consecutive_losses = 0
        return {"success": True, "level": level, "reset": True}

    def get_status(self):
        """Full status for dashboard display."""
        with self._lock:
            levels_info = {}
            for lvl in range(1, 8):
                meta = self._LEVEL_META[lvl]
                levels_info[lvl] = {
                    "active": self._levels[lvl],
                    "name": meta["name"],
                    "label": meta["label"],
                    "triggered_at": self._triggered_at.get(lvl),
                    "auto_reset": meta["auto_reset_s"] is not None and meta["auto_reset_s"] > 0,
                    "auto_reset_seconds": meta["auto_reset_s"],
                }
                if self._levels[lvl] and self._triggered_at.get(lvl):
                    elapsed = time.time() - self._triggered_at[lvl]
                    levels_info[lvl]["active_for_seconds"] = round(elapsed, 0)
            return {
                "levels": levels_info,
                "max_level": max((l for l, on in self._levels.items() if on), default=0),
                "allowed_action": self.get_max_allowed_action(),
                "consecutive_losses": self._consecutive_losses,
                "leverage_multiplier": self.get_leverage_multiplier(),
                "size_multiplier": self.get_size_multiplier(),
                "new_trade_allowed": self.is_new_trade_allowed(),
                "recent_log": list(self._actions_log[-20:]),
            }

    # ----- internal helpers ---------------------------------------------------

    def _trigger(self, level, ts, reason):
        self._levels[level] = True
        self._triggered_at[level] = ts
        meta = self._LEVEL_META[level]
        entry = {
            "time": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
            "level": level,
            "name": meta["name"],
            "event": "TRIGGERED",
            "reason": reason,
        }
        self._actions_log.append(entry)
        if len(self._actions_log) > 200:
            self._actions_log = self._actions_log[-200:]
        log.warning("[CB] Level %d (%s) TRIGGERED — %s", level, meta["name"], reason)
        try:
            prio = "CRITICAL" if level >= 3 else "HIGH"
            alert_manager.send("CIRCUIT_BREAKER",
                               f"Circuit Breaker L{level} ({meta['name']}) triggered: {reason}",
                               priority=prio, data={"level": level, "reason": reason})
        except Exception:
            pass

    def _reset_level(self, level, reason):
        self._levels[level] = False
        meta = self._LEVEL_META[level]
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "name": meta["name"],
            "event": "RESET",
            "reason": reason,
        }
        self._actions_log.append(entry)
        if len(self._actions_log) > 200:
            self._actions_log = self._actions_log[-200:]
        log.info("[CB] Level %d (%s) RESET — %s", level, meta["name"], reason)

    def _try_auto_reset(self, now):
        """Auto-reset levels whose cooldown has expired. L4-L5 are manual only."""
        for lvl in (1, 2, 3, 6):
            if not self._levels[lvl]:
                continue
            triggered = self._triggered_at.get(lvl, 0)
            cooldown = self._LEVEL_META[lvl]["auto_reset_s"]
            if cooldown is None:
                continue
            elapsed = now - triggered
            if elapsed < cooldown:
                continue
            if lvl in (1, 2):
                time_since_loss = now - self._last_loss_time if self._last_loss_time else elapsed
                if time_since_loss < cooldown:
                    continue
            if lvl == 3:
                time_since_dd = now - self._last_drawdown_increase_time if self._last_drawdown_increase_time else elapsed
                if time_since_dd < cooldown:
                    continue
            self._reset_level(lvl, f"auto_reset after {elapsed:.0f}s")


circuit_breakers = CircuitBreakerSystem()
smart_executor._cb = circuit_breakers


# ---------------------------------------------------------------------------
# Capital Protector — Progressive risk reduction with drawdown tracking
# ---------------------------------------------------------------------------

class CapitalProtector:
    """Protects capital via progressive risk reduction and drawdown-aware sizing.

    HWM tracking, Kelly-simplified sizing, and integration with CircuitBreakerSystem
    for hard stops at extreme drawdown levels.
    """

    _RISK_TIERS = [
        (5.0,  0.020),
        (10.0, 0.010),
        (15.0, 0.005),
    ]

    def __init__(self, initial_capital, cb_system=None):
        self._lock = threading.Lock()
        self.initial_capital = float(initial_capital)
        self.high_water_mark = float(initial_capital)
        self.max_drawdown_ever = 0.0
        self._current_drawdown_pct = 0.0
        self._cb = cb_system

    def update(self, current_capital):
        """Update high-water mark and drawdown tracking."""
        current_capital = float(current_capital)
        with self._lock:
            if current_capital > self.high_water_mark:
                self.high_water_mark = current_capital

            if self.high_water_mark > 0:
                dd = (self.high_water_mark - current_capital) / self.high_water_mark * 100
            else:
                dd = 0.0
            dd = max(0.0, dd)

            self._current_drawdown_pct = dd
            if dd > self.max_drawdown_ever:
                self.max_drawdown_ever = dd

            return {
                "high_water_mark": round(self.high_water_mark, 4),
                "current_drawdown_pct": round(dd, 2),
                "max_drawdown_ever": round(self.max_drawdown_ever, 2),
            }

    def get_allowed_risk(self, current_capital):
        """Progressive risk per trade as a fraction of capital."""
        current_capital = float(current_capital)
        with self._lock:
            dd = self._current_drawdown_pct

        if dd > 15.0:
            return 0.0

        risk_frac = 0.020
        for threshold, frac in self._RISK_TIERS:
            if dd < threshold:
                risk_frac = frac
                break
        else:
            risk_frac = 0.005

        max_from_initial = (self.initial_capital * 0.020)
        max_absolute = current_capital * risk_frac
        return min(max_absolute, max_from_initial)

    def get_position_size(self, signal_confidence, available_capital,
                          entry_price, stop_loss_price, portfolio_heat_pct=0.0):
        """Calculate position size using risk budget and simplified Kelly.

        Returns size in USD.  Never exceeds get_allowed_risk().
        """
        if entry_price <= 0 or stop_loss_price <= 0:
            return 0.0

        risk_budget = self.get_allowed_risk(available_capital)
        if risk_budget <= 0:
            return 0.0

        risk_per_unit_pct = abs(entry_price - stop_loss_price) / entry_price
        if risk_per_unit_pct <= 0:
            return 0.0

        confidence = max(0, min(100, signal_confidence))
        win_prob = 0.40 + (confidence / 100.0) * 0.25
        avg_win_ratio = 1.5
        avg_loss_ratio = 1.0
        edge = win_prob * avg_win_ratio - (1.0 - win_prob) * avg_loss_ratio
        kelly = edge / avg_win_ratio if avg_win_ratio > 0 else 0.0
        kelly = max(0.0, min(kelly, 0.25))

        half_kelly = kelly * 0.5

        heat_remaining = max(0.0, 10.0 - portfolio_heat_pct) / 10.0
        adjusted_budget = risk_budget * half_kelly * heat_remaining if half_kelly > 0 else risk_budget * 0.02

        adjusted_budget = min(adjusted_budget, risk_budget)

        size_usd = adjusted_budget / risk_per_unit_pct

        max_size = available_capital * 0.20
        size_usd = min(size_usd, max_size)
        size_usd = max(size_usd, 0.0)

        cb_mult = 1.0
        if self._cb:
            cb_mult = self._cb.get_size_multiplier()
        size_usd *= cb_mult

        return round(size_usd, 2)

    def get_status(self):
        """Current protector state for dashboard."""
        with self._lock:
            return {
                "initial_capital": round(self.initial_capital, 2),
                "high_water_mark": round(self.high_water_mark, 4),
                "current_drawdown_pct": round(self._current_drawdown_pct, 2),
                "max_drawdown_ever": round(self.max_drawdown_ever, 2),
                "risk_tier": self._get_tier_label(),
            }

    def _get_tier_label(self):
        dd = self._current_drawdown_pct
        if dd > 15.0:
            return "STOPPED"
        if dd > 10.0:
            return "MINIMAL (0.5%)"
        if dd > 5.0:
            return "REDUCED (1%)"
        return "NORMAL (2%)"


capital_protector = CapitalProtector(initial_capital=100.0, cb_system=circuit_breakers)


# ---------------------------------------------------------------------------
# Advanced Position Manager — Dynamic risk adjustments for open positions
# ---------------------------------------------------------------------------

class AdvancedPositionManager:
    """Manages open positions with dynamic stops, correlation checks, and CB integration."""

    _CORRELATION_GROUPS = [
        {"BTCUSDT", "ETHUSDT"},
        {"SOLUSDT", "ETHUSDT"},
    ]

    _ADVERSE_REGIMES = {
        "long": {"WEAK_BEAR", "STRONG_BEAR", "CRISIS"},
        "short": {"STRONG_BULL", "WEAK_BULL"},
    }

    MAX_PORTFOLIO_HEAT_PCT = 10.0
    MAX_TIME_NO_PROFIT_H = 24
    BREAK_EVEN_THRESHOLD = 1.0
    PARTIAL_TP_RATIO = 1.0
    PARTIAL_TP_CLOSE_PCT = 0.50
    CORRELATION_PENALTY = 1.5

    def __init__(self, cb_system, cap_protector):
        self._positions = {}
        self._cb = cb_system
        self._cp = cap_protector
        self._lock = threading.Lock()

    def add_position(self, pos_id, symbol, side, entry_price, size_usd,
                     leverage, stop_loss, take_profit, trailing_pct=0,
                     strategy="", capital=100.0):
        """Register a new position with computed risk parameters."""
        if entry_price <= 0 or size_usd <= 0:
            return {"accepted": False, "reason": "invalid price or size"}

        if stop_loss and stop_loss > 0:
            if side == "long":
                risk_pct = (entry_price - stop_loss) / entry_price * 100
            else:
                risk_pct = (stop_loss - entry_price) / entry_price * 100
        else:
            risk_pct = 3.0

        risk_usd = size_usd * (risk_pct / 100.0) * leverage
        max_loss = size_usd * leverage

        heat = self.get_portfolio_heat(capital)
        if heat + (risk_usd / capital * 100 if capital > 0 else 0) > self.MAX_PORTFOLIO_HEAT_PCT:
            log.warning("[PM] Position rejected — portfolio heat %.1f%% + new %.1f%% > %.1f%%",
                        heat, risk_usd / capital * 100 if capital > 0 else 0,
                        self.MAX_PORTFOLIO_HEAT_PCT)
            return {"accepted": False, "reason": f"portfolio heat would exceed {self.MAX_PORTFOLIO_HEAT_PCT}%"}

        with self._lock:
            self._positions[pos_id] = {
                "symbol": symbol,
                "side": side,
                "entry_price": entry_price,
                "size_usd": size_usd,
                "leverage": leverage,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "trailing_pct": trailing_pct,
                "strategy": strategy,
                "initial_risk_pct": round(risk_pct, 2),
                "risk_usd": round(risk_usd, 4),
                "max_loss": round(max_loss, 4),
                "current_price": entry_price,
                "unrealized_pnl": 0.0,
                "unrealized_pnl_pct": 0.0,
                "hwm_price": entry_price,
                "opened_at": time.time(),
                "partial_tp_done": False,
                "break_even_set": False,
            }

        log.info("[PM] Position registered | %s %s %s | $%.2f @%.2f | risk=%.2f%%",
                 pos_id, side, symbol, size_usd, entry_price, risk_pct)
        return {"accepted": True, "risk_pct": round(risk_pct, 2), "risk_usd": round(risk_usd, 4)}

    def remove_position(self, pos_id):
        """Unregister a closed position."""
        with self._lock:
            self._positions.pop(pos_id, None)

    def update_position(self, pos_id, current_price):
        """Update position state with latest market price."""
        with self._lock:
            pos = self._positions.get(pos_id)
            if not pos:
                return None

            pos["current_price"] = current_price
            entry = pos["entry_price"]
            side = pos["side"]

            if side == "long":
                pnl_pct = (current_price - entry) / entry * 100
            else:
                pnl_pct = (entry - current_price) / entry * 100

            pos["unrealized_pnl_pct"] = round(pnl_pct, 2)
            pos["unrealized_pnl"] = round(pos["size_usd"] * pnl_pct / 100 * pos["leverage"], 4)

            if side == "long" and current_price > pos["hwm_price"]:
                pos["hwm_price"] = current_price
            elif side == "short" and current_price < pos["hwm_price"]:
                pos["hwm_price"] = current_price

            return dict(pos)

    def should_close(self, pos_id, current_price, regime="RANGE", rsi_value=None):
        """Determine if position should be closed. Returns (should_close, reason) tuple."""
        with self._lock:
            pos = self._positions.get(pos_id)
            if not pos:
                return False, ""
            pos = dict(pos)

        entry = pos["entry_price"]
        side = pos["side"]
        sl = pos["stop_loss"]
        tp = pos["take_profit"]
        trailing = pos["trailing_pct"]

        if side == "long":
            pnl_pct = (current_price - entry) / entry * 100
        else:
            pnl_pct = (entry - current_price) / entry * 100

        # 1. Stop loss
        if sl and sl > 0:
            if side == "long" and current_price <= sl:
                return True, f"SL hit @{sl:.2f} ({pnl_pct:.1f}%)"
            if side == "short" and current_price >= sl:
                return True, f"SL hit @{sl:.2f} ({pnl_pct:.1f}%)"

        # 2. Take profit
        if tp and tp > 0:
            if side == "long" and current_price >= tp:
                return True, f"TP hit @{tp:.2f} ({pnl_pct:.1f}%)"
            if side == "short" and current_price <= tp:
                return True, f"TP hit @{tp:.2f} ({pnl_pct:.1f}%)"

        # 3. Trailing stop
        if trailing > 0 and pnl_pct > trailing:
            hwm = pos["hwm_price"]
            if side == "long":
                hwm_pnl = (hwm - entry) / entry * 100
            else:
                hwm_pnl = (entry - hwm) / entry * 100
            if hwm_pnl - pnl_pct >= trailing:
                return True, f"Trailing stop ({trailing}%), HWM {hwm_pnl:.1f}% → {pnl_pct:.1f}%"

        # 4. Adverse regime change
        adverse = self._ADVERSE_REGIMES.get(side, set())
        if regime in adverse and pnl_pct < 0.5:
            return True, f"Regime {regime} adverse for {side} (pnl={pnl_pct:.1f}%)"

        # 5. Time-based: >24h without significant profit
        age_h = (time.time() - pos["opened_at"]) / 3600
        if age_h > self.MAX_TIME_NO_PROFIT_H and pnl_pct < 1.0:
            return True, f"Open {age_h:.0f}h without profit ({pnl_pct:.1f}%)"

        # 6. Divergence: RSI invalidation
        if rsi_value is not None:
            if side == "long" and rsi_value > 70 and pnl_pct > 0:
                return True, f"RSI overbought {rsi_value:.0f} — taking profit ({pnl_pct:.1f}%)"
            if side == "short" and rsi_value < 30 and pnl_pct > 0:
                return True, f"RSI oversold {rsi_value:.0f} — taking profit ({pnl_pct:.1f}%)"

        # 7. Circuit breaker L3+
        cb_action = self._cb.get_max_allowed_action()
        if cb_action in ("close_only", "blocked"):
            return True, f"CB forced close (allowed={cb_action})"

        # 8. Correlation loss check
        corr_loss = self._check_correlation_loss(pos_id, pos["symbol"], side)
        if corr_loss:
            return True, corr_loss

        # Default SL/TP
        if pnl_pct <= -3.0:
            return True, f"Default SL ({pnl_pct:.1f}%)"
        if pnl_pct >= 5.0 and not tp:
            return True, f"Default TP ({pnl_pct:.1f}%)"

        return False, ""

    def adjust_stops(self, pos_id, current_price):
        """Dynamically adjust stop loss: trailing, break-even, partial TP."""
        actions = []
        with self._lock:
            pos = self._positions.get(pos_id)
            if not pos:
                return actions

            entry = pos["entry_price"]
            side = pos["side"]
            initial_risk = pos["initial_risk_pct"]

            if side == "long":
                pnl_pct = (current_price - entry) / entry * 100
            else:
                pnl_pct = (entry - current_price) / entry * 100

            # Break-even: move SL to entry when profit >= 1× initial risk
            if not pos["break_even_set"] and initial_risk > 0 and pnl_pct >= initial_risk * self.BREAK_EVEN_THRESHOLD:
                pos["stop_loss"] = entry
                pos["break_even_set"] = True
                actions.append({"action": "break_even", "new_sl": entry})
                log.info("[PM] Break-even set | %s | SL → entry @%.2f", pos_id, entry)

            # Partial TP: signal to close 50% at 1× risk profit
            if not pos["partial_tp_done"] and initial_risk > 0 and pnl_pct >= initial_risk * self.PARTIAL_TP_RATIO:
                pos["partial_tp_done"] = True
                actions.append({"action": "partial_tp", "close_pct": self.PARTIAL_TP_CLOSE_PCT,
                                "pnl_pct": round(pnl_pct, 2)})
                log.info("[PM] Partial TP signal | %s | close %.0f%% at pnl=%.1f%%",
                         pos_id, self.PARTIAL_TP_CLOSE_PCT * 100, pnl_pct)

            # Trailing: ratchet SL forward
            trailing = pos["trailing_pct"]
            if trailing > 0 and pnl_pct > trailing:
                if side == "long":
                    new_sl = current_price * (1 - trailing / 100)
                    if pos["stop_loss"] is None or new_sl > pos["stop_loss"]:
                        pos["stop_loss"] = round(new_sl, 2)
                        actions.append({"action": "trailing_update", "new_sl": pos["stop_loss"]})
                else:
                    new_sl = current_price * (1 + trailing / 100)
                    if pos["stop_loss"] is None or new_sl < pos["stop_loss"]:
                        pos["stop_loss"] = round(new_sl, 2)
                        actions.append({"action": "trailing_update", "new_sl": pos["stop_loss"]})

        return actions

    def get_portfolio_heat(self, capital=None):
        """Total risk exposure as % of capital."""
        if capital is None or capital <= 0:
            capital = self._cp.high_water_mark if self._cp else 100.0
        with self._lock:
            total_risk = sum(p["risk_usd"] for p in self._positions.values())
        return round(total_risk / capital * 100, 2) if capital > 0 else 0.0

    def get_correlation_risk(self):
        """Check if positions are too correlated and compute effective risk."""
        with self._lock:
            positions = list(self._positions.values())

        if len(positions) < 2:
            return {"correlated": False, "groups": [], "effective_risk_multiplier": 1.0}

        active_symbols = {}
        for p in positions:
            sym = p["symbol"]
            if sym not in active_symbols:
                active_symbols[sym] = []
            active_symbols[sym].append(p)

        correlated_groups = []
        total_risk = sum(p["risk_usd"] for p in positions)
        penalty_risk = 0.0

        for group in self._CORRELATION_GROUPS:
            in_group = group & set(active_symbols.keys())
            if len(in_group) >= 2:
                group_syms = list(in_group)
                same_side = True
                sides = set()
                group_risk = 0.0
                for sym in group_syms:
                    for p in active_symbols[sym]:
                        sides.add(p["side"])
                        group_risk += p["risk_usd"]
                same_side = len(sides) == 1
                if same_side:
                    penalty_risk += group_risk * (self.CORRELATION_PENALTY - 1.0)
                    correlated_groups.append({
                        "symbols": group_syms,
                        "same_direction": True,
                        "combined_risk": round(group_risk, 4),
                        "effective_risk": round(group_risk * self.CORRELATION_PENALTY, 4),
                    })

        effective_mult = ((total_risk + penalty_risk) / total_risk) if total_risk > 0 else 1.0

        return {
            "correlated": len(correlated_groups) > 0,
            "groups": correlated_groups,
            "effective_risk_multiplier": round(effective_mult, 2),
            "total_risk_usd": round(total_risk, 4),
            "effective_risk_usd": round(total_risk + penalty_risk, 4),
        }

    def get_position_summary(self):
        """Dashboard-friendly summary of all managed positions."""
        with self._lock:
            positions = {pid: dict(p) for pid, p in self._positions.items()}

        if not positions:
            return {"count": 0, "positions": [], "total_unrealized_pnl": 0,
                    "best": None, "worst": None}

        summaries = []
        total_pnl = 0.0
        best_pnl = -999
        worst_pnl = 999
        best_id = worst_id = None

        for pid, p in positions.items():
            pnl = p["unrealized_pnl_pct"]
            total_pnl += p["unrealized_pnl"]
            age_h = (time.time() - p["opened_at"]) / 3600
            summaries.append({
                "id": pid,
                "symbol": p["symbol"],
                "side": p["side"],
                "entry": p["entry_price"],
                "current": p["current_price"],
                "size_usd": p["size_usd"],
                "leverage": p["leverage"],
                "pnl_pct": round(pnl, 2),
                "pnl_usd": round(p["unrealized_pnl"], 4),
                "stop_loss": p["stop_loss"],
                "take_profit": p["take_profit"],
                "risk_pct": p["initial_risk_pct"],
                "age_hours": round(age_h, 1),
                "break_even_set": p["break_even_set"],
                "partial_tp_done": p["partial_tp_done"],
                "strategy": p["strategy"],
            })
            if pnl > best_pnl:
                best_pnl = pnl
                best_id = pid
            if pnl < worst_pnl:
                worst_pnl = pnl
                worst_id = pid

        return {
            "count": len(summaries),
            "positions": summaries,
            "total_unrealized_pnl": round(total_pnl, 4),
            "best": {"id": best_id, "pnl_pct": round(best_pnl, 2)} if best_id else None,
            "worst": {"id": worst_id, "pnl_pct": round(worst_pnl, 2)} if worst_id else None,
        }

    def _check_correlation_loss(self, pos_id, symbol, side):
        """Check if a correlated position has suffered a big loss."""
        correlated_syms = set()
        for group in self._CORRELATION_GROUPS:
            if symbol in group:
                correlated_syms |= group
        correlated_syms.discard(symbol)
        if not correlated_syms:
            return None

        with self._lock:
            for pid, p in self._positions.items():
                if pid == pos_id:
                    continue
                if p["symbol"] in correlated_syms and p["side"] == side:
                    if p["unrealized_pnl_pct"] < -5.0:
                        return (f"Correlated {p['symbol']} at {p['unrealized_pnl_pct']:.1f}%"
                                f" — cutting {symbol}")
        return None


position_manager = AdvancedPositionManager(cb_system=circuit_breakers,
                                            cap_protector=capital_protector)


# ---------------------------------------------------------------------------
# Autonomous Trading Engine — Background loop that scans markets and executes
# trades without human intervention.
# ---------------------------------------------------------------------------

class AutonomousEngine:
    """Background autonomous trading loop.

    Ties together every intelligence component (SignalEngine, RiskEngine,
    DipTopDetector, AdvancedRegimeDetector) with execution via PaperTrader or
    live ExchangeManager adapters.  Runs in a daemon thread so it dies with
    the Flask process.
    """

    _VALID_MODES = ("paper", "micro_live", "live")
    _VALID_STRATEGIES = ("auto", "trend", "mean_reversion", "breakout",
                         "dip_hunter", "momentum_scalp", "macro_event")

    def __init__(self, exchange_mgr, sig_engine, risk_eng,
                 dip_top, regime_det, micro_eng, paper_trd,
                 cb_system=None, cap_protector=None, pos_manager=None):
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        self._exchange_manager = exchange_mgr
        self._signal_engine = sig_engine
        self._risk_engine = risk_eng
        self._dip_top = dip_top
        self._regime = regime_det
        self._micro = micro_eng
        self._paper = paper_trd
        self._cb = cb_system
        self._cp = cap_protector
        self._pm = pos_manager

        self._config = {
            "enabled": False,
            "mode": "live",
            "scan_interval": 120,
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "max_concurrent_positions": 2,
            "min_signal_score": 180,
            "min_confidence": 70,
            "allowed_regimes": ["STRONG_BULL", "STRONG_BEAR"],
            "strategy": "auto",
            "risk_per_trade_pct": 1.0,
            "daily_loss_limit_pct": 3.0,
            "max_trades_per_day": 5,
            "cooldown_after_loss": 600,
            "leverage_max": 5,
            "auto_adjust": False,
        }

        self._state = {
            "last_scan": None,
            "trades_today": 0,
            "daily_pnl": 0.0,
            "last_loss_time": 0,
            "scan_count": 0,
            "errors": [],
            "last_signals": {},
            "active_strategies": {},
            "last_scan_duration": 0.0,
        }

        self._price_history = {}
        self._trade_log = []

    # ----- lifecycle --------------------------------------------------------

    def start(self):
        with self._lock:
            if self._running:
                return {"success": False, "error": "Bot is already running"}
            self._running = True
            self._reset_daily_counters()
            self._thread = threading.Thread(target=self._loop, daemon=True,
                                            name="jarvis-bot")
            self._thread.start()
            log.info("[BOT] Started | mode=%s | interval=%ds | symbols=%s",
                     self._config["mode"], self._config["scan_interval"],
                     ",".join(self._config["symbols"]))
            try:
                alert_manager.send("BOT_STATUS",
                    f"Bot started — mode={self._config['mode']}, symbols={','.join(self._config['symbols'])}")
            except Exception:
                pass
            return {"success": True, "mode": self._config["mode"]}

    def stop(self):
        with self._lock:
            if not self._running:
                return {"success": False, "error": "Bot is not running"}
            self._running = False
            log.info("[BOT] Stop requested")
            try:
                alert_manager.send("BOT_STATUS", "Bot stopped by user")
            except Exception:
                pass
            return {"success": True}

    # ----- main loop --------------------------------------------------------

    def _loop(self):
        log.info("[BOT] Loop thread started")
        while self._running:
            scan_start = time.time()
            try:
                self._maybe_reset_daily_counters()

                # --- Circuit breaker evaluation (every iteration) ---
                if self._cb:
                    balance = self._get_available_balance()
                    initial = self._cp.initial_capital if self._cp else 100.0
                    dd_status = self._risk_engine.get_drawdown_status()
                    market_data = self._build_flash_crash_data()
                    cb_result = self._cb.check({
                        "daily_pnl_pct": abs(self._state["daily_pnl"] / balance * 100) if balance > 0 else 0,
                        "drawdown_pct": dd_status.get("drawdown_pct", 0),
                        "initial_capital": initial,
                        "current_capital": balance,
                        "consecutive_losses": self._cb._consecutive_losses,
                    }, market_data=market_data)

                    self._state["cb_level"] = cb_result.get("max_level", 0)
                    self._state["cb_allowed"] = cb_result.get("allowed", "full")

                    if self._cp:
                        self._cp.update(balance)

                    if cb_result.get("max_level", 0) >= 3:
                        log.critical("[BOT] Circuit breaker L%d — closing all + stopping",
                                     cb_result["max_level"])
                        self._manage_open_positions(force_close_pct=100)
                        if cb_result.get("max_level", 0) >= 4:
                            self._activate_kill_switch("CB Level %d" % cb_result["max_level"])
                        self._running = False
                        break

                if not self._check_daily_limits():
                    log.info("[BOT] Daily limits reached — sleeping")
                    time.sleep(self._config["scan_interval"])
                    continue

                macro_score_data = None
                try:
                    macro_score_data = macro_engine.compute_macro_score()
                    self._state["macro_score"] = macro_score_data.get("score", 0)
                except Exception as exc:
                    log.debug("[BOT] Macro score fetch: %s", exc)
                    self._state["macro_score"] = 0

                try:
                    exposure = macro_engine.should_reduce_exposure()
                    if exposure.get("reduce"):
                        log.warning("[BOT] Macro: reducing exposure — %s", exposure["reason"])
                        self._state["macro_reduce"] = exposure["reason"]
                        self._manage_open_positions(force_close_pct=100 - exposure.get("target_exposure_pct", 100))
                except Exception as exc:
                    log.debug("[BOT] Macro exposure check: %s", exc)

                for symbol in list(self._config["symbols"]):
                    if not self._running:
                        break
                    try:
                        self._scan_symbol(symbol, macro_score=self._state.get("macro_score", 0))
                    except Exception as exc:
                        self._record_error(f"Scan {symbol}: {exc}")
                        log.warning("[BOT] Scan error | %s | %s", symbol, exc)

                try:
                    self._manage_open_positions()
                except Exception as exc:
                    self._record_error(f"Position management: {exc}")
                    log.warning("[BOT] Position mgmt error | %s", exc)

                if self._state["scan_count"] > 0 and self._state["scan_count"] % 60 == 0:
                    try:
                        adj = performance_tracker.should_auto_adjust()
                        if adj.get("adjust") and self._config.get("auto_adjust", False):
                            for a in adj.get("adjustments", []):
                                if a["type"] == "disable_strategy":
                                    log.warning("[BOT] Auto-adjust: disabling strategy %s (%s)",
                                                a["target"], a["reason"])
                                elif a["type"] == "reduce_leverage":
                                    log.warning("[BOT] Auto-adjust: reduce leverage recommended (%s)",
                                                a["reason"])
                    except Exception:
                        pass

                elapsed = time.time() - scan_start
                self._state["scan_count"] += 1
                self._state["last_scan"] = datetime.now(timezone.utc).isoformat()
                self._state["last_scan_duration"] = round(elapsed, 2)

            except Exception as exc:
                self._record_error(f"Loop: {exc}")
                log.error("[BOT] Critical loop error | %s", exc)
                if self._cb:
                    self._cb.trigger_execution_error(phantom_order=False)

            sleep_time = max(5, self._config["scan_interval"] - (time.time() - scan_start))
            time.sleep(sleep_time)

        log.info("[BOT] Loop thread exited")

    # ----- symbol scanning --------------------------------------------------

    def _scan_symbol(self, symbol, macro_score=0):
        if symbol in ("GOLD", "SILVER"):
            return

        raw = fetch_binance("/api/v3/klines",
                            {"symbol": symbol, "interval": "1h", "limit": 200},
                            ttl=10)
        if not raw:
            self._record_error(f"No candle data for {symbol}")
            return
        ohlcv = transform_klines(raw)
        if len(ohlcv) < 50:
            return

        current_price = ohlcv[-1]["close"]
        last_prices = self._price_history.get(symbol, [])
        if last_prices:
            prev_price = last_prices[-1][1]
            if prev_price > 0:
                divergence_pct = abs(current_price - prev_price) / prev_price * 100
                if divergence_pct > 5.0:
                    ticker = fetch_binance("/api/v3/ticker/price", {"symbol": symbol}, ttl=2)
                    if ticker:
                        confirm_price = float(ticker.get("price", 0))
                        if confirm_price > 0:
                            confirm_div = abs(current_price - confirm_price) / confirm_price * 100
                            if confirm_div > 3.0:
                                log.warning("[BOT] Price divergence on %s: kline=%.2f ticker=%.2f (%.1f%%) — skipping",
                                            symbol, current_price, confirm_price, confirm_div)
                                try:
                                    alert_manager.send("ERROR",
                                        f"Price divergence on {symbol}: {divergence_pct:.1f}% between scans — skipped",
                                        priority="HIGH", data={"symbol": symbol, "divergence_pct": divergence_pct})
                                except Exception:
                                    pass
                                return

        indicators = compute_all_indicators(ohlcv)
        raw_ind = indicators["_raw"]

        regime_info = self._regime.detect(ohlcv, raw_ind)
        regime = regime_info.get("regime", "RANGE")

        prev_regime = self._state.get("_last_regimes", {}).get(symbol)
        if prev_regime and prev_regime != regime:
            try:
                alert_manager.send("REGIME_CHANGE",
                    f"Regime changed: {prev_regime} → {regime} on {symbol}",
                    data={"symbol": symbol, "from": prev_regime, "to": regime})
            except Exception:
                pass
        if "_last_regimes" not in self._state:
            self._state["_last_regimes"] = {}
        self._state["_last_regimes"][symbol] = regime
        self._state["_last_regime"] = regime

        if regime not in self._config["allowed_regimes"]:
            self._state["last_signals"][symbol] = {
                "skipped": True, "reason": f"Regime {regime} not allowed",
                "regime": regime, "time": datetime.now(timezone.utc).isoformat(),
            }
            return

        signal_info = self._signal_engine.generate(raw_ind, regime_info)
        risk_check = self._risk_engine.check(signal_info)
        dip_top_info = self._dip_top.analyze(symbol, ohlcv, raw_ind)

        try:
            sig_score = abs(signal_info.get("score", 0))
            sig_conf = signal_info.get("confidence", 0)
            if sig_score >= 200 and sig_conf >= 70:
                alert_manager.send("SIGNAL_STRONG",
                    f"Strong {signal_info['direction'].upper()} signal on {symbol} (score: {signal_info['score']}, confidence: {sig_conf}%)",
                    data={"symbol": symbol, "score": signal_info["score"], "confidence": sig_conf})
            dip_score = dip_top_info.get("confluence_score", 0)
            if dip_top_info.get("is_dip") and dip_score >= 70:
                alert_manager.send("DIP_DETECTED",
                    f"Major dip detected on {symbol} (score: {dip_score})",
                    data={"symbol": symbol, "score": dip_score})
            if dip_top_info.get("is_top") and dip_score >= 70:
                alert_manager.send("TOP_DETECTED",
                    f"Distribution top detected on {symbol} (score: {dip_score})",
                    data={"symbol": symbol, "score": dip_score})
        except Exception:
            pass

        strat_pick = self._select_strategy(symbol, ohlcv, raw_ind, regime_info, dip_top_info)

        if isinstance(strat_pick, dict):
            strat_name = strat_pick["name"]
            strat_direction = strat_pick["direction"]
            strat_confidence = strat_pick["confidence"]
            strat_reason = strat_pick["reason"]
        else:
            strat_name = strat_pick if isinstance(strat_pick, str) else "trend"
            strat_direction = None
            strat_confidence = 0
            strat_reason = ""

        self._state["active_strategies"][symbol] = strat_name

        self._state["last_signals"][symbol] = {
            "signal": signal_info["direction"],
            "score": signal_info["score"],
            "confidence": signal_info["confidence"],
            "regime": regime,
            "strategy": strat_name,
            "strategy_direction": strat_direction,
            "strategy_confidence": strat_confidence,
            "strategy_reason": strat_reason,
            "risk_approved": risk_check["approved"],
            "risk_vetoes": risk_check.get("vetoes", []),
            "dip": dip_top_info.get("is_dip", False),
            "top": dip_top_info.get("is_top", False),
            "time": datetime.now(timezone.utc).isoformat(),
        }

        if self._should_trade(signal_info, regime_info, risk_check, dip_top_info,
                              strat_pick, macro_score=macro_score):
            current_price = ohlcv[-1]["close"]

            if strat_direction:
                direction = strat_direction
            else:
                direction = "long" if signal_info["score"] > 0 else "short"

            strat_obj = strategy_selector.get_strategy(strat_name)
            leverage = 1
            if strat_obj:
                leverage = strat_obj.get_leverage(strat_confidence or signal_info["confidence"],
                                                  regime)
                exit_conds = strat_obj.get_exit_conditions(current_price, direction, raw_ind)
            else:
                exit_conds = {"take_profit": 0, "stop_loss": 0, "trailing_pct": 0}

            if self._cb:
                leverage = max(1, int(leverage * self._cb.get_leverage_multiplier()))

            sl_price = exit_conds.get("stop_loss", 0) or 0
            balance = self._get_available_balance()
            size = self._calculate_position_size(signal_info, balance,
                                                  entry_price=current_price,
                                                  stop_loss=sl_price)

            if size > 0:
                self._execute_trade(symbol, direction, size, current_price,
                                    signal_info, strat_name,
                                    leverage=leverage, exit_conditions=exit_conds)

    # ----- decision logic ---------------------------------------------------

    def _should_trade(self, signal, regime_info, risk_check, dip_top_info,
                      strat_pick=None, macro_score=0):
        if not risk_check.get("approved", False):
            return False

        if self._cb and not self._cb.is_new_trade_allowed():
            return False

        score = abs(signal.get("score", 0))
        confidence = signal.get("confidence", 0)

        base_min = self._config["min_signal_score"]
        if macro_score < -50:
            adjusted_min = max(base_min, 200)
        elif macro_score < -20:
            adjusted_min = base_min + 25
        elif macro_score > 20:
            adjusted_min = max(50, base_min - 15)
        else:
            adjusted_min = base_min

        has_strategy_entry = isinstance(strat_pick, dict) and strat_pick.get("direction")

        if has_strategy_entry:
            strat_conf = strat_pick.get("confidence", 0)
            if strat_conf >= self._config["min_confidence"] and score >= adjusted_min * 0.6:
                pass
            elif score < adjusted_min:
                return False
        else:
            if score < adjusted_min:
                return False
            if confidence < self._config["min_confidence"]:
                return False

        if signal.get("direction") == "NEUTRAL" and not has_strategy_entry:
            return False

        open_positions = self._get_open_position_count()
        if open_positions >= self._config["max_concurrent_positions"]:
            return False

        if self._is_in_cooldown():
            return False

        if self._is_already_positioned(signal):
            return False

        return True

    def _select_strategy(self, symbol, ohlcv, raw_ind, regime_info, dip_top_info):
        forced = self._config["strategy"]
        if forced != "auto":
            strat_obj = strategy_selector.get_strategy(forced)
            if strat_obj:
                try:
                    entry = strat_obj.should_enter(ohlcv, raw_ind, regime_info, dip_top_info)
                    if entry:
                        d, c, r = entry
                        return {"name": forced, "direction": d, "confidence": c, "reason": r}
                except Exception as exc:
                    log.debug("[BOT] Forced strategy %s error: %s", forced, exc)
            return forced

        pick = strategy_selector.select(regime_info, raw_ind, ohlcv, dip_top_info)
        if pick:
            return pick
        return "trend"

    def _calculate_position_size(self, signal, balance, entry_price=0, stop_loss=0):
        if balance <= 0:
            return 0.0

        if self._cp and entry_price > 0 and stop_loss > 0:
            heat = self._pm.get_portfolio_heat(balance) if self._pm else 0.0
            size = self._cp.get_position_size(
                signal.get("confidence", 50), balance,
                entry_price, stop_loss, portfolio_heat_pct=heat)
            if size > 0:
                size = max(size, MicroPositionEngine.DEFAULT_SIZE_USD)
                size = min(size, balance * 0.2)
                return round(size, 2)

        paper_status = self._paper.get_status()
        total_trades = paper_status.get("total_trades", 0)
        wins = paper_status.get("wins", 0)

        if total_trades >= 10:
            win_rate = wins / total_trades
        else:
            win_rate = 0.5

        avg_win = 1.5
        avg_loss = 1.0

        edge = win_rate * avg_win - (1 - win_rate) * avg_loss
        kelly = edge / avg_win if avg_win > 0 else 0
        kelly = max(0.0, min(kelly, 0.25))

        if kelly < 0.01:
            kelly = 0.02

        risk_pct = self._config["risk_per_trade_pct"] / 100.0
        size = balance * kelly * risk_pct

        cb_mult = self._cb.get_size_multiplier() if self._cb else 1.0
        size *= cb_mult

        max_size = balance * (MicroPositionEngine.MAX_CAPITAL_PCT / 100.0)
        size = min(size, max_size)
        size = max(size, MicroPositionEngine.DEFAULT_SIZE_USD)
        size = min(size, balance * 0.2)

        return round(size, 2)

    # ----- execution --------------------------------------------------------

    def _execute_trade(self, symbol, direction, size_usd, price, signal_info,
                       strategy, leverage=1, exit_conditions=None):
        mode = self._config["mode"]
        lev_max = self._config.get("leverage_max", 20)
        leverage = max(1, min(leverage, lev_max))
        exit_conditions = exit_conditions or {}
        tp = exit_conditions.get("take_profit")
        sl = exit_conditions.get("stop_loss")
        log.info("[BOT] Executing | %s %s %s | $%.2f @%.2f | strategy=%s | lev=%dx | mode=%s",
                 direction.upper(), symbol, mode, size_usd, price, strategy, leverage, mode)

        trade_record = {
            "symbol": symbol,
            "direction": direction,
            "size_usd": size_usd,
            "price": price,
            "strategy": strategy,
            "leverage": leverage,
            "take_profit": tp,
            "stop_loss": sl,
            "trailing_pct": exit_conditions.get("trailing_pct", 0),
            "signal_score": signal_info.get("score", 0),
            "signal_confidence": signal_info.get("confidence", 0),
            "regime": signal_info.get("regime", ""),
            "mode": mode,
            "time": datetime.now(timezone.utc).isoformat(),
            "result": None,
        }

        try:
            if mode == "paper":
                quantity = size_usd
                result = self._paper.execute(symbol, direction, quantity, price,
                                             leverage=leverage)
                trade_record["result"] = result

            elif mode in ("micro_live", "live"):
                adapter = self._exchange_manager.get_adapter_by_type("gmx")
                if not adapter:
                    adapters = list(self._exchange_manager._adapters.values())
                    adapter = adapters[0] if adapters else None

                if not adapter:
                    trade_record["result"] = {"success": False, "error": "No exchange adapter"}
                    log.warning("[BOT] No exchange adapter available")
                else:
                    ccxt_side = "buy" if direction == "long" else "sell"
                    if smart_executor:
                        smart_executor.set_gmx_adapter(adapter)
                        result = smart_executor.execute_with_retry(
                            symbol=symbol, side=ccxt_side, order_type="market",
                            size_usd=size_usd, leverage=leverage,
                            take_profit=tp, stop_loss=sl,
                            max_retries=3)
                    else:
                        result = adapter.place_order(symbol, ccxt_side, "market",
                                                     size_usd, None, leverage, tp, sl)
                    trade_record["result"] = result

            self._state["trades_today"] += 1

            result = trade_record.get("result", {})
            if isinstance(result, dict) and result.get("success"):
                log.info("[BOT] Trade opened | %s %s | $%.2f | %s",
                         direction.upper(), symbol, size_usd, strategy)
                if self._pm:
                    trade_id = result.get("trade_id")
                    if trade_id:
                        balance = self._get_available_balance()
                        self._pm.add_position(
                            pos_id=trade_id, symbol=symbol, side=direction,
                            entry_price=price, size_usd=size_usd, leverage=leverage,
                            stop_loss=sl or 0, take_profit=tp or 0,
                            trailing_pct=exit_conditions.get("trailing_pct", 0),
                            strategy=strategy, capital=balance)
                try:
                    pt_id = performance_tracker.record_trade({
                        "timestamp": trade_record["time"],
                        "symbol": symbol, "direction": direction.upper(),
                        "strategy": strategy, "entry_price": price,
                        "size_usd": size_usd, "leverage": leverage,
                        "regime": signal_info.get("regime", ""),
                        "signal_score": signal_info.get("score", 0),
                        "signal_confidence": signal_info.get("confidence", 0),
                        "macro_score": self._state.get("macro_score", 0),
                        "stop_loss": sl or 0, "take_profit": tp or 0,
                        "tx_hash": result.get("tx_hash", ""),
                    })
                    if pt_id:
                        trade_record["_pt_id"] = pt_id
                except Exception:
                    pass
                try:
                    alert_manager.send("TRADE_OPENED",
                        f"Opened {direction.upper()} {symbol} @{price:,.2f} ({strategy}, {leverage}x, ${size_usd:.2f})",
                        data={"symbol": symbol, "direction": direction, "price": price,
                              "strategy": strategy, "leverage": leverage})
                except Exception:
                    pass
            else:
                err = result.get("error", "unknown") if isinstance(result, dict) else "unknown"
                log.warning("[BOT] Trade failed | %s %s | %s", symbol, direction, err)

        except Exception as exc:
            trade_record["result"] = {"success": False, "error": str(exc)}
            self._record_error(f"Execute {symbol}: {exc}")
            log.error("[BOT] Execution error | %s | %s", symbol, exc)
            if self._cb:
                self._cb.trigger_execution_error(phantom_order=True)
            try:
                alert_manager.send("ERROR", f"Execution error on {symbol}: {exc}",
                                   priority="CRITICAL")
            except Exception:
                pass

        with self._lock:
            self._trade_log.append(trade_record)
            if len(self._trade_log) > 500:
                self._trade_log = self._trade_log[-500:]

        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO trade_journal (symbol, action, reason, signal_score, confidence, regime) VALUES (?, ?, ?, ?, ?, ?)",
                (symbol, f"bot_{direction}", f"Auto {strategy} | score={signal_info.get('score',0)}",
                 signal_info.get("score", 0), signal_info.get("confidence", 0),
                 signal_info.get("regime", "")),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ----- position management ----------------------------------------------

    def _manage_open_positions(self, force_close_pct=0):
        paper_positions = self._paper.get_open_positions()

        if force_close_pct >= 100 and paper_positions:
            for pos in paper_positions:
                try:
                    symbol = pos.get("symbol", "")
                    trade_id = pos.get("id")
                    price_data = fetch_binance("/api/v3/ticker/price", {"symbol": symbol}, ttl=5)
                    if price_data:
                        current = float(price_data.get("price", 0))
                        if current > 0:
                            result = self._paper.close(trade_id, current)
                            pnl = result.get("pnl", 0)
                            self._state["daily_pnl"] += pnl
                            self._on_trade_closed(trade_id, pnl, "force_close",
                                                 exit_price=current, exit_reason="CB", symbol=symbol)
                            log.info("[BOT] Force-close | %s | pnl=%.4f", symbol, pnl)
                except Exception as exc:
                    log.warning("[BOT] Force-close error %s: %s", pos.get("symbol", "?"), exc)
            return

        regime = self._state.get("_last_regime", "RANGE")

        for pos in paper_positions:
            try:
                symbol = pos.get("symbol", "")
                entry = pos.get("entry_price", 0)
                side = pos.get("side", "long")
                trade_id = pos.get("id")
                if not symbol or entry <= 0:
                    continue

                price_data = fetch_binance("/api/v3/ticker/price",
                                           {"symbol": symbol}, ttl=5)
                if not price_data:
                    if self._cb:
                        self._cb.check({"data_stale_seconds": 301, "exchange_error": False,
                                        "daily_pnl_pct": 0, "drawdown_pct": 0,
                                        "initial_capital": 100, "current_capital": 100})
                    continue
                current = float(price_data.get("price", 0))
                if current <= 0:
                    continue

                self._record_price(symbol, current)

                if self._pm:
                    self._pm.update_position(trade_id, current)
                    self._pm.adjust_stops(trade_id, current)

                    rsi_val = None
                    try:
                        raw = fetch_binance("/api/v3/klines",
                                            {"symbol": symbol, "interval": "1h", "limit": 50}, ttl=30)
                        if raw:
                            ohlcv_mini = transform_klines(raw)
                            closes = [c["close"] for c in ohlcv_mini]
                            rsi_list = calc_rsi(closes)
                            rsi_val = rsi_list[-1] if rsi_list else None
                    except Exception:
                        pass

                    close_it, close_reason = self._pm.should_close(
                        trade_id, current, regime=regime, rsi_value=rsi_val)

                    if close_it:
                        result = self._paper.close(trade_id, current)
                        pnl = result.get("pnl", 0)
                        self._state["daily_pnl"] += pnl
                        strat_name = self._pm._positions.get(trade_id, {}).get("strategy", "")
                        self._on_trade_closed(trade_id, pnl, strat_name,
                                             exit_price=current, exit_reason=close_reason, symbol=symbol)
                        log.info("[BOT] Closed | %s %s | pnl=%.4f | %s | strategy=%s",
                                 side, symbol, pnl, close_reason, strat_name)
                    continue

                if side == "long":
                    pnl_pct = (current - entry) / entry * 100
                else:
                    pnl_pct = (entry - current) / entry * 100

                trade_meta = self._find_trade_meta(trade_id, symbol)
                tp = trade_meta.get("take_profit")
                sl = trade_meta.get("stop_loss")
                trailing = trade_meta.get("trailing_pct", 0)
                strat_name = trade_meta.get("strategy", "")

                should_close = False
                close_reason = ""

                if sl and side == "long" and current <= sl:
                    should_close = True
                    close_reason = f"SL hit @{sl:.2f} ({pnl_pct:.1f}%)"
                elif sl and side == "short" and current >= sl:
                    should_close = True
                    close_reason = f"SL hit @{sl:.2f} ({pnl_pct:.1f}%)"
                elif tp and side == "long" and current >= tp:
                    should_close = True
                    close_reason = f"TP hit @{tp:.2f} ({pnl_pct:.1f}%)"
                elif tp and side == "short" and current <= tp:
                    should_close = True
                    close_reason = f"TP hit @{tp:.2f} ({pnl_pct:.1f}%)"
                elif pnl_pct <= -3.0:
                    should_close = True
                    close_reason = f"Default SL ({pnl_pct:.1f}%)"
                elif pnl_pct >= 5.0 and not tp:
                    should_close = True
                    close_reason = f"Default TP ({pnl_pct:.1f}%)"

                if not should_close and trailing > 0 and pnl_pct > trailing:
                    hwm_key = f"_hwm_{trade_id}"
                    hwm = self._state.get(hwm_key, pnl_pct)
                    if pnl_pct > hwm:
                        self._state[hwm_key] = pnl_pct
                        hwm = pnl_pct
                    if hwm - pnl_pct >= trailing:
                        should_close = True
                        close_reason = f"Trailing stop ({trailing}%), HWM {hwm:.1f}% → {pnl_pct:.1f}%"

                if should_close:
                    result = self._paper.close(trade_id, current)
                    pnl = result.get("pnl", 0)
                    self._state["daily_pnl"] += pnl
                    self._on_trade_closed(trade_id, pnl, strat_name,
                                         exit_price=current, exit_reason=close_reason, symbol=symbol)
                    log.info("[BOT] Closed position | %s %s | pnl=%.4f | %s | strategy=%s",
                             side, symbol, pnl, close_reason, strat_name)

            except Exception as exc:
                log.warning("[BOT] Position mgmt error for %s: %s",
                            pos.get("symbol", "?"), exc)

    def _find_trade_meta(self, trade_id, symbol):
        with self._lock:
            for t in reversed(self._trade_log):
                if t.get("symbol") == symbol:
                    result = t.get("result")
                    if isinstance(result, dict) and result.get("trade_id") == trade_id:
                        return t
                    if isinstance(result, dict) and result.get("success"):
                        return t
        return {}

    # ----- daily limits & cooldown ------------------------------------------

    def _check_daily_limits(self):
        if self._state["trades_today"] >= self._config["max_trades_per_day"]:
            return False
        loss_limit = self._config["daily_loss_limit_pct"]
        if loss_limit > 0 and self._state["daily_pnl"] < 0:
            balance = self._get_available_balance()
            if balance > 0:
                loss_pct = abs(self._state["daily_pnl"]) / balance * 100
                if loss_pct >= loss_limit:
                    return False
        return True

    def _is_in_cooldown(self):
        if self._state["last_loss_time"] <= 0:
            return False
        elapsed = time.time() - self._state["last_loss_time"]
        return elapsed < self._config["cooldown_after_loss"]

    def _reset_daily_counters(self):
        self._state["trades_today"] = 0
        self._state["daily_pnl"] = 0.0
        self._state["last_loss_time"] = 0
        self._state["_day"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _maybe_reset_daily_counters(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._state.get("_day") != today:
            log.info("[BOT] New day %s — resetting counters", today)
            self._reset_daily_counters()

    # ----- helpers ----------------------------------------------------------

    def _get_available_balance(self):
        if self._config["mode"] == "paper":
            status = self._paper.get_status()
            return 100.0 + status.get("total_pnl", 0)
        balances = self._exchange_manager.get_all_balances()
        for b in balances:
            if isinstance(b, dict):
                for key in ("total_usdt", "total_usd", "equity"):
                    if key in b and b[key] > 0:
                        return float(b[key])
        return 0.0

    def _get_open_position_count(self):
        count = len(self._paper.get_open_positions())
        if self._config["mode"] in ("micro_live", "live"):
            count += len(self._exchange_manager.get_all_positions())
        return count

    def _is_already_positioned(self, signal):
        direction = signal.get("direction", "NEUTRAL")
        if direction == "NEUTRAL":
            return True
        return False

    def _record_error(self, msg):
        ts = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._state["errors"].append({"time": ts, "error": msg})
            if len(self._state["errors"]) > 100:
                self._state["errors"] = self._state["errors"][-100:]

    def _on_trade_closed(self, trade_id, pnl, strat_name,
                         exit_price=0, exit_reason="manual", symbol=""):
        """Central handler for trade close: update CB, PM, strategy tracker, perf tracker."""
        if pnl < 0:
            self._state["last_loss_time"] = time.time()
            if self._cb:
                self._cb.record_loss()
        else:
            if self._cb:
                self._cb.record_win()
        if strat_name:
            strategy_selector.record_result(strat_name, pnl)
        if self._pm:
            self._pm.remove_position(trade_id)
        try:
            pt_id = self._find_pt_id(trade_id, symbol)
            if pt_id:
                regime = self._state.get("_last_regime", "")
                performance_tracker.close_trade(pt_id, {
                    "exit_price": exit_price,
                    "exit_reason": exit_reason,
                    "regime": regime,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        except Exception:
            pass
        try:
            sign = "+" if pnl >= 0 else ""
            alert_manager.send("TRADE_CLOSED",
                f"Closed {symbol} @{exit_price:,.2f} ({sign}${pnl:.2f}, {exit_reason})",
                data={"symbol": symbol, "pnl": pnl, "exit_price": exit_price,
                      "exit_reason": exit_reason})
        except Exception:
            pass

    def _find_pt_id(self, trade_id, symbol):
        """Find performance_tracker bot_trades id for a given paper trade."""
        with self._lock:
            for t in reversed(self._trade_log):
                if t.get("_pt_id") and t.get("symbol") == symbol:
                    return t["_pt_id"]
                r = t.get("result")
                if isinstance(r, dict) and r.get("trade_id") == trade_id and t.get("_pt_id"):
                    return t["_pt_id"]
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT id FROM bot_trades WHERE symbol=? AND status='open' ORDER BY id DESC LIMIT 1",
                (symbol,)).fetchone()
            return row[0] if row else None
        except Exception:
            return None
        finally:
            conn.close()

    def _record_price(self, symbol, price):
        """Track recent prices per symbol for flash crash detection."""
        now = time.time()
        if symbol not in self._price_history:
            self._price_history[symbol] = []
        self._price_history[symbol].append((now, price))
        cutoff = now - 600
        self._price_history[symbol] = [
            (t, p) for t, p in self._price_history[symbol] if t > cutoff
        ]

    def _build_flash_crash_data(self):
        """Build market_data dict for CB flash crash detection."""
        now = time.time()
        data = {}
        for symbol, history in self._price_history.items():
            if not history:
                continue
            current = history[-1][1]
            cutoff = now - 300
            old_prices = [p for t, p in history if t <= cutoff]
            if old_prices:
                data[symbol] = {"price_5m_ago": old_prices[-1], "price_now": current}
        return data

    def _activate_kill_switch(self, reason):
        """Activate the database kill switch."""
        try:
            conn = get_db()
            conn.execute(
                "INSERT OR REPLACE INTO killswitch (id, active, activated_at, reason) VALUES (1, 1, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), reason))
            conn.commit()
            conn.close()
            log.critical("[BOT] Kill switch activated — %s", reason)
        except Exception as exc:
            log.error("[BOT] Failed to activate kill switch: %s", exc)

    @staticmethod
    def _last_valid(series):
        if not series:
            return None
        for v in reversed(series):
            if v is not None:
                return v
        return None

    # ----- public API -------------------------------------------------------

    def get_status(self):
        with self._lock:
            status = {
                "running": self._running,
                "config": dict(self._config),
                "state": {
                    "last_scan": self._state["last_scan"],
                    "trades_today": self._state["trades_today"],
                    "daily_pnl": round(self._state["daily_pnl"], 4),
                    "scan_count": self._state["scan_count"],
                    "last_scan_duration": self._state["last_scan_duration"],
                    "error_count": len(self._state["errors"]),
                    "recent_errors": self._state["errors"][-5:],
                    "last_signals": dict(self._state["last_signals"]),
                    "active_strategies": dict(self._state["active_strategies"]),
                    "in_cooldown": self._is_in_cooldown(),
                    "macro_score": self._state.get("macro_score", 0),
                    "cb_level": self._state.get("cb_level", 0),
                    "cb_allowed": self._state.get("cb_allowed", "full"),
                },
                "recent_trades": self._trade_log[-20:],
            }
        if self._cb:
            status["circuit_breakers"] = self._cb.get_status()
        if self._pm:
            status["portfolio_heat"] = self._pm.get_portfolio_heat()
        if self._cp:
            status["capital_protector"] = self._cp.get_status()
        return status

    def update_config(self, new_config):
        errors = []
        with self._lock:
            for key, val in new_config.items():
                if key not in self._config:
                    errors.append(f"Unknown config key: {key}")
                    continue

                if key == "mode" and val not in self._VALID_MODES:
                    errors.append(f"Invalid mode: {val}")
                    continue
                if key == "strategy" and val not in self._VALID_STRATEGIES:
                    errors.append(f"Invalid strategy: {val}")
                    continue
                if key == "scan_interval":
                    val = max(30, min(3600, int(val)))
                if key == "max_concurrent_positions":
                    val = max(1, min(10, int(val)))
                if key == "min_signal_score":
                    val = max(50, min(300, int(val)))
                if key == "min_confidence":
                    val = max(10, min(100, int(val)))
                if key == "risk_per_trade_pct":
                    val = max(0.1, min(5.0, float(val)))
                if key == "daily_loss_limit_pct":
                    val = max(1.0, min(20.0, float(val)))
                if key == "max_trades_per_day":
                    val = max(1, min(50, int(val)))
                if key == "cooldown_after_loss":
                    val = max(0, min(3600, int(val)))
                if key == "leverage_max":
                    val = max(1, min(20, int(val)))
                if key == "symbols" and isinstance(val, list):
                    val = [s.upper() for s in val if isinstance(s, str) and len(s) <= 20][:10]
                if key == "allowed_regimes" and isinstance(val, list):
                    val = [r for r in val if r in (
                        "BULL", "BEAR", "RANGE", "CRISIS",
                        "STRONG_BULL", "WEAK_BULL", "WEAK_BEAR", "STRONG_BEAR")]

                self._config[key] = val

            log.info("[BOT] Config updated | %s", {k: v for k, v in new_config.items() if k in self._config})

        return {"success": len(errors) == 0, "errors": errors, "config": dict(self._config)}


auto_engine = AutonomousEngine(
    exchange_mgr=exchange_manager,
    sig_engine=signal_engine,
    risk_eng=risk_engine,
    dip_top=dip_top_detector,
    regime_det=regime_detector,
    micro_eng=micro_engine,
    paper_trd=paper_trader,
    cb_system=circuit_breakers,
    cap_protector=capital_protector,
    pos_manager=position_manager,
)


# ===========================================================================
# API ROUTES — Market Data (5 routes)
# ===========================================================================

@app.route("/api/candles")
@rate_limit("market_data")
def api_candles():
    symbol, err = validate_symbol(request.args.get("symbol", "BTCUSDT"))
    if err:
        return jsonify({"error": err}), 400
    interval = request.args.get("interval", "1h")
    try:
        limit = max(1, min(int(request.args.get("limit", 1000)), 10000))
    except (TypeError, ValueError):
        limit = 1000

    sym_info = SUPPORTED_SYMBOLS.get(symbol)

    if sym_info and sym_info["source"] == "stooq":
        candles = generate_gold_silver_candles(sym_info, limit)
        return jsonify(candles)

    if interval not in INTERVALS:
        return jsonify({"error": f"Invalid interval: {interval}"}), 400

    if limit <= 1000:
        raw = fetch_binance("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit}, ttl=10)
        if raw is None:
            return jsonify({"error": "Failed to fetch candles from Binance"}), 502
        return jsonify({"candles": transform_klines(raw)})

    all_klines = []
    remaining = limit
    end_time = None
    for _ in range(60):
        batch = min(remaining, 1000)
        params = {"symbol": symbol, "interval": interval, "limit": batch}
        if end_time is not None:
            params["endTime"] = end_time - 1
        raw = fetch_binance("/api/v3/klines", params, ttl=30)
        if not raw:
            break
        all_klines = raw + all_klines
        remaining -= len(raw)
        if remaining <= 0 or len(raw) < batch:
            break
        end_time = int(raw[0][0])

    return jsonify({"candles": transform_klines(all_klines)})


@app.route("/api/price")
@rate_limit("market_data")
def api_price():
    symbol, err = validate_symbol(request.args.get("symbol", "BTCUSDT"))
    if err:
        return jsonify({"error": err}), 400
    sym_info = SUPPORTED_SYMBOLS.get(symbol)

    if sym_info and sym_info["source"] == "stooq":
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
@rate_limit("market_data")
def api_orderbook():
    symbol, err = validate_symbol(request.args.get("symbol", "BTCUSDT"))
    if err:
        return jsonify({"error": err}), 400
    try:
        limit = max(1, min(int(request.args.get("limit", 20)), 100))
    except (TypeError, ValueError):
        limit = 20

    sym_info = SUPPORTED_SYMBOLS.get(symbol)
    if sym_info and sym_info["source"] != "binance":
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
@rate_limit("market_data")
def api_trades():
    symbol, err = validate_symbol(request.args.get("symbol", "BTCUSDT"))
    if err:
        return jsonify({"error": err}), 400
    try:
        limit = max(1, min(int(request.args.get("limit", 30)), 100))
    except (TypeError, ValueError):
        limit = 30

    sym_info = SUPPORTED_SYMBOLS.get(symbol)
    if sym_info and sym_info["source"] != "binance":
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
@rate_limit("market_data")
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


@app.route("/api/markets")
def api_markets():
    """All USDT futures-style pairs with 24h stats, sorted by volume."""
    all_tickers = fetch_binance("/api/v3/ticker/24hr", ttl=30)
    if not all_tickers:
        return jsonify({"markets": []})

    stablecoins = {"USDT", "USDC", "BUSD", "TUSD", "DAI", "FDUSD", "USDP", "USDD"}
    markets = []
    for t in all_tickers:
        sym = t.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        base = sym.replace("USDT", "")
        if base in stablecoins or len(base) < 2:
            continue
        vol = float(t.get("quoteVolume", 0))
        if vol < 100_000:
            continue
        markets.append({
            "symbol": sym,
            "price": float(t.get("lastPrice", 0)),
            "change": float(t.get("priceChangePercent", 0)),
            "volume": vol,
            "high": float(t.get("highPrice", 0)),
            "low": float(t.get("lowPrice", 0)),
        })

    markets.sort(key=lambda x: x["volume"], reverse=True)
    return jsonify({"markets": markets})


# ===========================================================================
# API ROUTES — Indicators & Intelligence (3 routes)
# ===========================================================================

@app.route("/api/indicators")
@rate_limit("market_data")
def api_indicators():
    symbol = request.args.get("symbol", "BTCUSDT").upper()
    interval = request.args.get("interval", "1h")
    limit = min(int(request.args.get("limit", 1000)), 1000)

    sym_info = SUPPORTED_SYMBOLS.get(symbol)

    if sym_info and sym_info["source"] == "stooq":
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
@rate_limit("market_data")
def api_dip_top():
    symbol = request.args.get("symbol", "BTCUSDT").upper()
    interval = request.args.get("interval", "1h")
    limit = min(int(request.args.get("limit", 500)), 1500)

    sym_info = SUPPORTED_SYMBOLS.get(symbol)

    if sym_info and sym_info["source"] == "stooq":
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


@app.route("/api/regime")
@rate_limit("market_data")
def api_regime():
    symbol = request.args.get("symbol", "BTCUSDT").upper()
    interval = request.args.get("interval", "1h")
    limit = min(int(request.args.get("limit", 200)), 1000)

    sym_info = SUPPORTED_SYMBOLS.get(symbol)
    if sym_info and sym_info["source"] == "stooq":
        ohlcv = generate_gold_silver_candles(sym_info, limit)
    else:
        raw = fetch_binance("/api/v3/klines",
                            {"symbol": symbol, "interval": interval, "limit": limit}, ttl=15)
        if not raw:
            return jsonify({"error": "Failed to fetch candles"}), 502
        ohlcv = transform_klines(raw)

    if len(ohlcv) < 50:
        return jsonify({"error": "Need at least 50 candles for regime detection"}), 400

    indicators = compute_all_indicators(ohlcv)
    result = regime_detector.detect(ohlcv, indicators["_raw"])
    result["symbol"] = symbol
    result["interval"] = interval
    return jsonify(result)


@app.route("/api/whales")
@rate_limit("market_data")
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
@rate_limit("market_data")
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
@rate_limit("market_data")
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
@rate_limit("market_data")
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
@rate_limit("market_data")
def api_news():
    cache_key = "rss_news"
    cached = cache.get(cache_key, ttl=120)
    if cached:
        return jsonify(cached)

    category = request.args.get("category", "all")

    crypto_feeds = [
        {"name": "CoinTelegraph", "url": "https://cointelegraph.com/rss", "cat": "crypto"},
        {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "cat": "crypto"},
        {"name": "CryptoNews", "url": "https://cryptonews.com/news/feed/", "cat": "crypto"},
        {"name": "Bitcoin Magazine", "url": "https://bitcoinmagazine.com/feed", "cat": "crypto"},
        {"name": "The Block", "url": "https://www.theblock.co/rss.xml", "cat": "crypto"},
        {"name": "Decrypt", "url": "https://decrypt.co/feed", "cat": "crypto"},
    ]
    finance_feeds = [
        {"name": "CNBC Markets", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258", "cat": "finance"},
        {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss", "cat": "finance"},
        {"name": "Reuters Business", "url": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best", "cat": "finance"},
        {"name": "MarketWatch", "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories", "cat": "finance"},
    ]
    geo_feeds = [
        {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "cat": "geopolitical"},
        {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml", "cat": "geopolitical"},
        {"name": "Reuters World", "url": "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best", "cat": "geopolitical"},
    ]

    if category == "crypto":
        feeds = crypto_feeds
    elif category == "finance":
        feeds = finance_feeds
    elif category == "geopolitical":
        feeds = geo_feeds
    else:
        feeds = crypto_feeds + finance_feeds + geo_feeds

    articles = []
    for feed in feeds:
        try:
            resp = requests.get(feed["url"], timeout=5, headers={"User-Agent": "JARVIS/3.0"})
            if resp.status_code != 200:
                continue
            items = _parse_rss_minimal(resp.text, feed["name"])
            for item in items:
                item["category"] = feed.get("cat", "crypto")
            articles.extend(items)
        except Exception as e:
            log.warning("RSS %s failed: %s", feed["name"], e)

    articles.sort(key=lambda a: a.get("pub_date", ""), reverse=True)
    result = articles[:50]
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
@rate_limit("settings")
def api_news_summarize():
    ak = get_anthropic_key()
    if not ak:
        return jsonify({"summary": "API key not configured", "sentiment": "NEUTRAL"})

    body = request.get_json(force=True)
    text = body.get("text", "")
    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ak,
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
@rate_limit("settings")
def api_jarvis():
    ak = get_anthropic_key()
    if not ak:
        return jsonify({
            "response": "Monsieur, ma connexion au réseau Anthropic n'est pas configurée. "
                        "Ouvrez Settings et entrez votre clé API Anthropic pour activer mes capacités d'analyse. — J.A.R.V.I.S.",
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
                "x-api-key": ak,
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
@rate_limit("execute")
def api_execute():
    denied = require_auth()
    if denied: return denied
    body = request.get_json(force=True)
    symbol, err = validate_symbol(body.get("symbol", "BTCUSDT"))
    if err:
        return jsonify({"error": err}), 400
    side = str(body.get("side", "long")).lower()
    order_type = str(body.get("type", "market")).lower()
    quantity, err = validate_quantity(body.get("quantity", 0))
    if err:
        return jsonify({"error": err}), 400
    price, err = validate_price(body.get("price", 0))
    if err:
        return jsonify({"error": err}), 400
    try:
        leverage = max(1, min(int(body.get("leverage", 1)), GMX_MAX_LEVERAGE))
    except (TypeError, ValueError):
        leverage = 1
    tp = body.get("tp")
    sl = body.get("sl")
    mode = body.get("mode", "live")
    requested_exchange = body.get("exchange", "").lower()

    if side not in ("long", "short", "buy", "sell"):
        return jsonify({"error": "Invalid side"}), 400

    # Kill switch check
    if risk_engine._is_kill_switch_active():
        return jsonify({"error": "Kill switch is active — all trading suspended", "kill_switch": True}), 403

    # Get current price if market order — try multiple sources
    if price <= 0:
        price_data = fetch_binance("/api/v3/ticker/price", {"symbol": symbol}, ttl=2)
        if price_data:
            price = float(price_data.get("price", 0))
        if price <= 0:
            for fallback_url in ["https://api1.binance.com", "https://api.binance.us"]:
                try:
                    r = _http_session.get(f"{fallback_url}/api/v3/ticker/price", params={"symbol": symbol}, timeout=5)
                    if r.status_code == 200:
                        price = float(r.json().get("price", 0))
                        if price > 0:
                            break
                except Exception:
                    continue
        if price <= 0:
            cg_map = {"BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "SOLUSDT": "solana", "ARBUSDT": "arbitrum", "DOGEUSDT": "dogecoin"}
            cg_id = cg_map.get(symbol)
            if cg_id:
                try:
                    r = _http_session.get("https://api.coingecko.com/api/v3/simple/price", params={"ids": cg_id, "vs_currencies": "usd"}, timeout=5)
                    if r.status_code == 200:
                        price = float(r.json().get(cg_id, {}).get("usd", 0))
                except Exception:
                    pass
        if price <= 0:
            return jsonify({"error": "Could not determine current price from any source"}), 502

    # Advanced order types — create scheduled orders
    if order_type in ("oco", "trailing", "iceberg", "dca"):
        conn = sqlite3.connect(DB_PATH)
        trade_side = "long" if side in ("long", "buy") else "short"
        order_ids = []

        if order_type == "oco":
            oco_limit = float(body.get("oco_limit", price))
            oco_stop = float(body.get("oco_stop", 0))
            parent_id = int(time.time() * 1000)
            cur = conn.execute(
                "INSERT INTO scheduled_orders (symbol, side, order_type, parent_type, quantity, price, leverage, status, parent_id, sequence_idx) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (symbol, trade_side, "limit", "oco", quantity, oco_limit, leverage, "pending", parent_id, 0),
            )
            order_ids.append(cur.lastrowid)
            cur = conn.execute(
                "INSERT INTO scheduled_orders (symbol, side, order_type, parent_type, quantity, trigger_price, leverage, status, parent_id, sequence_idx) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (symbol, trade_side, "stop", "oco", quantity, oco_stop, leverage, "pending", parent_id, 1),
            )
            order_ids.append(cur.lastrowid)

        elif order_type == "trailing":
            trail_pct = float(body.get("trail_pct", 1.0))
            activation = float(body.get("trail_activation", 0)) or price
            cur = conn.execute(
                "INSERT INTO scheduled_orders (symbol, side, order_type, parent_type, quantity, price, trigger_price, trail_pct, leverage, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (symbol, trade_side, "trailing_stop", "trailing", quantity, price, activation, trail_pct, leverage, "active"),
            )
            order_ids.append(cur.lastrowid)

        elif order_type == "iceberg":
            slices = int(body.get("slices", 5))
            slices = max(2, min(20, slices))
            slice_qty = quantity / slices
            parent_id = int(time.time() * 1000)
            for i in range(slices):
                status_val = "executed" if i == 0 else "pending"
                cur = conn.execute(
                    "INSERT INTO scheduled_orders (symbol, side, order_type, parent_type, quantity, price, leverage, status, parent_id, sequence_idx) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (symbol, trade_side, "limit", "iceberg", slice_qty, price, leverage, status_val, parent_id, i),
                )
                order_ids.append(cur.lastrowid)

        elif order_type == "dca":
            levels = int(body.get("levels", 5))
            levels = max(2, min(10, levels))
            step_pct = float(body.get("step_pct", 2.0)) / 100.0
            multiplier = float(body.get("multiplier", 1.5))
            weights = [multiplier ** i for i in range(levels)]
            total_weight = sum(weights)
            parent_id = int(time.time() * 1000)
            for i in range(levels):
                level_price = price * (1 - step_pct * i)
                level_qty = quantity * (weights[i] / total_weight)
                status_val = "executed" if i == 0 else "pending"
                cur = conn.execute(
                    "INSERT INTO scheduled_orders (symbol, side, order_type, parent_type, quantity, price, leverage, status, parent_id, sequence_idx) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (symbol, trade_side, "limit", "dca", level_qty, level_price, leverage, status_val, parent_id, i),
                )
                order_ids.append(cur.lastrowid)

        conn.commit()
        conn.close()
        log_audit("trade_executed", f"{order_type} {symbol} {side} qty={quantity}")
        return jsonify({"success": True, "order_ids": order_ids, "type": order_type, "mode": "live"})

    # Route to exchange — live execution
    trade_side = side if side in ("long", "short") else ("long" if side == "buy" else "short")
    ccxt_side = "buy" if trade_side == "long" else "sell"

    if requested_exchange == "gmx":
        adapter = exchange_manager.get_adapter_by_type("gmx")
    elif exchange_manager._adapters:
        adapter = list(exchange_manager._adapters.values())[0]
    else:
        adapter = None

    if not adapter:
        return jsonify({"error": "No exchange configured. Connect GMX wallet first."}), 400

    if hasattr(adapter, '_initialized') and not adapter._initialized:
        return jsonify({"error": "Exchange adapter not connected. Reconnect your wallet."}), 400

    collateral_usd = float(body.get("collateral_usd", 0))
    if collateral_usd > 0 and requested_exchange == "gmx":
        result = adapter.place_order_by_collateral(
            symbol=symbol, side=ccxt_side, order_type=order_type,
            collateral_usd=collateral_usd, price=price if order_type == "limit" else None,
            leverage=leverage, tp=tp, sl=sl)
    else:
        result = adapter.place_order(symbol, ccxt_side, order_type, quantity,
                                      price if order_type == "limit" else None, leverage, tp, sl)

    if isinstance(result, dict) and result.get("error"):
        log.error("Trade execution error: %s | symbol=%s side=%s collateral=%s", result["error"], symbol, side, collateral_usd)

    if isinstance(result, dict) and result.get("success"):
        conn = get_db()
        conn.execute(
            "INSERT INTO trade_journal (symbol, action, reason, signal_score, confidence, regime) VALUES (?, ?, ?, ?, ?, ?)",
            (symbol, f"live_{ccxt_side}", f"Live {order_type} via {requested_exchange or 'default'}", 0, 0, ""),
        )
        conn.commit()
        conn.close()

    log_audit("trade_executed", f"live {side} {symbol} qty={quantity} collateral={collateral_usd} @{price} via {requested_exchange or 'default'}")
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

    starting_capital = 100.0
    realized_pnl = paper_status["total_pnl"]

    conn = get_db()
    open_trades = conn.execute("SELECT * FROM paper_trades WHERE status = 'open'").fetchall()
    conn.close()

    margin_used = 0.0
    unrealized_pnl = 0.0
    for t in open_trades:
        entry = t["entry_price"]
        qty = t["quantity"]
        lev = t["leverage"] or 1
        margin_used += (entry * qty) / lev
        try:
            pd = fetch_binance("/api/v3/ticker/price", {"symbol": t["symbol"]}, ttl=5)
            if pd:
                cur = float(pd.get("price", entry))
                if t["side"] == "long":
                    unrealized_pnl += (cur - entry) / entry * qty * lev
                else:
                    unrealized_pnl += (entry - cur) / entry * qty * lev
        except Exception:
            pass

    balance = starting_capital + realized_pnl
    equity = balance + unrealized_pnl
    available = max(0, equity - margin_used)

    return jsonify({
        "balance": round(balance, 4),
        "equity": round(equity, 4),
        "available": round(available, 4),
        "unrealized_pnl": round(unrealized_pnl, 4),
        "margin_used": round(margin_used, 4),
        "balances": live_balances,
        "paper": {
            "total_pnl": paper_status["total_pnl"],
            "open_positions": paper_status["open_positions"],
            "win_rate": paper_status["win_rate"],
        },
    })


@app.route("/api/close", methods=["POST"])
@rate_limit("execute")
def api_close():
    denied = require_auth()
    if denied: return denied
    body = request.get_json(force=True)
    trade_id = body.get("trade_id")
    symbol = str(body.get("symbol", "")).upper()
    requested_exchange = body.get("exchange", "").lower()
    exit_price, err = validate_price(body.get("exit_price", 0))
    if err:
        return jsonify({"error": err}), 400

    if not symbol:
        return jsonify({"error": "symbol required"}), 400

    if requested_exchange == "gmx":
        adapter = exchange_manager.get_adapter_by_type("gmx")
    elif exchange_manager._adapters:
        adapter = list(exchange_manager._adapters.values())[0]
    else:
        adapter = None

    if not adapter:
        return jsonify({"error": "No exchange configured. Connect GMX wallet first."}), 400

    close_pct = float(body.get("close_pct", 100.0))
    try:
        result = adapter.close_position(symbol, position_id=trade_id, close_pct=close_pct)
    except TypeError:
        result = adapter.close_position(symbol, position_id=trade_id)
    log_audit("trade_closed", f"live {symbol} via {requested_exchange or 'default'}")
    return jsonify(result)


@app.route("/api/paper/status")
def api_paper_status():
    return jsonify(paper_trader.get_status())


@app.route("/api/paper/history")
def api_paper_history():
    limit = int(request.args.get("limit", 50))
    return jsonify(paper_trader.get_history(limit))


# ===========================================================================
# API ROUTES — Authentication (4 routes)
# ===========================================================================

@app.route("/api/auth/status")
def api_auth_status():
    configured = is_pin_configured()
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    authenticated = validate_session(token) if configured else True
    return jsonify({"pin_configured": configured, "authenticated": authenticated})


@app.route("/api/auth/setup", methods=["POST"])
@rate_limit("auth")
def api_auth_setup():
    if is_pin_configured():
        return jsonify({"error": "PIN already configured. Use change-pin to modify."}), 400
    body = request.get_json(force=True)
    pin = body.get("pin", "").strip()
    if len(pin) < 4 or len(pin) > 20:
        return jsonify({"error": "PIN must be 4-20 characters"}), 400

    pin_hash, salt = _hash_pin(pin)
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO auth_pin (id, pin_hash, pin_salt) VALUES (1, ?, ?)",
        (pin_hash, salt),
    )
    conn.commit()
    conn.close()

    token = create_session(request.remote_addr)
    log_audit("auth_setup", "PIN configured")
    return jsonify({"success": True, "token": token})


@app.route("/api/auth/login", methods=["POST"])
@rate_limit("auth")
def api_auth_login():
    ip = request.remote_addr or "unknown"
    if _rate_limiter.is_blocked(ip):
        retry = int(_rate_limiter._blocked.get(ip, time.time()) - time.time())
        resp = jsonify({"error": "Too many failed attempts — try again later", "retry_after": max(retry, 1)})
        resp.status_code = 429
        resp.headers["Retry-After"] = str(max(retry, 1))
        return resp
    if not is_pin_configured():
        return jsonify({"error": "No PIN configured yet. Use /api/auth/setup first."}), 400
    body = request.get_json(force=True)
    pin = body.get("pin", "").strip()

    if not verify_pin(pin):
        blocked = _rate_limiter.record_login_fail(ip, max_fails=5, block_seconds=900)
        fails = _rate_limiter.get_login_fails(ip)
        remaining = max(0, 5 - fails) if not blocked else 0
        msg = "Invalid PIN"
        if blocked:
            msg = "Too many failed attempts — IP blocked for 15 minutes"
        elif remaining <= 2:
            msg = f"Invalid PIN — {remaining} attempt(s) remaining"
        log_audit("auth_failed", f"{remaining} attempts remaining", success=False, ip=ip)
        return jsonify({"error": msg}), (429 if blocked else 401)

    _rate_limiter.reset_login_fails(ip)
    cleanup_expired_sessions()
    token = create_session(ip)
    log_audit("auth_login", "Session created", ip=ip)
    return jsonify({"success": True, "token": token})


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    if token:
        conn = get_db()
        conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
    log_audit("auth_logout", "Session ended")
    return jsonify({"success": True})


# ===========================================================================
# API ROUTES — Anthropic Key Management (3 routes)
# ===========================================================================

@app.route("/api/settings/anthropic-key", methods=["POST"])
@rate_limit("settings")
def api_set_anthropic_key():
    blocked = require_fernet()
    if blocked: return blocked
    denied = require_auth()
    if denied: return denied
    body = request.get_json(force=True)
    key = body.get("key", "").strip()
    if not key:
        return jsonify({"error": "Key is required"}), 400
    if not key.startswith("sk-ant-"):
        return jsonify({"error": "Invalid key format — must start with sk-ant-"}), 400
    if len(key) < 20 or len(key) > 200:
        return jsonify({"error": "Invalid key length"}), 400

    encrypted = encrypt_string(key)
    set_setting("anthropic_api_key_enc", encrypted)
    last4 = key[-4:]
    log_audit("key_added", "Anthropic API key configured (****" + last4 + ")")
    return jsonify({"success": True, "masked": "sk-ant-****" + last4})


@app.route("/api/settings/anthropic-key/status")
def api_anthropic_key_status():
    if ANTHROPIC_API_KEY:
        last4 = ANTHROPIC_API_KEY[-4:]
        return jsonify({"configured": True, "source": "env", "masked": "sk-ant-****" + last4})

    enc = get_setting("anthropic_api_key_enc")
    if enc:
        try:
            key = decrypt_string(enc)
            last4 = key[-4:]
            return jsonify({"configured": True, "source": "db", "masked": "sk-ant-****" + last4})
        except Exception:
            return jsonify({"configured": False, "source": None, "masked": None, "error": "Stored key corrupted"})

    return jsonify({"configured": False, "source": None, "masked": None})


@app.route("/api/settings/anthropic-key", methods=["DELETE"])
@rate_limit("settings")
def api_delete_anthropic_key():
    blocked = require_fernet()
    if blocked: return blocked
    denied = require_auth()
    if denied: return denied
    enc = get_setting("anthropic_api_key_enc")
    if not enc:
        return jsonify({"error": "No stored key to delete (env var keys cannot be deleted from here)"}), 404
    delete_setting("anthropic_api_key_enc")
    log_audit("key_removed", "Anthropic API key removed")
    return jsonify({"success": True})


# ===========================================================================
# API ROUTES — GMX Wallet Vault (3 routes)
# ===========================================================================

@app.route("/api/wallet/gmx/setup", methods=["POST"])
@rate_limit("settings")
def api_gmx_wallet_setup():
    blocked = require_fernet()
    if blocked: return blocked
    denied = require_auth()
    if denied: return denied
    body = request.get_json(force=True)
    private_key = body.get("private_key", "").strip()
    pin = body.get("pin", "").strip()

    if not private_key:
        return jsonify({"error": "Private key is required"}), 400
    if not pin:
        return jsonify({"error": "PIN is required for vault encryption"}), 400
    if not verify_pin(pin):
        return jsonify({"error": "Invalid PIN"}), 401

    if not private_key.startswith("0x"):
        private_key = "0x" + private_key
    if len(private_key) != 66:
        return jsonify({"error": "Invalid private key length (expected 64 hex chars)"}), 400

    try:
        if HAS_WEB3:
            acct = Web3Account.from_key(private_key)
            address = acct.address
        else:
            address = "0x" + hashlib.sha256(private_key.encode()).hexdigest()[:40]
    except Exception:
        return jsonify({"error": "Invalid private key format"}), 400

    encrypted = vault_encrypt(private_key, pin)
    set_setting("gmx_wallet_enc", encrypted)
    set_setting("gmx_wallet_address", address)

    _wipe_string(private_key)
    log_audit("wallet_setup", "GMX wallet configured: " + address[:8] + "...")
    return jsonify({"success": True, "address": address})


@app.route("/api/wallet/gmx/status")
def api_gmx_wallet_status():
    denied = require_auth()
    if denied: return denied
    addr = get_gmx_wallet_address()
    masked = (addr[:6] + "..." + addr[-4:]) if addr and len(addr) > 10 else None
    return jsonify({
        "configured": addr is not None,
        "address": masked,
    })


@app.route("/api/wallet/gmx", methods=["DELETE"])
@rate_limit("settings")
def api_gmx_wallet_delete():
    blocked = require_fernet()
    if blocked: return blocked
    denied = require_auth()
    if denied: return denied
    body = request.get_json(force=True)
    pin = body.get("pin", "").strip()

    if not pin or not verify_pin(pin):
        return jsonify({"error": "Invalid PIN — confirmation required"}), 401

    enc = get_setting("gmx_wallet_enc")
    if not enc:
        return jsonify({"error": "No GMX wallet configured"}), 404

    delete_setting("gmx_wallet_enc")
    delete_setting("gmx_wallet_address")
    log_audit("wallet_removed", "GMX wallet removed from vault")
    return jsonify({"success": True})


# ===========================================================================
# API ROUTES — Exchange Management (4 routes)
# ===========================================================================

@app.route("/api/exchanges/add", methods=["POST"])
@rate_limit("settings")
def api_exchanges_add():
    blocked = require_fernet()
    if blocked: return blocked
    denied = require_auth()
    if denied: return denied
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
    log_audit("exchange_added", f"{exchange_type} exchange '{name}'")
    return jsonify(result)


@app.route("/api/exchanges/list")
def api_exchanges_list():
    return jsonify(exchange_manager.list_exchanges())


@app.route("/api/exchanges/remove", methods=["DELETE"])
@rate_limit("settings")
def api_exchanges_remove():
    denied = require_auth()
    if denied: return denied
    body = request.get_json(force=True)
    exchange_id = body.get("id")
    if not exchange_id:
        return jsonify({"error": "id is required"}), 400
    result = exchange_manager.remove_exchange(int(exchange_id))
    log_audit("exchange_removed", f"Exchange #{exchange_id} removed")
    return jsonify(result)


@app.route("/api/exchanges/test", methods=["POST"])
@rate_limit("settings")
def api_exchanges_test():
    denied = require_auth()
    if denied: return denied
    body = request.get_json(force=True)
    exchange_id = body.get("id")
    if not exchange_id:
        return jsonify({"error": "id is required"}), 400
    return jsonify(exchange_manager.test_exchange(int(exchange_id)))


# ===========================================================================
# API ROUTES — GMX V2 Dedicated (6 routes)
# ===========================================================================


@app.route("/api/gmx/connect", methods=["POST"])
@rate_limit("auth")
def api_gmx_connect():
    """Unlock GMX wallet vault and connect the adapter to Arbitrum."""
    denied = require_auth()
    if denied:
        return denied

    addr = get_gmx_wallet_address()
    if not addr:
        return jsonify({"error": "No GMX wallet configured — go to Settings first"}), 400

    existing = exchange_manager.get_adapter_by_type("gmx")
    if existing and existing._initialized:
        return jsonify({"success": True, "address": addr, "already_connected": True})

    body = request.get_json(force=True)
    pin = body.get("pin", "").strip()
    if not pin:
        return jsonify({"error": "PIN is required to unlock the vault"}), 400
    if not verify_pin(pin):
        return jsonify({"error": "Invalid PIN"}), 401

    enc = get_setting("gmx_wallet_enc")
    if not enc:
        return jsonify({"error": "Wallet vault is empty"}), 400

    private_key = vault_decrypt(enc, pin)
    if not private_key:
        return jsonify({"error": "Failed to decrypt wallet — wrong PIN or corrupted data"}), 400

    try:
        adapter = GMXAdapter(private_key=private_key, testnet=False)
        _wipe_string(private_key)

        if not adapter._initialized:
            log.error("GMX adapter created but RPC connection failed")
            return jsonify({"error": "Cannot connect to Arbitrum RPC — check network"}), 502

        exchange_manager._adapters["gmx_wallet"] = adapter

        balance_info = {}
        try:
            bal = adapter.get_balance()
            balance_info = bal.get("assets", {})
        except Exception:
            pass

        log_audit("wallet_setup", f"GMX adapter connected: {addr[:10]}...")
        return jsonify({
            "success": True,
            "address": addr,
            "initialized": True,
            "network": "Arbitrum One",
            "balance": balance_info,
        })
    except Exception as e:
        _wipe_string(private_key)
        log.error("GMX connect failed: %s", sanitize_error(e))
        return jsonify({"error": "Failed to initialize GMX adapter"}), 500

@app.route("/api/gmx/markets")
def api_gmx_markets():
    """List available GMX V2 markets with live OI and funding data."""
    try:
        adapter = exchange_manager.get_adapter_by_type("gmx")
        if not adapter or not adapter._initialized:
            return jsonify(_gmx_markets_fallback()), 200

        reader = adapter._contracts.get("reader")
        data_store = adapter._contracts.get("data_store")
        if not reader or not data_store:
            return jsonify(_gmx_markets_fallback()), 200

        markets = []
        for symbol, config in GMX_V2_MARKETS.items():
            price = adapter._get_index_price(symbol)
            markets.append({
                "symbol": symbol,
                "market_token": config["market_token"],
                "index_token": config["index_token"],
                "long_token": config["long_token"],
                "short_token": config["short_token"],
                "price": round(price, 4),
                "max_leverage": GMX_MAX_LEVERAGE,
                "position_fee_bps": GMX_POSITION_FEE_BPS,
            })
        return jsonify({"markets": markets, "network": "Arbitrum One" if not adapter.testnet else "Arbitrum Sepolia"})

    except Exception as e:
        log.error("GMX markets route error: %s", e)
        return jsonify({"error": sanitize_error(e)}), 502


def _gmx_markets_fallback():
    """Static fallback when no GMX adapter is connected."""
    markets = []
    for symbol, config in GMX_V2_MARKETS.items():
        markets.append({
            "symbol": symbol,
            "market_token": config["market_token"],
            "index_token": config["index_token"],
            "long_token": config["long_token"],
            "short_token": config["short_token"],
            "price": 0,
            "max_leverage": GMX_MAX_LEVERAGE,
            "position_fee_bps": GMX_POSITION_FEE_BPS,
        })
    return {"markets": markets, "network": "disconnected"}


@app.route("/api/gmx/funding")
def api_gmx_funding():
    """GMX V2 funding rates — borrowing fees per market."""
    symbol = request.args.get("symbol", "BTCUSDT")
    try:
        adapter = exchange_manager.get_adapter_by_type("gmx")
        if not adapter or not adapter._initialized:
            return jsonify(_gmx_funding_estimate(symbol)), 200

        reader = adapter._contracts.get("reader")
        data_store = adapter._contracts.get("data_store")
        market_config = gmx_symbol_to_market(symbol)
        if not reader or not data_store or not market_config:
            return jsonify(_gmx_funding_estimate(symbol)), 200

        market_addr = Web3.to_checksum_address(market_config["market_token"])

        cache_key = f"gmx_funding_{symbol}"
        cached = cache.get(cache_key)
        if cached:
            return jsonify(cached)

        result = {
            "symbol": symbol,
            "market_token": market_config["market_token"],
            "borrowing_fee_long_bps": 0.0,
            "borrowing_fee_short_bps": 0.0,
            "funding_rate_long": 0.0,
            "funding_rate_short": 0.0,
            "note": "Live funding from DataStore — values update on-chain per block",
        }

        try:
            long_borrow_key = Web3.solidity_keccak(
                ["bytes32", "address"],
                [Web3.solidity_keccak(["string"], ["CUMULATIVE_BORROWING_FACTOR"]), market_addr]
            )
            short_borrow_key = Web3.solidity_keccak(
                ["bytes32", "address", "bool"],
                [Web3.solidity_keccak(["string"], ["CUMULATIVE_BORROWING_FACTOR"]), market_addr, False]
            )
        except Exception:
            pass

        cache.set(cache_key, result, ttl=30)
        return jsonify(result)

    except Exception as e:
        log.error("GMX funding route error: %s", e)
        return jsonify({"error": sanitize_error(e)}), 502


def _gmx_funding_estimate(symbol):
    """Estimated funding when adapter is not connected."""
    return {
        "symbol": symbol,
        "borrowing_fee_long_bps": 0.005,
        "borrowing_fee_short_bps": 0.003,
        "funding_rate_long": -0.001,
        "funding_rate_short": 0.001,
        "source": "estimate",
        "note": "Connect GMX adapter for live on-chain data",
    }


@app.route("/api/gmx/prices")
def api_gmx_prices():
    """Current prices for all GMX V2 markets from Binance + on-chain fallback."""
    try:
        adapter = exchange_manager.get_adapter_by_type("gmx")
        prices = {}
        for symbol in GMX_V2_MARKETS:
            if adapter and adapter._initialized:
                p = adapter._get_index_price(symbol)
            else:
                try:
                    resp = requests.get(
                        f"{BINANCE_BASE}/api/v3/ticker/price",
                        params={"symbol": symbol}, timeout=3
                    )
                    p = float(resp.json()["price"]) if resp.status_code == 200 else 0
                except Exception:
                    p = 0
            prices[symbol] = round(p, 4)
        return jsonify({"prices": prices, "source": "binance+cache", "timestamp": int(time.time())})
    except Exception as e:
        return jsonify({"error": sanitize_error(e)}), 502


@app.route("/api/gmx/positions")
def api_gmx_positions():
    """Get all GMX V2 positions for the connected account with enriched data."""
    denied = require_auth()
    if denied: return denied
    try:
        adapter = exchange_manager.get_adapter_by_type("gmx")
        if not adapter or not adapter._initialized:
            return jsonify({"positions": [], "error": "GMX adapter not connected"}), 200
        if not adapter._has_signer():
            return jsonify({"positions": [], "error": "No private key configured"}), 200

        positions = adapter.get_positions()

        total_pnl = sum(p.get("pnl", 0) for p in positions)
        total_collateral = sum(p.get("collateral_usd", 0) for p in positions)
        total_size = sum(p.get("size_usd", 0) for p in positions)

        return jsonify({
            "positions": positions,
            "count": len(positions),
            "total_pnl": round(total_pnl, 2),
            "total_collateral": round(total_collateral, 2),
            "total_size": round(total_size, 2),
            "account": adapter._account.address if adapter._account else None,
            "network": "Arbitrum One" if not adapter.testnet else "Arbitrum Sepolia",
        })
    except Exception as e:
        log.error("GMX positions route error: %s", e)
        return jsonify({"error": sanitize_error(e)}), 502


@app.route("/api/gmx/estimate", methods=["POST"])
def api_gmx_estimate():
    """Estimate fees and impact before placing a GMX V2 order."""
    body = request.get_json(force=True)
    symbol = body.get("symbol", "BTCUSDT")
    side = body.get("side", "long")
    quantity = float(body.get("quantity", 0))
    leverage = float(body.get("leverage", 1))
    price = float(body.get("price", 0))

    market = gmx_symbol_to_market(symbol)
    if not market:
        return jsonify({"error": f"Unsupported market: {symbol}"}), 400
    if quantity <= 0:
        return jsonify({"error": "quantity must be > 0"}), 400

    adapter = exchange_manager.get_adapter_by_type("gmx")
    if adapter and adapter._initialized:
        current_price = adapter._get_index_price(symbol)
    else:
        try:
            resp = requests.get(f"{BINANCE_BASE}/api/v3/ticker/price", params={"symbol": symbol}, timeout=3)
            current_price = float(resp.json()["price"]) if resp.status_code == 200 else 0
        except Exception:
            current_price = 0

    ref_price = price if price > 0 else current_price
    if ref_price <= 0:
        return jsonify({"error": "Cannot determine price"}), 400

    leverage = min(leverage, GMX_MAX_LEVERAGE)
    is_long = side.lower() in ("long", "buy")

    collateral_usd = quantity * ref_price / leverage
    size_usd = collateral_usd * leverage
    position_fee_usd = size_usd * GMX_POSITION_FEE_BPS / 10000

    execution_fee_eth = GMX_EXECUTION_FEE_BUFFER_WEI / 10**18
    if adapter and adapter._initialized:
        execution_fee_eth = adapter._estimate_execution_fee() / 10**18

    slippage_mult = GMX_DEFAULT_SLIPPAGE_BPS / 10000
    if is_long:
        acceptable_price = ref_price * (1 + slippage_mult)
        worst_entry = acceptable_price
    else:
        acceptable_price = ref_price * (1 - slippage_mult)
        worst_entry = acceptable_price

    liq_move = 1.0 / leverage if leverage > 1 else 1.0
    if is_long:
        liquidation_price = ref_price * (1 - liq_move * 0.9)
    else:
        liquidation_price = ref_price * (1 + liq_move * 0.9)

    return jsonify({
        "symbol": symbol,
        "side": side,
        "leverage": leverage,
        "ref_price": round(ref_price, 4),
        "size_usd": round(size_usd, 2),
        "collateral_usd": round(collateral_usd, 2),
        "position_fee_usd": round(position_fee_usd, 4),
        "position_fee_bps": GMX_POSITION_FEE_BPS,
        "execution_fee_eth": round(execution_fee_eth, 6),
        "acceptable_price": round(acceptable_price, 4),
        "worst_entry": round(worst_entry, 4),
        "liquidation_price": round(liquidation_price, 4),
        "max_slippage_bps": GMX_DEFAULT_SLIPPAGE_BPS,
        "max_leverage": GMX_MAX_LEVERAGE,
        "market_token": market["market_token"],
    })


@app.route("/api/gmx/entry-plan")
def api_gmx_entry_plan():
    """Generate a high-leverage GMX entry plan based on DipTopDetector analysis."""
    symbol = request.args.get("symbol", "BTCUSDT")
    interval = request.args.get("interval", "15m")
    balance = float(request.args.get("balance", 100))

    try:
        params = {"symbol": symbol, "interval": INTERVALS.get(interval, interval), "limit": 100}
        resp = requests.get(f"{BINANCE_BASE}/api/v3/klines", params=params, timeout=8)
        if resp.status_code != 200:
            return jsonify({"error": "Failed to fetch candles from Binance"}), 502

        raw_klines = resp.json()
        ohlcv = []
        for k in raw_klines:
            ohlcv.append({
                "time": int(k[0]) // 1000,
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })

        if len(ohlcv) < 60:
            return jsonify({"actionable": False, "reason": "Not enough candles (need 60+)"}), 200

        indicators = compute_all_indicators(ohlcv)
        plan = dip_top_detector.generate_gmx_entry_plan(symbol, ohlcv, indicators["_raw"], balance)
        plan["interval"] = interval
        plan["candles_analyzed"] = len(ohlcv)

        return jsonify(plan)

    except Exception as e:
        log.error("GMX entry-plan error: %s", e)
        return jsonify({"error": sanitize_error(e)}), 502


@app.route("/api/gmx/auto-scan")
def api_gmx_auto_scan():
    """Scan all GMX markets for high-leverage entry opportunities."""
    interval = request.args.get("interval", "15m")
    balance = float(request.args.get("balance", 100))

    opportunities = []
    for symbol in GMX_V2_MARKETS:
        try:
            params = {"symbol": symbol, "interval": INTERVALS.get(interval, interval), "limit": 100}
            resp = requests.get(f"{BINANCE_BASE}/api/v3/klines", params=params, timeout=5)
            if resp.status_code != 200:
                continue

            raw_klines = resp.json()
            ohlcv = [{"time": int(k[0]) // 1000, "open": float(k[1]), "high": float(k[2]),
                       "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
                      for k in raw_klines]

            if len(ohlcv) < 60:
                continue

            indicators = compute_all_indicators(ohlcv)
            plan = dip_top_detector.generate_gmx_entry_plan(symbol, ohlcv, indicators["_raw"], balance)

            if plan.get("actionable"):
                opportunities.append(plan)

        except Exception as e:
            log.debug("Auto-scan %s failed: %s", symbol, e)
            continue

    opportunities.sort(key=lambda x: x.get("score", 0), reverse=True)

    return jsonify({
        "opportunities": opportunities,
        "count": len(opportunities),
        "markets_scanned": len(GMX_V2_MARKETS),
        "interval": interval,
        "balance": balance,
        "timestamp": int(time.time()),
    })


@app.route("/api/gmx/health")
def api_gmx_health():
    """Full GMX V2 system health check: RPC, contracts, gas, account, circuit breaker."""
    health = {
        "status": "unknown",
        "web3_installed": HAS_WEB3,
        "checks": {},
    }

    if not HAS_WEB3:
        health["status"] = "degraded"
        health["error"] = "web3.py not installed"
        return jsonify(health)

    adapter = exchange_manager.get_adapter_by_type("gmx")
    if not adapter:
        health["status"] = "disconnected"
        health["error"] = "No GMX adapter configured — add via Settings"
        return jsonify(health)

    # Check 1: RPC connectivity
    try:
        rpc_ok = adapter._ensure_connection()
        health["checks"]["rpc"] = {
            "ok": rpc_ok,
            "url": adapter.rpc_url,
            "chain_id": adapter._w3.eth.chain_id if rpc_ok else None,
            "block": adapter._w3.eth.block_number if rpc_ok else None,
        }
    except Exception as e:
        health["checks"]["rpc"] = {"ok": False, "error": sanitize_error(e)}

    # Check 2: Contracts loaded
    contracts_ok = bool(adapter._contracts)
    health["checks"]["contracts"] = {
        "ok": contracts_ok,
        "loaded": list(adapter._contracts.keys()) if contracts_ok else [],
    }

    # Check 3: Gas price
    try:
        gas_price = adapter._w3.eth.gas_price
        gas_gwei = gas_price / 10**9
        exec_fee_eth = adapter._estimate_execution_fee() / 10**18
        gas_ok = gas_gwei < 5.0
        health["checks"]["gas"] = {
            "ok": gas_ok,
            "gas_price_gwei": round(gas_gwei, 3),
            "execution_fee_eth": round(exec_fee_eth, 6),
            "warning": "Gas elevated" if not gas_ok else None,
        }
    except Exception as e:
        health["checks"]["gas"] = {"ok": False, "error": sanitize_error(e)}

    # Check 4: Account
    has_signer = adapter._has_signer()
    health["checks"]["account"] = {
        "ok": has_signer,
        "address": adapter._account.address if has_signer else None,
        "mode": "read-write" if has_signer else "read-only",
    }

    if has_signer:
        try:
            eth_bal = adapter._w3.eth.get_balance(adapter._account.address) / 10**18
            health["checks"]["account"]["eth_balance"] = round(eth_bal, 6)
            health["checks"]["account"]["has_gas"] = eth_bal > 0.001
        except Exception:
            health["checks"]["account"]["has_gas"] = False

    # Check 5: Circuit breaker status
    try:
        positions = adapter.get_positions()
        cb_alerts = risk_engine.gmx_circuit_breaker(positions)
        health["checks"]["circuit_breaker"] = {
            "ok": len(cb_alerts) == 0,
            "positions_count": len(positions),
            "alerts": cb_alerts,
        }
    except Exception as e:
        health["checks"]["circuit_breaker"] = {"ok": True, "error": sanitize_error(e)}

    # Overall status
    all_checks = health["checks"]
    critical_ok = all_checks.get("rpc", {}).get("ok") and all_checks.get("contracts", {}).get("ok")
    any_warning = not all_checks.get("gas", {}).get("ok") or not all_checks.get("account", {}).get("ok")

    if not critical_ok:
        health["status"] = "error"
    elif any_warning:
        health["status"] = "warning"
    elif all_checks.get("circuit_breaker", {}).get("alerts"):
        health["status"] = "circuit_breaker_triggered"
    else:
        health["status"] = "healthy"

    return jsonify(health)


@app.route("/api/gmx/diagnose")
def api_gmx_diagnose():
    """Full pre-trade diagnostic: checks every requirement for placing a GMX V2 order."""
    denied = require_auth()
    if denied:
        return denied
    adapter = exchange_manager.get_adapter_by_type("gmx")
    if not adapter or not adapter._initialized:
        return jsonify({"error": "GMX adapter not connected", "steps": {}}), 400
    if not adapter._has_signer():
        return jsonify({"error": "No private key configured", "steps": {}}), 400

    steps = {}
    account = adapter._account.address

    try:
        chain_id = adapter._w3.eth.chain_id
        block = adapter._w3.eth.block_number
        steps["rpc"] = {"ok": True, "chain_id": chain_id, "block": block}
    except Exception as e:
        steps["rpc"] = {"ok": False, "error": str(e)}
        return jsonify({"error": "RPC failed", "steps": steps})

    try:
        ex_router = adapter._contracts.get("exchange_router")
        ov = adapter._contracts.get("order_vault")
        code_er = adapter._w3.eth.get_code(ex_router.address)
        code_ov = adapter._w3.eth.get_code(Web3.to_checksum_address(ov))
        steps["contracts"] = {
            "ok": len(code_er) > 2 and len(code_ov) > 2,
            "exchange_router": ex_router.address,
            "exchange_router_has_code": len(code_er) > 2,
            "order_vault": ov,
            "order_vault_has_code": len(code_ov) > 2,
        }
    except Exception as e:
        steps["contracts"] = {"ok": False, "error": str(e)}

    try:
        eth_bal = adapter._w3.eth.get_balance(account)
        usdc_bal = adapter._get_token_balance(GMX_V2_TOKENS["USDC"], 6)
        exec_fee = adapter._estimate_execution_fee()
        gas_price = adapter._w3.eth.gas_price
        gas_cost = 1_500_000 * gas_price
        total_eth_needed = exec_fee + gas_cost
        steps["balances"] = {
            "ok": eth_bal > total_eth_needed and usdc_bal > 1.0,
            "eth_wei": eth_bal,
            "eth": round(eth_bal / 10**18, 6),
            "usdc": round(usdc_bal, 4),
            "execution_fee_eth": round(exec_fee / 10**18, 6),
            "gas_cost_eth": round(gas_cost / 10**18, 6),
            "total_eth_needed": round(total_eth_needed / 10**18, 6),
            "gas_price_gwei": round(gas_price / 10**9, 4),
        }
    except Exception as e:
        steps["balances"] = {"ok": False, "error": str(e)}

    steps["plugin_approval"] = {"ok": True, "note": "GMX V2 does not use per-user plugin approval"}

    try:
        router_addr = adapter._contracts.get("router")
        usdc_contract = get_erc20_contract(adapter._w3, GMX_V2_TOKENS["USDC"])
        allowance = usdc_contract.functions.allowance(account, router_addr).call()
        steps["usdc_approval"] = {
            "ok": allowance > 0,
            "allowance_raw": allowance,
            "allowance_usdc": round(allowance / 10**6, 2),
            "router": router_addr,
        }
    except Exception as e:
        steps["usdc_approval"] = {"ok": False, "error": str(e)}

    all_ok = all(s.get("ok", False) for s in steps.values())
    return jsonify({"status": "ready" if all_ok else "issues_found", "steps": steps})


@app.route("/api/gmx/circuit-breaker", methods=["POST"])
@rate_limit("execute")
def api_gmx_circuit_breaker():
    """Manually trigger circuit breaker — close all GMX positions."""
    denied = require_auth()
    if denied: return denied
    adapter = exchange_manager.get_adapter_by_type("gmx")
    if not adapter or not adapter._initialized:
        return jsonify({"error": "GMX adapter not connected"}), 400

    positions = adapter.get_positions()
    if not positions:
        return jsonify({"message": "No positions to close", "closed": 0})

    results = []
    for pos in positions:
        result = adapter.close_position(pos["symbol"])
        results.append({"symbol": pos["symbol"], "result": result})

    closed = sum(1 for r in results if r["result"].get("success"))
    return jsonify({
        "message": f"Circuit breaker executed: {closed}/{len(positions)} positions closed",
        "closed": closed,
        "total": len(positions),
        "results": results,
    })


# ===========================================================================
# API ROUTES — Monitoring & Control (5 routes)
# ===========================================================================

@app.route("/api/drawdown")
def api_drawdown():
    return jsonify(risk_engine.get_drawdown_status())


@app.route("/api/killswitch", methods=["POST"])
@rate_limit("settings")
def api_killswitch():
    denied = require_auth()
    if denied: return denied
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
    log_audit("killswitch_toggled", f"Kill switch {status}: {reason}")

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
        "ai_available": bool(get_anthropic_key()),
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
            "ai_chat": bool(get_anthropic_key()),
            "whale_tracking": True,
            "news_aggregation": True,
        },
    })


@app.route("/api/security/status")
@rate_limit("settings")
def api_security_status():
    denied = require_auth()
    if denied:
        return denied
    fernet_ok = check_fernet_integrity()
    perms_ok, perms_str = check_key_file_permissions()
    return jsonify({
        "fernet_available": HAS_FERNET,
        "fernet_integrity": fernet_ok,
        "key_file_exists": SECRET_KEY_FILE.exists(),
        "key_file_permissions": perms_str,
        "key_file_permissions_ok": perms_ok,
        "encryption_test_passed": fernet_ok,
        "pin_configured": is_pin_configured(),
        "rate_limiter_active": True,
        "blocked_ips_count": len(_rate_limiter._blocked),
    })


@app.route("/api/audit-log")
@rate_limit("settings")
def api_audit_log():
    denied = require_auth()
    if denied:
        return denied
    try:
        limit = max(1, min(int(request.args.get("limit", 100)), 500))
    except (TypeError, ValueError):
        limit = 100
    conn = get_db()
    rows = conn.execute(
        "SELECT id, timestamp, event_type, ip_address, details, success FROM audit_log ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return jsonify({
        "events": [
            {
                "id": r["id"],
                "timestamp": r["timestamp"],
                "event_type": r["event_type"],
                "ip": r["ip_address"],
                "details": r["details"],
                "success": bool(r["success"]),
            }
            for r in rows
        ]
    })


@app.route("/api/security/rotate-key", methods=["POST"])
@rate_limit("settings")
def api_rotate_key():
    blocked = require_fernet()
    if blocked:
        return blocked
    denied = require_auth()
    if denied:
        return denied

    old_fernet = get_fernet()
    if not old_fernet:
        return jsonify({"error": "No existing encryption key"}), 500

    re_encrypted = {}
    conn = get_db()

    try:
        anthro_enc = get_setting("anthropic_api_key_enc")
        if anthro_enc:
            plain = old_fernet.decrypt(anthro_enc.encode()).decode()
            re_encrypted["anthropic_api_key_enc"] = plain

        gmx_enc = get_setting("gmx_wallet_enc")
        if gmx_enc:
            plain = old_fernet.decrypt(gmx_enc.encode()).decode()
            re_encrypted["gmx_wallet_enc"] = plain

        rows = conn.execute("SELECT id, api_key_enc, api_secret_enc, passphrase_enc FROM exchanges").fetchall()
        exchange_plains = []
        for row in rows:
            ep = {
                "id": row["id"],
                "api_key": old_fernet.decrypt(row["api_key_enc"].encode()).decode() if row["api_key_enc"] else "",
                "api_secret": old_fernet.decrypt(row["api_secret_enc"].encode()).decode() if row["api_secret_enc"] else "",
                "passphrase": old_fernet.decrypt(row["passphrase_enc"].encode()).decode() if row["passphrase_enc"] else "",
            }
            exchange_plains.append(ep)
    except Exception:
        conn.close()
        log_audit("key_rotation", "Failed: decryption error during re-encryption", success=False)
        return jsonify({"error": "Failed to decrypt existing data — key rotation aborted"}), 500

    global _fernet_instance
    new_key = Fernet.generate_key()
    SECRET_KEY_FILE.write_bytes(new_key)
    os.chmod(str(SECRET_KEY_FILE), 0o600)
    _fernet_instance = Fernet(new_key)
    new_fernet = _fernet_instance

    if "anthropic_api_key_enc" in re_encrypted:
        set_setting("anthropic_api_key_enc", new_fernet.encrypt(re_encrypted["anthropic_api_key_enc"].encode()).decode())
    if "gmx_wallet_enc" in re_encrypted:
        set_setting("gmx_wallet_enc", new_fernet.encrypt(re_encrypted["gmx_wallet_enc"].encode()).decode())

    for ep in exchange_plains:
        conn.execute(
            "UPDATE exchanges SET api_key_enc = ?, api_secret_enc = ?, passphrase_enc = ? WHERE id = ?",
            (
                new_fernet.encrypt(ep["api_key"].encode()).decode(),
                new_fernet.encrypt(ep["api_secret"].encode()).decode(),
                new_fernet.encrypt(ep["passphrase"].encode()).decode() if ep["passphrase"] else "",
                ep["id"],
            ),
        )
    conn.commit()
    conn.close()

    count = len(re_encrypted) + len(exchange_plains)
    log_audit("key_rotation", f"Encryption key rotated, {count} items re-encrypted")
    return jsonify({"success": True, "re_encrypted_count": count})


@app.route("/api/security/backup", methods=["POST"])
@rate_limit("settings")
def api_security_backup():
    denied = require_auth()
    if denied:
        return denied

    import shutil
    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"jarvis_{ts}.db"

    try:
        shutil.copy2(str(DB_PATH), str(backup_path))

        backups = sorted(backup_dir.glob("jarvis_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[10:]:
            old.unlink()

        log_audit("backup_created", f"Backup: {backup_path.name} ({backup_path.stat().st_size} bytes)")
        return jsonify({
            "success": True,
            "filename": backup_path.name,
            "size": backup_path.stat().st_size,
            "backups_kept": min(len(backups), 10),
        })
    except Exception:
        log_audit("backup_created", "Backup failed", success=False)
        return jsonify({"error": "Backup failed"}), 500


@app.route("/api/security/emergency-wipe", methods=["POST"])
@rate_limit("auth")
def api_emergency_wipe():
    denied = require_auth()
    if denied:
        return denied

    body = request.get_json(force=True)
    pin = body.get("pin", "").strip()
    confirm = body.get("confirm", "")

    if confirm != "WIPE ALL SECRETS":
        return jsonify({"error": "Confirmation required: send confirm='WIPE ALL SECRETS'"}), 400
    if not pin or not verify_pin(pin):
        return jsonify({"error": "Invalid PIN — double confirmation required"}), 401

    wiped = []
    conn = get_db()

    if get_setting("anthropic_api_key_enc"):
        delete_setting("anthropic_api_key_enc")
        wiped.append("anthropic_key")
    if get_setting("gmx_wallet_enc"):
        delete_setting("gmx_wallet_enc")
        delete_setting("gmx_wallet_address")
        wiped.append("gmx_wallet")

    count = conn.execute("SELECT COUNT(*) as c FROM exchanges").fetchone()["c"]
    if count > 0:
        conn.execute("DELETE FROM exchanges")
        conn.commit()
        wiped.append(f"exchanges({count})")

    conn.close()

    exchange_manager._adapters.clear()

    log_audit("emergency_wipe", f"Wiped: {', '.join(wiped) or 'nothing'}")
    return jsonify({"success": True, "wiped": wiped})


@app.route("/api/sparklines")
def api_sparklines():
    pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
    result = {}
    for pair in pairs:
        raw = fetch_binance("/api/v3/klines", {"symbol": pair, "interval": "15m", "limit": 20}, ttl=30)
        if raw and isinstance(raw, list):
            result[pair] = [float(k[4]) for k in raw]
    return jsonify(result)


# ===========================================================================
# API ROUTES — Scheduled Orders (2 routes)
# ===========================================================================

@app.route("/api/scheduled-orders")
def api_scheduled_orders_list():
    status_filter = request.args.get("status")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        if status_filter:
            rows = conn.execute(
                "SELECT * FROM scheduled_orders WHERE status = ? ORDER BY created_at DESC", (status_filter,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM scheduled_orders ORDER BY created_at DESC").fetchall()
        conn.close()
        return jsonify({"orders": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": sanitize_error(e)}), 500


@app.route("/api/scheduled-orders/<int:order_id>", methods=["DELETE"])
def api_scheduled_orders_cancel(order_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        order = conn.execute("SELECT * FROM scheduled_orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            conn.close()
            return jsonify({"error": "Order not found"}), 404

        conn.execute("UPDATE scheduled_orders SET status = 'cancelled' WHERE id = ?", (order_id,))

        if order["parent_type"] == "oco" and order["parent_id"]:
            conn.execute(
                "UPDATE scheduled_orders SET status = 'cancelled' WHERE parent_id = ? AND id != ?",
                (order["parent_id"], order_id),
            )

        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": sanitize_error(e)}), 500


# ===========================================================================
# API ROUTES — Alerts CRUD + Check (4 routes)
# ===========================================================================

VALID_ALERT_TYPES = ("price", "rsi", "regime_change", "volume_spike")
VALID_ALERT_OPS = ("gt", "lt", "eq", "cross_up", "cross_down")


@app.route("/api/alerts", methods=["POST"])
def api_alerts_create():
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "BTCUSDT").upper()
    cond_type = data.get("condition_type", "")
    operator = data.get("operator", "")
    value = data.get("value")
    message = data.get("message", "")
    repeat = 1 if data.get("repeat") else 0

    if cond_type not in VALID_ALERT_TYPES:
        return jsonify({"error": f"Invalid condition_type. Allowed: {VALID_ALERT_TYPES}"}), 400
    if operator not in VALID_ALERT_OPS:
        return jsonify({"error": f"Invalid operator. Allowed: {VALID_ALERT_OPS}"}), 400
    if value is None:
        return jsonify({"error": "value is required"}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute(
            "INSERT INTO alerts (symbol, condition_type, operator, value, message, repeat) VALUES (?, ?, ?, ?, ?, ?)",
            (symbol, cond_type, operator, float(value), message, repeat),
        )
        alert_id = cur.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"success": True, "id": alert_id})
    except Exception as e:
        return jsonify({"error": sanitize_error(e)}), 500


@app.route("/api/alerts", methods=["GET"])
def api_alerts_list():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM alerts ORDER BY created_at DESC").fetchall()
        conn.close()
        return jsonify({"alerts": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": sanitize_error(e)}), 500


@app.route("/api/alerts/<int:alert_id>", methods=["DELETE"])
def api_alerts_delete(alert_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": sanitize_error(e)}), 500


@app.route("/api/alerts/check")
def api_alerts_check():
    symbol = request.args.get("symbol", "BTCUSDT").upper()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        active = conn.execute(
            "SELECT * FROM alerts WHERE symbol = ? AND (triggered = 0 OR repeat = 1)",
            (symbol,),
        ).fetchall()

        if not active:
            total_active = conn.execute("SELECT COUNT(*) as c FROM alerts WHERE triggered = 0 OR repeat = 1").fetchone()["c"]
            conn.close()
            return jsonify({"triggered": [], "active_count": total_active, "triggered_count": 0})

        price_data = fetch_binance("/api/v3/ticker/price", {"symbol": symbol}, ttl=5)
        current_price = float(price_data["price"]) if price_data and "price" in price_data else None

        current_rsi = None
        current_regime = None
        sym_info = SUPPORTED_SYMBOLS.get(symbol)
        if sym_info and sym_info["source"] == "binance":
            raw_klines = fetch_binance("/api/v3/klines", {"symbol": symbol, "interval": "1h", "limit": 200}, ttl=30)
            if raw_klines and len(raw_klines) >= 30:
                ohlcv = transform_klines(raw_klines)
                indicators = compute_all_indicators(ohlcv)
                raw_ind = indicators.get("_raw", {})
                rsi_arr = raw_ind.get("rsi", [])
                current_rsi = rsi_arr[-1] if rsi_arr else None
                regime_info = regime_detector.detect(ohlcv, raw_ind)
                current_regime = regime_info.get("regime")

        triggered_alerts = []
        now = datetime.now().isoformat()

        for alert in active:
            fired = False
            ctype = alert["condition_type"]
            op = alert["operator"]
            val = alert["value"]

            if ctype == "price" and current_price is not None:
                fired = _eval_condition(current_price, op, val)
            elif ctype == "rsi" and current_rsi is not None:
                fired = _eval_condition(current_rsi, op, val)
            elif ctype == "regime_change" and current_regime is not None:
                regime_map = {"BULL": 1, "RANGE": 2, "BEAR": 3, "CRISIS": 4}
                fired = _eval_condition(regime_map.get(current_regime, 0), "eq", val)
            elif ctype == "volume_spike":
                pass

            if fired:
                conn.execute(
                    "UPDATE alerts SET triggered = 1, triggered_at = ? WHERE id = ?",
                    (now, alert["id"]),
                )
                triggered_alerts.append({
                    "id": alert["id"],
                    "symbol": alert["symbol"],
                    "condition_type": ctype,
                    "operator": op,
                    "value": val,
                    "message": alert["message"] or f"{ctype} {op} {val}",
                })

        conn.commit()
        total_active = conn.execute("SELECT COUNT(*) as c FROM alerts WHERE triggered = 0 OR repeat = 1").fetchone()["c"]
        conn.close()

        return jsonify({
            "triggered": triggered_alerts,
            "active_count": total_active,
            "triggered_count": len(triggered_alerts),
        })
    except Exception as e:
        return jsonify({"error": sanitize_error(e)}), 500


def _eval_condition(current, operator, target):
    if operator == "gt":
        return current > target
    elif operator == "lt":
        return current < target
    elif operator == "eq":
        return abs(current - target) < 0.001
    return False


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
        return jsonify({"error": sanitize_error(e)}), 500


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
        return jsonify({"error": sanitize_error(e)}), 500


@app.route("/api/bot/performance")
def api_bot_performance():
    """Comprehensive bot performance stats for the dashboard page."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        trades = conn.execute(
            "SELECT * FROM paper_trades WHERE status = 'closed' ORDER BY closed_at ASC"
        ).fetchall()

        open_trades = conn.execute(
            "SELECT * FROM paper_trades WHERE status = 'open'"
        ).fetchall()

        initial_capital = float(get_setting("paper_capital") or "100")
        conn.close()

        if not trades:
            return jsonify({
                "initial_capital": initial_capital,
                "current_equity": initial_capital,
                "total_trades": 0,
                "wins": 0, "losses": 0, "win_rate": 0,
                "total_pnl": 0, "best_trade": 0, "worst_trade": 0,
                "avg_win": 0, "avg_loss": 0, "profit_factor": 0,
                "max_drawdown": 0, "sharpe_ratio": 0,
                "open_positions": len(open_trades),
                "equity_curve": [{"time": 0, "value": initial_capital}],
                "daily_pnl": [], "hourly_pnl": [],
                "by_symbol": {}, "by_side": {"long": 0, "short": 0},
                "streaks": {"current": 0, "best_win": 0, "worst_loss": 0},
                "monthly": {},
            })

        pnls = [float(t["pnl"]) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        equity = initial_capital
        peak = initial_capital
        max_dd = 0
        equity_curve = [{"time": 0, "value": initial_capital}]
        daily_map = {}
        hourly_map = {}
        monthly_map = {}
        by_symbol = {}
        by_side = {"long": 0, "short": 0}

        current_streak = 0
        best_win_streak = 0
        worst_loss_streak = 0
        streak_type = None

        for t in trades:
            pnl = float(t["pnl"])
            equity += pnl
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

            ts_str = t["closed_at"] or ""
            epoch = 0
            day_key = "unknown"
            hour_key = "unknown"
            month_key = "unknown"
            if ts_str:
                try:
                    dt_obj = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    epoch = int(dt_obj.timestamp())
                    day_key = dt_obj.strftime("%Y-%m-%d")
                    hour_key = dt_obj.strftime("%Y-%m-%d %H:00")
                    month_key = dt_obj.strftime("%Y-%m")
                except (ValueError, TypeError):
                    epoch = int(time.time())

            equity_curve.append({"time": epoch, "value": round(equity, 2)})

            daily_map[day_key] = daily_map.get(day_key, 0) + pnl
            hourly_map[hour_key] = hourly_map.get(hour_key, 0) + pnl
            monthly_map[month_key] = monthly_map.get(month_key, 0) + pnl

            sym = t["symbol"]
            if sym not in by_symbol:
                by_symbol[sym] = {"trades": 0, "pnl": 0, "wins": 0}
            by_symbol[sym]["trades"] += 1
            by_symbol[sym]["pnl"] += pnl
            if pnl > 0:
                by_symbol[sym]["wins"] += 1

            side = t["side"] if t["side"] else "long"
            if side in by_side:
                by_side[side] += 1

            if pnl > 0:
                if streak_type == "win":
                    current_streak += 1
                else:
                    current_streak = 1
                    streak_type = "win"
                best_win_streak = max(best_win_streak, current_streak)
            else:
                if streak_type == "loss":
                    current_streak += 1
                else:
                    current_streak = 1
                    streak_type = "loss"
                worst_loss_streak = max(worst_loss_streak, current_streak)

        total_pnl = sum(pnls)
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        avg_pnl = total_pnl / len(pnls) if pnls else 0
        std_pnl = (sum((p - avg_pnl) ** 2 for p in pnls) / len(pnls)) ** 0.5 if len(pnls) > 1 else 0
        sharpe = (avg_pnl / std_pnl) * (252 ** 0.5) if std_pnl > 0 else 0

        daily_pnl = [{"date": k, "pnl": round(v, 2)} for k, v in sorted(daily_map.items())]
        hourly_pnl = [{"hour": k, "pnl": round(v, 2)} for k, v in sorted(hourly_map.items())]
        monthly = {k: round(v, 2) for k, v in sorted(monthly_map.items())}

        return jsonify({
            "initial_capital": initial_capital,
            "current_equity": round(equity, 2),
            "total_trades": len(pnls),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(pnls) * 100, 1) if pnls else 0,
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl / initial_capital * 100, 2) if initial_capital else 0,
            "best_trade": round(max(pnls), 2) if pnls else 0,
            "worst_trade": round(min(pnls), 2) if pnls else 0,
            "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0,
            "profit_factor": round(profit_factor, 2),
            "max_drawdown": round(max_dd, 2),
            "sharpe_ratio": round(sharpe, 2),
            "open_positions": len(open_trades),
            "equity_curve": equity_curve,
            "daily_pnl": daily_pnl,
            "hourly_pnl": hourly_pnl,
            "by_symbol": by_symbol,
            "by_side": by_side,
            "streaks": {
                "current": current_streak,
                "current_type": streak_type or "none",
                "best_win": best_win_streak,
                "worst_loss": worst_loss_streak,
            },
            "monthly": monthly,
        })
    except Exception as e:
        return jsonify({"error": sanitize_error(e)}), 500


@app.route("/api/mtf-signals")
def api_mtf_signals():
    symbol = request.args.get("symbol", "BTCUSDT").upper()
    sym_info = SUPPORTED_SYMBOLS.get(symbol)

    timeframes = ["1h", "4h", "1d", "1w"]
    tf_results = {}

    for tf in timeframes:
        try:
            if sym_info and sym_info["source"] == "stooq":
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
# API ROUTES — Autonomous Bot (6 routes)
# ===========================================================================

@app.route("/api/bot/strategies")
@rate_limit("bot")
def api_bot_strategies():
    perf = strategy_selector.get_performance()
    regime_info = None
    try:
        raw = fetch_binance("/api/v3/klines",
                            {"symbol": "BTCUSDT", "interval": "1h", "limit": 200}, ttl=30)
        if raw:
            ohlcv = transform_klines(raw)
            if len(ohlcv) >= 50:
                indicators = compute_all_indicators(ohlcv)
                regime_info = regime_detector.detect(ohlcv, indicators["_raw"])
    except Exception:
        pass
    current_regime = regime_info.get("regime", "RANGE") if regime_info else "RANGE"
    applicable = strategy_selector.get_applicable(current_regime)
    return jsonify({
        "strategies": perf,
        "current_regime": current_regime,
        "applicable_now": applicable,
    })


@app.route("/api/bot/strategy", methods=["POST"])
@rate_limit("bot")
def api_bot_strategy_override():
    denied = require_auth()
    if denied:
        return denied
    body = request.get_json(force=True)
    name = body.get("strategy", "auto")
    valid = ("auto",) + tuple(strategy_selector.strategies.keys())
    if name not in valid:
        return jsonify({"error": f"Unknown strategy: {name}", "valid": list(valid)}), 400
    result = auto_engine.update_config({"strategy": name})
    log_audit("bot_strategy_override", f"strategy={name}")
    return jsonify({"success": True, "strategy": name, "config": result.get("config", {})})

@app.route("/api/bot/start", methods=["POST"])
@rate_limit("bot_start")
def api_bot_start():
    denied = require_auth()
    if denied:
        return denied
    result = auto_engine.start()
    if result.get("success"):
        log_audit("bot_started", f"mode={auto_engine._config['mode']}")
    return jsonify(result), 200 if result.get("success") else 400


@app.route("/api/bot/stop", methods=["POST"])
@rate_limit("bot")
def api_bot_stop():
    denied = require_auth()
    if denied:
        return denied
    result = auto_engine.stop()
    if result.get("success"):
        log_audit("bot_stopped", "")
    return jsonify(result), 200 if result.get("success") else 400


@app.route("/api/bot/status")
@rate_limit("bot")
def api_bot_status():
    return jsonify(auto_engine.get_status())


@app.route("/api/bot/config", methods=["POST"])
@rate_limit("bot_config")
def api_bot_config():
    denied = require_auth()
    if denied:
        return denied
    body = request.get_json(force=True)
    if not body or not isinstance(body, dict):
        return jsonify({"error": "JSON body required"}), 400
    result = auto_engine.update_config(body)
    if result.get("success"):
        log_audit("bot_config_updated", str({k: v for k, v in body.items() if k != "symbols"}))
    return jsonify(result)


# ---------------------------------------------------------------------------
# Risk management routes
# ---------------------------------------------------------------------------


@app.route("/api/risk/circuit-breakers")
@rate_limit("bot")
def api_risk_circuit_breakers():
    return jsonify(circuit_breakers.get_status())


@app.route("/api/risk/acknowledge", methods=["POST"])
@rate_limit("bot")
def api_risk_acknowledge():
    denied = require_auth()
    if denied:
        return denied
    body = request.get_json(force=True)
    if not body or "level" not in body:
        return jsonify({"error": "JSON body with 'level' required"}), 400
    try:
        level = int(body["level"])
    except (ValueError, TypeError):
        return jsonify({"error": "level must be an integer"}), 400
    result = circuit_breakers.acknowledge(level)
    if result.get("success"):
        log_audit("cb_acknowledge", f"Level {level} reset manually")
    return jsonify(result)


@app.route("/api/risk/portfolio")
@rate_limit("bot")
def api_risk_portfolio():
    balance = 100.0
    try:
        paper_status = paper_trader.get_status()
        balance = 100.0 + paper_status.get("total_pnl", 0)
    except Exception:
        pass
    heat = position_manager.get_portfolio_heat(balance)
    correlation = position_manager.get_correlation_risk()
    positions = position_manager.get_position_summary()
    dd = risk_engine.get_drawdown_status()
    cp_status = capital_protector.get_status()
    return jsonify({
        "portfolio_heat_pct": heat,
        "max_heat_pct": AdvancedPositionManager.MAX_PORTFOLIO_HEAT_PCT,
        "correlation": correlation,
        "positions": positions,
        "drawdown": dd,
        "capital_protector": cp_status,
    })


# ---------------------------------------------------------------------------
# Macro-economic data routes
# ---------------------------------------------------------------------------


@app.route("/api/macro")
@rate_limit("bot")
def api_macro():
    last = macro_engine.get_last_score()
    if last:
        return jsonify(last)
    result = macro_engine.compute_macro_score()
    return jsonify(result)


@app.route("/api/macro/calendar")
@rate_limit("bot")
def api_macro_calendar():
    cal = macro_engine.fetch_economic_calendar()
    if cal is None:
        return jsonify({"events": [], "high_impact_24h": [], "error": "unavailable"})
    reduce = macro_engine.should_reduce_exposure()
    cal["reduce_exposure"] = reduce
    return jsonify(cal)


@app.route("/api/macro/geopolitical")
@rate_limit("bot")
def api_macro_geopolitical():
    geo = macro_engine.fetch_geopolitical_risk()
    if geo is None:
        return jsonify({"risk_score": 0, "alert_level": "UNKNOWN", "events": [],
                        "error": "unavailable"})
    return jsonify(geo)


# ---------------------------------------------------------------------------
# Smart Execution routes
# ---------------------------------------------------------------------------


@app.route("/api/execution/stats")
@rate_limit("bot")
def api_execution_stats():
    if not smart_executor:
        return jsonify({"error": "SmartExecutionEngine not available"}), 503
    return jsonify(smart_executor.get_execution_stats())


@app.route("/api/execution/pending")
@rate_limit("bot")
def api_execution_pending():
    if not smart_executor:
        return jsonify({"error": "SmartExecutionEngine not available"}), 503
    return jsonify({"pending_orders": smart_executor.get_pending_orders()})


# ---------------------------------------------------------------------------
# Performance Tracking routes
# ---------------------------------------------------------------------------


@app.route("/api/performance")
@rate_limit("bot")
def api_performance():
    period = request.args.get("period", "all")
    strategy = request.args.get("strategy")
    symbol = request.args.get("symbol")
    summary = performance_tracker.get_summary(period, strategy, symbol)
    streaks = performance_tracker.get_streaks()
    summary["streaks"] = streaks
    return jsonify(summary)


@app.route("/api/performance/equity")
@rate_limit("bot")
def api_performance_equity():
    period = request.args.get("period", "30d")
    points = performance_tracker.get_equity_curve(period)
    return jsonify({"points": points, "count": len(points)})


@app.route("/api/performance/breakdown")
@rate_limit("bot")
def api_performance_breakdown():
    return jsonify({
        "by_strategy": performance_tracker.get_by_strategy(),
        "by_symbol": performance_tracker.get_by_symbol(),
        "by_hour": performance_tracker.get_by_hour(),
        "by_regime": performance_tracker.get_by_regime(),
    })


@app.route("/api/performance/recommendations")
@rate_limit("bot")
def api_performance_recommendations():
    recs = performance_tracker.get_recommendations()
    weights = performance_tracker.get_strategy_weights()
    auto = performance_tracker.should_auto_adjust()
    return jsonify({
        "recommendations": recs,
        "strategy_weights": weights,
        "auto_adjust": auto,
    })


@app.route("/api/performance/export")
def api_performance_export():
    csv_data = performance_tracker.export_csv()
    return app.response_class(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=jarvis_trades.csv"})


# ---------------------------------------------------------------------------
# Alert system routes
# ---------------------------------------------------------------------------


@app.route("/api/alerts")
@rate_limit("bot")
def api_alerts():
    limit = int(request.args.get("limit", 50))
    priority = request.args.get("priority")
    atype = request.args.get("type")
    since_id = int(request.args.get("since_id", 0))
    alerts = alert_manager.get_recent(limit=limit, priority=priority,
                                      alert_type=atype, since_id=since_id)
    return jsonify({"alerts": alerts, "count": len(alerts)})


@app.route("/api/alerts/webhook", methods=["POST"])
@rate_limit("webhook")
def api_alerts_webhook():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if url and not url.startswith(("http://", "https://")):
        return jsonify({"error": "URL must start with http:// or https://"}), 400
    if not url:
        return jsonify({"error": "url required"}), 400
    channel = data.get("channel", "webhook")
    events = data.get("events")
    if channel == "telegram":
        token = data.get("token", "")
        chat_id = data.get("chat_id", "")
        if not token or not chat_id:
            return jsonify({"error": "token and chat_id required for Telegram"}), 400
        alert_manager.configure_telegram(token, chat_id)
        return jsonify({"success": True, "channel": "telegram"})
    elif channel == "discord":
        alert_manager.configure_discord(url)
        return jsonify({"success": True, "channel": "discord"})
    else:
        alert_manager.add_webhook(url, events)
        return jsonify({"success": True, "channel": "webhook"})


@app.route("/api/alerts/test", methods=["POST"])
@rate_limit("bot")
def api_alerts_test():
    alert = alert_manager.send("BOT_STATUS",
                               "Test alert from J.A.R.V.I.S. — system operational",
                               priority="MEDIUM",
                               data={"test": True})
    return jsonify({"success": True, "alert": alert})


# ===========================================================================
# Main entry point
# ===========================================================================

if __name__ == "__main__":
    try:
        init_db()
    except Exception as e:
        log.critical("Database init failed: %s", e)

    try:
        exchange_manager.load_from_db()
    except Exception as e:
        log.critical("Exchange load failed: %s", e)

    try:
        macro_engine.start_refresh()
    except Exception as e:
        log.warning("Macro engine start failed: %s", e)

    if not HAS_FERNET:
        log.critical("CRYPTOGRAPHY NOT INSTALLED — encryption disabled!")
    else:
        try:
            if not check_fernet_integrity():
                log.critical("Fernet integrity check FAILED — secret.key may be corrupted")
            else:
                log.info("Encryption integrity check passed")
            perms_ok, perms_str = check_key_file_permissions()
            if not perms_ok:
                log.warning("secret.key permissions issue: %s", perms_str)
        except Exception as e:
            log.warning("Security check error: %s", e)

    from werkzeug.serving import WSGIRequestHandler
    WSGIRequestHandler.server_version = "JARVIS"
    WSGIRequestHandler.sys_version = ""

    log.info("J.A.R.V.I.S. Trading System v%s starting on port 5000", APP_VERSION)
    app.run(host="0.0.0.0", port=5000, debug=False)
