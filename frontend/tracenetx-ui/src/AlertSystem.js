import React, { useEffect, useState } from "react";

const alertColor = (level) => {
  if (level === "CRITICAL") return "#FF0000";
  if (level === "HIGH") return "#FF4500";
  return "#FFA500";
};

const alertBg = (level) => {
  if (level === "CRITICAL") return "linear-gradient(135deg, #2a0000, #3a0808)";
  if (level === "HIGH") return "linear-gradient(135deg, #1a0800, #2a1008)";
  return "linear-gradient(135deg, #1a1000, #2a1808)";
};

const alertEmoji = (level) => {
  if (level === "CRITICAL") return "🚨";
  if (level === "HIGH") return "🔴";
  return "⚠️";
};

const alertShadow = (level) => {
  if (level === "CRITICAL") return "0 4px 24px rgba(255,0,0,0.4)";
  if (level === "HIGH") return "0 4px 24px rgba(255,69,0,0.3)";
  return "0 4px 24px rgba(255,165,0,0.2)";
};

function AlertSystem() {
  const [alerts, setAlerts] = useState([]);
  const [dismissed, setDismissed] = useState([]);
  const [visible, setVisible] = useState([]);

  useEffect(() => {
    fetch("http://localhost:8001/alerts")
      .then(r => r.json())
      .then(data => {
        const top = (data.alerts || []).slice(0, 4);
        setAlerts(top);
        top.forEach((_, i) => {
          setTimeout(() => setVisible(v => [...v, i]), i * 600 + 500);
          setTimeout(() => setDismissed(d => [...d, i]), i * 600 + 6000);
        });
      });
  }, []);

  const active = alerts.filter((_, i) => visible.includes(i) && !dismissed.includes(i));
  if (!active.length) return null;

  return (
    <div style={{
      position: "fixed", top: 75, right: 16,
      zIndex: 9999, display: "flex",
      flexDirection: "column", gap: 8, width: 300
    }}>
      {active.map((alert, i) => (
        <div key={i} style={{
          background: alertBg(alert.level),
          border: `1px solid ${alertColor(alert.level)}`,
          borderLeft: `4px solid ${alertColor(alert.level)}`,
          borderRadius: 10,
          padding: "12px 14px",
          animation: "slideIn 0.4s ease",
          boxShadow: alertShadow(alert.level),
          display: "flex", justifyContent: "space-between", alignItems: "flex-start"
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
              <span style={{ fontSize: 14 }}>{alertEmoji(alert.level)}</span>
              <span style={{ color: alertColor(alert.level), fontSize: 11, fontWeight: "bold", letterSpacing: 1 }}>
                {alert.level} RISK DETECTED
              </span>
            </div>
            <div style={{ color: "#fff", fontSize: 15, fontWeight: "bold", marginBottom: 4 }}>
              {alert.account_id}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <div style={{
                background: alertColor(alert.level),
                borderRadius: 20, padding: "2px 8px",
                color: "#fff", fontSize: 11, fontWeight: "bold"
              }}>
                {alert.score}/100
              </div>
              <div style={{ color: "#8b949e", fontSize: 11 }}>Risk Score</div>
            </div>
            {alert.flags.slice(0, 2).map((f, j) => (
              <div key={j} style={{ color: "#aaa", fontSize: 11, marginTop: 2 }}>
                ⚠ {f}
              </div>
            ))}
          </div>
          <button
            onClick={() => setDismissed(d => [...d, alerts.indexOf(alert)])}
            style={{
              background: "none", border: "none",
              color: "#555", cursor: "pointer",
              fontSize: 16, padding: "0 4px", marginLeft: 8,
              lineHeight: 1
            }}>✕</button>
        </div>
      ))}
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(60px); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

export default AlertSystem;
