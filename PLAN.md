# PLAN.md — J.A.R.V.I.S. Trading System v3.0 — Roadmap & Navigation

> **Fichier persistant** — Ce fichier est la source de vérité pour toutes les tâches
> d'amélioration du dashboard. Il survit aux compressions de contexte et aux
> changements de session. **Toujours le relire avant de commencer une étape.**

---

## 0. RÈGLES ANTI-PERTE DE MÉMOIRE

### 0.1 Protocole de début d'étape

Avant de coder quoi que ce soit, exécuter systématiquement :

```
1. Lire PLAN.md (ce fichier) — section de l'étape concernée
2. Lire les coordonnées de navigation (Section 2) pour localiser les zones d'insertion
3. Vérifier le statut de l'étape dans le tableau de suivi (Section 5)
4. Marquer l'étape [EN COURS] dans le tableau de suivi
```

### 0.2 Protocole de fin d'étape

Après chaque étape terminée :

```
1. Vérifier la syntaxe : python3 -m py_compile server.py (si server.py modifié)
2. Mettre à jour les coordonnées de navigation (Section 2) avec les nouveaux numéros de ligne
3. Marquer l'étape [FAIT] dans le tableau de suivi (Section 5)
4. Commit avec message : feat: step XX — <description courte>
5. Push sur la branche : git push -u origin claude/jarvis-trading-dashboard-HGW7A
```

### 0.3 Règles de numérotation

| Élément | Format | Exemple |
|---------|--------|---------|
| Étape principale | `X.0` | `1.0 Multi-Timeframe Analysis` |
| Sous-tâche | `X.Y` | `1.3 Ajouter la route API` |
| Sous-sous-tâche | `X.Y.Z` | `1.3.2 Gérer le cache TTL` |
| Commit | `step XX` | `feat: step 29 — multi-timeframe analysis panel` |
| Numéro de ligne | `L:NNN` | `dashboard.html L:1288` |

### 0.4 Conventions de code

| Règle | Détail |
|-------|--------|
| Python | Pas de numpy/pandas — calculs pure Python |
| JS | `function` declarations uniquement, pas de arrow functions |
| CSS | Variables dans `:root`, inline dans `<style>` de dashboard.html |
| Insertion CSS | Toujours AVANT `</style>` (repère : `dashboard.html L:1175`) |
| Insertion HTML | Identifier la zone exacte via Section 2 |
| Insertion JS | Toujours AVANT `// ========== INIT ON DOM READY ==========` (repère : `dashboard.html L:3142`) |
| Insertion route | Toujours AVANT `@app.route("/")` (repère : `server.py L:2785`) |
| Fichiers | Ne jamais créer de nouveau fichier .py ou .js — architecture single-file |
| Indicateurs | Pas de dépendances lourdes — tout en pure Python |

### 0.5 Stratégie de navigation rapide

Chaque étape de ce plan contient des **coordonnées d'insertion** au format :

```
INSERTION CSS  → dashboard.html L:1173  (avant </style>)
INSERTION HTML → dashboard.html L:XXXX  (zone spécifique documentée)
INSERTION JS   → dashboard.html L:3141  (avant INIT ON DOM READY)
INSERTION ROUTE → server.py L:2783      (avant la route "/")
```

Ces coordonnées sont mises à jour après chaque étape dans la **Section 2 — Carte de Navigation**.
Quand les lignes bougent après une insertion, recalculer le décalage :
`nouvelle_ligne = ancienne_ligne + nombre_de_lignes_ajoutées_avant`

### 0.6 Fichiers du projet (ne jamais modifier cette liste)

| Fichier | Rôle | Modifiable |
|---------|------|------------|
| `server.py` | Backend Flask unique | OUI |
| `dashboard.html` | Frontend SPA unique | OUI |
| `lw-charts.js` | TradingView Charts v4.2.1 vendored | NON |
| `CLAUDE.md` | Conventions Claude Code | OUI (référence PLAN.md) |
| `PLAN.md` | Ce fichier — roadmap & navigation | OUI (mise à jour après chaque étape) |
| `requirements.txt` | Dépendances Python | OUI (si nouvelle dep légère) |
| `scripts/*.sh` | Scripts opérationnels | OUI (si nouvelle route à tester) |

### 0.7 Numérotation des commits

Les 28 premiers steps (commits existants) couvrent la construction initiale.
Les nouvelles étapes d'amélioration commencent à **step 29** :

| Commit | Étape | Feature |
|--------|-------|---------|
| step 29 | 1.0 | Multi-Timeframe Analysis |
| step 30 | 2.0 | Portfolio Tracker & Equity Curve |
| step 31 | 3.0 | Alertes & Notifications |
| step 32 | 4.0 | Drawing Tools |
| step 33 | 5.0 | Advanced Order Types |
| step 34 | 6.0 | Effets Sonores |
| step 35 | 7.0 | Sparklines |
| step 36 | 8.0 | Heatmap |
| step 37 | 9.0 | Responsive Mobile |
| step 38 | 10.0 | Dark/Light Mode |

---
## 1. CARTE DE NAVIGATION — COORDONNÉES EXACTES

> **Usage** — Avant chaque étape, consulter cette carte pour localiser
> précisément les zones d'insertion. Après chaque étape, mettre à jour
> les numéros de ligne qui ont bougé (décalage = lignes ajoutées avant la zone).

---

### 1.1 POINTS D'INSERTION CRITIQUES (ancres principales)

| Ancre | Fichier | Ligne | Repère textuel |
|-------|---------|-------|----------------|
| FIN CSS | `dashboard.html` | `L:1175` | `</style>` |
| DEBUT BODY | `dashboard.html` | `L:1177` | `<body>` |
| FIN BODY HTML | `dashboard.html` | `L:1580` | `<!-- Lightweight Charts -->` |
| DEBUT JS | `dashboard.html` | `L:1582` | `<script>` |
| FIN GLOBAL STATE | `dashboard.html` | `L:1614` | fin du bloc `indicatorState` |
| FIN UTILITIES | `dashboard.html` | `L:1635` | fin de `epochToLocal()` |
| AVANT INIT | `dashboard.html` | `L:3142` | `// ========== INIT ON DOM READY ==========` |
| FIN INIT | `dashboard.html` | `L:3173` | `</script>` |
| AVANT ROUTE "/" | `server.py` | `L:2785` | `@app.route("/")` |
| AVANT MAIN | `server.py` | `L:2799` | `if __name__ == "__main__":` |
| FIN FICHIER | `server.py` | `L:2803` | `app.run(...)` |

---

### 1.2 dashboard.html — CSS (L:8 → L:1175)

| Zone CSS | Lignes | Sélecteurs clés |
|----------|--------|-----------------|
| **Variables :root** | `L:9 → L:40` | `--bg`, `--surface`, `--green`, `--red`, `--accent`, `--yellow` |
| **Reset & Base** | `L:41 → L:62` | `*`, `body`, `html`, scrollbar |
| **Navbar** | `L:64 → L:161` | `.navbar`, `.navbar-logo`, `.btn-nav`, `.btn-kill`, `.navbar-clock` |
| **Asset Bar** | `L:163 → L:227` | `.asset-bar`, `.asset-selector`, `.asset-price`, `.asset-stat`, `.asset-shortcuts` |
| **Main Layout** | `L:229 → L:234` | `.main-layout` (CSS grid 3 colonnes) |
| **Chart Area** | `L:235 → L:354` | `.chart-area`, `.chart-tabs`, `.chart-toolbar`, `.toolbar-toggle`, `.chart-main-wrap`, `.chart-ohlcv-overlay`, `.subchart-wrap`, `.subchart-label` |
| **Drawing Toolbar** | `L:356 → L:379` | `.draw-toolbar`, `.draw-toolbar button` |
| **Right Panel** | `L:381 → L:389` | `.right-panel` |
| **Order Book** | `L:391 → L:509` | `.orderbook`, `.ob-rows`, `.ob-row`, `.ob-spread`, `.ob-ratio-bar` |
| **Order Form** | `L:511 → L:673` | `.order-form`, `.of-tabs`, `.of-margin-mode`, `.of-leverage`, `.of-type-tabs`, `.of-field`, `.of-pct-btns`, `.of-tpsl`, `.of-info`, `.of-actions`, `.btn-long`, `.btn-short` |
| **Wallet** | `L:675 → L:707` | `.wallet-section`, `.wallet-row`, `.wallet-actions` |
| **Bottom Panel** | `L:709 → L:806` | `.bottom-panel`, `.bp-tabs`, `.bp-table-wrap`, `.bp-table`, `.bp-empty` |
| **Recent Trades** | `L:808 → L:827` | `.trades-list`, `.t-row`, `.t-price`, `.t-qty`, `.t-time` |
| **JARVIS Chat** | `L:829 → L:949` | `.jarvis-chat`, `.jc-header`, `.jc-messages`, `.jc-msg`, `.jc-quick-btns`, `.jc-input-wrap`, `.btn-mic` |
| **Alert Banners** | `L:951 → L:993` | `.alert-banner`, `.alert-kill`, `.alert-event`, `.alert-drawdown`, `.alert-diptop`, `@keyframes slide-down` |
| **Footer** | `L:994 → L:1067` | `.footer`, `.ft-status`, `.ft-dot`, `.ft-ticker`, `.ft-ticker-inner`, `.ft-ticker-item`, `.ft-info`, `.ft-regime`, `.ft-mode`, `@keyframes ticker-scroll` |
| **Modals** | `L:1069 → L:1147` | `.modal-overlay`, `.modal`, `.modal-header`, `.modal-body`, `.modal-field`, `.modal-footer` |
| **Exchange List** | `L:1149 → L:1174` | `.exchange-list`, `.exchange-item` |
| **>>> INSÉRER ICI** | `L:1174` | **Nouvelle CSS → avant L:1175 (`</style>`)** |

---

### 1.3 dashboard.html — HTML BODY (L:1177 → L:1579)

| Zone HTML | Lignes | IDs / Classes clés |
|-----------|--------|---------------------|
| **Navbar** | `L:1179 → L:1198` | `#btn-killswitch`, `#clock` |
| **Alert Banners** | `L:1200 → L:1216` | `#alert-kill`, `#alert-event`, `#alert-drawdown`, `#alert-diptop` |
| **Asset Bar** | `L:1218 → L:1244` | `#sym-select`, `#asset-price`, `#stat-change`, `#stat-high`, `#stat-low`, `#stat-vol`, `#stat-funding`, `#stat-oi` |
| **Main Layout (ouverture)** | `L:1246 → L:1248` | `div.main-layout` |
| **Drawing Toolbar** | `L:1249 → L:1260` | `div.draw-toolbar` (boutons dessin) |
| **Chart Area** | `L:1261 → L:1330` | `#chart-container`, `#ohlcv-overlay`, `#rsi-container`, `#macd-container` |
| **Chart Tabs** | `L:1264 → L:1271` | Boutons Chart / Info / Depth |
| **Chart Toolbar** | `L:1273 → L:1290` | Timeframes (1m→1w) + Indicateurs (BB, EMA, VOL) |
| **Main Chart** | `L:1292 → L:1303` | `#chart-container`, `#ov-o/h/l/c/v` |
| **RSI Sub-chart** | `L:1304 → L:1309` | `#rsi-container` |
| **MACD Sub-chart** | `L:1310 → L:1315` | `#macd-container` |
| **Bottom Panel** | `L:1316 → L:1330` | `#pos-count`, `#bp-content` (tabs: Positions, Open Orders, History, Journal) |
| **Right Panel (ouverture)** | `L:1332 → L:1333` | `div.right-panel` |
| **Order Book** | `L:1334 → L:1365` | `#ob-asks`, `#ob-bids`, `#ob-spread`, `#spread-pct`, `#ratio-buy`, `#ratio-sell` |
| **Order Form** | `L:1367 → L:1422` | `#order-price`, `#order-qty`, `#order-tp`, `#order-sl`, `#lev-display`, `#qty-unit` |
| **Wallet** | `L:1424 → L:1435` | `#w-balance`, `#w-equity`, `#w-available`, `#w-pnl` |
| **Recent Trades** | `L:1436 → L:1447` | `#trades-list` |
| **Fin Main Layout** | `L:1448` | `</div><!-- /main-layout -->` |
| **JARVIS Chat** | `L:1450 → L:1472` | `#jarvis-chat`, `#jc-messages`, `#jc-input`, `#btn-mic` |
| **Settings Modal** | `L:1474 → L:1507` | `#modal-settings`, `#set-api-key`, `#set-default-symbol`, `#set-capital` |
| **Exchange Modal** | `L:1509 → L:1542` | `#modal-exchange`, `#ex-type`, `#ex-name`, `#ex-key`, `#ex-secret` |
| **Kill Switch Modal** | `L:1544 → L:1560` | `#modal-kill` |
| **Footer** | `L:1562 → L:1578` | `#ft-dot`, `#ft-net`, `#ft-ticker`, `#ft-regime`, `#ft-signal`, `#ft-fg`, `#ft-dd`, `#ft-mode` |
| **>>> INSÉRER HTML** | `L:1579` | **Nouveau HTML → avant L:1580 (`<!-- Lightweight Charts -->`)** |

---

### 1.4 dashboard.html — JAVASCRIPT (L:1582 → L:3173)

| Zone JS | Lignes | Fonctions |
|---------|--------|-----------|
| **Global State** | `L:1585 → L:1614` | `API`, `currentSymbol`, `currentInterval`, `candleData`, chart/series refs, `indicatorState` |
| **Utilities** | `L:1616 → L:1635` | `fmt()`, `fmtK()`, `$()`, `epochToLocal()` |
| **Chart Theme** | `L:1637 → L:1671` | `chartOptions` (objet de config TradingView) |
| **Init Main Chart** | `L:1672 → L:1720` | `initMainChart()` |
| **Init Sub-Charts** | `L:1722 → L:1793` | `subChartOptions`, `initRSIChart()`, `initMACDChart()` |
| **Sync Time Scales** | `L:1795 → L:1828` | `syncTimeScales()` |
| **Load Candles** | `L:1830 → L:1874` | `loadCandles(symbol, interval)` |
| **Load Indicators** | `L:1876 → L:1940` | `loadIndicators(symbol, interval)` |
| **Indicator Overlay Helpers** | `L:1942 → L:1998` | `buildOverlayData()`, `applyBollinger()`, `removeBollinger()`, `applyEMA()`, `removeEMA()` |
| **Toggle Indicators** | `L:2000 → L:2017` | `toggleIndicator(key)` |
| **Change Symbol/TF** | `L:2019 → L:2050` | `changeSymbol(sym)`, `changeTF(tf)` |
| **Display Helpers** | `L:2052 → L:2076` | `updateAssetPrice()`, `updateRegimeDisplay()`, `updateSignalDisplay()` |
| **Clock** | `L:2077 → L:2082` | `updateClock()` |
| **Order Book** | `L:2083 → L:2171` | `obLastPrice`, `obLastDirection`, `loadOrderBook(symbol)` |
| **Recent Trades** | `L:2173 → L:2199` | `loadTrades(symbol)` |
| **Ticker** | `L:2201 → L:2245` | `loadTicker()` |
| **Price Data** | `L:2247 → L:2271` | `loadPriceData(symbol)` |
| **Funding + Sentiment** | `L:2273 → L:2306` | `loadFunding(symbol)`, `loadSentiment(symbol)` |
| **Fear & Greed** | `L:2308 → L:2324` | `loadFearGreed()` |
| **Drawdown** | `L:2326 → L:2349` | `loadDrawdown()` |
| **Kill Switch Status** | `L:2351 → L:2370` | `loadKillSwitchStatus()` |
| **Bottom Panel Tabs** | `L:2372 → L:2380` | `switchBPTab(tab)` |
| **Positions Table** | `L:2382 → L:2433` | `loadPositions()` |
| **Paper Trade History** | `L:2435 → L:2475` | `loadPaperHistory()` |
| **Order Form State** | `L:2477 → L:2482` | `orderTab`, `marginMode`, `orderType`, `leverage` |
| **Leverage Slider** | `L:2483 → L:2489` | `updateLeverage(val)` |
| **Order Tab/Type Switch** | `L:2490 → L:2527` | `switchOrderTab()`, `switchOrderType()` |
| **Margin Mode** | `L:2528 → L:2528` | (toggle isolated/cross) |
| **Field Adjustments** | `L:2529 → L:2569` | `adjustField()`, `getTickSize()`, `getQtyStep()`, `getPriceDecimals()`, `getQtyDecimals()` |
| **Qty Percentage** | `L:2571 → L:2582` | `setQtyPct(pct)` |
| **Order Info** | `L:2584 → L:2602` | `updateOrderInfo()` |
| **Execute Order** | `L:2604 → L:2661` | `executeOrder(side)` |
| **Close Position** | `L:2663 → L:2686` | `closePosition(posId)` |
| **Toast Notifications** | `L:2688 → L:2698` | `showToast(msg, type)` — inline CSS, pas de classe |
| **Paper Status** | `L:2700 → L:2720` | `loadPaperStatus()` |
| **Wallet / Balance** | `L:2722 → L:2741` | `loadWallet()` |
| **Kill Switch** | `L:2743 → L:2780` | `toggleKillSwitch()`, `confirmKillSwitch()`, `confirmKillSwitchOff()` |
| **Modals** | `L:2782 → L:2786` | `openModal()`, `closeModal()`, `showSettings()`, `showAddExchange()` |
| **Settings** | `L:2788 → L:2801` | `saveSettings()` |
| **Exchange Mgmt** | `L:2803 → L:2874` | `loadExchangeList()`, `addExchange()`, `removeExchange()` |
| **JARVIS Chat** | `L:2876 → L:2923` | `toggleJarvisChat()`, `sendJarvisQuick()`, `sendJarvis()`, `appendChatMsg()` |
| **Voice Recognition** | `L:2925 → L:3006` | `recognition`, `isRecording`, `voiceCommands`, `toggleVoice()`, `stopVoice()` |
| **News** | `L:3008 → L:3018` | `loadNews()` |
| **Calendar** | `L:3020 → L:3035` | `loadCalendar()` |
| **Dip/Top Alerts** | `L:3037 → L:3062` | `loadDipTop(symbol)` |
| **Whale Tracking** | `L:3064 → L:3075` | `loadWhales(symbol)` |
| **Auto-Refresh** | `L:3076 → L:3118` | `refreshTimers`, `startAutoRefresh()` |
| **Keyboard Shortcuts** | `L:3120 → L:3140` | `keydown` listener (1-8 timeframes, Escape) |
| **Init on DOM Ready** | `L:3142 → L:3172` | `DOMContentLoaded` → init charts + load all data + start refresh |
| **>>> INSÉRER JS** | `L:3141` | **Nouveau JS → avant L:3142 (`// ========== INIT ON DOM READY ==========`)** |

---

### 1.5 server.py — STRUCTURE COMPLÈTE (L:1 → L:2803)

| Zone | Lignes | Contenu |
|------|--------|---------|
| **Docstring + Imports** | `L:1 → L:43` | shebang, docstring, 20 imports stdlib + 5 externals |
| **Configuration** | `L:45 → L:107` | `BASE_DIR`, `DB_PATH`, `APP_VERSION`, `SYMBOLS` dict (7 paires), `INTERVALS` list (16 TF), Flask app init, CORS, logging |
| **Cache** | `L:109 → L:131` | `class Cache` — TTL cache thread-safe, `get()`, `set()`, `invalidate()` |
| **Database** | `L:133 → L:202` | `get_db()`, `init_db()` — 5 tables: exchanges, paper_trades, trade_journal, settings, killswitch |
| **Encryption** | `L:204 → L:240` | `get_fernet()`, `encrypt_string()`, `decrypt_string()` — Fernet AES |
| **Settings** | `L:242 → L:261` | `get_setting()`, `set_setting()` |
| **Binance Proxy** | `L:263 → L:296` | `fetch_binance()` (GET avec cache TTL), `transform_klines()` |
| **Gold/Silver (Stooq)** | `L:298 → L:358` | `fetch_stooq_price()`, `generate_gold_silver_candles()` |
| **Indicateurs Part 1** | `L:360 → L:476` | `calc_sma()`, `calc_ema()`, `calc_rsi()`, `calc_macd()`, `_std_dev()`, `calc_bollinger()` |
| **Indicateurs Part 2** | `L:478 → L:616` | `calc_atr()`, `calc_stoch_rsi()`, `calc_adx()`, `calc_obv()`, `calc_williams_r()` |
| **compute_all_indicators** | `L:618 → L:690` | Batch computation des 11 indicateurs |
| **MarketRegimeDetector** | `L:692 → L:825` | `class MarketRegimeDetector` — BULL/BEAR/RANGE/CRISIS |
| **SignalEngine** | `L:826 → L:1047` | `class SignalEngine` — scoring multi-indicateurs pondéré |
| **RiskEngine** | `L:1049 → L:1202` | `class RiskEngine` — 7 veto conditions + drawdown tracking |
| **DipTopDetector** | `L:1204 → L:1406` | `class DipTopDetector` — RSI div, volume climax, Wyckoff, confluence |
| **ExchangeAdapter** | `L:1408 → L:1440` | `class ExchangeAdapter(ABC)` — 5 méthodes abstraites |
| **MEXCAdapter** | `L:1442 → L:1562` | `class MEXCAdapter` — CCXT impl |
| **GMXAdapter** | `L:1564 → L:1595` | `class GMXAdapter` — placeholder |
| **ExchangeManager** | `L:1597 → L:1687` | `class ExchangeManager` — multi-exchange registry |
| **MicroPositionEngine** | `L:1689 → L:1739` | `class MicroPositionEngine` — sizing 5% max, 5 concurrent |
| **PaperTrader** | `L:1741 → L:1828` | `class PaperTrader` — virtual execution, 50-trade gate |
| **Instances globales** | `L:1828` | `exchange_manager`, `position_engine`, `paper_trader` (après PaperTrader) |

---

### 1.6 server.py — ROUTES API (L:1830 → L:2793)

| Groupe | Lignes | Routes |
|--------|--------|--------|
| **Market Data** | `L:1830 → L:1987` | `GET /api/candles` L:1834, `GET /api/price` L:1857, `GET /api/orderbook` L:1888, `GET /api/trades` L:1926, `GET /api/ticker` L:1953 |
| **Intelligence** | `L:1989 → L:2131` | `GET /api/indicators` L:1993, `GET /api/dip-top` L:2032, `GET /api/whales` L:2058 |
| **Sentiment & News** | `L:2133 → L:2403` | `GET /api/funding` L:2137, `GET /api/fear-greed` L:2185, `GET /api/sentiment` L:2234, `GET /api/news` L:2267, `POST /api/news/summarize` L:2331, `GET /api/calendar` L:2369 |
| **AI Assistant** | `L:2405 → L:2475` | `POST /api/jarvis` L:2422 |
| **Execution** | `L:2477 → L:2624` | `POST /api/execute` L:2481, `GET /api/positions` L:2559, `GET /api/balance` L:2572, `POST /api/close` L:2587, `GET /api/paper/status` L:2615, `GET /api/paper/history` L:2620 |
| **Exchanges** | `L:2626 → L:2671` | `POST /api/exchanges/add` L:2630, `GET /api/exchanges/list` L:2650, `DELETE /api/exchanges/remove` L:2655, `POST /api/exchanges/test` L:2664 |
| **Risk & Monitoring** | `L:2673 → L:2748` | `GET /api/drawdown` L:2677, `POST /api/killswitch` L:2682, `GET /api/killswitch/status` L:2703, `GET /api/journal` L:2717, `GET /api/export/csv` L:2728 |
| **System** | `L:2750 → L:2793` | `GET /api/status` L:2754, `GET /` L:2785, `GET /<path>` L:2790 |
| **>>> INSÉRER ROUTE** | `L:2783` | **Nouvelle route → avant L:2785 (`@app.route("/")`)** |

---

### 1.7 RÉSUMÉ DES POINTS D'INSERTION PAR TYPE

```
┌─────────────────────────────────────────────────────────────────┐
│                    POINTS D'INSERTION                           │
├──────────────┬──────────────────┬───────────────────────────────┤
│ Type         │ Fichier          │ Insérer AVANT la ligne        │
├──────────────┼──────────────────┼───────────────────────────────┤
│ CSS          │ dashboard.html   │ L:1175  (</style>)            │
│ HTML         │ dashboard.html   │ L:1580  (<!-- Lightweight -->) │
│ JS function  │ dashboard.html   │ L:3142  (INIT ON DOM READY)   │
│ JS init call │ dashboard.html   │ L:3171  (startAutoRefresh)    │
│ API route    │ server.py        │ L:2785  (@app.route("/"))     │
│ Classe Python│ server.py        │ L:1828  (après PaperTrader)   │
│ Indicateur   │ server.py        │ L:618   (avant compute_all)   │
└──────────────┴──────────────────┴───────────────────────────────┘
```

---
## 2. ÉTAPES D'AMÉLIORATION

---

### ÉTAPE 1.0 — MULTI-TIMEFRAME ANALYSIS PANEL

**Commit cible** : `feat: step 29 — multi-timeframe analysis panel`

**Objectif** : Afficher un panneau latéral montrant les signaux (RSI, MACD, régime,
direction) sur 4 timeframes simultanés (1h, 4h, 1d, 1w) pour le symbole actif.
L'utilisateur voit d'un coup d'œil si les timeframes convergent ou divergent.

---

#### Fichiers touchés

| Fichier | Action | Zone d'insertion |
|---------|--------|------------------|
| `server.py` | Nouvelle route API | Avant `L:2785` (`@app.route("/")`) |
| `dashboard.html` | CSS du panneau MTF | Avant `L:1175` (`</style>`) |
| `dashboard.html` | HTML du panneau MTF | Après `L:1448` (`</div><!-- /main-layout -->`) |
| `dashboard.html` | JS : fetch + render | Avant `L:3142` (`// INIT ON DOM READY`) |
| `dashboard.html` | JS : appel init | Dans `DOMContentLoaded` bloc `L:3143` |
| `dashboard.html` | JS : auto-refresh | Dans `startAutoRefresh()` `L:3079` |

---

#### Sous-tâches

**1.1 — Route API `GET /api/mtf-signals`** (`server.py`)

- Insérer avant `L:2785`
- Paramètre : `?symbol=BTCUSDT`
- Pour chaque TF dans `["1h", "4h", "1d", "1w"]` :
  - Fetch candles via `fetch_binance()` (limit=200)
  - Appeler `compute_all_indicators(ohlcv)`
  - Appeler `regime_detector.detect()`
  - Appeler `signal_engine.generate()`
  - Extraire : `rsi_last`, `macd_direction`, `regime`, `signal_direction`, `confidence`
- Retourner un JSON :
```json
{
  "symbol": "BTCUSDT",
  "timeframes": {
    "1h":  {"rsi": 42, "macd": "bearish", "regime": "RANGE", "direction": "SHORT", "confidence": 55},
    "4h":  {"rsi": 58, "macd": "bullish", "regime": "BULL",  "direction": "LONG",  "confidence": 72},
    "1d":  {"rsi": 61, "macd": "bullish", "regime": "BULL",  "direction": "LONG",  "confidence": 68},
    "1w":  {"rsi": 55, "macd": "flat",    "regime": "RANGE", "direction": "NEUTRAL","confidence": 40}
  },
  "confluence": {"direction": "LONG", "agreement": 3, "total": 4, "pct": 75}
}
```
- Calcul `confluence` : compter combien de TF partagent la même direction majoritaire
- Cache TTL = 30s (données multi-TF coûteuses)

**1.2 — CSS du panneau MTF** (`dashboard.html`)

- Insérer avant `L:1175` (`</style>`)
- Classes à créer :
  - `.mtf-panel` — conteneur fixe, largeur ~280px, sous la main-layout
  - `.mtf-header` — titre "Multi-Timeframe" + bouton toggle
  - `.mtf-grid` — grille 4 lignes (1 par TF)
  - `.mtf-row` — une ligne : label TF + RSI + MACD dot + régime badge + direction flèche
  - `.mtf-confluence` — barre de confluence en bas (agreement X/4)
  - `.mtf-cell` — cellule individuelle
  - `.mtf-dot.bull` / `.mtf-dot.bear` / `.mtf-dot.neutral` — pastilles colorées
- Respecter les variables `:root` existantes (`--green`, `--red`, `--yellow`, `--accent`)
- Transitions 0.15s ease cohérentes avec le reste

**1.3 — HTML du panneau MTF** (`dashboard.html`)

- Insérer après `L:1448` (`</div><!-- /main-layout -->`)
- Structure :
```html
<!-- MTF PANEL -->
<div class="mtf-panel" id="mtf-panel">
    <div class="mtf-header">
        <span>Multi-Timeframe</span>
        <button onclick="toggleMTFPanel()">&#9660;</button>
    </div>
    <div class="mtf-grid" id="mtf-grid">
        <!-- Rempli dynamiquement par JS -->
    </div>
    <div class="mtf-confluence" id="mtf-confluence">
        Confluence: --
    </div>
</div>
```

**1.4 — JS : fonction `loadMTF()`** (`dashboard.html`)

- Insérer avant `L:3142` (`// INIT ON DOM READY`)
- Fetch `GET /api/mtf-signals?symbol=` + `currentSymbol`
- Pour chaque TF dans la réponse, générer une ligne HTML :
  - Label du TF (gras)
  - RSI value (colorée : <30 vert, >70 rouge, sinon neutre)
  - MACD dot (vert bullish, rouge bearish, gris flat)
  - Régime badge (réutiliser classes `.ft-regime.bull/.bear/.range/.crisis`)
  - Direction flèche (▲ LONG vert, ▼ SHORT rouge, ◆ NEUTRAL gris)
  - Confidence % (numérique)
- Mettre à jour `#mtf-confluence` avec la barre de confluence
- Fonction `toggleMTFPanel()` : toggle classe `.collapsed` sur `#mtf-panel`

**1.5 — Intégration dans le cycle de vie** (`dashboard.html`)

- Dans `DOMContentLoaded` (L:3143) : ajouter `loadMTF();`
- Dans `startAutoRefresh()` (L:3079) : ajouter un interval 60s pour `loadMTF()`
- Dans `changeSymbol()` (L:2020) : ajouter `loadMTF();` après le changement
- Bouton toggle dans la navbar (L:1192) : ajouter un `btn-nav` pour ouvrir/fermer le panneau

---

#### Critères de validation

| # | Critère | Comment vérifier |
|---|---------|------------------|
| V1.1 | `python3 -m py_compile server.py` passe | Commande terminal |
| V1.2 | `GET /api/mtf-signals?symbol=BTCUSDT` retourne 4 timeframes | `curl` ou navigateur |
| V1.3 | Le panneau MTF s'affiche sous le chart | Ouvrir dashboard dans navigateur |
| V1.4 | Les pastilles de couleur correspondent aux valeurs | Vérifier RSI <30 = vert, >70 = rouge |
| V1.5 | La confluence affiche X/4 agreement | Comparer avec les directions individuelles |
| V1.6 | Le panneau se toggle (collapse/expand) | Cliquer le bouton toggle |
| V1.7 | Changement de symbole rafraîchit le MTF | Changer de paire et observer |
| V1.8 | Auto-refresh toutes les 60s fonctionne | Attendre 60s, vérifier mise à jour |

---

#### Note de reprise

> Si cette étape est reprise dans une nouvelle session :
> 1. Lire `PLAN.md` section 1.0
> 2. Vérifier la carte de navigation (section 2) pour les lignes actuelles
> 3. Les lignes ont pu bouger si des étapes précédentes ont ajouté du code
> 4. Chercher les ancres textuelles (`</style>`, `<!-- /main-layout -->`, `// INIT ON DOM READY`)
>    plutôt que se fier uniquement aux numéros de ligne

---
### ÉTAPE 2.0 — PORTFOLIO TRACKER & EQUITY CURVE

**Commit cible** : `feat: step 30 — portfolio tracker & equity curve`

**Objectif** : Vue portefeuille complète avec PnL cumulé, allocation par symbole
(pie chart SVG), et courbe d'equity historique (line chart TradingView) basée
sur l'historique des paper trades. Accessible via un onglet du Bottom Panel.

---

#### Fichiers touchés

| Fichier | Action | Zone d'insertion |
|---------|--------|------------------|
| `server.py` | Nouvelle route `GET /api/portfolio` | Avant `L:2785` (`@app.route("/")`) |
| `server.py` | Nouvelle route `GET /api/equity-curve` | Avant `L:2785` (`@app.route("/")`) |
| `dashboard.html` | CSS du portfolio | Avant `L:1175` (`</style>`) |
| `dashboard.html` | HTML onglet Portfolio dans Bottom Panel | Modifier `L:1318` zone `.bp-tabs` |
| `dashboard.html` | JS : fetch + render + SVG pie | Avant `L:3142` (`// INIT ON DOM READY`) |
| `dashboard.html` | JS : appel init | Dans `DOMContentLoaded` `L:3143` |

---

#### Sous-tâches

**2.1 — Route API `GET /api/portfolio`** (`server.py`)

- Insérer avant `L:2785`
- Requête SQL sur `paper_trades` (status = 'closed') :
  - Grouper par `symbol` → total PnL par symbole, nombre de trades, win rate
  - Calculer PnL cumulé global
  - Calculer allocation = PnL par symbole / PnL total (pour pie chart)
- Requête SQL sur `paper_trades` (status = 'open') :
  - Positions ouvertes actuelles avec unrealized PnL estimé
- Retourner :
```json
{
  "total_pnl": 125.40,
  "total_trades": 34,
  "win_rate": 62.5,
  "open_positions": 2,
  "unrealized_pnl": -12.30,
  "by_symbol": [
    {"symbol": "BTCUSDT", "pnl": 89.20, "trades": 18, "win_rate": 66.7, "pct": 71.1},
    {"symbol": "ETHUSDT", "pnl": 36.20, "trades": 16, "win_rate": 56.3, "pct": 28.9}
  ],
  "best_trade": {"symbol": "BTCUSDT", "pnl": 42.10, "date": "2026-04-18"},
  "worst_trade": {"symbol": "ETHUSDT", "pnl": -18.50, "date": "2026-04-15"}
}
```

**2.2 — Route API `GET /api/equity-curve`** (`server.py`)

- Insérer juste après la route portfolio (avant `L:2785`)
- Requête SQL : `SELECT closed_at, pnl FROM paper_trades WHERE status='closed' ORDER BY closed_at ASC`
- Calculer le PnL cumulé chronologique :
  - Commencer au capital initial (`get_setting('paper_capital', '100')`)
  - Pour chaque trade fermé : `equity += pnl`
  - Retourner tableau `[{time: epoch, value: equity}, ...]`
- Format compatible TradingView `LineSeries` :
```json
{
  "initial_capital": 100,
  "current_equity": 225.40,
  "curve": [
    {"time": 1713400000, "value": 100},
    {"time": 1713450000, "value": 112.30},
    {"time": 1713500000, "value": 108.10}
  ]
}
```

**2.3 — CSS du Portfolio** (`dashboard.html`)

- Insérer avant `L:1175` (`</style>`)
- Classes à créer :
  - `.portfolio-wrap` — conteneur flex horizontal (pie + stats)
  - `.portfolio-stats` — colonne gauche : total PnL, win rate, trades count
  - `.portfolio-stat` — une ligne stat (label + value), réutiliser style `.wallet-row`
  - `.portfolio-pie` — conteneur SVG 120×120px pour le pie chart
  - `.portfolio-legend` — légende couleurs sous le pie
  - `.equity-chart-wrap` — conteneur pour le mini line chart equity (hauteur 150px)
- Couleurs : utiliser palette tournante `--green`, `--accent`, `--yellow`, `--red`, `#9b59b6`, `#e67e22`

**2.4 — HTML : onglet Portfolio dans Bottom Panel** (`dashboard.html`)

- Modifier la zone `.bp-tabs` (`L:1318 → L:1325`)
- Ajouter un bouton entre "Paper Trades" et "Journal" :
```html
<button onclick="switchBPTab('portfolio')">Portfolio</button>
```
- Le contenu sera rendu dynamiquement dans `#bp-content` par JS

**2.5 — JS : fonction `loadPortfolio()`** (`dashboard.html`)

- Insérer avant `L:3142` (`// INIT ON DOM READY`)
- Fetch `GET /api/portfolio`
- Générer le HTML dans `#bp-content` :
  - Section stats : Total PnL (coloré vert/rouge), Win Rate %, Total Trades, Open Positions
  - Best/Worst trade
- Appeler `renderPieChart()` avec les données `by_symbol`

**2.6 — JS : fonction `renderPieChart(data)`** (`dashboard.html`)

- Insérer juste après `loadPortfolio()`
- Générer un SVG inline (pas de librairie externe) :
  - `<svg viewBox="0 0 120 120">` avec arcs `<path>` pour chaque symbole
  - Calcul des arcs via `Math.cos` / `Math.sin` et coordonnées polaires
  - Légende sous le SVG : pastille couleur + symbole + pourcentage
- Fonction pure : prend un tableau `[{symbol, pct, pnl}]`, retourne un string HTML

**2.7 — JS : fonction `loadEquityCurve()`** (`dashboard.html`)

- Insérer juste après `renderPieChart()`
- Fetch `GET /api/equity-curve`
- Créer un mini chart TradingView `createChart()` dans un div `#equity-chart`
  - Hauteur 150px, même thème que `subChartOptions` (L:1723)
  - `LineSeries` avec couleur `--accent`
  - Données = `curve` de la réponse API
- Appelée depuis `loadPortfolio()` après le render des stats

**2.8 — Intégration `switchBPTab()`** (`dashboard.html`)

- Modifier `switchBPTab()` (`L:2373`) :
  - Ajouter `case 'portfolio': loadPortfolio(); break;`
- Dans `DOMContentLoaded` : ne pas appeler `loadPortfolio()` au démarrage (chargement à la demande seulement)

---

#### Critères de validation

| # | Critère | Comment vérifier |
|---|---------|------------------|
| V2.1 | `python3 -m py_compile server.py` passe | Commande terminal |
| V2.2 | `GET /api/portfolio` retourne PnL et by_symbol | `curl` |
| V2.3 | `GET /api/equity-curve` retourne un tableau curve[] | `curl` |
| V2.4 | L'onglet "Portfolio" apparaît dans le Bottom Panel | Navigateur |
| V2.5 | Cliquer l'onglet affiche stats + pie chart SVG | Navigateur |
| V2.6 | Le pie chart reflète les proportions par symbole | Comparer pct vs arc visuel |
| V2.7 | L'equity curve s'affiche en line chart | Navigateur |
| V2.8 | Avec 0 trades fermés, affichage "No trades yet" | Tester sur DB vide |

---

#### Note de reprise

> Dépendance : cette étape utilise la table `paper_trades` (L:160 server.py).
> Pas besoin de modifier le schéma DB — toutes les colonnes nécessaires existent
> déjà (`symbol`, `side`, `entry_price`, `exit_price`, `pnl`, `status`, `closed_at`).
> Le pie chart est en SVG pur — pas de dépendance externe.
> L'equity curve réutilise TradingView `createChart` (déjà chargé via `lw-charts.js`).

---
### ÉTAPE 3.0 — ALERTES & NOTIFICATIONS

**Commit cible** : `feat: step 31 — alert system with price & indicator triggers`

**Objectif** : Système d'alertes configurable où l'utilisateur définit des conditions
(prix franchit un seuil, RSI > 70, régime change, etc.). Quand une condition est
remplie, une toast notification empilable s'affiche avec un badge compteur dans
la navbar. Les alertes sont persistées en SQLite et évaluées à chaque cycle
de refresh.

---

#### Fichiers touchés

| Fichier | Action | Zone d'insertion |
|---------|--------|------------------|
| `server.py` | Nouvelle table `alerts` dans `init_db()` | Dans `L:145` (`init_db()`) après la table `killswitch` |
| `server.py` | Route `POST /api/alerts` (créer) | Avant `L:2785` (`@app.route("/")`) |
| `server.py` | Route `GET /api/alerts` (lister) | Avant `L:2785` |
| `server.py` | Route `DELETE /api/alerts/<id>` (supprimer) | Avant `L:2785` |
| `server.py` | Route `GET /api/alerts/check` (évaluer) | Avant `L:2785` |
| `dashboard.html` | CSS : toasts empilables + modal alertes + badge | Avant `L:1175` (`</style>`) |
| `dashboard.html` | HTML : modal création d'alerte | Après `L:1560` (après modal kill) |
| `dashboard.html` | HTML : badge compteur dans navbar | Modifier `L:1192` (navbar-actions) |
| `dashboard.html` | JS : CRUD alertes + évaluation + toasts | Avant `L:3142` (`// INIT ON DOM READY`) |
| `dashboard.html` | JS : refactor `showToast()` avec empilement | Modifier `L:2689` |
| `dashboard.html` | JS : auto-refresh check alertes | Dans `startAutoRefresh()` `L:3079` |

---

#### Sous-tâches

**3.1 — Table SQLite `alerts`** (`server.py`)

- Insérer dans `init_db()` après la table `killswitch` (~`L:199`)
- Schéma :
```sql
CREATE TABLE IF NOT EXISTS alerts (
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
)
```
- `condition_type` : `"price"`, `"rsi"`, `"macd_cross"`, `"regime_change"`, `"volume_spike"`
- `operator` : `"gt"` (>), `"lt"` (<), `"eq"` (=), `"cross_up"`, `"cross_down"`
- `repeat` : 0 = one-shot (se désactive après trigger), 1 = répète à chaque cycle

**3.2 — Route `POST /api/alerts`** (`server.py`)

- Insérer avant `L:2785`
- Body JSON : `{symbol, condition_type, operator, value, message, repeat}`
- Validation : condition_type dans la liste autorisée, operator valide
- Insert dans SQLite, retourner `{id, success: true}`

**3.3 — Route `GET /api/alerts`** (`server.py`)

- Insérer après la route POST
- Retourner toutes les alertes triées par `created_at DESC`
- Inclure le statut triggered/active

**3.4 — Route `DELETE /api/alerts/<id>`** (`server.py`)

- Insérer après la route GET
- Supprimer par ID, retourner `{success: true}`

**3.5 — Route `GET /api/alerts/check`** (`server.py`)

- Insérer après la route DELETE
- Paramètre : `?symbol=BTCUSDT`
- Pour chaque alerte active (triggered=0 ou repeat=1) du symbole :
  - Fetch le prix actuel via cache (déjà dans `fetch_binance`)
  - Fetch les indicateurs via `compute_all_indicators()` (utiliser le cache existant)
  - Évaluer la condition :
    - `price gt 70000` → prix actuel > 70000
    - `rsi gt 70` → dernier RSI > 70
    - `regime_change eq CRISIS` → régime actuel == CRISIS
    - `volume_spike gt 3` → volume > 3× moyenne
  - Si condition remplie : marquer `triggered=1`, `triggered_at=now`
- Retourner la liste des alertes nouvellement déclenchées :
```json
{
  "triggered": [
    {"id": 3, "symbol": "BTCUSDT", "condition_type": "price", "operator": "gt", "value": 70000, "message": "BTC above 70K!"}
  ],
  "active_count": 5,
  "triggered_count": 2
}
```

**3.6 — Refactor `showToast()` avec empilement** (`dashboard.html`)

- Modifier `showToast()` (`L:2689`)
- Au lieu d'un positionnement fixe unique, empiler les toasts :
  - Variable `let toastStack = []` dans le Global State
  - Chaque toast se positionne à `top: 60px + (index * 50px)`
  - Maximum 5 toasts visibles simultanément (les plus anciens disparaissent)
  - Ajouter le type `"warning"` (fond jaune) en plus de `"error"` et `"success"`
- Ajouter une classe CSS `.toast` au lieu du inline style actuel

**3.7 — CSS alertes** (`dashboard.html`)

- Insérer avant `L:1175` (`</style>`)
- Classes :
  - `.toast` — position fixe, z-index 999, animation slide-down
  - `.toast.success` — fond `--green`
  - `.toast.error` — fond `--red`
  - `.toast.warning` — fond `--yellow`, texte `--bg`
  - `.toast-stack` — conteneur fixe top-right pour l'empilement
  - `.alert-modal` — réutiliser `.modal` existant
  - `.alert-form` — formulaire avec selects pour type/operator + input value
  - `.alert-list` — liste des alertes actives avec bouton supprimer
  - `.alert-badge` — badge rond dans la navbar (même style que `#pos-count` L:738)

**3.8 — HTML : modal création d'alerte** (`dashboard.html`)

- Insérer après `L:1560` (après la modal kill switch)
- Structure :
```html
<!-- ALERT MODAL -->
<div class="modal-overlay" id="modal-alert">
    <div class="modal">
        <div class="modal-header">
            <span>Create Alert</span>
            <button onclick="closeModal('modal-alert')">&times;</button>
        </div>
        <div class="modal-body">
            <div class="modal-field">
                <label>Symbol</label>
                <select id="alert-symbol"><!-- options dynamiques --></select>
            </div>
            <div class="modal-field">
                <label>Condition</label>
                <select id="alert-type">
                    <option value="price">Price</option>
                    <option value="rsi">RSI(14)</option>
                    <option value="regime_change">Regime</option>
                    <option value="volume_spike">Volume Spike</option>
                </select>
            </div>
            <div class="modal-field">
                <label>Operator</label>
                <select id="alert-op">
                    <option value="gt">Above (>)</option>
                    <option value="lt">Below (<)</option>
                    <option value="eq">Equals (=)</option>
                </select>
            </div>
            <div class="modal-field">
                <label>Value</label>
                <input type="number" id="alert-value" placeholder="70000">
            </div>
            <div class="modal-field">
                <label>Message (optional)</label>
                <input type="text" id="alert-msg" placeholder="BTC above 70K!">
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn-cancel" onclick="closeModal('modal-alert')">Cancel</button>
            <button class="btn-confirm" onclick="createAlert()">Create</button>
        </div>
    </div>
</div>
```

**3.9 — HTML : badge + bouton navbar** (`dashboard.html`)

- Modifier la zone `navbar-actions` (`L:1192`)
- Ajouter avant le bouton AI :
```html
<button class="btn-nav" onclick="showAlertModal()">Alerts <span class="badge" id="alert-badge" style="display:none">0</span></button>
```

**3.10 — JS : fonctions CRUD alertes** (`dashboard.html`)

- Insérer avant `L:3142` (`// INIT ON DOM READY`)
- `showAlertModal()` — ouvre `#modal-alert`, charge la liste des alertes existantes
- `createAlert()` — POST `/api/alerts` avec les valeurs du formulaire, ferme modal, toast success
- `deleteAlert(id)` — DELETE `/api/alerts/<id>`, refresh la liste
- `loadAlertList()` — GET `/api/alerts`, rend la liste dans le modal (avec bouton ✕ par alerte)

**3.11 — JS : fonction `checkAlerts()`** (`dashboard.html`)

- Insérer après les fonctions CRUD
- Fetch `GET /api/alerts/check?symbol=` + `currentSymbol`
- Pour chaque alerte triggered : appeler `showToast(alert.message, 'warning')`
- Mettre à jour le badge `#alert-badge` avec `active_count`

**3.12 — Intégration auto-refresh** (`dashboard.html`)

- Dans `startAutoRefresh()` (`L:3079`) : ajouter un interval 30s pour `checkAlerts()`
- Dans `changeSymbol()` (`L:2020`) : appeler `checkAlerts()` après le changement

---

#### Critères de validation

| # | Critère | Comment vérifier |
|---|---------|------------------|
| V3.1 | `python3 -m py_compile server.py` passe | Terminal |
| V3.2 | La table `alerts` est créée au démarrage | Vérifier `jarvis.db` avec sqlite3 |
| V3.3 | `POST /api/alerts` crée une alerte | `curl -X POST` avec body JSON |
| V3.4 | `GET /api/alerts` retourne la liste | `curl` |
| V3.5 | `DELETE /api/alerts/1` supprime | `curl -X DELETE` |
| V3.6 | `GET /api/alerts/check` évalue et déclenche | Créer alerte prix < current, vérifier |
| V3.7 | Les toasts s'empilent sans se chevaucher | Déclencher 3 alertes simultanément |
| V3.8 | Le badge navbar affiche le compte | Créer des alertes, vérifier le badge |
| V3.9 | La modal s'ouvre et liste les alertes | Cliquer "Alerts" dans la navbar |
| V3.10 | Alerte one-shot ne se redéclenche pas | Vérifier triggered=1 après premier trigger |

---

#### Note de reprise

> Cette étape ajoute une nouvelle table SQLite — `init_db()` la créera automatiquement
> au prochain démarrage. Pas de migration nécessaire car on utilise `CREATE TABLE IF NOT EXISTS`.
> Le `showToast()` existant (L:2689) sera **remplacé** (pas dupliqué) par la version empilable.
> Les 4 routes API suivent le pattern CRUD standard du projet.
> Le check d'alertes réutilise `fetch_binance()` et `compute_all_indicators()` déjà cachés.

---
### ÉTAPE 4.0 — DRAWING TOOLS

**Commit cible** : `feat: step 32 — interactive drawing tools on chart`

**Objectif** : Rendre les boutons de la toolbar de dessin (L:1250-1258) fonctionnels.
L'utilisateur peut dessiner sur le chart : lignes de tendance, niveaux horizontaux,
retracements de Fibonacci, rectangles, et annotations texte. Les dessins sont
stockés en localStorage par symbole+TF et restaurés au changement de vue.
Implémentation 100% frontend — pas de route API (les dessins sont locaux).

---

#### Fichiers touchés

| Fichier | Action | Zone d'insertion |
|---------|--------|------------------|
| `server.py` | **Aucun** — fonctionnalité 100% frontend | — |
| `dashboard.html` | CSS : toolbar active, canvas overlay, fib levels | Avant `L:1175` (`</style>`) |
| `dashboard.html` | HTML : modifier les boutons toolbar existants | Modifier `L:1250 → L:1259` |
| `dashboard.html` | HTML : ajouter un `<canvas>` overlay sur le chart | Après `L:1301` (`<div id="chart-container">`) |
| `dashboard.html` | JS : état dessin global | Dans Global State après `L:1614` |
| `dashboard.html` | JS : moteur de dessin complet | Avant `L:3142` (`// INIT ON DOM READY`) |
| `dashboard.html` | JS : init dans DOMContentLoaded | Dans `L:3143` |

---

#### Sous-tâches

**4.1 — HTML : activer les boutons toolbar** (`dashboard.html`)

- Modifier `L:1250 → L:1259`
- Ajouter `onclick` et `id` à chaque bouton :
```html
<div class="draw-toolbar">
    <button id="draw-cursor" title="Cursor" onclick="setDrawMode('cursor')" class="active">+</button>
    <button id="draw-crosshair" title="Crosshair" onclick="setDrawMode('crosshair')">&#9547;</button>
    <button id="draw-trendline" title="Trend Line" onclick="setDrawMode('trendline')">&#9585;</button>
    <button id="draw-hline" title="Horizontal" onclick="setDrawMode('hline')">&#8213;</button>
    <button id="draw-fib" title="Fib Retracement" onclick="setDrawMode('fib')">&#916;</button>
    <button id="draw-rect" title="Rectangle" onclick="setDrawMode('rect')">&#9633;</button>
    <button id="draw-text" title="Text" onclick="setDrawMode('text')">T</button>
    <button id="draw-measure" title="Measure" onclick="setDrawMode('measure')">&#8614;</button>
    <button id="draw-clear" title="Clear All" onclick="clearDrawings()" style="margin-top:auto;color:var(--red)">&#10005;</button>
</div>
```

**4.2 — HTML : canvas overlay sur le chart** (`dashboard.html`)

- Modifier la zone `chart-main-wrap` (`L:1293`)
- Ajouter un `<canvas>` positionné en absolute au-dessus du chart container :
```html
<div class="chart-main-wrap">
    <div class="chart-ohlcv-overlay" id="ohlcv-overlay">...</div>
    <div id="chart-container"></div>
    <canvas id="draw-canvas" class="draw-canvas"></canvas>
</div>
```
- Le canvas couvre exactement le `#chart-container` (position absolute, inset 0)

**4.3 — CSS : canvas + toolbar état actif** (`dashboard.html`)

- Insérer avant `L:1175` (`</style>`)
- Classes :
  - `.draw-canvas` — position absolute, inset 0, z-index 10, pointer-events none par défaut
  - `.draw-canvas.active` — pointer-events auto, cursor crosshair
  - `.draw-toolbar button.active` — couleur `--yellow`, fond `--surface-2`
  - `.draw-fib-level` — labels texte pour niveaux Fibonacci (0, 0.236, 0.382, 0.5, 0.618, 0.786, 1)
  - `.draw-measure-popup` — petit tooltip affichant distance prix/% entre deux points
  - `.draw-text-input` — input flottant pour saisir le texte d'annotation

**4.4 — JS : état global dessin** (`dashboard.html`)

- Insérer après `L:1614` (fin du bloc `indicatorState`)
```javascript
let drawMode = 'cursor';
let drawStart = null;
let drawings = [];
let drawCtx = null;
```

**4.5 — JS : fonction `setDrawMode(mode)`** (`dashboard.html`)

- Insérer avant `L:3142`
- Désactive tous les boutons `.draw-toolbar button` (retirer `.active`)
- Active le bouton sélectionné
- Met à jour `drawMode`
- Si mode != 'cursor' : ajouter `.active` au canvas (active pointer-events)
- Si mode == 'cursor' : retirer `.active` du canvas

**4.6 — JS : fonctions de conversion coordonnées** (`dashboard.html`)

- Insérer après `setDrawMode()`
- `pixelToPrice(y)` — convertit position Y pixel en valeur prix via l'API TradingView :
  - `mainChart.priceScale('right').coordinateToPrice(y)`
  - Fallback : interpolation linéaire si l'API ne supporte pas
- `pixelToTime(x)` — convertit position X pixel en timestamp :
  - `mainChart.timeScale().coordinateToTime(x)`
- `priceToPixel(price)` — inverse de `pixelToPrice`
- `timeToPixel(time)` — inverse de `pixelToTime`

**4.7 — JS : événements souris du canvas** (`dashboard.html`)

- Insérer après les fonctions de conversion
- `mousedown` sur `#draw-canvas` :
  - Si `drawMode == 'cursor'` : ignorer
  - Stocker `drawStart = {x, y, price: pixelToPrice(y), time: pixelToTime(x)}`
- `mousemove` sur `#draw-canvas` :
  - Si `drawStart` non null : dessiner la preview (ligne temporaire, rect temporaire, etc.)
  - Appeler `renderDrawingPreview()`
- `mouseup` sur `#draw-canvas` :
  - Finaliser le dessin : pousser dans `drawings[]`
  - Appeler `saveDrawings()` pour persister en localStorage
  - Reset `drawStart = null`
  - Appeler `renderAllDrawings()`

**4.8 — JS : fonctions de rendu par type** (`dashboard.html`)

- Insérer après les event handlers
- `drawTrendLine(ctx, from, to)` — ligne entre deux points (prix/temps)
  - Convertir prix→pixel, temps→pixel
  - `ctx.beginPath(); ctx.moveTo(); ctx.lineTo(); ctx.stroke()`
  - Couleur : `--accent` (#00d4ff), épaisseur 1.5px
- `drawHorizontalLine(ctx, price)` — ligne horizontale sur toute la largeur
  - Label prix à droite
  - Style : tirets (`setLineDash([5, 3])`)
  - Couleur : `--yellow`
- `drawFibRetracement(ctx, from, to)` — niveaux 0, 0.236, 0.382, 0.5, 0.618, 0.786, 1
  - Ligne horizontale par niveau + label pourcentage + valeur prix
  - Couleurs dégradées du vert (0) au rouge (1)
- `drawRectangle(ctx, from, to)` — rectangle semi-transparent
  - Fill : `rgba(0, 212, 255, 0.08)`, border : `--accent`
- `drawTextAnnotation(ctx, pos, text)` — texte à position donnée
  - Prompt via `prompt()` ou input flottant
  - Font : 11px, couleur `--text`
- `drawMeasure(ctx, from, to)` — ligne + popup avec distance
  - Affiche : prix delta, pourcentage delta, nombre de barres

**4.9 — JS : `renderAllDrawings()` et synchronisation chart** (`dashboard.html`)

- Insérer après les fonctions de rendu
- Efface le canvas puis redessine tous les `drawings[]`
- Appelée à chaque :
  - Scroll/zoom du chart (via `mainChart.timeScale().subscribeVisibleTimeRangeChange`)
  - Resize du chart (via le ResizeObserver existant L:1717)
  - Changement de symbole/TF

**4.10 — JS : persistence localStorage** (`dashboard.html`)

- Insérer après `renderAllDrawings()`
- `saveDrawings()` — stocke en localStorage avec clé `drawings_<symbol>_<interval>`
  - Format : `JSON.stringify(drawings)` — chaque dessin stocke prix/temps pas pixels
- `loadDrawings()` — charge depuis localStorage pour le symbole/TF actuel
  - Appelée dans `changeSymbol()` (L:2020) et `changeTF()` (L:2036)
- `clearDrawings()` — vide `drawings[]`, efface le canvas, supprime la clé localStorage

**4.11 — JS : intégration init** (`dashboard.html`)

- Dans `initMainChart()` (L:1673) après la création du chart :
  - Initialiser `drawCtx = $('draw-canvas').getContext('2d')`
  - Dimensionner le canvas = taille du chart-container
  - Attacher le ResizeObserver au canvas aussi
- Dans `DOMContentLoaded` (L:3143) : appeler `loadDrawings()`
- Dans `changeSymbol()` (L:2020) : appeler `saveDrawings()` puis `loadDrawings()`
- Dans `changeTF()` (L:2036) : même chose

---

#### Critères de validation

| # | Critère | Comment vérifier |
|---|---------|------------------|
| V4.1 | Les boutons toolbar changent d'état actif | Cliquer chaque bouton |
| V4.2 | Le canvas overlay couvre exactement le chart | Inspecter l'élément au devtools |
| V4.3 | Trend line : dessiner du point A au point B | Cliquer-glisser en mode trendline |
| V4.4 | Horizontal line : trait sur toute la largeur avec label | Cliquer en mode hline |
| V4.5 | Fibonacci : 7 niveaux horizontaux avec labels | Cliquer-glisser en mode fib |
| V4.6 | Rectangle : zone semi-transparente | Cliquer-glisser en mode rect |
| V4.7 | Les dessins survivent au scroll/zoom | Scroller le chart, vérifier |
| V4.8 | Les dessins persistent au refresh page | F5 et vérifier |
| V4.9 | Changer de symbole charge les bons dessins | Dessiner sur BTC, switch ETH, revenir BTC |
| V4.10 | "Clear All" efface tout | Cliquer le bouton ✕ rouge |

---

#### Note de reprise

> Étape 100% frontend — aucune modification de `server.py`.
> Les boutons de la toolbar existent déjà (L:1250-1258) mais sont inactifs.
> TradingView Lightweight Charts n'a PAS d'API de dessin native — on utilise un
> `<canvas>` superposé. La conversion pixel↔prix passe par les méthodes
> `coordinateToPrice()` / `coordinateToTime()` de l'API TradingView.
> Les dessins sont stockés en coordonnées prix/temps (pas pixel) pour survivre
> aux resize et scroll. Le localStorage est segmenté par `symbol_interval`.

---
### ÉTAPE 5.0 — ADVANCED ORDER TYPES

**Commit cible** : `feat: step 33 — OCO, trailing stop, iceberg & DCA orders`

**Objectif** : Étendre le système d'ordres avec 4 types avancés : OCO (One-Cancels-Other),
Trailing Stop visuel, Iceberg (découpage en sous-ordres), et DCA automatique
(Dollar-Cost Averaging sur N paliers). L'UI du formulaire d'ordre s'adapte
dynamiquement au type sélectionné. Le backend gère l'exécution et le suivi.

---

#### Fichiers touchés

| Fichier | Action | Zone d'insertion |
|---------|--------|------------------|
| `server.py` | Nouvelle table `scheduled_orders` | Dans `init_db()` après `L:199` |
| `server.py` | Route `POST /api/execute` étendue | Modifier `L:2481 → L:2556` |
| `server.py` | Route `GET /api/scheduled-orders` | Avant `L:2785` (`@app.route("/")`) |
| `server.py` | Route `DELETE /api/scheduled-orders/<id>` | Avant `L:2785` |
| `server.py` | Fonction `process_scheduled_orders()` | Avant `L:2785` |
| `dashboard.html` | CSS : champs conditionnels, DCA grid | Avant `L:1175` (`</style>`) |
| `dashboard.html` | HTML : modifier les tabs order type | Modifier `L:1383 → L:1388` |
| `dashboard.html` | HTML : champs conditionnels par type | Après `L:1412` (après TP/SL) |
| `dashboard.html` | JS : `switchOrderType()` étendue | Modifier `L:2497 → L:2511` |
| `dashboard.html` | JS : logique d'exécution avancée | Modifier `executeOrder()` `L:2605` |
| `dashboard.html` | JS : fonctions DCA/Iceberg | Avant `L:3142` (`// INIT ON DOM READY`) |

---

#### Sous-tâches

**5.1 — Table SQLite `scheduled_orders`** (`server.py`)

- Insérer dans `init_db()` après la table `killswitch` (~`L:199`)
- Schéma :
```sql
CREATE TABLE IF NOT EXISTS scheduled_orders (
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
)
```
- `parent_type` : `"oco"`, `"trailing"`, `"iceberg"`, `"dca"`
- `status` : `"pending"`, `"active"`, `"executed"`, `"cancelled"`
- `parent_id` : pour lier les sous-ordres entre eux (OCO pair, iceberg chunks, DCA paliers)

**5.2 — HTML : tabs order type étendus** (`dashboard.html`)

- Modifier `L:1383 → L:1388`
- Remplacer par :
```html
<div class="of-type-tabs">
    <button class="active" onclick="switchOrderType('limit')">Limit</button>
    <button onclick="switchOrderType('market')">Market</button>
    <button onclick="switchOrderType('oco')">OCO</button>
    <button onclick="switchOrderType('trailing')">Trail</button>
    <button onclick="switchOrderType('iceberg')">Iceberg</button>
    <button onclick="switchOrderType('dca')">DCA</button>
</div>
```

**5.3 — HTML : champs conditionnels par type** (`dashboard.html`)

- Insérer après `L:1412` (après le bloc `.of-tpsl`)
- Champs masqués par défaut, affichés selon `orderType` :
```html
<!-- OCO fields -->
<div class="of-advanced" id="oco-fields" style="display:none">
    <div class="of-field"><label>Limit Price</label><input type="text" id="oco-limit" placeholder="0.00"></div>
    <div class="of-field"><label>Stop Price</label><input type="text" id="oco-stop" placeholder="0.00"></div>
</div>
<!-- Trailing fields -->
<div class="of-advanced" id="trailing-fields" style="display:none">
    <div class="of-field"><label>Callback %</label><input type="text" id="trail-pct" placeholder="1.0"><span class="unit">%</span></div>
    <div class="of-field"><label>Activation</label><input type="text" id="trail-activation" placeholder="Optional"></div>
</div>
<!-- Iceberg fields -->
<div class="of-advanced" id="iceberg-fields" style="display:none">
    <div class="of-field"><label>Visible Qty</label><input type="text" id="ice-visible" placeholder="10%"><span class="unit">%</span></div>
    <div class="of-field"><label>Slices</label><input type="number" id="ice-slices" value="5" min="2" max="20"></div>
</div>
<!-- DCA fields -->
<div class="of-advanced" id="dca-fields" style="display:none">
    <div class="of-field"><label>Levels</label><input type="number" id="dca-levels" value="5" min="2" max="10"></div>
    <div class="of-field"><label>Step %</label><input type="text" id="dca-step" placeholder="2.0"><span class="unit">%</span></div>
    <div class="of-field"><label>Multiplier</label><input type="text" id="dca-mult" placeholder="1.5"></div>
    <div class="dca-preview" id="dca-preview"></div>
</div>
```

**5.4 — CSS : champs avancés** (`dashboard.html`)

- Insérer avant `L:1175` (`</style>`)
- Classes :
  - `.of-advanced` — display none par défaut, même padding que `.of-tpsl`
  - `.of-advanced.visible` — display flex, flex-direction column, gap 6px
  - `.dca-preview` — mini grille montrant les paliers DCA (prix + quantité par niveau)
  - `.dca-preview-row` — une ligne par palier (numéro, prix, qty, % du total)
  - `.of-type-tabs` — ajuster pour 6 boutons (réduire font-size à 10px si nécessaire)

**5.5 — JS : `switchOrderType()` étendue** (`dashboard.html`)

- Modifier `L:2497 → L:2511`
- Masquer tous les `.of-advanced` au switch
- Afficher le bloc correspondant au type sélectionné :
  - `'oco'` → `#oco-fields.visible`
  - `'trailing'` → `#trailing-fields.visible`
  - `'iceberg'` → `#iceberg-fields.visible`
  - `'dca'` → `#dca-fields.visible`, appeler `updateDCAPreview()`
- Pour `'limit'` et `'market'` : masquer tous les champs avancés
- Gérer le champ prix : disabled pour market, activé pour tous les autres

**5.6 — JS : `updateDCAPreview()`** (`dashboard.html`)

- Insérer avant `L:3142`
- Lit les valeurs : prix de base, quantité totale, levels, step%, multiplier
- Calcule les paliers :
  - Level 1 : prix de base, qty = total / somme_des_poids
  - Level N : prix = base × (1 - step% × N), qty = qty_level1 × multiplier^(N-1)
- Rend un tableau de preview dans `#dca-preview` :
```
Level 1: $67,000 — 0.001 BTC (20%)
Level 2: $65,660 — 0.0015 BTC (30%)
Level 3: $64,320 — 0.00225 BTC (45%)
...
```
- Appeler sur `oninput` des champs DCA

**5.7 — JS : `executeOrder()` étendue** (`dashboard.html`)

- Modifier `executeOrder()` (`L:2605`)
- Selon `orderType` :
  - `'limit'` / `'market'` : comportement existant (inchangé)
  - `'oco'` : envoyer `POST /api/execute` avec `type: "oco"` + `oco_limit` + `oco_stop`
  - `'trailing'` : envoyer avec `type: "trailing"` + `trail_pct` + `trail_activation`
  - `'iceberg'` : envoyer avec `type: "iceberg"` + `visible_pct` + `slices`
  - `'dca'` : envoyer avec `type: "dca"` + `levels` + `step_pct` + `multiplier`
- Toast de confirmation adaptée au type

**5.8 — Backend `POST /api/execute` étendu** (`server.py`)

- Modifier `L:2481 → L:2556`
- Après la validation initiale existante, brancher sur `order_type` :
  - **OCO** : créer 2 entrées dans `scheduled_orders` liées par `parent_id`
    - Ordre limit + ordre stop, status `"pending"`
    - En mode paper : exécuter le limit immédiatement, stocker le stop
  - **Trailing** : créer 1 entrée dans `scheduled_orders`
    - `trail_pct`, `trigger_price` = prix actuel
    - En mode paper : simuler le trailing (stocker le prix haut/bas)
  - **Iceberg** : calculer les slices, créer N entrées `scheduled_orders`
    - Chaque slice = quantité totale / N
    - Exécuter la première slice immédiatement, les autres en `"pending"`
  - **DCA** : calculer les paliers, créer N entrées
    - Chaque palier = prix décalé de step%, quantité selon multiplier
    - Exécuter le premier palier, les autres en `"pending"`
- Retourner `{success, order_ids: [1,2,3], type: "dca", levels: 5}`

**5.9 — Route `GET /api/scheduled-orders`** (`server.py`)

- Insérer avant `L:2785`
- Retourner toutes les entrées de `scheduled_orders` triées par `created_at DESC`
- Filtrer par `?status=pending` optionnel
- Inclure le lien parent (OCO pair, iceberg/DCA siblings)

**5.10 — Route `DELETE /api/scheduled-orders/<id>`** (`server.py`)

- Insérer après la route GET
- Annuler un ordre programmé : mettre `status = "cancelled"`
- Si c'est un parent OCO : annuler aussi le sibling

**5.11 — Affichage ordres programmés dans Bottom Panel** (`dashboard.html`)

- Modifier `switchBPTab()` (`L:2373`)
- Ajouter `case 'open-orders'` : fetch `GET /api/scheduled-orders?status=pending`
- Rendre un tableau : Type, Symbol, Side, Price/Trigger, Qty, Status, bouton Cancel
- Chaque ligne a un bouton ✕ qui appelle `cancelScheduledOrder(id)`

**5.12 — JS : `cancelScheduledOrder(id)`** (`dashboard.html`)

- Insérer avant `L:3142`
- `DELETE /api/scheduled-orders/<id>`
- Toast "Order cancelled", refresh le tableau

---

#### Critères de validation

| # | Critère | Comment vérifier |
|---|---------|------------------|
| V5.1 | `python3 -m py_compile server.py` passe | Terminal |
| V5.2 | Les 6 onglets de type apparaissent | Navigateur |
| V5.3 | Sélectionner OCO affiche limit+stop fields | Cliquer OCO |
| V5.4 | Sélectionner DCA affiche le preview des paliers | Cliquer DCA, remplir les champs |
| V5.5 | Le preview DCA se met à jour en temps réel | Modifier step% ou multiplier |
| V5.6 | Exécuter un OCO paper crée 2 entrées | POST puis GET scheduled-orders |
| V5.7 | Exécuter un DCA paper crée N paliers | POST avec 5 levels |
| V5.8 | Les ordres pending apparaissent dans Open Orders | Cliquer l'onglet Open Orders |
| V5.9 | Annuler un ordre OCO annule aussi le sibling | Cancel un leg, vérifier l'autre |
| V5.10 | La table `scheduled_orders` est créée au boot | `sqlite3 jarvis.db .tables` |

---

#### Note de reprise

> Cette étape modifie `POST /api/execute` (L:2481) — la route la plus critique du système.
> Procéder avec précaution : ne pas casser le flux limit/market existant.
> Ajouter les nouveaux types EN PLUS, jamais en remplacement.
> La table `scheduled_orders` est indépendante de `paper_trades` — pas de migration.
> L'exécution réelle des ordres programmés (trailing qui suit le prix) est simulée
> en paper mode. En mode live, seuls limit/market passent à l'exchange via CCXT.
> Les ordres avancés restent dans `scheduled_orders` comme couche applicative.

---
### ÉTAPE 6.0 — EFFETS SONORES (WEB AUDIO API)

**Commit cible** : `feat: step 34 — sound effects via Web Audio API`

**Objectif** : Ajouter un feedback sonore synthétique à 7 événements clés du dashboard
via l'API Web Audio (oscillateurs, pas de fichiers .mp3). Sons courts et discrets,
avec un toggle mute global dans la navbar. Aucun fichier externe, aucune dépendance.

---

#### Fichiers touchés

| Fichier | Action | Zone d'insertion |
|---------|--------|------------------|
| `server.py` | **Aucun** — fonctionnalité 100% frontend | — |
| `dashboard.html` | CSS : bouton mute navbar | Avant `L:1175` (`</style>`) |
| `dashboard.html` | HTML : bouton mute dans navbar-actions | Modifier `L:1192` |
| `dashboard.html` | JS : moteur audio + 7 sons | Avant `L:3142` (`// INIT ON DOM READY`) |
| `dashboard.html` | JS : variable globale `soundEnabled` | Dans Global State après `L:1614` |
| `dashboard.html` | JS : intégrer les sons dans les fonctions existantes | Modifier 7 fonctions existantes |

---

#### Sous-tâches

**6.1 — JS : état global son** (`dashboard.html`)

- Insérer après `L:1614` (fin de `indicatorState`)
```javascript
let soundEnabled = localStorage.getItem('jarvis_sound') !== 'off';
let audioCtx = null;
```
- `audioCtx` initialisé au premier clic utilisateur (politique navigateur autoplay)

**6.2 — JS : fonction `initAudio()`** (`dashboard.html`)

- Insérer avant `L:3142`
- Crée le `AudioContext` au premier appel :
```javascript
function initAudio() {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    return audioCtx;
}
```

**6.3 — JS : 7 fonctions de son** (`dashboard.html`)

- Insérer après `initAudio()`
- Chaque fonction vérifie `if (!soundEnabled) return;` en premier

| Fonction | Événement | Son |
|----------|-----------|-----|
| `playOrderSound()` | Ordre exécuté avec succès | Ding aigu : sine 880Hz→1200Hz, 150ms, gain 0.3 |
| `playErrorSound()` | Erreur d'exécution ou validation | Buzz grave : square 200Hz, 200ms, gain 0.2 |
| `playAlertSound()` | Alerte déclenchée (étape 3.0) | Double bip : sine 660Hz × 2 coups, 100ms chacun, gap 80ms |
| `playKillSound()` | Kill switch activé | Alarme : sawtooth 440Hz→220Hz descendant, 500ms, gain 0.4 |
| `playClickSound()` | Changement de tab/bouton toolbar | Tick subtil : sine 1000Hz, 30ms, gain 0.1 |
| `playDipTopSound()` | Signal dip/top confluence ≥60 | Montée : sine 400Hz→800Hz, 300ms, gain 0.25 |
| `playTradeCloseSound()` | Position fermée (PnL positif) | Accord : sine 523Hz + 659Hz + 784Hz simultanés, 200ms |

- Pattern commun pour chaque fonction :
```javascript
function playOrderSound() {
    if (!soundEnabled) return;
    var ctx = initAudio();
    var osc = ctx.createOscillator();
    var gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(1200, ctx.currentTime + 0.15);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.15);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.15);
}
```

**6.4 — JS : fonction `toggleSound()`** (`dashboard.html`)

- Insérer après les 7 fonctions de son
```javascript
function toggleSound() {
    soundEnabled = !soundEnabled;
    localStorage.setItem('jarvis_sound', soundEnabled ? 'on' : 'off');
    var btn = $('btn-sound');
    if (btn) btn.textContent = soundEnabled ? '🔊' : '🔇';
    if (soundEnabled) playClickSound();
}
```

**6.5 — HTML : bouton mute dans navbar** (`dashboard.html`)

- Modifier `L:1192` (`navbar-actions`)
- Ajouter avant le bouton AI :
```html
<button class="btn-nav btn-sound" id="btn-sound" onclick="toggleSound()">🔊</button>
```

**6.6 — CSS : bouton son** (`dashboard.html`)

- Insérer avant `L:1175` (`</style>`)
```css
.btn-sound { font-size: 14px; min-width: 32px; }
.btn-sound.muted { opacity: 0.4; }
```

**6.7 — Intégration dans les fonctions existantes** (`dashboard.html`)

7 points d'insertion dans des fonctions déjà existantes :

| Fonction cible | Ligne | Ajouter | Emplacement dans la fonction |
|----------------|-------|---------|------------------------------|
| `executeOrder()` | `L:2605` | `playOrderSound();` | Après le `showToast` de succès (~L:2652) |
| `executeOrder()` | `L:2605` | `playErrorSound();` | Dans chaque `showToast(..., 'error')` (~L:2612, 2616) |
| `confirmKillSwitch()` | `L:2753` | `playKillSound();` | Après le fetch réussi (~L:2763) |
| `closePosition()` | `L:2664` | `playTradeCloseSound();` | Après le `showToast` de succès (~L:2682) |
| `loadDipTop()` | `L:3038` | `playDipTopSound();` | Quand `confluence_score >= 60` (~L:3048) |
| `showToast()` | `L:2689` | `playAlertSound();` | Quand `type === 'warning'` uniquement |
| `switchBPTab()` | `L:2373` | `playClickSound();` | En début de fonction |

**6.8 — Init du bouton son au chargement** (`dashboard.html`)

- Dans `DOMContentLoaded` (`L:3143`) ajouter :
```javascript
var soundBtn = $('btn-sound');
if (soundBtn) soundBtn.textContent = soundEnabled ? '🔊' : '🔇';
```

---

#### Critères de validation

| # | Critère | Comment vérifier |
|---|---------|------------------|
| V6.1 | Le bouton 🔊 apparaît dans la navbar | Navigateur |
| V6.2 | Cliquer le bouton toggle mute/unmute | Cliquer, vérifier icône change |
| V6.3 | Exécuter un ordre paper → ding aigu | Passer un ordre, écouter |
| V6.4 | Erreur de validation → buzz grave | Soumettre sans quantité |
| V6.5 | Activer kill switch → alarme descendante | Cliquer KILL |
| V6.6 | Signal dip/top fort → son montant | Attendre un signal ≥60 |
| V6.7 | Le mute persiste au refresh (localStorage) | Muter, F5, vérifier état |
| V6.8 | Aucun son quand muted | Muter puis déclencher chaque événement |
| V6.9 | Pas d'erreur console au premier clic | Ouvrir devtools, cliquer |

---

#### Note de reprise

> Étape 100% frontend — aucune modification de `server.py`.
> Le `AudioContext` doit être créé APRÈS une interaction utilisateur (politique
> autoplay des navigateurs). `initAudio()` gère ça via lazy init.
> Les 7 fonctions de son sont indépendantes — chacune crée ses propres
> oscillateur + gain et les détruit automatiquement via `osc.stop()`.
> Le localStorage key est `jarvis_sound` (valeurs: `"on"` / `"off"`).
> Si l'étape 3.0 (Alertes) n'est pas encore implémentée, le `playAlertSound()`
> dans `showToast` sera inactif car le type `'warning'` n'existe pas encore.

---
### ÉTAPE 7.0 — SPARKLINES (MINI-CHARTS SVG)

**Commit cible** : `feat: step 35 — sparkline mini-charts in ticker and asset bar`

**Objectif** : Ajouter des mini-courbes SVG (50×16px) à côté de chaque symbole dans
le ticker footer et dans l'asset bar. Chaque sparkline montre les 20 derniers
prix pour donner un aperçu visuel instantané de la tendance. Les données viennent
d'une nouvelle route API légère qui retourne des mini-séries.

---

#### Fichiers touchés

| Fichier | Action | Zone d'insertion |
|---------|--------|------------------|
| `server.py` | Nouvelle route `GET /api/sparklines` | Avant `L:2785` (`@app.route("/")`) |
| `dashboard.html` | CSS : svg sparkline | Avant `L:1175` (`</style>`) |
| `dashboard.html` | JS : `buildSparklineSVG()` (pur SVG string) | Avant `L:3142` (`// INIT ON DOM READY`) |
| `dashboard.html` | JS : modifier `loadTicker()` | Modifier `L:2202` |
| `dashboard.html` | JS : modifier `loadPriceData()` | Modifier `L:2248` |
| `dashboard.html` | HTML : placeholder dans asset bar | Modifier `L:1237` (avant asset-shortcuts) |

---

#### Sous-tâches

**7.1 — Route API `GET /api/sparklines`** (`server.py`)

- Insérer avant `L:2785`
- Pour chaque paire dans `["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","DOGEUSDT"]` :
  - Fetch klines 15m, limit=20 via `fetch_binance()` (cache TTL 30s)
  - Extraire uniquement les closes : `[float(k[4]) for k in raw]`
- Pour GOLD/SILVER : utiliser `fetch_stooq_price()` (un seul point, pas de sparkline)
- Retourner :
```json
{
  "BTCUSDT": [67000, 67120, 67050, 66980, ...],
  "ETHUSDT": [3520, 3515, 3530, 3542, ...],
  "SOLUSDT": [145.2, 144.8, 145.5, ...],
  "XRPUSDT": [0.512, 0.515, 0.511, ...],
  "DOGEUSDT": [0.155, 0.156, 0.154, ...]
}
```
- Cache TTL = 30s (aligner avec le refresh ticker)

**7.2 — JS : `buildSparklineSVG(prices, width, height, color)`** (`dashboard.html`)

- Insérer avant `L:3142`
- Fonction pure qui retourne un string HTML `<svg>...</svg>`
- Paramètres par défaut : `width=50, height=16, color='var(--accent)'`
- Algorithme :
  - Si `prices.length < 2` : retourner chaîne vide
  - Trouver min/max des prix
  - Normaliser chaque point : `x = i * (width / (len-1))`, `y = height - ((p - min) / (max - min)) * height`
  - Construire un attribut `points` pour `<polyline>`
  - Couleur : `--green` si dernier > premier, `--red` si dernier < premier, `--accent` sinon
```javascript
function buildSparklineSVG(prices, width, height, color) {
    if (!prices || prices.length < 2) return '';
    width = width || 50;
    height = height || 16;
    var min = Math.min.apply(null, prices);
    var max = Math.max.apply(null, prices);
    var range = max - min || 1;
    if (!color) color = prices[prices.length-1] >= prices[0] ? 'var(--green)' : 'var(--red)';
    var pts = '';
    for (var i = 0; i < prices.length; i++) {
        var x = (i / (prices.length - 1)) * width;
        var y = height - ((prices[i] - min) / range) * (height - 2) - 1;
        pts += x.toFixed(1) + ',' + y.toFixed(1) + ' ';
    }
    return '<svg class="sparkline" viewBox="0 0 ' + width + ' ' + height
        + '" width="' + width + '" height="' + height + '">'
        + '<polyline points="' + pts.trim() + '" fill="none" stroke="' + color
        + '" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
}
```

**7.3 — JS : variable globale sparkline data** (`dashboard.html`)

- Insérer après `L:1614` (fin de `indicatorState`)
```javascript
let sparklineData = {};
```

**7.4 — JS : `loadSparklines()`** (`dashboard.html`)

- Insérer après `buildSparklineSVG()`
- Fetch `GET /api/sparklines`
- Stocker dans `sparklineData`
- Appelée depuis `loadTicker()` quand les données sont vides ou toutes les 30s

**7.5 — JS : modifier `loadTicker()` pour injecter les sparklines** (`dashboard.html`)

- Modifier `L:2212 → L:2224` (boucle de rendu du ticker footer)
- Après le prix et le changement %, ajouter l'appel SVG :
```javascript
html += '<span class="ft-ticker-item">'
    + '<span class="sym">' + t.symbol + '</span>'
    + buildSparklineSVG(sparklineData[t.symbol], 40, 14)
    + '<span class="val ' + cls + '">' + fmt(parseFloat(t.price)) + ' ' + sign + parseFloat(t.change_pct).toFixed(2) + '%</span>'
    + '</span>';
```

**7.6 — HTML : placeholder sparkline dans asset bar** (`dashboard.html`)

- Modifier `L:1237` — ajouter un `<span>` avant les asset-shortcuts :
```html
<div class="asset-sparkline" id="asset-sparkline"></div>
<div class="asset-shortcuts">
```

**7.7 — JS : modifier `loadPriceData()` pour mettre à jour l'asset sparkline** (`dashboard.html`)

- Modifier `loadPriceData()` (`L:2248`)
- Après les stats existantes, ajouter :
```javascript
var sparkEl = $('asset-sparkline');
if (sparkEl && sparklineData[symbol]) {
    sparkEl.innerHTML = buildSparklineSVG(sparklineData[symbol], 80, 24);
}
```

**7.8 — CSS sparkline** (`dashboard.html`)

- Insérer avant `L:1175` (`</style>`)
```css
.sparkline {
    vertical-align: middle;
    opacity: 0.85;
}
.ft-ticker-item .sparkline {
    margin: 0 2px;
}
.asset-sparkline {
    display: flex;
    align-items: center;
    margin: 0 8px;
}
.asset-sparkline .sparkline {
    width: 80px;
    height: 24px;
}
```

**7.9 — Intégration refresh** (`dashboard.html`)

- Dans `startAutoRefresh()` (`L:3079`) : appeler `loadSparklines()` dans l'intervalle 30s du ticker (~L:3087)
- Dans `DOMContentLoaded` (`L:3143`) : appeler `loadSparklines()` après `loadTicker()`
- Dans `changeSymbol()` (`L:2020`) : mettre à jour `#asset-sparkline`

---

#### Critères de validation

| # | Critère | Comment vérifier |
|---|---------|------------------|
| V7.1 | `python3 -m py_compile server.py` passe | Terminal |
| V7.2 | `GET /api/sparklines` retourne 5 tableaux de 20 prix | `curl` |
| V7.3 | Les sparklines s'affichent dans le ticker footer | Navigateur, regarder le bandeau bas |
| V7.4 | Couleur verte si tendance haussière, rouge si baissière | Comparer direction vs couleur |
| V7.5 | La sparkline apparaît dans l'asset bar | Regarder à côté du prix principal |
| V7.6 | Changer de symbole met à jour l'asset sparkline | Cliquer BTC → ETH |
| V7.7 | Les SVG sont nets (pas de pixelisation) | Zoom navigateur 200% |
| V7.8 | Auto-refresh toutes les 30s fonctionne | Attendre, observer changement |

---

#### Note de reprise

> Étape légère — 1 route API simple + 1 fonction SVG pure + intégration dans
> 2 fonctions existantes (`loadTicker`, `loadPriceData`).
> Le SVG est construit comme un string HTML (pas `document.createElementNS`).
> Les données sparkline sont cachées 30s côté serveur et stockées dans
> `sparklineData` côté client pour éviter les refetch inutiles.
> GOLD/SILVER n'auront pas de sparkline (Stooq ne fournit qu'un prix spot).
> La fonction `buildSparklineSVG` est réutilisable pour l'étape 8.0 (Heatmap).

---
### ÉTAPE 8.0 — HEATMAP (PERFORMANCE RELATIVE)

**Commit cible** : `feat: step 36 — market heatmap with relative performance`

**Objectif** : Ajouter une bande de heatmap horizontale entre l'asset bar et le
main layout. Chaque cellule représente une paire (BTC, ETH, SOL, XRP, DOGE,
GOLD, SILVER) colorée selon sa performance 24h : vert intense pour forte hausse,
rouge intense pour forte baisse, neutre au centre. Taille de cellule proportionnelle
au volume. Les données viennent de la route `/api/ticker` existante enrichie.

---

#### Fichiers touchés

| Fichier | Action | Zone d'insertion |
|---------|--------|------------------|
| `server.py` | Enrichir la route `GET /api/ticker` | Modifier `L:1953 → L:1986` |
| `dashboard.html` | CSS : bande heatmap | Avant `L:1175` (`</style>`) |
| `dashboard.html` | HTML : conteneur heatmap | Après `L:1244` (après `</div>` asset-bar, avant main-layout) |
| `dashboard.html` | JS : `renderHeatmap()` | Avant `L:3142` (`// INIT ON DOM READY`) |
| `dashboard.html` | JS : intégrer dans `loadTicker()` | Modifier `L:2202` |

---

#### Sous-tâches

**8.1 — Enrichir `GET /api/ticker`** (`server.py`)

- Modifier `L:1964 → L:1973` (boucle des paires Binance)
- Ajouter `volume`, `high`, `low` depuis le 24hr ticker (déjà fetché à L:1966) :
```python
result.append({
    "symbol": pair,
    "base": SUPPORTED_SYMBOLS[pair]["base"],
    "price": price_map[pair],
    "change_pct": change_pct,
    "high": float(ticker_24h.get("highPrice", 0)) if ticker_24h else 0,
    "low": float(ticker_24h.get("lowPrice", 0)) if ticker_24h else 0,
    "volume": float(ticker_24h.get("quoteVolume", 0)) if ticker_24h else 0,
})
```
- Pour GOLD/SILVER (`L:1975 → L:1984`) : ajouter `"volume": 0, "high": 0, "low": 0`
- Retourner le tout emballé : `{"tickers": result}` au lieu de `result` directement
- **Attention** : vérifier que `loadTicker()` côté JS utilise déjà `data.tickers`
  (oui, L:2207 fait `const tickers = data.tickers || [];` — déjà compatible)

**8.2 — HTML : conteneur heatmap** (`dashboard.html`)

- Insérer après `L:1244` (fin de `</div>` asset-bar) et avant `L:1246` (`<!-- MAIN LAYOUT -->`)
```html
<!-- HEATMAP -->
<div class="heatmap-bar" id="heatmap-bar"></div>
```

**8.3 — CSS heatmap** (`dashboard.html`)

- Insérer avant `L:1175` (`</style>`)
```css
.heatmap-bar {
    display: flex;
    height: 28px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    overflow: hidden;
}
.hm-cell {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 0 6px;
    font-size: 10px;
    font-weight: 600;
    font-family: var(--font-mono);
    color: white;
    cursor: pointer;
    transition: opacity 0.15s ease;
    min-width: 40px;
    position: relative;
    overflow: hidden;
}
.hm-cell:hover { opacity: 0.85; }
.hm-cell .hm-sym { font-size: 9px; opacity: 0.8; }
.hm-cell .hm-pct { font-size: 10px; font-weight: 700; }
```

**8.4 — JS : `heatmapColorScale(changePct)`** (`dashboard.html`)

- Insérer avant `L:3142`
- Convertit un pourcentage de changement en couleur RGB :
  - `changePct >= +5%` → vert intense `rgb(14, 203, 129)` (#0ecb81)
  - `changePct == 0%` → gris neutre `rgb(60, 65, 80)` (--surface-2)
  - `changePct <= -5%` → rouge intense `rgb(246, 70, 93)` (#f6465d)
  - Interpolation linéaire entre les bornes
- Algorithme :
```javascript
function heatmapColorScale(pct) {
    var clamped = Math.max(-5, Math.min(5, pct));
    var t = (clamped + 5) / 10;
    var r = Math.round(246 + (14 - 246) * t);
    var g = Math.round(70 + (203 - 70) * t);
    var b = Math.round(93 + (129 - 93) * t);
    return 'rgb(' + r + ',' + g + ',' + b + ')';
}
```

**8.5 — JS : `renderHeatmap(tickers)`** (`dashboard.html`)

- Insérer après `heatmapColorScale()`
- Paramètre : le tableau `tickers` déjà disponible dans `loadTicker()`
- Calcul de la largeur proportionnelle au volume :
  - `totalVolume = sum(ticker.volume)` (ignorer GOLD/SILVER si volume=0)
  - Chaque cellule : `flex: <volume / totalVolume>` ou `min-width: 40px` si pas de volume
- Pour chaque ticker :
  - Couleur de fond = `heatmapColorScale(change_pct)`
  - Contenu = symbole court (BTC, ETH...) + changement %
  - `onclick` = `changeSymbol(ticker.symbol)`
- Injecter dans `#heatmap-bar`
```javascript
function renderHeatmap(tickers) {
    var el = $('heatmap-bar');
    if (!el || !tickers || !tickers.length) return;
    var totalVol = 0;
    for (var i = 0; i < tickers.length; i++) totalVol += (tickers[i].volume || 1);
    var html = '';
    for (var i = 0; i < tickers.length; i++) {
        var t = tickers[i];
        var pct = parseFloat(t.change_pct) || 0;
        var bg = heatmapColorScale(pct);
        var flex = ((t.volume || 1) / totalVol * 100).toFixed(1);
        var sign = pct >= 0 ? '+' : '';
        html += '<div class="hm-cell" style="flex:' + flex + ';background:' + bg
            + '" onclick="changeSymbol(\'' + t.symbol + '\')">'
            + '<span class="hm-sym">' + (t.base || t.symbol) + '</span>'
            + '<span class="hm-pct">' + sign + pct.toFixed(2) + '%</span>'
            + '</div>';
    }
    el.innerHTML = html;
}
```

**8.6 — JS : intégrer dans `loadTicker()`** (`dashboard.html`)

- Modifier `loadTicker()` (`L:2202`)
- Après la construction du footer ticker (~L:2225), ajouter :
```javascript
renderHeatmap(tickers);
```
- La heatmap se rafraîchit automatiquement avec le ticker (toutes les 10s via auto-refresh)

**8.7 — Tooltip au survol (optionnel enrichissement)** (`dashboard.html`)

- Dans `renderHeatmap()`, ajouter un `title` attribut sur chaque `.hm-cell` :
```javascript
+ '" title="' + t.symbol + ': $' + fmt(parseFloat(t.price)) + ' (' + sign + pct.toFixed(2) + '%)"'
```
- Tooltip natif navigateur — pas de lib, pas de JS supplémentaire

---

#### Critères de validation

| # | Critère | Comment vérifier |
|---|---------|------------------|
| V8.1 | `python3 -m py_compile server.py` passe | Terminal |
| V8.2 | `GET /api/ticker` retourne `volume`, `high`, `low` par paire | `curl` |
| V8.3 | La bande heatmap s'affiche entre asset bar et chart | Navigateur |
| V8.4 | BTC en hausse → cellule verte, en baisse → rouge | Comparer couleur vs change_pct |
| V8.5 | BTC (plus gros volume) a la cellule la plus large | Comparer visuellement |
| V8.6 | Cliquer une cellule change le symbole actif | Cliquer sur ETH, vérifier chart |
| V8.7 | Tooltip au survol affiche prix + % | Hover sur une cellule |
| V8.8 | Rafraîchissement automatique toutes les 10s | Attendre, observer changement couleurs |

---

#### Note de reprise

> Cette étape modifie la route `/api/ticker` existante (L:1953) — ajouter des champs
> au retour, ne rien supprimer. Le frontend lit déjà `data.tickers` (L:2207) donc
> pas de breaking change. La heatmap est rendue dans `loadTicker()` — pas de
> fetch séparé. La fonction `heatmapColorScale()` fait une interpolation linéaire
> entre rouge (-5%) et vert (+5%) avec clamping aux bornes.
> GOLD/SILVER auront `volume: 0` → largeur minimale (min-width 40px).

---
### ÉTAPE 9.0 — RESPONSIVE MOBILE

**Commit cible** : `feat: step 37 — responsive layout for tablet and mobile`

**Objectif** : Rendre le dashboard utilisable sur tablette (768-1024px) et mobile
(<768px). Le layout 3 colonnes se transforme en colonne unique avec le right panel
en slide-over. Un bouton hamburger dans la navbar pilote la navigation mobile.
Le chart reste prioritaire. Aucun changement de HTML structurel majeur — uniquement
des media queries CSS et un toggle JS minimal.

---

#### Fichiers touchés

| Fichier | Action | Zone d'insertion |
|---------|--------|------------------|
| `server.py` | **Aucun** — fonctionnalité 100% CSS/JS frontend | — |
| `dashboard.html` | Meta viewport | Déjà présent `L:5` ✓ |
| `dashboard.html` | CSS : media queries tablette + mobile | Avant `L:1175` (`</style>`) |
| `dashboard.html` | HTML : bouton hamburger dans navbar | Modifier `L:1191` (avant navbar-spacer) |
| `dashboard.html` | HTML : overlay backdrop pour slide-over | Après `L:1448` (`</div><!-- /main-layout -->`) |
| `dashboard.html` | JS : `toggleMobilePanel()` | Avant `L:3142` (`// INIT ON DOM READY`) |

---

#### Sous-tâches

**9.1 — HTML : bouton hamburger** (`dashboard.html`)

- Modifier `L:1191` — ajouter avant `<div class="navbar-spacer">` :
```html
<button class="btn-nav btn-hamburger" id="btn-hamburger" onclick="toggleMobilePanel()">&#9776;</button>
```
- Masqué par défaut en desktop (CSS), visible en mobile

**9.2 — HTML : overlay backdrop** (`dashboard.html`)

- Insérer après `L:1448` (`</div><!-- /main-layout -->`) :
```html
<div class="mobile-overlay" id="mobile-overlay" onclick="toggleMobilePanel()"></div>
```

**9.3 — CSS : variables responsive** (`dashboard.html`)

- Insérer avant `L:1175` (`</style>`)
- Ajouter les styles de base pour le hamburger et l'overlay :
```css
.btn-hamburger { display: none; font-size: 18px; }
.mobile-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.5);
    z-index: 149;
}
.mobile-overlay.visible { display: block; }
```

**9.4 — CSS : media query TABLETTE (768px → 1024px)** (`dashboard.html`)

- Insérer après les styles de base (avant `</style>`)
```css
@media (max-width: 1024px) {
    /* Navbar : cacher les liens texte, garder les boutons */
    .navbar-menu a { font-size: 10px; padding: 4px 6px; }

    /* Drawing toolbar : cacher (trop petit pour dessiner) */
    .draw-toolbar { display: none; }

    /* Right panel : réduire à 240px */
    .right-panel { width: 240px; min-width: 240px; }

    /* Order form : réduire les paddings */
    .order-form { padding: 6px; }
    .of-type-tabs button { font-size: 9px; padding: 3px 4px; }

    /* Asset bar : masquer OI et Funding */
    .asset-stat:nth-child(n+6) { display: none; }

    /* Footer : réduire */
    .ft-info span:nth-child(n+4) { display: none; }

    /* JARVIS chat : pleine largeur en bas */
    .jarvis-chat { width: 300px; right: 8px; }
}
```

**9.5 — CSS : media query MOBILE (<768px)** (`dashboard.html`)

- Insérer après la media query tablette
```css
@media (max-width: 768px) {
    /* Hamburger visible */
    .btn-hamburger { display: flex; }

    /* Navbar : compacter */
    .navbar-menu { display: none; }
    .navbar-logo span { display: none; }
    .navbar-clock { display: none; }

    /* Asset bar : scroll horizontal, masquer stats secondaires */
    .asset-bar { overflow-x: auto; gap: 6px; padding: 4px 8px; }
    .asset-stat:nth-child(n+4) { display: none; }
    .asset-shortcuts { display: none; }

    /* Heatmap bar (étape 8.0) : masquer texte, garder couleurs */
    .hm-cell .hm-sym { display: none; }
    .hm-cell { min-width: 30px; font-size: 8px; }

    /* Main layout : colonne unique */
    .main-layout {
        flex-direction: column;
        height: auto;
        overflow-y: auto;
    }

    /* Chart area : hauteur fixe adaptée */
    .chart-area {
        border-right: none;
        border-bottom: 1px solid var(--border);
        height: 50vh;
        min-height: 300px;
    }

    /* Sub-charts : plus compacts */
    .subchart-wrap { height: 60px; min-height: 60px; }

    /* Drawing toolbar : masquer */
    .draw-toolbar { display: none; }

    /* Right panel : slide-over depuis la droite */
    .right-panel {
        position: fixed;
        top: 48px;
        right: -300px;
        width: 280px;
        height: calc(100vh - 48px - 28px);
        z-index: 150;
        transition: right 0.25s ease;
        border-left: 1px solid var(--border);
        overflow-y: auto;
    }
    .right-panel.open { right: 0; }

    /* Bottom panel : scroll horizontal pour les tabs */
    .bp-tabs { overflow-x: auto; flex-wrap: nowrap; }
    .bp-tabs button { white-space: nowrap; font-size: 10px; }

    /* Footer : simplifier */
    .footer { height: 24px; font-size: 9px; gap: 6px; }
    .ft-ticker { display: none; }
    .ft-info span:nth-child(n+3) { display: none; }

    /* JARVIS chat : plein écran mobile */
    .jarvis-chat {
        width: 100%;
        height: calc(100vh - 80px);
        bottom: 28px;
        right: 0;
        border-radius: 0;
    }

    /* Modals : pleine largeur */
    .modal { width: 95vw; max-height: 85vh; }
}
```

**9.6 — CSS : media query PETIT MOBILE (<480px)** (`dashboard.html`)

- Insérer après la media query mobile
```css
@media (max-width: 480px) {
    .navbar { padding: 0 6px; gap: 4px; }
    .btn-nav { padding: 4px 6px; font-size: 10px; }
    .chart-area { height: 40vh; min-height: 250px; }
    .asset-bar { height: auto; flex-wrap: wrap; }
    .asset-stat:nth-child(n+3) { display: none; }
    .right-panel { width: 100%; right: -100%; }
    .right-panel.open { right: 0; }
}
```

**9.7 — JS : `toggleMobilePanel()`** (`dashboard.html`)

- Insérer avant `L:3142`
```javascript
function toggleMobilePanel() {
    var panel = document.querySelector('.right-panel');
    var overlay = $('mobile-overlay');
    if (!panel) return;
    var isOpen = panel.classList.contains('open');
    panel.classList.toggle('open');
    if (overlay) overlay.classList.toggle('visible');
    // Empêcher scroll du body quand panel ouvert
    document.body.style.overflow = isOpen ? '' : 'hidden';
}
```

**9.8 — JS : fermer le panel au changement de symbole** (`dashboard.html`)

- Modifier `changeSymbol()` (`L:2020`)
- Ajouter en fin de fonction :
```javascript
// Fermer le panel mobile si ouvert
var panel = document.querySelector('.right-panel');
if (panel && panel.classList.contains('open')) toggleMobilePanel();
```

**9.9 — JS : resize handler pour cleanup** (`dashboard.html`)

- Insérer après `toggleMobilePanel()`
- Si l'utilisateur passe de mobile à desktop (resize fenêtre) :
```javascript
window.addEventListener('resize', function() {
    if (window.innerWidth > 768) {
        var panel = document.querySelector('.right-panel');
        var overlay = $('mobile-overlay');
        if (panel) panel.classList.remove('open');
        if (overlay) overlay.classList.remove('visible');
        document.body.style.overflow = '';
    }
});
```

---

#### Critères de validation

| # | Critère | Comment vérifier |
|---|---------|------------------|
| V9.1 | Desktop (>1024px) : aucun changement visuel | Ouvrir en plein écran |
| V9.2 | Tablette (768-1024px) : right panel réduit, stats masquées | DevTools responsive 800px |
| V9.3 | Mobile (<768px) : layout colonne unique | DevTools responsive 375px |
| V9.4 | Le hamburger ☰ apparaît en mobile | Vérifier navbar à 375px |
| V9.5 | Cliquer ☰ ouvre le right panel en slide-over | Tester le toggle |
| V9.6 | L'overlay assombrit le fond quand panel ouvert | Observer le backdrop |
| V9.7 | Cliquer l'overlay ferme le panel | Cliquer hors du panel |
| V9.8 | Le chart occupe ~50% de l'écran mobile | Vérifier la hauteur |
| V9.9 | Les modals sont pleine largeur en mobile | Ouvrir Settings à 375px |
| V9.10 | Resize desktop→mobile→desktop ne casse rien | Redimensionner la fenêtre |

---

#### Note de reprise

> Étape 100% frontend — aucune modification de `server.py`.
> Le `<meta viewport>` existe déjà (`L:5`).
> Les media queries utilisent uniquement `max-width` (mobile-first inversé).
> Le right panel passe en `position: fixed` + slide-over en mobile.
> Le `overflow: hidden` sur body empêche le double-scroll.
> Si l'étape 8.0 (Heatmap) n'est pas encore implémentée, les règles `.hm-cell`
> seront simplement ignorées (pas d'erreur CSS).
> Ne jamais mettre `display: none` sur `.chart-area` — le chart doit toujours
> être visible, c'est la pièce centrale du dashboard.

---
### ÉTAPE 10.0 — DARK/LIGHT MODE

**Commit cible** : `feat: step 38 — dark/light theme toggle with chart sync`

**Objectif** : Ajouter un toggle dark/light mode dans la navbar. Le thème light
redéfinit toutes les variables CSS `:root`, synchronise les couleurs des 3 charts
TradingView, et persiste en localStorage. Le mode dark actuel devient le défaut.
Transition fluide via `transition` sur `background-color` et `color`.

---

#### Fichiers touchés

| Fichier | Action | Zone d'insertion |
|---------|--------|------------------|
| `server.py` | **Aucun** — fonctionnalité 100% frontend | — |
| `dashboard.html` | CSS : variables light dans `[data-theme="light"]` | Après `:root` (`L:31`) |
| `dashboard.html` | CSS : transition globale pour le switch | Modifier `L:33` (reset `*`) |
| `dashboard.html` | HTML : bouton toggle dans navbar | Modifier `L:1192` (navbar-actions) |
| `dashboard.html` | JS : état global thème | Dans Global State après `L:1614` |
| `dashboard.html` | JS : `toggleTheme()` + sync charts | Avant `L:3142` (`// INIT ON DOM READY`) |
| `dashboard.html` | JS : `chartOptions` / `subChartOptions` dynamiques | Modifier `L:1638` et `L:1723` |
| `dashboard.html` | JS : init thème dans DOMContentLoaded | Dans `L:3143` |

---

#### Sous-tâches

**10.1 — CSS : variables light** (`dashboard.html`)

- Insérer après `L:31` (après la fermeture de `:root`)
- Définir le thème light via l'attribut `data-theme` sur `<html>` :
```css
[data-theme="light"] {
    --bg: #f5f5f5;
    --surface: #ffffff;
    --surface-2: #f0f0f0;
    --surface-3: #e0e0e0;
    --border: #d9d9d9;
    --text: #1a1a1a;
    --text-dim: #555555;
    --text-muted: #999999;
    --green: #0a9e6a;
    --green-bg: rgba(10,158,106,0.1);
    --red: #d63a4a;
    --red-bg: rgba(214,58,74,0.1);
    --accent: #0090b3;
    --accent-bg: rgba(0,144,179,0.1);
    --yellow: #c99400;
    --yellow-bg: rgba(201,148,0,0.1);
    --orange: #cc7000;
}
```

**10.2 — CSS : transition fluide** (`dashboard.html`)

- Modifier `L:33` (le reset `*`)
- Ajouter `transition` pour les propriétés de couleur :
```css
*, *::before, *::after {
    margin: 0; padding: 0; box-sizing: border-box;
    transition: background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease;
}
```

**10.3 — JS : constantes de thème pour les charts** (`dashboard.html`)

- Insérer après `L:1614` (fin du Global State)
```javascript
let currentTheme = localStorage.getItem('jarvis_theme') || 'dark';

var CHART_THEMES = {
    dark: {
        bg: '#0b0e11',
        text: '#848e9c',
        textMuted: '#5e6673',
        grid: 'rgba(43,49,57,0.5)',
        gridSub: 'rgba(43,49,57,0.3)',
        border: '#2b3139',
        crosshair: 'rgba(255,255,255,0.2)',
        watermark: 'rgba(0,212,255,0.04)',
    },
    light: {
        bg: '#ffffff',
        text: '#555555',
        textMuted: '#999999',
        grid: 'rgba(0,0,0,0.06)',
        gridSub: 'rgba(0,0,0,0.04)',
        border: '#d9d9d9',
        crosshair: 'rgba(0,0,0,0.15)',
        watermark: 'rgba(0,144,179,0.04)',
    }
};
```

**10.4 — JS : rendre `chartOptions` dynamique** (`dashboard.html`)

- Modifier `L:1638 → L:1670` (`chartOptions`)
- Remplacer les couleurs hardcodées par une fonction :
```javascript
function getChartOptions() {
    var t = CHART_THEMES[currentTheme];
    return {
        layout: { background: { color: t.bg }, textColor: t.text, fontSize: 11, fontFamily: "'SF Mono', 'Consolas', monospace" },
        grid: { vertLines: { color: t.grid }, horzLines: { color: t.grid } },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: { color: t.crosshair, style: 0, width: 1 },
            horzLine: { color: t.crosshair, style: 0, width: 1 },
        },
        rightPriceScale: { borderColor: t.border, scaleMargins: { top: 0.05, bottom: 0.05 } },
        timeScale: { borderColor: t.border, timeVisible: true, secondsVisible: false },
        watermark: { visible: true, text: 'J.A.R.V.I.S.', fontSize: 48, color: t.watermark },
        handleScroll: { vertTouchDrag: false },
    };
}
var chartOptions = getChartOptions();
```

**10.5 — JS : rendre `subChartOptions` dynamique** (`dashboard.html`)

- Modifier `L:1723 → L:1733` (`subChartOptions`)
- Même pattern :
```javascript
function getSubChartOptions() {
    var t = CHART_THEMES[currentTheme];
    return {
        layout: { background: { color: t.bg }, textColor: t.textMuted, fontSize: 10 },
        grid: { vertLines: { color: t.gridSub }, horzLines: { color: t.gridSub } },
        rightPriceScale: { borderColor: t.border, scaleMargins: { top: 0.1, bottom: 0.1 } },
        timeScale: { visible: false },
        crosshair: { horzLine: { visible: false }, vertLine: { visible: false } },
        handleScroll: { vertTouchDrag: false },
    };
}
var subChartOptions = getSubChartOptions();
```

**10.6 — JS : `applyChartTheme()`** (`dashboard.html`)

- Insérer avant `L:3142`
- Synchronise les 3 charts TradingView avec le thème actif :
```javascript
function applyChartTheme() {
    var t = CHART_THEMES[currentTheme];
    var opts = getChartOptions();
    var subOpts = getSubChartOptions();
    if (mainChart) mainChart.applyOptions(opts);
    if (rsiChart) rsiChart.applyOptions(subOpts);
    if (macdChart) macdChart.applyOptions(subOpts);
}
```

**10.7 — JS : `toggleTheme()`** (`dashboard.html`)

- Insérer après `applyChartTheme()`
```javascript
function toggleTheme() {
    currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', currentTheme);
    localStorage.setItem('jarvis_theme', currentTheme);
    applyChartTheme();
    var btn = $('btn-theme');
    if (btn) btn.textContent = currentTheme === 'dark' ? '☀' : '☾';
}
```

**10.8 — HTML : bouton toggle dans navbar** (`dashboard.html`)

- Modifier `L:1192` (`navbar-actions`)
- Ajouter avant le bouton son (étape 6.0) ou avant le bouton AI :
```html
<button class="btn-nav btn-theme" id="btn-theme" onclick="toggleTheme()">☀</button>
```

**10.9 — CSS : style du bouton thème** (`dashboard.html`)

- Insérer avant `L:1175` (`</style>`)
```css
.btn-theme { font-size: 16px; min-width: 32px; cursor: pointer; }
```

**10.10 — JS : init thème au chargement** (`dashboard.html`)

- Dans `DOMContentLoaded` (`L:3143`), ajouter EN TOUT PREMIER (avant `initMainChart`) :
```javascript
// Appliquer le thème sauvegardé
if (currentTheme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
}
var themeBtn = $('btn-theme');
if (themeBtn) themeBtn.textContent = currentTheme === 'dark' ? '☀' : '☾';
```
- Important : l'attribut `data-theme` doit être appliqué AVANT `initMainChart()`
  pour que les charts soient créés avec les bonnes couleurs dès le départ

**10.11 — Mise à jour `initMainChart()` et `initRSIChart()` / `initMACDChart()`**

- Modifier `initMainChart()` (`L:1673`) : remplacer `chartOptions` statique par `getChartOptions()`
```javascript
mainChart = LightweightCharts.createChart(container, {
    ...getChartOptions(),
    width: container.clientWidth,
    height: container.clientHeight,
});
```
- Modifier `initRSIChart()` (`L:1735`) et `initMACDChart()` (`L:1760`) : idem avec `getSubChartOptions()`

---

#### Critères de validation

| # | Critère | Comment vérifier |
|---|---------|------------------|
| V10.1 | Le bouton ☀/☾ apparaît dans la navbar | Navigateur |
| V10.2 | Cliquer bascule entre dark et light | Cliquer, observer le fond |
| V10.3 | En light : fond blanc, texte noir, borders grises | Vérifier visuellement |
| V10.4 | Les 3 charts (main, RSI, MACD) suivent le thème | Vérifier fond + grille des charts |
| V10.5 | Les couleurs vert/rouge restent lisibles en light | Comparer contraste |
| V10.6 | La transition est fluide (pas de flash) | Observer le switch |
| V10.7 | Le thème persiste au refresh (localStorage) | F5 en mode light, vérifier |
| V10.8 | Le watermark JARVIS est visible dans les deux thèmes | Zoom sur le chart |
| V10.9 | Les modals, toasts, alertes suivent le thème | Ouvrir Settings en light |
| V10.10 | Retour en dark mode fonctionne correctement | Re-cliquer le bouton |

---

#### Note de reprise

> Étape 100% frontend — aucune modification de `server.py`.
> Le principe : `[data-theme="light"]` sur `<html>` surcharge les variables `:root`.
> Toutes les couleurs du CSS utilisent déjà `var(--xxx)` — le switch est automatique.
> SAUF les charts TradingView qui ont des couleurs hardcodées en JS → `applyChartTheme()`
> les met à jour dynamiquement via l'API `chart.applyOptions()`.
> Le `chartOptions` et `subChartOptions` passent de `const` à `var` car ils sont
> maintenant retournés par des fonctions (`getChartOptions()`, `getSubChartOptions()`).
> L'init du thème DOIT être avant `initMainChart()` dans DOMContentLoaded.
> localStorage key : `jarvis_theme` (valeurs : `"dark"` / `"light"`).

---
## 3. DÉPENDANCES & ORDRE D'EXÉCUTION

---

### 3.1 MATRICE DE DÉPENDANCES

Lecture : la ligne **dépend de** la colonne. `●` = dépendance dure, `○` = dépendance souple (fonctionne sans, mais mieux avec).

```
                 1    2    3    4    5    6    7    8    9   10
                MTF  PTF  ALR  DRW  ORD  SND  SPK  HMP  RSP  DRK
  1  MTF         ─                                              
  2  PTF              ─                                         
  3  ALR              ○    ─                                    
  4  DRW                        ─                               
  5  ORD                             ─                          
  6  SND              ○    ○              ─                     
  7  SPK                                       ─               
  8  HMP                                            ─          
  9  RSP                   ○    ○    ○    ○    ○    ○    ─      
 10  DRK                                                     ─ 
```

### 3.2 DÉTAIL DES DÉPENDANCES

| De → Vers | Type | Raison |
|-----------|------|--------|
| 3 (Alertes) → 2 (Portfolio) | ○ souple | Le badge navbar utilise le même pattern que le badge positions — pas bloquant |
| 6 (Sons) → 2 (Portfolio) | ○ souple | `playTradeCloseSound()` s'accroche dans `closePosition()` qui existe déjà |
| 6 (Sons) → 3 (Alertes) | ○ souple | `playAlertSound()` dans `showToast('warning')` — si Alertes pas encore faite, le type `warning` n'existe pas encore, le son ne joue pas (pas d'erreur) |
| 9 (Responsive) → 3-8 | ○ souple | Les media queries référencent des classes de toutes les étapes (`.hm-cell`, `.mtf-panel`, etc.) — si la classe n'existe pas, la règle CSS est ignorée (pas d'erreur) |

### 3.3 ÉTAPES 100% INDÉPENDANTES

Ces étapes n'ont **aucune dépendance entre elles** et peuvent être faites dans n'importe quel ordre :

- **1 (MTF)** — route API isolée + panneau HTML/JS autonome
- **2 (Portfolio)** — route API isolée + onglet Bottom Panel autonome
- **4 (Drawing)** — 100% frontend, canvas overlay isolé
- **5 (Orders)** — étend le formulaire existant, table SQL indépendante
- **7 (Sparklines)** — route API isolée + SVG inline dans ticker
- **8 (Heatmap)** — enrichit `/api/ticker` + bande HTML autonome
- **10 (Dark/Light)** — variables CSS + toggle JS, indépendant de tout

### 3.4 ORDRE D'EXÉCUTION OPTIMAL

Critères de tri :
1. **Indépendantes d'abord** — pas de risque de casse
2. **Backend avant frontend** — les routes API n'ont pas d'impact visuel si le JS n'est pas encore là
3. **Petites étapes d'abord** — momentum + validation rapide
4. **Responsive et thème en dernier** — elles s'adaptent à tout le contenu existant

```
PHASE 1 — FONDATIONS (étapes sans dépendance, petites)
═══════════════════════════════════════════════════════
  Step 29 → Étape 10.0 Dark/Light Mode        ← CSS pur, valide l'infra de thème
  Step 30 → Étape  7.0 Sparklines             ← 1 route + 1 fonction SVG, rapide
  Step 31 → Étape  8.0 Heatmap                ← enrichit ticker, rapide

PHASE 2 — FONCTIONNALITÉS CORE (étapes moyennes, autonomes)
═══════════════════════════════════════════════════════
  Step 32 → Étape  1.0 Multi-Timeframe        ← route + panneau, moyen
  Step 33 → Étape  2.0 Portfolio Tracker       ← 2 routes + SVG pie, moyen
  Step 34 → Étape  3.0 Alertes & Notifications← 4 routes + CRUD, moyen-lourd

PHASE 3 — FONCTIONNALITÉS AVANCÉES (étapes complexes)
═══════════════════════════════════════════════════════
  Step 35 → Étape  4.0 Drawing Tools          ← canvas, événements souris, lourd
  Step 36 → Étape  5.0 Advanced Orders        ← modifie execute, critique
  Step 37 → Étape  6.0 Effets Sonores         ← Web Audio, intègre dans existant

PHASE 4 — POLISH (s'adapte à tout le contenu)
═══════════════════════════════════════════════════════
  Step 38 → Étape  9.0 Responsive Mobile      ← media queries sur tout le contenu final
```

### 3.5 POURQUOI CET ORDRE

| Position | Étape | Justification |
|----------|-------|---------------|
| 1er | Dark/Light | Pose l'infra `[data-theme]` — toutes les étapes suivantes bénéficient automatiquement du thème light si elles utilisent `var(--xxx)` |
| 2e-3e | Sparklines + Heatmap | Petites, visuellement impactantes, valident le cycle complet route→JS→rendu |
| 4e-5e | MTF + Portfolio | Ajoutent des panneaux complets — testent l'intégration de nouvelles sections |
| 6e | Alertes | Plus complexe (4 routes + table SQL + CRUD) — nécessite un cycle de test plus long |
| 7e | Drawing Tools | Le plus complexe côté frontend (canvas, events, conversions coordonnées) |
| 8e | Advanced Orders | Modifie la route critique `/api/execute` — faire en dernier pour ne rien casser |
| 9e | Sons | S'intègre dans les fonctions existantes + celles des étapes 3, 5 — mieux d'avoir tout avant |
| 10e (dernier) | Responsive | Doit voir tout le contenu final pour ajuster les media queries correctement |

### 3.6 RÈGLE D'OR

> **Chaque étape doit laisser le dashboard fonctionnel.**
> Après chaque commit, le dashboard doit démarrer (`python3 server.py`),
> s'afficher sans erreur console, et toutes les features existantes doivent
> continuer à fonctionner. Si une étape casse quelque chose, la corriger
> AVANT de passer à la suivante.

---
## 4. TABLEAU DE SUIVI D'AVANCEMENT

> **Instruction** : après chaque étape terminée, mettre à jour ce tableau.
> Remplacer `[ ]` par `[x]`, ajouter le hash du commit et la date.

---

### 4.1 SUIVI GLOBAL

| Phase | Step | Étape | Statut | Commit | Date |
|-------|------|-------|--------|--------|------|
| 1 | 29 | 10.0 Dark/Light Mode | `[ ]` EN ATTENTE | — | — |
| 1 | 30 | 7.0 Sparklines | `[ ]` EN ATTENTE | — | — |
| 1 | 31 | 8.0 Heatmap | `[ ]` EN ATTENTE | — | — |
| 2 | 32 | 1.0 Multi-Timeframe Analysis | `[ ]` EN ATTENTE | — | — |
| 2 | 33 | 2.0 Portfolio Tracker | `[ ]` EN ATTENTE | — | — |
| 2 | 34 | 3.0 Alertes & Notifications | `[ ]` EN ATTENTE | — | — |
| 3 | 35 | 4.0 Drawing Tools | `[ ]` EN ATTENTE | — | — |
| 3 | 36 | 5.0 Advanced Order Types | `[ ]` EN ATTENTE | — | — |
| 3 | 37 | 6.0 Effets Sonores | `[ ]` EN ATTENTE | — | — |
| 4 | 38 | 9.0 Responsive Mobile | `[ ]` EN ATTENTE | — | — |

**Progression : 0 / 10 étapes terminées**

---

### 4.2 SUIVI DÉTAILLÉ PAR SOUS-TÂCHE

#### Étape 10.0 — Dark/Light Mode (Step 29)

| # | Sous-tâche | Fait |
|---|------------|------|
| 10.1 | CSS variables light `[data-theme="light"]` | `[ ]` |
| 10.2 | CSS transition fluide sur `*` | `[ ]` |
| 10.3 | JS constantes `CHART_THEMES` dark/light | `[ ]` |
| 10.4 | JS `getChartOptions()` dynamique | `[ ]` |
| 10.5 | JS `getSubChartOptions()` dynamique | `[ ]` |
| 10.6 | JS `applyChartTheme()` | `[ ]` |
| 10.7 | JS `toggleTheme()` + localStorage | `[ ]` |
| 10.8 | HTML bouton ☀/☾ dans navbar | `[ ]` |
| 10.9 | CSS `.btn-theme` | `[ ]` |
| 10.10 | JS init thème dans DOMContentLoaded | `[ ]` |
| 10.11 | Mise à jour `initMainChart` / `initRSI` / `initMACD` | `[ ]` |

#### Étape 7.0 — Sparklines (Step 30)

| # | Sous-tâche | Fait |
|---|------------|------|
| 7.1 | Route `GET /api/sparklines` | `[ ]` |
| 7.2 | JS `buildSparklineSVG()` | `[ ]` |
| 7.3 | JS variable globale `sparklineData` | `[ ]` |
| 7.4 | JS `loadSparklines()` | `[ ]` |
| 7.5 | Intégrer dans `loadTicker()` | `[ ]` |
| 7.6 | HTML placeholder `#asset-sparkline` | `[ ]` |
| 7.7 | Intégrer dans `loadPriceData()` | `[ ]` |
| 7.8 | CSS `.sparkline`, `.asset-sparkline` | `[ ]` |
| 7.9 | Intégrer dans auto-refresh + init | `[ ]` |

#### Étape 8.0 — Heatmap (Step 31)

| # | Sous-tâche | Fait |
|---|------------|------|
| 8.1 | Enrichir `GET /api/ticker` (volume, high, low) | `[ ]` |
| 8.2 | HTML `#heatmap-bar` | `[ ]` |
| 8.3 | CSS `.heatmap-bar`, `.hm-cell` | `[ ]` |
| 8.4 | JS `heatmapColorScale()` | `[ ]` |
| 8.5 | JS `renderHeatmap()` | `[ ]` |
| 8.6 | Intégrer dans `loadTicker()` | `[ ]` |
| 8.7 | Tooltip au survol | `[ ]` |

#### Étape 1.0 — Multi-Timeframe Analysis (Step 32)

| # | Sous-tâche | Fait |
|---|------------|------|
| 1.1 | Route `GET /api/mtf-signals` | `[ ]` |
| 1.2 | CSS `.mtf-panel`, `.mtf-grid`, `.mtf-row` | `[ ]` |
| 1.3 | HTML `#mtf-panel` | `[ ]` |
| 1.4 | JS `loadMTF()` + `toggleMTFPanel()` | `[ ]` |
| 1.5 | Intégrer dans init + auto-refresh + `changeSymbol()` | `[ ]` |

#### Étape 2.0 — Portfolio Tracker (Step 33)

| # | Sous-tâche | Fait |
|---|------------|------|
| 2.1 | Route `GET /api/portfolio` | `[ ]` |
| 2.2 | Route `GET /api/equity-curve` | `[ ]` |
| 2.3 | CSS `.portfolio-wrap`, `.portfolio-pie` | `[ ]` |
| 2.4 | HTML onglet Portfolio dans Bottom Panel | `[ ]` |
| 2.5 | JS `loadPortfolio()` | `[ ]` |
| 2.6 | JS `renderPieChart()` SVG | `[ ]` |
| 2.7 | JS `loadEquityCurve()` mini chart | `[ ]` |
| 2.8 | Intégrer dans `switchBPTab()` | `[ ]` |

#### Étape 3.0 — Alertes & Notifications (Step 34)

| # | Sous-tâche | Fait |
|---|------------|------|
| 3.1 | Table SQLite `alerts` | `[ ]` |
| 3.2 | Route `POST /api/alerts` | `[ ]` |
| 3.3 | Route `GET /api/alerts` | `[ ]` |
| 3.4 | Route `DELETE /api/alerts/<id>` | `[ ]` |
| 3.5 | Route `GET /api/alerts/check` | `[ ]` |
| 3.6 | Refactor `showToast()` empilable | `[ ]` |
| 3.7 | CSS `.toast`, `.alert-badge`, `.alert-list` | `[ ]` |
| 3.8 | HTML modal création alerte | `[ ]` |
| 3.9 | HTML badge navbar | `[ ]` |
| 3.10 | JS CRUD `createAlert()`, `deleteAlert()`, `loadAlertList()` | `[ ]` |
| 3.11 | JS `checkAlerts()` | `[ ]` |
| 3.12 | Intégrer dans auto-refresh + `changeSymbol()` | `[ ]` |

#### Étape 4.0 — Drawing Tools (Step 35)

| # | Sous-tâche | Fait |
|---|------------|------|
| 4.1 | HTML activer boutons toolbar | `[ ]` |
| 4.2 | HTML canvas overlay | `[ ]` |
| 4.3 | CSS `.draw-canvas`, toolbar active | `[ ]` |
| 4.4 | JS état global dessin | `[ ]` |
| 4.5 | JS `setDrawMode()` | `[ ]` |
| 4.6 | JS fonctions conversion coordonnées | `[ ]` |
| 4.7 | JS événements souris canvas | `[ ]` |
| 4.8 | JS fonctions rendu (6 types) | `[ ]` |
| 4.9 | JS `renderAllDrawings()` + sync chart | `[ ]` |
| 4.10 | JS persistence localStorage | `[ ]` |
| 4.11 | JS intégration init + changeSymbol/TF | `[ ]` |

#### Étape 5.0 — Advanced Order Types (Step 36)

| # | Sous-tâche | Fait |
|---|------------|------|
| 5.1 | Table SQLite `scheduled_orders` | `[ ]` |
| 5.2 | HTML tabs order type étendus (6 types) | `[ ]` |
| 5.3 | HTML champs conditionnels | `[ ]` |
| 5.4 | CSS `.of-advanced`, `.dca-preview` | `[ ]` |
| 5.5 | JS `switchOrderType()` étendue | `[ ]` |
| 5.6 | JS `updateDCAPreview()` | `[ ]` |
| 5.7 | JS `executeOrder()` étendue | `[ ]` |
| 5.8 | Backend `POST /api/execute` étendu | `[ ]` |
| 5.9 | Route `GET /api/scheduled-orders` | `[ ]` |
| 5.10 | Route `DELETE /api/scheduled-orders/<id>` | `[ ]` |
| 5.11 | Affichage dans Bottom Panel Open Orders | `[ ]` |
| 5.12 | JS `cancelScheduledOrder()` | `[ ]` |

#### Étape 6.0 — Effets Sonores (Step 37)

| # | Sous-tâche | Fait |
|---|------------|------|
| 6.1 | JS état global `soundEnabled`, `audioCtx` | `[ ]` |
| 6.2 | JS `initAudio()` | `[ ]` |
| 6.3 | JS 7 fonctions de son | `[ ]` |
| 6.4 | JS `toggleSound()` + localStorage | `[ ]` |
| 6.5 | HTML bouton mute navbar | `[ ]` |
| 6.6 | CSS `.btn-sound` | `[ ]` |
| 6.7 | Intégrer sons dans 7 fonctions existantes | `[ ]` |
| 6.8 | Init bouton son dans DOMContentLoaded | `[ ]` |

#### Étape 9.0 — Responsive Mobile (Step 38)

| # | Sous-tâche | Fait |
|---|------------|------|
| 9.1 | HTML bouton hamburger | `[ ]` |
| 9.2 | HTML overlay backdrop | `[ ]` |
| 9.3 | CSS base hamburger + overlay | `[ ]` |
| 9.4 | CSS media query tablette (≤1024px) | `[ ]` |
| 9.5 | CSS media query mobile (≤768px) | `[ ]` |
| 9.6 | CSS media query petit mobile (≤480px) | `[ ]` |
| 9.7 | JS `toggleMobilePanel()` | `[ ]` |
| 9.8 | JS fermer panel au changement symbole | `[ ]` |
| 9.9 | JS resize handler cleanup | `[ ]` |

---
## 5. CHECKLIST POST-IMPLÉMENTATION & PROTOCOLES DE TEST

---

### 5.1 CHECKLIST À EXÉCUTER APRÈS CHAQUE ÉTAPE

Avant de marquer une étape comme terminée dans le tableau de suivi (Section 4),
exécuter cette checklist dans l'ordre :

```
□  1. SYNTAXE PYTHON
     python3 -m py_compile server.py
     → Doit retourner 0 (aucune erreur)
     → Si pas de modif server.py, ignorer

□  2. SYNTAXE HTML/JS
     Ouvrir dashboard.html dans le navigateur
     → Console DevTools : 0 erreurs JS
     → Pas de texte cassé / éléments manquants

□  3. DÉMARRAGE SERVEUR
     python3 server.py
     → Le serveur démarre sur port 5000 sans traceback
     → Le log affiche "J.A.R.V.I.S. Trading System vX.X starting"

□  4. HEALTH CHECK (si serveur tourne)
     ./scripts/health-check.sh
     → Toutes les routes existantes répondent 200 ou 502 (proxy externe)
     → Les nouvelles routes de l'étape répondent 200

□  5. CODE REVIEW AUTOMATISÉE
     ./scripts/code-review.sh
     → 0 issues critiques
     → Warnings acceptables uniquement

□  6. FEATURES EXISTANTES NON CASSÉES
     → Le chart se charge et affiche des bougies
     → L'order book se remplit
     → Le ticker footer défile
     → Le formulaire d'ordre fonctionne (paper trade)
     → JARVIS chat répond (si clé API configurée)
     → Le kill switch s'active/désactive

□  7. NOUVELLE FEATURE FONCTIONNE
     → Exécuter les critères de validation de l'étape (Section 2)
     → Chaque critère V.X.Y doit passer

□  8. MISE À JOUR PLAN.MD
     → Cocher les sous-tâches dans le tableau détaillé (Section 4.2)
     → Mettre à jour la carte de navigation (Section 1) si les lignes ont bougé
     → Marquer l'étape comme FAITE dans le suivi global (Section 4.1)

□  9. COMMIT & PUSH
     → git add server.py dashboard.html PLAN.md
     → git commit -m "feat: step XX — <description>"
     → git push -u origin claude/jarvis-trading-dashboard-HGW7A

□ 10. VÉRIFIER LE PUSH
     → Le commit apparaît sur GitHub
     → Le nombre de commits a augmenté de 1
```

---

### 5.2 PROTOCOLE DE TEST PAR TYPE DE MODIFICATION

#### A. Nouvelle route API (server.py)

```
1. python3 -m py_compile server.py
2. Démarrer le serveur
3. curl -s http://localhost:5000/api/<nouvelle-route> | python3 -m json.tool
   → Vérifier : code HTTP 200, JSON valide, champs attendus présents
4. curl avec paramètres invalides
   → Vérifier : code HTTP 400, message d'erreur descriptif
5. Ajouter la route dans scripts/health-check.sh
```

#### B. Nouvelle CSS (dashboard.html)

```
1. Ouvrir dans le navigateur, pas d'erreur visuelle
2. Vérifier que les nouvelles classes utilisent var(--xxx) pas de couleurs hardcodées
3. Tester en mode light (si étape 10.0 déjà faite) : les éléments restent lisibles
4. Tester en responsive (si étape 9.0 déjà faite) : pas de débordement à 375px
5. Vérifier les transitions (0.15s ease cohérent)
```

#### C. Nouveau JavaScript (dashboard.html)

```
1. Console DevTools : 0 erreurs au chargement
2. Console DevTools : 0 erreurs à l'interaction
3. Vérifier que toutes les fonctions utilisent "function" (pas de arrow functions)
4. Vérifier que les variables sont déclarées avec var/let/const (pas de globales implicites)
5. Tester le scénario nominal (golden path)
6. Tester le scénario d'erreur (réseau coupé, données vides)
7. Vérifier que le auto-refresh ne crée pas de fuites mémoire (pas d'accumulaton de listeners)
```

#### D. Nouvelle table SQLite (server.py)

```
1. Supprimer jarvis.db (ou le renommer)
2. python3 server.py → la table est créée automatiquement par init_db()
3. sqlite3 jarvis.db ".tables" → la nouvelle table apparaît
4. sqlite3 jarvis.db ".schema <table>" → le schéma correspond au plan
5. Tester INSERT, SELECT, DELETE via les routes API
```

#### E. Modification d'une fonction existante

```
1. Relire la fonction AVANT modification (dans PLAN.md section navigation)
2. S'assurer que le comportement existant est préservé
3. Tester le scénario existant (ne doit pas casser)
4. Tester le nouveau scénario ajouté
5. Si la fonction est appelée depuis startAutoRefresh(), vérifier qu'elle
   ne provoque pas de surcharge réseau
```

---

### 5.3 TESTS DE RÉGRESSION RAPIDES

Séquence de 60 secondes à exécuter après toute modification importante :

```
TEMPS  ACTION                                 VÉRIFIER
─────  ──────────────────────────────────────  ─────────────────────────
 0s    Ouvrir http://localhost:5000            Page se charge sans flash
 3s    Regarder le chart                      Bougies affichées
 5s    Regarder l'order book                  Asks et bids remplis
 8s    Regarder le ticker footer              Défilement actif
10s    Changer de symbole (cliquer ETH)       Chart, OB, ticker se mettent à jour
15s    Changer de timeframe (cliquer 4h)      Chart recharge
20s    Ouvrir JARVIS chat (cliquer AI)        Chat s'ouvre, pas d'erreur
25s    Cliquer un onglet Bottom Panel          Contenu change
30s    Ouvrir Settings (cliquer Settings)     Modal s'ouvre
35s    Fermer Settings (Escape)               Modal se ferme
40s    Ouvrir console DevTools                0 erreurs rouges
50s    Attendre 10 secondes                   Auto-refresh fonctionne (OB bouge)
60s    ✓ Régression OK
```

---

### 5.4 COMMANDES DE DIAGNOSTIC RAPIDE

```bash
# Vérifier syntaxe Python
python3 -m py_compile server.py && echo "OK" || echo "ERREUR"

# Compter les lignes (pour vérifier les insertions)
wc -l server.py dashboard.html

# Vérifier les routes déclarées
grep -c "@app.route" server.py

# Vérifier les fonctions JS
grep -c "^function \|^async function " dashboard.html

# Chercher les arrow functions (interdit)
grep -n "=>" dashboard.html | grep -v "<!--" | head -5

# Chercher les couleurs hardcodées (devrait utiliser var(--xxx))
grep -n "#[0-9a-fA-F]\{6\}" dashboard.html | grep -v ":root" | grep -v "data-theme" | grep -v "CHART_THEMES" | head -10

# Vérifier que les fichiers sensibles ne sont pas commités
git status --short | grep -E "\.env|secret\.key|jarvis\.db"

# Taille totale du projet
wc -l server.py dashboard.html PLAN.md
```

---

### 5.5 GESTION DES ERREURS COURANTES

| Erreur | Cause probable | Solution |
|--------|----------------|----------|
| `SyntaxError` dans server.py | Parenthèse manquante, indentation | `python3 -m py_compile server.py` pour localiser |
| Écran blanc dashboard | Erreur JS bloquante | Console DevTools → première erreur rouge |
| `TypeError: $(...) is null` | ID d'élément mal orthographié | Vérifier l'ID dans le HTML |
| Chart ne s'affiche pas | `lw-charts.js` non chargé | Vérifier que `<script src="lw-charts.js">` est avant le JS principal |
| Route retourne 404 | Route mal déclarée ou serveur pas redémarré | Redémarrer `python3 server.py` |
| CORS error dans console | Appel cross-origin | Vérifier que CORS est activé (déjà fait dans server.py) |
| SQLite "table locked" | Connexion non fermée | Vérifier `conn.close()` dans chaque route |
| Toast ne s'affiche pas | `showToast` appelé avant que le DOM soit prêt | Vérifier que l'appel est dans un handler, pas au top-level |
| Mémoire qui monte | setInterval sans cleanup | Vérifier que les timers sont dans `refreshTimers[]` |

---
## 6. NOTES DE REPRISE INTER-SESSION & STRATÉGIE DE RECOVERY

> **Ce fichier est la première chose à lire en début de session.**
> Si le contexte conversationnel a été perdu (nouvelle session, compression,
> timeout), cette section contient tout ce qu'il faut pour reprendre.

---

### 6.1 PROCÉDURE DE REPRISE (EXÉCUTER À CHAQUE DÉBUT DE SESSION)

```
ÉTAPE 1 — Identifier où on en est
    Lire PLAN.md section 4.1 (tableau de suivi global)
    → Trouver la dernière étape marquée [x] FAIT
    → L'étape suivante est celle à faire

ÉTAPE 2 — Vérifier l'état du code
    git status
    → S'il y a des modifications non commitées, les analyser avant de continuer
    git log --oneline -5
    → Vérifier le dernier commit (quel step ?)

ÉTAPE 3 — Lire l'étape à faire
    Lire PLAN.md section de l'étape concernée (chercher "### ÉTAPE X.0")
    → Lire l'objectif, les fichiers touchés, les sous-tâches

ÉTAPE 4 — Vérifier la carte de navigation
    Lire PLAN.md section 1 (carte de navigation)
    → Les numéros de ligne ont pu changer après les étapes précédentes
    → Utiliser les ANCRES TEXTUELLES plutôt que les numéros de ligne

ÉTAPE 5 — Commencer
    Marquer l'étape EN COURS dans le tableau de suivi
    Coder la première sous-tâche
```

---

### 6.2 ANCRES TEXTUELLES DE RÉFÉRENCE

Les numéros de ligne bougent à chaque étape. Ces chaînes de texte, elles,
ne bougent JAMAIS. Les utiliser pour se repérer avec `grep -n` :

```bash
# Points d'insertion CSS
grep -n "</style>" dashboard.html              # → fin du CSS

# Points d'insertion HTML
grep -n "<!-- MAIN LAYOUT -->" dashboard.html  # → début du layout
grep -n "<!-- /main-layout -->" dashboard.html # → fin du layout (après chart+panels)
grep -n "<!-- FOOTER -->" dashboard.html       # → début du footer
grep -n "<!-- Lightweight Charts -->" dashboard.html # → fin du HTML body

# Points d'insertion JS
grep -n "GLOBAL STATE" dashboard.html          # → variables globales
grep -n "INIT ON DOM READY" dashboard.html     # → fin du JS (avant init)
grep -n "AUTO-REFRESH" dashboard.html          # → bloc des timers

# Points d'insertion server.py
grep -n '@app.route("/")' server.py            # → dernière route avant main
grep -n 'if __name__' server.py                # → entry point
grep -n 'def init_db' server.py                # → création des tables
```

---

### 6.3 COMMANDE DE DIAGNOSTIC RAPIDE POUR REPRENDRE

Copier-coller cette commande en début de session pour un état complet :

```bash
echo "=== GIT ===" && \
git branch --show-current && \
git log --oneline -3 && \
git status --short && \
echo "=== FICHIERS ===" && \
wc -l server.py dashboard.html PLAN.md 2>/dev/null && \
echo "=== ROUTES ===" && \
grep -c "@app.route" server.py && \
echo "=== FONCTIONS JS ===" && \
grep -c "^function \|^async function " dashboard.html && \
echo "=== SYNTAXE ===" && \
python3 -m py_compile server.py 2>&1 && echo "server.py OK" || echo "server.py ERREUR"
```

---

### 6.4 TABLE DE CORRESPONDANCE RAPIDE

Pour retrouver instantanément quelle étape correspond à quoi :

```
QUOI CHERCHER                    → OÙ DANS PLAN.MD
─────────────────────────────────────────────────────
Où en est-on ?                   → Section 4.1 (suivi global)
Quoi faire maintenant ?          → Section 3.4 (ordre d'exécution)
Détail d'une étape ?             → Chercher "### ÉTAPE X.0"
Où insérer du CSS ?              → Section 1.2 + ancre "</style>"
Où insérer du HTML ?             → Section 1.3 + ancre "<!-- Lightweight Charts -->"
Où insérer du JS ?               → Section 1.4 + ancre "INIT ON DOM READY"
Où insérer une route ?           → Section 1.6 + ancre '@app.route("/")'
Comment tester ?                 → Section 5 (checklist + protocoles)
Quelles dépendances ?            → Section 3.1 (matrice)
```

---

### 6.5 STRATÉGIE DE RECOVERY EN CAS DE PROBLÈME

#### Cas 1 : Le dashboard ne se charge plus (écran blanc)

```
1. Ouvrir la console DevTools (F12)
2. Lire la première erreur rouge
3. Cas fréquent : erreur de syntaxe JS → chercher la ligne indiquée
4. Si le problème est dans les dernières modifications :
   git diff HEAD~1 dashboard.html | head -50
   → Voir ce qui a changé
5. En dernier recours :
   git stash
   → Revenir à l'état propre, ouvrir le dashboard, vérifier que ça marche
   git stash pop
   → Réappliquer les changements et corriger
```

#### Cas 2 : Le serveur ne démarre pas (traceback Python)

```
1. Lire le traceback — la dernière ligne donne le fichier et la ligne
2. python3 -m py_compile server.py
   → Donne la ligne exacte de l'erreur de syntaxe
3. Si c'est une ImportError : vérifier requirements.txt et pip install
4. Si c'est une erreur SQLite : supprimer jarvis.db et relancer
   (init_db() recrée les tables automatiquement)
```

#### Cas 3 : Une étape a cassé une feature existante

```
1. Identifier la feature cassée
2. git log --oneline -5 → quel step a été fait en dernier ?
3. git diff HEAD~1 → voir les changements
4. Chercher dans le diff les modifications de fonctions existantes
5. La cause est presque toujours :
   - Variable renommée ou supprimée
   - Fonction modifiée avec un bug
   - ID d'élément HTML changé
6. Corriger le bug DANS L'ÉTAPE EN COURS (pas de nouveau commit)
7. Re-tester la régression (Section 5.3)
```

#### Cas 4 : Le PLAN.md a des numéros de ligne obsolètes

```
1. Les numéros de ligne bougent après chaque insertion
2. Ne JAMAIS se fier uniquement aux numéros — utiliser les ancres (Section 6.2)
3. Pour recalculer : grep -n "<ancre>" dashboard.html
4. Mettre à jour la section 1 (carte de navigation) avec les nouvelles valeurs
5. Commiter la mise à jour du PLAN.md avec l'étape
```

#### Cas 5 : Confusion sur quelle étape faire

```
1. Lire Section 4.1 → dernière étape [x]
2. Lire Section 3.4 → ordre d'exécution optimal
3. L'étape suivante est la prochaine non-cochée dans l'ordre de la Section 3.4
4. En cas de doute, demander à l'utilisateur :
   "La dernière étape terminée est X.0. Je fais Y.0 maintenant ?"
```

---

### 6.6 FICHIERS À NE JAMAIS PERDRE

| Fichier | Criticité | Recovery si perdu |
|---------|-----------|-------------------|
| `PLAN.md` | HAUTE | Récupérer depuis GitHub (pushé à chaque étape) |
| `server.py` | CRITIQUE | Récupérer depuis GitHub |
| `dashboard.html` | CRITIQUE | Récupérer depuis GitHub |
| `lw-charts.js` | HAUTE | Re-télécharger TradingView Lightweight Charts v4.2.1 |
| `jarvis.db` | BASSE | `init_db()` recrée les tables (données perdues OK en dev) |
| `secret.key` | MOYENNE | Régénéré automatiquement au premier lancement |

---

### 6.7 RÉSUMÉ EN UNE PHRASE PAR ÉTAPE

Pour se rappeler rapidement de quoi parle chaque étape :

```
 1.0  MTF        Panneau montrant RSI/MACD/régime sur 4 timeframes simultanés
 2.0  Portfolio   PnL cumulé + pie chart SVG + equity curve TradingView
 3.0  Alertes     CRUD alertes prix/indicateurs + toasts empilables + badge navbar
 4.0  Drawing     Canvas overlay sur le chart pour dessiner lignes/fib/rectangles
 5.0  Orders      OCO, Trailing, Iceberg, DCA dans le formulaire d'ordre
 6.0  Sons        7 sons synthétiques Web Audio API + toggle mute localStorage
 7.0  Sparklines  Mini SVG polyline 50×16px dans le ticker footer et asset bar
 8.0  Heatmap     Bande de cellules colorées vert/rouge entre asset bar et chart
 9.0  Responsive  Media queries 1024/768/480px + right panel slide-over + hamburger
10.0  Dark/Light  Variables CSS light + sync charts TradingView + localStorage toggle
```

---
## 7. MISE À JOUR CLAUDE.MD & RÈGLES DE MAINTENANCE

---

### 7.1 CONTENU À AJOUTER DANS CLAUDE.MD

Ajouter la section suivante dans `CLAUDE.md` entre "## Testing" et "## Common Tasks" :

```markdown
## Roadmap & Navigation

- **`PLAN.md`** — Roadmap complète des 10 étapes d'amélioration avec :
  - Carte de navigation (numéros de ligne exacts de server.py et dashboard.html)
  - 10 étapes détaillées avec sous-tâches numérotées et critères de validation
  - Matrice de dépendances et ordre d'exécution optimal
  - Tableau de suivi d'avancement (cocher après chaque étape)
  - Checklist post-implémentation et protocoles de test
  - Notes de reprise inter-session
- **Toujours lire PLAN.md avant de commencer une étape**
- **Toujours mettre à jour PLAN.md après chaque étape**
```

Ajouter dans la section "## Common Tasks" :

```markdown
### Starting a new enhancement step
1. Read PLAN.md — find the next unchecked step in Section 4.1
2. Read the step's detail section (search "### ÉTAPE X.0")
3. Use text anchors (Section 6.2) to find insertion points — don't trust line numbers blindly
4. Follow the sub-tasks in order
5. Run the post-implementation checklist (Section 5.1)
6. Update PLAN.md: check sub-tasks, update navigation map, mark step as done
7. Commit with message: `feat: step XX — <description>`
```

Ajouter dans la section "## Do Not" :

```markdown
- Do not start coding an enhancement step without reading PLAN.md first
- Do not skip the post-implementation checklist after completing a step
- Do not trust PLAN.md line numbers after multiple steps — use text anchors
```

---

### 7.2 RÈGLES DE MISE À JOUR DE LA CARTE DE NAVIGATION

Après chaque étape, la carte de navigation (Section 1) doit être mise à jour
car les insertions de code décalent les numéros de ligne.

#### Procédure

```
1. Compter les lignes ajoutées dans chaque zone :
   - Lignes CSS ajoutées avant </style>
   - Lignes HTML ajoutées dans le body
   - Lignes JS ajoutées avant INIT ON DOM READY
   - Lignes ajoutées dans server.py

2. Recalculer les points d'insertion critiques :
   grep -n "</style>" dashboard.html
   grep -n "INIT ON DOM READY" dashboard.html
   grep -n '@app.route("/")' server.py

3. Mettre à jour Section 1.1 (ancres principales) avec les nouvelles valeurs

4. Mettre à jour les sections 1.2 → 1.7 :
   - Seules les zones APRÈS l'insertion bougent
   - Les zones AVANT l'insertion restent identiques
   - Décalage = nombre de lignes insérées
```

#### Exemple de mise à jour après l'étape 10.0 (Dark/Light Mode)

Supposons qu'on ajoute :
- 22 lignes CSS (variables light `[data-theme="light"]`)
- 1 ligne CSS (transition sur `*`)
- 2 lignes HTML (bouton dans navbar)
- 20 lignes JS (thème state + CHART_THEMES)
- 30 lignes JS (fonctions toggle/apply)

Alors :
```
dashboard.html AVANT : 3176 lignes
dashboard.html APRÈS : 3176 + 22 + 1 + 2 + 20 + 30 = 3251 lignes

Ancres mises à jour :
  </style>          : L:1175 → L:1198 (+23 lignes CSS)
  <!-- MAIN LAYOUT -->: L:1246 → L:1271 (+23 CSS + 2 HTML)
  INIT ON DOM READY : L:3142 → L:3189 (+23 CSS + 2 HTML + 20 JS avant init + 2 shift HTML)
```

#### Raccourci : utiliser les ancres textuelles

Au lieu de recalculer manuellement, toujours utiliser :

```bash
grep -n "</style>" dashboard.html
grep -n "INIT ON DOM READY" dashboard.html
grep -n "AUTO-REFRESH" dashboard.html
grep -n '@app.route("/")' server.py
```

Puis mettre à jour les valeurs dans la Section 1.1 du PLAN.md.

---

### 7.3 QUAND METTRE À JOUR QUOI

| Événement | PLAN.md à modifier | CLAUDE.md |
|-----------|--------------------|-----------| 
| Étape terminée | Section 4.1 (suivi), Section 4.2 (sous-tâches), Section 1.1 (ancres) | Non |
| Nouvelle route API ajoutée | Section 1.6 (routes) | Non |
| Nouvelle fonction JS ajoutée | Section 1.4 (JS) | Non |
| Nouvelle classe Python ajoutée | Section 1.5 (structure) | Ajouter dans "Important Classes" |
| Nouvelle table SQLite | Section 1.5 | Non |
| Nouveau script shell | Non | Ajouter dans "Testing" |
| Toutes les 10 étapes terminées | Archiver, créer PLAN_v2.md | Mettre à jour les compteurs de lignes |

---

### 7.4 FORMAT DU COMMIT DE MISE À JOUR PLAN.MD

La mise à jour du PLAN.md se fait dans LE MÊME commit que l'étape :

```
git add server.py dashboard.html PLAN.md
git commit -m "feat: step XX — <description>"
```

Ne PAS faire un commit séparé pour la mise à jour du PLAN.md.
Le PLAN.md est un outil vivant, pas un livrable — il évolue avec le code.

---

## 8. PLAN SÉCURITÉ — 10 ÉTAPES

> **Date de l'audit** : 2026-04-21
> **Fichiers audités** : `server.py` (~5200 lignes), `dashboard.html` (~7260 lignes)
> **Objectif** : sécuriser le stockage des clés API Anthropic, du portefeuille GMX,
> et corriger toutes les vulnérabilités identifiées pour un déploiement production.

---

### 8.1 RÉSUMÉ DE L'AUDIT DE SÉCURITÉ

#### Statistiques

| Sévérité | Nombre | % |
|----------|--------|---|
| CRITIQUE | 8 | 27% |
| HAUTE | 9 | 31% |
| MOYENNE | 8 | 27% |
| BASSE | 4 | 14% |
| **TOTAL** | **29** | 100% |

---

### 8.2 VULNÉRABILITÉS DÉTAILLÉES — CLASSÉES PAR SÉVÉRITÉ

#### 🔴 CRITIQUE (8 vulnérabilités)

| # | ID | Fichier | Ligne(s) | Vulnérabilité | Description |
|---|-----|---------|----------|---------------|-------------|
| 1 | C-01 | server.py | 384 | **Aucune authentification** | Zéro auth — toutes les 50+ routes API sont publiquement accessibles. N'importe qui connaissant l'IP:port peut exécuter des trades, ajouter/supprimer des exchanges, lire les clés. |
| 2 | C-02 | server.py | 384 | **CORS non restreint** | `CORS(app)` sans paramètre = n'importe quel site web peut appeler toutes les routes API. Un attaquant peut créer une page qui exécute des ordres depuis le navigateur de la victime. |
| 3 | C-03 | server.py | 568, 575 | **Fallback base64 si Fernet absent** | `encrypt_string()` et `decrypt_string()` tombent en base64 (aucun chiffrement) si `cryptography` n'est pas installé. Les clés API sont alors stockées en clair décodable. |
| 4 | C-04 | server.py | 2275-2278 | **Private key GMX en mémoire indéfiniment** | `self._account = Web3Account.from_key(private_key)` — la clé privée reste en RAM tant que l'adaptateur existe. Aucun nettoyage, aucun timeout. Un dump mémoire = fonds volés. |
| 5 | C-05 | server.py | 2278 | **Private key loggée dans les exceptions** | `log.error("GMXAdapter: invalid private key: %s", e)` — l'exception peut contenir des fragments de la clé privée dans le message d'erreur. |
| 6 | C-06 | dashboard.html | 5126 | **Hack __set_key__ non fonctionnel** | `saveSettings()` envoie la clé Anthropic via `{message: '__set_key__:' + key}` à `/api/jarvis` — le serveur n'a pas de handler, la clé est envoyée comme message à Claude API. La clé Anthropic est transmise à un service tiers. |
| 7 | C-07 | dashboard.html | 6457-6468 | **XSS via innerHTML (GMX Entry Plan)** | `container.innerHTML = '...' + signals + '...'` — les signaux du serveur sont injectés sans échappement. Un serveur compromis ou MITM peut exécuter du JS arbitraire. |
| 8 | C-08 | dashboard.html | Absent | **Aucun Content-Security-Policy** | Pas de CSP dans le `<head>` — aucune protection contre l'injection de scripts externes, inline scripts malveillants, ou chargement de ressources tierces. |

#### 🟠 HAUTE (9 vulnérabilités)

| # | ID | Fichier | Ligne(s) | Vulnérabilité | Description |
|---|-----|---------|----------|---------------|-------------|
| 9 | H-01 | server.py | 4158, 4227, 4264, 4294, 4408, 4721, 4746, 4785, 4797, 4809, 4888, 4969, 5005, 5162 | **14× `str(e)` exposé au client** | 14 endpoints retournent `jsonify({"error": str(e)})` — les stack traces Python complètes sont envoyées au frontend. Fuite de chemins internes, versions de bibliothèques, structure du code. |
| 10 | H-02 | server.py | 572-576 | **Aucun try/except dans decrypt_string()** | Si la clé Fernet est corrompue ou les données altérées, `decrypt_string()` crash le serveur avec une exception non gérée. Aucun fallback gracieux. |
| 11 | H-03 | server.py | Absent | **Aucun rate limiting** | Zéro protection contre le brute force, le spam d'ordres, ou le DDoS. Un attaquant peut envoyer 10000 requêtes/seconde sur `/api/execute`. |
| 12 | H-04 | server.py | Absent | **Aucun header de sécurité HTTP** | Pas de `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, `Referrer-Policy`, `Permissions-Policy`. Le dashboard peut être intégré dans une iframe malveillante (clickjacking). |
| 13 | H-05 | dashboard.html | 4183, 4202 | **XSS via innerHTML (Order Book)** | `asksEl.innerHTML = asksHtml` et `bidsEl.innerHTML = bidsHtml` — les prix/quantités du carnet d'ordres injectés sans échappement HTML. |
| 14 | H-06 | dashboard.html | 4258 | **XSS via innerHTML (Recent Trades)** | `el.innerHTML = html` — les trades récents (prix, quantité, heure) injectés sans échappement. |
| 15 | H-07 | dashboard.html | 4295 | **XSS via innerHTML (Ticker Footer)** | `tickerEl.innerHTML = html` — les symboles et prix du ticker injectés sans échappement. `t.symbol` peut contenir du HTML malveillant. |
| 16 | H-08 | dashboard.html | 5157 | **XSS via innerHTML (Exchange List)** | `el.innerHTML = html` — `ex.name` et `ex.status` injectés sans échappement + injection onclick via `ex.id`. |
| 17 | H-09 | dashboard.html | 5175, 4919, 5195 | **Aucun token CSRF** | Toutes les requêtes POST/DELETE (execute, exchanges/add, exchanges/remove, killswitch, close, alerts) sont envoyées sans token CSRF. Attaque cross-site possible. |

#### 🟡 MOYENNE (8 vulnérabilités)

| # | ID | Fichier | Ligne(s) | Vulnérabilité | Description |
|---|-----|---------|----------|---------------|-------------|
| 18 | M-01 | server.py | 67 | **Clé Anthropic uniquement via env var** | `ANTHROPIC_API_KEY = os.environ.get(...)` — aucune route pour la sauvegarder/modifier depuis le dashboard. Le hack `__set_key__` (C-06) ne fonctionne pas. L'utilisateur ne peut pas configurer JARVIS AI depuis l'interface. |
| 19 | M-02 | server.py | 554-559 | **Aucune rotation de clé Fernet** | La clé `secret.key` est générée une fois, jamais renouvelée. Si compromise, toutes les données chiffrées sont exposées à vie. Aucun mécanisme de re-chiffrement. |
| 20 | M-03 | server.py | 3830-3860 | **Aucune validation profonde sur /api/execute** | Le symbole n'est pas validé (regex), la quantité n'a pas de maximum, le levier n'est pas borné côté serveur. Un appel crafté peut passer n'importe quelle valeur. |
| 21 | M-04 | server.py | Absent | **Aucun audit trail** | Aucun log structuré des opérations sensibles (ajout/suppression d'exchange, trades exécutés, tentatives d'accès). Impossible de retracer une intrusion. |
| 22 | M-05 | dashboard.html | 4547, 5154, 6334 | **Injection onclick avec données serveur** | `onclick="closePosition('" + p.id + "')"` — si `p.id` contient `'); alert('XSS'); //`, le JS est exécuté. Même risque pour `ex.id` et `p.symbol`. |
| 23 | M-06 | dashboard.html | 3060, 3110 | **Champs secrets sans autocomplete="off"** | Les champs pour la clé Anthropic et le secret exchange n'ont pas `autocomplete="off"`. Le navigateur peut sauvegarder et auto-remplir les secrets. |
| 24 | M-07 | dashboard.html | 5167 | **Variables clés non nettoyées après envoi** | `const apiKey = $('ex-key').value` — la variable reste en mémoire JS après `addExchange()`. Pas de `= ''` après envoi. Accessible via DevTools. |
| 25 | M-08 | dashboard.html | 6527 | **XSS via err.message dans innerHTML** | `'Scan error: ' + err.message` injecté dans innerHTML. Un message d'erreur crafté peut exécuter du JS. |

#### 🟢 BASSE (4 vulnérabilités)

| # | ID | Fichier | Ligne(s) | Vulnérabilité | Description |
|---|-----|---------|----------|---------------|-------------|
| 26 | B-01 | server.py | 383 | **Flask en mode debug potentiel** | `Flask(__name__)` sans `debug=False` explicite. Si lancé avec `FLASK_DEBUG=1`, le debugger interactif est accessible (exécution de code arbitraire). |
| 27 | B-02 | server.py | Absent | **Pas de vérification permissions secret.key au runtime** | Les permissions `0o600` sont fixées à la création mais jamais revérifiées. Un `chmod` accidentel n'est pas détecté. |
| 28 | B-03 | dashboard.html | 3106 | **Champ API key en type="text"** | `<input type="text" id="ex-key">` — la clé API exchange est visible en clair à l'écran. Devrait être `type="password"`. |
| 29 | B-04 | dashboard.html | 6772 | **localStorage non chiffré** | La watchlist et les préférences sont en localStorage brut. Si un XSS est exploité, toutes ces données sont volées. Risque mineur car pas de secrets stockés actuellement. |

---

### 8.3 SQUELETTE DES 10 ÉTAPES DE SÉCURITÉ

> **Convention** : Les étapes sécurité utilisent le préfixe `S` (S1.0 à S10.0).
> Chaque étape sera détaillée avec ses sous-tâches au moment de l'implémentation.
> Les colonnes "Corrige" réfèrent aux IDs de vulnérabilités ci-dessus.

| Step | ID | Titre | Objectif | Corrige |
|------|----|-------|----------|---------|
| 39 | S1.0 | **Authentification PIN & Sessions** | Protéger toutes les routes sensibles par un PIN hashé PBKDF2 + tokens de session avec expiration + écran de verrouillage glassmorphism + auto-lock 15 min. | C-01, H-09 |
| 40 | S2.0 | **Stockage sécurisé clé Anthropic** | Créer des routes dédiées pour sauvegarder/lire/supprimer la clé Anthropic chiffrée en DB, corriger le hack `__set_key__`, modifier JARVIS pour lire depuis la DB si env vide. | C-06, M-01 |
| 41 | S3.0 | **Coffre-fort GMX Wallet** | Stocker la clé privée GMX avec double chiffrement (Fernet + PBKDF2 dérivé du PIN), nettoyage mémoire après usage, affichage adresse publique uniquement, modal sécurisé. | C-04, C-05 |
| 42 | S4.0 | **CORS & Headers HTTP** | Restreindre CORS aux origines autorisées, ajouter CSP/X-Frame-Options/HSTS/nosniff/Referrer-Policy/Permissions-Policy, supprimer le header Server Flask. | C-02, C-08, H-04 |
| 43 | S5.0 | **Rate Limiting & Anti-brute force** | Implémenter un rate limiter pure Python par IP avec limites par catégorie (auth 5/min, execute 30/min, data 120/min), blocage IP après 5 échecs auth, réponse 429. | H-03 |
| 44 | S6.0 | **Blindage du chiffrement** | Supprimer le fallback base64, ajouter try/except à decrypt_string(), vérifier l'intégrité Fernet au démarrage, vérifier permissions secret.key, route /api/security/status. | C-03, H-02, B-02 |
| 45 | S7.0 | **Validation des entrées & assainissement erreurs** | Fonctions validate_symbol/quantity/price, remplacer les 14× `str(e)` par des messages génériques, appliquer la validation à toutes les routes sensibles. | H-01, M-03 |
| 46 | S8.0 | **Sécurité Frontend (XSS & DOM)** | Fonction `escapeHtml()`, corriger tous les innerHTML dangereux (order book, trades, ticker, exchange list, GMX), sécuriser les onclick dynamiques, autocomplete="off", nettoyage variables. | H-05, H-06, H-07, H-08, M-05, M-06, M-07, M-08, B-03 |
| 47 | S9.0 | **Audit Trail & Logging sécurisé** | Table audit_log, tracer auth/trades/clés/settings, masquer les secrets dans les logs, route GET /api/audit-log, onglet Security Log dans le dashboard. | M-04, C-05 |
| 48 | S10.0 | **Rotation des clés, backup & test final** | Rotation Fernet avec re-chiffrement, backup DB chiffré, wipe d'urgence, test de pénétration complet de toutes les routes, matrice de couverture finale. | M-02, B-01, B-04 |

---

### 8.4 MATRICE DE DÉPENDANCES

```
S1.0 (Auth)          ← aucune dépendance (PREMIÈRE ÉTAPE OBLIGATOIRE)
  │
  ├── S2.0 (Clé Anthropic)   ← nécessite S1.0 (routes protégées par auth)
  ├── S3.0 (Wallet GMX)      ← nécessite S1.0 (PIN pour dérivation PBKDF2)
  ├── S5.0 (Rate Limiting)   ← nécessite S1.0 (protection brute force sur /auth/login)
  │
  S4.0 (CORS & Headers)      ← indépendant, peut être fait en parallèle avec S1.0
  S6.0 (Chiffrement)         ← indépendant, peut être fait en parallèle
  S7.0 (Validation)          ← indépendant, peut être fait en parallèle
  S8.0 (Frontend XSS)        ← indépendant, peut être fait en parallèle
  │
  S9.0 (Audit Trail)         ← nécessite S1.0 (log des events auth)
  S10.0 (Test final)         ← nécessite S1-S9 terminées (DERNIÈRE ÉTAPE)
```

**Ordre d'exécution recommandé** : S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8 → S9 → S10

---

### 8.5 TABLEAU DE SUIVI SÉCURITÉ

| Step | ID | Étape | Statut | Commit | Date |
|------|----|-------|--------|--------|------|
| 39 | S1.0 | Authentification PIN & Sessions | `[ ]` EN ATTENTE | — | — |
| 40 | S2.0 | Stockage sécurisé clé Anthropic | `[ ]` EN ATTENTE | — | — |
| 41 | S3.0 | Coffre-fort GMX Wallet | `[ ]` EN ATTENTE | — | — |
| 42 | S4.0 | CORS & Headers HTTP | `[ ]` EN ATTENTE | — | — |
| 43 | S5.0 | Rate Limiting & Anti-brute force | `[ ]` EN ATTENTE | — | — |
| 44 | S6.0 | Blindage du chiffrement | `[ ]` EN ATTENTE | — | — |
| 45 | S7.0 | Validation entrées & erreurs | `[ ]` EN ATTENTE | — | — |
| 46 | S8.0 | Sécurité Frontend (XSS & DOM) | `[ ]` EN ATTENTE | — | — |
| 47 | S9.0 | Audit Trail & Logging sécurisé | `[ ]` EN ATTENTE | — | — |
| 48 | S10.0 | Rotation, backup & test final | `[ ]` EN ATTENTE | — | — |

**Progression sécurité : 0 / 10 étapes terminées**

---

### 8.6 SUIVI DÉTAILLÉ PAR SOUS-TÂCHE (sera rempli étape par étape)

> Chaque étape sera détaillée ici au moment de son implémentation,
> avec les sous-tâches S1.1, S1.2, ... exactes et les lignes d'insertion.

---
