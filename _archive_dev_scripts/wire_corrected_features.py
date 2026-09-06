path = "/home/x0_shravan_0x/Tracenetx/backend/ml_pipeline.py"
with open(path, "r") as f:
    content = f.read()

old_set = '''    LEAKAGE_EXCLUDED_FEATURES = {
        'F2230',
        'F3895', 'F3896', 'F3897', 'F3898', 'F3899',
        'F3900', 'F3901', 'F3902', 'F3903', 'F3904', 'F3905', 'F3906', 'F3907',
        'F3908', 'F3909', 'F3910', 'F3911', 'F3912', 'F3913', 'F3914', 'F3915',
        'F3916', 'F3917', 'F3918', 'F3919', 'F3920', 'F3921', 'F3922', 'F3923',
    }'''

new_set = '''    # Corrected scope (Aug 2026): individually tested all 29 F3895-F3923
    # columns for correlation with the target. Only F2230 (categorical,
    # perfect separation) and F3912 (0.969 correlation) are genuinely leaky.
    # The other 27 were wrongly excluded on a proximity assumption in an
    # earlier pass -- confirmed clean and restored.
    LEAKAGE_EXCLUDED_FEATURES = {
        'F2230',
        'F3912',
    }'''

count = content.count(old_set)
if count != 1:
    raise RuntimeError(f"Expected 1 match, found {count}")
content = content.replace(old_set, new_set)

old_load = '''    def load_production_features(self, feature_list_path="top_100_features_clean.txt"):'''
new_load = '''    def load_production_features(self, feature_list_path="top_features_corrected.txt"):'''

count = content.count(old_load)
if count != 1:
    raise RuntimeError(f"Expected 1 match for load_production_features signature, found {count}")
content = content.replace(old_load, new_load)

with open(path, "w") as f:
    f.write(content)
print("ml_pipeline.py updated: corrected leak set (2 columns) + pointing at top_features_corrected.txt")
