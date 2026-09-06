import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

class TemporalPatternEngine:
    """
    Rule-based behavioral sequence detector for mule account lifecycle patterns.
    Not a trained neural network — deterministic threshold/window logic over
    each account's transaction timeline (dormant reactivation, delayed
    layering, velocity spikes, smurfing, rapid forwarding).
    """
    """
    Temporal pattern detection for mule account lifecycle.
    Detects:
    - DORMANT REACTIVATION: Account dormant -> warm-up -> sudden large inflow -> rapid forward -> dormant
    - DELAYED LAYERING: Funds received -> held days/weeks -> forwarded in coordinated burst
    - VELOCITY SPIKE: Normal baseline -> sudden 10x frequency -> returns to normal
    - SMURFING SEQUENCE: Large amount split into many small timed transfers
    """

    def __init__(self):
        self.patterns_detected = []

    def analyze_account_timeline(self, account_id: str, df: pd.DataFrame):
        outgoing = df[df['sender_id'] == account_id].copy()
        incoming = df[df['receiver_id'] == account_id].copy()

        if len(outgoing) == 0 and len(incoming) == 0:
            return None

        patterns = []

        try:
            outgoing['timestamp'] = pd.to_datetime(outgoing['timestamp'])
            incoming['timestamp'] = pd.to_datetime(incoming['timestamp'])
        except:
            return None

        # PATTERN 1 — DORMANT REACTIVATION
        dormant = self._detect_dormant_reactivation(account_id, incoming, outgoing)
        if dormant:
            patterns.append(dormant)

        # PATTERN 2 — DELAYED LAYERING
        delayed = self._detect_delayed_layering(account_id, incoming, outgoing)
        if delayed:
            patterns.append(delayed)

        # PATTERN 3 — VELOCITY SPIKE
        velocity = self._detect_velocity_spike(account_id, outgoing)
        if velocity:
            patterns.append(velocity)

        # PATTERN 4 — SMURFING SEQUENCE
        smurfing = self._detect_smurfing_sequence(account_id, outgoing)
        if smurfing:
            patterns.append(smurfing)

        # PATTERN 5 — RAPID FORWARD (receive then immediately forward)
        rapid = self._detect_rapid_forward(account_id, incoming, outgoing)
        if rapid:
            patterns.append(rapid)

        lifecycle_score = min(len(patterns) * 25, 100)

        return {
            "account_id": account_id,
            "patterns_detected": patterns,
            "pattern_count": len(patterns),
            "temporal_risk_score": lifecycle_score,
            "temporal_risk_level": self._score_to_level(lifecycle_score),
            "timeline_summary": self._build_timeline(account_id, incoming, outgoing)
        }

    def _detect_dormant_reactivation(self, account_id, incoming, outgoing):
        all_txns = pd.concat([
            incoming[['timestamp', 'amount']],
            outgoing[['timestamp', 'amount']]
        ]).sort_values('timestamp')

        if len(all_txns) < 3:
            return None

        times = all_txns['timestamp'].tolist()
        for i in range(1, len(times)):
            gap = (times[i] - times[i-1]).total_seconds() / 86400  # days
            if gap >= 30:  # dormant for 30+ days
                # Check if activity surged after reactivation
                after_reactivation = all_txns[all_txns['timestamp'] >= times[i]]
                before_dormancy = all_txns[all_txns['timestamp'] < times[i-1]]

                if len(after_reactivation) >= 2:
                    avg_after = after_reactivation['amount'].mean()
                    avg_before = before_dormancy['amount'].mean() if len(before_dormancy) > 0 else 0

                    if avg_after > avg_before * 1.5 or avg_before == 0:
                        return {
                            "pattern": "DORMANT_REACTIVATION",
                            "severity": "HIGH",
                            "description": f"Account dormant for {int(gap)} days then reactivated with {len(after_reactivation)} transactions",
                            "dormancy_days": int(gap),
                            "reactivation_date": str(times[i])[:10],
                            "alert": "Classic mule lifecycle — account reactivated after dormancy with increased activity"
                        }
        return None

    def _detect_delayed_layering(self, account_id, incoming, outgoing):
        if len(incoming) == 0 or len(outgoing) == 0:
            return None

        for _, in_row in incoming.iterrows():
            for _, out_row in outgoing.iterrows():
                delay = (out_row['timestamp'] - in_row['timestamp']).total_seconds() / 3600
                if 1 <= delay <= 336:  # 1 hour to 2 weeks delay
                    amount_ratio = out_row['amount'] / (in_row['amount'] + 1)
                    if 0.7 <= amount_ratio <= 1.0:  # forwards most of what it received
                        return {
                            "pattern": "DELAYED_LAYERING",
                            "severity": "HIGH",
                            "description": f"Received ₹{int(in_row['amount'])} then forwarded ₹{int(out_row['amount'])} after {int(delay)}hr delay",
                            "delay_hours": int(delay),
                            "amount_retained_pct": round((1 - amount_ratio) * 100, 1),
                            "alert": "Deliberate time delay before forwarding — classic layering technique"
                        }
        return None

    def _detect_velocity_spike(self, account_id, outgoing):
        if len(outgoing) < 3:
            return None

        outgoing = outgoing.sort_values('timestamp')
        times = outgoing['timestamp'].tolist()

        # Check for sudden burst in transaction frequency
        total_span = (times[-1] - times[0]).total_seconds() / 3600
        if total_span <= 0:
            return None

        avg_rate = len(times) / total_span  # txns per hour

        # Check if any 2hr window has 3x the average rate
        for i, t in enumerate(times):
            window_end = t + pd.Timedelta(hours=2)
            window_txns = outgoing[
                (outgoing['timestamp'] >= t) &
                (outgoing['timestamp'] <= window_end)
            ]
            window_rate = len(window_txns) / 2  # txns per hour in window

            if window_rate >= avg_rate * 2.5 and len(window_txns) >= 2:
                return {
                    "pattern": "VELOCITY_SPIKE",
                    "severity": "MEDIUM",
                    "description": f"Transaction velocity {window_rate:.1f}x/hr vs baseline {avg_rate:.2f}x/hr in 2hr window",
                    "spike_start": str(t)[:16],
                    "transactions_in_window": len(window_txns),
                    "alert": "Sudden velocity spike — coordination signal detected"
                }
        return None

    def _detect_smurfing_sequence(self, account_id, outgoing):
        if len(outgoing) < 3:
            return None

        outgoing = outgoing.sort_values('timestamp')
        amounts = outgoing['amount'].tolist()

        # Check: large incoming split into many small outgoing below threshold
        avg_amount = sum(amounts) / len(amounts)
        threshold = 50000  # ₹50K reporting threshold

        small_txns = [a for a in amounts if a < threshold]
        if len(small_txns) >= 3 and len(small_txns) / len(amounts) >= 0.6:
            total_small = sum(small_txns)
            return {
                "pattern": "SMURFING_SEQUENCE",
                "severity": "HIGH",
                "description": f"{len(small_txns)} transfers below ₹{threshold//1000}K threshold totaling ₹{int(total_small//1000)}K",
                "small_transaction_count": len(small_txns),
                "total_smurfed_amount": int(total_small),
                "alert": f"Structuring detected — amounts kept below ₹{threshold//1000}K reporting threshold"
            }
        return None

    def _detect_rapid_forward(self, account_id, incoming, outgoing):
        if len(incoming) == 0 or len(outgoing) == 0:
            return None

        for _, in_row in incoming.iterrows():
            for _, out_row in outgoing.iterrows():
                delay = (out_row['timestamp'] - in_row['timestamp']).total_seconds() / 3600
                if 0 < delay <= 6:  # forwarded within 6 hours
                    return {
                        "pattern": "RAPID_FORWARD",
                        "severity": "CRITICAL",
                        "description": f"Received ₹{int(in_row['amount'])} and forwarded ₹{int(out_row['amount'])} within {delay:.1f} hours (same-day layering)",
                        "forward_delay_hours": round(delay, 1),
                        "alert": "Instant forwarding — account used purely as pass-through mule"
                    }
        return None

    def _score_to_level(self, score):
        if score >= 75: return "CRITICAL"
        if score >= 50: return "HIGH"
        if score >= 25: return "MEDIUM"
        if score > 0: return "LOW"
        return "CLEAR"

    def _build_timeline(self, account_id, incoming, outgoing):
        events = []
        for _, row in incoming.iterrows():
            events.append({
                "time": str(row['timestamp'])[:16],
                "type": "INCOMING",
                "amount": int(row['amount']),
                "direction": "↓ IN"
            })
        for _, row in outgoing.iterrows():
            events.append({
                "time": str(row['timestamp'])[:16],
                "type": "OUTGOING",
                "amount": int(row['amount']),
                "direction": "↑ OUT"
            })
        events.sort(key=lambda x: x['time'])
        return events

    def analyze_all_accounts(self, df: pd.DataFrame):
        accounts = set(df['sender_id']).union(set(df['receiver_id']))
        results = []
        for acc in accounts:
            result = self.analyze_account_timeline(acc, df)
            if result and result['pattern_count'] > 0:
                results.append(result)
        results.sort(key=lambda x: x['temporal_risk_score'], reverse=True)
        return results

# Global instance
lstm_detector = TemporalPatternEngine()
