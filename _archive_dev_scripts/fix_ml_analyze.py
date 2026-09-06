path_main = "/home/x0_shravan_0x/Tracenetx/backend/main.py"
with open(path_main, "r") as f:
    content = f.read()

old = '''@app.get("/ml/analyze")
def ml_analyze_all():
    """Run full ML pipeline on all accounts"""
    df = pd.read_csv("transactions.csv")
    results = ml_pipeline.predict(df)
    # Apply overrides
    for r in results:
        aid = r['account_id'].upper()
        if 'CRIMINAL' in aid:
            r['risk_level'] = 'CRITICAL'; r['risk_score'] = 92
            r['recommended_action'] = 'Immediate freeze + STR filing + ED/CBI referral'
            r['mule_type'] = 'WILLING (knowing participant)'
        elif 'DEALER' in aid or 'COLLECTOR' in aid:
            r['risk_level'] = 'CRITICAL'; r['risk_score'] = 90
            r['recommended_action'] = 'Immediate freeze + STR filing + ED/CBI referral'
            r['mule_type'] = 'WILLING (knowing participant)'
        elif 'CRYPTO' in aid:
            r['risk_level'] = 'HIGH'; r['risk_score'] = 75
            r['recommended_action'] = 'Account freeze + investigation + police referral'
        elif 'HAWALA' in aid or 'SHELL' in aid:
            r['risk_level'] = 'MEDIUM'; r['risk_score'] = 58
            r['recommended_action'] = 'Enhanced monitoring + bank outreach + customer interview'
        elif 'RECRUITER' in aid or 'RECR' in aid:
            r['risk_level'] = 'MEDIUM'; r['risk_score'] = 55
            r['recommended_action'] = 'Enhanced monitoring + bank outreach + customer interview'
        elif aid.startswith('ACC_'):
            r['risk_level'] = 'CLEAR'; r['risk_score'] = 15
            r['recommended_action'] = 'No action — continue standard monitoring'
            r['mule_type'] = 'UNWITTING (possible victim)'
    results.sort(key=lambda x: x['risk_score'], reverse=True)'''

new = '''@app.get("/ml/analyze")
def ml_analyze_all():
    """Run full ML pipeline on all accounts — real ensemble output only, no overrides"""
    df = pd.read_csv("transactions.csv")
    results = ml_pipeline.predict(df)
    results.sort(key=lambda x: x['risk_score'], reverse=True)'''

count = content.count(old)
if count != 1:
    raise RuntimeError(f"[/ml/analyze] expected 1 match, found {count}")
content = content.replace(old, new)
print("[/ml/analyze] override block removed — real predict() output only")

with open(path_main, "w") as f:
    f.write(content)
