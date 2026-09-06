path_app = "/home/x0_shravan_0x/Tracenetx/frontend/tracenetx-ui/src/App.js"
with open(path_app, "r") as f:
    content = f.read()

def patch(old, new, label):
    global content
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"[{label}] expected 1 match, found {count}")
    content = content.replace(old, new)
    print(f"[{label}] patched OK")

# 1. Add state
patch(
    '  const [temporalData, setTemporalData] = useState(null);\n  const [temporalLoading, setTemporalLoading] = useState(false);',
    '  const [temporalData, setTemporalData] = useState(null);\n  const [temporalLoading, setTemporalLoading] = useState(false);\n  const [validationData, setValidationData] = useState(null);\n  const [validationLoading, setValidationLoading] = useState(false);',
    "add state"
)

# 2. Add fetch function, right after fetchTemporal
patch(
    '''  const fetchTemporal = async () => {
    setTemporalLoading(true);
    try {
      const res = await fetch("http://localhost:8001/temporal/analyze");
      const data = await res.json();
      setTemporalData(data);
    } catch (e) { console.error(e); }
    setTemporalLoading(false);
  };''',
    '''  const fetchTemporal = async () => {
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
  };''',
    "add fetch function"
)

# 3. Wire into tab switch handler
patch(
    '    if (tab === "temporal" && !temporalData) fetchTemporal();\n  };',
    '    if (tab === "temporal" && !temporalData) fetchTemporal();\n    if (tab === "validation" && !validationData) fetchValidation();\n  };',
    "wire tab switch"
)

# 4. Add tab button
patch(
    '            ["temporal", "⏱ Temporal"],\n            ["dashboard", "📊 Dashboard"],',
    '            ["temporal", "⏱ Temporal"],\n            ["validation", "🔬 Model Validation"],\n            ["dashboard", "📊 Dashboard"],',
    "add tab button"
)

# 5. Add render block, right after the temporal block closes and before evidence
anchor = '''        {activeTab === "evidence" && ('''

new_block = '''        {activeTab === "validation" && (
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

''' + anchor

count = content.count(anchor)
if count != 1:
    raise RuntimeError(f"[render block] expected 1 match for evidence anchor, found {count}")
content = content.replace(anchor, new_block)
print("[render block] patched OK")

with open(path_app, "w") as f:
    f.write(content)

print("\\nAll patches applied successfully.")
