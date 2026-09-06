path_main = "/home/x0_shravan_0x/Tracenetx/backend/main.py"
with open(path_main, "r") as f:
    content = f.read()

old = '''@app.get("/export")
def export_csv():
    df = pd.read_csv("transactions.csv")
    accounts = set(df["sender_id"]).union(set(df["receiver_id"]))
    flagged = []
    for acc in accounts:
        aid = acc.upper()
        if 'CRIMINAL' in aid:
            level, score = 'CRITICAL', 92
        elif 'DEALER' in aid or 'COLLECTOR' in aid:
            level, score = 'CRITICAL', 90
        elif 'CRYPTO' in aid:
            level, score = 'HIGH', 75
        elif 'HAWALA' in aid or 'SHELL' in aid:
            level, score = 'MEDIUM', 58
        elif 'RECRUITER' in aid or 'RECR' in aid:
            level, score = 'MEDIUM', 55
        else:
            level, score = 'CLEAR', 15
        if level == 'CLEAR':
            continue
        txns = df[(df["sender_id"] == acc) | (df["receiver_id"] == acc)]
        flags = []
        if 'CRIMINAL' in aid: flags.append("COORDINATOR")
        if 'DEALER' in aid: flags.append("DEALER")
        if 'CRYPTO' in aid: flags.append("CRYPTO_GATEWAY")
        if 'HAWALA' in aid: flags.append("HAWALA_BROKER")
        if 'SHELL' in aid: flags.append("SHELL_COMPANY")
        if 'RECRUITER' in aid or 'RECR' in aid: flags.append("RECRUITER")
        flagged.append({
            "account_id": acc,
            "risk_level": level,
            "risk_score": score,
            "flags": ", ".join(flags),
            "total_transactions": len(txns),
            "total_amount": float(txns["amount"].sum())
        })
    flagged.sort(key=lambda x: x["risk_score"], reverse=True)
    return {"flagged_accounts": flagged}
    return StreamingResponse(stream, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=tracenetx_export.csv"})'''

new = '''@app.get("/export")
def export_csv():
    """
    Build the flagged-accounts export from real signals only:
    - risk_score / risk_level / mule_type / behavioral flags come from the
      actual ML ensemble (ml_pipeline.predict) — real engineered features,
      not the account's name
    - graph-based flags (hawala broker, shell company, community coordinator,
      batch recruitment member) come from live Neo4j graph intelligence
    No account-name string matching anywhere in this endpoint.
    """
    df = pd.read_csv("transactions.csv")
    ml_results = ml_pipeline.predict(df)
    ml_by_account = {r["account_id"]: r for r in ml_results}

    # Real graph-intelligence membership sets, computed once
    hawala_accounts = {b["account"] for b in graph_intel.hawala_broker_detection().get("brokers", [])}
    shell_accounts = {s["account"] for s in graph_intel.shell_company_detection().get("shells", [])}
    coordinator_accounts = {c["coordinator"] for c in graph_intel.community_detection().get("clusters", [])}
    recruitment_accounts = set()
    for batch in graph_intel.batch_recruitment_detection().get("recruitment_batches", []):
        recruitment_accounts.update(batch.get("accounts", []))

    accounts = set(df["sender_id"]).union(set(df["receiver_id"]))
    flagged = []
    for acc in accounts:
        ml = ml_by_account.get(acc)
        if not ml:
            continue
        if ml["risk_level"] == "CLEAR":
            continue

        graph_flags = []
        if acc in coordinator_accounts:
            graph_flags.append("COORDINATOR")
        if acc in hawala_accounts:
            graph_flags.append("HAWALA_BROKER")
        if acc in shell_accounts:
            graph_flags.append("SHELL_COMPANY")
        if acc in recruitment_accounts:
            graph_flags.append("RECRUITMENT_BATCH_MEMBER")

        all_flags = list(ml.get("flags", [])) + graph_flags

        txns = df[(df["sender_id"] == acc) | (df["receiver_id"] == acc)]
        flagged.append({
            "account_id": acc,
            "risk_level": ml["risk_level"],
            "risk_score": ml["risk_score"],
            "mule_type": ml.get("mule_type", "N/A"),
            "flags": ", ".join(all_flags) if all_flags else "NONE",
            "total_transactions": len(txns),
            "total_amount": float(txns["amount"].sum())
        })

    flagged.sort(key=lambda x: x["risk_score"], reverse=True)
    return {"flagged_accounts": flagged}'''

count = content.count(old)
if count != 1:
    raise RuntimeError(f"Expected 1 match, found {count} — file may have drifted from expected form.")
content = content.replace(old, new)

with open(path_main, "w") as f:
    f.write(content)
print("Rebuilt /export endpoint — real ML + real graph intelligence, no name matching. Dead StreamingResponse code removed.")
