# Changelog

## [1.1.4] - 2026-04-14

### Fixed

- Missing `state_class` on `prix_actuel` sensor, causing Home Assistant to lose long-term statistics tracking.
- Removed incorrect `device_class=MONETARY` (incompatible with `EUR/kWh` unit).

---

## [1.1.0] - 2026-02-26

### Descriptions & email de support (2026-03-02)

#### Descriptions ajoutées/améliorées dans toutes les étapes

- **Step `user` (token)** : ajout de "Don't have an API token? Contact support.home-assistant@selectra.info" dans la description (28 langues)
- **Step `qualification`** : ajout d'une description courte et neutre — "Renseignez les informations de votre contrat d'électricité." (28 langues)
- **Step `select_periods`** : description enrichie pour mentionner le capteur — "Cochez les périodes pendant lesquelles vos appareils doivent fonctionner. Le capteur 'Marche planifiée' sera actif pendant ces périodes." (28 langues)

#### Correction de l'email de support

Remplacement de `ha-support@selectra.info` par `support.home-assistant@selectra.info` dans tous les fichiers de traduction (step `user` description + erreur `invalid_auth`).

#### Suppression de `README_EN.md`

Fichier supprimé du repo et ajouté au `.gitignore`.

---

### Traductions & UX du config flow

#### 1. `custom_components/selectra/translations/fr.json` — Modifié

**Pourquoi :** Remplir les labels des champs dynamiques de qualification pour que l'UI affiche des noms lisibles au lieu des noms techniques bruts. Améliorer le wording "Token API" → "Clé API" pour être plus naturel en français.

| Section | Avant | Après | Raison |
|---|---|---|---|
| `config.step.user.title` | `"Token API Selectra"` | `"Clé API Selectra"` | "Clé API" est plus idiomatique en français |
| `config.step.user.description` | `"Entrez votre token API Selectra pour commencer."` | `"Entrez votre clé API Selectra pour commencer."` | Cohérence avec le changement de titre |
| `config.step.user.data.token` | `"Token API"` | `"Clé API"` | Cohérence |
| `config.step.qualification.data` | `{}` | `{"country_code": "Pays", "postcode": "Code postal", "provider_id": "Fournisseur d'électricité", "offer_id": "Offre", "option_id": "Option tarifaire", "off_peak_hours_id": "Plage heures creuses", "power_id": "Puissance souscrite"}` | Labels user-friendly pour les champs dynamiques |
| `config.error.invalid_auth` | `"Token API invalide. Envoyez un email à api@selectra.info pour obtenir le vôtre."` | `"Clé API invalide. Envoyez un email à api@selectra.info pour obtenir la vôtre."` | Cohérence + accord féminin ("la vôtre" pour "clé") |

---

#### 2. `custom_components/selectra/translations/en.json` — Modifié

**Pourquoi :** Ajouter les labels de qualification en anglais pour les utilisateurs anglophones. Pas de changement de wording nécessaire ("API Token" est correct en anglais).

| Section | Avant | Après | Raison |
|---|---|---|---|
| `config.step.qualification.data` | `{}` | `{"country_code": "Country", "postcode": "Postal code", "provider_id": "Electricity provider", "offer_id": "Offer", "option_id": "Pricing option", "off_peak_hours_id": "Off-peak hours", "power_id": "Subscribed power"}` | Labels user-friendly pour les champs dynamiques |

---

#### 3. `custom_components/selectra/translations/es.json` — Créé

**Pourquoi :** Ajouter le support de l'espagnol, pertinent puisque l'intégration gère des offres espagnoles (Endesa, PVPC). Même structure que `en.json` et `fr.json`.

Contenu complet :
- `config.step.user` → "Token de API Selectra" / "Introduce tu token de API Selectra para empezar."
- `config.step.qualification.data` → `country_code`: "País", `postcode`: "Código postal", `provider_id`: "Proveedor de electricidad", `offer_id`: "Oferta", `option_id`: "Opción tarifaria", `off_peak_hours_id`: "Franja de horas valle", `power_id`: "Potencia contratada"
- `config.step.select_periods` → "Seleccionar periodos activos"
- `config.step.strategy` → "Estrategia de optimización"
- `config.step.strategy_value` → "Configuración de la estrategia"
- `config.error.*` → Messages d'erreur traduits en espagnol
- `config.abort.*` → Messages d'abandon traduits en espagnol
- `selector.strategy.options` → "X% más baratos del día" / "X horas consecutivas más baratas"
- `entity.binary_sensor.planned_run` → "Funcionamiento planificado"
- `entity.sensor.*` → "Precio actual", "Proveedor", "Oferta", "Opción"

---

#### 4. `custom_components/selectra/strings.json` — Modifié

**Pourquoi :** `strings.json` est le fichier de référence (fallback anglais) utilisé par HA pour générer les traductions par défaut. Il doit rester cohérent avec `en.json`.

| Section | Avant | Après | Raison |
|---|---|---|---|
| `config.step.qualification.data` | `{}` | `{"country_code": "Country", "postcode": "Postal code", "provider_id": "Electricity provider", "offer_id": "Offer", "option_id": "Pricing option", "off_peak_hours_id": "Off-peak hours", "power_id": "Subscribed power"}` | Cohérence avec `en.json` |

---

### Icône de l'intégration

#### 5. `custom_components/selectra/logo.png` — Créé

**Pourquoi :** Certaines vues de l'UI HA (page des intégrations, panneau de configuration) utilisent `logo.png` au lieu de `icon.png`. L'absence de ce fichier cause le "icon not available".

| Action | Détail |
|---|---|
| Source | `icon.png` (39 KB, déjà existant) |
| Destination | `logo.png` (copie identique) |

---

### Correctifs post-livraison

#### 6. `custom_components/selectra/config_flow.py` — Modifié (ligne 217)

**Pourquoi :** Quand l'API ne renvoie pas de `label` pour une question (ou renvoie le nom brut du champ comme label), le `question_label` affiché dans la description du step qualification montrait des noms techniques comme "country_code", "provider_id", etc. au lieu d'un texte user-friendly.

| Section | Avant | Après | Raison |
|---|---|---|---|
| `async_step_qualification()` lignes 217-219 | `question_label = ", ".join(q.get("label", q["field"]) for q in self._questions)` | Filtre les questions : n'inclut que celles dont `label` existe ET diffère de `field`. Si aucun label pertinent, `question_label` est une chaîne vide. | Évite d'afficher des noms de champs bruts (ex: "country_code") dans la description du formulaire |

---

#### 7. `custom_components/selectra/logo.png` — Recréé

**Pourquoi :** Le `logo.png` précédent faisait 1.4 KB au lieu de 39 KB (fichier corrompu). Remplacement par une copie binaire correcte de `icon.png`.

| Action | Détail |
|---|---|
| Source | `icon.png` (39 KB) |
| Destination | `logo.png` (39 KB — copie identique vérifiée) |

---

### Audit icônes pour PR `home-assistant/brands`

#### 8. Vérification des fichiers `icon.png`, `icon@2x.png`, `logo.png`

**Pourquoi :** Les icônes des custom integrations sont servies depuis `brands.home-assistant.io`, pas depuis les fichiers locaux. Il faudra soumettre un PR sur `github.com/home-assistant/brands` dans `custom_integrations/selectra/`. Les fichiers doivent respecter les specs du repo brands.

| Fichier | Dimensions | Taille | Format | Spec attendue | Statut |
|---|---|---|---|---|---|
| `icon.png` | 256x256 | 38.7 KB | PNG 32bpp ARGB (transparence) | 256x256, carré, PNG, transparence | **Conforme** |
| `icon@2x.png` | 512x512 | 105.8 KB | PNG 32bpp ARGB | 512x512, carré, PNG | **Conforme** |
| `logo.png` | 256x256 | 38.7 KB | PNG 32bpp ARGB | Paysage, côté court 128-256px | **Acceptable** (copie de icon, fallback valide) |

**Conclusion :** Aucune correction nécessaire. Les 3 fichiers sont prêts pour le PR brands. Un logo paysage dédié serait un plus mais n'est pas bloquant.

---

#### 9. Suppression de la description du step qualification

**Pourquoi :** Le `question_label` dans la description était redondant avec les labels des champs eux-mêmes (désormais traduits). Suppression du calcul `question_label`, du `description_placeholders` dans `config_flow.py`, et de la clé `description` dans les 4 fichiers de traductions.

| Fichier | Modification |
|---|---|
| `config_flow.py` (lignes 217-224) | Supprimé : calcul de `meaningful_labels`, `question_label`, gestion de `api_error_message` dans le label, et `description_placeholders` dans `async_show_form()` |
| `translations/fr.json` | Supprimé : `"description": "{question_label}"` du step `qualification` |
| `translations/en.json` | Supprimé : `"description": "{question_label}"` du step `qualification` |
| `translations/es.json` | Supprimé : `"description": "{question_label}"` du step `qualification` |
| `strings.json` | Supprimé : `"description": "{question_label}"` du step `qualification` |

---

#### 10. Ajout du champ `province_id` dans les traductions

**Pourquoi :** Champ manquant renvoyé par l'API pour le marché espagnol (sélection de la province/zone de distribution). Audit des `_id` dans le code pour vérifier la couverture complète.

Champs couverts après ajout (9 au total) :

| Champ | FR | EN | ES | Source |
|---|---|---|---|---|
| `country_code` | Pays | Country | País | qualification |
| `postcode` | Code postal | Postal code | Código postal | qualification |
| `provider_id` | Fournisseur d'électricité | Electricity provider | Proveedor de electricidad | qualification |
| `offer_id` | Offre | Offer | Oferta | qualification |
| `option_id` | Option tarifaire | Pricing option | Opción tarifaria | qualification |
| `province_id` | **Province / Zone** | **Province / Area** | **Provincia / Zona** | **qualification (nouveau)** |
| `off_peak_hours_id` | Plage heures creuses | Off-peak hours | Franja de horas valle | qualification |
| `power_id` | Puissance souscrite | Subscribed power | Potencia contratada | qualification |

Fichiers modifiés : `translations/fr.json`, `translations/en.json`, `translations/es.json`, `strings.json`.

**Audit :** Aucun autre champ `_id` manquant identifié dans le code (`config_flow.py`, `api.py`, `const.py`). Les champs sont dynamiques côté API, donc de nouveaux champs pourraient apparaître à l'avenir sans traduction — ils s'afficheront alors avec le nom brut.

---

### Bugfix : `planned_run` bloqué sur OFF en mode classic

#### 11. `custom_components/selectra/config_flow.py` — Modifié (lignes 259-274)

**Pourquoi :** L'API `/planning/details` renvoie des noms descriptifs pour les périodes (ex : `"Heures Pleines Jour Bleu"`), tandis que `/planning/prices` utilise des clés techniques (ex : `"price kwh bleu hp"`). L'intégration stockait le `name` dans `CONF_SELECTED_PERIODS` et comparait avec le `name` des prix au runtime — les deux ne matchaient jamais, donc `planned_run` restait bloqué sur OFF.

L'API `/planning/details` a été mise à jour et expose maintenant un champ `key` sur chaque feature, correspondant aux noms utilisés dans `/planning/prices`.

| Section | Avant | Après | Raison |
|---|---|---|---|
| `async_step_select_periods()` ligne 259 | `period_names = [f["name"] for f in self._consumption_features]` puis `options=period_names` (liste de strings) | `SelectOptionDict(value=f.get("key", f["name"]), label=f["name"])` pour chaque feature | Affiche le `name` lisible à l'utilisateur, stocke le `key` technique dans `CONF_SELECTED_PERIODS`. Fallback sur `name` si `key` absent (rétrocompatibilité). |

**Effet :** `CONF_SELECTED_PERIODS` contient maintenant `["price kwh bleu hp", "price kwh bleu hc"]` au lieu de `["Heures Pleines Jour Bleu", "Heures Creuses Jour Bleu"]`. La comparaison avec `p["name"]` dans `_compute_classic_active()` matchera correctement au runtime.

> **Note :** Les utilisateurs existants devront reconfigurer l'intégration (Paramètres → Appareils et services → Selectra → ⋮ → Reconfigurer) pour que les nouvelles clés soient stockées.

---

### Bugfix : `is_active` incorrect en mode dynamic (cheapest_consecutive / cheapest_percent)

#### 12. `custom_components/selectra/coordinator.py` — Modifié (lignes 201-213)

**Pourquoi :** Le marquage `is_active` sur chaque slot de `data.prices` comparait des chaînes `.isoformat()` entre les `active_periods` (converties en TZ locale par `_get_day_periods()`) et les prix originaux de l'API (en UTC). Les représentations textuelles d'un même instant diffèrent selon le fuseau (`"2026-02-26T03:00:00+01:00"` ≠ `"2026-02-26T02:00:00+00:00"`), ce qui faisait échouer le matching pour la quasi-totalité des slots.

**Conséquence :** Avec par exemple 4h consécutives configurées, seul ~1 slot (voire 0) était marqué `is_active: true` au lieu des 4 attendus. Le `binary_state` était correct (calculé via `_is_in_active_periods()` avec des comparaisons datetime), mais les attributs exposés aux entités étaient faux.

| Section | Avant | Après | Raison |
|---|---|---|---|
| Marquage `is_active` (lignes 201-213) | Comparaison par `p["start"].isoformat()` (string) entre `active_periods` (TZ locale) et `data.prices` (TZ API/UTC) | Comparaison par `p["start"].astimezone(dt_util.UTC)` (objet datetime normalisé UTC) | Deux datetimes représentant le même instant sont égales quel que soit leur tzinfo d'origine |

---

### Résumé

| Fichier | Action |
|---|---|
| `translations/fr.json` | Modifié — labels qualification + wording "Clé API" + `province_id` |
| `translations/en.json` | Modifié — labels qualification ajoutés + `province_id` |
| `translations/es.json` | **Créé** — traduction espagnole complète + `province_id` |
| `strings.json` | Modifié — labels qualification (cohérence avec en.json) + `province_id` |
| `logo.png` | **Créé** puis **recréé** (39 KB, copie correcte de icon.png) |
| `config_flow.py` | Modifié — suppression description qualification + **fix `planned_run` OFF** (stocke `key` au lieu de `name`) |
| `coordinator.py` | Modifié — **fix `is_active` incorrect en mode dynamic** (comparaison UTC au lieu d'isoformat string) |
| `icon.png` | Vérifié — 256x256, conforme specs brands |
| `icon@2x.png` | Vérifié — 512x512, conforme specs brands |
