"""
geoip_lookup.py — GeoIP + ASN enrichment for the TRACE-X Bitcoin pipeline.

Satisfies PS 26146's minimum dataset field requirement:
"geo_country/asn (integrate open source downloadable GeoIP database)".

Uses DB-IP Lite CSVs (free, no-signup, CC-BY-4.0 licensed) — fully offline
after the one-time download, no runtime internet dependency. Range lookups
are done via binary search (np.searchsorted) since each file has 400k-700k+
IP ranges — linear scan would be far too slow per-request.
"""

import socket
import struct
import numpy as np
import pandas as pd


def _ip_to_int(ip: str) -> int:
    try:
        return struct.unpack("!I", socket.inet_aton(ip))[0]
    except OSError:
        return -1  # malformed/IPv6 — callers should treat -1 as "unresolvable"


def load_country_index(csv_path: str):
    """
    DB-IP country-lite columns: start_ip, end_ip, country_code (no header).
    """
    df = pd.read_csv(
        csv_path, header=None,
        names=["start_ip", "end_ip", "country"],
        dtype=str,
    )
    df["start_int"] = df["start_ip"].apply(_ip_to_int)
    df["end_int"] = df["end_ip"].apply(_ip_to_int)
    df = df[df["start_int"] >= 0].sort_values("start_int").reset_index(drop=True)
    return {
        "start": df["start_int"].to_numpy(),
        "end": df["end_int"].to_numpy(),
        "country": df["country"].to_numpy(),
    }


def load_asn_index(csv_path: str):
    """
    DB-IP asn-lite columns: start_ip, end_ip, asn, asn_org (no header).
    """
    df = pd.read_csv(
        csv_path, header=None,
        names=["start_ip", "end_ip", "asn", "asn_org"],
        dtype=str,
    )
    df["start_int"] = df["start_ip"].apply(_ip_to_int)
    df["end_int"] = df["end_ip"].apply(_ip_to_int)
    df = df[df["start_int"] >= 0].sort_values("start_int").reset_index(drop=True)
    return {
        "start": df["start_int"].to_numpy(),
        "end": df["end_int"].to_numpy(),
        "asn": df["asn"].to_numpy(),
        "asn_org": df["asn_org"].to_numpy(),
    }


def _lookup(index: dict, ip: str, value_keys: list):
    ip_int = _ip_to_int(ip)
    if ip_int < 0:
        return {k: None for k in value_keys}

    starts = index["start"]
    pos = np.searchsorted(starts, ip_int, side="right") - 1
    if pos < 0 or pos >= len(starts):
        return {k: None for k in value_keys}
    if not (starts[pos] <= ip_int <= index["end"][pos]):
        return {k: None for k in value_keys}

    return {k: index[k][pos] for k in value_keys}


def lookup_country(country_index: dict, ip: str):
    return _lookup(country_index, ip, ["country"])["country"]


def lookup_asn(asn_index: dict, ip: str) -> dict:
    return _lookup(asn_index, ip, ["asn", "asn_org"])


def enrich_ip(country_index: dict, asn_index: dict, ip: str) -> dict:
    country = lookup_country(country_index, ip)
    asn_info = lookup_asn(asn_index, ip)
    return {
        "ip": ip,
        "geo_country": country,
        "asn": asn_info["asn"],
        "asn_org": asn_info["asn_org"],
    }


def enrich_relay_df(country_index: dict, asn_index: dict, relay_df: pd.DataFrame) -> pd.DataFrame:
    """
    Bulk-enrich a relay_events DataFrame (columns include src_ip, dst_ip).
    Deduplicates IPs before lookup so repeated IPs aren't re-searched.
    """
    unique_ips = pd.unique(pd.concat([relay_df["src_ip"], relay_df["dst_ip"]]).dropna())
    cache = {ip: enrich_ip(country_index, asn_index, ip) for ip in unique_ips}

    out = relay_df.copy()
    out["src_geo_country"] = out["src_ip"].map(lambda ip: cache.get(ip, {}).get("geo_country"))
    out["src_asn"] = out["src_ip"].map(lambda ip: cache.get(ip, {}).get("asn"))
    out["src_asn_org"] = out["src_ip"].map(lambda ip: cache.get(ip, {}).get("asn_org"))
    out["dst_geo_country"] = out["dst_ip"].map(lambda ip: cache.get(ip, {}).get("geo_country"))
    out["dst_asn"] = out["dst_ip"].map(lambda ip: cache.get(ip, {}).get("asn"))
    out["dst_asn_org"] = out["dst_ip"].map(lambda ip: cache.get(ip, {}).get("asn_org"))
    return out
