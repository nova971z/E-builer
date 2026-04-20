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
