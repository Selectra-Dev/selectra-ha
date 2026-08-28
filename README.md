# ⚡ Selectra for Home Assistant

![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Integration-blue?logo=homeassistant)
![Status](https://img.shields.io/badge/Status-Beta-orange)
![License](https://img.shields.io/badge/License-Apache%202.0-green)
![Free](https://img.shields.io/badge/Price-Free-brightgreen)

**An electricity price integration for Home Assistant from [Selectra](https://selectra.com).**

Turn your devices on and off based on the real-time price of electricity. Perfect for off-peak schedules, demand-response programs, and dynamic pricing offers.

---

## 🚧 Beta Notice

> This integration is currently in **beta**. We are actively developing new features and improving reliability. We'd love your feedback — whether it's a bug report, a feature request, or just an idea. Don't hesitate to [open an issue](../../issues)!

---

## ✨ Features

- **Real-time electricity pricing** — Access current and upcoming electricity prices for your plan directly in Home Assistant.
- **A ready-to-automate "Planned Run" signal** — A single binary sensor that turns `on` when it's a good time to run your devices, whatever your tariff type.
- **Smart automations** — Trigger automations based on price thresholds, off-peak windows, or the cheapest upcoming hours.
- **Feed-in tariffs** — If you have solar panels, track what your exported kWh earn you, right next to what you pay.
- **Light on the API** — Responses are cached for as long as they stay valid, so restarting Home Assistant costs you nothing against your rate limit.
- **Massive coverage** — 80 countries, 2,000+ energy providers, and 16,000+ electricity plans supported today.
- **Always free** — This integration is and will remain free to use.

## 🌍 Coverage

| | Current | Goal (end of 2026) |
|---|---|---|
| **Countries** | 80 | Worldwide |
| **Energy providers** | 2,000+ | All residential providers |
| **Electricity plans** | 16,000+ | Every residential plan |

Can't find your provider or plan? [Open an issue](../../issues) and we'll look into adding it.

## ✅ Requirements

- **Home Assistant 2025.12.0 or newer.**
- A **free Selectra API token** — see [Data Source & API Access](#-data-source--api-access).

## 📦 Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant.
2. Search for **Selectra** and install it.
3. Restart Home Assistant.
4. Go to **Settings** → **Devices & Services** → **Add Integration** → search for **Selectra**.

> **Not finding it?** Go to HACS → three-dot menu → *Custom repositories*, paste `https://github.com/Selectra-Dev/selectra-ha` and select *Integration*.

### Manual installation

1. Download the latest release from the [Releases](../../releases) page.
2. Copy the `custom_components/selectra` folder into your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.
4. Go to **Settings** → **Devices & Services** → **Add Integration** → search for **Selectra**.

## 🔄 Upgrading

Updating through HACS brings the new code, but **it does not re-run your setup**. Anything that depends on a question you were never asked needs a reconfiguration.

**Feed-in tariffs (new in v1.2.0)** are the case in point: your contract was qualified before that question existed, so it won't appear on its own.

To get it:

1. **Settings** → **Devices & Services**, then open the **Selectra** entry.
2. **⋮ menu** → **Reconfigure**.
3. Answer the questions again — **your API token is not asked for again**, the existing one is reused.
4. Answer **yes** to the feed-in question, then complete the follow-up questions about your installation.

What to expect:

- **The whole qualification runs again**, from the country onwards. That is normal — the flow is rebuilt from scratch rather than edited in place. On a **classic** plan you'll pick your active periods again; on a **dynamic** one, your strategy. Note your current settings down first if you'd rather not think about them twice.
- **Your entities and their history are kept.** Reconfiguring updates the existing entry, so every entity keeps its identity and its recorded history. The new **Feed-in Price** sensor is simply added.
- **No solar panels?** Answer **no**, or don't reconfigure at all. Nothing else changes.

Improvements that don't depend on your answers — caching, bug fixes — apply on their own after the restart that follows an update.

## ⚙️ Configuration

Everything is configured through the Home Assistant UI — no YAML required. After adding the integration you'll go through a short guided setup:

1. **API token** — Paste your free Selectra API token (see [below](#-data-source--api-access)).
2. **Qualification** — Identify your exact contract: country, postal code, electricity provider, offer, pricing option, subscribed power, and off-peak hours where applicable. Where feed-in tariffs are available you'll also be asked whether you export solar power, and if so a few questions about your installation (see [Feed-in tariffs](#-feed-in-tariffs)).
3. **Behaviour** — For **classic** (multi-period) and **dynamic** plans, you'll then either:
   - **pick the active periods** (classic plans, e.g. peak / off-peak), or
   - **choose an optimization strategy** (dynamic plans).

   **Flat-rate plans skip this step** — the integration is ready as soon as qualification is done.

> Need to change something later? Select the integration → **⋮ menu → Reconfigure**. This is Home Assistant's native reconfigure flow: it reuses your existing API token and re-runs qualification — you won't be asked for the token again.

## 🧠 How it works — operating modes

The integration adapts to your tariff. The **Planned Run** binary sensor turns `on` according to one of three modes:

| Mode | For which plans | When `Planned Run` is `on` |
|---|---|---|
| **Flat** | Single flat-rate tariffs | Always `on` (the price never changes). |
| **Classic** | Multi-period plans (e.g. peak / off-peak) | During the **periods you selected** at setup. |
| **Dynamic** | Dynamic / spot-price plans | During the cheapest hours, based on your chosen **strategy**. |

For **dynamic** plans, two strategies are available:

- **Cheapest X% of the day** — the sensor is `on` during the cheapest `X%` of today's hours (e.g. the cheapest 30%).
- **Cheapest X consecutive hours** — the sensor is `on` during the single cheapest uninterrupted window of `X` hours (great for EV charging or a dishwasher run).

## 📟 Entities

Once configured, the integration creates the following entities:

| Entity | Type | Description |
|---|---|---|
| **Planned Run** | `binary_sensor` | The core entity. `on` = good time to run your devices (see modes above). |
| **Current Price** | `sensor` | The current electricity price per kWh, in your currency. |
| **Feed-in Price** | `sensor` *(optional)* | What you are paid per kWh exported. Only created if you qualified with a feed-in tariff. |
| **Provider** | `sensor` *(diagnostic)* | Your electricity provider. |
| **Offer** | `sensor` *(diagnostic)* | Your offer/plan. Carries rich attributes (category, distributor, off-peak hours, features…). |
| **Option** | `sensor` *(diagnostic)* | Your pricing option. |

> **⚠️ Entity IDs are built from the entity name in your Home Assistant language, with no `selectra` prefix.** On an English instance you get `binary_sensor.planned_run` and `sensor.current_price`; on a French one, `binary_sensor.marche_planifiee` and `sensor.prix_actuel`.
>
> The examples below use the English IDs. **Check your own** under **Settings → Devices & Services → Selectra → entities**, and adapt them — an automation pointing at an entity that doesn't exist fails silently.

### Useful attributes

**`Planned Run`** exposes, among others:

- `current_period_name`, `current_price`, `currency`
- `next_change` — when the sensor will next switch on/off
- `prices` — the full list of upcoming price periods, each with `name`, `price`, `start`, `end`, and `is_active`. Ideal for building charts (see [Visualization](#-visualization)). Periods also carry `feed_in_price` when you have a feed-in tariff.

**`Current Price`** exposes `period_name`, `period_start`, `period_end`, and `next_update`.

**`Feed-in Price`** exposes `period_name` plus whatever extras your market defines — grid fees (`feed_in_monthly_fee`, `feed_in_yearly_fee`, `feed_in_yearly_fee_per_kw`), the scheme or band you fall under, and any free-form conditions (`feed_in_extra_text`).

## ☀️ Feed-in tariffs

If you export solar power to the grid, the integration can also track what that export earns you.

During setup you'll be asked whether you have a feed-in tariff. Say yes and the integration asks a few follow-up questions about your installation — which ones depends on your country: commissioning date, peak power (kWp/kWc), whether you sell your surplus or your full production, which compensation scheme applies, or simply which tariff you're on.

You then get a **Feed-in Price** sensor holding your current export rate per kWh, and every period in the `prices` attribute gains a `feed_in_price`.

> **Already had the integration installed?** The question only appears when the setup runs again — see [Upgrading](#-upgrading).

> **Not asked about it?** Feed-in tariffs are available on a subset of countries and API tokens. If the question doesn't appear, your token or your country isn't covered yet — [open an issue](../../issues) and we'll tell you where it stands. Saying no, or never being asked, leaves everything else unchanged.

**Charge the home battery from the grid only when importing costs less than exporting pays:**

```yaml
automation:
  - alias: "Battery — charge while import beats export"
    trigger:
      - platform: state
        entity_id: sensor.current_price
    condition:
      - condition: template
        value_template: >
          {{ states('sensor.current_price') | float
             < states('sensor.feed_in_price') | float }}
    action:
      - action: switch.turn_on
        target:
          entity_id: switch.battery_grid_charge
```

## 🤖 Automation examples

> **Your entity IDs may differ from the examples below.** Check the real IDs under **Settings → Devices & Services → Selectra** and adjust the automations and chart config accordingly.

**Run your water heater during the planned (cheap) periods:**

```yaml
automation:
  - alias: "Water heater — cheap hours only"
    trigger:
      - platform: state
        entity_id: binary_sensor.planned_run
        to: "on"
    action:
      - action: switch.turn_on
        target:
          entity_id: switch.water_heater
  - alias: "Water heater — off outside cheap hours"
    trigger:
      - platform: state
        entity_id: binary_sensor.planned_run
        to: "off"
    action:
      - action: switch.turn_off
        target:
          entity_id: switch.water_heater
```

**Charge the EV only when the price drops below a threshold:**

```yaml
automation:
  - alias: "EV charging — below 0.15 /kWh"
    trigger:
      - platform: numeric_state
        entity_id: sensor.current_price
        below: 0.15
    action:
      - action: switch.turn_on
        target:
          entity_id: switch.ev_charger
```

## 📊 Visualization

You can plot today's prices using the `prices` attribute of the **Planned Run** sensor — for example with the popular [ApexCharts card](https://github.com/RomRider/apexcharts-card):

```yaml
type: custom:apexcharts-card
header:
  title: Electricity prices today
series:
  - entity: binary_sensor.planned_run
    name: Price
    type: column
    data_generator: |
      return entity.attributes.prices.map(p => [new Date(p.start).getTime(), p.price]);
```

With a feed-in tariff you can plot both sides at once by adding a second series:

```yaml
  - entity: binary_sensor.planned_run
    name: Feed-in
    type: line
    data_generator: |
      return entity.attributes.prices
        .filter(p => p.feed_in_price != null)
        .map(p => [new Date(p.start).getTime(), p.feed_in_price]);
```

## 📡 Data Source & API Access

All electricity pricing data is provided by the Selectra Electricity Planning API.

This integration requires an API token. To get one:

1. Visit the [Selectra Electricity Planning API](https://api.selectra.com/ha/register) registration page.
2. Follow the instructions to request your **free** API key.
3. Paste the token during the integration's setup (first step).

Need help? Contact us at **support.home-assistant@selectra.info**.

## ❓ FAQ & Troubleshooting

**"Reconfiguration Required" notification appears / entities show as `unavailable`.**
Your contract details need to be refreshed (e.g. your provider changed something). Open **Settings → Devices & Services → Selectra → Reconfigure** and re-run the setup. Entities come back automatically once reconfiguration succeeds.

**"Invalid or missing API key" during setup.**
Double-check the token, or register for a free one at the [API page](https://api.selectra.com/ha/register). Still stuck? Email **support.home-assistant@selectra.info**.

**"Too many requests" / rate limited.**
The Selectra API applies rate limits. Wait a few minutes and try again — the integration also backs off automatically and retries on its own.

**`Current Price` or `Planned Run` shows `unknown` / no data.**
This can happen when no price data is available yet for the current day. The integration polls regularly and will populate the values as soon as data is published.

**I updated but there's no feed-in question and no Feed-in Price sensor.**
Updating doesn't re-run your setup. Reconfigure the integration to be asked — see [Upgrading](#-upgrading). If the question still doesn't appear after reconfiguring, your token's plan or your country isn't covered yet; email **support.home-assistant@selectra.info** and we'll tell you where it stands.

**My automation does nothing, even though the sensor looks right.**
Check the entity ID. IDs are generated from the entity name in your Home Assistant language and carry no `selectra` prefix — a French instance has `binary_sensor.marche_planifiee`, not `binary_sensor.selectra_planned_run`. An automation pointing at a non-existent entity fails silently. Your real IDs are under **Settings → Devices & Services → Selectra → entities**.

**How often does it update?**
Polling is dynamic: the integration follows the API's `next_update` hint (at most once a minute, ~every 15 minutes by default) and recalculates the `Planned Run` state locally at each period boundary — so transitions are on time without hammering the API.

**Does it re-download everything when I restart Home Assistant?**
No. Responses are cached on disk: your contract details for 48 hours, and prices until the `next_update` the API returns with them. A restart reuses what is still valid, so restarting often costs you nothing against your rate limit. Reconfiguring, or removing the integration, clears the cache.

## 🤝 Contributing

We welcome contributions of all kinds! Here's how you can help:

- **🐛 Report bugs** — [Open an issue](../../issues) with steps to reproduce.
- **💡 Suggest features** — We're very open to ideas and requests. Tell us what would make this integration more useful for you.
- **🔧 Submit a PR** — Fork the repo, make your changes, and open a pull request.

Running the tests:

```bash
pip install -r requirements-test.txt
pytest
```

> Home Assistant doesn't run on Windows — use WSL or Linux.

## 📄 License

This project is licensed under the [Apache License 2.0](LICENSE.txt).

---

<p align="center">
  Made with ⚡ by <a href="https://selectra.com">Selectra</a>
</p>
