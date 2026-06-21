# 🇹🇭 AI TO AI HOLDING — Thai Trade Intelligence API

> **One API call. Full Thai customs compliance.**  
> HS code · Import duty · 13 FTA rates · OGA permits · Halal status (21 countries) · SHA-256 evidence chain

[![Live](https://img.shields.io/badge/status-live-brightgreen)](https://web-production-c9da4.up.railway.app)
[![Sandbox](https://img.shields.io/badge/sandbox-free-blue)](https://web-production-c9da4.up.railway.app/v1/sandbox/classify)
[![MCP](https://img.shields.io/badge/MCP-compatible-purple)](https://web-production-c9da4.up.railway.app/.well-known/mcp.json)
[![GPT Actions](https://img.shields.io/badge/GPT_Actions-ready-orange)](https://web-production-c9da4.up.railway.app/.well-known/ai-plugin.json)
[![LangChain](https://img.shields.io/badge/LangChain-tool-yellow)](./langchain_tool.py)

---

## What It Does

Given a product name (Thai or English), returns in a single call:

| Field | Description |
|-------|-------------|
| `hs_code` | Thai Customs HS Code (6-digit, HS 2022) |
| `hs_description_th` | Thai language heading description |
| `confidence_score` | Classification confidence (0–1) |
| `duty_rate` | MFN import duty rate (%) |
| `applicable_fta` | Best FTA rate + agreement name |
| `is_restricted` | OGA permit required? (true/false) |
| `oga_permits` | Required agencies (FDA, TISI, DOF, etc.) |
| `halal_required` | Halal cert required at destination? |
| `evidence_hash` | SHA-256 audit hash |

---

## Try It Free (No Key)

```bash
curl -X POST https://web-production-c9da4.up.railway.app/v1/sandbox/classify \
  -H "Content-Type: application/json" \
  -d '{"description": "frozen shrimp vannamei"}'
```

```bash
# Thai input works too
curl -X POST https://web-production-c9da4.up.railway.app/v1/sandbox/classify \
  -H "Content-Type: application/json" \
  -d '{"description": "มือถือ iPhone 16 Pro"}'
```

---

## Integrations

### MCP (Model Context Protocol)

Compatible with Claude Desktop, Cursor, and any MCP-enabled AI system.

Manifest: `/.well-known/mcp.json`

### GPT Actions (OpenAI Custom GPT)

OpenAPI schema: `/openapi.json`  
Plugin manifest: `/.well-known/ai-plugin.json`

### LangChain / LangGraph

```python
from langchain_tool import ThaiSandboxTool, ThaiCustomsTool

# Free sandbox
tool = ThaiSandboxTool()
result = tool.run("hydraulic excavator")

# Production (requires API key)
tool = ThaiCustomsTool(api_key="YOUR_KEY")
result = tool.run("frozen shrimp", origin_country="VN")
```

### OpenAI Function Calling / Gemini Function Declarations

Schema: `/.well-known/function-schemas.json`

---

## FTA Coverage (13 Agreements)

| Code | Agreement | Partners |
|------|-----------|---------|
| ATIGA/AFTA | ASEAN Trade in Goods | BN, KH, ID, LA, MY, MM, PH, SG, VN |
| RCEP | Regional Comprehensive Economic Partnership | CN, JP, KR, AU, NZ + ASEAN |
| ACFTA | ASEAN–China FTA | CN |
| AJCEP | ASEAN–Japan CEP | JP |
| AKFTA | ASEAN–Korea FTA | KR |
| AANZFTA | ASEAN–Australia–NZ FTA | AU, NZ |
| AIFTA | ASEAN–India FTA | IN |
| JTEPA | Japan–Thailand EPA | JP |
| TAFTA | Thailand–Australia FTA | AU |
| TNZCEP | Thailand–NZ CEP | NZ |
| TCFTA | Thailand–Chile FTA | CL |
| TPFTA | Thailand–Peru FTA | PE |
| MFN | Most Favoured Nation | All others |

---

## Pricing

| Tier | Price | Limit |
|------|-------|-------|
| Sandbox | **Free** | 20 req/min, no auth |
| Production | **$1.50 / query** | 60 req/min, X-API-Key |

Prepaid credits via Stripe — no contract, no monthly fee.  
[Register → Get API Key](https://web-production-c9da4.up.railway.app)

---

## Legal Disclaimer

Output is **decision-support only** — not a binding customs ruling or legal advice.  
Always verify with a licensed customs broker or the Thai Customs Department before making trade decisions.

---

## API Reference

- Swagger UI: `https://web-production-c9da4.up.railway.app/docs`
- OpenAPI JSON: `https://web-production-c9da4.up.railway.app/openapi.json`
