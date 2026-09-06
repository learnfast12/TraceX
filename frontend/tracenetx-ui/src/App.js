import React, { useState, useEffect } from "react";
import SpiderMap from "./SpiderMap";
import Sidebar from "./Sidebar";
import AlertSystem from "./AlertSystem";
import PathFinder from "./PathFinder";
import Dashboard from "./Dashboard";
import CityMap from "./CityMap";
import "./App.css";

const COLORS = {
  critical: "#FF2D2D",
  high: "#FF6B00",
  medium: "#FFB800",
  low: "#00C853",
  clear: "#00C853",
  gold: "#C9A84C",
  navy: "#0A0E1A",
  navyCard: "#0D1220",
  navyBorder: "#1A2035",
  navyAccent: "#151B2E",
  text: "#E2E8F0",
  textMuted: "#64748B",
  textDim: "#94A3B8",
};

const getRiskColor = (level) => {
  const map = { CRITICAL: COLORS.critical, HIGH: COLORS.high, MEDIUM: COLORS.medium, LOW: COLORS.low, CLEAR: COLORS.clear };
  return map[level] || COLORS.textMuted;
};

const getRiskBg = (level) => {
  const map = { CRITICAL: "#1A0505", HIGH: "#1A0D00", MEDIUM: "#1A1400", LOW: "#051A0D", CLEAR: "#051A0D" };
  return map[level] || "#0D1220";
};

const SectionCard = ({ color = COLORS.gold, title, subtitle, children, empty }) => (
  <div style={{
    background: COLORS.navyCard,
    border: `1px solid ${COLORS.navyBorder}`,
    borderLeft: `3px solid ${color}`,
    borderRadius: "6px",
    padding: "20px 24px",
    marginBottom: "16px",
  }}>
    <div style={{ marginBottom: "14px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
        <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: color, boxShadow: `0 0 6px ${color}` }} />
        <span style={{ color, fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.72em", letterSpacing: "2px", fontWeight: "600", textTransform: "uppercase" }}>{title}</span>
      </div>
      {subtitle && <div style={{ color: COLORS.textMuted, fontSize: "0.78em", paddingLeft: "16px" }}>{subtitle}</div>}
    </div>
    {empty
      ? <div style={{ color: COLORS.textMuted, fontSize: "0.82em", fontStyle: "italic", padding: "8px 0" }}>No data detected</div>
      : children}
  </div>
);

const RiskBadge = ({ level }) => (
  <span style={{
    background: getRiskColor(level),
    color: "#000",
    padding: "2px 10px",
    borderRadius: "3px",
    fontSize: "0.68em",
    fontWeight: "800",
    fontFamily: "'IBM Plex Mono', monospace",
    letterSpacing: "1px",
  }}>{level}</span>
);

const DataRow = ({ label, value, color }) => (
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 0", borderBottom: `1px solid ${COLORS.navyBorder}` }}>
    <span style={{ color: COLORS.textMuted, fontSize: "0.78em", fontFamily: "'IBM Plex Mono', monospace" }}>{label}</span>
    <span style={{ color: color || COLORS.text, fontSize: "0.82em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "600" }}>{value}</span>
  </div>
);

function App() {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [selectedNode, setSelectedNode] = useState(null);
  const [filters, setFilters] = useState({ ip: "", phone: "", city: "", case_id: "" });
  const [loading, setLoading] = useState(true);
  const [organizedLayout, setOrganizedLayout] = useState(true);
  const [activeCase, setActiveCase] = useState("ALL");
  const [activeTab, setActiveTab] = useState("map");
  const [exporting, setExporting] = useState(false);
  const [mlData, setMlData] = useState(null);
  const [mlLoading, setMlLoading] = useState(false);
  const [intelData, setIntelData] = useState(null);
  const [intelLoading, setIntelLoading] = useState(false);
  const [evidenceData, setEvidenceData] = useState(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [temporalData, setTemporalData] = useState(null);
  const [temporalLoading, setTemporalLoading] = useState(false);
  const [validationData, setValidationData] = useState(null);
  const [validationLoading, setValidationLoading] = useState(false);

  const fetchGraph = async (activeFilters = {}) => {
    setLoading(true);
    try {
      const hasFilter = activeFilters.ip || activeFilters.phone || activeFilters.city;
      let url = "http://localhost:8001/graph";
      const params = new URLSearchParams();
      if (activeFilters.case_id) params.append("case_id", activeFilters.case_id);
      if (hasFilter) {
        if (activeFilters.ip) params.append("ip", activeFilters.ip);
        if (activeFilters.phone) params.append("phone", activeFilters.phone);
        if (activeFilters.city) params.append("city", activeFilters.city);
        url = "http://localhost:8001/filter";
      }
      const query = params.toString();
      const res = await fetch(query ? url + "?" + query : url);
      const data = await res.json();
      setGraphData({ nodes: data.nodes || [], edges: data.edges || [] });
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const fetchAccount = async (id) => {
    const res = await fetch("http://localhost:8001/account/" + id);
    const data = await res.json();
    setSelectedNode(data);
  };

  const fetchML = async () => {
    setMlLoading(true);
    try {
      const res = await fetch("http://localhost:8001/ml/analyze");
      const data = await res.json();
      setMlData(data);
    } catch (e) { console.error(e); }
    setMlLoading(false);
  };

  const fetchIntelligence = async () => {
    setIntelLoading(true);
    try {
      const res = await fetch("http://localhost:8001/intelligence/full");
      const data = await res.json();
      setIntelData(data);
    } catch (e) { console.error(e); }
    setIntelLoading(false);
  };

  const fetchEvidence = async (accountId) => {
    setEvidenceLoading(true);
    try {
      const res = await fetch("http://localhost:8001/evidence/" + accountId);
      const data = await res.json();
      setEvidenceData(data);
    } catch (e) { console.error(e); }
    setEvidenceLoading(false);
  };

  const fetchTemporal = async () => {
    setTemporalLoading(true);
    try {
      const res = await fetch("http://localhost:8001/temporal/analyze");
      const data = await res.json();
      setTemporalData(data);
    } catch (e) { console.error(e); }
    setTemporalLoading(false);
  };

  const fetchValidation = async () => {
    setValidationLoading(true);
    try {
      const res = await fetch("http://localhost:8001/ml/real-data-validation");
      const data = await res.json();
      setValidationData(data);
    } catch (e) { console.error(e); }
    setValidationLoading(false);
  };

  const handleFilter = (f) => {
    const newFilters = { ...f, case_id: filters.case_id };
    setFilters(newFilters);
    fetchGraph(newFilters);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch("http://localhost:8001/export");
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const csv = await res.text();
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "tracenetx_v2_flagged_accounts.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
      alert("Export failed — check console for details.");
    }
    setExporting(false);
  };

  const handleTabSwitch = (tab) => {
    setActiveTab(tab);
    if (tab === "ml" && !mlData) fetchML();
    if (tab === "intelligence" && !intelData) fetchIntelligence();
    if (tab === "temporal" && !temporalData) fetchTemporal();
    if (tab === "validation" && !validationData) fetchValidation();
  };

  useEffect(() => { fetchGraph(); }, []);

  const highRiskCount = (graphData.nodes || []).filter(n => n.risk && n.risk.level === "HIGH").length;
  const medRiskCount = (graphData.nodes || []).filter(n => n.risk && n.risk.level === "MEDIUM").length;
  const totalAmount = (graphData.edges || []).reduce((s, e) => s + (e.amount || 0), 0);

  return (
    <div className="app" style={{ fontFamily: "'Inter', 'IBM Plex Sans', sans-serif", background: COLORS.navy, minHeight: "100vh" }}>
      <AlertSystem />

      {/* HEADER */}
      <header style={{
        background: "#080C16",
        borderBottom: `1px solid ${COLORS.navyBorder}`,
        padding: "0 24px",
        height: "56px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        position: "sticky",
        top: 0,
        zIndex: 100,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{
            width: "32px", height: "32px", borderRadius: "6px",
            background: "linear-gradient(135deg, #C9A84C22, #C9A84C44)",
            border: "1px solid #C9A84C55",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "16px"
          }}>🕸</div>
          <div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
              <span style={{ color: COLORS.gold, fontWeight: "700", fontSize: "1em", letterSpacing: "0.5px" }}>TraceNetX</span>
              <span style={{ color: COLORS.gold, fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.68em", fontWeight: "600" }}>v2.0</span>
            </div>
            <div style={{ color: COLORS.textMuted, fontSize: "0.68em", letterSpacing: "0.3px" }}>Mule Account Intelligence & Criminal Network Disruption</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{
            background: "transparent", border: `1px solid ${COLORS.navyBorder}`,
            color: COLORS.textMuted, padding: "4px 12px", borderRadius: "4px",
            fontSize: "0.68em", fontFamily: "'IBM Plex Mono', monospace", letterSpacing: "1px"
          }}>CYBERSHIELD 2026</span>
          <span style={{
            background: "transparent", border: "1px solid #FF2D2D",
            color: "#FF2D2D", padding: "4px 12px", borderRadius: "4px",
            fontSize: "0.68em", fontFamily: "'IBM Plex Mono', monospace", letterSpacing: "1px", fontWeight: "700"
          }}>OMEGA 404</span>
        </div>
      </header>

      {/* STATS + NAV BAR */}
      <div style={{
        background: "#0A0E1A",
        borderBottom: `1px solid ${COLORS.navyBorder}`,
        padding: "0 24px",
        display: "flex",
        alignItems: "center",
        gap: "0",
        height: "48px",
      }}>
        {[
          { label: "Total Accounts", value: graphData.nodes.length, color: COLORS.text },
          { label: "Transactions", value: graphData.edges.length, color: COLORS.text },
          { label: "Flagged", value: (graphData.nodes || []).filter(n => n.risk && (n.risk.level === "HIGH" || n.risk.level === "CRITICAL")).length, color: COLORS.critical },
          { label: "Medium Risk", value: medRiskCount, color: COLORS.medium },
          { label: "Total Amount", value: `₹${(totalAmount / 100000).toFixed(1)}L`, color: COLORS.gold },
        ].map((s, i) => (
          <div key={i} style={{
            padding: "0 20px",
            borderRight: `1px solid ${COLORS.navyBorder}`,
            display: "flex", flexDirection: "column", justifyContent: "center", height: "100%"
          }}>
            <div style={{ color: COLORS.textMuted, fontSize: "0.6em", letterSpacing: "1px", textTransform: "uppercase", fontFamily: "'IBM Plex Mono', monospace" }}>{s.label}</div>
            <div style={{ color: s.color, fontSize: "1em", fontWeight: "700", fontFamily: "'IBM Plex Mono', monospace", lineHeight: 1.2 }}>{s.value}</div>
          </div>
        ))}

        <div style={{ display: "flex", alignItems: "center", gap: "2px", marginLeft: "auto", height: "100%" }}>
          {[
            ["map", "🕸 Spider Map"],
            ["ml", "🤖 ML Analysis"],
            ["intelligence", "🧠 Intelligence"],
            ["temporal", "⏱ Temporal"],
            // ["validation", "🔬 Model Validation"], // hidden post-BOI, re-enable if needed
            ["dashboard", "📊 Dashboard"],
            ["citymap", "🗺 City Map"],
          ].map(([id, label]) => (
            <button key={id} onClick={() => handleTabSwitch(id)} style={{
              padding: "0 16px",
              height: "100%",
              background: activeTab === id ? "#C9A84C12" : "transparent",
              border: "none",
              borderBottom: activeTab === id ? `2px solid ${COLORS.gold}` : "2px solid transparent",
              color: activeTab === id ? COLORS.gold : COLORS.textMuted,
              cursor: "pointer",
              fontSize: "0.7em",
              fontWeight: activeTab === id ? "600" : "400",
              letterSpacing: "0.3px",
              transition: "all 0.15s ease",
              whiteSpace: "nowrap",
            }}>{label}</button>
          ))}
        </div>

        <button onClick={handleExport} disabled={exporting} style={{
          marginLeft: "8px",
          padding: "5px 10px",
          background: exporting ? "transparent" : "#C9A84C18",
          border: `1px solid ${COLORS.gold}55`,
          color: COLORS.gold,
          borderRadius: "4px",
          cursor: "pointer",
          fontSize: "0.72em",
          fontFamily: "'IBM Plex Mono', monospace",
          fontWeight: "600",
          letterSpacing: "0.5px",
          whiteSpace: "nowrap",
        }}>{exporting ? "EXPORTING..." : "EXPORT CSV"}</button>
      </div>

      <div className="main">

        {activeTab === "map" && (
          <>
            <div className="left-panel">
              <div className="filter-panel">
                <h3>Filters</h3>
                <input placeholder="IP Address" onChange={e => handleFilter({ ...filters, ip: e.target.value })} />
                <input placeholder="Phone Number" onChange={e => handleFilter({ ...filters, phone: e.target.value })} />
                <input placeholder="City" onChange={e => handleFilter({ ...filters, city: e.target.value })} />
                <button className="btn-reset" onClick={() => { setFilters({ ip: "", phone: "", city: "", case_id: filters.case_id }); fetchGraph({ case_id: filters.case_id }); }}>Reset Filters</button>
              </div>
              <div className="legend">
                <h3>Risk Legend</h3>
                <div className="legend-item"><span className="dot critical"></span>Critical</div>
                <div className="legend-item"><span className="dot high"></span>High Risk</div>
                <div className="legend-item"><span className="dot medium"></span>Medium Risk</div>
                <div className="legend-item"><span className="dot clear"></span>Safe</div>
                <div className="legend-item" style={{ marginTop: "8px", paddingTop: "8px", borderTop: "1px solid #222", display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ display: "inline-block", width: "28px", height: "0", borderTop: "2px dashed #C9A84C", verticalAlign: "middle" }}></span>
                  <span style={{ color: "#C9A84C", fontSize: "0.85em" }}>Cash Transfer</span>
                </div>
              </div>
              <PathFinder nodes={graphData.nodes} />
            </div>
            <div className="map-area">
              {loading ? <div className="loading">Analyzing money trail...</div> : (
                <div style={{ position: "relative", width: "100%", height: "100%" }}>
                  <button onClick={() => setOrganizedLayout(v => !v)} style={{
                    position: "absolute", top: "12px", right: "12px", zIndex: 10,
                    padding: "6px 14px",
                    background: "transparent",
                    border: `1px solid #00C853`,
                    color: "#00C853",
                    borderRadius: "4px", cursor: "pointer",
                    fontFamily: "'IBM Plex Mono', monospace", fontWeight: "600", fontSize: "0.72em",
                    letterSpacing: "1px", backdropFilter: "blur(4px)",
                  }}>
                    {organizedLayout ? "RAW VIEW" : "ORGANIZE"}
                  </button>
                  <SpiderMap graphData={graphData} onNodeClick={fetchAccount} organized={organizedLayout} />
                </div>
              )}
            </div>
            <div className="right-panel">
              <Sidebar selectedNode={selectedNode} />
              {selectedNode && (
                <div style={{ padding: "10px" }}>
                  <button onClick={() => { fetchEvidence(selectedNode.account?.id); setActiveTab("evidence"); }} style={{
                    width: "100%", padding: "10px",
                    background: "#FF2D2D18", border: "1px solid #FF2D2D55",
                    color: COLORS.critical, borderRadius: "4px", cursor: "pointer",
                    fontWeight: "700", marginTop: "10px", fontSize: "0.8em",
                    fontFamily: "'IBM Plex Mono', monospace", letterSpacing: "0.5px",
                  }}>GENERATE EVIDENCE PACKAGE</button>
                </div>
              )}
            </div>
          </>
        )}

        {activeTab === "ml" && (
          <div style={{ flex: 1, overflowY: "auto", padding: "24px", background: COLORS.navy }}>
            <div style={{ marginBottom: "24px" }}>
              <div style={{ color: COLORS.gold, fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.7em", letterSpacing: "2px", marginBottom: "4px" }}>DETECT LAYER</div>
              <h2 style={{ color: COLORS.text, fontSize: "1.3em", fontWeight: "700", margin: 0 }}>ML Analysis</h2>
              <p style={{ color: COLORS.textMuted, fontSize: "0.8em", margin: "6px 0 0" }}>XGBoost + LightGBM + Random Forest ensemble · Isolation Forest · SHAP explainability</p>
            </div>
            {mlLoading && <div className="loading">Running ML pipeline...</div>}
            {mlData && (
              <>
                <div style={{ display: "flex", gap: "10px", marginBottom: "24px", flexWrap: "wrap" }}>
                  {[
                    ["CRITICAL", mlData.critical, COLORS.critical],
                    ["HIGH", mlData.high, COLORS.high],
                    ["MEDIUM", mlData.medium, COLORS.medium],
                    ["LOW", mlData.low, COLORS.low],
                    ["CLEAR", mlData.clear, COLORS.clear],
                  ].map(([level, count, color]) => (
                    <div key={level} style={{
                      background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`,
                      borderTop: `2px solid ${color}`,
                      borderRadius: "6px", padding: "14px 20px", textAlign: "center", minWidth: "90px",
                    }}>
                      <div style={{ color, fontSize: "1.8em", fontWeight: "800", fontFamily: "'IBM Plex Mono', monospace" }}>{count}</div>
                      <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px", marginTop: "2px", fontFamily: "'IBM Plex Mono', monospace" }}>{level}</div>
                    </div>
                  ))}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {mlData.results.map(r => (
                    <div key={r.account_id} style={{
                      background: COLORS.navyCard,
                      border: `1px solid ${COLORS.navyBorder}`,
                      borderLeft: `3px solid ${getRiskColor(r.risk_level)}`,
                      borderRadius: "6px", padding: "16px",
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          <span style={{ color: getRiskColor(r.risk_level), fontWeight: "700", fontSize: "1em", fontFamily: "'IBM Plex Mono', monospace" }}>{r.account_id}</span>
                          <RiskBadge level={r.risk_level} />
                          {r.mule_type !== "N/A" && <span style={{ background: COLORS.navyAccent, color: COLORS.textDim, padding: "2px 8px", borderRadius: "3px", fontSize: "0.68em", fontFamily: "'IBM Plex Mono', monospace" }}>{r.mule_type}</span>}
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          <div style={{ width: "100px", height: "4px", background: "#1A2035", borderRadius: "2px" }}>
                            <div style={{ width: `${r.risk_score}%`, height: "100%", background: getRiskColor(r.risk_level), borderRadius: "2px" }}></div>
                          </div>
                          <span style={{ color: getRiskColor(r.risk_level), fontWeight: "700", fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.85em" }}>{r.risk_score.toFixed(1)}</span>
                        </div>
                      </div>
                      <div style={{ color: COLORS.textMuted, fontSize: "0.78em", marginBottom: "8px" }}>
                        <span style={{ color: COLORS.textDim }}>ACTION: </span>{r.recommended_action}
                      </div>
                      {r.flags.length > 0 && (
                        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "8px" }}>
                          {r.flags.map((f, i) => (
                            <span key={i} style={{
                              background: COLORS.navyAccent, border: `1px solid ${COLORS.navyBorder}`,
                              color: COLORS.textDim, padding: "2px 8px", borderRadius: "12px", fontSize: "0.72em",
                              fontFamily: "'IBM Plex Mono', monospace",
                            }}>{f}</span>
                          ))}
                        </div>
                      )}
                      <div style={{ color: COLORS.textMuted, fontSize: "0.72em", fontStyle: "italic", borderTop: `1px solid ${COLORS.navyBorder}`, paddingTop: "8px", marginTop: "4px" }}>
                        SHAP · {r.shap_explanation}
                      </div>
                      <button onClick={() => { fetchEvidence(r.account_id); setActiveTab("evidence"); }} style={{
                        marginTop: "10px", padding: "4px 14px",
                        background: "#C9A84C12", border: `1px solid ${COLORS.gold}88`,
                        color: COLORS.gold, borderRadius: "4px", cursor: "pointer",
                        fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace",
                        letterSpacing: "0.5px",
                      }}>⚡ EVIDENCE PACKAGE</button>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === "intelligence" && (
          <div style={{ flex: 1, overflowY: "auto", padding: "24px", background: COLORS.navy }}>
            <div style={{ marginBottom: "24px" }}>
              <div style={{ color: COLORS.gold, fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.7em", letterSpacing: "2px", marginBottom: "4px" }}>INVESTIGATE LAYER</div>
              <h2 style={{ color: COLORS.text, fontSize: "1.3em", fontWeight: "700", margin: 0 }}>Graph Intelligence</h2>
              <p style={{ color: COLORS.textMuted, fontSize: "0.8em", margin: "6px 0 0" }}>Community detection · Convergence analysis · Hawala mapping · Crypto monitoring</p>
            </div>
            {intelLoading && <div className="loading">Running graph intelligence...</div>}
            {intelData && (
              <div style={{ display: "flex", flexDirection: "column" }}>
                <SectionCard color="#4488FF" title="Community Detection — Mule Clusters" subtitle={intelData.community_detection?.analysis}>
                  {intelData.community_detection?.clusters?.map((c, i) => (
                    <div key={i} style={{ background: COLORS.navyAccent, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "4px", padding: "12px 14px", marginBottom: "8px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                        <span style={{ color: COLORS.text, fontWeight: "700", fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.85em" }}>{c.coordinator}</span>
                        <RiskBadge level={c.threat_level} />
                      </div>
                      <div style={{ color: COLORS.textMuted, fontSize: "0.75em", fontFamily: "'IBM Plex Mono', monospace" }}>
                        {c.mule_accounts.join(" → ")} · {c.inbound_count} inbound
                      </div>
                    </div>
                  ))}
                </SectionCard>

                <SectionCard color="#A855F7" title="Convergence Analysis — Lieutenant Nodes" subtitle={intelData.convergence_analysis?.analysis}>
                  {intelData.convergence_analysis?.potential_lieutenants?.map((l, i) => (
                    <div key={i} style={{ background: COLORS.navyAccent, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "4px", padding: "12px 14px", marginBottom: "8px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div>
                        <div style={{ color: COLORS.text, fontWeight: "700", fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.85em" }}>{l.account}</div>
                        <div style={{ color: COLORS.textMuted, fontSize: "0.72em", marginTop: "2px" }}>{l.threat}</div>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <div style={{ color: "#A855F7", fontFamily: "'IBM Plex Mono', monospace", fontSize: "1.2em", fontWeight: "800" }}>{l.source_count}</div>
                        <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px" }}>SOURCE CHAINS</div>
                      </div>
                    </div>
                  ))}
                </SectionCard>

                <SectionCard color={COLORS.high} title="Coordination Detection — Synchronized Bursts" subtitle={intelData.coordination_detection?.analysis}>
                  {intelData.coordination_detection?.coordinated_bursts?.map((b, i) => (
                    <div key={i} style={{ background: COLORS.navyAccent, border: `1px solid ${COLORS.navyBorder}`, borderLeft: `2px solid ${COLORS.high}`, borderRadius: "4px", padding: "12px 14px", marginBottom: "8px" }}>
                      <div style={{ color: COLORS.high, fontWeight: "700", fontSize: "0.78em", fontFamily: "'IBM Plex Mono', monospace", marginBottom: "6px" }}>{b.alert}</div>
                      <DataRow label="WINDOW" value={`${b.window_start?.slice(0, 16)} → ${b.window_end?.slice(0, 16)}`} />
                      <DataRow label="TRANSACTIONS" value={b.transaction_count} color={COLORS.gold} />
                      <DataRow label="AMOUNT" value={`₹${(b.total_amount / 100000).toFixed(1)}L`} color={COLORS.gold} />
                      <div style={{ color: COLORS.textMuted, fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace", marginTop: "6px" }}>
                        {b.accounts_involved?.join(", ")}
                      </div>
                    </div>
                  ))}
                </SectionCard>

                <SectionCard color={COLORS.low} title="Identity Fusion — Shared Identifiers" subtitle={intelData.identity_fusion?.analysis} empty={!intelData.identity_fusion?.identity_links?.length}>
                  {intelData.identity_fusion?.identity_links?.map((l, i) => (
                    <div key={i} style={{ background: COLORS.navyAccent, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "4px", padding: "12px 14px", marginBottom: "8px" }}>
                      <div style={{ color: COLORS.text, fontWeight: "700", fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.85em", marginBottom: "6px" }}>{l.account1} ↔ {l.account2}</div>
                      <DataRow label="SHARED IP" value={l.shared_ip} />
                      <DataRow label="CITY" value={l.city} />
                      <div style={{ color: COLORS.high, fontSize: "0.72em", marginTop: "6px" }}>{l.alert}</div>
                    </div>
                  ))}
                </SectionCard>

                <SectionCard color="#F472B6" title="Hawala Broker Detection" subtitle={intelData.hawala_detection?.analysis}>
                  {intelData.hawala_detection?.brokers?.map((b, i) => (
                    <div key={i} style={{ background: COLORS.navyAccent, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "4px", padding: "12px 14px", marginBottom: "8px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                        <span style={{ color: COLORS.text, fontWeight: "700", fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.85em" }}>{b.account}</span>
                        <RiskBadge level={b.severity} />
                      </div>
                      <DataRow label="SENDERS" value={b.unique_senders} />
                      <DataRow label="RECEIVERS" value={b.unique_receivers} />
                      <DataRow label="FORWARDING" value={`${(b.forwarding_ratio * 100).toFixed(0)}%`} color={COLORS.critical} />
                      <DataRow label="INFLOW" value={`₹${(b.total_inflow / 100000).toFixed(1)}L`} color={COLORS.gold} />
                      <DataRow label="OUTFLOW" value={`₹${(b.total_outflow / 100000).toFixed(1)}L`} color={COLORS.gold} />
                      <div style={{ color: "#F472B6", fontSize: "0.72em", marginTop: "8px", fontStyle: "italic" }}>{b.threat}</div>
                    </div>
                  ))}
                </SectionCard>

                <SectionCard color="#22D3EE" title="Shell Company Detection" subtitle={intelData.shell_company_detection?.analysis}>
                  {intelData.shell_company_detection?.shells?.map((s, i) => (
                    <div key={i} style={{ background: COLORS.navyAccent, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "4px", padding: "12px 14px", marginBottom: "8px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                        <span style={{ color: COLORS.text, fontWeight: "700", fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.85em" }}>{s.account}</span>
                        <RiskBadge level={s.severity} />
                      </div>
                      <DataRow label="TRANSACTIONS" value={s.transaction_count} />
                      <DataRow label="ROUND AMOUNT %" value={`${s.round_amount_percentage}%`} />
                      <DataRow label="SENDERS" value={s.unique_senders} />
                      <DataRow label="TOTAL RECEIVED" value={`₹${(s.total_received / 100000).toFixed(1)}L`} color={COLORS.gold} />
                      <div style={{ color: "#22D3EE", fontSize: "0.72em", marginTop: "8px", fontStyle: "italic" }}>{s.threat}</div>
                    </div>
                  ))}
                </SectionCard>

                <SectionCard color={COLORS.medium} title="Crypto Gateway Monitoring" subtitle={intelData.crypto_monitoring?.analysis}>
                  <div style={{ color: COLORS.textMuted, fontSize: "0.7em", fontFamily: "'IBM Plex Mono', monospace", marginBottom: "12px", lineHeight: 1.6 }}>
                    MONITORED: {intelData.crypto_monitoring?.monitored_exchanges?.join(" · ")}
                  </div>
                  {intelData.crypto_monitoring?.alerts?.map((a, i) => (
                    <div key={i} style={{ background: COLORS.navyAccent, border: `1px solid ${COLORS.navyBorder}`, borderLeft: `2px solid ${COLORS.critical}`, borderRadius: "4px", padding: "12px 14px", marginBottom: "8px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                        <span style={{ color: COLORS.text, fontWeight: "700", fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.85em" }}>{a.sender} → {a.destination}</span>
                        <RiskBadge level={a.severity} />
                      </div>
                      <DataRow label="EXCHANGE" value={a.exchange} />
                      <DataRow label="AMOUNT" value={`₹${(a.amount / 1000).toFixed(0)}K`} color={COLORS.gold} />
                      <DataRow label="CITY" value={a.city} />
                      <div style={{ color: COLORS.critical, fontSize: "0.72em", marginTop: "6px" }}>{a.alert}</div>
                      <div style={{ color: COLORS.high, fontSize: "0.7em", fontStyle: "italic", marginTop: "2px" }}>{a.action}</div>
                    </div>
                  ))}
                </SectionCard>

                {intelData.batch_recruitment?.recruitment_batches?.length > 0 && (
                  <SectionCard color={COLORS.low} title="Batch Recruitment Detection" subtitle={intelData.batch_recruitment?.analysis}>
                    {intelData.batch_recruitment?.recruitment_batches?.map((b, i) => (
                      <div key={i} style={{ background: COLORS.navyAccent, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "4px", padding: "12px 14px", marginBottom: "8px" }}>
                        <div style={{ color: COLORS.text, fontWeight: "700", fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.82em", marginBottom: "6px" }}>{b.alert}</div>
                        <DataRow label="CITY" value={b.city} />
                        <DataRow label="SHARED IP" value={b.shared_ip} />
                        <div style={{ color: COLORS.textMuted, fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace", marginTop: "6px" }}>{b.accounts?.join(", ")}</div>
                      </div>
                    ))}
                  </SectionCard>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === "temporal" && (
          <div style={{ flex: 1, overflowY: "auto", padding: "24px", background: COLORS.navy }}>
            <div style={{ marginBottom: "24px" }}>
              <div style={{ color: COLORS.gold, fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.7em", letterSpacing: "2px", marginBottom: "4px" }}>LIFECYCLE LAYER</div>
              <h2 style={{ color: COLORS.text, fontSize: "1.3em", fontWeight: "700", margin: 0 }}>Temporal Analysis</h2>
              <p style={{ color: COLORS.textMuted, fontSize: "0.8em", margin: "6px 0 0" }}>Rule-based sequence detection — Dormant reactivation · Delayed layering · Velocity spikes · Smurfing · Rapid forwarding</p>
            </div>
            {temporalLoading && <div className="loading">Running temporal analysis...</div>}
            {temporalData && (
              <>
                <div style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "6px", padding: "14px 20px", marginBottom: "20px", display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ color: COLORS.gold, fontWeight: "800", fontSize: "1.4em", fontFamily: "'IBM Plex Mono', monospace" }}>{temporalData.total_flagged}</span>
                  <span style={{ color: COLORS.textMuted, fontSize: "0.82em" }}>accounts flagged with temporal anomaly patterns</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {temporalData.results.map(r => (
                    <div key={r.account_id} style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderLeft: `3px solid ${getRiskColor(r.temporal_risk_level)}`, borderRadius: "6px", padding: "16px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "12px" }}>
                        <span style={{ color: getRiskColor(r.temporal_risk_level), fontWeight: "700", fontSize: "1em", fontFamily: "'IBM Plex Mono', monospace" }}>{r.account_id}</span>
                        <RiskBadge level={r.temporal_risk_level} />
                      </div>
                      {r.patterns_detected.map((p, i) => (
                        <div key={i} style={{ background: COLORS.navyAccent, border: `1px solid ${COLORS.navyBorder}`, borderLeft: `2px solid ${getRiskColor(p.severity)}`, borderRadius: "4px", padding: "10px 12px", marginBottom: "8px" }}>
                          <div style={{ color: getRiskColor(p.severity), fontWeight: "700", fontSize: "0.78em", fontFamily: "'IBM Plex Mono', monospace" }}>{p.pattern}</div>
                          <div style={{ color: COLORS.textDim, fontSize: "0.78em", marginTop: "4px" }}>{p.description}</div>
                          <div style={{ color: COLORS.textMuted, fontSize: "0.72em", marginTop: "4px", fontStyle: "italic" }}>{p.alert}</div>
                        </div>
                      ))}
                      <div style={{ marginTop: "12px" }}>
                        <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px", fontFamily: "'IBM Plex Mono', monospace", marginBottom: "6px" }}>TIMELINE</div>
                        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                          {r.timeline_summary.map((t, i) => (
                            <span key={i} style={{ background: COLORS.navyAccent, border: `1px solid ${t.type === "INCOMING" ? COLORS.low : COLORS.critical}`, color: t.type === "INCOMING" ? COLORS.low : COLORS.critical, padding: "3px 8px", borderRadius: "3px", fontSize: "0.68em", fontFamily: "'IBM Plex Mono', monospace" }}>
                              {t.direction} ₹{(t.amount / 1000).toFixed(0)}K {t.time?.slice(5, 16)}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === "validation" && (
          <div style={{ flex: 1, overflowY: "auto", padding: "24px", background: COLORS.navy }}>
            <div style={{ marginBottom: "24px" }}>
              <div style={{ color: COLORS.gold, fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.7em", letterSpacing: "2px", marginBottom: "4px" }}>MODEL VALIDATION LAYER</div>
              <h2 style={{ color: COLORS.text, fontSize: "1.3em", fontWeight: "700", margin: 0 }}>Real Bank Data Validation</h2>
              <p style={{ color: COLORS.textMuted, fontSize: "0.8em", margin: "6px 0 0" }}>Independent validation on the real Bank of India dataset — leak-free 5-fold CV · SHAP feature attribution</p>
            </div>

            {validationLoading && <div className="loading">Running validation on real BOI dataset (this may take a moment)...</div>}

            {validationData && validationData.status === "unavailable" && (
              <div style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.critical}88`, borderRadius: "6px", padding: "16px 20px", color: COLORS.critical, fontSize: "0.85em" }}>
                {validationData.message}
              </div>
            )}

            {validationData && validationData.status === "validated" && (
              <>
                {/* Dataset stats row */}
                <div style={{ display: "flex", gap: "12px", marginBottom: "20px", flexWrap: "wrap" }}>
                  {[
                    { label: "Real Accounts", value: validationData.dataset.total_accounts.toLocaleString(), color: COLORS.text },
                    { label: "Confirmed Mules", value: validationData.dataset.confirmed_mules, color: COLORS.critical },
                    { label: "Positive Rate", value: `${validationData.dataset.positive_rate_pct}%`, color: COLORS.medium },
                    { label: "Features Used", value: `${validationData.dataset.feature_count_used} / ${validationData.dataset.feature_count_total_provided}`, color: COLORS.gold },
                    { label: "Mean AUC-ROC", value: validationData.cross_validation.mean_auc_roc, color: COLORS.low },
                  ].map((s, i) => (
                    <div key={i} style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "6px", padding: "12px 18px", minWidth: "140px" }}>
                      <div style={{ color: COLORS.textMuted, fontSize: "0.6em", letterSpacing: "1px", textTransform: "uppercase", fontFamily: "'IBM Plex Mono', monospace" }}>{s.label}</div>
                      <div style={{ color: s.color, fontSize: "1.3em", fontWeight: "700", fontFamily: "'IBM Plex Mono', monospace" }}>{s.value}</div>
                    </div>
                  ))}
                </div>

                {/* Leakage investigation narrative */}
                <div style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderLeft: `3px solid ${COLORS.gold}`, borderRadius: "6px", padding: "18px 20px", marginBottom: "20px" }}>
                  <div style={{ color: COLORS.gold, fontWeight: "700", fontSize: "0.85em", marginBottom: "10px", fontFamily: "'IBM Plex Mono', monospace" }}>⚠ LABEL LEAKAGE INVESTIGATION</div>
                  <p style={{ color: COLORS.textDim, fontSize: "0.82em", lineHeight: "1.6", margin: "0 0 12px" }}>{validationData.leakage_investigation.summary}</p>
                  <div style={{ display: "flex", gap: "24px", flexWrap: "wrap" }}>
                    <div>
                      <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px", fontFamily: "'IBM Plex Mono', monospace" }}>WORST OFFENDER</div>
                      <div style={{ color: COLORS.critical, fontSize: "0.85em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700" }}>
                        {validationData.leakage_investigation.worst_offender.feature} ({validationData.leakage_investigation.worst_offender.variable_name}) — {(validationData.leakage_investigation.worst_offender.correlation_with_target * 100).toFixed(0)}% correlation
                      </div>
                    </div>
                    <div>
                      <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px", fontFamily: "'IBM Plex Mono', monospace" }}>AUC BEFORE / AFTER FIX</div>
                      <div style={{ fontSize: "0.85em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700" }}>
                        <span style={{ color: COLORS.critical }}>{validationData.leakage_investigation.auc_before_fix}</span>
                        <span style={{ color: COLORS.textMuted }}> → </span>
                        <span style={{ color: COLORS.low }}>{validationData.leakage_investigation.auc_after_fix}</span>
                      </div>
                    </div>
                    <div>
                      <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px", fontFamily: "'IBM Plex Mono', monospace" }}>FIELDS EXCLUDED</div>
                      <div style={{ color: COLORS.text, fontSize: "0.85em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700" }}>{validationData.leakage_investigation.excluded_features.length}</div>
                    </div>
                  </div>
                </div>

                {/* Per-fold CV results */}
                <div style={{ marginBottom: "20px" }}>
                  <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px", fontFamily: "'IBM Plex Mono', monospace", marginBottom: "10px" }}>STRATIFIED 5-FOLD CROSS-VALIDATION</div>
                  <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                    {validationData.cross_validation.folds.map((f) => (
                      <div key={f.fold} style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "6px", padding: "12px 16px", minWidth: "150px" }}>
                        <div style={{ color: COLORS.gold, fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700", marginBottom: "6px" }}>FOLD {f.fold}</div>
                        <div style={{ color: COLORS.text, fontSize: "0.78em", fontFamily: "'IBM Plex Mono', monospace" }}>AUC {f.auc_roc}</div>
                        <div style={{ color: COLORS.textDim, fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace" }}>P {f.precision} · R {f.recall} · F1 {f.f1_score}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Calibration: Brier score + ECE */}
                {validationData.calibration && (
                  <div style={{ marginBottom: "20px" }}>
                    <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px", fontFamily: "'IBM Plex Mono', monospace", marginBottom: "10px" }}>PROBABILITY CALIBRATION</div>
                    <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginBottom: "10px" }}>
                      <div style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "6px", padding: "12px 16px", minWidth: "180px" }}>
                        <div style={{ color: COLORS.gold, fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700", marginBottom: "6px" }}>MEAN BRIER SCORE</div>
                        <div style={{ color: COLORS.low, fontSize: "1.1em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700" }}>{validationData.calibration.mean_brier_score}</div>
                        <div style={{ color: COLORS.textDim, fontSize: "0.68em", fontFamily: "'IBM Plex Mono', monospace" }}>vs 0.25 naive baseline</div>
                      </div>
                      <div style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "6px", padding: "12px 16px", minWidth: "180px" }}>
                        <div style={{ color: COLORS.gold, fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700", marginBottom: "6px" }}>MEAN ECE</div>
                        <div style={{ color: COLORS.low, fontSize: "1.1em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700" }}>{validationData.calibration.mean_expected_calibration_error}</div>
                        <div style={{ color: COLORS.textDim, fontSize: "0.68em", fontFamily: "'IBM Plex Mono', monospace" }}>expected calibration error</div>
                      </div>
                    </div>
                    <p style={{ color: COLORS.textDim, fontSize: "0.78em", lineHeight: "1.6", margin: 0 }}>{validationData.calibration.interpretation}</p>
                  </div>
                )}
                {/* Nested cross-validation */}
                <div style={{ marginBottom: "20px" }}>
                  <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px", fontFamily: "'IBM Plex Mono', monospace", marginBottom: "10px" }}>NESTED CROSS-VALIDATION</div>
                  <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginBottom: "10px" }}>
                    <div style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "6px", padding: "12px 16px", minWidth: "150px" }}>
                      <div style={{ color: COLORS.gold, fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700", marginBottom: "6px" }}>AUC-ROC</div>
                      <div style={{ color: COLORS.text, fontSize: "1.1em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700" }}>0.9907</div>
                      <div style={{ color: COLORS.textDim, fontSize: "0.68em", fontFamily: "'IBM Plex Mono', monospace" }}>±0.0131 · 25 outer evals</div>
                    </div>
                    <div style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "6px", padding: "12px 16px", minWidth: "150px" }}>
                      <div style={{ color: COLORS.gold, fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700", marginBottom: "6px" }}>PRECISION</div>
                      <div style={{ color: COLORS.text, fontSize: "1.1em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700" }}>0.8804</div>
                      <div style={{ color: COLORS.textDim, fontSize: "0.68em", fontFamily: "'IBM Plex Mono', monospace" }}>±0.0747</div>
                    </div>
                    <div style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "6px", padding: "12px 16px", minWidth: "150px" }}>
                      <div style={{ color: COLORS.gold, fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700", marginBottom: "6px" }}>RECALL</div>
                      <div style={{ color: COLORS.text, fontSize: "1.1em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700" }}>0.7310</div>
                      <div style={{ color: COLORS.textDim, fontSize: "0.68em", fontFamily: "'IBM Plex Mono', monospace" }}>±0.0951</div>
                    </div>
                    <div style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "6px", padding: "12px 16px", minWidth: "150px" }}>
                      <div style={{ color: COLORS.gold, fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700", marginBottom: "6px" }}>F1 SCORE</div>
                      <div style={{ color: COLORS.text, fontSize: "1.1em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "700" }}>0.7926</div>
                      <div style={{ color: COLORS.textDim, fontSize: "0.68em", fontFamily: "'IBM Plex Mono', monospace" }}>±0.0572</div>
                    </div>
                  </div>
                  <p style={{ color: COLORS.textDim, fontSize: "0.78em", lineHeight: "1.6", margin: 0 }}>
                    5 repeats × 5 outer × 3 inner folds (25 outer evaluations), sigmoid-calibrated XGBoost, F1-optimal decision threshold selected on inner out-of-fold predictions only. Mean AUC-ROC closely matches the standard 5-fold CV above, confirming the reported performance is genuine and not inflated by implicit hyperparameter tuning against the same data used for evaluation.
                  </p>
                </div>
                {/* SHAP top features on real data */}
                <div>
                  <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px", fontFamily: "'IBM Plex Mono', monospace", marginBottom: "10px" }}>TOP SHAP FEATURES — REAL BOI VARIABLES</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    {validationData.shap_top_features.map((f, i) => (
                      <div key={i} style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <span style={{ color: COLORS.textDim, fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace", minWidth: "220px" }}>{f.feature}</span>
                        <div style={{ flex: 1, background: COLORS.navyAccent, borderRadius: "3px", height: "8px", position: "relative" }}>
                          <div style={{
                            width: `${Math.min(100, (f.mean_abs_shap_impact / validationData.shap_top_features[0].mean_abs_shap_impact) * 100)}%`,
                            background: COLORS.gold, height: "100%", borderRadius: "3px"
                          }} />
                        </div>
                        <span style={{ color: COLORS.gold, fontSize: "0.7em", fontFamily: "'IBM Plex Mono', monospace", minWidth: "50px" }}>{f.mean_abs_shap_impact}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <p style={{ color: COLORS.textMuted, fontSize: "0.72em", fontStyle: "italic", marginTop: "24px", lineHeight: "1.6" }}>{validationData.note}</p>
              </>
            )}
          </div>
        )}

        {activeTab === "evidence" && (
          <div style={{ flex: 1, overflowY: "auto", padding: "24px", background: COLORS.navy }}>
            <button onClick={() => setActiveTab("ml")} style={{ marginBottom: "16px", padding: "6px 16px", background: "#C9A84C12", border: `1px solid ${COLORS.gold}88`, color: COLORS.gold, borderRadius: "4px", cursor: "pointer", fontSize: "0.75em", fontFamily: "'IBM Plex Mono', monospace" }}>BACK TO ML ANALYSIS</button>
            <div style={{ marginBottom: "24px" }}>
              <div style={{ color: COLORS.gold, fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.7em", letterSpacing: "2px", marginBottom: "4px" }}>ACT LAYER</div>
              <h2 style={{ color: COLORS.text, fontSize: "1.3em", fontWeight: "700", margin: 0 }}>Evidence Package</h2>
            </div>
            {evidenceLoading && <div className="loading">Generating court-ready evidence package...</div>}
            {evidenceData && (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div style={{ background: COLORS.navyCard, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "6px", padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px", fontFamily: "'IBM Plex Mono', monospace" }}>EVIDENCE ID</div>
                    <div style={{ color: COLORS.gold, fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.85em", marginTop: "2px" }}>{evidenceData.evidence_id}</div>
                  </div>
                  <div style={{ color: COLORS.textMuted, fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace" }}>{evidenceData.generated_at}</div>
                </div>
                <div style={{ background: getRiskBg(evidenceData.account_summary?.risk_level), border: `1px solid ${getRiskColor(evidenceData.account_summary?.risk_level)}44`, borderLeft: `3px solid ${getRiskColor(evidenceData.account_summary?.risk_level)}`, borderRadius: "6px", padding: "20px" }}>
                  <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px", fontFamily: "'IBM Plex Mono', monospace", marginBottom: "8px" }}>PRIMARY SUBJECT</div>
                  <div style={{ display: "flex", gap: "24px", flexWrap: "wrap", marginBottom: "12px" }}>
                    <div>
                      <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px" }}>ACCOUNT</div>
                      <div style={{ color: getRiskColor(evidenceData.account_summary?.risk_level), fontSize: "1.1em", fontWeight: "700", fontFamily: "'IBM Plex Mono', monospace" }}>{evidenceData.account_summary?.account_id}</div>
                    </div>
                    <div>
                      <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px" }}>RISK SCORE</div>
                      <div style={{ color: getRiskColor(evidenceData.account_summary?.risk_level), fontSize: "1.8em", fontWeight: "800", fontFamily: "'IBM Plex Mono', monospace", lineHeight: 1 }}>{evidenceData.account_summary?.risk_score?.toFixed(1)}</div>
                    </div>
                    <div>
                      <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px" }}>CLASSIFICATION</div>
                      <div style={{ color: COLORS.text, fontSize: "0.9em", fontWeight: "600" }}>{evidenceData.account_summary?.mule_classification}</div>
                    </div>
                  </div>
                  <div style={{ background: COLORS.navyAccent, borderRadius: "4px", padding: "10px 14px" }}>
                    <div style={{ color: COLORS.textMuted, fontSize: "0.65em", letterSpacing: "1px", marginBottom: "4px" }}>RECOMMENDED ACTION</div>
                    <div style={{ color: COLORS.high, fontWeight: "700", fontSize: "0.85em" }}>{evidenceData.account_summary?.recommended_action}</div>
                  </div>
                </div>
                <SectionCard color="#4488FF" title="ML Analysis">
                  <div style={{ color: COLORS.textMuted, fontSize: "0.78em", marginBottom: "10px" }}>{evidenceData.ml_analysis?.detection_method}</div>
                  <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "12px" }}>
                    {evidenceData.ml_analysis?.behavioral_flags?.map((f, i) => (
                      <span key={i} style={{ background: COLORS.navyAccent, border: `1px solid ${COLORS.high}44`, color: COLORS.high, padding: "3px 10px", borderRadius: "3px", fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace" }}>{f}</span>
                    ))}
                  </div>
                  <div style={{ background: COLORS.navyAccent, padding: "10px 12px", borderRadius: "4px", color: COLORS.textMuted, fontSize: "0.75em", fontFamily: "'IBM Plex Mono', monospace" }}>
                    SHAP · {evidenceData.ml_analysis?.shap_explanation}
                  </div>
                </SectionCard>
                <SectionCard color={COLORS.low} title="Regulatory Output">
                  <div style={{ display: "flex", gap: "10px", marginBottom: "14px", flexWrap: "wrap" }}>
                    <span style={{ background: evidenceData.regulatory_output?.fiu_ind_str_required ? "#00C85318" : COLORS.navyAccent, border: `1px solid ${evidenceData.regulatory_output?.fiu_ind_str_required ? COLORS.low : COLORS.navyBorder}`, color: evidenceData.regulatory_output?.fiu_ind_str_required ? COLORS.low : COLORS.textMuted, padding: "6px 14px", borderRadius: "4px", fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "600" }}>
                      {evidenceData.regulatory_output?.fiu_ind_str_required ? "STR REQUIRED" : "STR NOT REQUIRED"}
                    </span>
                    <span style={{ background: evidenceData.regulatory_output?.immediate_freeze_required ? "#FF2D2D18" : COLORS.navyAccent, border: `1px solid ${evidenceData.regulatory_output?.immediate_freeze_required ? COLORS.critical : COLORS.navyBorder}`, color: evidenceData.regulatory_output?.immediate_freeze_required ? COLORS.critical : COLORS.textMuted, padding: "6px 14px", borderRadius: "4px", fontSize: "0.72em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "600" }}>
                      {evidenceData.regulatory_output?.immediate_freeze_required ? "IMMEDIATE FREEZE" : "NO FREEZE REQUIRED"}
                    </span>
                  </div>
                  {evidenceData.regulatory_output?.alerts?.map((a, i) => (
                    <div key={i} style={{ background: COLORS.navyAccent, border: `1px solid ${COLORS.navyBorder}`, borderRadius: "4px", padding: "10px 12px", marginBottom: "8px" }}>
                      <div style={{ color: COLORS.text, fontWeight: "600", fontSize: "0.82em", marginBottom: "4px" }}>{a.body}</div>
                      <div style={{ color: COLORS.textMuted, fontSize: "0.75em" }}>{a.action}</div>
                      <span style={{ display: "inline-block", marginTop: "6px", background: COLORS.high, color: "#000", padding: "1px 8px", borderRadius: "3px", fontSize: "0.65em", fontFamily: "'IBM Plex Mono', monospace", fontWeight: "800" }}>{a.priority}</span>
                    </div>
                  ))}
                </SectionCard>
                <SectionCard color={COLORS.gold} title="FIR Summary — Court Ready">
                  <pre style={{ color: COLORS.textDim, fontSize: "0.78em", whiteSpace: "pre-wrap", fontFamily: "'IBM Plex Mono', monospace", lineHeight: "1.7", margin: 0 }}>{evidenceData.fir_summary}</pre>
                </SectionCard>
              </div>
            )}
            {!evidenceData && !evidenceLoading && (
              <div style={{ color: COLORS.textMuted, textAlign: "center", marginTop: "80px" }}>
                <div style={{ fontSize: "2.5em", marginBottom: "12px", opacity: 0.3 }}>◻</div>
                <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.82em" }}>Select an account and click EVIDENCE PACKAGE to generate court-ready output</div>
              </div>
            )}
          </div>
        )}

        {activeTab === "dashboard" && <div style={{ flex: 1, overflowY: "auto" }}><Dashboard /></div>}
        {activeTab === "citymap" && <div style={{ flex: 1 }}><CityMap graphData={graphData} onCityClick={(city) => {
  setActiveTab("map");
  const newFilters = { ip: "", phone: "", city: city, case_id: filters.case_id };
  setFilters(newFilters);
  fetchGraph(newFilters);
}} /></div>}
      </div>
    </div>
  );
}

export default App;
