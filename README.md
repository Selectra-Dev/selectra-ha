# Selectra - Home Assistant Integration

Intégration Home Assistant pour récupérer les prix de l'électricité en temps réel via l'[API Electricity Planning de Selectra](https://api.selectra.com). Les prix sont exposés sous forme de capteurs et peuvent être utilisés dans des automatisations pour piloter vos appareils aux heures les moins chères.

## Couverture

L'API couvre un grand nombre de pays, fournisseurs et offres à travers le monde. Parmi les marchés supportés : toutes les offres du marché domestique français (Tempo, EJP, Modulo, Zen Flex, Flexiwatt, Heures Eco+, prix dynamiques...), le PVPC espagnol, les offres dynamiques belges et néerlandaises, les tarifs multi-horaires italiens, et bien d'autres. Consultez l'[API Store Selectra](https://api.selectra.com) pour la couverture à jour.

### Clé API

Cette intégration est gratuite pour les utilisateurs Home Assistant, mais nécessite une clé API afin de sécuriser son utilisation. Envoyez un email à aurian@selectra.info pour obtenir votre clé sous 24h.

---

## Capteurs

L'intégration crée les entités suivantes :

| Entité | Type | Description |
|--------|------|-------------|
| `binary_sensor.<nom>_planned_run` | Binary sensor | ON quand c'est le moment de consommer, OFF sinon |
| `sensor.<nom>_current_price` | Sensor | Prix en cours (EUR/kWh) |
| `sensor.<nom>_provider` | Sensor | Fournisseur configuré |
| `sensor.<nom>_offer` | Sensor | Offre configurée |
| `sensor.<nom>_option` | Sensor | Option tarifaire configurée |

> `<nom>` est généré automatiquement par Home Assistant à partir du nom de votre fournisseur et offre (ex : `edf_tempo`). Les noms affichés dans l'interface sont traduits selon la langue configurée dans HA.

### Attributs de `binary_sensor.<nom>_planned_run`

Le capteur binaire porte des attributs avec l'ensemble des données tarifaires :

| Attribut | Description |
|----------|-------------|
| `mode` | Type de tarif : `flat`, `classic` ou `dynamic` |
| `current_period_name` | Nom de la période en cours (ex : "Heures Creuses") |
| `current_price` | Prix actuel en EUR/kWh |
| `currency` | Devise |
| `next_change` | Prochain changement de période |
| `prices` | Liste complète des prix horaires avec `name`, `price`, `start`, `end`, `is_active` |

---

## Installation

### HACS

1. Ouvrez **HACS** → **Intégrations** → menu **⋮** → **Dépôts personnalisés**
2. Ajoutez l'URL du dépôt avec la catégorie **Intégration**
3. Recherchez **Selectra** et cliquez sur **Télécharger**
4. Redémarrez Home Assistant

### Manuelle

Copiez le dossier `custom_components/selectra/` dans votre répertoire `config/custom_components/` et redémarrez Home Assistant.

---

## Configuration

1. Allez dans **Paramètres → Appareils et services**
2. Cliquez sur **+ Ajouter une intégration**
3. Recherchez **Selectra**

L'assistant vous guide à travers la qualification de votre contrat : pays, code postal, fournisseur, offre et option tarifaire. Les choix sont chargés dynamiquement depuis l'API en fonction de votre marché.

Pour les **tarifs multi-horaires** (Heures Creuses / Heures Pleines, Tempo, EJP, etc.), une étape vous permet de sélectionner les périodes pendant lesquelles vos appareils doivent fonctionner. Par exemple, cochez uniquement « Heures Creuses » pour ne consommer qu'en heures creuses, ou décochez « Jour Rouge » pour couper vos appareils les jours les plus chers.

Pour les **tarifs dynamiques** (PVPC, prix spot, etc.), une étape supplémentaire vous propose une stratégie d'optimisation :

- **X% les moins chers du jour** (défaut : 30%) - Sélectionne les heures les moins chères de la journée
- **X heures consécutives les moins chères** (défaut : 6h) - Trouve le meilleur créneau continu (idéal pour la recharge d'un véhicule électrique)

---

## Utilisation

Le principe est simple : `binary_sensor.<nom>_planned_run` passe à **ON** quand le prix est avantageux et à **OFF** quand il ne l'est plus. Utilisez-le comme déclencheur dans n'importe quelle automatisation pour piloter vos appareils connectés (chauffe-eau, wallbox, climatisation, prises connectées, etc.).

Pour créer une automatisation via l'interface :

1. **Paramètres → Automatisations → Créer une automatisation**
2. **Déclencheur** : État → `binary_sensor.<nom>_planned_run` → vers **on**
3. **Action** : Allumer l'appareil de votre choix

Créez une seconde automatisation identique avec le déclencheur vers **off** pour éteindre l'appareil.

Le `sensor.<nom>_current_price` peut aussi être utilisé directement dans des templates pour des scénarios plus avancés, comme ajuster une consigne de chauffage proportionnellement au prix.

---

## Graphique des prix

Les attributs `prices` de `binary_sensor.<nom>_planned_run` contiennent les prix horaires de la journée. Ils peuvent être affichés avec la carte [ApexCharts](https://github.com/RomRider/apexcharts-card) (disponible via HACS) :

```yaml
type: custom:apexcharts-card
graph_span: 24h
span:
  start: day
now:
  show: true
  label: Maintenant
header:
  show: true
  title: Prix de l'électricité aujourd'hui (€/kWh)
yaxis:
  - decimals: 3
series:
  - entity: binary_sensor.<nom>_planned_run
    stroke_width: 2
    type: column
    opacity: 1
    data_generator: |
      return entity.attributes.prices.map((entry) => {
        return [new Date(entry.start), entry.price];
      });
```

Le `sensor.<nom>_current_price` peut aussi être affiché avec une simple carte **Historique** pour visualiser l'évolution des prix.

---

## Langues

L'interface de configuration est disponible en français, anglais et espagnol. Les noms des offres et périodes tarifaires sont renvoyés dans la langue correspondant à votre configuration Home Assistant.

## Reconfiguration

Pour changer d'offre ou de fournisseur : **Paramètres → Appareils et services → Selectra → ⋮ → Reconfigurer**.

## Dépannage

- **L'intégration ne se connecte pas** - Vérifiez votre clé API et votre connexion internet.
- **Les prix ne se mettent pas à jour** - L'intégration se met à jour automatiquement selon le calendrier tarifaire de votre offre. Pour les tarifs dynamiques (ex : PVPC), les prix du lendemain sont généralement publiés en fin de journée.

## Support

Pour toute question sur l'API ou la clé d'accès, vous pouvez nous contacter directement à support.home-assistant@selectra.info. Ou bien rendez-vous sur l'[API Store Selectra](https://api.selectra.com). Pour un bug lié à l'intégration, ouvrez une issue sur ce dépôt.
