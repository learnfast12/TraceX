import React from "react";

const fmt = (v) => "₹" + (v >= 100000 ? (v/100000).toFixed(1) + "L" : (v/1000).toFixed(0) + "K");

const riskColor = (level) => {
  if (level === "CRITICAL") return "#FF0000";
  if (level === "HIGH") return "#FF4500";
  if (level === "MEDIUM") return "#FFA500";
  if (level === "CLEAR") return "#00CC44";
  return "#00CC44";
};

const riskBg = (level) => {
  if (level === "CRITICAL") return "rgba(255,0,0,0.1)";
  if (level === "HIGH") return "rgba(255,69,0,0.1)";
  if (level === "MEDIUM") return "rgba(255,165,0,0.1)";
  return "rgba(0,204,68,0.1)";
};

function Sidebar({ selectedNode }) {
  if (!selectedNode) return (
    <div style={{
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      height: "100%", padding: 24, gap: 16, textAlign: "center"
    }}>
      <div style={{ fontSize: 48, opacity: 0.3 }}>🕸️</div>
      <div style={{ color: "#8b949e", fontSize: 13, lineHeight: 1.6 }}>
        Click any node on the map to inspect account details
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%", marginTop: 8 }}>
        {["Click a RED node to see criminal flags", "Click CRIMINAL1 to see outgoing trail", "Use Trace Path to follow the money"].map((tip, i) => (
          <div key={i} style={{
            background: "#161b22", border: "1px solid #30363d",
            borderRadius: 8, padding: "8px 12px",
            color: "#8b949e", fontSize: 11, textAlign: "left"
          }}>
            💡 {tip}
          </div>
        ))}
      </div>
    </div>
  );

  const { account, risk } = selectedNode;
  const level = risk?.level || "LOW";
  const score = risk?.score || 0;
  const flags = risk?.flags || [];

  return (
    <div style={{ padding: 16, overflowY: "auto", height: "100%" }}>

      {/* Risk Score Header */}
      <div style={{
        background: riskBg(level),
        border: `1px solid ${riskColor(level)}`,
        borderRadius: 12, padding: 16, marginBottom: 16,
        textAlign: "center"
      }}>
        <div style={{ color: riskColor(level), fontSize: 11, fontWeight: "bold", letterSpacing: 1, marginBottom: 8 }}>
          {level === "CRITICAL" ? "🚨" : level === "HIGH" ? "🔴" : level === "MEDIUM" ? "⚠️" : "✅"} {level === "CLEAR" ? "SAFE" : level + " RISK"}
        </div>
        <div style={{ color: "#e6edf3", fontSize: 22, fontWeight: "bold", marginBottom: 8 }}>
          {account?.id}
        </div>

        {/* Score bar */}
        <div style={{ background: "#0d1117", borderRadius: 20, height: 8, marginBottom: 6, overflow: "hidden" }}>
          <div style={{
            width: `${score}%`,
            height: "100%",
            background: `linear-gradient(90deg, ${riskColor(level)}, ${riskColor(level)}88)`,
            borderRadius: 20,
            transition: "width 1s ease"
          }} />
        </div>
        <div style={{ color: riskColor(level), fontSize: 13, fontWeight: "bold" }}>
          {score}/100
        </div>
      </div>

      {/* Money Summary */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <div style={{
          flex: 1, background: "rgba(39,174,96,0.08)",
          border: "1px solid rgba(39,174,96,0.3)",
          borderRadius: 10, padding: 12, textAlign: "center"
        }}>
          <div style={{ color: "#8b949e", fontSize: 10, marginBottom: 4 }}>INCOMING</div>
          <div style={{ color: "#27ae60", fontSize: 16, fontWeight: "bold" }}>
            {fmt(account?.total_incoming || 0)}
          </div>
        </div>
        <div style={{
          flex: 1, background: "rgba(231,76,60,0.08)",
          border: "1px solid rgba(231,76,60,0.3)",
          borderRadius: 10, padding: 12, textAlign: "center"
        }}>
          <div style={{ color: "#8b949e", fontSize: 10, marginBottom: 4 }}>OUTGOING</div>
          <div style={{ color: "#e74c3c", fontSize: 16, fontWeight: "bold" }}>
            {fmt(account?.total_outgoing || 0)}
          </div>
        </div>
      </div>

      {/* Own IP */}
      {account?.own_ip && (
        <div style={{ marginBottom: 16, background:"#0d1117", border:"1px solid #58a6ff", borderRadius:8, padding:"10px 14px", display:"flex", justifyContent:"space-between", alignItems:"center" }}>
          <span style={{ color:"#8b949e", fontSize:11, fontWeight:"bold" }}>DEVICE IP</span>
          <span style={{ color:"#58a6ff", fontSize:13, fontFamily:"monospace", fontWeight:"bold" }}>🌐 {account.own_ip}</span>
        </div>
      )}

      {/* Flags */}
      {flags.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ color: "#8b949e", fontSize: 11, fontWeight: "bold", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>
            🚩 Suspicion Flags
          </div>
          {flags.map((f, i) => (
            <div key={i} style={{
              background: "rgba(231,76,60,0.08)",
              border: "1px solid rgba(231,76,60,0.25)",
              borderLeft: "3px solid #e74c3c",
              borderRadius: "0 8px 8px 0",
              padding: "8px 12px",
              marginBottom: 6,
              color: "#ffa07a",
              fontSize: 12
            }}>
              ⚠ {f}
            </div>
          ))}
        </div>
      )}

      {/* Incoming Transactions */}
      {account?.incoming?.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ color: "#8b949e", fontSize: 11, fontWeight: "bold", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>
            📥 Incoming ({account.incoming.length})
          </div>
          {account.incoming.map((tx, i) => (
            <div key={i} style={{
              background: "#161b22", border: "1px solid #30363d",
              borderRadius: 8, padding: "10px 12px", marginBottom: 6
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                <span style={{ color: "#58a6ff", fontSize: 13, fontWeight: "bold" }}>{tx.sender}</span>
                <span style={{ color: "#27ae60", fontSize: 13, fontWeight: "bold" }}>{fmt(tx.amount)}</span>
              </div>
              <div style={{ color: "#8b949e", fontSize: 11 }}>
                📍 {tx.city} &nbsp;•&nbsp; 🌐 {tx.ip}
              </div>
              {tx.timestamp && (
                <div style={{ color: "#8b949e", fontSize: 10, marginTop: 2 }}>
                  🕐 {tx.timestamp}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Outgoing Transactions */}
      {account?.outgoing?.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ color: "#8b949e", fontSize: 11, fontWeight: "bold", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>
            📤 Outgoing ({account.outgoing.length})
          </div>
          {account.outgoing.map((tx, i) => (
            <div key={i} style={{
              background: "#161b22", border: "1px solid #30363d",
              borderRadius: 8, padding: "10px 12px", marginBottom: 6
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                <span style={{ color: "#e74c3c", fontSize: 13, fontWeight: "bold" }}>{tx.receiver}</span>
                <span style={{ color: "#e74c3c", fontSize: 13, fontWeight: "bold" }}>{fmt(tx.amount)}</span>
              </div>
              {tx.timestamp && (
                <div style={{ color: "#8b949e", fontSize: 10, marginTop: 2 }}>
                  🕐 {tx.timestamp}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

    </div>
  );
}

export default Sidebar;
