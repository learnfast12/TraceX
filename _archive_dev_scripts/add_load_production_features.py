path_backend = "/home/x0_shravan_0x/Tracenetx/backend/ml_pipeline.py"
with open(path_backend, "r") as f:
    content = f.read()

anchor = "    def load_real_dataset(self, csv_path):"

if anchor not in content:
    raise RuntimeError("Could not find load_real_dataset anchor to insert before.")

if content.count(anchor) > 1:
    raise RuntimeError("Anchor not unique — refusing to insert blindly.")

new_members = '''    # PRODUCTION FEATURE SET (validated Aug 2026)
    # Excludes known leakage columns found via SHAP investigation:
    #   - F2230 (MNTH - data collection metadata, not behavioral)
    #   - F3895-F3923 (bank's own internal incident-score/alert-flag/resolution
    #     fields - these only exist AFTER an account has already been investigated,
    #     so training on them taught the model to recognize accounts the bank had
    #     already flagged rather than learning real mule behavior; F3912
    #     FRAUD_SUSPECTED alone had 0.97 correlation with the target)
    # Result: 5-fold CV mean AUC-ROC 0.9859 (+/-0.0121) on the clean feature set,
    # vs a fake 0.9999 when leakage columns were included.
    LEAKAGE_EXCLUDED_FEATURES = {
        'F2230',
        'F3895', 'F3896', 'F3897', 'F3898', 'F3899',
        'F3900', 'F3901', 'F3902', 'F3903', 'F3904', 'F3905', 'F3906', 'F3907',
        'F3908', 'F3909', 'F3910', 'F3911', 'F3912', 'F3913', 'F3914', 'F3915',
        'F3916', 'F3917', 'F3918', 'F3919', 'F3920', 'F3921', 'F3922', 'F3923',
    }

    def load_production_features(self, feature_list_path="top_100_features_clean.txt"):
        """Load the validated top-100 clean feature list from disk."""
        import os
        full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), feature_list_path)
        with open(full_path) as f:
            feats = [line.strip() for line in f if line.strip()]
        leaked = set(feats) & self.LEAKAGE_EXCLUDED_FEATURES
        if leaked:
            raise RuntimeError(f"Feature list contains excluded leakage columns: {leaked}")
        return feats

'''

content = content.replace(anchor, new_members + anchor)

with open(path_backend, "w") as f:
    f.write(content)

print("Added load_production_features and LEAKAGE_EXCLUDED_FEATURES to ml_pipeline.py")
