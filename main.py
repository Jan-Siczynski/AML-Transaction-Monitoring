"""
main.py
AML Transaction Monitoring Pipeline

Usage:
    python main.py                     # generate synthetic data + run full pipeline
    python main.py --input data/transactions.csv  # use existing CSV

Pipeline:
    1. Load / generate transactions
    2. Run AML rules engine
    3. Score each transaction (0–100)
    4. Generate HTML alert report
    5. Print summary to console
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

# ── Ensure project root is on path ────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from data.generate_transactions import generate_dataset
from engine.scorer import score_transactions
from reports.report import generate_report


def print_summary(scored: pd.DataFrame, flags: pd.DataFrame) -> None:
    n_total  = len(scored)
    n_high   = int((scored["risk_tier"] == "HIGH").sum())
    n_medium = int((scored["risk_tier"] == "MEDIUM").sum())
    n_low    = int((scored["risk_tier"] == "LOW").sum())
    n_flags  = len(flags)

    print("\n" + "═" * 60)
    print("  AML MONITORING PIPELINE — SUMMARY")
    print("═" * 60)
    print(f"  Total transactions analysed : {n_total:>6,}")
    print(f"  Rule hits (flag events)     : {n_flags:>6,}")
    print(f"  ─────────────────────────────────")
    print(f"  HIGH  risk alerts           : {n_high:>6,}  ({n_high/n_total*100:.1f}%)")
    print(f"  MEDIUM risk alerts          : {n_medium:>6,}  ({n_medium/n_total*100:.1f}%)")
    print(f"  LOW   (clean)               : {n_low:>6,}  ({n_low/n_total*100:.1f}%)")
    print("═" * 60)

    if n_high > 0:
        print("\n  TOP HIGH-RISK TRANSACTIONS:")
        top = scored[scored["risk_tier"] == "HIGH"].nlargest(5, "risk_score")
        for _, r in top.iterrows():
            print(
                f"  [{r['risk_score']:>3}] {r['transaction_id']:<15}"
                f"  {r['amount']:>10,.0f} {r['currency']}"
                f"  | {r['rules_triggered']}"
            )

    # Precision check against injected ground truth
    if "is_suspicious_injected" in scored.columns:
        detected_injected = scored[
            (scored["is_suspicious_injected"]) &
            (scored["risk_tier"] != "LOW")
        ]
        total_injected = scored["is_suspicious_injected"].sum()
        recall = len(detected_injected) / total_injected * 100 if total_injected else 0
        print(f"\n  DETECTION RECALL (injected patterns): {recall:.1f}% ({len(detected_injected)}/{total_injected})")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="AML Transaction Monitoring Pipeline")
    parser.add_argument("--input", type=str, default=None, help="Path to existing transactions CSV")
    parser.add_argument("--output", type=str, default="reports/aml_alert_report.html")
    parser.add_argument("--n", type=int, default=2000, help="Number of normal transactions to generate")
    args = parser.parse_args()

    # ── Step 1: Load or generate data ─────────────────────────────────────────
    if args.input and Path(args.input).exists():
        print(f"[Pipeline] Loading transactions from {args.input} …")
        df = pd.read_csv(args.input, parse_dates=["timestamp"])
    else:
        print("[Pipeline] Generating synthetic transaction dataset …")
        Path("data").mkdir(exist_ok=True)
        df = generate_dataset(n_normal=args.n, output_path="data/transactions.csv")

    print(f"[Pipeline] Loaded {len(df):,} transactions.")

    # ── Step 2–3: Score transactions ───────────────────────────────────────────
    print("[Pipeline] Running AML rules engine …")
    scored, flags = score_transactions(df)
    print(f"[Pipeline] Scoring complete. {len(flags)} rule flags generated.")

    # ── Step 4: Generate report ────────────────────────────────────────────────
    Path("reports").mkdir(exist_ok=True)
    report_path = generate_report(scored, flags, output_path=args.output)

    # ── Step 5: Console summary ────────────────────────────────────────────────
    print_summary(scored, flags)
    print(f"  Report → {report_path}\n")

    # ── Persist scored CSV ─────────────────────────────────────────────────────
    scored_path = "data/transactions_scored.csv"
    scored.to_csv(scored_path, index=False)
    print(f"[Pipeline] Scored transactions saved → {scored_path}")


if __name__ == "__main__":
    main()