"""
TRACE-X Synthetic Dataset Generator — entities.py
Archetype classes: each generates wallets, transactions (inputs/outputs), and relay
events (IP/timing) consistent with its behavioral signature. Ground truth
(entity_type, is_illicit) is tracked internally and exported SEPARATELY from the
CSV data fed to the model — never leaked into training features.
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

    def _random_start_time(self):
        days_back = random.randint(0, self.config.get("timespan_days", 180))
        return datetime.now() - timedelta(days=days_back)

    def _new_wallet(self):
        wid = f"wallet_{self.entity_id}_{len(self.wallets):03d}_{uuid.uuid4().hex[:6]}"
        self.wallets.append(wid)
        return wid

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

    def generate(self):
        raise NotImplementedError

    def ground_truth(self):
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "is_illicit": self.is_illicit,
            "wallets": list(self.wallets),
        }


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
            txid = self._new_txid()
            wallet = random.choice(self.wallets)
            amount = round(random.lognormvariate(-2.5, 1.2), 8)
            fee = round(amount * random.uniform(0.0005, 0.003), 8)
            role = random.choice(["input", "output"])
            self._record_tx(txid, wallet, role, amount, t, fee)
            self._record_relay(txid, t, home_ip)


class LegitBusiness(BaseEntity):
    entity_type = "legit_business"
    is_illicit = False

    def generate(self):
        for _ in range(random.randint(3, 8)):
            self._new_wallet()
        t = self.start_time
        ip_pool = [self._random_ip() for _ in range(random.randint(1, 3))]
        for _ in range(random.randint(50, 200)):
            t += timedelta(minutes=random.randint(10, 240))
            txid = self._new_txid()
            wallet = random.choice(self.wallets)
            amount = round(random.lognormvariate(-1.0, 1.0), 8)
            fee = round(amount * random.uniform(0.0003, 0.002), 8)
            role = random.choices(["input", "output"], weights=[0.4, 0.6])[0]
            self._record_tx(txid, wallet, role, amount, t, fee)
            self._record_relay(txid, t, random.choice(ip_pool))
            if random.random() < 0.03:
                for _ in range(random.randint(3, 6)):
                    sub_txid = self._new_txid()
                    sub_amount = round(amount * random.uniform(0.1, 0.4), 8)
                    self._record_tx(sub_txid, wallet, "output", sub_amount, t, fee)
                    self._record_relay(sub_txid, t, random.choice(ip_pool))


class RansomwareCollector(BaseEntity):
    entity_type = "ransomware_collector"
    is_illicit = True

    def generate(self):
        collector_wallet = self._new_wallet()
        demand_amount = round(random.uniform(0.05, 2.0), 8)
        t = self.start_time
        collector_ip = self._random_ip()
        inbound = []
        for _ in range(random.randint(5, 25)):
            t += timedelta(hours=random.uniform(1, 72))
            txid = self._new_txid()
            amount = round(demand_amount * random.uniform(0.97, 1.03), 8)
            fee = round(amount * random.uniform(0.001, 0.01), 8)
            self._record_tx(txid, collector_wallet, "output", amount, t, fee)
            self._record_relay(txid, t, collector_ip)
            inbound.append((txid, amount, t))
        sweep_t = t + timedelta(hours=random.uniform(1, 12))
        sweep_txid = self._new_txid()
        total = sum(a for _, a, _ in inbound)
        self._record_tx(sweep_txid, collector_wallet, "input", total, sweep_t,
                         fee=round(total * 0.002, 8))
        self._record_relay(sweep_txid, sweep_t, collector_ip)


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
            txid = self._new_txid()
            peel_fraction = random.uniform(0.03, 0.08)
            peeled = round(current_amount * peel_fraction, 8)
            remainder = round(current_amount - peeled, 8)
            self._record_tx(txid, current_wallet, "input", current_amount, t,
                             fee=round(current_amount * 0.0005, 8))
            self._record_tx(txid, next_wallet, "output", remainder, t)
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


class MixerService(BaseEntity):
    entity_type = "mixer_coinjoin"
    is_illicit = True

    def generate(self):
        t = self.start_time
        std_denom = random.choice([0.01, 0.05, 0.1, 0.5, 1.0])
        for _ in range(random.randint(3, 10)):
            round_txid = self._new_txid()
            round_ip_pool = [self._random_ip() for _ in range(random.randint(2, 4))]
            for _ in range(random.randint(5, 15)):
                in_wallet = self._new_wallet()
                out_wallet = self._new_wallet()
                amount = round(std_denom * random.uniform(0.995, 1.005), 8)
                self._record_tx(round_txid, in_wallet, "input", amount, t,
                                 fee=round(amount * 0.0008, 8))
                self._record_tx(round_txid, out_wallet, "output", amount, t)
                self._record_relay(round_txid, t, random.choice(round_ip_pool))
            t += timedelta(hours=random.uniform(1, 24))


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
            txid = self._new_txid()
            wallet = random.choice(receiving_wallets)
            amount = round(random.lognormvariate(-3.0, 0.8), 8)
            self._record_tx(txid, wallet, "output", amount, t, fee=round(amount * 0.001, 8))
            self._record_relay(txid, t, random.choice(vendor_ip_pool))
            pending.append((wallet, amount, t))
            if len(pending) >= random.randint(8, 15):
                sweep_txid = self._new_txid()
                sweep_t = t + timedelta(hours=random.uniform(1, 6))
                total = sum(a for _, a, _ in pending)
                for w, a, _ in pending:
                    self._record_tx(sweep_txid, w, "input", a, sweep_t)
                self._record_tx(sweep_txid, vault_wallet, "output",
                                 round(total * 0.98, 8), sweep_t,
                                 fee=round(total * 0.002, 8))
                self._record_relay(sweep_txid, sweep_t, random.choice(vendor_ip_pool))
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
