"""
rules.py
AML detection rules. Each rule function receives the full DataFrame,
returns a DataFrame of flagged rows with columns:
    transaction_id, rule_name, score_contribution, detail
"""

import pandas as pd
import numpy as np

# ── Thresholds (configurable) ──────────────────────────────────────────────────
STRUCTURING_THRESHOLD = 10_000        # PLN – regulatory reporting threshold
STRUCTURING_WINDOW_H  = 24           # hours to aggregate structuring attempts
STRUCTURING_MIN_COUNT = 3            # minimum transactions in window

ROUND_AMOUNT_MODULUS  = 1000         # amount divisible by N → round flag
ROUND_AMOUNT_MIN      = 5_000        # only flag if amount exceeds this

UNUSUAL_HOUR_START    = 0            # 00:00
UNUSUAL_HOUR_END      = 5            # 05:59
UNUSUAL_HOUR_MIN_AMT  = 10_000       # only high-value night transactions

VELOCITY_WINDOW_H     = 1            # hour window
VELOCITY_MAX_TX       = 10           # flag if >N transactions in window

HIGH_RISK_COUNTRIES   = {"CY", "BVI", "PA", "KY", "VG"}
HIGH_RISK_MIN_AMT     = 5_000        # threshold for high-risk jurisdiction flag

# Score weights per rule
SCORE_WEIGHTS = {
    "structuring":          35,
    "round_amount":         15,
    "unusual_hours":        20,
    "velocity_burst":       25,
    "high_risk_jurisdiction": 30,
}


# ── Individual rule implementations ───────────────────────────────────────────

def rule_structuring(df: pd.DataFrame) -> pd.DataFrame:
    """
    Structuring / smurfing detection.
    Flag accounts that send multiple transactions below the reporting threshold
    within a rolling time window, where the SUM would exceed the threshold.

    Why: criminals deliberately keep single transactions below 10k to avoid
    mandatory Suspicious Activity Reports (SARs). Pattern: several 9k transfers
    from same account in short succession.
    """
    flags = []
    df_sorted = df.sort_values("timestamp")

    for account, group in df_sorted.groupby("sender_account"):
        group = group.copy().reset_index(drop=True)
        below = group[group["amount"] < STRUCTURING_THRESHOLD].copy()
        if len(below) < STRUCTURING_MIN_COUNT:
            continue

        # Rolling window: check each transaction as a potential window start
        for i, row in below.iterrows():
            window_end = row["timestamp"] + pd.Timedelta(hours=STRUCTURING_WINDOW_H)
            window_txns = below[
                (below["timestamp"] >= row["timestamp"]) &
                (below["timestamp"] <= window_end)
            ]
            if len(window_txns) >= STRUCTURING_MIN_COUNT and window_txns["amount"].sum() >= STRUCTURING_THRESHOLD:
                for _, flagged in window_txns.iterrows():
                    flags.append({
                        "transaction_id": flagged["transaction_id"],
                        "rule_name": "structuring",
                        "score_contribution": SCORE_WEIGHTS["structuring"],
                        "detail": (
                            f"Account {account}: {len(window_txns)} txns "
                            f"totalling {window_txns['amount'].sum():,.0f} PLN "
                            f"within {STRUCTURING_WINDOW_H}h window "
                            f"(each below {STRUCTURING_THRESHOLD:,} PLN threshold)"
                        ),
                    })
                break  # one flag per account per window is enough

    return pd.DataFrame(flags).drop_duplicates("transaction_id") if flags else pd.DataFrame(
        columns=["transaction_id", "rule_name", "score_contribution", "detail"]
    )


def rule_round_amounts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Round amount detection.
    Real commercial transactions rarely land on exact round numbers.
    Large round amounts (e.g. 10 000, 25 000, 100 000 PLN) suggest manual
    entry and possible layering of illicit funds.
    """
    mask = (
        (df["amount"] % ROUND_AMOUNT_MODULUS == 0) &
        (df["amount"] >= ROUND_AMOUNT_MIN)
    )
    flagged = df[mask].copy()
    flagged["rule_name"]           = "round_amount"
    flagged["score_contribution"]  = SCORE_WEIGHTS["round_amount"]
    flagged["detail"]              = flagged["amount"].apply(
        lambda a: f"Round amount: {a:,.0f} (divisible by {ROUND_AMOUNT_MODULUS}, above {ROUND_AMOUNT_MIN:,})"
    )
    return flagged[["transaction_id", "rule_name", "score_contribution", "detail"]]


def rule_unusual_hours(df: pd.DataFrame) -> pd.DataFrame:
    """
    Unusual-hours detection.
    High-value transfers between 00:00–05:59 are statistically anomalous
    for legitimate business. Night-time activity can indicate automated
    layering or attempts to avoid human oversight.
    """
    hour = df["timestamp"].dt.hour
    mask = (
        (hour >= UNUSUAL_HOUR_START) &
        (hour < UNUSUAL_HOUR_END) &
        (df["amount"] >= UNUSUAL_HOUR_MIN_AMT)
    )
    flagged = df[mask].copy()
    flagged["rule_name"]           = "unusual_hours"
    flagged["score_contribution"]  = SCORE_WEIGHTS["unusual_hours"]
    flagged["detail"]              = flagged.apply(
        lambda r: (
            f"Transaction at {r['timestamp'].strftime('%H:%M')} "
            f"for {r['amount']:,.0f} {r['currency']} "
            f"(outside business hours, amount ≥ {UNUSUAL_HOUR_MIN_AMT:,})"
        ),
        axis=1,
    )
    return flagged[["transaction_id", "rule_name", "score_contribution", "detail"]]


def rule_velocity_burst(df: pd.DataFrame) -> pd.DataFrame:
    """
    Velocity burst detection.
    More than N transactions from a single account within 1 hour may indicate
    automated money mule activity, card testing, or rapid layering.
    """
    flags = []
    df_sorted = df.sort_values("timestamp")

    for account, group in df_sorted.groupby("sender_account"):
        group = group.reset_index(drop=True)
        for i, row in group.iterrows():
            window_end = row["timestamp"] + pd.Timedelta(hours=VELOCITY_WINDOW_H)
            window_txns = group[
                (group["timestamp"] >= row["timestamp"]) &
                (group["timestamp"] <= window_end)
            ]
            if len(window_txns) > VELOCITY_MAX_TX:
                for _, flagged in window_txns.iterrows():
                    flags.append({
                        "transaction_id": flagged["transaction_id"],
                        "rule_name": "velocity_burst",
                        "score_contribution": SCORE_WEIGHTS["velocity_burst"],
                        "detail": (
                            f"Account {account}: {len(window_txns)} transactions "
                            f"in {VELOCITY_WINDOW_H}h window "
                            f"(threshold: >{VELOCITY_MAX_TX})"
                        ),
                    })
                break

    return pd.DataFrame(flags).drop_duplicates("transaction_id") if flags else pd.DataFrame(
        columns=["transaction_id", "rule_name", "score_contribution", "detail"]
    )


def rule_high_risk_jurisdiction(df: pd.DataFrame) -> pd.DataFrame:
    """
    High-risk jurisdiction detection.
    Transactions to/from FATF grey-listed or offshore secrecy jurisdictions
    (Cyprus, BVI, Panama, etc.) warrant enhanced due diligence per
    EU AML Directive 6AMLD and FATF Recommendations 10/12.
    """
    mask = (
        (df["receiver_country"].isin(HIGH_RISK_COUNTRIES) |
         df["sender_country"].isin(HIGH_RISK_COUNTRIES)) &
        (df["amount"] >= HIGH_RISK_MIN_AMT)
    )
    flagged = df[mask].copy()
    flagged["rule_name"]           = "high_risk_jurisdiction"
    flagged["score_contribution"]  = SCORE_WEIGHTS["high_risk_jurisdiction"]
    flagged["detail"]              = flagged.apply(
        lambda r: (
            f"Transaction involving high-risk jurisdiction: "
            f"{r['sender_country']} → {r['receiver_country']}, "
            f"amount {r['amount']:,.0f} {r['currency']}"
        ),
        axis=1,
    )
    return flagged[["transaction_id", "rule_name", "score_contribution", "detail"]]


# ── Rule registry ──────────────────────────────────────────────────────────────

ALL_RULES = [
    rule_structuring,
    rule_round_amounts,
    rule_unusual_hours,
    rule_velocity_burst,
    rule_high_risk_jurisdiction,
]