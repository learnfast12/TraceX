import React, { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell, Legend } from "recharts";

const fmt = (v) => "₹" + (v >= 100000 ? (v/100000).toFixed(1) + "L" : (v/1000).toFixed(0) + "K");

const COLORS = { CRITICAL: "#FF0000", HIGH: "#FF4500", MEDIUM: "#FFA500", LOW: "#00CC44", CLEAR: "#00CC44" };
const CITY_COLORS = ["#e74c3c","#f39c12","#27ae60","#58a6ff","#9b59b6","#1abc9c","#e67e22","#2ecc71"];

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 8, padding: "10px 14px" }}>
        <div style={{ color: "#8b949e", fontSize: 11, marginBottom: 4 }}>{label}</div>
        <div style={{ color: "#e6edf3", fontSize: 14, fontWeight: "bold" }}>
          {typeof payload[0].value === "number" && payload[0].value > 1000 ? fmt(payload[0].value) : payload[0].value}
        </div>
      </div>
    );
  }
  return null;
};

const StatCard = ({ label, value, color, icon }) => (
  <div style={{
    background: "linear-gradient(135deg, #161b22, #1c2128)",
    border: "1px solid #30363d",
    borderRadius: 12,
    padding: "20px 24px",
    flex: 1,
    position: "relative",
    overflow: "hidden"
  }}>
    <div style={{ position: "absolute", top: 12, right: 16, fontSize: 24, opacity: 0.15 }}>{icon}</div>
    <div style={{ color: "#8b949e", fontSize: 11, textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>{label}</div>
    <div style={{ color: color || "#e6edf3", fontSize: 28, fontWeight: "bold" }}>{value}</div>
  </div>
);

function Dashboard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    fetch("http://localhost:8001/dashboard")
      .then(r => r.json())
      .then(setData);
  }, []);

  if (!data) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", flexDirection: "column", gap: 16 }}>
      <div style={{ color: "#e74c3c", fontSize: 32 }}>🕸️</div>
      <div style={{ color: "#8b949e", fontSize: 14 }}>Loading intelligence data...</div>
    </div>
  );

  const riskDist = [
    { name: "Critical", value: data.risk_data.filter(r => r.level === "CRITICAL").length, color: "#FF0000" },
    { name: "High Risk", value: data.risk_data.filter(r => r.level === "HIGH").length, color: "#FF4500" },
    { name: "Medium Risk", value: data.risk_data.filter(r => r.level === "MEDIUM").length, color: "#FFA500" },
    { name: "Safe", value: data.risk_data.filter(r => r.level === "CLEAR").length, color: "#00CC44" },
  ];

  return (
    <div style={{ padding: "20px 24px", overflowY: "auto", height: "100%", background: "#0d1117" }}>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <div style={{ fontSize: 22 }}>📊</div>
        <div>
          <h2 style={{ color: "#e6edf3", fontSize: 18, fontWeight: "bold" }}>Risk Intelligence Dashboard</h2>
          <p style={{ color: "#8b949e", fontSize: 12 }}>Real-time AML analysis across all cases</p>
        </div>
      </div>

      {/* Stat Cards */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20 }}>
        <StatCard label="Total Amount" value={fmt(data.total_amount)} color="#58a6ff" icon="💰" />
        <StatCard label="Transactions" value={data.total_transactions} color="#e6edf3" icon="🔄" />
        <StatCard label="Critical" value={data.risk_data?.filter(r => r.level === "CRITICAL").length || 0} color="#FF0000" icon="🚨" />
        <StatCard label="High Risk" value={data.risk_data?.filter(r => r.level === "HIGH").length || 0} color="#FF4500" icon="🔴" />
        <StatCard label="Medium Risk" value={data.risk_data?.filter(r => r.level === "MEDIUM").length || 0} color="#FFA500" icon="⚠️" />
      </div>

      {/* Bar Chart — full width */}
      <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 12, padding: "20px 24px", marginBottom: 20 }}>
        <div style={{ marginBottom: 16 }}>
          <div style={{ color: "#e6edf3", fontSize: 14, fontWeight: "bold" }}>Account Risk Scores</div>
          <div style={{ color: "#8b949e", fontSize: 11, marginTop: 2 }}>Ranked by suspicion level — red = CRITICAL, orange = HIGH, yellow = MEDIUM, green = SAFE</div>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data.risk_data} barCategoryGap="30%">
            <XAxis dataKey="account" tick={{ fill: "#8b949e", fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: "#8b949e", fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 100]} />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
            <Bar dataKey="score" radius={[6, 6, 0, 0]}>
              {data.risk_data.map((entry, i) => (
                <Cell key={i} fill={COLORS[entry.level] || "#27ae60"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Bottom Row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>

        {/* Pie Chart */}
        <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 12, padding: "20px 24px" }}>
          <div style={{ color: "#e6edf3", fontSize: 14, fontWeight: "bold", marginBottom: 4 }}>Risk Distribution</div>
          <div style={{ color: "#8b949e", fontSize: 11, marginBottom: 16 }}>Breakdown by risk level</div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={riskDist}
                cx="50%" cy="45%"
                innerRadius={55}
                outerRadius={80}
                paddingAngle={3}
                dataKey="value"
              >
                {riskDist.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 8 }} />
              <Legend formatter={(v) => <span style={{ color: "#8b949e", fontSize: 11 }}>{v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* City Pie */}
        <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 12, padding: "20px 24px" }}>
          <div style={{ color: "#e6edf3", fontSize: 14, fontWeight: "bold", marginBottom: 4 }}>Money by City</div>
          <div style={{ color: "#8b949e", fontSize: 11, marginBottom: 16 }}>Transaction origin distribution</div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={data.city_data}
                cx="50%" cy="45%"
                innerRadius={55}
                outerRadius={80}
                paddingAngle={3}
                dataKey="amount"
                nameKey="city"
              >
                {data.city_data.map((_, i) => (
                  <Cell key={i} fill={CITY_COLORS[i % CITY_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 8 }} formatter={(v) => fmt(v)} />
              <Legend formatter={(v) => <span style={{ color: "#8b949e", fontSize: 11 }}>{v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Line Chart */}
        <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 12, padding: "20px 24px" }}>
          <div style={{ color: "#e6edf3", fontSize: 14, fontWeight: "bold", marginBottom: 4 }}>Daily Volume</div>
          <div style={{ color: "#8b949e", fontSize: 11, marginBottom: 16 }}>Transaction flow over time</div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data.daily_data}>
              <XAxis dataKey="date" tick={{ fill: "#8b949e", fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#8b949e", fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={fmt} />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="amount"
                stroke="#e74c3c"
                strokeWidth={2.5}
                dot={{ fill: "#e74c3c", r: 5, strokeWidth: 2, stroke: "#0d1117" }}
                activeDot={{ r: 7, fill: "#ff6b6b" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

      </div>
    </div>
  );
}

export default Dashboard;
