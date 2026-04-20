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
