import re

path = "real_validation.py"
with open(path, "r") as f:
    src = f.read()

# 1. Add average_precision_score to the sklearn import
old_import = "from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score, confusion_matrix, brier_score_loss"
new_import = "from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score, confusion_matrix, brier_score_loss, average_precision_score"
assert src.count(old_import) == 1, "import line not found or not unique"
src = src.replace(old_import, new_import)

# 2. Add per-fold AUPRC into the fold_results dict in _run_cv
old_fold_dict = '''        fold_results.append({
            "fold": fold,
            "auc_roc": round(float(roc_auc_score(y_test, y_proba)), 4),
            "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
            "f1_score": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
            "brier_score": brier,
            "expected_calibration_error": ece,
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
            "test_positive_count": int(y_test.sum()),
            "test_size": int(len(y_test)),
        })'''
new_fold_dict = '''        fold_results.append({
            "fold": fold,
            "auc_roc": round(float(roc_auc_score(y_test, y_proba)), 4),
            "auprc": round(float(average_precision_score(y_test, y_proba)), 4),
            "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
            "f1_score": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
            "brier_score": brier,
            "expected_calibration_error": ece,
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
            "test_positive_count": int(y_test.sum()),
            "test_size": int(len(y_test)),
        })'''
assert src.count(old_fold_dict) == 1, "fold_results.append block not found or not unique"
src = src.replace(old_fold_dict, new_fold_dict)

# 3. Aggregate AUPRC alongside the existing aucs/precisions/etc lists
old_agg = '''    aucs = [f["auc_roc"] for f in fold_results]
    precisions = [f["precision"] for f in fold_results]
    recalls = [f["recall"] for f in fold_results]
    f1s = [f["f1_score"] for f in fold_results]
    briers = [f["brier_score"] for f in fold_results]
    eces = [f["expected_calibration_error"] for f in fold_results]'''
new_agg = '''    aucs = [f["auc_roc"] for f in fold_results]
    auprcs = [f["auprc"] for f in fold_results]
    precisions = [f["precision"] for f in fold_results]
    recalls = [f["recall"] for f in fold_results]
    f1s = [f["f1_score"] for f in fold_results]
    briers = [f["brier_score"] for f in fold_results]
    eces = [f["expected_calibration_error"] for f in fold_results]'''
assert src.count(old_agg) == 1, "aggregation block not found or not unique"
src = src.replace(old_agg, new_agg)

# 4. Add mean/std AUPRC to the cross_validation dict
old_cv_dict = '''            "mean_precision": round(float(np.mean(precisions)), 4),
            "mean_recall": round(float(np.mean(recalls)), 4),
            "mean_f1_score": round(float(np.mean(f1s)), 4),
        },'''
new_cv_dict = '''            "mean_precision": round(float(np.mean(precisions)), 4),
            "mean_recall": round(float(np.mean(recalls)), 4),
            "mean_f1_score": round(float(np.mean(f1s)), 4),
            "mean_auprc": round(float(np.mean(auprcs)), 4),
            "std_auprc": round(float(np.std(auprcs)), 4),
        },'''
assert src.count(old_cv_dict) == 1, "cross_validation dict not found or not unique"
src = src.replace(old_cv_dict, new_cv_dict)

# 5. After the final_model / SHAP block, add freeze-tier precision + residual-leak check,
#    computed on the same held-out test split already used for SHAP.
old_shap_end = '''    top_features = [
        {"feature": feature_cols[i], "mean_abs_shap_impact": round(float(mean_abs_shap[i]), 4)}
        for i in top_idx
    ]

    _cached_result = {'''
new_shap_end = '''    top_features = [
        {"feature": feature_cols[i], "mean_abs_shap_impact": round(float(mean_abs_shap[i]), 4)}
        for i in top_idx
    ]

    # --- HIGH-risk freeze-tier precision (mirrors MuleGuard's 69/70 = 98.6% style claim) ---
    final_proba = final_model.predict_proba(X_test)[:, 1]
    y_test_arr = y_test.values if hasattr(y_test, "values") else np.asarray(y_test)
    freeze_threshold = 0.9
    freeze_mask = final_proba >= freeze_threshold
    freeze_flagged = int(freeze_mask.sum())
    freeze_true_positives = int(y_test_arr[freeze_mask].sum())
    freeze_tier = {
        "threshold": freeze_threshold,
        "flagged_count": freeze_flagged,
        "true_positive_count": freeze_true_positives,
        "precision_pct": round((freeze_true_positives / freeze_flagged) * 100, 2) if freeze_flagged > 0 else None,
        "note": "Computed on the held-out 20% test split (same split used for SHAP), not cross-validated.",
    }

    # --- Residual-leak check: max univariate AUROC across all finalized features post-cleaning ---
    univariate_aurocs = []
    for col in feature_cols:
        col_vals = X_test_raw[col].fillna(0).values if hasattr(X_test_raw[col], "fillna") else X_test_raw[col]
        try:
            auc = roc_auc_score(y_test, col_vals)
            auc = max(auc, 1 - auc)  # direction-agnostic
        except ValueError:
            continue
        univariate_aurocs.append((col, float(auc)))
    univariate_aurocs.sort(key=lambda x: x[1], reverse=True)
    residual_leak_check = {
        "top_5_univariate_features": [
            {"feature": f, "univariate_auroc": round(a, 4)} for f, a in univariate_aurocs[:5]
        ],
        "max_univariate_auroc": round(univariate_aurocs[0][1], 4) if univariate_aurocs else None,
        "note": "Direction-agnostic univariate AUROC per finalized feature, computed on held-out test split, to confirm no single column silently leaks the target after F2230/F3912 exclusion.",
    }

    _cached_result = {'''
assert src.count(old_shap_end) == 1, "SHAP top_features block not found or not unique"
src = src.replace(old_shap_end, new_shap_end)

# 6. Wire freeze_tier and residual_leak_check into the returned dict, next to shap_top_features
old_note_block = '''        "shap_top_features": top_features,
        "note": ('''
new_note_block = '''        "shap_top_features": top_features,
        "high_risk_freeze_tier": freeze_tier,
        "residual_leak_check": residual_leak_check,
        "note": ('''
assert src.count(old_note_block) == 1, "shap_top_features/note block not found or not unique"
src = src.replace(old_note_block, new_note_block)

with open(path, "w") as f:
    f.write(src)

print("Patch applied cleanly. Diff summary:")
print("  + average_precision_score import")
print("  + per-fold auprc in fold_results")
print("  + mean_auprc / std_auprc in cross_validation")
print("  + high_risk_freeze_tier (threshold=0.9) in top-level result")
print("  + residual_leak_check (max univariate AUROC) in top-level result")
