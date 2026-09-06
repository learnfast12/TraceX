path = "main.py"
with open(path) as f:
    src = f.read()

anchor = '# ── V2.0 ML ENDPOINTS ───────────────────────────────────────────────'
assert src.count(anchor) == 1, "anchor not found or not unique — aborting, no changes made"

new_endpoint = '''@app.get("/model-validation")
def get_model_validation():
    result = run_real_validation()
    if result.get("status") != "validated":
        return {"status": result.get("status", "unavailable"), "message": result.get("message")}

    cv = result.get("cross_validation", {})
    freeze = result.get("high_risk_freeze_tier", {})
    leak = result.get("residual_leak_check", {})
    top_feat = leak.get("top_5_univariate_features", [{}])[0] if leak.get("top_5_univariate_features") else {}

    return {
        "status": "validated",
        "dataset": result.get("dataset"),
        "auprc_mean": cv.get("mean_auprc"),
        "auroc_mean": cv.get("mean_auc_roc"),
        "precision_mean": cv.get("mean_precision"),
        "recall_mean": cv.get("mean_recall"),
        "f1_mean": cv.get("mean_f1_score"),
        "freeze_tier": {
            "label": "HIGH-RISK AUTO-FREEZE",
            "threshold": freeze.get("threshold"),
            "precision": (freeze.get("precision_pct") / 100.0) if freeze.get("precision_pct") is not None else None,
            "n_flagged": freeze.get("flagged_count"),
            "n_correct": freeze.get("true_positive_count"),
            "note": freeze.get("note"),
        },
        "leak_audit": {
            "top_residual_feature": top_feat.get("feature"),
            "univariate_auroc": top_feat.get("univariate_auroc"),
            "max_univariate_auroc": leak.get("max_univariate_auroc"),
            "note": leak.get("note"),
        },
    }

'''

src = src.replace(anchor, new_endpoint + anchor)
with open(path, "w") as f:
    f.write(src)
print("Patched main.py — /model-validation endpoint added.")
