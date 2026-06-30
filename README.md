# ⚡ Selectra for Home Assistant

![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Integration-blue?logo=homeassistant)
![Status](https://img.shields.io/badge/Status-Beta-orange)
![License](https://img.shields.io/badge/License-Apache%202.0-green)
![Free](https://img.shields.io/badge/Price-Free-brightgreen)

**An electricity price integration for Home Assistant from [Selectra](https://selectra.com).**

Turn your devices on and off based on the real-time price of electricity. Perfect for off-peak schedules, demand-response programs, and dynamic pricing offers.

---

## 🚧 Beta Notice

> This integration is currently in **beta**. We are actively developing new features and improving reliability. We'd love your feedback — whether it's a bug report, a feature request, or just an idea. Don't hesitate to [open an issue](../../issues) or [start a discussion](../../discussions)!

---

## ✨ Features

- **Real-time electricity pricing** — Access current and upcoming electricity prices for your plan directly in Home Assistant.
- **A ready-to-automate "Planned Run" signal** — A single binary sensor that turns `on` when it's a good time to run your devices, whatever your tariff type.
- **Smart automations** — Trigger automations based on price thresholds, off-peak windows, or the cheapest upcoming hours.
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

## ⚙️ Configuration

Everything is configured through the Home Assistant UI — no YAML required. After adding the integration you'll go through a short guided setup:

1. **API token** — Paste your free Selectra API token (see [below](#-data-source--api-access)).
2. **Qualification** — Identify your exact contract: country, postal code, electricity provider, offer, pricing option, subscribed power, and off-peak hours where applicable.
3. **Behaviour** — Depending on your plan type, you'll then either:
   - **pick the active periods** (multi-period plans, e.g. off-peak), or
   - **choose an optimization strategy** (dynamic plans).

> Need to change something later? Select the integration → **Configure / Reconfigure** to re-run this flow without removing the integration.

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
| **Provider** | `sensor` *(diagnostic)* | Your electricity provider. |
| **Offer** | `sensor` *(diagnostic)* | Your offer/plan. Carries rich attributes (category, distributor, off-peak hours, features…). |
| **Option** | `sensor` *(diagnostic)* | Your pricing option. |

> Exact entity IDs depend on your setup — check them under **Settings → Devices & Services → Selectra**. The examples below use `binary_sensor.selectra_planned_run` and `sensor.selectra_current_price`.

### Useful attributes

**`Planned Run`** exposes, among others:

- `current_period_name`, `current_price`, `currency`
- `next_change` — when the sensor will next switch on/off
- `prices` — the full list of upcoming price periods, each with `name`, `price`, `start`, `end`, and `is_active`. Ideal for building charts (see [Visualization](#-visualization)).

**`Current Price`** exposes `period_name`, `period_start`, `period_end`, and `next_update`.

## 🤖 Automation examples

**Run your water heater during the planned (cheap) periods:**

```yaml
automation:
  - alias: "Water heater — cheap hours only"
    trigger:
      - platform: state
        entity_id: binary_sensor.selectra_planned_run
        to: "on"
    action:
      - action: switch.turn_on
        target:
          entity_id: switch.water_heater
  - alias: "Water heater — off outside cheap hours"
    trigger:
      - platform: state
        entity_id: binary_sensor.selectra_planned_run
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
        entity_id: sensor.selectra_current_price
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
  - entity: binary_sensor.selectra_planned_run
    name: Price
    type: column
    data_generator: |
      return entity.attributes.prices.map(p => [new Date(p.start).getTime(), p.price]);
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

**How often does it update?**
Polling is dynamic: the integration follows the API's `next_update` hint (at most once a minute, ~every 15 minutes by default) and recalculates the `Planned Run` state locally at each period boundary — so transitions are on time without hammering the API.

## 🤝 Contributing

We welcome contributions of all kinds! Here's how you can help:

- **🐛 Report bugs** — [Open an issue](../../issues) with steps to reproduce.
- **💡 Suggest features** — We're very open to ideas and requests. Tell us what would make this integration more useful for you.
- **🔧 Submit a PR** — Fork the repo, make your changes, and open a pull request.

## 📄 License

This project is licensed under the [Apache License 2.0](LICENSE.txt).

---

<p align="center">
  Made with ⚡ by <a href="https://selectra.com">Selectra</a>
</p>
