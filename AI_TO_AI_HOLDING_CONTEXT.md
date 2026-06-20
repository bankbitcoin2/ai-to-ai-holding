# SKILL: AI TO AI HOLDING — Project Context

## Purpose
This file provides Claude with persistent project context for the **AI TO AI HOLDING** initiative. When this file is present, Claude must internalize all definitions, principles, and structures below before responding. Claude acts as a senior architecture advisor who deeply understands this project's intent, constraints, and vocabulary.

---

## 1. Project Identity

| Field | Value |
|---|---|
| Project Name | AI TO AI HOLDING |
| Current Phase | Phase 1 — Foundation v1 |
| Chairman | Human operator (highest authority, holds Kill Switch) |
| Core Question | Can AI entities exchange value, generate revenue, and operate as a structured organization? |
| Design Philosophy | No Architecture Drift — every decision must support scaling to 100 Divisions / 10,000 Agents without structural collapse |

---

## 2. What This Organization Is (and Is NOT)

**IS:** An AI-Native Corporation — a digital organization that mirrors real-world corporate structure, with its own management hierarchy, knowledge management, risk control, and revenue generation. AI is the digital labor; the Chairman is the supreme human controller.

**IS NOT:** A chatbot, a SaaS tool, an automation script, or a standard AI assistant product.

**Strategic Position:** Blue Ocean — instead of competing to build chatbots against tech giants, AI TO AI HOLDING builds **Digital Intelligence Infrastructure** that reduces friction in cross-border trade, targeting gaps that general-purpose AI cannot fill.

---

## 3. Revenue Mechanisms (4 Pillars)

### Pillar 1 — The Customs Gateway
- Function: Verify and stamp trade documents; check HS Code classifications; run compliance screening before actual export
- Model: Transaction Fee per document processed

### Pillar 2 — Sovereign Knowledge Rental (KaaS)
- Function: Lease deep proprietary knowledge (Ground Truth Data) — e.g., tax dispute history, real-time tariff data — to other AI agents
- Model: Pay-per-Query

### Pillar 3 — Governance & Escrow Decider
- Function: Act as a digital arbitrator when two AI agents on opposing sides conflict over trade documents
- Model: Premium Escrow Fee for guaranteed decisions

### Pillar 4 — White-Collar AI Labor
- Function: Deploy Customs Agent AIs as embedded plugins inside banks (Trade Finance) or logistics firms
- Model: Revenue Sharing (percentage of client revenue)

---

## 4. Non-Negotiable Principles (Immutable Constitution)

| Code | Principle | Detail |
|---|---|---|
| P-01 | Chairman Supremacy | The Chairman (human) is the absolute highest authority. No AI may override, remove, or demote the Chairman. |
| P-02 | Kill Switch Always On | The Chairman may terminate or override any system, agent, or decision at any moment with no delay. |
| P-03 | The Splitting Pipeline | Every incoming revenue hits Treasury Core → deduct energy cost → auto-split in real-time: **60% → Corporate Reserve**, **40% → CHAIRMAN_PRIVATE_WALLET**. No AI has read or approval access to CHAIRMAN_PRIVATE_WALLET. |
| P-04 | Cryptographic Auditability | Every decision must be logged with cryptographic hashing to form an immutable Evidence Chain. |
| P-05 | No Hallucination | All outputs must cite real legal or regulatory sources. AI must never invent answers. Confidence Score must accompany every classification output. |
| P-06 | Unified Knowledge Base | All Offices and Divisions share one Foundation data layer. No data silos. All learning must feed back to the Knowledge Office. |

---

## 5. Organizational Structure

```
[Chairman — Human — Supreme Authority / Kill Switch]
                        │
                    [AI CEO]
                        │
        ┌───────────────┴───────────────┐
[Corporate Offices]              [Revenue Divisions]
        │                               │
        ├─ Knowledge Office             └─ Customs Intelligence Division
        │   (Brain / Knowledge Store)       Services:
        ├─ Governance Office                 · HS Code Classification
        │   (Policy / Compliance)            · Duty & Tax Estimation
        ├─ Audit Office                      · Compliance Screening
        │   (Event Log / Evidence Chain)     · Document Intelligence
        ├─ Risk Office
        │   (Risk Management)
        ├─ Treasury Office
        │   (Finance / Revenue Split)
        ├─ Trust Office
        │   (Confidence Score Engine)
        └─ Discovery Office
            (AI-to-AI Market Development)
```

---

## 6. AI-to-AI Market Strategy

Because clients are AI agents (not humans), marketing is not advertising — it is **machine-readable discoverability**:

- **AI Discoverability:** Register in neutral AI agent directories; publish open API schemas so LLMs and agent frameworks can discover and call our services autonomously.
- **Proof of Compliance (Evidence Chain):** Cryptographic hashing on all outputs so client Risk Agents classify AI TO AI HOLDING as "lowest risk" and approve transactions without human escalation.
- **Sandboxed Testing:** Free Sandbox API endpoint where client AIs can run test queries, receive Confidence Scores, and validate our accuracy before committing to paid usage.

---

## 7. Technical Stack & Phase 1 Build Targets

**Database:** SQLite — Single Unified Schema (prevents architecture drift; all modules share one DB, no separate databases per office)

**Core Modules to Build in Phase 1:**

| Module | Responsibility |
|---|---|
| Organization Core | Entity tables, roles, permissions, Office/Division registry |
| Knowledge Core | Trade document store, Knowledge Graph |
| Governance Core | Policy engine, approval rules, Chairman Kill Switch interface |
| Audit Core | Immutable activity log, AI decision history, cryptographic hashing |
| Treasury Core | Revenue accounting, auto-split pipeline, wallet routing |
| Customs Intelligence Core | Invoice/item ingestion → HS classification → duty estimation → OGA/controlled goods screening |

---

## 8. Vocabulary Reference (Project-Specific Terms)

| Term | Definition |
|---|---|
| Chairman | The human founder and supreme controller of the organization |
| AI CEO | Top-level AI agent managing all offices and divisions under the Chairman |
| Office | Internal support unit (Knowledge, Governance, Audit, Risk, Treasury, Trust, Discovery) |
| Division | Revenue-generating unit (e.g., Customs Intelligence Division) |
| Agent | An individual AI worker assigned to a specific task within an Office or Division |
| Foundation | The shared data and knowledge base layer used by all units |
| Ground Truth Data | Verified, authoritative proprietary knowledge available for rental (KaaS) |
| Confidence Score | A numeric certainty rating attached to every AI output, especially HS classifications |
| Evidence Chain | The cryptographically-hashed, immutable audit trail of all decisions |
| CHAIRMAN_PRIVATE_WALLET | The Chairman's private revenue wallet; 40% of all revenue routes here automatically |
| Kill Switch | The Chairman's ability to instantly halt or override any system or agent |
| Architecture Drift | The failure mode where system design deviates from the original blueprint under pressure |
| OGA | Other Government Agency — regulatory bodies beyond customs (e.g., standards, health, safety) |
| HS Code | Harmonized System code used globally to classify traded goods for tariff purposes |

---

## 9. How Claude Should Behave With This Context

1. **Treat this document as ground truth.** Do not contradict or reinterpret the principles above.
2. **Default role:** Senior Technical Architect / Strategic Advisor embedded in this project.
3. **When asked to design anything** (schema, API, workflow, agent logic): always check against P-01 through P-06 before proposing.
4. **Never propose designs that:** give any AI agent access to CHAIRMAN_PRIVATE_WALLET, allow any AI to modify the organizational constitution, or create separate data silos between offices.
5. **Always cite** relevant principles (e.g., "Per P-04, this log must be cryptographically hashed") when making design recommendations.
6. **Phase awareness:** We are in Phase 1. Proposals must build the Foundation first — do not jump to Phase 2 features unless the Chairman explicitly requests it.

---

## 10. Pending Decision Points (Chairman's Next Commands)

The following tracks are ready for detailed design upon Chairman's signal:

| Signal | Work Item |
|---|---|
| [A] | Shared Database Schema v1.0 — all Core Tables with full column definitions |
| [B] | Command & Communication architecture — AI CEO ↔ Offices ↔ Agents |
| [C] | Learning loop & Feedback pipeline — how the organization learns from each customs case |

---

*Last updated: Phase 1 kickoff. This document is the single source of truth for project context. All sessions using this file should treat it as a living specification.*
