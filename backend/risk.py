import pandas as pd

def calculate_risk(account_id: str):
    df = pd.read_csv("transactions.csv")
    score = 0
    flags = []
    incoming = df[df["receiver_id"] == account_id]
    outgoing = df[df["sender_id"] == account_id]

    # Flag 1: sends to multiple accounts
    unique_receivers = outgoing["receiver_id"].nunique()
    if unique_receivers >= 3:
        score += 35
        flags.append(f"Sends to {unique_receivers} unique accounts — structuring pattern")
    elif unique_receivers >= 2:
        score += 20
        flags.append(f"Sends to {unique_receivers} accounts simultaneously")

    # Flag 2: receives from multiple accounts
    unique_senders = incoming["sender_id"].nunique()
    if unique_senders >= 3:
        score += 20
        flags.append(f"Receives from {unique_senders} different accounts — aggregation point")
    elif unique_senders >= 2:
        score += 10
        flags.append(f"Receives from {unique_senders} accounts — possible coordination")

    # Flag 3: multiple senders share same IP
    if len(incoming) >= 2:
        unique_ips = incoming["sender_ip"].nunique()
        if unique_ips == 1:
            score += 30
            flags.append(f"All senders share same IP {incoming['sender_ip'].iloc[0]} — coordinated origin")
        elif unique_ips < len(incoming):
            score += 15
            flags.append(f"Only {unique_ips} unique IPs across {len(incoming)} incoming transactions — IP reuse detected")

    # Flag 4: sent to same IP as received from
    if len(incoming) > 0 and len(outgoing) > 0:
        in_ips = set(incoming["sender_ip"].tolist())
        out_ips = set(outgoing["sender_ip"].tolist())
        shared_ips = in_ips & out_ips
        if shared_ips:
            score += 20
            flags.append(f"Sent and received from same IP {list(shared_ips)[0]} — identity link")

    # Flag 5: rapid outgoing bursts
    if len(outgoing) >= 2:
        try:
            times = pd.to_datetime(outgoing["timestamp"]).sort_values()
            span = (times.iloc[-1] - times.iloc[0]).total_seconds() / 60
            if span <= 30:
                score += 25
                flags.append(f"All {len(outgoing)} transfers within {int(span)} mins — rapid burst")
            elif span <= 120:
                score += 15
                flags.append(f"Rapid transfers within 2-hour window")
        except:
            pass

    # Flag 6: multi-state outgoing
    if len(outgoing) >= 2:
        out_cities = outgoing["sender_city"].unique()
        if len(out_cities) >= 3:
            score += 15
            flags.append(f"Sent from {len(out_cities)} states: {', '.join(out_cities[:3])} — geographic spread")
        elif len(out_cities) >= 2:
            score += 8
            flags.append(f"Activity across {len(out_cities)} cities: {', '.join(out_cities)}")

    # Flag 7: multi-state incoming
    if len(incoming) >= 2:
        in_cities = incoming["sender_city"].unique()
        if len(in_cities) >= 3:
            score += 15
            flags.append(f"Received from {len(in_cities)} states: {', '.join(in_cities[:3])}")
        elif len(in_cities) >= 2:
            score += 8
            flags.append(f"Incoming from multiple cities: {', '.join(in_cities)}")

    # Flag 8: high forwarding ratio
    total_in = incoming["amount"].sum()
    total_out = outgoing["amount"].sum()
    if total_in > 0 and total_out > 0:
        ratio = total_out / total_in
        if ratio >= 0.9:
            score += 20
            flags.append(f"Forwards {int(ratio*100)}% of received funds — pass-through behavior")
        elif ratio >= 0.7:
            score += 10
            flags.append(f"Forwards {int(ratio*100)}% of received funds — suspicious outflow")

    # Flag 9: high volume
    total_out_val = outgoing["amount"].sum()
    if total_out_val > 300000:
        score += 15
        flags.append(f"Total outflow ₹{int(total_out_val/100000)}.{int((total_out_val%100000)/1000)}L — high volume")
    elif total_out_val > 100000:
        score += 8
        flags.append(f"Total outflow ₹{int(total_out_val/1000)}K above threshold")

    # Flag 10: round amount pattern
    all_amounts = list(incoming["amount"]) + list(outgoing["amount"])
    if len(all_amounts) >= 2:
        round_count = sum(1 for a in all_amounts if a % 10000 == 0)
        if round_count / len(all_amounts) >= 0.8:
            score += 10
            flags.append(f"Round-amount pattern ({round_count}/{len(all_amounts)} txns) — shell company signature")

    if score >= 70:
        level = "CRITICAL"
    elif score >= 50:
        level = "HIGH"
    elif score >= 25:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {"score": min(score, 100), "level": level, "flags": flags}
