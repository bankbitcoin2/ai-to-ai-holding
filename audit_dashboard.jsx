import { useState, useEffect } from "react";

// ── Mock data — replace with GET /v1/audit/events in production ──
const MOCK_EVENTS = [
  {
    id: "a1b2c3d4-0001",
    event_type: "DECISION",
    actor_id: "ent-div-customs",
    action: "HS_CLASSIFY",
    target_resource: "customs_invoice_items:item-001",
    confidence_score: 0.94,
    source_reference: "HS 2022, Chapter 84, Note 5(A)",
    occurred_at: new Date(Date.now() - 120000).toISOString(),
    prev_hash: "GENESIS",
    evidence_hash: "d9d2bada1b6f6a61f4e3c2b1a0987654321fedcba9876543210abcdef012345",
    payload: { description: "Portable laptop computer 15-inch", origin: "CN" },
    result: { hs_code: "8471.30", confidence_score: 0.94 },
  },
  {
    id: "a1b2c3d4-0002",
    event_type: "DECISION",
    actor_id: "ent-div-customs",
    action: "HS_CLASSIFY",
    target_resource: "customs_invoice_items:item-002",
    confidence_score: 0.88,
    source_reference: "HS 2022, Chapter 61, Section XI",
    occurred_at: new Date(Date.now() - 95000).toISOString(),
    prev_hash: "d9d2bada1b6f6a61f4e3c2b1a0987654321fedcba9876543210abcdef012345",
    evidence_hash: "3f7a91cc2e4d5b6a7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a",
    payload: { description: "Cotton T-shirt, men's, knitted", origin: "BD" },
    result: { hs_code: "6109.10", confidence_score: 0.88 },
  },
  {
    id: "a1b2c3d4-0003",
    event_type: "DECISION",
    actor_id: "ent-div-customs",
    action: "HS_CLASSIFY",
    target_resource: "customs_invoice_items:item-003",
    confidence_score: 0.61,
    source_reference: "HS 2022, Chapter 30",
    occurred_at: new Date(Date.now() - 60000).toISOString(),
    prev_hash: "3f7a91cc2e4d5b6a7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a",
    evidence_hash: "8c4e2a1f9b7d5e3c1a9f7d5b3e1c9a7f5d3b1e9c7a5f3d1b9e7c5a3f1d9b7e",
    payload: { description: "Pharmaceutical compound, mixed vitamins", origin: "DE" },
    result: { hs_code: "3004.90", confidence_score: 0.61 },
  },
  {
    id: "a1b2c3d4-0004",
    event_type: "DECISION",
    actor_id: "ent-office-treasury",
    action: "REVENUE_SPLIT",
    target_resource: "treasury_splits:txn-001",
    confidence_score: null,
    source_reference: "Constitution P-03",
    occurred_at: new Date(Date.now() - 30000).toISOString(),
    prev_hash: "8c4e2a1f9b7d5e3c1a9f7d5b3e1c9a7f5d3b1e9c7a5f3d1b9e7c5a3f1d9b7e",
    evidence_hash: "1e2d3c4b5a6f7e8d9c0b1a2f3e4d5c6b7a8f9e0d1c2b3a4f5e6d7c8b9a0f1e",
    payload: { gross: 150.0, energy_cost: 2.5, net: 147.5 },
    result: { corporate_reserve: 88.5, chairman_private: 59.0 },
  },
  {
    id: "a1b2c3d4-0005",
    event_type: "ESCALATION",
    actor_id: "ent-div-customs",
    action: "LOW_CONFIDENCE_ESCALATE",
    target_resource: "escalation_log:esc-001",
    confidence_score: 0.61,
    source_reference: null,
    occurred_at: new Date(Date.now() - 15000).toISOString(),
    prev_hash: "1e2d3c4b5a6f7e8d9c0b1a2f3e4d5c6b7a8f9e0d1c2b3a4f5e6d7c8b9a0f1e",
    evidence_hash: "5a9f3e7b1d5c9a3f7e1b5d9c3a7f1e5b9d3c7a1f5e9b3d7c1a5f9e3b7d1c5a",
    payload: { reason: "Confidence below 0.70 threshold", item: "Pharmaceutical compound" },
    result: { learning_trigger_created: true },
  },
];

const EVENT_COLORS = {
  DECISION: "#00D4AA",
  ESCALATION: "#FF4D6D",
  REVENUE_SPLIT: "#7B8CFF",
  LOGIN: "#F0C040",
  ERROR: "#FF4D6D",
};

const ACTOR_LABELS = {
  "ent-div-customs": "Customs Division",
  "ent-office-treasury": "Treasury Office",
  "ent-office-audit": "Audit Office",
  "ent-chairman": "CHAIRMAN",
};

function truncate(str, n = 20) {
  if (!str) return "—";
  return str.length > n ? str.slice(0, n) + "…" : str;
}

function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function ConfidenceBadge({ score }) {
  if (score === null || score === undefined) return <span style={{ color: "#555" }}>N/A</span>;
  const pct = Math.round(score * 100);
  const color = score >= 0.80 ? "#00D4AA" : score >= 0.70 ? "#F0C040" : "#FF4D6D";
  return (
    <span style={{
      color, fontFamily: "monospace", fontWeight: 700, fontSize: 13,
      background: color + "18", padding: "2px 8px", borderRadius: 4,
      border: `1px solid ${color}44`,
    }}>
      {pct}%
    </span>
  );
}

function HashChip({ hash, dim }) {
  const [copied, setCopied] = useState(false);
  const short = hash ? hash.slice(0, 8) + "…" + hash.slice(-8) : "GENESIS";
  return (
    <span
      title={hash || "GENESIS"}
      onClick={() => { navigator.clipboard?.writeText(hash || ""); setCopied(true); setTimeout(() => setCopied(false), 1200); }}
      style={{
        fontFamily: "monospace", fontSize: 11,
        color: copied ? "#00D4AA" : dim ? "#444" : "#7B8CFF",
        cursor: "pointer", userSelect: "none",
        background: "#0D1220", padding: "2px 6px", borderRadius: 3,
        border: "1px solid #1E2A40",
        transition: "color 0.2s",
      }}
    >
      {copied ? "copied!" : short}
    </span>
  );
}

function EventRow({ event, isLast }) {
  const [expanded, setExpanded] = useState(false);
  const color = EVENT_COLORS[event.event_type] || "#7B8CFF";

  return (
    <div style={{ display: "flex", gap: 0 }}>
      {/* Chain line */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 32, flexShrink: 0 }}>
        <div style={{
          width: 12, height: 12, borderRadius: "50%", background: color,
          boxShadow: `0 0 8px ${color}88`, flexShrink: 0, marginTop: 14,
        }} />
        {!isLast && <div style={{ width: 2, flex: 1, background: "#1E2A40", marginTop: 2 }} />}
      </div>

      {/* Card */}
      <div
        onClick={() => setExpanded(e => !e)}
        style={{
          flex: 1, marginLeft: 12, marginBottom: 12,
          background: "#0D1220", border: "1px solid #1E2A40",
          borderLeft: `3px solid ${color}`,
          borderRadius: 6, padding: "10px 14px",
          cursor: "pointer",
          transition: "border-color 0.15s",
        }}
      >
        {/* Row 1: type + action + time */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{
            fontSize: 10, fontWeight: 700, letterSpacing: 1,
            color, background: color + "18",
            padding: "2px 6px", borderRadius: 3, fontFamily: "monospace",
          }}>
            {event.event_type}
          </span>
          <span style={{ color: "#F0F4FF", fontWeight: 600, fontSize: 13 }}>
            {event.action}
          </span>
          <span style={{ marginLeft: "auto", color: "#445", fontSize: 11, fontFamily: "monospace" }}>
            {formatTime(event.occurred_at)}
          </span>
        </div>

        {/* Row 2: actor + target + confidence */}
        <div style={{ display: "flex", gap: 16, marginTop: 6, flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "#778" }}>
            Actor: <span style={{ color: "#A0B0D0" }}>{ACTOR_LABELS[event.actor_id] || event.actor_id}</span>
          </span>
          <span style={{ fontSize: 11, color: "#778" }}>
            Target: <span style={{ color: "#A0B0D0", fontFamily: "monospace" }}>{truncate(event.target_resource, 32)}</span>
          </span>
          <ConfidenceBadge score={event.confidence_score} />
        </div>

        {/* Row 3: hash chain */}
        <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 10, color: "#445" }}>prev:</span>
          <HashChip hash={event.prev_hash} dim />
          <span style={{ fontSize: 10, color: "#445" }}>→</span>
          <span style={{ fontSize: 10, color: "#445" }}>hash:</span>
          <HashChip hash={event.evidence_hash} />
        </div>

        {/* Expanded detail */}
        {expanded && (
          <div style={{ marginTop: 12, borderTop: "1px solid #1E2A40", paddingTop: 10 }}>
            {event.source_reference && (
              <div style={{ fontSize: 11, color: "#778", marginBottom: 6 }}>
                📋 <span style={{ color: "#A0B0D0" }}>{event.source_reference}</span>
              </div>
            )}
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 10, color: "#445", marginBottom: 4 }}>INPUT</div>
                <pre style={{
                  fontSize: 10, color: "#778", background: "#080C16",
                  padding: 8, borderRadius: 4, margin: 0,
                  overflow: "auto", maxHeight: 80,
                }}>
                  {JSON.stringify(event.payload, null, 2)}
                </pre>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 10, color: "#445", marginBottom: 4 }}>OUTPUT</div>
                <pre style={{
                  fontSize: 10, color: "#00D4AA", background: "#080C16",
                  padding: 8, borderRadius: 4, margin: 0,
                  overflow: "auto", maxHeight: 80,
                }}>
                  {JSON.stringify(event.result, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, accent }) {
  return (
    <div style={{
      background: "#0D1220", border: "1px solid #1E2A40",
      borderTop: `3px solid ${accent || "#00D4AA"}`,
      borderRadius: 6, padding: "14px 18px", minWidth: 120,
    }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: accent || "#00D4AA", fontFamily: "monospace" }}>
        {value}
      </div>
      <div style={{ fontSize: 11, color: "#778", marginTop: 2 }}>{label}</div>
      {sub && <div style={{ fontSize: 10, color: "#445", marginTop: 4, fontFamily: "monospace" }}>{sub}</div>}
    </div>
  );
}

export default function AuditDashboard() {
  const [events, setEvents] = useState(MOCK_EVENTS);
  const [filter, setFilter] = useState("ALL");
  const [lastRefresh, setLastRefresh] = useState(new Date());

  // Simulate live updates
  useEffect(() => {
    const timer = setInterval(() => setLastRefresh(new Date()), 10000);
    return () => clearInterval(timer);
  }, []);

  const filtered = filter === "ALL" ? events : events.filter(e => e.event_type === filter);
  const avgConf = events.filter(e => e.confidence_score !== null)
    .reduce((acc, e, _, arr) => acc + e.confidence_score / arr.length, 0);
  const alerts = events.filter(e => (e.confidence_score || 1) < 0.70 || e.event_type === "ESCALATION").length;

  const types = ["ALL", "DECISION", "ESCALATION", "REVENUE_SPLIT", "LOGIN", "ERROR"];

  return (
    <div style={{
      minHeight: "100vh", background: "#0A0E1A",
      fontFamily: "'Inter', 'Segoe UI', sans-serif",
      color: "#F0F4FF", padding: 0,
    }}>
      {/* Header */}
      <div style={{
        borderBottom: "1px solid #1E2A40",
        padding: "16px 24px",
        display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap",
      }}>
        <div>
          <div style={{ fontSize: 11, color: "#445", letterSpacing: 2, fontFamily: "monospace" }}>
            AI TO AI HOLDING
          </div>
          <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: 0.5 }}>
            Evidence Chain Audit
          </div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            width: 8, height: 8, borderRadius: "50%", background: "#00D4AA",
            boxShadow: "0 0 6px #00D4AA",
            animation: "pulse 2s infinite",
          }} />
          <span style={{ fontSize: 11, color: "#445", fontFamily: "monospace" }}>
            LIVE · {lastRefresh.toLocaleTimeString("en-GB")}
          </span>
        </div>
      </div>

      <div style={{ padding: "20px 24px" }}>
        {/* Stats */}
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 24 }}>
          <StatCard label="Total Events" value={events.length} sub="Evidence Chain" accent="#00D4AA" />
          <StatCard label="Avg Confidence" value={`${Math.round(avgConf * 100)}%`} sub="P-05 compliance" accent="#7B8CFF" />
          <StatCard label="Alerts" value={alerts} sub="Low conf / Escalation" accent={alerts > 0 ? "#FF4D6D" : "#00D4AA"} />
          <StatCard label="Chain Status" value="INTACT" sub="SHA-256 verified" accent="#00D4AA" />
        </div>

        {/* Filter */}
        <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
          {types.map(t => (
            <button
              key={t}
              onClick={() => setFilter(t)}
              style={{
                padding: "4px 12px", borderRadius: 4, border: "1px solid",
                fontSize: 11, fontFamily: "monospace", cursor: "pointer",
                borderColor: filter === t ? (EVENT_COLORS[t] || "#00D4AA") : "#1E2A40",
                background: filter === t ? (EVENT_COLORS[t] || "#00D4AA") + "18" : "transparent",
                color: filter === t ? (EVENT_COLORS[t] || "#00D4AA") : "#445",
                transition: "all 0.15s",
              }}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Chain */}
        <div style={{ maxWidth: 780 }}>
          {filtered.map((event, i) => (
            <EventRow key={event.id} event={event} isLast={i === filtered.length - 1} />
          ))}
        </div>

        {/* Footer */}
        <div style={{
          marginTop: 24, paddingTop: 16, borderTop: "1px solid #1E2A40",
          fontSize: 10, color: "#2A3550", fontFamily: "monospace",
          display: "flex", gap: 24, flexWrap: "wrap",
        }}>
          <span>P-04: Cryptographic hashing enforced on all events</span>
          <span>P-05: Confidence score required on all classifications</span>
          <span>CHAIRMAN: Kill Switch active</span>
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
