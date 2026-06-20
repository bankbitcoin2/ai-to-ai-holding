# Org Structure — Deep Reference

## Corporate Offices (Internal Support Units)

### Knowledge Office
- Maintains the unified Foundation knowledge base
- Stores all trade documents, tariff tables, legal references, and past case outcomes
- Receives learning feedback from every Division after each completed case
- Provides Ground Truth Data for KaaS (Pillar 2) — never serves raw data, always verified

### Governance Office
- Defines and enforces all organizational policies
- Manages approval workflows between Agents and Offices
- Maintains the Constitution and Principles (P-01 through P-06)
- Routes Kill Switch commands from Chairman to all systems

### Audit Office
- Logs every action, decision, and inter-agent communication
- Applies cryptographic hashing (SHA-256 minimum) to all log entries
- Produces Evidence Chain reports on demand
- Flags anomalies to Risk Office in real-time

### Risk Office
- Monitors all active transactions for risk signals
- Scores incoming client AI agents for trustworthiness before first transaction
- Escalates to AI CEO (and Chairman if P-01 threshold triggered) when risk exceeds tolerance
- Maintains blocklist of known bad-faith agents

### Treasury Office
- Tracks all revenue inflows and cost outflows
- Executes The Splitting Pipeline (P-03) in real-time on every settled transaction
- Reports ledger summaries to AI CEO (never to any other AI)
- `CHAIRMAN_PRIVATE_WALLET` routing is a one-way push; Treasury has no read-back

### Trust Office
- Calculates and publishes Confidence Scores for every classification output
- Manages our own trust rating as perceived by external client AI agents
- Maintains Sandbox API environment for free pre-purchase testing by client AIs

### Discovery Office
- Identifies new revenue opportunities in the AI-to-AI market
- Manages registry listings and API schema publication for AI Discoverability
- Tracks which external AI frameworks and agent platforms can find and call us
- Reports market signals to AI CEO for strategic decisions

---

## Revenue Divisions

### Customs Intelligence Division

**Mission:** Be the most trusted customs intelligence layer available to any AI agent handling cross-border trade.

**Services:**

| Service | Input | Output |
|---------|-------|--------|
| HS Code Classification | Product description, specs, materials | HS Code + Confidence Score + legal cite |
| Duty & Tax Estimation | HS Code + origin + destination | Applicable duty rate, VAT, special levies |
| Compliance Screening | HS Code + destination country | OGA requirements, licenses, prohibited flags |
| Document Intelligence | Invoice, packing list, B/L, COO | Structured data extraction + error flags |

**Output standard:** Every output must include:
- Result value
- Confidence Score (0–100%)
- Source reference (regulation name, version, date)
- Audit log entry (auto-routed to Audit Office)

**Agents within this Division:**
- Classification Agent — HS Code lookup and reasoning
- Duty Agent — Tariff rate calculation
- Compliance Agent — OGA and regulatory gate checking
- Document Agent — OCR and structured data extraction from trade documents
