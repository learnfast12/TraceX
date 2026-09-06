import React, { useEffect, useRef, useState } from "react";

const CITIES = {
  Delhi:     { x: 0.52, y: 0.22 },
  Mumbai:    { x: 0.35, y: 0.52 },
  Chennai:   { x: 0.52, y: 0.78 },
  Kolkata:   { x: 0.74, y: 0.36 },
  Bangalore: { x: 0.48, y: 0.70 },
  Pune:      { x: 0.38, y: 0.55 },
  Hyderabad: { x: 0.50, y: 0.60 },
  Ahmedabad: { x: 0.35, y: 0.32 },
  Jaipur:    { x: 0.44, y: 0.28 },
  Lucknow:   { x: 0.55, y: 0.30 },
  Nagpur:    { x: 0.50, y: 0.50 },
  Bhopal:    { x: 0.46, y: 0.42 },
  Surat:     { x: 0.34, y: 0.43 },
  Agra:        { x: 0.50, y: 0.26 },
  Kanpur:      { x: 0.55, y: 0.33 },
  Varanasi:    { x: 0.60, y: 0.38 },
  Patna:       { x: 0.65, y: 0.32 },
  Ranchi:      { x: 0.68, y: 0.42 },
  Bhubaneswar: { x: 0.72, y: 0.52 },
  Indore:      { x: 0.43, y: 0.46 },
  Goa:         { x: 0.38, y: 0.65 },
};

export default function CityMap({ graphData, onCityClick }) {
  const canvasRef = useRef(null);
  const animRef   = useRef(null);
  const [cityFlows, setCityFlows]       = useState([]);
  const [cityTotals, setCityTotals]     = useState({});
  const [selectedCity, setSelectedCity] = useState(null);
  const [investigate, setInvestigate]   = useState(null);
  const frameRef = useRef(0);

  useEffect(() => {
    fetch("http://localhost:8001/city/flows")
      .then(r => r.json())
      .then(d => {
        setCityFlows(d.city_flows || []);
        setCityTotals(d.city_totals || {});
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    function resize() {
      canvas.width  = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    const pts = [];
    cityFlows.forEach((f, fi) => {
      if (f.from_city === f.to_city) return;
      for (let p = 0; p < 2; p++) {
        pts.push({ fi, progress: Math.random(), speed: 0.004 + Math.random()*0.003 });
      }
    });

    function getFlowType(f) {
      const cashCount = (f.transactions||[]).filter(t=>t.transfer_type==="SUSPECTED_CASH").length;
      const total = (f.transactions||[]).length;
      if (total === 0) return "digital";
      return cashCount / total >= 0.5 ? "cash" : "digital";
    }

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

      const india = [
        [0.50,0.05],[0.55,0.06],[0.62,0.08],[0.68,0.12],[0.72,0.18],
        [0.75,0.25],[0.78,0.30],[0.80,0.38],[0.78,0.45],[0.74,0.50],
        [0.70,0.55],[0.65,0.62],[0.60,0.68],[0.58,0.74],[0.55,0.80],
        [0.52,0.85],[0.50,0.88],[0.48,0.85],[0.46,0.80],[0.44,0.74],
        [0.40,0.68],[0.35,0.62],[0.30,0.56],[0.26,0.48],[0.24,0.40],
        [0.25,0.32],[0.28,0.25],[0.32,0.18],[0.37,0.12],[0.42,0.08],
        [0.47,0.06],[0.50,0.05],
      ];
      ctx.beginPath();
      india.forEach(([px,py],i) => {
        i===0 ? ctx.moveTo(px*W, py*H) : ctx.lineTo(px*W, py*H);
      });
      ctx.closePath();
      const grad = ctx.createLinearGradient(0,0,0,H);
      grad.addColorStop(0,"rgba(88,166,255,0.07)");
      grad.addColorStop(1,"rgba(88,166,255,0.02)");
      ctx.fillStyle = grad; ctx.fill();
      ctx.strokeStyle = "rgba(88,166,255,0.2)";
      ctx.lineWidth = 1.5; ctx.stroke();

      cityFlows.forEach((f, fi) => {
        if (f.from_city === f.to_city) return;
        const fc = CITIES[f.from_city], tc = CITIES[f.to_city];
        if (!fc || !tc) return;

        const sx = fc.x*W, sy = fc.y*H;
        const tx = tc.x*W, ty = tc.y*H;
        const mx = (sx+tx)/2;
        const my = (sy+ty)/2 - Math.sqrt((tx-sx)**2+(ty-sy)**2)*0.3;

        const isSelected = selectedCity === f.from_city || selectedCity === f.to_city;
        const isRelated  = selectedCity && (f.from_city===selectedCity || f.to_city===selectedCity);
        const dimmed     = selectedCity && !isRelated;
        const flowType   = getFlowType(f);
        const isCash     = flowType === "cash";
        const baseR      = isCash ? "255,200,0" : "255,80,80";

        const alpha = dimmed ? 0.05 : isSelected ? 1 : 0.5;
        const lw    = isSelected ? Math.max(2, Math.min(5, f.total_amount/100000)) : isCash ? 2 : 1.5;

        if (isCash) { ctx.setLineDash([8, 4]); } else { ctx.setLineDash([]); }

        ctx.beginPath();
        ctx.moveTo(sx,sy);
        ctx.quadraticCurveTo(mx,my,tx,ty);
        ctx.strokeStyle = `rgba(${baseR},${alpha})`;
        ctx.lineWidth = lw;
        ctx.stroke();
        ctx.setLineDash([]);

        if (!dimmed) {
          const angle = Math.atan2(ty-my, tx-mx);
          ctx.beginPath();
          ctx.moveTo(tx,ty);
          ctx.lineTo(tx-10*Math.cos(angle-0.4), ty-10*Math.sin(angle-0.4));
          ctx.lineTo(tx-10*Math.cos(angle+0.4), ty-10*Math.sin(angle+0.4));
          ctx.closePath();
          ctx.fillStyle = `rgba(${baseR},${alpha})`; ctx.fill();
        }

        if (isSelected) {
          const lx2 = (sx+2*mx+tx)/4;
          const ly2 = (sy+2*my+ty)/4 - 10;
          ctx.font = "bold 10px monospace";
          ctx.fillStyle = isCash ? "rgba(255,200,0,0.85)" : "#fff";
          ctx.textAlign = "center";
          ctx.fillText("₹"+(f.total_amount/1000).toFixed(0)+"K", lx2, ly2);
        }
      });

      pts.forEach(p => {
        const f = cityFlows[p.fi];
        if (!f || f.from_city===f.to_city) return;
        const isRelated = !selectedCity || f.from_city===selectedCity || f.to_city===selectedCity;
        if (!isRelated) { p.progress+=p.speed; if(p.progress>1)p.progress=0; return; }

        const fc = CITIES[f.from_city], tc = CITIES[f.to_city];
        if (!fc||!tc) return;
        const sx=fc.x*W, sy=fc.y*H, tx2=tc.x*W, ty2=tc.y*H;
        const mx=(sx+tx2)/2, my2=(sy+ty2)/2-Math.sqrt((tx2-sx)**2+(ty2-sy)**2)*0.3;
        const t2=p.progress;
        const px2=(1-t2)*(1-t2)*sx+2*(1-t2)*t2*mx+t2*t2*tx2;
        const py2=(1-t2)*(1-t2)*sy+2*(1-t2)*t2*my2+t2*t2*ty2;
        const isCash = getFlowType(f) === "cash";
        ctx.beginPath(); ctx.arc(px2,py2,3,0,2*Math.PI);
        ctx.fillStyle = isCash ? "rgba(255,210,0,0.95)" : "rgba(255,100,100,0.9)"; ctx.fill();
        p.progress+=p.speed; if(p.progress>1)p.progress=0;
      });

      Object.entries(CITIES).forEach(([city, pos]) => {
        const x=pos.x*W, y=pos.y*H;
        const total = cityTotals[city] || 0;
        const isSelected2 = selectedCity===city;
        const hasFlow = cityFlows.some(f=>f.from_city===city||f.to_city===city);
        const isDimmed = selectedCity && !isSelected2 &&
          !cityFlows.some(f=>(f.from_city===selectedCity||f.to_city===selectedCity)&&(f.from_city===city||f.to_city===city));

        const r = isSelected2 ? 16 : total > 500000 ? 13 : total > 100000 ? 11 : 8;
        const alpha2 = isDimmed ? 0.2 : 1;

        if (isSelected2) {
          const pulse = Math.sin(frameRef.current*0.08)*0.5+0.5;
          ctx.beginPath(); ctx.arc(x,y,r+10+pulse*8,0,2*Math.PI);
          ctx.strokeStyle=`rgba(255,200,0,${0.4+pulse*0.4})`; ctx.lineWidth=2; ctx.stroke();
          const grd=ctx.createRadialGradient(x,y,r,x,y,r+25);
          grd.addColorStop(0,"rgba(255,200,0,0.3)"); grd.addColorStop(1,"rgba(0,0,0,0)");
          ctx.beginPath(); ctx.arc(x,y,r+25,0,2*Math.PI); ctx.fillStyle=grd; ctx.fill();
        }

        if (hasFlow && !isDimmed) {
          const grd=ctx.createRadialGradient(x,y,r,x,y,r+15);
          grd.addColorStop(0,`rgba(255,80,80,${0.3*alpha2})`);
          grd.addColorStop(1,"rgba(0,0,0,0)");
          ctx.beginPath(); ctx.arc(x,y,r+15,0,2*Math.PI); ctx.fillStyle=grd; ctx.fill();
        }

        ctx.beginPath(); ctx.arc(x,y,r,0,2*Math.PI);
        ctx.fillStyle = isSelected2
          ? "#FFD700"
          : hasFlow ? `rgba(231,76,60,${alpha2})` : `rgba(48,54,61,${alpha2})`;
        ctx.fill();
        ctx.strokeStyle = isSelected2 ? "#fff" : `rgba(255,255,255,${0.6*alpha2})`;
        ctx.lineWidth = isSelected2 ? 2.5 : 1.5; ctx.stroke();

        ctx.font = `bold ${isSelected2?13:11}px monospace`;
        ctx.fillStyle = isDimmed ? "rgba(255,255,255,0.15)" : isSelected2 ? "#FFD700" : "#e6edf3";
        ctx.textAlign = "center";
        ctx.fillText(city, x, y-r-6);
      });

      frameRef.current++;
    }

    function loop() { draw(); animRef.current=requestAnimationFrame(loop); }
    loop();
    return () => { cancelAnimationFrame(animRef.current); window.removeEventListener("resize",resize); };
  }, [cityFlows, cityTotals, selectedCity]);

  const handleCanvasClick = (e) => {
    const canvas = canvasRef.current;
    const rect   = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const W  = canvas.offsetWidth;
    const H  = canvas.offsetHeight;

    for (const [city, pos] of Object.entries(CITIES)) {
      const cx = pos.x*W, cy = pos.y*H;
      if (Math.sqrt((mx-cx)**2+(my-cy)**2) < 22) {
        if (selectedCity===city) {
          setSelectedCity(null); setInvestigate(null);
        } else {
          setSelectedCity(city);
          const related = cityFlows.filter(f=>f.from_city===city||f.to_city===city);
          setInvestigate({ city, flows: related });
        }
        return;
      }
    }
    setSelectedCity(null); setInvestigate(null);
  };

  const relatedFlows = investigate
    ? cityFlows.filter(f=>f.from_city===investigate.city||f.to_city===investigate.city)
    : [];

  return (
    <div style={{width:"100%",height:"100%",display:"flex",background:"#0d1117",position:"relative"}}>
      <div style={{flex:1,position:"relative"}}>
        <canvas
          ref={canvasRef}
          onClick={handleCanvasClick}
          style={{width:"100%",height:"100%",display:"block",cursor:"crosshair"}}
        />
        <div style={{position:"absolute",bottom:16,left:16,background:"rgba(22,27,34,0.92)",
          border:"1px solid #30363d",borderRadius:8,padding:"10px 16px",
          color:"#8b949e",fontSize:"11px",fontFamily:"monospace",display:"flex",gap:16,alignItems:"center"}}>
          <span>🗺 India Money Flow Map</span>
          <span style={{color:"#e74c3c"}}>━━ Digital Transfer</span>
          <span style={{color:"#FFD700"}}>╌╌ Hawala / Cash</span>
          {!selectedCity && <span style={{color:"#58a6ff"}}>Click any city to investigate</span>}
        </div>
      </div>

      {investigate && (
        <div style={{
          width:"320px", background:"#0d1117",
          borderLeft:"1px solid #21262d",
          overflowY:"auto", padding:"16px",
          fontFamily:"monospace",
        }}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:16}}>
            <div>
              <div style={{color:"#FFD700",fontSize:"1.1em",fontWeight:"bold"}}>
                📍 {investigate.city}
              </div>
              <div style={{color:"#8b949e",fontSize:"0.75em",marginTop:2}}>
                Total: ₹{((cityTotals[investigate.city]||0)/100000).toFixed(1)}L across {
                  relatedFlows.reduce((s,f)=>s+f.transactions.length,0)
                } transactions
              </div>
            </div>
            <button onClick={()=>{setSelectedCity(null);setInvestigate(null);}}
              style={{background:"transparent",border:"1px solid #30363d",color:"#8b949e",
                borderRadius:4,padding:"4px 8px",cursor:"pointer",fontSize:"0.8em"}}>
              ✕
            </button>
          </div>

          {relatedFlows.map((f,i) => (
            <div key={i} style={{
              background:"#161b22",border:"1px solid #21262d",
              borderRadius:8,padding:12,marginBottom:10
            }}>
              <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:8}}>
                <span style={{color: f.from_city===investigate.city?"#FF4500":"#8b949e",
                  fontWeight:"bold",fontSize:"0.85em"}}>
                  {f.from_city}
                </span>
                <span style={{color:"#555"}}>→</span>
                <span style={{color: f.to_city===investigate.city?"#00C853":"#8b949e",
                  fontWeight:"bold",fontSize:"0.85em"}}>
                  {f.to_city}
                </span>
                <span style={{marginLeft:"auto",color:"#FFD700",fontWeight:"bold",fontSize:"0.85em"}}>
                  ₹{(f.total_amount/1000).toFixed(0)}K
                </span>
              </div>

              {f.transactions.map((t,j) => (
                <div key={j} style={{
                  background:"#0d1117",borderRadius:6,padding:"6px 10px",
                  marginBottom:4,fontSize:"0.75em",
                  borderLeft:`2px solid ${t.transfer_type==="SUSPECTED_CASH"?"#FFD700":"#FF4500"}`
                }}>
                  <div style={{display:"flex",justifyContent:"space-between"}}>
                    <span style={{color:"#ff6b6b"}}>{t.sender}</span>
                    <span style={{color:"#00C853"}}>₹{(t.amount/1000).toFixed(0)}K</span>
                  </div>
                  <div style={{color:"#8b949e",marginTop:2}}>→ {t.receiver}</div>
                  <div style={{color:"#444",marginTop:2,display:"flex",justifyContent:"space-between"}}>
                    <span>{t.timestamp?.slice(0,10)}</span>
                    <span style={{color:t.transfer_type==="SUSPECTED_CASH"?"#FFD700":"#555"}}>
                      {t.transfer_type==="SUSPECTED_CASH"?"💵 CASH":"💳 DIGITAL"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ))}

          {relatedFlows.length===0 && (
            <div style={{color:"#555",textAlign:"center",marginTop:40,fontSize:"0.85em"}}>
              No inter-city flows from {investigate.city}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
