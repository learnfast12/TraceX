import React, { useEffect, useRef } from "react";

const RISK_COLOR = {
  CRITICAL: "#FF2D2D",
  HIGH:     "#FF6B00",
  MEDIUM:   "#FFB300",
  SAFE:     "#00C853",
  CLEAR:    "#00C853",
  LOW:      "#00C853",
};

const RISK_SIZE = {
  CRITICAL: 44,
  HIGH:     36,
  MEDIUM:   30,
  SAFE:     24,
  CLEAR:    24,
  LOW:      24,
};

// tier_role comes from the backend (real chain-hop position / sweep
// membership) — never inferred from the wallet address string.
const ROLE_TIER = {
  source:      0,
  hop:         1,
  peel_sink:   2,
  sweep_input: 3,
  sweep_vault: 4,
  sink:        4,
};

function getTier(node) {
  return ROLE_TIER[node.tier_role] ?? 1;
}

function shortLabel(id) {
  if (id.length <= 12) return id;
  return id.slice(0, 6) + "…" + id.slice(-4);
}

function formatBTC(amount) {
  if (amount === null || amount === undefined) return null;
  return "₿" + Number(amount).toFixed(4);
}

function SpiderMap({ graphData, onNodeClick, organized = true }) {
  const canvasRef = useRef(null);
  const stateRef  = useRef({ selectedId: null, pulseFrame: 0, particles: [], animId: null });

  useEffect(() => {
    if (!graphData.nodes.length) return;

    const canvas = canvasRef.current;
    const ctx    = canvas.getContext("2d");
    const rect   = canvas.getBoundingClientRect();
    const DPR    = window.devicePixelRatio || 1;
    canvas.width  = rect.width  * DPR;
    canvas.height = rect.height * DPR;
    ctx.scale(DPR, DPR);
    const W = rect.width;
    const H = rect.height;

    const state = stateRef.current;
    const edges = graphData.edges || [];
    const nodes = graphData.nodes || [];

    /* ── TIER TARGET POSITIONS ────────────────────────────────── */
    const tiers = { 0:[], 1:[], 2:[], 3:[], 4:[] };
    nodes.forEach(n => { tiers[getTier(n)].push(n); });

    const TIER_Y = { 0:H*0.08, 1:H*0.28, 2:H*0.48, 3:H*0.68, 4:H*0.90 };

    const tierTargets = {};
    [0,1,2,3,4].forEach(ti => {
      const group = tiers[ti];
      if (!group.length) return;
      const pad = 80;
      const step = (W - pad*2) / Math.max(group.length, 1);
      group.forEach((n, i) => {
        tierTargets[n.id] = {
          x: group.length === 1 ? W/2 : pad + step*i + step/2,
          y: TIER_Y[ti],
        };
      });
    });

    /* ── FORCE-DIRECTED RAW POSITIONS ──────────────────────────── */
    const positions = {};
    nodes.forEach((n, i) => {
      const angle = (2*Math.PI*i)/nodes.length - Math.PI/2;
      const r = Math.min(W,H)*0.35;
      positions[n.id] = {
        x: W/2 + r*Math.cos(angle),
        y: H/2 + r*Math.sin(angle),
        vx: 0, vy: 0, node: n,
      };
    });

    state.lerpT      = state.lerpT ?? (organized ? 1 : 0);
    state.lerpTarget = organized ? 1 : 0;

    function tick() {
      const tgt = state.lerpTarget;
      state.lerpT += (tgt - state.lerpT) * 0.06;
      if (state.lerpT > 0.95) state.lerpT = 1.0;

      const ids = Object.keys(positions);

      if (state.lerpT < 1.0) {
        for (let i = 0; i < ids.length; i++) {
          for (let j = i+1; j < ids.length; j++) {
            const a = positions[ids[i]], b = positions[ids[j]];
            const dx = b.x-a.x, dy = b.y-a.y;
            const dist = Math.sqrt(dx*dx+dy*dy)||1;
            const aCritical = a.node?.risk?.level === "CRITICAL";
            const bCritical = b.node?.risk?.level === "CRITICAL";
            const boost = (aCritical || bCritical) ? 1.1 : 1;
            const force = (12000*boost)/(dist*dist);
            const fx = dx/dist*force, fy = dy/dist*force;
            a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy;
          }
        }
        edges.forEach(e => {
          const a = positions[e.source], b = positions[e.target];
          if (!a||!b) return;
          const dx=b.x-a.x, dy=b.y-a.y, dist=Math.sqrt(dx*dx+dy*dy)||1;
          const aCritical = a.node?.risk?.level === "CRITICAL";
          const bCritical = b.node?.risk?.level === "CRITICAL";
          const targetDist = (aCritical || bCritical) ? 240 : 180;
          const force=(dist-targetDist)*0.03;
          const fx=dx/dist*force, fy=dy/dist*force;
          a.vx+=fx; a.vy+=fy; b.vx-=fx; b.vy-=fy;
        });
        ids.forEach(id => {
          const p = positions[id];
          const tier = getTier(p.node);
          let pullX = W/2, pullY = H/2, pull = 0.004;
          if (tier === 0) { pullX = W/2; pullY = H * 0.2; pull = 0.05; }
          else if (tier === 4) { pullX = W/2; pullY = H * 0.85; pull = 0.05; }
          p.vx += (pullX-p.x)*pull; p.vy += (pullY-p.y)*pull;
          p.vx *= 0.6; p.vy *= 0.6;
          p.x = Math.max(55, Math.min(W-55, p.x+p.vx));
          p.y = Math.max(55, Math.min(H-55, p.y+p.vy));
        });
      }

      const lt = Math.min(state.lerpT, 1);
      ids.forEach(id => {
        const p = positions[id];
        const tgt = tierTargets[id];
        if (!tgt) return;
        if (lt > 0.01) {
          const dx = tgt.x - p.x, dy = tgt.y - p.y;
          if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) {
            p.x += dx * lt * 0.12;
            p.y += dy * lt * 0.12;
          } else {
            p.x = tgt.x; p.y = tgt.y;
          }
        }
      });
    }

    state.particles = [];
    edges.forEach((e, ei) => {
      const count = (e.transfer_type === "SWEEP_CONVERGE") ? 1 : 3;
      for (let p = 0; p < count; p++) {
        state.particles.push({
          ei, progress: Math.random(),
          speed: 0.0012 + Math.random() * 0.0012,
        });
      }
    });

    function draw() {
      ctx.clearRect(0, 0, W, H);

      ctx.fillStyle = "rgba(255,255,255,0.025)";
      for (let x = 40; x < W; x += 55)
        for (let y = 40; y < H; y += 55) {
          ctx.beginPath(); ctx.arc(x, y, 1, 0, 2*Math.PI); ctx.fill();
        }

      const bands = [
        { y: TIER_Y[0], label: "SOURCE WALLET",     col: "rgba(255,45,45,0.08)"  },
        { y: TIER_Y[1], label: "CHAIN HOP",         col: "rgba(255,107,0,0.06)"  },
        { y: TIER_Y[2], label: "PEELED OFF",        col: "rgba(255,179,0,0.06)"  },
        { y: TIER_Y[3], label: "SWEEP INPUT",       col: "rgba(0,200,83,0.04)"   },
        { y: TIER_Y[4], label: "COLLECTION VAULT",  col: "rgba(0,100,255,0.07)"  },
      ];
      if (state.lerpT > 0.1) bands.forEach(b => {
        ctx.fillStyle = b.col;
        ctx.fillRect(0, b.y - 52, W, 104);
        ctx.font = "bold 10px monospace";
        ctx.fillStyle = "rgba(255,255,255,0.10)";
        ctx.textAlign = "left";
        ctx.globalAlpha = Math.min(state.lerpT, 1);
        ctx.fillText(b.label, 14, b.y - 36);
        ctx.globalAlpha = 1;
      });

      edges.forEach(e => {
        const s = positions[e.source];
        const t = positions[e.target];
        if (!s || !t) return;

        const isSweep    = e.transfer_type === "SWEEP_CONVERGE";
        const sLevel     = s.node.risk?.level || "CLEAR";
        const isSelected = state.selectedId === e.source || state.selectedId === e.target;

        const edgeColor = isSweep
          ? (isSelected ? "rgba(255,220,80,0.9)" : "rgba(255,220,80,0.4)")
          : sLevel === "CRITICAL"
            ? (isSelected ? "rgba(255,45,45,0.95)" : "rgba(255,45,45,0.5)")
            : sLevel === "HIGH"
              ? (isSelected ? "rgba(255,107,0,0.9)" : "rgba(255,107,0,0.35)")
              : (isSelected ? "rgba(88,166,255,0.8)" : "rgba(88,166,255,0.18)");

        const cx = (s.x + t.x) / 2;
        const cy = (s.y + t.y) / 2;

        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.quadraticCurveTo(cx, cy, t.x, t.y);

        if (isSweep) {
          ctx.setLineDash([6, 5]);
          ctx.lineWidth = isSelected ? 2 : 1.5;
        } else {
          ctx.setLineDash([]);
          ctx.lineWidth = isSelected ? 2.8 : (sLevel === "CRITICAL" ? 2 : 1.2);
        }
        ctx.strokeStyle = edgeColor;
        ctx.stroke();
        ctx.setLineDash([]);

        const angle = Math.atan2(t.y - cy, t.x - cx);
        const rNode = RISK_SIZE[t.node?.risk?.level] || 24;
        const ax = t.x - (rNode + 2) * Math.cos(angle);
        const ay = t.y - (rNode + 2) * Math.sin(angle);
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(ax - 10*Math.cos(angle-0.42), ay - 10*Math.sin(angle-0.42));
        ctx.lineTo(ax - 10*Math.cos(angle+0.42), ay - 10*Math.sin(angle+0.42));
        ctx.closePath();
        ctx.fillStyle = isSweep ? "rgba(255,220,80,0.7)" : edgeColor;
        ctx.fill();

        const amtLabel = formatBTC(e.amount);
        const midX = 0.25*s.x + 0.5*cx + 0.25*t.x;
        const midY = 0.25*s.y + 0.5*cy + 0.25*t.y - 7;
        if (amtLabel && Math.abs(t.x - s.x) + Math.abs(t.y - s.y) > 60) {
          ctx.font = "9px monospace";
          ctx.fillStyle = isSelected ? "#fff" : (isSweep ? "rgba(255,220,80,0.7)" : "rgba(150,150,150,0.7)");
          ctx.textAlign = "center";
          ctx.fillText(amtLabel, midX, midY);
        }
      });

      state.particles.forEach(p => {
        const e = edges[p.ei];
        if (!e) return;
        const s = positions[e.source];
        const t = positions[e.target];
        if (!s || !t) return;
        if (e.transfer_type === "SWEEP_CONVERGE") { p.progress += p.speed; if(p.progress>1) p.progress=0; return; }
        const sLevel = s.node?.risk?.level;
        const t2 = p.progress;
        const cx = (s.x+t.x)/2;
        const cy = (s.y+t.y)/2;
        const px = (1-t2)*(1-t2)*s.x + 2*(1-t2)*t2*cx + t2*t2*t.x;
        const py = (1-t2)*(1-t2)*s.y + 2*(1-t2)*t2*cy + t2*t2*t.y;
        ctx.beginPath();
        ctx.arc(px, py, sLevel==="CRITICAL" ? 3.5 : 2.5, 0, 2*Math.PI);
        ctx.fillStyle = sLevel==="CRITICAL"
          ? "rgba(255,45,45,0.95)"
          : sLevel==="HIGH" ? "rgba(255,107,0,0.85)"
          : "rgba(88,166,255,0.6)";
        ctx.fill();
        p.progress += p.speed;
        if (p.progress > 1) p.progress = 0;
      });

      Object.values(positions).forEach(p => {
        const n      = p.node;
        const level  = n.risk?.level || "CLEAR";
        const color  = RISK_COLOR[level] || "#00C853";
        const r      = RISK_SIZE[level]  || 24;
        const isSelected = state.selectedId === n.id;

        if (level === "CRITICAL") {
          const pulse = Math.sin(state.pulseFrame * 0.13) * 0.5 + 0.5;
          const grd = ctx.createRadialGradient(p.x, p.y, r, p.x, p.y, r+28);
          grd.addColorStop(0, `rgba(255,45,45,${0.25 + pulse*0.25})`);
          grd.addColorStop(1, "rgba(0,0,0,0)");
          ctx.beginPath(); ctx.arc(p.x, p.y, r+28, 0, 2*Math.PI);
          ctx.fillStyle = grd; ctx.fill();
          ctx.beginPath(); ctx.arc(p.x, p.y, r+10+pulse*10, 0, 2*Math.PI);
          ctx.strokeStyle = `rgba(255,45,45,${0.5+pulse*0.4})`;
          ctx.lineWidth = 2; ctx.stroke();
        }

        if (level === "HIGH") {
          const grd = ctx.createRadialGradient(p.x, p.y, r, p.x, p.y, r+18);
          grd.addColorStop(0, "rgba(255,107,0,0.3)");
          grd.addColorStop(1, "rgba(0,0,0,0)");
          ctx.beginPath(); ctx.arc(p.x, p.y, r+18, 0, 2*Math.PI);
          ctx.fillStyle = grd; ctx.fill();
        }

        if (isSelected) {
          const pulse = Math.sin(state.pulseFrame * 0.1) * 0.5 + 0.5;
          ctx.beginPath(); ctx.arc(p.x, p.y, r+13+pulse*5, 0, 2*Math.PI);
          ctx.strokeStyle = `rgba(255,255,255,${0.4+pulse*0.4})`;
          ctx.lineWidth = 2.5; ctx.stroke();
        }

        ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, 2*Math.PI);
        const fill = ctx.createRadialGradient(p.x-r*0.3, p.y-r*0.3, 1, p.x, p.y, r);
        fill.addColorStop(0, color + "ff");
        fill.addColorStop(1, color + "99");
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.strokeStyle = isSelected ? "#fff" : color;
        ctx.lineWidth   = isSelected ? 3 : 1.8;
        ctx.stroke();

        const label = shortLabel(n.id);
        ctx.font = `bold 9px monospace`;
        ctx.fillStyle = "#fff";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(label, p.x, p.y);

        ctx.font = "bold 8px monospace";
        ctx.fillStyle = color;
        ctx.textBaseline = "top";
        const badge = level === "CLEAR" ? "SAFE" : level;
        ctx.fillText(badge, p.x, p.y + r + 4);
      });

      state.pulseFrame++;
    }

    for (let i = 0; i < 600; i++) tick();
    Object.values(positions).forEach(p => { p.vx = 0; p.vy = 0; });

    function loop() {
      draw();
      state.animId = requestAnimationFrame(loop);
    }
    loop();

    const handleClick = e => {
      const br = canvas.getBoundingClientRect();
      const mx = e.clientX - br.left;
      const my = e.clientY - br.top;
      for (const id in positions) {
        const p = positions[id];
        if (Math.sqrt((mx-p.x)**2 + (my-p.y)**2) < 50) {
          state.selectedId = id;
          onNodeClick(id);
          break;
        }
      }
    };
    canvas.addEventListener("click", handleClick);
    return () => { cancelAnimationFrame(state.animId); canvas.removeEventListener("click", handleClick); };
  }, [graphData, organized]);

  return (
    <canvas ref={canvasRef} style={{
      width:"100%", height:"100%",
      background:"#0d1117",
      borderRadius:"12px",
      cursor:"crosshair",
      display:"block",
    }} />
  );
}

export default SpiderMap;
