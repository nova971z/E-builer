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
