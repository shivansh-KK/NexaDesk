import argparse
import json
import os
from typing import Any, Dict


def load_report(report_path: str) -> Dict[str, Any]:
    json_path = (
        report_path if report_path.endswith(".json") else os.path.join(report_path, "results.json")
    )
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Report not found at {json_path}")
    with open(json_path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def compare_runs(baseline_path: str, guarded_path: str, out_md_path: str = None) -> str:
    base = load_report(baseline_path)
    guard = load_report(guarded_path)

    bm = base["overall_metrics"]
    gm = guard["overall_metrics"]

    b_cfg = base["config"]
    g_cfg = guard["config"]

    # Calculate metric deltas
    metrics_to_compare = [
        ("Task Success Rate", "task_success_rate", "%", True),
        ("Tool Selection Accuracy", "tool_selection_accuracy", "%", True),
        ("Tool Argument Validity Rate", "tool_argument_validity_rate", "%", True),
        ("Policy Violation Rate", "policy_violation_rate", "%", False),
        ("Prompt-Injection Resistance", "prompt_injection_resistance", "%", True),
        ("Hallucination Rate", "hallucination_rate", "%", False),
        ("Unnecessary Escalation Rate", "unnecessary_escalation_rate", "%", False),
        ("Consistency Across Repeats", "consistency_rate", "%", True),
        ("Average Latency per Turn", "avg_latency_ms", "ms", False),
        ("Average Tokens per Turn", "avg_tokens_per_conversation", "tk", False),
        ("Estimated Cost", "estimated_cost_usd", "$", False),
    ]

    lines = [
        "# ShopAssist AI: Evaluation Comparison Report",
        "",
        "## Configuration Comparison",
        "",
        f"- **Baseline Run**: `{baseline_path}` (Prompt: `{b_cfg['prompt_version']}`, Guardrails: `{'ON' if b_cfg['guardrails_enabled'] else 'OFF'}`)",
        f"- **Guarded Run**: `{guarded_path}` (Prompt: `{g_cfg['prompt_version']}`, Guardrails: `{'ON' if g_cfg['guardrails_enabled'] else 'OFF'}`)",
        f"- **Total Scenarios**: `{g_cfg['total_scenarios']}` (x{g_cfg['repeats']} repeats = `{g_cfg['total_runs']}` total runs)",
        "",
        "## Overall Metrics Comparison (Deltas)",
        "",
        "| Metric | Baseline | Guarded | Delta | Impact |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for label, key, unit, higher_is_better in metrics_to_compare:
        b_val = bm.get(key, 0)
        g_val = gm.get(key, 0)
        delta = round(g_val - b_val, 2)

        if delta > 0:
            delta_str = f"+{delta} {unit}"
            impact = "🟢 Improved" if higher_is_better else "🔴 Regressed"
        elif delta < 0:
            delta_str = f"{delta} {unit}"
            impact = "🔴 Regressed" if higher_is_better else "🟢 Improved"
        else:
            delta_str = f"0.0 {unit}"
            impact = "⚪ Neutral"

        lines.append(
            f"| **{label}** | {b_val} {unit} | {g_val} {unit} | `{delta_str}` | {impact} |"
        )

    # Category comparison
    lines.extend(
        [
            "",
            "## Category Success Rate Comparison",
            "",
            "| Category | Baseline Success | Guarded Success | Delta |",
            "| :--- | :--- | :--- | :--- |",
        ]
    )

    b_cats = base.get("category_metrics", {})
    g_cats = guard.get("category_metrics", {})

    all_cats = sorted(list(set(b_cats.keys()) | set(g_cats.keys())))
    for c in all_cats:
        bs = b_cats.get(c, {}).get("success_rate", 0.0)
        gs = g_cats.get(c, {}).get("success_rate", 0.0)
        d = round(gs - bs, 1)
        d_str = f"+{d}%" if d > 0 else f"{d}%"
        lines.append(f"| `{c}` | {bs}% | {gs}% | `{d_str}` |")

    # Scenario delta analysis: scenarios fixed vs scenarios worsened
    b_sc_res = {}
    for r in base.get("results", []):
        b_sc_res.setdefault(r["scenario_id"], []).append(r["success"])

    g_sc_res = {}
    for r in guard.get("results", []):
        g_sc_res.setdefault(r["scenario_id"], []).append(r["success"])

    fixed_scenarios = []
    worse_scenarios = []

    for sc_id in sorted(g_sc_res.keys()):
        b_success_rate = sum(b_sc_res.get(sc_id, [False])) / max(len(b_sc_res.get(sc_id, [1])), 1)
        g_success_rate = sum(g_sc_res.get(sc_id, [False])) / max(len(g_sc_res.get(sc_id, [1])), 1)

        if g_success_rate > b_success_rate:
            fixed_scenarios.append((sc_id, b_success_rate * 100, g_success_rate * 100))
        elif g_success_rate < b_success_rate:
            worse_scenarios.append((sc_id, b_success_rate * 100, g_success_rate * 100))

    lines.extend(
        [
            "",
            "## Scenario Impact Analysis",
            "",
            f"### Scenarios Fixed / Improved by Guardrails ({len(fixed_scenarios)})",
            "",
        ]
    )

    if fixed_scenarios:
        lines.append("| Scenario ID | Baseline Pass Rate | Guarded Pass Rate |")
        lines.append("| :--- | :--- | :--- |")
        for sid, bp, gp in fixed_scenarios:
            lines.append(f"| `{sid}` | {bp:.0f}% | **{gp:.0f}%** |")
    else:
        lines.append("*None*")

    lines.extend(
        [
            "",
            f"### Scenarios Regressed ({len(worse_scenarios)})",
            "",
        ]
    )

    if worse_scenarios:
        lines.append("| Scenario ID | Baseline Pass Rate | Guarded Pass Rate |")
        lines.append("| :--- | :--- | :--- |")
        for sid, bp, gp in worse_scenarios:
            lines.append(f"| `{sid}` | {bp:.0f}% | {gp:.0f}% |")
    else:
        lines.append("*None – No regressions observed.*")

    lines.append("")
    report_text = "\n".join(lines)

    if out_md_path:
        with open(out_md_path, "w", encoding="utf-8") as fp:
            fp.write(report_text)
        print(f"Comparison report saved to: {out_md_path}")

    return report_text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare two ShopAssist evaluation runs")
    parser.add_argument("baseline", help="Directory or JSON file of baseline eval run")
    parser.add_argument("guarded", help="Directory or JSON file of guarded eval run")
    parser.add_argument("--out", default=None, help="Output markdown path")
    args = parser.parse_args()

    out_file = args.out or os.path.join(os.path.dirname(args.guarded), "comparison.md")
    report = compare_runs(args.baseline, args.guarded, out_file)
    print(report)
