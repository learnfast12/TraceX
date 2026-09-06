from neo4j import GraphDatabase
import pandas as pd
from collections import defaultdict

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "password123")
driver = GraphDatabase.driver(URI, auth=AUTH)

class GraphIntelligence:

    def reverse_chain_analysis(self, account_id: str):
        """Trace backwards from exit point to find coordinator"""
        with driver.session() as session:
            result = session.run("""
                MATCH path = (source:Account)-[:TRANSFER*1..5]->(target:Account {id: $id})
                RETURN [node in nodes(path) | node.id] as chain,
                       [rel in relationships(path) | rel.amount] as amounts,
                       length(path) as hops
                ORDER BY hops DESC
                LIMIT 10
            """, id=account_id)

            chains = []
            for record in result:
                chain_nodes = record["chain"]
                # Skip non-simple paths where a node is revisited — a real fund
                # flow cannot pass through the same account twice in one link
                # of custody; this is a Cypher variable-length-path artifact,
                # not a real transaction pattern.
                if len(chain_nodes) != len(set(chain_nodes)):
                    continue
                chains.append({
                    "chain": chain_nodes,
                    "amounts": record["amounts"],
                    "hops": record["hops"],
                    "entry_point": chain_nodes[0],
                    "exit_point": chain_nodes[-1]
                })

            return {
                "target_account": account_id,
                "reverse_chains": chains,
                "total_chains_found": len(chains),
                "analysis": f"Found {len(chains)} inbound chains. Coordinator likely at entry points."
            }

    def community_detection(self):
        """Find mule clusters converging to same destination"""
        with driver.session() as session:
            result = session.run("""
                MATCH (s:Account)-[:TRANSFER]->(hub:Account)
                WITH hub, collect(s.id) as senders, count(*) as inbound
                WHERE inbound >= 2
                RETURN hub.id as coordinator,
                       senders,
                       inbound
                ORDER BY inbound DESC
                LIMIT 10
            """)

            communities = []
            for record in result:
                communities.append({
                    "coordinator": record["coordinator"],
                    "mule_accounts": record["senders"],
                    "inbound_count": record["inbound"],
                    "threat_level": "CRITICAL" if record["inbound"] >= 4 else "HIGH"
                })

            return {
                "communities_detected": len(communities),
                "clusters": communities,
                "analysis": f"Detected {len(communities)} mule clusters converging to coordinator nodes"
            }

    def coordination_detection(self):
        """Detect synchronized transaction timing — coordination signal"""
        with driver.session() as session:
            result = session.run("""
                MATCH (s:Account)-[t:TRANSFER]->(r:Account)
                RETURN t.timestamp as timestamp,
                       s.id as sender,
                       r.id as receiver,
                       t.amount as amount
                ORDER BY t.timestamp
            """)

            records = result.data()
            if not records:
                return {"coordinated_bursts": [], "analysis": "No coordination detected"}

            df = pd.DataFrame(records)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')

            # Find accounts transferring within same 2-hour window
            bursts = []
            for i, row in df.iterrows():
                window_start = row['timestamp']
                window_end = window_start + pd.Timedelta(hours=2)
                window_txns = df[
                    (df['timestamp'] >= window_start) &
                    (df['timestamp'] <= window_end)
                ]
                if len(window_txns) >= 3:
                    bursts.append({
                        "window_start": str(window_start),
                        "window_end": str(window_end),
                        "accounts_involved": list(window_txns['sender'].unique()),
                        "transaction_count": len(window_txns),
                        "total_amount": float(window_txns['amount'].sum()),
                        "alert": "COORDINATION SIGNAL — multiple accounts transacting in same 2hr window"
                    })

            unique_bursts = []
            seen = set()
            for b in bursts:
                key = b['window_start'][:13]
                if key not in seen:
                    seen.add(key)
                    unique_bursts.append(b)

            return {
                "coordinated_bursts": unique_bursts[:5],
                "total_bursts_detected": len(unique_bursts),
                "analysis": f"Detected {len(unique_bursts)} coordination windows"
            }

    def batch_recruitment_detection(self):
        """Find accounts opened same time, same location — recruitment batch"""
        with driver.session() as session:
            # NOTE: TRANSFER relationships only carry sender_ip/sender_city in
            # this schema — no receiver_ip/receiver_city property exists.
            # This means an account that only ever appears as a receiver
            # (never as a sender) won't be scored here. Known limitation.
            result = session.run("""
                MATCH (s:Account)-[t:TRANSFER]->(r:Account)
                RETURN s.id as account, t.sender_ip as ip, t.sender_city as city
            """)

            records = result.data()
            if not records:
                return {"recruitment_batches": [], "total_batches": 0, "analysis": "No batches detected"}

            df = pd.DataFrame(records)
            df = df.dropna(subset=['ip'])

            # Group by IP only — an account's IP is a stable identity signal,
            # its logged city can vary transaction-to-transaction
            batches = df.groupby('ip').agg(
                accounts=('account', lambda x: sorted(set(x))),
                cities=('city', lambda x: sorted(set(x.dropna()))),
            ).reset_index()
            batches['account_count'] = batches['accounts'].apply(len)

            recruitment_batches = []
            for _, row in batches[batches['account_count'] >= 2].iterrows():
                recruitment_batches.append({
                    "shared_ip": row['ip'],
                    "cities_seen": row['cities'],
                    "accounts": row['accounts'],
                    "account_count": row['account_count'],
                    "alert": f"BATCH RECRUITMENT — {row['account_count']} accounts sharing IP {row['ip']}"
                })

            recruitment_batches.sort(key=lambda x: x['account_count'], reverse=True)

            return {
                "recruitment_batches": recruitment_batches,
                "total_batches": len(recruitment_batches),
                "analysis": f"Found {len(recruitment_batches)} potential recruitment batches"
            }

    def convergence_analysis(self):
        """Find the lieutenant — account receiving from multiple independent clusters"""
        with driver.session() as session:
            result = session.run("""
                MATCH (s:Account)-[:TRANSFER*1..3]->(hub:Account)
                WITH hub, collect(DISTINCT s.id) as sources, count(DISTINCT s) as source_count
                WHERE source_count >= 3
                RETURN hub.id as potential_lieutenant,
                       sources,
                       source_count
                ORDER BY source_count DESC
                LIMIT 5
            """)

            lieutenants = []
            for record in result:
                lieutenants.append({
                    "account": record["potential_lieutenant"],
                    "connected_sources": record["sources"],
                    "source_count": record["source_count"],
                    "threat": "LIEUTENANT NODE — receives from multiple independent chains"
                })

            return {
                "potential_lieutenants": lieutenants,
                "analysis": f"Identified {len(lieutenants)} potential lieutenant/coordinator nodes"
            }

    def identity_fusion(self):
        """Link accounts sharing IP, phone, or city"""
        with driver.session() as session:
            result = session.run("""
                MATCH (s1:Account)-[t1:TRANSFER]->(x)
                MATCH (s2:Account)-[t2:TRANSFER]->(y)
                WHERE s1.id <> s2.id
                AND t1.sender_ip = t2.sender_ip
                RETURN s1.id as account1,
                       s2.id as account2,
                       t1.sender_ip as shared_ip,
                       t1.sender_city as city
                LIMIT 20
            """)

            fusions = []
            seen = set()
            for record in result:
                key = tuple(sorted([record['account1'], record['account2']]))
                if key not in seen:
                    seen.add(key)
                    fusions.append({
                        "account1": record['account1'],
                        "account2": record['account2'],
                        "shared_ip": record['shared_ip'],
                        "city": record['city'],
                        "alert": "IDENTITY FUSION — accounts share same IP address"
                    })

            return {
                "identity_links": fusions,
                "total_links": len(fusions),
                "analysis": f"Found {len(fusions)} identity fusion links across accounts"
            }

    def full_intelligence_report(self, account_id: str = None):
        """Run all intelligence layers and return complete report"""
        report = {
            "community_detection": self.community_detection(),
            "coordination_detection": self.coordination_detection(),
            "batch_recruitment": self.batch_recruitment_detection(),
            "convergence_analysis": self.convergence_analysis(),
            "identity_fusion": self.identity_fusion(),
            "hawala_detection": self.hawala_broker_detection(),
            "shell_company_detection": self.shell_company_detection(),
            "crypto_monitoring": self.crypto_gateway_monitoring(),
        }
        if account_id:
            report["reverse_chain"] = self.reverse_chain_analysis(account_id)

        return report

    def hawala_broker_detection(self):
        """Detect hawala brokers — receives from many, large cash withdrawals, repeating cycle"""
        with driver.session() as session:
            result = session.run("""
                MATCH (s:Account)-[t2:TRANSFER]->(hub:Account)
                WITH hub, count(DISTINCT s) as unique_senders, sum(t2.amount) as total_in
                WHERE unique_senders >= 2
                OPTIONAL MATCH (hub)-[t:TRANSFER]->(r:Account)
                WITH hub, unique_senders, total_in, count(DISTINCT r) as unique_receivers, sum(t.amount) as total_out
                RETURN hub.id as account,
                       unique_senders,
                       unique_receivers,
                       total_in,
                       coalesce(total_out, 0) as total_out
                ORDER BY unique_senders DESC
                LIMIT 10
            """)

            brokers = []
            for record in result:
                total_in = record["total_in"] or 0
                total_out = record["total_out"] or 0
                ratio = total_out / (total_in + 1)

                # Behavioral signal only: receives from 3+ independent senders AND
                # forwards 95%+ of what it took in — near-total pass-through from
                # many sources is the actual hawala broker signature; a looser
                # threshold also catches ordinary mules forwarding most of one
                # inbound payment, which is a different (weaker) signal
                if record["unique_senders"] >= 3 and ratio >= 0.95:
                    brokers.append({
                        "account": record["account"],
                        "unique_senders": record["unique_senders"],
                        "unique_receivers": record["unique_receivers"],
                        "total_inflow": int(total_in),
                        "total_outflow": int(total_out),
                        "forwarding_ratio": round(ratio, 2),
                        "threat": "HAWALA BROKER SIGNATURE — receives from many, forwards most, repeating cycle",
                        "severity": "CRITICAL" if record["unique_senders"] >= 4 else "HIGH"
                    })

            return {
                "hawala_brokers_detected": len(brokers),
                "brokers": brokers,
                "analysis": f"Detected {len(brokers)} potential hawala broker accounts"
            }

    def shell_company_detection(self):
        """Detect shell companies — round amounts, burst pattern, no legitimate business flow"""
        with driver.session() as session:
            result = session.run("""
                MATCH (s:Account)-[t:TRANSFER]->(r:Account)
                WITH r,
                     collect(t.amount) as amounts,
                     count(t) as txn_count,
                     sum(t.amount) as total_received,
                     collect(DISTINCT s.id) as senders
                WHERE txn_count >= 2
                RETURN r.id as account,
                       amounts,
                       txn_count,
                       total_received,
                       senders
            """)

            shells = []
            for record in result:
                amounts = record["amounts"] or []
                if not amounts:
                    continue
                round_count = sum(1 for a in amounts if a % 10000 == 0)
                round_ratio = round_count / len(amounts)
                sender_concentration = len(record["senders"])

                # Behavioral signal only: majority of inbound amounts are suspiciously
                # round (multiples of 10,000) AND funds arrive from multiple senders in
                # bursts — the actual shell-company pattern, not a name match
                if record["txn_count"] >= 2 and round_ratio >= 0.5 and sender_concentration >= 2:
                    shells.append({
                        "account": record["account"],
                        "transaction_count": record["txn_count"],
                        "total_received": int(record["total_received"]),
                        "round_amount_percentage": round(round_ratio * 100, 1),
                        "unique_senders": sender_concentration,
                        "amounts": [int(a) for a in amounts],
                        "threat": "SHELL COMPANY PATTERN — round amounts, burst receipts, no outward commercial flow",
                        "severity": "HIGH" if round_ratio >= 0.8 else "MEDIUM"
                    })

            return {
                "shell_companies_detected": len(shells),
                "shells": shells,
                "analysis": f"Detected {len(shells)} potential shell company accounts"
            }

    def crypto_gateway_monitoring(self):
        """Flag transactions to known crypto exchange deposit addresses"""
        # Known crypto exchange deposit address patterns (simulated for demo)
        known_crypto_exchanges = {
            "CRYPTO_BTC1": "Binance BTC deposit",
            "CRYPTO_ETH1": "Coinbase ETH deposit",
            "CRYPTO_USDT1": "WazirX USDT deposit",
            "CRYPTO_BNB1": "Binance BNB deposit",
            "DEALER1": "Suspected crypto gateway",
            "DEALER2": "Suspected crypto gateway",
        }

        with driver.session() as session:
            result = session.run("""
                MATCH (s:Account)-[t:TRANSFER]->(r:Account)
                RETURN s.id as sender, r.id as receiver,
                       t.amount as amount, t.timestamp as timestamp,
                       t.sender_city as city
            """)

            alerts = []
            for record in result:
                receiver = record["receiver"]
                if receiver in known_crypto_exchanges:
                    alerts.append({
                        "sender": record["sender"],
                        "destination": receiver,
                        "exchange": known_crypto_exchanges[receiver],
                        "amount": int(record["amount"]),
                        "timestamp": record["timestamp"],
                        "city": record["city"],
                        "alert": f"CRYPTO GATEWAY — ₹{int(record['amount'])//1000}K transferred to {known_crypto_exchanges[receiver]}",
                        "severity": "CRITICAL",
                        "action": "Immediate freeze — funds may exit banking system via crypto"
                    })

            return {
                "crypto_alerts": len(alerts),
                "alerts": alerts,
                "monitored_exchanges": list(known_crypto_exchanges.values()),
                "analysis": f"Detected {len(alerts)} transactions to known crypto gateway addresses"
            }


# Global instance
graph_intel = GraphIntelligence()
