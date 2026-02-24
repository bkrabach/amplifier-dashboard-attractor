#!/usr/bin/env python3
"""Generate a consistent set of pipeline log files for dashboard testing.

Writes realistic pipeline data to /tmp/attractor-pipeline/ so the dashboard
can display a complete, consistent pipeline run with connected nodes.

Usage:
    python scripts/generate_sample_data.py [--output-dir /tmp/attractor-pipeline]
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

DEFAULT_OUTPUT = "/tmp/attractor-pipeline"

# --- Graph definition (single source of truth) ---

GRAPH_NAME = "feature_build"
GOAL = "Build a Python calculator with tests"

# Ordered list of nodes — order matters for execution path
NODES = [
    {
        "id": "start",
        "shape": "Mdiamond",
        "prompt_attr": None,
        "duration_ms": 0.5,
        "notes": "Start node: start",
        "prompt_text": None,
        "response_text": None,
    },
    {
        "id": "plan",
        "shape": "box",
        "prompt_attr": "List the steps to build a calculator",
        "duration_ms": 3200,
        "notes": "Generated implementation plan with 4 steps",
        "prompt_text": (
            "You are a software architect. List the steps to build a Python "
            "calculator with basic arithmetic operations.\n\n"
            "Requirements:\n"
            "- Support add, subtract, multiply, divide\n"
            "- Handle division by zero\n"
            "- Clean, testable code\n\n"
            "Output a numbered list of implementation steps."
        ),
        "response_text": (
            "## Implementation Plan\n\n"
            "1. **Create `calculator.py`** — Define a `Calculator` class with "
            "methods: `add(a, b)`, `subtract(a, b)`, `multiply(a, b)`, "
            "`divide(a, b)`\n"
            "2. **Handle edge cases** — `divide()` should raise `ValueError` "
            "on division by zero with a clear message\n"
            "3. **Create `test_calculator.py`** — Write pytest tests covering:\n"
            "   - Basic operations with positive/negative numbers\n"
            "   - Division by zero error handling\n"
            "   - Float precision edge cases\n"
            "4. **Verify** — Run `pytest -v` and confirm all tests pass\n"
        ),
    },
    {
        "id": "implement",
        "shape": "box",
        "prompt_attr": "Create calculator.py with add, subtract, multiply, divide",
        "duration_ms": 8500,
        "notes": "Created calculator.py with Calculator class (4 methods)",
        "prompt_text": (
            "Create calculator.py with add, subtract, multiply, divide.\n\n"
            "## Context from previous steps\n\n"
            "Plan:\n"
            "1. Create Calculator class with four methods\n"
            "2. Handle division by zero with ValueError\n"
            "3. Clean, testable code\n\n"
            "Write the complete calculator.py file."
        ),
        "response_text": (
            "```python\n"
            '"""Simple calculator module."""\n\n\n'
            "class Calculator:\n"
            '    """Basic arithmetic calculator."""\n\n'
            "    def add(self, a: float, b: float) -> float:\n"
            '        """Return the sum of a and b."""\n'
            "        return a + b\n\n"
            "    def subtract(self, a: float, b: float) -> float:\n"
            '        """Return the difference of a and b."""\n'
            "        return a - b\n\n"
            "    def multiply(self, a: float, b: float) -> float:\n"
            '        """Return the product of a and b."""\n'
            "        return a * b\n\n"
            "    def divide(self, a: float, b: float) -> float:\n"
            '        """Return the quotient of a and b.\n\n'
            "        Raises:\n"
            "            ValueError: If b is zero.\n"
            '        """\n'
            "        if b == 0:\n"
            '            raise ValueError("Cannot divide by zero")\n'
            "        return a / b\n"
            "```\n"
        ),
    },
    {
        "id": "test",
        "shape": "box",
        "prompt_attr": "Write tests for the calculator",
        "duration_ms": 5100,
        "notes": "Created test_calculator.py with 8 test cases — all passing",
        "prompt_text": (
            "Write tests for the calculator.\n\n"
            "## Context from previous steps\n\n"
            "calculator.py has been created with a Calculator class containing "
            "add, subtract, multiply, divide methods. divide raises ValueError "
            "on zero.\n\n"
            "Write comprehensive pytest tests."
        ),
        "response_text": (
            "```python\n"
            '"""Tests for calculator module."""\n\n'
            "import pytest\n"
            "from calculator import Calculator\n\n\n"
            "@pytest.fixture\n"
            "def calc():\n"
            "    return Calculator()\n\n\n"
            "def test_add(calc):\n"
            "    assert calc.add(2, 3) == 5\n"
            "    assert calc.add(-1, 1) == 0\n\n\n"
            "def test_subtract(calc):\n"
            "    assert calc.subtract(5, 3) == 2\n"
            "    assert calc.subtract(1, 5) == -4\n\n\n"
            "def test_multiply(calc):\n"
            "    assert calc.multiply(3, 4) == 12\n"
            "    assert calc.multiply(-2, 3) == -6\n\n\n"
            "def test_divide(calc):\n"
            "    assert calc.divide(10, 2) == 5.0\n"
            "    assert calc.divide(7, 2) == 3.5\n\n\n"
            "def test_divide_by_zero(calc):\n"
            "    with pytest.raises(ValueError, match='Cannot divide by zero'):\n"
            "        calc.divide(1, 0)\n"
            "```\n"
        ),
    },
    {
        "id": "done",
        "shape": "Msquare",
        "prompt_attr": None,
        "duration_ms": 0.3,
        "notes": "Pipeline complete: all steps succeeded",
        "prompt_text": None,
        "response_text": None,
    },
]

# Edges derived from node order: start -> plan -> implement -> test -> done
EDGES = [(NODES[i]["id"], NODES[i + 1]["id"]) for i in range(len(NODES) - 1)]


def _build_dot_source() -> str:
    """Build the DOT source from the node/edge definitions."""
    lines = [f"digraph {GRAPH_NAME} {{"]
    lines.append(f'    graph [goal="{GOAL}"]')
    lines.append("")
    for node in NODES:
        attrs = [f"shape={node['shape']}"]
        if node["prompt_attr"]:
            attrs.append(f'prompt="{node["prompt_attr"]}"')
        attr_str = ", ".join(attrs)
        lines.append(f"    {node['id']:10s} [{attr_str}]")
    lines.append("")
    chain = " -> ".join(n["id"] for n in NODES)
    lines.append(f"    {chain}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _build_manifest(start_time: datetime) -> dict:
    return {
        "graph_name": GRAPH_NAME,
        "goal": GOAL,
        "start_time": start_time.isoformat(),
        "node_count": len(NODES),
        "edge_count": len(EDGES),
    }


def _build_checkpoint(start_time: datetime) -> dict:
    completed = {n["id"]: "success" for n in NODES}
    node_outcomes = {}
    for node in NODES:
        node_outcomes[node["id"]] = {
            "status": "success",
            "notes": node["notes"],
            "failure_reason": None,
            "preferred_label": None,
        }
    return {
        "current_node": "done",
        "completed_nodes": completed,
        "context": {
            "graph.goal": GOAL,
            "outcome": "success",
        },
        "node_outcomes": node_outcomes,
        "timestamp": start_time.isoformat(),
        "node_retries": {},
        "logs": [],
    }


def _build_node_status(node: dict) -> dict:
    return {
        "node_id": node["id"],
        "outcome": "success",
        "status": "success",
        "preferred_next_label": None,
        "suggested_next_ids": None,
        "context_updates": None,
        "duration_ms": node["duration_ms"],
        "notes": node["notes"],
        "failure_reason": None,
    }


def generate(output_dir: str = DEFAULT_OUTPUT) -> None:
    """Generate a consistent set of pipeline log files."""
    out = Path(output_dir)

    # Clean existing data
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    start_time = datetime.now(timezone.utc) - timedelta(minutes=5)

    # Write graph.dot
    (out / "graph.dot").write_text(_build_dot_source(), encoding="utf-8")

    # Write manifest.json
    (out / "manifest.json").write_text(
        json.dumps(_build_manifest(start_time), indent=2), encoding="utf-8"
    )

    # Write checkpoint.json
    (out / "checkpoint.json").write_text(
        json.dumps(_build_checkpoint(start_time), indent=2), encoding="utf-8"
    )

    # Write per-node directories
    for node in NODES:
        node_dir = out / node["id"]
        node_dir.mkdir(exist_ok=True)

        # status.json (always present)
        (node_dir / "status.json").write_text(
            json.dumps(_build_node_status(node), indent=2), encoding="utf-8"
        )

        # prompt.md (if node has a prompt)
        if node["prompt_text"]:
            (node_dir / "prompt.md").write_text(node["prompt_text"], encoding="utf-8")

        # response.md (if node has a response)
        if node["response_text"]:
            (node_dir / "response.md").write_text(
                node["response_text"], encoding="utf-8"
            )

    # Write artifacts directory (empty, but present for consistency)
    (out / "artifacts").mkdir(exist_ok=True)

    # Summary
    total_ms = sum(n["duration_ms"] for n in NODES)
    print(f"Generated pipeline data in {out}")
    print(f"  Graph: {GRAPH_NAME} ({len(NODES)} nodes, {len(EDGES)} edges)")
    print(f"  Goal:  {GOAL}")
    print(f"  Total: {total_ms:.0f}ms")
    print("  Files:")
    print(f"    graph.dot        ({len(_build_dot_source())} bytes)")
    print("    manifest.json")
    print("    checkpoint.json")
    for node in NODES:
        files = ["status.json"]
        if node["prompt_text"]:
            files.append("prompt.md")
        if node["response_text"]:
            files.append("response.md")
        print(f"    {node['id']}/  ({', '.join(files)})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate sample pipeline log data")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    generate(args.output_dir)
