# RapidAPI Listing Content — AI TO AI HOLDING: Thai Trade Intelligence

## API Name
Thai Trade Intelligence — HS Code, FTA Rates, OGA & Halal

## Short Description (150 chars)
One call: Thai HS code + import duty + 13 FTA rates + OGA permits + Halal status. Accepts Thai & English. Free sandbox.

## Long Description
Thai Trade Intelligence API is the fastest way for AI agents and developers to get complete Thai customs import compliance data in a single API call.

**What you get per call:**
- HS Code classification (6-digit, HS 2022) with confidence score
- Thai-language HS description
- MFN import duty rate
- Best preferential rate across all 13 Thai FTA agreements (RCEP, AFTA/ATIGA, ACFTA, AJCEP, AKFTA, AANZFTA, AIFTA, JTEPA, TAFTA, TNZCEP, TCFTA, TPFTA)
- OGA (Other Government Agency) permit requirements — FDA, TISI/มอก., กรมประมง, กรมปศุสัตว์, กรมวิชาการเกษตร, CITES, MOD, ONCB
- Halal certification requirement check across 21 countries
- SHA-256 evidence hash for audit trail

**Input:** Product description in Thai, English, or both mixed. No preprocessing needed.

**Built for AI agents** — MCP compatible, OpenAI Function Calling ready, LangChain tool wrapper included.

**Try free:** Sandbox endpoint requires no API key (20 req/min rate limit).

## Categories
- Machine Learning
- Data
- Translation
- Business

## Tags
thai customs, hs code, import duty, fta, halal, oga, trade compliance, asean, rcep, langchain, mcp, gpt-actions, thailand, supply chain

## Endpoints to List

### 1. Sandbox Classify (Free)
- Method: POST
- Path: /v1/sandbox/classify
- Auth: None
- Rate limit: 20/min
- Body: `{"description": "string"}`

### 2. Production Classify
- Method: POST
- Path: /v1/customs/classify
- Auth: X-API-Key header
- Rate limit: 60/min
- Body: `{"description": "string", "origin_country": "CN", "value_usd": 1000}`

## Pricing Tiers

### Free (BASIC)
- Endpoint: /v1/sandbox/classify only
- Rate: 20 req/min
- Price: $0.00/month
- Quota: Unlimited requests (rate limited)

### Pro
- All endpoints
- Rate: 60 req/min
- Price: Pay-per-use $1.50/query via prepaid Stripe credits
- No monthly fee, no contract
- Note: Register at https://web-production-c9da4.up.railway.app to get API key

## Base URL
https://web-production-c9da4.up.railway.app

## OpenAPI Spec URL
https://web-production-c9da4.up.railway.app/openapi.json

## Website
https://web-production-c9da4.up.railway.app

## Contact
bankbitcoin2@gmail.com
