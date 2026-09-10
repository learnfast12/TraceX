import React, { useEffect, useState, useCallback, useRef } from "react";
import SpiderMap from "./SpiderMap";

const API = "http://localhost:8002";

const C = {
  bg: "#05070c",
  surface: "#0d1420",
  surfaceRaised: "#111a29",
  border: "#1c2636",
  borderLit: "#2a3a52",
  gold: "#c9a84c",
  btc: "#f7931a",
  text: "#eef2f7",
  textMuted: "#7a8699",
  textDim: "#4a5568",
  CRITICAL: "#ef4a52",
  HIGH: "#f0a03c",
  MEDIUM: "#e8c547",
  CLEAR: "#35c98c",
  mono: "'IBM Plex Mono', 'SF Mono', monospace",
  sans: "'Inter', -apple-system, system-ui, sans-serif",
};

const tierColor = (t) => C[t] || C.textMuted;
const short = (w, n = 10) => (w && w.length > n * 2 + 1) ? `${w.slice(0, n)}…${w.slice(-4)}` : w;

function CopyableHash({ value, size = 12.5 }) {
  const [copied, setCopied] = useState(false);
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{ fontFamily: C.mono, fontSize: size, color: C.text }}>{short(value)}</span>
      <button
        onClick={(e) => { e.stopPropagation(); navigator.clipboard?.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1000); }}
        title="Copy full address"
        style={{
          background: "none", border: "none", cursor: "pointer", padding: 2,
          color: copied ? C.CLEAR : C.textDim, fontSize: size - 1, lineHeight: 1,
        }}
      >{copied ? "✓" : "⧉"}</button>
    </span>
  );
}

// Radial threat gauge — single hero moment
function ThreatGauge({ critical, total }) {
  const pct = total ? (critical / total) : 0;
  const r = 74, circ = 2 * Math.PI * r;
  const dash = circ * pct;
  return (
    <div style={{ position: "relative", width: 180, height: 180, flexShrink: 0 }}>
      <svg width="180" height="180" viewBox="0 0 180 180">
        <circle cx="90" cy="90" r={r} fill="none" stroke={C.border} strokeWidth="10" />
        <circle
          cx="90" cy="90" r={r} fill="none" stroke={C.CRITICAL} strokeWidth="10"
          strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round"
          transform="rotate(-90 90 90)"
          style={{ filter: `drop-shadow(0 0 6px ${C.CRITICAL}88)`, transition: "stroke-dasharray 0.8s ease" }}
        />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontFamily: C.mono, fontSize: 30, fontWeight: 700, color: C.CRITICAL, lineHeight: 1 }}>{critical}</div>
        <div style={{ fontFamily: C.mono, fontSize: 10, color: C.textMuted, letterSpacing: 1, marginTop: 4 }}>CRITICAL / {total}</div>
      </div>
    </div>
  );
}

function TierBar({ tierBreakdown, total }) {
  const tiers = ["CRITICAL", "HIGH", "MEDIUM", "CLEAR"];
  return (
    <div style={{ flex: 1 }}>
      <div style={{ display: "flex", height: 6, borderRadius: 3, overflow: "hidden", background: C.border }}>
        {tiers.map((t) => {
          const count = tierBreakdown[t] || 0;
          const pct = total ? (count / total) * 100 : 0;
          return <div key={t} style={{ width: `${pct}%`, background: tierColor(t), transition: "width 0.6s ease" }} />;
        })}
      </div>
      <div style={{ display: "flex", gap: 24, marginTop: 14 }}>
        {tiers.map((t) => (
          <div key={t}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: tierColor(t), boxShadow: `0 0 6px ${tierColor(t)}` }} />
              <span style={{ fontSize: 10.5, color: C.textMuted, letterSpacing: 0.5 }}>{t}</span>
            </div>
            <div style={{ fontFamily: C.mono, fontSize: 17, fontWeight: 700, color: C.text, marginTop: 2 }}>{tierBreakdown[t] || 0}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ScoreBreakdown({ label, value, color }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: C.textMuted, marginBottom: 4 }}>
        <span>{label}</span><span style={{ fontFamily: C.mono, color: C.text }}>{value?.toFixed(1)}</span>
      </div>
      <div style={{ height: 4, background: C.border, borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${value}%`, height: "100%", background: color, transition: "width 0.5s ease" }} />
      </div>
    </div>
  );
}

function WalletRow({ w, onClick, active }) {
  return (
    <div onClick={() => onClick(w.wallet)} style={{
      display: "grid", gridTemplateColumns: "1fr 70px 70px 70px 90px", gridTemplateRows: "auto auto", rowGap: 4,
      gap: 12, padding: "11px 16px", borderBottom: `1px solid ${C.border}`,
      cursor: "pointer", alignItems: "center",
      background: active ? `${C.gold}0d` : "transparent",
      borderLeft: active ? `2px solid ${C.gold}` : "2px solid transparent",
      transition: "background 0.12s ease",
    }}
      onMouseEnter={e => { if (!active) e.currentTarget.style.background = "#ffffff05"; }}
      onMouseLeave={e => { if (!active) e.currentTarget.style.background = "transparent"; }}
    >
      <CopyableHash value={w.wallet} />
      <span style={{ fontFamily: C.mono, fontSize: 12, color: C.textDim }}>{w.direct_evidence_score?.toFixed(1)}</span>
      <span style={{ fontFamily: C.mono, fontSize: 12, color: C.textDim }}>{w.propagated_score?.toFixed(1)}</span>
      <span style={{ fontFamily: C.mono, fontSize: 12.5, color: C.text, fontWeight: 700 }}>{w.final_score?.toFixed(1)}</span>
      <span style={{
        fontSize: 10.5, fontWeight: 700, letterSpacing: 0.5, color: tierColor(w.tier),
        background: `${tierColor(w.tier)}18`, border: `1px solid ${tierColor(w.tier)}44`,
        borderRadius: 4, padding: "2px 7px", width: "fit-content",
      }}>{w.tier}</span>
      <div style={{ display: "flex", gap: 4, gridColumn: "1 / -1", marginTop: 2 }}>
        {(w.geo_countries || []).slice(0, 4).map(c => (
          <span key={c} style={{
            fontSize: 9.5, fontFamily: C.mono, color: C.textDim,
            background: "#ffffff08", border: `1px solid ${C.border}`,
            borderRadius: 3, padding: "1px 5px",
          }}>{c}</span>
        ))}
        {typeof w.anomaly_score === "number" && (
          <span style={{
            fontSize: 9.5, fontFamily: C.mono,
            color: w.anomaly_score >= 70 ? C.CRITICAL : w.anomaly_score >= 40 ? C.HIGH : C.textDim,
            background: "#ffffff08", border: `1px solid ${C.border}`,
            borderRadius: 3, padding: "1px 5px",
          }}>ML {w.anomaly_score?.toFixed(0)}</span>
        )}
      </div>
    </div>
  );
}

// Small hop-chain visual: dots + connecting line instead of text arrows
function ChainFlow({ wallets, sinks }) {
  const shown = wallets.slice(0, 6);
  const overflow = wallets.length - shown.length;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 2, marginTop: 12, flexWrap: "wrap" }}>
      {shown.map((w, i) => (
        <React.Fragment key={i}>
          <div title={w} style={{
            width: 9, height: 9, borderRadius: "50%",
            background: i === 0 ? C.CRITICAL : C.gold,
            boxShadow: `0 0 5px ${i === 0 ? C.CRITICAL : C.gold}aa`,
          }} />
          {i < shown.length - 1 && <div style={{ width: 18, height: 1, background: C.borderLit }} />}
        </React.Fragment>
      ))}
      {overflow > 0 && (
        <span style={{ fontSize: 11, color: C.textMuted, marginLeft: 6, fontFamily: C.mono }}>+{overflow} more hops</span>
      )}
      {sinks?.length > 0 && (
        <>
          <div style={{ width: 18, height: 1, background: `${C.CLEAR}66`, marginLeft: 4 }} />
          <div title="peel-sink" style={{ width: 9, height: 9, borderRadius: 2, background: C.CLEAR, boxShadow: `0 0 5px ${C.CLEAR}aa` }} />
          <span style={{ fontSize: 10.5, color: C.textMuted, marginLeft: 4 }}>{sinks.length} sinks</span>
        </>
      )}
    </div>
  );
}

// Convergence glyph for darknet sweeps: many dots -> one
function SweepConverge({ count }) {
  const n = Math.min(count, 7);
  const angles = Array.from({ length: n }, (_, i) => (i / n) * 2 * Math.PI);
  return (
    <svg width="60" height="60" viewBox="0 0 60 60" style={{ flexShrink: 0 }}>
      {angles.map((a, i) => {
        const x1 = 30 + Math.cos(a) * 22, y1 = 30 + Math.sin(a) * 22;
        return <line key={i} x1={x1} y1={y1} x2="30" y2="30" stroke={C.CRITICAL} strokeWidth="1" opacity="0.5" />;
      })}
      {angles.map((a, i) => {
        const x1 = 30 + Math.cos(a) * 22, y1 = 30 + Math.sin(a) * 22;
        return <circle key={i} cx={x1} cy={y1} r="2.2" fill={C.gold} />;
      })}
      <circle cx="30" cy="30" r="5" fill={C.CRITICAL} style={{ filter: `drop-shadow(0 0 4px ${C.CRITICAL})` }} />
    </svg>
  );
}

export default function BtcDashboard() {
  const [status, setStatus] = useState(null);
  const [dash, setDash] = useState(null);
  const [chains, setChains] = useState([]);
  const [sweeps, setSweeps] = useState([]);
  const [tierFilter, setTierFilter] = useState("CRITICAL");
  const [tierResults, setTierResults] = useState([]);
  const [selectedWallet, setSelectedWallet] = useState(null);
  const [walletDetail, setWalletDetail] = useState(null);
  const [anomalyDetail, setAnomalyDetail] = useState(null);
  const [geoDetail, setGeoDetail] = useState(null);
  const [tab, setTab] = useState("overview");
  const [error, setError] = useState(null);
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [organizedLayout, setOrganizedLayout] = useState(true);
  const [shadowData, setShadowData] = useState(null);
  const [selectedCluster, setSelectedCluster] = useState(null);
  const [clusterWalletMatches, setClusterWalletMatches] = useState(null);
  const [clusterInspectWallet, setClusterInspectWallet] = useState(null);
  const mounted = useRef(false);

  const load = useCallback(() => {
    fetch(`${API}/btc/status`).then(r => r.json()).then(d => { setError(d.error || null); setStatus(d); }).catch(e => setError(String(e)));
    fetch(`${API}/btc/dashboard`).then(r => r.json()).then(setDash).catch(() => {});
    fetch(`${API}/btc/graph`).then(r => r.json()).then(d => setGraphData({ nodes: d.nodes || [], edges: d.edges || [] })).catch(() => {});
    fetch(`${API}/btc/peeling-chains?limit=25`).then(r => r.json()).then(d => setChains(d.results || [])).catch(() => {});
    fetch(`${API}/btc/darknet-sweeps?limit=25`).then(r => r.json()).then(d => setSweeps(d.results || [])).catch(() => {});
    fetch(`${API}/btc/shadow-entities`).then(r => r.json()).then(setShadowData).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    fetch(`${API}/btc/risk-scores?tier=${tierFilter}&limit=50`).then(r => r.json()).then(d => setTierResults(d.results || [])).catch(() => {});
  }, [tierFilter]);

  const openWallet = (walletId) => {
    setSelectedWallet(walletId);
    fetch(`${API}/btc/wallet/${walletId}`).then(r => r.json()).then(setWalletDetail).catch(() => {});
    fetch(`${API}/btc/wallet/${walletId}/anomaly-explanation`).then(r => r.json()).then(setAnomalyDetail).catch(() => setAnomalyDetail(null));
    fetch(`${API}/btc/wallet/${walletId}/geo`).then(r => r.json()).then(setGeoDetail).catch(() => setGeoDetail(null));
  };

  const openClusterWallet = (walletId) => {
    setClusterInspectWallet(walletId);
    fetch(`${API}/btc/wallet/${walletId}/shadow-matches`)
      .then(r => r.json())
      .then(setClusterWalletMatches)
      .catch(() => setClusterWalletMatches(null));
  };

  if (error) {
    return (
      <div style={{ padding: 40, color: C.CRITICAL, fontFamily: C.mono, fontSize: 13 }}>
        Bitcoin layer unavailable: {error}
      </div>
    );
  }

  return (
    <div style={{ background: C.bg, color: C.text, minHeight: "100%", fontFamily: C.sans }}>
      {/* Hero */}
      <div style={{
        padding: "28px 32px", borderBottom: `1px solid ${C.border}`,
        background: `radial-gradient(ellipse at top left, ${C.btc}0f, transparent 60%)`,
      }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 32 }}>
          <ThreatGauge critical={dash?.tier_breakdown?.CRITICAL || 0} total={dash?.total_wallets || 0} />
          <div style={{ flex: 1, paddingTop: 6 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: C.CLEAR, boxShadow: `0 0 6px ${C.CLEAR}`, display: "inline-block" }} />
              <span style={{ fontSize: 10.5, color: C.textMuted, letterSpacing: 1 }}>LIVE — offline Bitcoin intelligence layer</span>
            </div>
            <div style={{ fontSize: 26, fontWeight: 800, color: C.text, marginTop: 6, letterSpacing: -0.5 }}>
              {status?.transactions_indexed?.toLocaleString()} transactions across {status?.wallets_indexed?.toLocaleString()} wallets
            </div>
            <div style={{ color: C.textMuted, fontSize: 13, marginTop: 4 }}>
              {status?.peeling_chains_flagged} peeling chains and {status?.darknet_sweeps_flagged} darknet sweeps flagged by the risk-propagation engine
            </div>
            <div style={{ marginTop: 20 }}>
              <TierBar tierBreakdown={dash?.tier_breakdown || {}} total={dash?.total_wallets} />
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, padding: "0 32px", borderBottom: `1px solid ${C.border}` }}>
        {[["overview", "Overview"], ["chains", "Peeling Chains"], ["sweeps", "Darknet Sweeps"], ["shadow", "Shadow Clusters"], ["spidermap", "Spider Map"]].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} style={{
            background: "none", border: "none", padding: "12px 6px", cursor: "pointer",
            fontSize: 13, fontWeight: 600, color: tab === id ? C.text : C.textMuted,
            borderBottom: tab === id ? `2px solid ${C.btc}` : "2px solid transparent",
            marginRight: 20, fontFamily: C.sans,
          }}>{label}</button>
        ))}
      </div>

      <div style={{ padding: "24px 32px" }}>
        {tab === "overview" && (
          <div style={{ display: "grid", gridTemplateColumns: selectedWallet ? "1fr 300px" : "1fr", gap: 20 }}>
            <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, overflow: "hidden" }}>
              <div style={{ display: "flex", gap: 8, padding: "12px 16px", borderBottom: `1px solid ${C.border}` }}>
                {["CRITICAL", "HIGH", "MEDIUM", "CLEAR"].map(t => (
                  <button key={t} onClick={() => setTierFilter(t)} style={{
                    background: tierFilter === t ? `${tierColor(t)}18` : "transparent",
                    border: `1px solid ${tierFilter === t ? tierColor(t) : C.border}`,
                    color: tierFilter === t ? tierColor(t) : C.textMuted,
                    borderRadius: 5, padding: "5px 12px", fontSize: 11, fontWeight: 700,
                    cursor: "pointer", fontFamily: C.mono, letterSpacing: 0.5,
                  }}>{t}</button>
                ))}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 70px 70px 70px 90px", gap: 12, padding: "9px 16px", fontSize: 10, color: C.textDim, letterSpacing: 0.5, borderBottom: `1px solid ${C.border}` }}>
                <span>WALLET</span><span>DIRECT</span><span>PROP.</span><span>FINAL</span><span>TIER</span>
              </div>
              <div style={{ maxHeight: 520, overflowY: "auto" }}>
                {tierResults.map(w => <WalletRow key={w.wallet} w={w} onClick={openWallet} active={selectedWallet === w.wallet} />)}
                {tierResults.length === 0 && <div style={{ padding: 28, color: C.textMuted, fontSize: 13, textAlign: "center" }}>No wallets in this tier.</div>}
              </div>
            </div>

            {selectedWallet && walletDetail && (
              <div style={{ background: C.surfaceRaised, border: `1px solid ${C.border}`, borderRadius: 10, padding: 20, height: "fit-content" }}>
                <div style={{ fontSize: 10.5, color: C.textMuted, letterSpacing: 1, marginBottom: 6 }}>WALLET INSPECTOR</div>
                <CopyableHash value={selectedWallet} size={13} />
                {walletDetail.risk && (
                  <>
                    <div style={{ margin: "16px 0" }}>
                      <div style={{ fontSize: 34, fontWeight: 800, color: tierColor(walletDetail.risk.tier), fontFamily: C.mono, lineHeight: 1 }}>
                        {walletDetail.risk.final_score?.toFixed(1)}
                      </div>
                      <div style={{
                        display: "inline-block", marginTop: 8, fontSize: 10.5, fontWeight: 700, letterSpacing: 0.5,
                        color: tierColor(walletDetail.risk.tier), background: `${tierColor(walletDetail.risk.tier)}18`,
                        border: `1px solid ${tierColor(walletDetail.risk.tier)}44`, borderRadius: 4, padding: "3px 8px",
                      }}>{walletDetail.risk.tier}</div>
                    </div>
                    <ScoreBreakdown label="Direct evidence" value={walletDetail.risk.direct_evidence_score} color={C.gold} />
                    <ScoreBreakdown label="Propagated risk" value={walletDetail.risk.propagated_score} color={C.btc} />
                  </>
                )}
                <div style={{ display: "flex", gap: 20, marginTop: 16, paddingTop: 16, borderTop: `1px solid ${C.border}` }}>
                  <div>
                    <div style={{ fontSize: 20, fontWeight: 700, fontFamily: C.mono, color: C.text }}>{walletDetail.peeling_chain_membership?.length ?? 0}</div>
                    <div style={{ fontSize: 10.5, color: C.textMuted }}>peeling chains</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 20, fontWeight: 700, fontFamily: C.mono, color: C.text }}>{walletDetail.darknet_sweep_membership?.length ?? 0}</div>
                    <div style={{ fontSize: 10.5, color: C.textMuted }}>darknet sweeps</div>
                  </div>
                </div>

                {anomalyDetail?.top_contributing_features?.length > 0 && (
                  <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${C.border}` }}>
                    <div style={{ fontSize: 10.5, color: C.textMuted, letterSpacing: 0.5, marginBottom: 8 }}>ANOMALY DRIVERS</div>
                    {(() => {
                      const maxAbs = Math.max(...anomalyDetail.top_contributing_features.map(f => Math.abs(f.impact)), 0.0001);
                      return anomalyDetail.top_contributing_features.map(f => {
                        const pct = (Math.abs(f.impact) / maxAbs) * 100;
                        const barColor = f.impact >= 0 ? C.HIGH : C.btc;
                        return (
                          <div key={f.feature} style={{ marginBottom: 6 }}>
                            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, fontFamily: C.mono, color: C.textDim, marginBottom: 2 }}>
                              <span>{f.feature}</span>
                              <span style={{ color: barColor }}>{f.impact >= 0 ? "+" : ""}{f.impact.toFixed(3)}</span>
                            </div>
                            <div style={{ height: 4, background: "#ffffff0a", borderRadius: 2, overflow: "hidden" }}>
                              <div style={{ height: "100%", width: `${pct}%`, background: barColor, borderRadius: 2 }} />
                            </div>
                          </div>
                        );
                      });
                    })()}
                  </div>
                )}

                {geoDetail && (geoDetail.sending_ips?.length > 0 || geoDetail.receiving_ips?.length > 0) && (
                  <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${C.border}` }}>
                    <div style={{ fontSize: 10.5, color: C.textMuted, letterSpacing: 0.5, marginBottom: 8 }}>NETWORK</div>
                    {["sending_ips", "receiving_ips"].map(key => (
                      geoDetail[key]?.length > 0 && (
                        <div key={key} style={{ marginBottom: 8 }}>
                          <div style={{ fontSize: 9.5, color: C.textDim, letterSpacing: 0.5, marginBottom: 4 }}>
                            {key === "sending_ips" ? "SENDING" : "RECEIVING"}
                          </div>
                          {geoDetail[key].map((ipInfo, i) => (
                            <div key={`${key}-${i}`} style={{
                              display: "flex", justifyContent: "space-between", alignItems: "center",
                              fontSize: 11, fontFamily: C.mono, color: C.text, padding: "4px 0",
                              borderBottom: i < geoDetail[key].length - 1 ? `1px solid ${C.border}` : "none",
                            }}>
                              <span>{ipInfo.ip}</span>
                              <span style={{ display: "flex", gap: 6, alignItems: "center" }}>
                                <span style={{ fontSize: 9.5, color: C.textDim }}>{ipInfo.geo_country}</span>
                                <span style={{
                                  fontSize: 9.5, color: C.textMuted, background: "#ffffff08",
                                  border: `1px solid ${C.border}`, borderRadius: 3, padding: "1px 5px",
                                }}>{ipInfo.asn_org || `AS${ipInfo.asn}`}</span>
                              </span>
                            </div>
                          ))}
                        </div>
                      )
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {tab === "chains" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {chains.map((c, i) => (
              <div key={i} style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: "16px 18px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{c.hop_count}-hop peeling chain</span>
                  <span style={{ color: C.HIGH, fontFamily: C.mono, fontWeight: 700, fontSize: 13 }}>{(c.confidence * 100).toFixed(1)}%</span>
                </div>
                <ChainFlow wallets={c.chain_wallets} sinks={c.peel_sink_wallets} />
                <div style={{ fontSize: 10.5, color: C.textDim, marginTop: 10 }}>avg skew ratio {c.avg_skew_ratio}</div>
              </div>
            ))}
          </div>
        )}

        {tab === "sweeps" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {sweeps.map((s, i) => (
              <div key={i} style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: "14px 18px", display: "flex", gap: 16, alignItems: "center" }}>
                <SweepConverge count={s.input_count} />
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{s.input_count} inputs converge to one vault</span>
                    <span style={{ color: C.CRITICAL, fontFamily: C.mono, fontWeight: 700, fontSize: 13 }}>{(s.confidence * 100).toFixed(1)}%</span>
                  </div>
                  <div style={{ marginTop: 6 }}><CopyableHash value={s.vault_wallet} /></div>
                  <div style={{ fontSize: 10.5, color: C.textDim, marginTop: 6 }}>IP reuse ratio {s.ip_reuse_ratio}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "shadow" && (
          <div style={{ display: "grid", gridTemplateColumns: selectedCluster ? "340px 1fr" : "1fr", gap: 20 }}>
            <div>
              {shadowData?.diagnostics && (
                <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: "14px 16px", marginBottom: 14 }}>
                  <div style={{ fontSize: 10.5, color: C.textMuted, letterSpacing: 0.5, marginBottom: 10 }}>SHADOW ENTITY RESOLUTION — {shadowData.backend}</div>
                  <div style={{ display: "flex", gap: 24 }}>
                    <div>
                      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: C.mono, color: C.text }}>{shadowData.total_clusters}</div>
                      <div style={{ fontSize: 10, color: C.textMuted }}>clusters</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: C.mono, color: C.text }}>{shadowData.wallets_with_shadow_matches?.toLocaleString()}</div>
                      <div style={{ fontSize: 10, color: C.textMuted }}>wallets matched</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: C.mono, color: C.btc }}>{(shadowData.diagnostics.threshold_used * 100).toFixed(1)}%</div>
                      <div style={{ fontSize: 10, color: C.textMuted }}>similarity threshold</div>
                    </div>
                  </div>
                  <div style={{ fontSize: 10, color: C.textDim, marginTop: 10, fontFamily: C.mono }}>
                    {shadowData.diagnostics.eligible_wallets?.toLocaleString()} eligible · {shadowData.diagnostics.excluded_low_event_wallets?.toLocaleString()} excluded (fewer than {shadowData.diagnostics.min_events_required} events) · baseline p99 similarity {(shadowData.diagnostics.baseline_p99 * 100).toFixed(1)}%
                  </div>
                </div>
              )}
              <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, overflow: "hidden" }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 60px", gap: 12, padding: "9px 16px", fontSize: 10, color: C.textDim, letterSpacing: 0.5, borderBottom: `1px solid ${C.border}` }}>
                  <span>CLUSTER</span><span>SIZE</span>
                </div>
                <div style={{ maxHeight: 520, overflowY: "auto" }}>
                  {(shadowData?.clusters || []).map(c => (
                    <div key={c.cluster_id} onClick={() => { setSelectedCluster(c); setClusterInspectWallet(null); setClusterWalletMatches(null); }} style={{
                      display: "grid", gridTemplateColumns: "1fr 60px", gap: 12, padding: "10px 16px",
                      borderBottom: `1px solid ${C.border}`, cursor: "pointer",
                      background: selectedCluster?.cluster_id === c.cluster_id ? `${C.btc}10` : "transparent",
                    }}>
                      <span style={{ fontFamily: C.mono, fontSize: 12.5, color: C.text }}>Cluster #{c.cluster_id}</span>
                      <span style={{ fontFamily: C.mono, fontSize: 12.5, color: C.textMuted }}>{c.size}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {selectedCluster && (
              <div style={{ background: C.surfaceRaised, border: `1px solid ${C.border}`, borderRadius: 10, padding: 20 }}>
                <div style={{ fontSize: 10.5, color: C.textMuted, letterSpacing: 1, marginBottom: 12 }}>
                  CLUSTER #{selectedCluster.cluster_id} — {selectedCluster.size} WALLETS RESOLVED TO ONE SHADOW ENTITY
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: clusterInspectWallet ? 16 : 0, paddingBottom: clusterInspectWallet ? 16 : 0, borderBottom: clusterInspectWallet ? `1px solid ${C.border}` : "none" }}>
                  {selectedCluster.wallets.map(w => (
                    <button key={w} onClick={() => openClusterWallet(w)} style={{
                      background: clusterInspectWallet === w ? `${C.btc}18` : "transparent",
                      border: `1px solid ${clusterInspectWallet === w ? C.btc : C.border}`,
                      borderRadius: 5, padding: "5px 10px", cursor: "pointer",
                      fontFamily: C.mono, fontSize: 11.5, color: clusterInspectWallet === w ? C.btc : C.text,
                    }}>{short(w, 6)}</button>
                  ))}
                </div>

                {clusterInspectWallet && clusterWalletMatches?.shadow_matches && (
                  <div>
                    <div style={{ fontSize: 10.5, color: C.textMuted, letterSpacing: 0.5, marginBottom: 4 }}>
                      SHADOW MATCHES FOR <CopyableHash value={clusterInspectWallet} size={11} />
                    </div>
                    <div style={{ fontSize: 10, color: C.textDim, marginBottom: 10 }}>
                      Cluster membership confidence: {(clusterWalletMatches.cluster_membership_confidence * 100).toFixed(1)}%
                    </div>
                    {clusterWalletMatches.shadow_matches.map(m => (
                      <div key={m.wallet} style={{ marginBottom: 8 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, fontFamily: C.mono, marginBottom: 3 }}>
                          <CopyableHash value={m.wallet} size={11} />
                          <span style={{ color: C.gold }}>{(m.similarity * 100).toFixed(2)}%</span>
                        </div>
                        <div style={{ height: 4, background: "#ffffff0a", borderRadius: 2, overflow: "hidden" }}>
                          <div style={{ height: "100%", width: `${m.similarity * 100}%`, background: C.gold, borderRadius: 2 }} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {tab === "spidermap" && (
          <div style={{ position: "relative", height: 640 }}>
            <button onClick={() => setOrganizedLayout(v => !v)} style={{
              position: "absolute", top: 12, right: 12, zIndex: 10,
              padding: "6px 14px",
              background: "transparent",
              border: `1px solid ${C.CLEAR}`,
              color: C.CLEAR,
              borderRadius: 4, cursor: "pointer",
              fontFamily: C.mono, fontWeight: 600, fontSize: "0.72em",
              letterSpacing: "1px", backdropFilter: "blur(4px)",
            }}>
              {organizedLayout ? "RAW VIEW" : "ORGANIZE"}
            </button>
            {graphData.nodes.length === 0 ? (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: C.textMuted, fontFamily: C.mono, fontSize: 13 }}>
                Loading wallet graph…
              </div>
            ) : (
              <SpiderMap
                graphData={graphData}
                onNodeClick={(id) => setSelectedWallet(id)}
                organized={organizedLayout}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
