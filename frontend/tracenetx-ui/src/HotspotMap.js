import React, { useEffect, useRef, useState } from "react";

// Real lat/lng bounding box for India
const BOUNDS = { latMin: 6, latMax: 37, lngMin: 68, lngMax: 98 };

function project(lat, lng, W, H) {
  const x = (lng - BOUNDS.lngMin) / (BOUNDS.lngMax - BOUNDS.lngMin);
  const y = 1 - (lat - BOUNDS.latMin) / (BOUNDS.latMax - BOUNDS.latMin);
  return { x: x * W, y: y * H };
}

const SEVERITY_COLOR = {
  critical: "255,59,59",
  high:     "255,149,0",
  medium:   "255,215,0",
  low:      "63,185,80",
};

const TYPE_LABEL = {
  digital_arrest: "Digital Arrest Scam",
  fraud_ring:      "Fraud Ring Activity",
  counterfeit:     "Counterfeit Currency",
  cybercrime:      "Cybercrime Cluster",
};

function riskScore(h) {
  const sevWeight = { critical: 40, high: 25, medium: 12, low: 5 }[h.severity] || 0;
  const trendBonus = h.trend === "rising" ? 15 : h.trend === "stable" ? 0 : -8;
  return sevWeight + h.incidents_24h * 1.5 + trendBonus;
}

export default function HotspotMap({ hotspots: propHotspots }) {
  const canvasRef = useRef(null);
  const animRef = useRef(null);
  const frameRef = useRef(0);
  const [hotspots, setHotspots] = useState(propHotspots || []);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (propHotspots) return;
    fetch("http://localhost:8001/geospatial/hotspots")
      .then(r => r.json())
      .then(d => setHotspots(d.hotspots || []))
      .catch(() => {});
  }, [propHotspots]);

  const ranked = [...hotspots].sort((a, b) => riskScore(b) - riskScore(a));

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    function resize() {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    const india = [
      [0.50,0.05],[0.55,0.06],[0.62,0.08],[0.68,0.12],[0.72,0.18],
      [0.75,0.25],[0.78,0.30],[0.80,0.38],[0.78,0.45],[0.74,0.50],
      [0.70,0.55],[0.65,0.62],[0.60,0.68],[0.58,0.74],[0.55,0.80],
      [0.52,0.85],[0.50,0.88],[0.48,0.85],[0.46,0.80],[0.44,0.74],
      [0.40,0.68],[0.35,0.62],[0.30,0.56],[0.26,0.48],[0.24,0.40],
      [0.25,0.32],[0.28,0.25],[0.32,0.18],[0.37,0.12],[0.42,0.08],
      [0.47,0.06],[0.50,0.05],
    ];

    function draw() {
      const W = canvas.width, H = canvas.height;
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = "#0d1117";
      ctx.fillRect(0, 0, W, H);

      ctx.fillStyle = "rgba(255,255,255,0.025)";
      for (let x = 25; x < W; x += 40)
        for (let y = 25; y < H; y += 40) {
          ctx.beginPath(); ctx.arc(x, y, 1, 0, 2*Math.PI); ctx.fill();
        }

      ctx.beginPath();
      india.forEach(([px,py],i) => i===0 ? ctx.moveTo(px*W,py*H) : ctx.lineTo(px*W,py*H));
      ctx.closePath();
      const grad = ctx.createLinearGradient(0,0,0,H);
      grad.addColorStop(0,"rgba(88,166,255,0.06)");
      grad.addColorStop(1,"rgba(88,166,255,0.015)");
      ctx.fillStyle = grad; ctx.fill();
      ctx.strokeStyle = "rgba(88,166,255,0.18)";
      ctx.lineWidth = 1.5; ctx.stroke();

      hotspots.forEach(h => {
        const { x, y } = project(h.lat, h.lng, W, H);
        const color = SEVERITY_COLOR[h.severity] || "150,150,150";
        const baseR = 6 + Math.min(h.incidents_24h, 30) * 0.6;
        const isSelected = selected && selected.id === h.id;
        const pulse = Math.sin(frameRef.current * 0.05 + h.lat) * 0.5 + 0.5;

        const coronaR = baseR + 14 + pulse * (h.trend === "rising" ? 14 : 6);
        const cGrad = ctx.createRadialGradient(x,y,baseR,x,y,coronaR);
        cGrad.addColorStop(0, `rgba(${color},${isSelected?0.35:0.22})`);
        cGrad.addColorStop(1, "rgba(0,0,0,0)");
        ctx.beginPath(); ctx.arc(x,y,coronaR,0,2*Math.PI);
        ctx.fillStyle = cGrad; ctx.fill();

        ctx.beginPath(); ctx.arc(x,y,baseR,0,2*Math.PI);
        ctx.fillStyle = `rgba(${color},${isSelected?1:0.85})`;
        ctx.fill();
        ctx.strokeStyle = isSelected ? "#fff" : `rgba(255,255,255,0.5)`;
        ctx.lineWidth = isSelected ? 2.5 : 1.2;
        ctx.stroke();

        if (h.incidents_24h > 0) {
          ctx.font = "bold 9px monospace";
          ctx.fillStyle = "#0d1117";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(h.incidents_24h, x, y);
        }

        ctx.font = `bold ${isSelected?12:10}px monospace`;
        ctx.fillStyle = isSelected ? `rgb(${color})` : "#e6edf3";
        ctx.textAlign = "center";
        ctx.textBaseline = "alphabetic";
        ctx.fillText(h.name, x, y - baseR - 10);
      });

      frameRef.current++;
    }

    function loop() { draw(); animRef.current = requestAnimationFrame(loop); }
    loop();
    return () => { cancelAnimationFrame(animRef.current); window.removeEventListener("resize", resize); };
  }, [hotspots, selected]);

  const handleCanvasClick = (e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const W = canvas.offsetWidth, H = canvas.offsetHeight;

    for (const h of hotspots) {
      const { x, y } = project(h.lat, h.lng, W, H);
      if (Math.sqrt((mx-x)**2 + (my-y)**2) < 24) {
        setSelected(selected && selected.id === h.id ? null : h);
        return;
      }
    }
    setSelected(null);
  };

  return (
    <div style={{width:"100%",height:"100%",display:"flex",background:"#0d1117"}}>
      <div style={{flex:1,position:"relative"}}>
        <canvas ref={canvasRef} onClick={handleCanvasClick}
          style={{width:"100%",height:"100%",display:"block",cursor:"crosshair"}} />

        <div style={{position:"absolute",top:16,left:16,right:16,display:"flex",
          justifyContent:"space-between",fontFamily:"monospace",fontSize:"11px"}}>
          <div style={{display:"flex",gap:16,background:"rgba(22,27,34,0.92)",
            border:"1px solid #30363d",borderRadius:8,padding:"8px 16px",color:"#8b949e"}}>
            <span style={{color:"#3fb950",display:"flex",alignItems:"center",gap:6}}>
              <span style={{width:7,height:7,borderRadius:"50%",background:"#3fb950",
                boxShadow:"0 0 6px #3fb950"}} /> LIVE
            </span>
            <span>Active Hotspots: <b style={{color:"#e6edf3"}}>{hotspots.length}</b></span>
            <span>Incidents (24h): <b style={{color:"#e6edf3"}}>
              {hotspots.reduce((s,h)=>s+h.incidents_24h,0)}</b></span>
          </div>
        </div>

        <div style={{position:"absolute",bottom:16,left:16,background:"rgba(22,27,34,0.92)",
          border:"1px solid #30363d",borderRadius:8,padding:"10px 16px",
          color:"#8b949e",fontSize:"11px",fontFamily:"monospace",display:"flex",gap:14}}>
          {Object.entries(SEVERITY_COLOR).map(([sev,rgb]) => (
            <span key={sev} style={{color:`rgb(${rgb})`}}>● {sev}</span>
          ))}
        </div>
      </div>

      <div style={{width:"320px",background:"#0d1117",borderLeft:"1px solid #21262d",
        overflowY:"auto",padding:"16px",fontFamily:"monospace"}}>
        <div style={{color:"#e6edf3",fontSize:"1em",fontWeight:"bold",marginBottom:4}}>
          🚨 Patrol Priority Queue
        </div>
        <div style={{color:"#8b949e",fontSize:"0.7em",marginBottom:14}}>
          Ranked by severity × velocity × trend
        </div>

        {ranked.map((h, i) => {
          const score = riskScore(h);
          const color = SEVERITY_COLOR[h.severity] || "150,150,150";
          const isSelected = selected && selected.id === h.id;
          return (
            <div key={h.id} onClick={() => setSelected(h)}
              style={{
                background: isSelected ? "#1c2128" : "#161b22",
                border: `1px solid ${isSelected ? `rgb(${color})` : "#21262d"}`,
                borderRadius:8, padding:12, marginBottom:8, cursor:"pointer"
              }}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <span style={{color:"#58a6ff",fontWeight:"bold",fontSize:"0.75em"}}>#{i+1}</span>
                <span style={{color:`rgb(${color})`,fontWeight:"bold",fontSize:"0.9em",flex:1,marginLeft:8}}>
                  {h.name}
                </span>
                <span style={{color:"#e6edf3",fontWeight:"bold",fontSize:"0.8em"}}>
                  {score.toFixed(0)}
                </span>
              </div>
              <div style={{color:"#8b949e",fontSize:"0.7em",marginTop:6}}>
                {TYPE_LABEL[h.type] || h.type} · {h.incidents_24h} incidents/24h
              </div>
              <div style={{marginTop:4,fontSize:"0.7em",
                color: h.trend==="rising" ? "#ff3b3b" : h.trend==="falling" ? "#3fb950" : "#8b949e"}}>
                {h.trend==="rising" ? "▲ Rising" : h.trend==="falling" ? "▼ Falling" : "— Stable"}
              </div>
            </div>
          );
        })}

        {selected && (
          <div style={{marginTop:16,paddingTop:16,borderTop:"1px solid #21262d"}}>
            <div style={{color:"#FFD700",fontWeight:"bold",marginBottom:8,fontSize:"0.85em"}}>
              📍 {selected.name} — Detail
            </div>
            <div style={{color:"#8b949e",fontSize:"0.75em",lineHeight:1.8}}>
              <div>Type: <span style={{color:"#e6edf3"}}>{TYPE_LABEL[selected.type]}</span></div>
              <div>Severity: <span style={{color:`rgb(${SEVERITY_COLOR[selected.severity]})`}}>{selected.severity}</span></div>
              <div>Incidents (24h): <span style={{color:"#e6edf3"}}>{selected.incidents_24h}</span></div>
              <div>Incidents (7d): <span style={{color:"#e6edf3"}}>{selected.incidents_7d}</span></div>
              <div>Risk Score: <span style={{color:"#e6edf3"}}>{riskScore(selected).toFixed(1)}</span></div>
              <div>Recommended: <span style={{color:"#e6edf3"}}>
                {riskScore(selected) > 50 ? "Immediate patrol dispatch" : riskScore(selected) > 25 ? "Increased surveillance" : "Routine monitoring"}
              </span></div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
