"""Generate PR-friendly markdown summaries from compare output."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from schema_lens.compare.gate import evaluate_gate, load_gate_policy


def build_ci_summary_markdown(
    compare_data: dict[str, Any],
    *,
    compare_path: Path,
    policy_path: Path | None = None,
) -> str:
    summary = compare_data.get("summary", {})
    total = summary.get("queries_total", 0)
    avg_overlap = summary.get("avg_overlap", 0.0)
    high_risk_pct = summary.get("high_risk_percent", 0.0)
    avg_numfound_delta = summary.get("avg_numfound_delta", 0.0)
    avg_sort_instability = summary.get("avg_sort_instability_ratio", 0.0)

    gate_verdict = "NOT_EVALUATED"
    gate_detail = ""
    if policy_path:
        policy_data = load_gate_policy(policy_path)
        gate = evaluate_gate(
            compare_data=compare_data,
            policy_data=policy_data,
            policy_dir=policy_path.parent.resolve(),
        )
        gate_verdict = "PASS" if gate.get("pass", False) else "FAIL"
        if gate.get("failed_rules"):
            lines = []
            for rule in gate["failed_rules"]:
                lines.append(
                    f"- `{rule.get('metric')}` {rule.get('op')} {rule.get('value')} "
                    f"(actual: {rule.get('actual')})"
                )
            gate_detail = "\n".join(lines)

    lines = [
        "# Schema-Lens CI Summary",
        "",
        "## Overall Metrics",
        f"- Queries: **{total}**",
        f"- Avg overlap@K: **{avg_overlap:.3f}**",
        f"- High risk %: **{high_risk_pct:.2f}**",
        f"- Avg numFound delta: **{avg_numfound_delta:.3f}**",
        f"- Avg sort instability ratio: **{avg_sort_instability:.3f}**",
        "",
        "## Gate Verdict",
        f"- **{gate_verdict}**",
    ]
    if gate_detail:
        lines.extend(["", gate_detail])

    lines.extend(["", "## Top Regressions (10)", ""])
    top = compare_data.get("top_regressions", [])[:10]
    if not top:
        lines.append("- No regressions recorded.")
    else:
        for idx, diff in enumerate(top, start=1):
            lines.append(
                f"{idx}. qid={diff.get('query_id')} "
                f"risk={diff.get('risk_severity')} "
                f"overlap={diff.get('topk_overlap_count')} "
                f"tau={diff.get('kendall_tau')}"
            )

    lines.extend(
        [
            "",
            "## Artifact Paths",
            f"- Compare: `{compare_path}`",
        ]
    )
    if policy_path:
        lines.append(f"- Policy: `{policy_path}`")
    return "\n".join(lines) + "\n"

