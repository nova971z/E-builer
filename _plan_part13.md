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
