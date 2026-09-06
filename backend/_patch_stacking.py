path = "real_validation.py"
with open(path) as f:
    src = f.read()

old_imports_xgb = "import xgboost as xgb"
assert old_imports_xgb in src, "xgboost import not found"
src = src.replace(old_imports_xgb, old_imports_xgb + "\nimport lightgbm as lgb\nfrom sklearn.linear_model import LogisticRegression")

old_fit_block = '''        model = xgb.XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            scale_pos_weight=10, random_state=random_state,
            eval_metric='logloss', verbosity=0
        )
        model.fit(X_train_res, y_train_res)

        y_proba = model.predict_proba(X_test)[:, 1]
        y_pred = model.predict(X_test)'''
new_fit_block = '''        xgb_model = xgb.XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            scale_pos_weight=10, random_state=random_state,
            eval_metric='logloss', verbosity=0
        )
        xgb_model.fit(X_train_res, y_train_res)

        lgb_model = lgb.LGBMClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            scale_pos_weight=10, random_state=random_state,
            verbosity=-1
        )
        lgb_model.fit(X_train_res, y_train_res)

        xgb_train_proba = xgb_model.predict_proba(X_train_res)[:, 1]
        lgb_train_proba = lgb_model.predict_proba(X_train_res)[:, 1]
        blend_train = np.column_stack([xgb_train_proba, lgb_train_proba])
        blender = LogisticRegression()
        blender.fit(blend_train, y_train_res)

        xgb_test_proba = xgb_model.predict_proba(X_test)[:, 1]
        lgb_test_proba = lgb_model.predict_proba(X_test)[:, 1]
        blend_test = np.column_stack([xgb_test_proba, lgb_test_proba])

        y_proba = blender.predict_proba(blend_test)[:, 1]
        y_pred = (y_proba >= 0.5).astype(int)'''
assert src.count(old_fit_block) == 1, "fit block not found or not unique"
src = src.replace(old_fit_block, new_fit_block)

with open(path, "w") as f:
    f.write(src)

print("Stacking patch applied: XGBoost + LightGBM blended via logistic regression per fold.")
