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
