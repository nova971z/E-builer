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
