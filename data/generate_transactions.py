"""
generate_transactions.py
Generates synthetic transaction data for AML testing.
Includes deliberately injected suspicious patterns.
"""

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

SEED = 42
np.random.seed(SEED)
random.seed(SEED)

CURRENCIES = ["PLN", "USD", "EUR", "CHF"]
COUNTRIES = ["PL", "DE", "US", "UK", "CH", "CY", "BVI", "PA", "MT"]
HIGH_RISK_COUNTRIES = {"CY", "BVI", "PA"}  # offshore jurisdictions
TRANSACTION_TYPES = ["TRANSFER", "WITHDRAWAL", "DEPOSIT", "PAYMENT"]

ACCOUNTS = [f"ACC{str(i).zfill(5)}" for i in range(1, 201)]


def random_timestamp(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def generate_normal_transactions(n: int, start: datetime, end: datetime) -> list[dict]:
    rows = []
    for _ in range(n):
        sender = random.choice(ACCOUNTS)
        receiver = random.choice([a for a in ACCOUNTS if a != sender])
        rows.append({
            "transaction_id": f"TXN{random.randint(100000, 999999)}",
            "timestamp": random_timestamp(start, end),
            "sender_account": sender,
            "receiver_account": receiver,
            "amount": round(np.random.lognormal(mean=7, sigma=1.5), 2),
            "currency": random.choice(CURRENCIES),
            "transaction_type": random.choice(TRANSACTION_TYPES),
            "sender_country": random.choice(COUNTRIES[:5]),
            "receiver_country": random.choice(COUNTRIES[:5]),
            "is_suspicious_injected": False,
        })
    return rows


# ── Injected suspicious patterns ──────────────────────────────────────────────

def inject_structuring(base_time: datetime) -> list[dict]:
    """Structuring / smurfing: multiple transactions just below 10 000 PLN threshold."""
    account = random.choice(ACCOUNTS)
    target = random.choice([a for a in ACCOUNTS if a != account])
    rows = []
    for i in range(random.randint(5, 9)):
        rows.append({
            "transaction_id": f"TXN_STRUCT_{i}",
            "timestamp": base_time + timedelta(hours=i * 2),
            "sender_account": account,
            "receiver_account": target,
            "amount": round(random.uniform(9000, 9999), 2),
            "currency": "PLN",
            "transaction_type": "TRANSFER",
            "sender_country": "PL",
            "receiver_country": "PL",
            "is_suspicious_injected": True,
        })
    return rows


def inject_round_amounts(base_time: datetime) -> list[dict]:
    """Round amounts: psychologically unnatural in real commerce."""
    account = random.choice(ACCOUNTS)
    target = random.choice([a for a in ACCOUNTS if a != account])
    return [
        {
            "transaction_id": f"TXN_ROUND_{i}",
            "timestamp": base_time + timedelta(days=i),
            "sender_account": account,
            "receiver_account": target,
            "amount": float(random.choice([5000, 10000, 25000, 50000, 100000])),
            "currency": "PLN",
            "transaction_type": "TRANSFER",
            "sender_country": "PL",
            "receiver_country": random.choice(list(HIGH_RISK_COUNTRIES)),
            "is_suspicious_injected": True,
        }
        for i in range(4)
    ]


def inject_unusual_hours(base_time: datetime) -> list[dict]:
    """Unusual hours: transactions at 02:00–04:00 with high amounts."""
    account = random.choice(ACCOUNTS)
    target = random.choice([a for a in ACCOUNTS if a != account])
    rows = []
    for i in range(6):
        ts = base_time.replace(hour=random.randint(2, 4), minute=random.randint(0, 59))
        ts += timedelta(days=i)
        rows.append({
            "transaction_id": f"TXN_NIGHT_{i}",
            "timestamp": ts,
            "sender_account": account,
            "receiver_account": target,
            "amount": round(random.uniform(15000, 80000), 2),
            "currency": "EUR",
            "transaction_type": "TRANSFER",
            "sender_country": "PL",
            "receiver_country": "DE",
            "is_suspicious_injected": True,
        })
    return rows


def inject_velocity_burst(base_time: datetime) -> list[dict]:
    """Velocity burst: >10 transactions within 1 hour from a single account."""
    account = random.choice(ACCOUNTS)
    rows = []
    for i in range(12):
        rows.append({
            "transaction_id": f"TXN_VEL_{i}",
            "timestamp": base_time + timedelta(minutes=i * 4),
            "sender_account": account,
            "receiver_account": random.choice(ACCOUNTS),
            "amount": round(random.uniform(500, 3000), 2),
            "currency": "PLN",
            "transaction_type": "PAYMENT",
            "sender_country": "PL",
            "receiver_country": "PL",
            "is_suspicious_injected": True,
        })
    return rows


def inject_high_risk_jurisdiction(base_time: datetime) -> list[dict]:
    """High-risk jurisdiction: funds routed through offshore accounts."""
    account = random.choice(ACCOUNTS)
    rows = []
    for i, country in enumerate(HIGH_RISK_COUNTRIES):
        rows.append({
            "transaction_id": f"TXN_HRJ_{i}",
            "timestamp": base_time + timedelta(days=i),
            "sender_account": account,
            "receiver_account": random.choice(ACCOUNTS),
            "amount": round(random.uniform(30000, 200000), 2),
            "currency": random.choice(["USD", "CHF"]),
            "transaction_type": "TRANSFER",
            "sender_country": "PL",
            "receiver_country": country,
            "is_suspicious_injected": True,
        })
    return rows


# ── Entry point ────────────────────────────────────────────────────────────────

def generate_dataset(n_normal: int = 2000, output_path: str = "data/transactions.csv") -> pd.DataFrame:
    start = datetime(2024, 1, 1)
    end = datetime(2024, 6, 30)

    rows = generate_normal_transactions(n_normal, start, end)

    # Inject suspicious patterns at specific dates
    base = datetime(2024, 3, 15, 10, 0)
    rows += inject_structuring(base)
    rows += inject_round_amounts(base + timedelta(days=10))
    rows += inject_unusual_hours(base + timedelta(days=20))
    rows += inject_velocity_burst(base + timedelta(days=30))
    rows += inject_high_risk_jurisdiction(base + timedelta(days=40))

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    df.to_csv(output_path, index=False)
    print(f"[DataGen] Saved {len(df)} transactions → {output_path}")
    return df


if __name__ == "__main__":
    generate_dataset()