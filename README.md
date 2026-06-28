# 🛡 AML Transaction Monitoring

A Python-based Anti-Money Laundering (AML) transaction monitoring system that detects suspicious financial activity using rule-based pattern detection, risk scoring, and automated alert report generation.

---

## 📌 What is AML?

**Anti-Money Laundering (AML)** refers to a set of laws, regulations, and procedures designed to prevent criminals from disguising illegally obtained funds as legitimate income. Financial institutions are legally required (EU 6AMLD, FATF Recommendations) to monitor transactions and report suspicious activity via **Suspicious Activity Reports (SARs)**.

---

## 🏗 Project Structure

```
aml_monitor/
│
├── main.py                        # Pipeline entry point
│
├── data/
│   └── generate_transactions.py   # Synthetic dataset generator (2000+ transactions)
│
├── engine/
│   ├── rules.py                   # 5 AML detection rules
│   └── scorer.py                  # Risk scoring & tier classification
│
├── reports/
│   └── report.py                  # Automated HTML alert report generator
│
└── tests/
    └── test_rules.py              # 15 unit tests (pytest)
```

---

## 🔍 Detected Patterns (Rules)

| Rule | Score | Pattern |
|---|---|---|
| **Structuring** | +35 | Multiple transactions just below the 10,000 PLN reporting threshold within 24h (smurfing) |
| **Velocity Burst** | +25 | More than 10 transactions from a single account within 1 hour |
| **High-Risk Jurisdiction** | +30 | Transfers to/from offshore countries (Cyprus, BVI, Panama) above 5,000 |
| **Unusual Hours** | +20 | High-value transfers (>10,000) between 00:00–05:59 |
| **Round Amounts** | +15 | Amounts divisible by 1,000 above 5,000 (e.g. 25,000, 100,000 PLN) |

Scores accumulate — a transaction can trigger multiple rules simultaneously.

---

## 📊 Risk Tiers

| Tier | Score Range | Action |
|---|---|---|
| 🔴 HIGH | ≥ 60 | Immediate analyst review |
| 🟡 MEDIUM | 30–59 | Enhanced due diligence |
| 🟢 LOW | 0–29 | No action required |

---

## 🚀 How to Run

**Requirements:** Python 3.10+

```bash
# Install dependencies
pip install -r requirements.txt

# Run full pipeline (generates data + report)
python main.py

# Run on existing CSV
python main.py --input data/transactions.csv

# Run unit tests
python -m pytest tests/ -v
```

Output files:
- `data/transactions.csv` — raw synthetic transactions
- `data/transactions_scored.csv` — transactions with risk scores
- `reports/aml_alert_report.html` — alert report (open in browser)

---

## 📈 Sample Results (2,033 transactions)

```
Total transactions analysed :  2,033
Rule hits (flag events)     :     87
─────────────────────────────────────
HIGH  risk alerts           :     12  (0.6%)
MEDIUM risk alerts          :     15  (0.7%)
LOW   (clean)               :  2,006  (98.7%)

Detection recall on injected patterns: 81.8%
```

---

## 🛠 Tech Stack

- **Python 3.12**
- **Pandas** — transaction processing & rule logic
- **NumPy** — synthetic data generation
- **pytest** — unit testing
- **HTML/CSS** — self-contained alert report (no external dependencies)

---

## ⚠️ Disclaimer

This project is for educational and portfolio purposes only. The synthetic data, rules, and thresholds are illustrative and do not constitute legal or compliance advice. Any real AML system must be validated by qualified compliance professionals.
