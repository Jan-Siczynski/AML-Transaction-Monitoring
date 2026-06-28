"""
scorer.py
Aggregates rule hits into per-transaction risk scores and risk tiers.
"""

import pandas as pd
from engine.rules import ALL_RULES

# Risk tier thresholds (0–100 normalised score)
TIER_HIGH   = 60
TIER_MEDIUM = 30
MAX_RAW_SCORE = 100  # theoretical max if all rules fire


def run_all_rules(df: pd.DataFrame) -> pd.DataFrame:
    """Execute every rule and concatenate flagged rows."""
    results = []
    for rule_fn in ALL_RULES:
        result = rule_fn(df)
        if not result.empty:
            results.append(result)
    if not results:
        return pd.DataFrame(columns=["transaction_id", "rule_name", "score_contribution", "detail"])
    return pd.concat(results, ignore_index=True)


def compute_scores(df: pd.DataFrame, flags: pd.DataFrame) -> pd.DataFrame:
    """
    Join flags back onto the transaction DataFrame.
    Each transaction gets:
      - risk_score     : sum of score_contributions (capped at 100)
      - risk_tier      : HIGH / MEDIUM / LOW
      - rules_triggered: comma-separated list of triggered rules
      - alert_details  : joined detail strings
    """
    if flags.empty:
        df = df.copy()
        df["risk_score"]      = 0
        df["risk_tier"]       = "LOW"
        df["rules_triggered"] = ""
        df["alert_details"]   = ""
        return df

    agg = (
        flags.groupby("transaction_id")
        .agg(
            risk_score      =("score_contribution", "sum"),
            rules_triggered =("rule_name",          lambda x: ", ".join(sorted(set(x)))),
            alert_details   =("detail",             lambda x: " | ".join(x)),
        )
        .reset_index()
    )
    agg["risk_score"] = agg["risk_score"].clip(upper=100)

    scored = df.merge(agg, on="transaction_id", how="left")
    scored["risk_score"]      = scored["risk_score"].fillna(0).astype(int)
    scored["rules_triggered"] = scored["rules_triggered"].fillna("")
    scored["alert_details"]   = scored["alert_details"].fillna("")

    scored["risk_tier"] = scored["risk_score"].apply(
        lambda s: "HIGH" if s >= TIER_HIGH else ("MEDIUM" if s >= TIER_MEDIUM else "LOW")
    )
    return scored


def score_transactions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Main entry point.
    Returns (scored_df, flags_df).
    """
    flags  = run_all_rules(df)
    scored = compute_scores(df, flags)
    return scored, flags