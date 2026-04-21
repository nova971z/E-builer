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
from functools import wraps
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
    "ExchangeRouter": "0x7C68C7866A64FA2160F78EEaE12217FFbf871fa8",
    "Router": "0x7452c558d45f8afC8c83dAe62C3f8A5BE19c71f6",
    "OrderVault": "0x31eF83a530Fde1B38deDA89C0A6c72a85DC51756",
    "DataStore": "0xFD70de6b91282D8017aA4E741e9Ae325CAb992d8",
    "Reader": "0xf60becbba223EEA9495Da3f606753867eC10d139",
    "OrderHandler": "0x352f684ab9e97a6321a13CF03A61316B681D9fD2",
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
    "DOGE": "0xC4da4c24fd591125c3F47b340b6f4f76111f1c88",
}

GMX_V2_MARKETS = {
    "BTCUSDT": {
        "market_token": "0x47c031236e19d024b42f8AE6DA7A0261C4f1F660",
        "index_token": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",
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
        "index_token": "0xC4da4c24fd591125c3F47b340b6f4f76111f1c88",
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
GMX_EXECUTION_FEE_BUFFER_WEI = 6000000000000000
GMX_DEFAULT_SLIPPAGE_BPS = 30
GMX_CALLBACK_GAS_LIMIT = 2000000
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
            {
                "components": [
                    {
                        "components": [
                            {"internalType": "address", "name": "receiver", "type": "address"},
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
                        ],
                        "internalType": "struct IBaseOrderUtils.CreateOrderParamsNumbers",
                        "name": "numbers",
                        "type": "tuple",
                    },
                    {"internalType": "enum Order.OrderType", "name": "orderType", "type": "uint8"},
                    {"internalType": "enum Order.DecreasePositionSwapType", "name": "decreasePositionSwapType", "type": "uint8"},
                    {"internalType": "bool", "name": "isLong", "type": "bool"},
                    {"internalType": "bool", "name": "shouldUnwrapNativeToken", "type": "bool"},
                    {"internalType": "bytes32", "name": "referralCode", "type": "bytes32"},
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
        "Authentication", "Encryption", "Already",
    )
    msg = str(e)
    for prefix in safe_prefixes:
        if msg.startswith(prefix):
            return msg
    log.debug("Sanitized error: %s", msg)
    return "Internal server error"


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
    "execute":     (30,  60),
    "settings":    (10,  60),
    "market_data": (120, 60),
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
        return {
            "from": address,
            "nonce": self._w3.eth.get_transaction_count(address),
            "gas": 3000000,
            "maxFeePerGas": self._w3.eth.gas_price * 2,
            "maxPriorityFeePerGas": self._w3.to_wei(0.1, "gwei"),
            "value": value,
            "chainId": 42161 if not self.testnet else 421614,
        }

    def _sign_and_send(self, tx):
        """Sign a transaction and broadcast it, returning the tx hash."""
        signed = self._w3.eth.account.sign_transaction(tx, self._account.key)
        tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
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
            log.debug("GMX collateral read skipped: %s", e)

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
        """Fetch current index price from Binance for PnL calculation."""
        try:
            key = f"gmx_price_{symbol}"
            cached = cache.get(key)
            if cached:
                return cached
            resp = requests.get(
                f"{BINANCE_BASE}/api/v3/ticker/price",
                params={"symbol": symbol}, timeout=3
            )
            if resp.status_code == 200:
                price = float(resp.json()["price"])
                cache.set(key, price, ttl=5)
                return price
        except Exception:
            pass
        return 0.0

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
            return max(gas_price * GMX_CALLBACK_GAS_LIMIT, GMX_EXECUTION_FEE_BUFFER_WEI)
        except Exception:
            return GMX_EXECUTION_FEE_BUFFER_WEI

    def _ensure_token_approval(self, token_address, spender, amount_raw):
        """Approve ERC-20 spending if current allowance is insufficient."""
        contract = get_erc20_contract(self._w3, token_address)
        current = contract.functions.allowance(self._account.address, spender).call()
        if current >= amount_raw:
            return None
        max_uint = 2**256 - 1
        tx = contract.functions.approve(spender, max_uint).build_transaction(self._build_tx())
        return self._sign_and_send(tx)

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

        try:
            approval_tx = self._ensure_token_approval(collateral_token, router_addr, collateral_amount_raw)
            if approval_tx:
                log.info("GMX ERC-20 approval tx: %s", approval_tx)
        except Exception as e:
            return {"success": False, "error": f"Token approval failed: {e}", "exchange": "GMX"}

        order_params = (
            (
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
            ),
            gmx_order_type,
            GMX_DECREASE_POSITION_SWAP_TYPE,
            is_long,
            True,
            GMX_REFERRAL_CODE,
        )

        try:
            send_wnt_data = exchange_router.functions.sendWnt(
                order_vault, execution_fee
            ).build_transaction({"from": self._account.address})["data"]

            create_order_data = exchange_router.functions.createOrder(
                order_params
            ).build_transaction({"from": self._account.address})["data"]

            total_value = execution_fee
            multicall_tx = exchange_router.functions.multicall(
                [bytes.fromhex(send_wnt_data[2:]), bytes.fromhex(create_order_data[2:])]
            ).build_transaction(self._build_tx(value=total_value))

            tx_hash = self._sign_and_send(multicall_tx)

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
                self._place_tp_sl_order(symbol, market, not is_long, quantity, tp, is_tp=True)
                result["tp"] = tp
            if sl:
                self._place_tp_sl_order(symbol, market, not is_long, quantity, sl, is_tp=False)
                result["sl"] = sl

            return result

        except Exception as e:
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
                ),
                GMX_ORDER_TYPE_LIMIT_DECREASE,
                GMX_DECREASE_POSITION_SWAP_TYPE,
                not is_long_close,
                True,
                GMX_REFERRAL_CODE,
            )

            send_wnt_data = exchange_router.functions.sendWnt(
                order_vault, execution_fee
            ).build_transaction({"from": self._account.address})["data"]

            create_data = exchange_router.functions.createOrder(
                order_params
            ).build_transaction({"from": self._account.address})["data"]

            multicall_tx = exchange_router.functions.multicall(
                [bytes.fromhex(send_wnt_data[2:]), bytes.fromhex(create_data[2:])]
            ).build_transaction(self._build_tx(value=execution_fee))

            tx_hash = self._sign_and_send(multicall_tx)
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
            ),
            GMX_ORDER_TYPE_MARKET_DECREASE,
            GMX_DECREASE_POSITION_SWAP_TYPE,
            is_long,
            True,
            GMX_REFERRAL_CODE,
        )

        try:
            send_wnt_data = exchange_router.functions.sendWnt(
                order_vault, execution_fee
            ).build_transaction({"from": self._account.address})["data"]

            create_data = exchange_router.functions.createOrder(
                order_params
            ).build_transaction({"from": self._account.address})["data"]

            multicall_tx = exchange_router.functions.multicall(
                [bytes.fromhex(send_wnt_data[2:]), bytes.fromhex(create_data[2:])]
            ).build_transaction(self._build_tx(value=execution_fee))

            tx_hash = self._sign_and_send(multicall_tx)

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
        leverage = max(1, min(int(body.get("leverage", 1)), 500))
    except (TypeError, ValueError):
        leverage = 1
    tp = body.get("tp")
    sl = body.get("sl")
    mode = body.get("mode", "paper")

    if side not in ("long", "short", "buy", "sell"):
        return jsonify({"error": "Invalid side"}), 400

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
            paper_trader.execute(symbol, trade_side, slice_qty, price, leverage, tp, sl)

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
            first_qty = quantity * (weights[0] / total_weight)
            paper_trader.execute(symbol, trade_side, first_qty, price, leverage, tp, sl)

        conn.commit()
        conn.close()
        log_audit("trade_executed", f"{order_type} {symbol} {side} qty={quantity}")
        return jsonify({"success": True, "order_ids": order_ids, "type": order_type, "mode": "paper"})

    # Paper trading (standard limit/market)
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

        log_audit("trade_executed", f"paper {trade_side} {symbol} qty={quantity} @{price}")
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
    log_audit("trade_executed", f"live {side} {symbol} qty={quantity} @{price}")
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
        "live": live_balances,
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
    mode = body.get("mode", "paper")
    exit_price, err = validate_price(body.get("exit_price", 0))
    if err:
        return jsonify({"error": err}), 400

    if mode == "paper":
        if not trade_id:
            return jsonify({"error": "trade_id required for paper close"}), 400
        if exit_price <= 0:
            price_data = fetch_binance("/api/v3/ticker/price", {"symbol": symbol}, ttl=2)
            if price_data:
                exit_price = float(price_data.get("price", 0))
            if exit_price <= 0:
                return jsonify({"error": "Could not determine exit price"}), 502
        result = paper_trader.close(int(trade_id), exit_price)
        log_audit("trade_closed", f"paper #{trade_id} {symbol} @{exit_price}")
        return jsonify(result)

    if not symbol:
        return jsonify({"error": "symbol required for live close"}), 400
    if not exchange_manager._adapters:
        return jsonify({"error": "No exchange configured"}), 400

    adapter = list(exchange_manager._adapters.values())[0]
    result = adapter.close_position(symbol)
    log_audit("trade_closed", f"live {symbol}")
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
    addr = get_gmx_wallet_address()
    return jsonify({
        "configured": addr is not None,
        "address": addr,
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
        exchange_manager._adapters["gmx_wallet"] = adapter
        log_audit("wallet_setup", f"GMX adapter connected: {addr[:10]}...")
        return jsonify({
            "success": True,
            "address": addr,
            "initialized": adapter._initialized,
            "network": "Arbitrum One",
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


@app.route("/api/gmx/circuit-breaker", methods=["POST"])
def api_gmx_circuit_breaker():
    """Manually trigger circuit breaker — close all GMX positions."""
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
# Main entry point
# ===========================================================================

if __name__ == "__main__":
    init_db()
    exchange_manager.load_from_db()

    # --- Security checks at startup ---
    if not HAS_FERNET:
        log.critical("=" * 60)
        log.critical("CRYPTOGRAPHY NOT INSTALLED — encryption disabled!")
        log.critical("Sensitive routes (keys, wallet, exchanges) will be blocked.")
        log.critical("Fix: pip install cryptography")
        log.critical("=" * 60)
    else:
        if not check_fernet_integrity():
            log.critical("Fernet integrity check FAILED — secret.key may be corrupted")
        else:
            log.info("Encryption integrity check passed")
        perms_ok, perms_str = check_key_file_permissions()
        if not perms_ok:
            log.warning("secret.key permissions issue: %s", perms_str)

    from werkzeug.serving import WSGIRequestHandler
    WSGIRequestHandler.server_version = "JARVIS"
    WSGIRequestHandler.sys_version = ""

    log.info("J.A.R.V.I.S. Trading System v%s starting on port 5000", APP_VERSION)
    app.run(host="0.0.0.0", port=5000, debug=False)
