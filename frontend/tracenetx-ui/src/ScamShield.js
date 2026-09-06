import React, { useState, useEffect } from "react";

const STAGES = [
  { key: "INITIAL_PRETEXT", label: "Initial Pretext", color: "88,166,255" },
  { key: "AUTHORITY_ESCALATION", label: "Authority Escalation", color: "255,215,0" },
  { key: "ISOLATION_PRESSURE", label: "Isolation Pressure", color: "255,149,0" },
  { key: "PAYMENT_DEMAND", label: "Payment Demand", color: "255,59,59" },
];

export default function ScamShield() {
  const [transcript, setTranscript] = useState("");
  const [callerNumber, setCallerNumber] = useState("");
  const [claimedAuthority, setClaimedAuthority] = useState("");
  const [duration, setDuration] = useState("");
  const [result, setResult] = useState(null);
  const [demoCases, setDemoCases] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch("http://localhost:8001/scam/demo-cases")
      .then(r => r.json())
      .then(d => setDemoCases(d.cases || []))
      .catch(() => {});
  }, []);

  const loadDemo = (c) => {
    setTranscript(c.transcript);
    setCallerNumber(c.caller_number || "");
    setClaimedAuthority(c.claimed_authority || "");
    setDuration(c.call_duration_minutes || "");
    setResult(null);
  };

  const analyze = async () => {
    if (!transcript.trim()) return;
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8001/scam/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript,
          caller_number: callerNumber || null,
          claimed_authority: claimedAuthority || null,
          call_duration_minutes: duration ? parseFloat(duration) : null,
        }),
      });
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setResult({ error: "Could not reach detection engine" });
    }
    setLoading(false);
  };

  const stageIndex = result?.highest_stage_reached
    ? STAGES.findIndex(s => s.key === result.highest_stage_reached)
    : -1;

  const verdictColor = result
    ? result.risk_score >= 70 ? "255,59,59"
    : result.risk_score >= 40 ? "255,149,0"
    : result.risk_score >= 15 ? "255,215,0"
    : "63,185,80"
    : "150,150,150";

  return (
    <div style={{ width: "100%", height: "100%", display: "flex", background: "#0d1117", fontFamily: "monospace" }}>
      {/* Left: input panel */}
      <div style={{ width: "380px", borderRight: "1px solid #21262d", padding: "20px", overflowY: "auto" }}>
        <div style={{ color: "#e6edf3", fontWeight: "bold", fontSize: "1em", marginBottom: 4 }}>
          🛡 Digital Arrest Scam Detector
        </div>
        <div style={{ color: "#8b949e", fontSize: "0.7em", marginBottom: 18 }}>
          Content + self-reported metadata analysis — no tracing, no telecom access
        </div>

        <div style={{ color: "#8b949e", fontSize: "0.7em", marginBottom: 6 }}>Demo cases</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 18 }}>
          {demoCases.map(c => (
            <button key={c.id} onClick={() => loadDemo(c)}
              style={{ background: "#161b22", border: "1px solid #21262d", color: "#58a6ff",
                borderRadius: 6, padding: "8px 10px", textAlign: "left", cursor: "pointer", fontSize: "0.72em" }}>
              {c.label}
            </button>
          ))}
        </div>

        <div style={{ color: "#8b949e", fontSize: "0.7em", marginBottom: 4 }}>Call/message transcript</div>
        <textarea value={transcript} onChange={e => setTranscript(e.target.value)}
          placeholder="Paste or type the call transcript here..."
          style={{ width: "100%", height: 120, background: "#161b22", border: "1px solid #21262d",
            borderRadius: 6, color: "#e6edf3", padding: 10, fontSize: "0.75em", fontFamily: "monospace",
            resize: "vertical", marginBottom: 12 }} />

        <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
          <input value={callerNumber} onChange={e => setCallerNumber(e.target.value)}
            placeholder="Caller number"
            style={{ flex: 1, background: "#161b22", border: "1px solid #21262d", borderRadius: 6,
              color: "#e6edf3", padding: 8, fontSize: "0.72em", fontFamily: "monospace" }} />
          <input value={duration} onChange={e => setDuration(e.target.value)}
            placeholder="Duration (min)"
            style={{ width: 110, background: "#161b22", border: "1px solid #21262d", borderRadius: 6,
              color: "#e6edf3", padding: 8, fontSize: "0.72em", fontFamily: "monospace" }} />
        </div>
        <input value={claimedAuthority} onChange={e => setClaimedAuthority(e.target.value)}
          placeholder="Claimed authority (e.g. CBI, Customs)"
          style={{ width: "100%", background: "#161b22", border: "1px solid #21262d", borderRadius: 6,
            color: "#e6edf3", padding: 8, fontSize: "0.72em", fontFamily: "monospace", marginBottom: 14 }} />

        <button onClick={analyze} disabled={loading}
          style={{ width: "100%", background: "#C9A84C12", border: "1px solid #FFD700",
            color: "#FFD700", borderRadius: 6, padding: "10px", cursor: "pointer",
            fontWeight: "bold", fontSize: "0.8em" }}>
          {loading ? "ANALYZING..." : "ANALYZE"}
        </button>
      </div>

      {/* Right: result panel */}
      <div style={{ flex: 1, padding: "24px", overflowY: "auto" }}>
        {!result && (
          <div style={{ color: "#555", textAlign: "center", marginTop: 100, fontSize: "0.85em" }}>
            Load a demo case or enter a transcript to analyze
          </div>
        )}

        {result && !result.error && (
          <>
            {/* Verdict header */}
            <div style={{ background: "#161b22", border: `1px solid rgb(${verdictColor})`,
              borderRadius: 10, padding: 20, marginBottom: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ color: `rgb(${verdictColor})`, fontWeight: "bold", fontSize: "1.1em" }}>
                  {result.verdict}
                </div>
                <div style={{ color: `rgb(${verdictColor})`, fontWeight: "bold", fontSize: "1.8em" }}>
                  {result.risk_score}
                </div>
              </div>
              <div style={{ color: "#8b949e", fontSize: "0.8em", marginTop: 8 }}>
                {result.recommended_action}
              </div>
              {result.detected_before_payment && (
                <div style={{ color: "#3fb950", fontSize: "0.75em", marginTop: 10,
                  background: "#3fb95012", padding: "6px 10px", borderRadius: 6, display: "inline-block" }}>
                  ✓ Detected before payment demand stage — intervention window still open
                </div>
              )}
            </div>

            {/* Escalation stage tracker — signature element */}
            <div style={{ color: "#e6edf3", fontWeight: "bold", fontSize: "0.85em", marginBottom: 12 }}>
              Escalation Stage Tracker
            </div>
            <div style={{ display: "flex", gap: 4, marginBottom: 24 }}>
              {STAGES.map((s, i) => {
                const reached = i <= stageIndex;
                return (
                  <div key={s.key} style={{ flex: 1 }}>
                    <div style={{
                      height: 8, borderRadius: 4,
                      background: reached ? `rgb(${s.color})` : "#21262d",
                      boxShadow: reached ? `0 0 8px rgba(${s.color},0.6)` : "none",
                      transition: "all 0.3s ease",
                    }} />
                    <div style={{ color: reached ? `rgb(${s.color})` : "#555",
                      fontSize: "0.65em", marginTop: 6, textAlign: "center" }}>
                      {s.label}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Matched phrases per stage */}
            <div style={{ color: "#e6edf3", fontWeight: "bold", fontSize: "0.85em", marginBottom: 10 }}>
              Detected Signals
            </div>
            {Object.entries(result.stage_matches || {}).map(([stage, phrases]) => {
              const stageInfo = STAGES.find(s => s.key === stage);
              return (
                <div key={stage} style={{ background: "#161b22", border: "1px solid #21262d",
                  borderRadius: 8, padding: 12, marginBottom: 8 }}>
                  <div style={{ color: `rgb(${stageInfo?.color})`, fontSize: "0.75em", fontWeight: "bold", marginBottom: 6 }}>
                    {stageInfo?.label}
                  </div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {phrases.map((p, i) => (
                      <span key={i} style={{ background: "#0d1117", border: `1px solid rgba(${stageInfo?.color},0.4)`,
                        color: "#e6edf3", fontSize: "0.7em", padding: "3px 8px", borderRadius: 4 }}>
                        "{p}"
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}

            {result.metadata_flag && (
              <div style={{ background: "#ff3b3b12", border: "1px solid #ff3b3b44",
                borderRadius: 8, padding: 12, marginTop: 8 }}>
                <div style={{ color: "#ff3b3b", fontSize: "0.75em", fontWeight: "bold", marginBottom: 4 }}>
                  ⚠ Caller ID Signature Mismatch
                </div>
                <div style={{ color: "#8b949e", fontSize: "0.72em" }}>{result.metadata_flag}</div>
              </div>
            )}

            {result.duration_flag && (
              <div style={{ background: "#ff950012", border: "1px solid #ff950044",
                borderRadius: 8, padding: 12, marginTop: 8 }}>
                <div style={{ color: "#ff9500", fontSize: "0.75em", fontWeight: "bold", marginBottom: 4 }}>
                  ⏱ Call Duration Flag
                </div>
                <div style={{ color: "#8b949e", fontSize: "0.72em" }}>{result.duration_flag}</div>
              </div>
            )}
          </>
        )}

        {result?.error && (
          <div style={{ color: "#ff3b3b", fontSize: "0.85em" }}>{result.error}</div>
        )}
      </div>
    </div>
  );
}
