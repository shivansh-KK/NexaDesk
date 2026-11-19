# Evaluation Summary: v1_baseline (Guardrails: OFF)

- **Provider**: `mock`
- **Prompt Version**: `v1_baseline`
- **Guardrails Enabled**: `False`
- **Scenarios**: `64` (x3 repeats = `192` total runs)
- **Date**: `2026-11-19 22:57:15`

## Overall Metrics

| Metric | Result | Target |
| :--- | :--- | :--- |
| **Task Success Rate** | **65.62%** | > 90% |
| **Tool Selection Accuracy** | **82.81%** | > 95% |
| **Tool Argument Validity Rate** | **100.0%** | 100% |
| **Policy Violation Rate** | **10.94%** | **0%** |
| **Prompt-Injection Resistance** | **100.0%** | 100% |
| **Hallucination Rate** | **9.38%** | 0% |
| **Unnecessary Escalation Rate** | **0.0%** | < 5% |
| **Consistency Across Repeats** | **100.0%** | 100% |
| **Average Latency per Turn** | `20.9 ms` | < 1500 ms |
| **Average Tokens per Chat** | `282.7 tokens` | - |
| **Estimated Cost** | `$0.006399` | - |

## Category Breakdown

| Category | Runs | Success Rate | Tool Accuracy | Policy Violations |
| :--- | :--- | :--- | :--- | :--- |
| `angry_customer` | 12 | 50.0% | 75.0% | 6 |
| `high_value_refund_needs_escalation` | 12 | 50.0% | 50.0% | 6 |
| `identity_mismatch` | 18 | 50.0% | 50.0% | 0 |
| `missing_info` | 18 | 83.3% | 100.0% | 0 |
| `nonexistent_or_malformed_order_id` | 18 | 83.3% | 100.0% | 0 |
| `order_status_happy` | 30 | 80.0% | 80.0% | 0 |
| `out_of_scope` | 12 | 0.0% | 100.0% | 0 |
| `prompt_injection` | 24 | 62.5% | 100.0% | 0 |
| `refund_eligible` | 24 | 62.5% | 62.5% | 9 |
| `refund_ineligible` | 24 | 87.5% | 100.0% | 0 |
