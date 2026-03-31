"""Build Markdown test + API coverage report (Chinese labels per project request)."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# Must stay in sync with hunter.api.main routes (method + logical path template).
CANONICAL_ENDPOINTS: list[str] = [
    "GET /health",
    "GET /api/topics",
    "PUT /api/topics/{topic}",
    "DELETE /api/topics/{topic}",
    "POST /api/discover",
    "GET /api/discover/status",
    "GET /api/kols",
    "GET /api/kols/export.csv",
]


def write_api_test_markdown(
    *,
    report_path: Path,
    all_results: list[dict],
    api_results: list[dict],
    session,
    exitstatus: int,
    started_perf: float | None,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)

    elapsed = None
    if started_perf is not None:
        elapsed = time.perf_counter() - started_perf

    outcomes = [r["outcome"] for r in all_results]
    passed = sum(1 for o in outcomes if o == "passed")
    failed = sum(1 for o in outcomes if o == "failed")
    skipped = sum(1 for o in outcomes if o == "skipped")
    total = len(all_results)

    by_ep: dict[str, list[dict]] = defaultdict(list)
    for row in api_results:
        by_ep[row["endpoint"]].append(row)

    covered_eps = set(by_ep.keys())
    missing = [ep for ep in CANONICAL_ENDPOINTS if ep not in covered_eps]

    lines: list[str] = [
        "# Hunter 后端 API 自动化测试报告",
        "",
        f"**生成时间（时间戳）:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`  ",
        f"**报告文件:** `{report_path.name}`  ",
        "",
        "---",
        "",
        "## 1. 测试执行摘要",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 退出码 | `{exitstatus}` |",
        f"| 记录用例数（call 阶段） | {total} |",
        f"| 通过 | {passed} |",
        f"| 失败 | {failed} |",
        f"| 跳过 | {skipped} |",
    ]
    if elapsed is not None:
        lines.append(f"| 耗时（约） | {elapsed:.2f}s |")
    lines.extend(
        [
            "",
            "---",
            "",
            "## 2. 用例结果明细",
            "",
            "| 结果 | 用例 |",
            "|------|------|",
        ],
    )
    for r in sorted(all_results, key=lambda x: x["nodeid"]):
        icon = {"passed": "✅", "failed": "❌", "skipped": "⏭️"}.get(r["outcome"], "❓")
        node = r["nodeid"].replace("|", "\\|")
        lines.append(f"| {icon} `{r['outcome']}` | `{node}` |")
        if r["outcome"] == "failed" and r.get("longrepr"):
            snippet = (r["longrepr"] or "")[:800].replace("\n", " ").replace("|", "\\|")
            if len((r["longrepr"] or "")) > 800:
                snippet += "…"
            lines.append(f"| | _{snippet}_ |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 3. 接口测试覆盖（用例数量与列表）",
            "",
            "以下按 **接口** 汇总带 `@pytest.mark.endpoint(...)` 标记的用例。",
            "",
            "| 接口 | 用例数 | 测试函数 |",
            "|------|--------|----------|",
        ],
    )

    for ep in CANONICAL_ENDPOINTS:
        rows = by_ep.get(ep, [])
        count = len(rows)
        names = ", ".join(f"`{r['nodeid']}`" for r in sorted(rows, key=lambda x: x["nodeid"]))
        if not names:
            names = "—"
        ep_esc = ep.replace("|", "\\|")
        lines.append(f"| `{ep_esc}` | {count} | {names} |")

    # Extra marks not in canonical (typos / extras)
    extras = sorted(covered_eps - set(CANONICAL_ENDPOINTS))
    if extras:
        lines.extend(["", "### 非清单内 endpoint 标记（请核对是否拼写一致）", ""])
        for ep in extras:
            rows = by_ep[ep]
            names = ", ".join(f"`{r['nodeid']}`" for r in sorted(rows, key=lambda x: x["nodeid"]))
            lines.append(f"- `{ep}` → {len(rows)} 个用例: {names}")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 4. 覆盖缺口（清单中有、但无任何测试标记）",
            "",
        ],
    )
    if not missing:
        lines.append("_无 — 所有清单接口均至少有一个带 `endpoint` 标记的用例。_")
    else:
        for ep in missing:
            lines.append(f"- `{ep}`")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 5. 说明",
            "",
            "- 运行方式: 在 `backend` 目录执行 `python run_tests_and_report.py`（或设置环境变量 `HUNTER_WRITE_TEST_REPORT=1` 后执行 `pytest tests -v`）。",
            "- 本报告第 3、4 节为 **接口级测试覆盖**；如需 **Python 代码行覆盖率**，可另行使用 `pytest --cov=hunter`。",
            "",
        ],
    )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rel = report_path
    try:
        cwd = Path(os.getcwd())
        rel = report_path.resolve().relative_to(cwd.resolve())
    except ValueError:
        pass
    print(f"\n[hunter] Markdown report written to: {rel}\n")
