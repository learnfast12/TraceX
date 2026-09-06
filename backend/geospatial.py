"""
Geospatial Crime Pattern Intelligence — PS6 module
Aggregates real Neo4j transaction data by city into fraud/scam hotspots.
Severity and type are derived from the same account-naming risk convention
used in graph.py's override_risk (CRIMINAL/DEALER/CRYPTO/HAWALA/SHELL).
"""
from fastapi import APIRouter
from datetime import datetime, timedelta
from graph import driver

router = APIRouter()

CITY_COORDS = {
    "Delhi": (28.6139, 77.2090), "Mumbai": (19.0760, 72.8777),
    "Chennai": (13.0827, 80.2707), "Kolkata": (22.5726, 88.3639),
    "Bangalore": (12.9716, 77.5946), "Hyderabad": (17.3850, 78.4867),
    "Pune": (18.5204, 73.8567), "Ahmedabad": (23.0225, 72.5714),
    "Jaipur": (26.9124, 75.7873), "Lucknow": (26.8467, 80.9462),
    "Patna": (25.5941, 85.1376), "Bhopal": (23.2599, 77.4126),
    "Surat": (21.1702, 72.8311), "Indore": (22.7196, 75.8577),
    "Nagpur": (21.1458, 79.0882), "Goa": (15.2993, 74.1240),
    "Kanpur": (26.4499, 80.3319), "Varanasi": (25.3176, 82.9739),
    "Ranchi": (23.3441, 85.3096), "Bhubaneswar": (20.2961, 85.8245),
}

CRITICAL_KEYWORDS = ("CRIMINAL", "DEALER", "COLLECTOR")
HIGH_KEYWORDS = ("CRYPTO",)
MEDIUM_KEYWORDS = ("HAWALA", "SHELL", "RECRUITER", "RECR")
SEVERITY_RANK = {"critical": 3, "high": 2, "medium": 1, "low": 0}

def classify_account(account_id: str) -> str:
    aid = account_id.upper()
    if any(k in aid for k in CRITICAL_KEYWORDS): return "critical"
    if any(k in aid for k in HIGH_KEYWORDS): return "high"
    if any(k in aid for k in MEDIUM_KEYWORDS): return "medium"
    return "low"

def classify_type(account_ids) -> str:
    ids_upper = " ".join(account_ids).upper()
    # Organized fraud core: criminal handlers, dealers, collectors, recruiters
    if any(k in ids_upper for k in ("CRIMINAL", "DEALER", "COLLECTOR", "RECRUITER", "RECR")):
        return "fraud_ring"
    # Crypto exchange/gateway involvement
    if any(k in ids_upper for k in ("CRYPTO",)):
        return "cybercrime"
    # Hawala/shell company laundering conduits — typical of digital arrest scam payouts
    if any(k in ids_upper for k in ("HAWALA", "SHELL")):
        return "digital_arrest"
    # No specific role match — still part of a fraud network, just unclassified layer
    return "fraud_ring"

def fetch_transactions():
    with driver.session() as session:
        result = session.run("""
            MATCH (s:Account)-[t:TRANSFER]->(r:Account)
            RETURN s.id as sender, r.id as receiver, t.amount as amount,
                   t.timestamp as timestamp, t.sender_city as city,
                   t.transfer_type as transfer_type
        """)
        return result.data()

def generate_real_hotspots():
    rows = fetch_transactions()
    if not rows:
        return []

    timestamps = []
    for row in rows:
        try:
            timestamps.append(datetime.fromisoformat(row["timestamp"]))
        except Exception:
            pass
    if not timestamps:
        return []

    # Anchor "now" to the latest timestamp in this historical dataset,
    # so 24h/7d windows are meaningful even though the data isn't live.
    anchor = max(timestamps)
    day_ago = anchor - timedelta(days=1)
    two_days_ago = anchor - timedelta(days=2)
    week_ago = anchor - timedelta(days=7)

    by_city = {}
    for row in rows:
        city = row.get("city")
        if not city or city not in CITY_COORDS:
            continue
        try:
            ts = datetime.fromisoformat(row["timestamp"])
        except Exception:
            continue

        bucket = by_city.setdefault(city, {
            "accounts": set(), "incidents_24h": 0, "incidents_prev_24h": 0,
            "incidents_7d": 0, "total_amount": 0.0,
        })
        bucket["accounts"].add(row["sender"])
        bucket["accounts"].add(row["receiver"])
        bucket["total_amount"] += row["amount"] or 0

        if ts >= day_ago:
            bucket["incidents_24h"] += 1
        elif ts >= two_days_ago:
            bucket["incidents_prev_24h"] += 1
        if ts >= week_ago:
            bucket["incidents_7d"] += 1

    hotspots = []
    for i, (city, data) in enumerate(by_city.items()):
        lat, lng = CITY_COORDS[city]
        account_list = list(data["accounts"])
        severities = [classify_account(a) for a in account_list]
        top_severity = max(severities, key=lambda s: SEVERITY_RANK[s]) if severities else "low"
        hotspot_type = classify_type(account_list)

        if data["incidents_24h"] > data["incidents_prev_24h"]:
            trend = "rising"
        elif data["incidents_24h"] < data["incidents_prev_24h"]:
            trend = "falling"
        else:
            trend = "stable"

        hotspots.append({
            "id": f"hs_{i}",
            "name": city,
            "lat": lat, "lng": lng,
            "type": hotspot_type,
            "severity": top_severity,
            "incidents_24h": data["incidents_24h"],
            "incidents_7d": data["incidents_7d"],
            "trend": trend,
            "total_amount": data["total_amount"],
        })
    return hotspots

@router.get("/geospatial/hotspots")
def get_hotspots():
    return {"hotspots": generate_real_hotspots()}
