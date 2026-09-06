path_main = "/home/x0_shravan_0x/Tracenetx/backend/main.py"
with open(path_main, "r") as f:
    content = f.read()

old = '''    # Apply overrides
    aid = account_id.upper()
    if 'CRIMINAL' in aid:
        account_result['risk_level'] = 'CRITICAL'; account_result['risk_score'] = 92
        account_result['recommended_action'] = 'Immediate freeze + STR filing + ED/CBI referral'
        account_result['mule_type'] = 'WILLING (knowing participant)'
    elif 'DEALER' in aid or 'COLLECTOR' in aid:
        account_result['risk_level'] = 'CRITICAL'; account_result['risk_score'] = 90
        account_result['recommended_action'] = 'Immediate freeze + STR filing + ED/CBI referral'
        account_result['mule_type'] = 'WILLING (knowing participant)'
    elif 'CRYPTO' in aid:
        account_result['risk_level'] = 'HIGH'; account_result['risk_score'] = 75
        account_result['recommended_action'] = 'Account freeze + investigation + police referral'
        account_result['mule_type'] = 'WILLING (knowing participant)'
    elif 'HAWALA' in aid or 'SHELL' in aid:
        account_result['risk_level'] = 'MEDIUM'; account_result['risk_score'] = 58
        account_result['recommended_action'] = 'Enhanced monitoring + bank outreach + customer interview'
    elif 'RECRUITER' in aid or 'RECR' in aid:
        account_result['risk_level'] = 'MEDIUM'; account_result['risk_score'] = 55
        account_result['recommended_action'] = 'Enhanced monitoring + bank outreach + customer interview'
    elif aid.startswith('ACC_'):
        account_result['risk_level'] = 'CLEAR'; account_result['risk_score'] = 15
        account_result['recommended_action'] = 'No action — possible victim, recommend bank outreach'
        account_result['mule_type'] = 'UNWITTING (possible victim)'
    graph_report = graph_intel.full_intelligence_report(account_id)'''

new = '''    # No overrides — account_result is the real ml_pipeline.predict() output
    graph_report = graph_intel.full_intelligence_report(account_id)'''

count = content.count(old)
if count != 1:
    raise RuntimeError(f"[/evidence] expected 1 match, found {count}")
content = content.replace(old, new)
print("[/evidence/{account_id}] override block removed — real predict() output only")

with open(path_main, "w") as f:
    f.write(content)
