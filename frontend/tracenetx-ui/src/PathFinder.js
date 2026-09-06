import React, { useState } from "react";

function PathFinder({ nodes }) {
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const findPath = async () => {
    if (!source || !target) return;
    setLoading(true);
    try {
      const res = await fetch(`http://localhost:8001/path?source=${source}&target=${target}`);
      const data = await res.json();
      setResult(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  return (
    <div style={{ padding: 16 }}>
      <h3 style={{ color: "#58a6ff", fontSize: 14, marginBottom: 12 }}>🔍 Trace Money Path</h3>
      <select value={source} onChange={e => setSource(e.target.value)} style={selectStyle}>
        <option value="">From Account...</option>
        {nodes.map(n => <option key={n.id} value={n.id}>{n.id}</option>)}
      </select>
      <select value={target} onChange={e => setTarget(e.target.value)} style={{...selectStyle, marginTop: 8}}>
        <option value="">To Account...</option>
        {nodes.map(n => <option key={n.id} value={n.id}>{n.id}</option>)}
      </select>
      <button onClick={findPath} disabled={loading} style={btnStyle}>
        {loading ? "Tracing..." : "🔎 Trace Path"}
      </button>

      {result && (
        <div style={{ marginTop: 12 }}>
          {result.found ? (
            <div>
              <div style={{ color: "#27ae60", fontSize: 12, marginBottom: 8, fontWeight: "bold" }}>
                ✅ Money Trail Found! ({result.path.length - 1} hops)
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {result.details.map((d, i) => (
                  <div key={i} style={{
                    background: "#21262d",
                    border: "1px solid #30363d",
                    borderLeft: "3px solid #e74c3c",
                    borderRadius: 6,
                    padding: "8px 10px",
                    fontSize: 12,
                    display: "flex",
                    flexDirection: "column",
                    gap: 4
                  }}>
                    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center" }}>
                      <span style={{ color: "#58a6ff" }}>{d.from}</span>
                      <span style={{ color: "#666", margin: "0 6px" }}>→</span>
                      <span style={{ color: "#58a6ff" }}>{d.to}</span>
                    </div>
                    <span style={{ color: "#27ae60", fontWeight: "bold", alignSelf: "flex-end" }}>
                      ₹{d.amount.toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 10, background: "#e74c3c11", border: "1px solid #e74c3c", borderRadius: 6, padding: 10, fontSize: 12 }}>
                <div style={{ color: "#e74c3c", fontWeight: "bold" }}>💰 Full Path:</div>
                <div style={{ color: "#fff", marginTop: 4 }}>{result.path.join(" → ")}</div>
              </div>
            </div>
          ) : (
            <div style={{ color: "#e74c3c", fontSize: 12 }}>❌ No path found between these accounts.</div>
          )}
        </div>
      )}
    </div>
  );
}

const selectStyle = {
  width: "100%", background: "#21262d", border: "1px solid #30363d",
  color: "#e6edf3", padding: 8, borderRadius: 6, fontSize: 12, outline: "none"
};

const btnStyle = {
  width: "100%", marginTop: 8, background: "#1a3a5c", border: "1px solid #58a6ff",
  color: "#58a6ff", padding: 8, borderRadius: 6, fontSize: 12,
  fontWeight: "bold", cursor: "pointer"
};

export default PathFinder;
