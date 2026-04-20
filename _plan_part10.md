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
