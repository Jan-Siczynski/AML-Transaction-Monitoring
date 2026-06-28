"""
report.py
Generates an automated AML alert report as a self-contained HTML file.
No charting libraries needed – pure HTML/CSS tables and stat cards.
"""

import pandas as pd
from datetime import datetime
from pathlib import Path


# ── HTML template helpers ──────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #0d1117;
    color: #e6edf3;
    padding: 32px;
    line-height: 1.55;
}
h1 { font-size: 1.6rem; font-weight: 700; color: #f0f6fc; margin-bottom: 4px; }
h2 { font-size: 1.05rem; font-weight: 600; color: #8b949e; margin-bottom: 20px;
     text-transform: uppercase; letter-spacing: .08em; }
h3 { font-size: .9rem; font-weight: 600; color: #8b949e;
     text-transform: uppercase; letter-spacing: .07em; margin-bottom: 12px; }
.header { border-bottom: 1px solid #21262d; padding-bottom: 20px; margin-bottom: 32px; }
.meta { color: #8b949e; font-size: .82rem; margin-top: 6px; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 36px; }
.card {
    background: #161b22; border: 1px solid #21262d;
    border-radius: 8px; padding: 20px;
}
.card .val { font-size: 2rem; font-weight: 700; }
.card .lbl { font-size: .75rem; color: #8b949e; text-transform: uppercase; margin-top: 4px; }
.card.high   .val { color: #f85149; }
.card.medium .val { color: #e3b341; }
.card.low    .val { color: #3fb950; }
.card.total  .val { color: #58a6ff; }
table { width: 100%; border-collapse: collapse; font-size: .83rem; }
th {
    background: #161b22; color: #8b949e;
    text-align: left; padding: 10px 12px;
    border-bottom: 1px solid #21262d;
    font-weight: 600; font-size: .75rem; text-transform: uppercase; letter-spacing:.05em;
}
td { padding: 9px 12px; border-bottom: 1px solid #161b22; vertical-align: top; }
tr:hover td { background: #161b22; }
.tier { display:inline-block; padding: 2px 10px; border-radius: 999px;
        font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }
.tier-HIGH   { background:#3d0c0c; color:#f85149; }
.tier-MEDIUM { background:#2d2006; color:#e3b341; }
.tier-LOW    { background:#0d2818; color:#3fb950; }
.rules { font-size:.75rem; color:#8b949e; }
.section { background: #161b22; border: 1px solid #21262d;
           border-radius: 8px; padding: 24px; margin-bottom: 28px; }
.breakdown { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 28px; }
.bar-row { display:flex; align-items:center; gap:10px; margin-bottom:10px; font-size:.82rem; }
.bar-label { width:140px; color:#8b949e; }
.bar-track { flex:1; background:#21262d; border-radius:4px; height:8px; }
.bar-fill  { background:#58a6ff; border-radius:4px; height:8px; }
.bar-count { width:40px; text-align:right; color:#f0f6fc; font-weight:600; }
footer { color:#484f58; font-size:.75rem; margin-top:40px; text-align:center; }
"""


def _tier_badge(tier: str) -> str:
    return f'<span class="tier tier-{tier}">{tier}</span>'


def _stat_card(label: str, value, css_class: str = "total") -> str:
    return f"""
    <div class="card {css_class}">
        <div class="val">{value}</div>
        <div class="lbl">{label}</div>
    </div>"""


def _bar(label: str, count: int, max_count: int, color: str = "#58a6ff") -> str:
    pct = int(count / max_count * 100) if max_count else 0
    return f"""
    <div class="bar-row">
        <div class="bar-label">{label}</div>
        <div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>
        <div class="bar-count">{count}</div>
    </div>"""


# ── Main report function ───────────────────────────────────────────────────────

def generate_report(
    scored: pd.DataFrame,
    flags: pd.DataFrame,
    output_path: str = "reports/aml_alert_report.html",
) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    alerts = scored[scored["risk_tier"].isin(["HIGH", "MEDIUM"])].sort_values(
        "risk_score", ascending=False
    )

    n_total  = len(scored)
    n_high   = int((scored["risk_tier"] == "HIGH").sum())
    n_medium = int((scored["risk_tier"] == "MEDIUM").sum())
    n_low    = int((scored["risk_tier"] == "LOW").sum())

    # Rule frequency
    rule_counts: dict[str, int] = {}
    if not flags.empty:
        rule_counts = flags["rule_name"].value_counts().to_dict()

    RULE_COLORS = {
        "structuring":            "#f85149",
        "velocity_burst":         "#e3b341",
        "high_risk_jurisdiction": "#d29922",
        "unusual_hours":          "#58a6ff",
        "round_amount":           "#3fb950",
    }

    max_rule_count = max(rule_counts.values(), default=1)
    bars_html = "".join(
        _bar(rule.replace("_", " ").title(), cnt, max_rule_count, RULE_COLORS.get(rule, "#58a6ff"))
        for rule, cnt in sorted(rule_counts.items(), key=lambda x: -x[1])
    )

    # Alerts table rows
    table_rows = ""
    for _, row in alerts.head(50).iterrows():
        table_rows += f"""
        <tr>
            <td><code style="color:#58a6ff;font-size:.8rem">{row['transaction_id']}</code></td>
            <td>{row['timestamp'].strftime('%Y-%m-%d %H:%M') if pd.notnull(row.get('timestamp')) else ''}</td>
            <td>{row['sender_account']}</td>
            <td>{row['receiver_account']}</td>
            <td><strong>{row['amount']:,.2f}</strong> {row['currency']}</td>
            <td>{row['sender_country']} → {row['receiver_country']}</td>
            <td>{_tier_badge(row['risk_tier'])}</td>
            <td><strong style="color:#f0f6fc">{row['risk_score']}</strong></td>
            <td class="rules">{row['rules_triggered']}</td>
        </tr>"""

    # Account risk summary
    account_risk = (
        scored[scored["risk_tier"] != "LOW"]
        .groupby("sender_account")
        .agg(
            total_flagged_txns=("transaction_id", "count"),
            max_score=("risk_score", "max"),
            total_flagged_amount=("amount", "sum"),
        )
        .sort_values("max_score", ascending=False)
        .head(15)
        .reset_index()
    )

    acct_rows = ""
    for _, r in account_risk.iterrows():
        tier = "HIGH" if r["max_score"] >= 60 else "MEDIUM"
        acct_rows += f"""
        <tr>
            <td><code style="color:#58a6ff">{r['sender_account']}</code></td>
            <td>{int(r['total_flagged_txns'])}</td>
            <td><strong>{r['total_flagged_amount']:,.0f}</strong></td>
            <td>{_tier_badge(tier)}</td>
            <td><strong>{int(r['max_score'])}</strong></td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AML Alert Report – {generated_at[:10]}</title>
<style>{CSS}</style>
</head>
<body>

<div class="header">
    <h1>🛡 AML Transaction Monitoring — Alert Report</h1>
    <h2>Automated Suspicious Activity Analysis</h2>
    <div class="meta">
        Generated: {generated_at} &nbsp;|&nbsp;
        Period: {scored['timestamp'].min().date()} – {scored['timestamp'].max().date()} &nbsp;|&nbsp;
        Engine: v1.0 &nbsp;|&nbsp; Classification: <strong style="color:#f85149">CONFIDENTIAL</strong>
    </div>
</div>

<div class="grid">
    {_stat_card("Total Transactions", f"{n_total:,}", "total")}
    {_stat_card("HIGH Risk Alerts", n_high, "high")}
    {_stat_card("MEDIUM Risk Alerts", n_medium, "medium")}
    {_stat_card("Clean (LOW)", f"{n_low:,}", "low")}
</div>

<div class="breakdown">
    <div class="section">
        <h3>Rule Triggers</h3>
        {bars_html if bars_html else '<p style="color:#484f58">No flags triggered.</p>'}
    </div>
    <div class="section">
        <h3>Risk Distribution</h3>
        {_bar("HIGH risk", n_high, n_total, "#f85149")}
        {_bar("MEDIUM risk", n_medium, n_total, "#e3b341")}
        {_bar("LOW / clean", n_low, n_total, "#3fb950")}
        <div style="margin-top:16px;color:#484f58;font-size:.78rem">
            Alert rate: <strong style="color:#f0f6fc">
            {(n_high + n_medium) / n_total * 100:.1f}%</strong> of transactions flagged
        </div>
    </div>
</div>

<div class="section">
    <h3>Top Alerts (High &amp; Medium Risk) — top 50 shown</h3>
    <table>
        <thead>
            <tr>
                <th>Transaction ID</th><th>Timestamp</th>
                <th>Sender</th><th>Receiver</th>
                <th>Amount</th><th>Route</th>
                <th>Tier</th><th>Score</th><th>Rules</th>
            </tr>
        </thead>
        <tbody>{table_rows}</tbody>
    </table>
</div>

<div class="section">
    <h3>High-Risk Account Summary (top 15)</h3>
    <table>
        <thead>
            <tr>
                <th>Account</th><th>Flagged Txns</th>
                <th>Total Flagged Amount</th><th>Max Tier</th><th>Max Score</th>
            </tr>
        </thead>
        <tbody>{acct_rows}</tbody>
    </table>
</div>

<footer>
    AML Monitoring System — Automated Report — {generated_at} <br>
    Rules: Structuring · Round Amounts · Unusual Hours · Velocity Burst · High-Risk Jurisdiction<br>
    This report is auto-generated and requires human analyst review before any regulatory submission.
</footer>

</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[Report] Saved → {output_path}")
    return output_path