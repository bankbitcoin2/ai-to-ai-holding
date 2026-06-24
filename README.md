# AI TO AI HOLDING — Thai Trade Intelligence API

> **One API call. Full Thai customs compliance.**
> HS code · Import duty · 13 FTA rates · OGA permits · Halal status · Invoice analysis · XAI reasoning

[![Live](https://img.shields.io/badge/status-live-brightgreen)](https://web-production-c9da4.up.railway.app)
[![Sandbox](https://img.shields.io/badge/sandbox-free-blue)](https://web-production-c9da4.up.railway.app/v1/sandbox/classify)
[![License](https://img.shields.io/badge/license-BSL_1.1-orange)](./LICENSE.md)
[![MCP](https://img.shields.io/badge/MCP-compatible-purple)](./mcp_plugin.json)
[![LINE](https://img.shields.io/badge/LINE-Bot-00C300)](https://line.me)
[![PWA](https://img.shields.io/badge/PWA-mobile-blue)](https://web-production-c9da4.up.railway.app/pwa)

---

## Quick Start (5 lines)

```bash
# 1. ทดลองฟรี — ไม่ต้อง register
curl -X POST https://web-production-c9da4.up.railway.app/v1/sandbox/classify \
  -H "Content-Type: application/json" \
  -d '{"description": "frozen shrimp vannamei", "origin_country": "VN"}'

# 2. Register → ได้ API Key
curl -X POST https://web-production-c9da4.up.railway.app/v1/register \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "MyBot", "contact_email": "me@example.com"}'

# 3. Production classify (ต้องมี credit)
curl -X POST https://web-production-c9da4.up.railway.app/v1/customs/classify \
  -H "X-API-Key: sk-aitai-YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"description": "laptop computer 14 inch", "origin_country": "CN"}'
```

---

## What You Get

| Field | Description |
|-------|-------------|
| `hs_code` | Thai Customs HS Code (6-digit, HS 2022) |
| `hs_code_11` | Thai 11-digit statistical code (estimate) |
| `hs_description_th` | Thai language heading description |
| `confidence_score` | Classification confidence (0.00–1.00) |
| `candidates` | Top 3 alternative HS codes with confidence |
| `duty_rate` | MFN import duty rate (%) |
| `applicable_fta` | Best FTA rate + agreement name + savings |
| `oga_permits` | Required agencies: FDA, TISI, DOF, etc. |
| `halal_required` | Halal certification check (21 countries) |
| `xai_reasoning` | Explainable AI — why this HS code was chosen |
| `evidence_hash` | SHA-256 audit trail hash |

---

## Channels

### API (Production)
Full REST API with Swagger docs at `/docs`.

### LINE Bot
Add our LINE Official Account, bind your API key, send invoice photos — get instant results in chat.

### PWA (Mobile Web App)
Open `/pwa` on your phone, install to home screen. Camera capture, drag-and-drop upload, offline result cache.

### Claude MCP Plugin
Use `classify_hs`, `check_fta`, `exchange_rate` directly from Claude Desktop or Claude Code. See `mcp_plugin.json`.

---

## Invoice Analysis

Upload a full invoice (PDF, image, Excel, CSV) and get every line item classified automatically:

```bash
curl -X POST https://web-production-c9da4.up.railway.app/v1/invoice/upload \
  -H "X-API-Key: sk-aitai-YOUR_KEY" \
  -F "file=@invoice.pdf"
```

Returns: per-item HS code, duty, FTA savings, OGA flags, Halal status, validation warnings, and billing summary.

---

## Pricing

| Tier | Rate | Best For |
|------|------|----------|
| **Sandbox** | Free | Testing, 20 req/min |
| **Standard** | $0.50 / item | Individual users |
| **VAN / Software** | $0.015 / item | VAN integrations (500+ items/mo) |
| **Volume** | $0.003 / item | High-volume partners (5,000+/mo) |
| **Enterprise S** | $200/mo | 2,000 items included |
| **Enterprise M** | $350/mo | 5,000 items included |
| **Enterprise L** | $500/mo | 15,000 items included |

Prepaid credits via Stripe. Exchange rates available at `GET /v1/exchange-rates`.

### Membership Tiers (Auto-calculated)

| Tier | Qualification | Discount |
|------|---------------|----------|
| VIP | Register + top up | - |
| Gold | 100+ queries/mo or 100K+ THB | 5% |
| Platinum | 500+ queries/mo or 500K+ THB | 10% |
| Diamond | 2,000+ queries/mo or 2M+ THB | 15% |
| SuperPremium | 10,000+ queries/mo or 10M+ THB | 20% |

---

## FTA Coverage (13 Agreements)

ATIGA/AFTA, RCEP, ACFTA, AJCEP, AKFTA, AANZFTA, AIFTA, JTEPA, TAFTA, TNZCEP, TCFTA, TPFTA, MFN.

Covers: ASEAN (10 countries), China, Japan, Korea, Australia, New Zealand, India, Chile, Peru — and MFN for all others.

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/sandbox/classify` | None | Free trial classify |
| POST | `/v1/customs/classify` | API Key | Production classify |
| POST | `/v1/invoice/upload` | API Key | Full invoice analysis |
| POST | `/v1/register` | None | Register + get API key |
| GET | `/v1/billing/balance` | API Key | Check credit balance |
| POST | `/v1/billing/topup` | API Key | Top up via Stripe |
| GET | `/v1/client/analytics` | API Key | Your usage stats |
| GET | `/v1/client/membership` | API Key | Your membership tier |
| GET | `/v1/pricing/tiers` | None | Pricing info |
| GET | `/v1/exchange-rates` | None | Exchange rates (14 currencies) |
| GET | `/v1/exchange-rates/convert` | None | Currency conversion |
| POST | `/v1/mcp/classify_hs` | API Key | MCP: classify |
| POST | `/v1/mcp/check_fta` | API Key | MCP: FTA check |
| POST | `/v1/mcp/exchange_rate` | None | MCP: exchange rate |

Full Swagger: `https://web-production-c9da4.up.railway.app/docs`

---

## License

Business Source License 1.1 — free to use, but you may not build a competing customs classification service. See [LICENSE.md](./LICENSE.md) for details.

After 4 years, each release converts to Apache 2.0.

---

## Legal Disclaimer

Output is **decision-support only** — not a binding customs ruling or legal advice.
Always verify with a licensed customs broker or the Thai Customs Department before making trade decisions.

---

**Copyright (c) 2026 AI TO AI HOLDING. All rights reserved.**
