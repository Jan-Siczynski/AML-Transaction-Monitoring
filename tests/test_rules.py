"""
tests/test_rules.py
Unit tests for each AML detection rule.
Run with: python -m pytest tests/ -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import pytest
from datetime import datetime, timedelta

from engine.rules import (
    rule_structuring,
    rule_round_amounts,
    rule_unusual_hours,
    rule_velocity_burst,
    rule_high_risk_jurisdiction,
)
from engine.scorer import score_transactions


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_txn(txn_id, sender, receiver, amount, currency="PLN",
             txn_type="TRANSFER", sender_country="PL", receiver_country="PL",
             timestamp=None):
    if timestamp is None:
        timestamp = datetime(2024, 3, 15, 12, 0)
    return {
        "transaction_id": txn_id,
        "timestamp": pd.Timestamp(timestamp),
        "sender_account": sender,
        "receiver_account": receiver,
        "amount": float(amount),
        "currency": currency,
        "transaction_type": txn_type,
        "sender_country": sender_country,
        "receiver_country": receiver_country,
        "is_suspicious_injected": False,
    }


# ── Structuring ────────────────────────────────────────────────────────────────

def test_structuring_detects_classic_smurfing():
    base = datetime(2024, 3, 15, 9, 0)
    rows = [make_txn(f"S{i}", "ACC001", "ACC002", 9500, timestamp=base + timedelta(hours=i))
            for i in range(5)]
    df = pd.DataFrame(rows)
    result = rule_structuring(df)
    assert len(result) > 0, "Should flag structuring pattern"
    assert all(result["rule_name"] == "structuring")


def test_structuring_no_false_positive_single_txn():
    df = pd.DataFrame([make_txn("S1", "ACC001", "ACC002", 9500)])
    result = rule_structuring(df)
    assert len(result) == 0, "Single transaction should not trigger structuring"


def test_structuring_above_threshold_not_flagged():
    """Transactions above the threshold are not structuring."""
    base = datetime(2024, 3, 15, 9, 0)
    rows = [make_txn(f"S{i}", "ACC001", "ACC002", 15000, timestamp=base + timedelta(hours=i))
            for i in range(5)]
    df = pd.DataFrame(rows)
    result = rule_structuring(df)
    assert len(result) == 0


# ── Round amounts ──────────────────────────────────────────────────────────────

def test_round_amount_detects_exact_round():
    df = pd.DataFrame([make_txn("R1", "ACC001", "ACC002", 10000)])
    result = rule_round_amounts(df)
    assert len(result) == 1
    assert result.iloc[0]["rule_name"] == "round_amount"


def test_round_amount_ignores_small_round():
    df = pd.DataFrame([make_txn("R2", "ACC001", "ACC002", 1000)])
    result = rule_round_amounts(df)
    assert len(result) == 0, "Small round amounts below threshold should not flag"


def test_round_amount_ignores_non_round():
    df = pd.DataFrame([make_txn("R3", "ACC001", "ACC002", 10347.89)])
    result = rule_round_amounts(df)
    assert len(result) == 0


# ── Unusual hours ──────────────────────────────────────────────────────────────

def test_unusual_hours_flags_night_high_value():
    ts = datetime(2024, 3, 15, 3, 30)
    df = pd.DataFrame([make_txn("N1", "ACC001", "ACC002", 20000, timestamp=ts)])
    result = rule_unusual_hours(df)
    assert len(result) == 1
    assert result.iloc[0]["rule_name"] == "unusual_hours"


def test_unusual_hours_no_flag_daytime():
    ts = datetime(2024, 3, 15, 14, 0)
    df = pd.DataFrame([make_txn("N2", "ACC001", "ACC002", 20000, timestamp=ts)])
    result = rule_unusual_hours(df)
    assert len(result) == 0


def test_unusual_hours_no_flag_small_night():
    ts = datetime(2024, 3, 15, 3, 0)
    df = pd.DataFrame([make_txn("N3", "ACC001", "ACC002", 500, timestamp=ts)])
    result = rule_unusual_hours(df)
    assert len(result) == 0, "Low amount night transactions should not flag"


# ── Velocity burst ─────────────────────────────────────────────────────────────

def test_velocity_burst_detects_rapid_fire():
    base = datetime(2024, 3, 15, 10, 0)
    rows = [make_txn(f"V{i}", "ACC001", f"ACC{i+10}", 1000,
                     timestamp=base + timedelta(minutes=i * 3))
            for i in range(12)]
    df = pd.DataFrame(rows)
    result = rule_velocity_burst(df)
    assert len(result) > 0, "12 transactions in 1 hour should trigger velocity burst"


def test_velocity_burst_no_false_positive():
    base = datetime(2024, 3, 15, 10, 0)
    rows = [make_txn(f"V{i}", "ACC001", f"ACC{i+10}", 1000,
                     timestamp=base + timedelta(hours=i * 3))
            for i in range(5)]
    df = pd.DataFrame(rows)
    result = rule_velocity_burst(df)
    assert len(result) == 0, "5 transactions spread over hours should not flag"


# ── High-risk jurisdiction ─────────────────────────────────────────────────────

def test_high_risk_jurisdiction_flags_offshore():
    df = pd.DataFrame([make_txn("H1", "ACC001", "ACC002", 50000,
                                receiver_country="CY")])
    result = rule_high_risk_jurisdiction(df)
    assert len(result) == 1
    assert result.iloc[0]["rule_name"] == "high_risk_jurisdiction"


def test_high_risk_jurisdiction_ignores_safe_countries():
    df = pd.DataFrame([make_txn("H2", "ACC001", "ACC002", 50000,
                                receiver_country="DE")])
    result = rule_high_risk_jurisdiction(df)
    assert len(result) == 0


def test_high_risk_jurisdiction_ignores_small_amount():
    df = pd.DataFrame([make_txn("H3", "ACC001", "ACC002", 100,
                                receiver_country="BVI")])
    result = rule_high_risk_jurisdiction(df)
    assert len(result) == 0


# ── Scorer integration ─────────────────────────────────────────────────────────

def test_scorer_assigns_high_tier_for_combined_rules():
    """Transaction triggering multiple rules should reach HIGH tier."""
    ts = datetime(2024, 3, 15, 3, 0)  # unusual hour
    rows = [
        make_txn(f"MX{i}", "ACC001", "ACC999", 10000,  # round + high-risk
                 receiver_country="CY", timestamp=ts + timedelta(minutes=i))
        for i in range(3)
    ]
    df = pd.DataFrame(rows)
    scored, flags = score_transactions(df)
    top = scored.nlargest(1, "risk_score").iloc[0]
    assert top["risk_score"] >= 30, "Multiple rule hits should elevate score"


def test_scorer_clean_transaction_stays_low():
    ts = datetime(2024, 3, 15, 14, 0)
    df = pd.DataFrame([make_txn("C1", "ACC001", "ACC002", 347.50, timestamp=ts)])
    scored, _ = score_transactions(df)
    assert scored.iloc[0]["risk_tier"] == "LOW"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])