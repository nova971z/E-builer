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
