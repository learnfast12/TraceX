"""
TRACE-X Synthetic Dataset Generator — entities.py (v2, balanced UTXO edition)
Every generated transaction now obeys real UTXO accounting: sum(inputs) =
sum(outputs) + fee. This is what makes common-input-ownership clustering and
change-address detection meaningful instead of vacuous.
"""

import random
import uuid
from datetime import datetime, timedelta


class BaseEntity:
    entity_type = "base"
    is_illicit = False

    def __init__(self, entity_id, config, start_time=None):
        self.entity_id = entity_id
        self.config = config
        self.wallets = []
        self.start_time = start_time or self._random_start_time()
        self.transactions = []
        self.relay_events = []

    # -- helpers -------------------------------------------------------
    def _random_start_time(self):
        days_back = random.randint(0, self.config.get("timespan_days", 180))
        return datetime.now() - timedelta(days=days_back)

    def _new_wallet(self):
        wid = f"wallet_{self.entity_id}_{len(self.wallets):03d}_{uuid.uuid4().hex[:6]}"
        self.wallets.append(wid)
        return wid

    def _external_wallet(self):
        """Counterparty wallet NOT owned by this entity (victim, merchant, cash-out
        sink, other CoinJoin participant's own entity, etc). Never added to
        self.wallets, so it can never be pulled into this entity's cluster."""
        return f"ext_{uuid.uuid4().hex[:10]}"

    def _new_txid(self):
        return f"tx_{uuid.uuid4().hex[:16]}"

    def _random_ip(self, pool=None):
        pool = pool or self.config.get("ip_pool")
        if pool:
            return random.choice(pool)
        return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

    def _script_type(self):
        return random.choices(["P2PKH", "P2WPKH", "P2TR"], weights=[0.5, 0.35, 0.15])[0]

    def _record_tx(self, txid, wallet, role, amount, timestamp, fee=0.0, script_type=None):
        self.transactions.append({
            "txid": txid, "wallet": wallet, "role": role,
            "amount": round(amount, 8), "timestamp": timestamp.isoformat(),
            "fee": round(fee, 8), "script_type": script_type or self._script_type()
        })

    def _record_relay(self, txid, timestamp, src_ip, dst_ip=None, src_port=None, dst_port=None):
        self.relay_events.append({
            "txid": txid, "timestamp": timestamp.isoformat(),
            "src_ip": src_ip, "dst_ip": dst_ip or self._random_ip(),
            "src_port": src_port or random.randint(1024, 65535),
            "dst_port": dst_port or 8333
        })

    def _make_tx(self, timestamp, inputs, outputs):
        """
        inputs / outputs: list of (wallet, amount) tuples.
        Balances automatically: fee = sum(inputs) - sum(outputs). If rounding
        pushes fee slightly negative, the shortfall is shaved off the last
        output rather than allowed to violate conservation.
        Returns the shared txid.
        """
        total_in = sum(a for _, a in inputs)
        total_out = sum(a for _, a in outputs)
        fee = round(total_in - total_out, 8)

        if fee < 0:
            w, a = outputs[-1]
            outputs = outputs[:-1] + [(w, round(a + fee, 8))]  # shrink last output
            fee = 0.0

        txid = self._new_txid()
        for wallet, amount in inputs:
            self._record_tx(txid, wallet, "input", amount, timestamp, fee=fee)
        for wallet, amount in outputs:
            self._record_tx(txid, wallet, "output", amount, timestamp, fee=fee)
        return txid

    def generate(self):
        raise NotImplementedError

    def ground_truth(self):
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "is_illicit": self.is_illicit,
            "wallets": list(self.wallets),
        }


# ---------------------------------------------------------------------------
# Legit individual — mostly single-input spends, occasional payment+change
# ---------------------------------------------------------------------------

class LegitIndividual(BaseEntity):
    entity_type = "legit_individual"
    is_illicit = False

    def generate(self):
        for _ in range(random.randint(1, 2)):
            self._new_wallet()
        t = self.start_time
        home_ip = self._random_ip()

        for _ in range(random.randint(2, 15)):
            t += timedelta(hours=random.randint(6, 96))
            in_wallet = random.choice(self.wallets)
            in_amount = round(random.lognormvariate(-2.0, 1.0), 8)

            if random.random() < 0.5 and in_amount > 0.002:
                pay_amt = round(in_amount * random.uniform(0.3, 0.8), 8)
                change_wallet = self._new_wallet()  # fresh change address, own entity
                outputs = [(self._external_wallet(), pay_amt),
                           (change_wallet, round(in_amount - pay_amt, 8))]
            else:
                outputs = [(self._external_wallet(), in_amount)]

            txid = self._make_tx(t, [(in_wallet, in_amount)], outputs)
            self._record_relay(txid, t, home_ip)


# ---------------------------------------------------------------------------
# Legit business — regular cadence, stable infra, occasional multi-wallet
# consolidation (genuine common-input signal) and batch payouts
# ---------------------------------------------------------------------------

class LegitBusiness(BaseEntity):
    entity_type = "legit_business"
    is_illicit = False

    def _pick_spend_wallet(self):
        """Real coin-selection prefers recently-received UTXOs over uniform
        draws across an entity's entire address history. 70% of the time,
        pick from the 3 most-recently-created wallets; 30% uniform (models
        occasionally sweeping an old, dormant address)."""
        recent = self.wallets[-3:]
        if random.random() < 0.7 and recent:
            return random.choice(recent)
        return random.choice(self.wallets)

    def generate(self):
        for _ in range(random.randint(3, 8)):
            self._new_wallet()
        t = self.start_time
        ip_pool = [self._random_ip() for _ in range(random.randint(1, 3))]

        for _ in range(random.randint(50, 200)):
            t += timedelta(minutes=random.randint(10, 240))
            roll = random.random()

            if roll < 0.15 and len(self.wallets) >= 2:
                # consolidation — multiple own wallets co-signing one tx
                k = random.randint(2, min(3, len(self.wallets)))
                in_wallets = random.sample(self.wallets, k)
                in_amounts = [round(random.lognormvariate(-1.0, 1.0), 8) for _ in in_wallets]
                out_wallet = random.choice(self.wallets)
                txid = self._make_tx(t, list(zip(in_wallets, in_amounts)),
                                      [(out_wallet, round(sum(in_amounts) * 0.998, 8))])

            elif roll < 0.20:
                # batch payout — one input, several external recipients
                in_wallet = self._pick_spend_wallet()
                in_amount = round(random.lognormvariate(0.0, 1.0), 8)
                n = random.randint(3, 6)
                shares = [random.random() for _ in range(n)]
                shares = [s / sum(shares) for s in shares]
                outputs = [(self._external_wallet(), round(in_amount * s * 0.997, 8)) for s in shares]
                txid = self._make_tx(t, [(in_wallet, in_amount)], outputs)

            else:
                in_wallet = self._pick_spend_wallet()
                in_amount = round(random.lognormvariate(-1.0, 1.0), 8)
                if random.random() < 0.4 and in_amount > 0.003:
                    pay_amt = round(in_amount * random.uniform(0.3, 0.7), 8)
                    change_wallet = self._new_wallet()
                    outputs = [(self._external_wallet(), pay_amt),
                               (change_wallet, round(in_amount - pay_amt, 8))]
                else:
                    outputs = [(self._external_wallet(), in_amount)]
                txid = self._make_tx(t, [(in_wallet, in_amount)], outputs)

            self._record_relay(txid, t, random.choice(ip_pool))


# ---------------------------------------------------------------------------
# Ransomware collector — near-identical inbound "ransom quote" amounts from
# distinct victims, static infra, then a single consolidating sweep-out
# ---------------------------------------------------------------------------

class RansomwareCollector(BaseEntity):
    entity_type = "ransomware_collector"
    is_illicit = True

    def generate(self):
        collector_wallet = self._new_wallet()
        demand_amount = round(random.uniform(0.05, 2.0), 8)
        t = self.start_time
        collector_ip = self._random_ip()

        received = []
        for _ in range(random.randint(5, 25)):
            t += timedelta(hours=random.uniform(1, 72))
            victim_wallet = self._external_wallet()
            amount = round(demand_amount * random.uniform(0.97, 1.03), 8)  # tight jitter
            received_amt = round(amount * 0.995, 8)  # small implicit fee shaved via _make_tx
            txid = self._make_tx(t, [(victim_wallet, amount)], [(collector_wallet, received_amt)])
            self._record_relay(txid, t, collector_ip)
            received.append(received_amt)

        sweep_t = t + timedelta(hours=random.uniform(1, 12))
        total = round(sum(received), 8)
        next_hop = self._new_wallet()
        txid = self._make_tx(sweep_t, [(collector_wallet, total)],
                              [(next_hop, round(total * 0.998, 8))])
        self._record_relay(txid, sweep_t, collector_ip)


# ---------------------------------------------------------------------------
# Peeling-chain launderer — genuine 2-output hops (peel sink + next-hop
# remainder), sloppy (reused IP, tight timing) vs careful (Tor-like rotating
# IPs, randomized delay)
# ---------------------------------------------------------------------------

class PeelingChainLauncher(BaseEntity):
    entity_type = "peeling_chain"
    is_illicit = True
    careful = False

    def generate(self):
        chain_length = random.randint(self.config.get("peel_min_hops", 6),
                                       self.config.get("peel_max_hops", 20))
        current_amount = round(random.uniform(1.0, 15.0), 8)
        t = self.start_time
        current_wallet = self._new_wallet()

        for _ in range(chain_length):
            next_wallet = self._new_wallet()
            peel_fraction = random.uniform(0.03, 0.08)
            peeled = round(current_amount * peel_fraction, 8)
            remainder = round(current_amount - peeled, 8)
            peel_sink = self._external_wallet()  # cash-out / merchant, not this entity

            txid = self._make_tx(t, [(current_wallet, current_amount)],
                                  [(peel_sink, peeled), (next_wallet, remainder)])

            if self.careful:
                ip = self._random_ip(self.config.get("tor_like_ip_pool"))
                t += timedelta(hours=random.uniform(4, 48))
            else:
                ip = self._random_ip()
                t += timedelta(minutes=random.uniform(10, 90))

            self._record_relay(txid, t, ip)
            current_wallet, current_amount = next_wallet, remainder


class PeelingChainSloppy(PeelingChainLauncher):
    entity_type = "peeling_chain_sloppy"
    careful = False


class PeelingChainCareful(PeelingChainLauncher):
    entity_type = "peeling_chain_careful"
    careful = True


# ---------------------------------------------------------------------------
# Mixer / CoinJoin — a REAL CoinJoin shape: one transaction, many inputs
# from many participants, many near-equal-denomination outputs
# ---------------------------------------------------------------------------

class MixerService(BaseEntity):
    entity_type = "mixer_coinjoin"
    is_illicit = True

    def generate(self):
        t = self.start_time
        std_denom = random.choice([0.01, 0.05, 0.1, 0.5, 1.0])

        for _ in range(random.randint(3, 10)):
            round_ip_pool = [self._random_ip() for _ in range(random.randint(2, 4))]
            n = random.randint(5, 15)

            inputs, outputs = [], []
            for _ in range(n):
                inputs.append((self._new_wallet(), round(std_denom * random.uniform(1.0, 1.02), 8)))
                outputs.append((self._new_wallet(), round(std_denom * random.uniform(0.995, 1.005), 8)))

            txid = self._make_tx(t, inputs, outputs)  # single shared tx — real CoinJoin
            self._record_relay(txid, t, random.choice(round_ip_pool))
            t += timedelta(hours=random.uniform(1, 24))


# ---------------------------------------------------------------------------
# Darknet vendor — many small balanced buy-ins, periodic consolidation sweep
# into a small set of vault wallets, Tor-like broadcast infra
# ---------------------------------------------------------------------------

class DarknetVendor(BaseEntity):
    entity_type = "darknet_vendor"
    is_illicit = True

    def generate(self):
        receiving_wallets = [self._new_wallet() for _ in range(random.randint(5, 15))]
        vault_wallet = self._new_wallet()
        t = self.start_time
        vendor_ip_pool = [self._random_ip(self.config.get("tor_like_ip_pool"))
                           for _ in range(random.randint(2, 5))]

        pending = []
        for _ in range(random.randint(30, 100)):
            t += timedelta(hours=random.uniform(0.5, 12))
            buyer_wallet = self._external_wallet()
            wallet = random.choice(receiving_wallets)
            amount = round(random.lognormvariate(-3.0, 0.8), 8)
            received_amt = round(amount * 0.999, 8)
            txid = self._make_tx(t, [(buyer_wallet, amount)], [(wallet, received_amt)])
            self._record_relay(txid, t, random.choice(vendor_ip_pool))
            pending.append((wallet, received_amt))

            if len(pending) >= random.randint(8, 15):
                sweep_t = t + timedelta(hours=random.uniform(1, 6))
                total = round(sum(a for _, a in pending), 8)
                txid = self._make_tx(sweep_t, pending, [(vault_wallet, round(total * 0.998, 8))])
                self._record_relay(txid, sweep_t, random.choice(vendor_ip_pool))
                pending = []


ARCHETYPES = {
    "legit_individual": LegitIndividual,
    "legit_business": LegitBusiness,
    "ransomware_collector": RansomwareCollector,
    "peeling_chain_sloppy": PeelingChainSloppy,
    "peeling_chain_careful": PeelingChainCareful,
    "mixer_coinjoin": MixerService,
    "darknet_vendor": DarknetVendor,
}
