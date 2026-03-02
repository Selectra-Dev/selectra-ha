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
- **Smart automations** — Trigger automations based on price thresholds, off-peak windows, or cheapest upcoming hours.
- **Massive coverage** — 80 countries, 2,000+ energy providers, and 16,000+ electricity plans supported today.
- **Always free** — This integration is and will remain free to use.

## 🌍 Coverage

| | Current | Goal (end of 2026) |
|---|---|---|
| **Countries** | 80 | Worldwide |
| **Energy providers** | 2,000+ | All residential providers |
| **Electricity plans** | 16,000+ | Every residential plan |

Can't find your provider or plan? [Open an issue](../../issues) and we'll look into adding it.

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

After installing, add the integration through the Home Assistant UI. You will be prompted to select your country, energy provider, and electricity plan.

## 📡 Data Source & API Access

All electricity pricing data is provided by the [Selectra Electricity Planning API](https://api.selectra.com/electricity_planning).

This integration requires an API token from Selectra. Don't have one yet? Contact us at **support.home-assistant@selectra.info** and we'll get you set up.

## 🤝 Contributing

We welcome contributions of all kinds! Here's how you can help:

- **🐛 Report bugs** — [Open an issue](../../issues) with steps to reproduce.
- **💡 Suggest features** — We're very open to ideas and requests. Tell us what would make this integration more useful for you.
- **🔧 Submit a PR** — Fork the repo, make your changes, and open a pull request.

## 📄 License

This project is licensed under the [Apache License 2.0](LICENSE).

---

<p align="center">
  Made with ⚡ by <a href="https://selectra.com">Selectra</a>
</p>
