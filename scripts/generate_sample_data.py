#!/usr/bin/env python3
"""Generate consistent pipeline log files for dashboard testing.

Writes realistic pipeline data for three pipeline types so the dashboard
can display a variety of graph topologies: linear, branching, and complex SDLC.

Usage:
    python scripts/generate_sample_data.py

Output directories (pass via PIPELINE_LOGS_DIR, comma-separated):
    /tmp/attractor-pipeline-simple   -- linear 5-node feature build
    /tmp/attractor-pipeline-branch   -- branching with conditional routing
    /tmp/attractor-pipeline-sdlc     -- full SDLC with human review gate
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# DOT files to read from disk (real pipeline definitions)
# ---------------------------------------------------------------------------

BRANCHING_DOT_PATH = Path("/home/bkrabach/dev/attractor-native/examples/branching.dot")
SDLC_DOT_PATH = Path("/home/bkrabach/dev/attractor-native/pipelines/full-sdlc.dot")

# ---------------------------------------------------------------------------
# Pipeline 1: Simple Linear (feature_build)
# ---------------------------------------------------------------------------

SIMPLE_DIR = "/tmp/attractor-pipeline-simple"
SIMPLE_GRAPH_NAME = "feature_build"
SIMPLE_GOAL = "Build a Python calculator with tests"

SIMPLE_NODES = [
    {
        "id": "start",
        "shape": "Mdiamond",
        "duration_ms": 0.5,
        "notes": "Start node: start",
        "prompt_text": None,
        "response_text": None,
    },
    {
        "id": "plan",
        "shape": "box",
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
            "1. **Create `calculator.py`** \u2014 Define a `Calculator` class with "
            "methods: `add(a, b)`, `subtract(a, b)`, `multiply(a, b)`, "
            "`divide(a, b)`\n"
            "2. **Handle edge cases** \u2014 `divide()` should raise `ValueError` "
            "on division by zero with a clear message\n"
            "3. **Create `test_calculator.py`** \u2014 Write pytest tests covering:\n"
            "   - Basic operations with positive/negative numbers\n"
            "   - Division by zero error handling\n"
            "   - Float precision edge cases\n"
            "4. **Verify** \u2014 Run `pytest -v` and confirm all tests pass\n"
        ),
    },
    {
        "id": "implement",
        "shape": "box",
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
        "duration_ms": 5100,
        "notes": "Created test_calculator.py with 8 test cases \u2014 all passing",
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
        "duration_ms": 0.3,
        "notes": "Pipeline complete: all steps succeeded",
        "prompt_text": None,
        "response_text": None,
    },
]


def _build_simple_dot() -> str:
    """Build DOT source for the simple linear pipeline."""
    lines = [f"digraph {SIMPLE_GRAPH_NAME} {{"]
    lines.append(f'    graph [goal="{SIMPLE_GOAL}"]')
    lines.append("")
    for node in SIMPLE_NODES:
        prompt_part = ""
        lines.append(f"    {node['id']:10s} [shape={node['shape']}{prompt_part}]")
    lines.append("")
    chain = " -> ".join(n["id"] for n in SIMPLE_NODES)
    lines.append(f"    {chain}")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Pipeline 2: Branching with Conditional Routing
# ---------------------------------------------------------------------------

BRANCH_DIR = "/tmp/attractor-pipeline-branch"
BRANCH_GRAPH_NAME = "Branch"
BRANCH_GOAL = "Implement and validate a feature"

BRANCH_NODES = [
    {
        "id": "start",
        "shape": "Mdiamond",
        "duration_ms": 0.4,
        "notes": "Start node: entry point",
        "prompt_text": None,
        "response_text": None,
    },
    {
        "id": "plan",
        "shape": "box",
        "duration_ms": 4200,
        "notes": "Created implementation plan for the feature",
        "prompt_text": (
            "Plan the implementation\n\n"
            "Goal: Implement and validate a feature\n\n"
            "Break the goal down into concrete steps. Consider:\n"
            "- What components need to change\n"
            "- What order to implement changes\n"
            "- What tests will validate correctness"
        ),
        "response_text": (
            "## Implementation Plan\n\n"
            "1. **Identify affected components** \u2014 The feature touches the "
            "data layer and the API handler.\n"
            "2. **Implement data model changes** \u2014 Add new fields and migration.\n"
            "3. **Update API handler** \u2014 Accept and return new fields.\n"
            "4. **Write validation tests** \u2014 Unit tests for model, "
            "integration tests for API.\n"
        ),
    },
    {
        "id": "implement",
        "shape": "box",
        "duration_ms": 11300,
        "notes": "Implemented data model changes and API handler updates",
        "prompt_text": (
            "Implement the plan\n\n"
            "## Context from previous steps\n\n"
            "Plan:\n"
            "1. Add new fields to data model\n"
            "2. Update API handler to accept/return new fields\n"
            "3. Write validation tests\n\n"
            "Implement the changes now."
        ),
        "response_text": (
            "## Changes Made\n\n"
            "### Data Model (`models.py`)\n"
            "- Added `feature_flag: bool` field with default `False`\n"
            "- Added `feature_metadata: dict` field (nullable)\n"
            "- Created migration `003_add_feature_fields.py`\n\n"
            "### API Handler (`routes/features.py`)\n"
            "- `POST /features` now accepts `feature_flag` and `feature_metadata`\n"
            "- `GET /features/:id` returns the new fields\n"
            "- Input validation: `feature_metadata` must be valid JSON if provided\n"
        ),
    },
    {
        "id": "validate",
        "shape": "box",
        "duration_ms": 6800,
        "notes": "All 12 tests passing \u2014 validation complete",
        "prompt_text": (
            "Run tests and validate\n\n"
            "## Context from previous steps\n\n"
            "Implementation is complete:\n"
            "- Data model updated with new fields\n"
            "- API handler updated\n"
            "- Migration created\n\n"
            "Run all tests and verify everything works."
        ),
        "response_text": (
            "## Test Results\n\n"
            "```\n"
            "$ pytest -v\n"
            "tests/test_models.py::test_feature_flag_default PASSED\n"
            "tests/test_models.py::test_feature_flag_set PASSED\n"
            "tests/test_models.py::test_feature_metadata_nullable PASSED\n"
            "tests/test_models.py::test_feature_metadata_json PASSED\n"
            "tests/test_routes.py::test_create_feature_with_flag PASSED\n"
            "tests/test_routes.py::test_create_feature_without_flag PASSED\n"
            "tests/test_routes.py::test_get_feature_includes_new_fields PASSED\n"
            "tests/test_routes.py::test_invalid_metadata_rejected PASSED\n"
            "tests/test_routes.py::test_migration_forward PASSED\n"
            "tests/test_routes.py::test_migration_backward PASSED\n"
            "tests/test_integration.py::test_full_feature_lifecycle PASSED\n"
            "tests/test_integration.py::test_feature_flag_toggle PASSED\n\n"
            "12 passed in 3.2s\n"
            "```\n\n"
            "All tests passing. Feature is ready for review.\n"
        ),
    },
    {
        "id": "gate",
        "shape": "diamond",
        "duration_ms": 0.2,
        "notes": "Tests passing \u2014 routing to exit (Yes)",
        "prompt_text": None,
        "response_text": None,
    },
    {
        "id": "exit",
        "shape": "Msquare",
        "duration_ms": 0.1,
        "notes": "Pipeline complete: feature validated successfully",
        "prompt_text": None,
        "response_text": None,
    },
]

# ---------------------------------------------------------------------------
# Pipeline 3: Full SDLC with Human Review
# ---------------------------------------------------------------------------

SDLC_DIR = "/tmp/attractor-pipeline-sdlc"
SDLC_GRAPH_NAME = "full_sdlc"
SDLC_GOAL = "Build a REST API for user management"

SDLC_NODES = [
    {
        "id": "start",
        "shape": "Mdiamond",
        "duration_ms": 0.3,
        "notes": "Start node: entry point",
        "prompt_text": None,
        "response_text": None,
    },
    {
        "id": "spec",
        "shape": "box",
        "duration_ms": 5200,
        "notes": "Wrote technical specification with API contracts and data models",
        "prompt_text": (
            "Write a detailed technical specification for the following task. "
            "Include:\n"
            "- Requirements (functional and non-functional)\n"
            "- API contracts or interfaces\n"
            "- Data models\n"
            "- Error handling strategy\n"
            "- Acceptance criteria\n\n"
            "Task: Build a REST API for user management"
        ),
        "response_text": (
            "# Technical Specification: User Management REST API\n\n"
            "## Functional Requirements\n"
            "- CRUD operations for users (create, read, update, delete)\n"
            "- Email uniqueness constraint\n"
            "- Password hashing with bcrypt\n"
            "- Pagination for list endpoints\n\n"
            "## API Contracts\n\n"
            "### `POST /api/users`\n"
            "```json\n"
            '{ "email": "user@example.com", "name": "Alice", '
            '"password": "secret123" }\n'
            "```\n"
            "Response: `201 Created` with user object (no password)\n\n"
            "### `GET /api/users/:id`\n"
            "Response: `200 OK` with user object\n\n"
            "### `PUT /api/users/:id`\n"
            "Partial update, returns `200 OK`\n\n"
            "### `DELETE /api/users/:id`\n"
            "Returns `204 No Content`\n\n"
            "## Data Model\n"
            "```\n"
            "User:\n"
            "  id: UUID (auto-generated)\n"
            "  email: string (unique, indexed)\n"
            "  name: string\n"
            "  password_hash: string\n"
            "  created_at: datetime\n"
            "  updated_at: datetime\n"
            "```\n\n"
            "## Acceptance Criteria\n"
            "- All CRUD operations work correctly\n"
            "- Duplicate email returns 409 Conflict\n"
            "- Invalid input returns 422 with details\n"
            "- Passwords never returned in responses\n"
        ),
    },
    {
        "id": "design",
        "shape": "box",
        "duration_ms": 8100,
        "notes": "Designed architecture with FastAPI, SQLAlchemy, and Alembic",
        "prompt_text": (
            "Design the architecture and data model based on the specification. "
            "Consider:\n"
            "- Component boundaries\n"
            "- Data flow\n"
            "- Edge cases and failure modes\n"
            "- Security implications\n"
            "- Performance considerations"
        ),
        "response_text": (
            "# Architecture Design\n\n"
            "## Stack\n"
            "- **Framework**: FastAPI (async, auto-docs)\n"
            "- **ORM**: SQLAlchemy 2.0 with async session\n"
            "- **Migrations**: Alembic\n"
            "- **Database**: PostgreSQL\n"
            "- **Auth**: bcrypt for password hashing\n\n"
            "## Component Boundaries\n"
            "```\n"
            "routes/users.py     \u2190 HTTP layer (validation, serialization)\n"
            "services/users.py   \u2190 Business logic (uniqueness, hashing)\n"
            "models/user.py      \u2190 SQLAlchemy model\n"
            "schemas/user.py     \u2190 Pydantic schemas (request/response)\n"
            "```\n\n"
            "## Security\n"
            "- Password hashing with bcrypt (cost factor 12)\n"
            "- Input validation via Pydantic\n"
            "- SQL injection prevented by ORM\n"
            "- Rate limiting on create endpoint\n"
        ),
    },
    {
        "id": "implement",
        "shape": "box",
        "duration_ms": 15200,
        "notes": "Implemented all CRUD endpoints with FastAPI and SQLAlchemy",
        "prompt_text": (
            "Implement the feature per the spec and design. Write clean, "
            "production-quality code with proper error handling and documentation."
        ),
        "response_text": (
            "## Implementation Complete\n\n"
            "### Files Created\n"
            "- `app/models/user.py` \u2014 SQLAlchemy User model\n"
            "- `app/schemas/user.py` \u2014 Pydantic schemas (UserCreate, "
            "UserUpdate, UserResponse)\n"
            "- `app/services/users.py` \u2014 Business logic with async DB operations\n"
            "- `app/routes/users.py` \u2014 FastAPI router with all CRUD endpoints\n"
            "- `app/main.py` \u2014 Application factory with router registration\n"
            "- `alembic/versions/001_create_users.py` \u2014 Migration\n\n"
            "### Key Decisions\n"
            "- Used `asyncpg` for async PostgreSQL driver\n"
            "- Password hashing in service layer (not model)\n"
            "- Pagination with `skip` and `limit` query params\n"
            "- Custom exception handlers for 409 and 422\n"
        ),
    },
    {
        "id": "test",
        "shape": "box",
        "duration_ms": 12400,
        "notes": "22 tests passing \u2014 full coverage of CRUD and edge cases",
        "prompt_text": (
            "Write comprehensive tests covering:\n"
            "- Happy path\n"
            "- Edge cases\n"
            "- Error conditions\n"
            "- Integration points\n\n"
            "Run all tests and fix any failures."
        ),
        "response_text": (
            "## Test Results\n\n"
            "```\n"
            "$ pytest -v --cov=app\n"
            "tests/test_models.py::test_user_model_creation PASSED\n"
            "tests/test_models.py::test_user_password_not_stored PASSED\n"
            "tests/test_schemas.py::test_user_create_validation PASSED\n"
            "tests/test_schemas.py::test_user_response_excludes_password PASSED\n"
            "tests/test_services.py::test_create_user PASSED\n"
            "tests/test_services.py::test_create_duplicate_email PASSED\n"
            "tests/test_services.py::test_get_user PASSED\n"
            "tests/test_services.py::test_get_nonexistent_user PASSED\n"
            "tests/test_services.py::test_update_user PASSED\n"
            "tests/test_services.py::test_delete_user PASSED\n"
            "tests/test_routes.py::test_create_user_201 PASSED\n"
            "tests/test_routes.py::test_create_duplicate_409 PASSED\n"
            "tests/test_routes.py::test_create_invalid_422 PASSED\n"
            "tests/test_routes.py::test_get_user_200 PASSED\n"
            "tests/test_routes.py::test_get_user_404 PASSED\n"
            "tests/test_routes.py::test_update_user_200 PASSED\n"
            "tests/test_routes.py::test_delete_user_204 PASSED\n"
            "tests/test_routes.py::test_list_users_paginated PASSED\n"
            "tests/test_integration.py::test_full_crud_lifecycle PASSED\n"
            "tests/test_integration.py::test_concurrent_create PASSED\n"
            "tests/test_integration.py::test_pagination PASSED\n"
            "tests/test_integration.py::test_email_case_insensitive PASSED\n\n"
            "22 passed in 4.8s\n"
            "Coverage: 94%\n"
            "```\n"
        ),
    },
    {
        "id": "human_review",
        "shape": "hexagon",
        "duration_ms": 2100,
        "notes": "Human approved: code looks good, ready for deployment",
        "prompt_text": (
            "Implementation complete. Please review the changes.\n\n"
            "Summary:\n"
            "- User management REST API with full CRUD\n"
            "- FastAPI + SQLAlchemy + PostgreSQL\n"
            "- 22 tests passing with 94% coverage\n"
            "- bcrypt password hashing, Pydantic validation"
        ),
        "response_text": (
            "## Human Review: APPROVED\n\n"
            "Reviewed by: tech-lead\n\n"
            "Comments:\n"
            "- Clean separation of concerns\n"
            "- Good test coverage\n"
            "- Proper error handling\n"
            "- Approved for deployment preparation\n"
        ),
    },
    {
        "id": "deploy_prep",
        "shape": "box",
        "duration_ms": 3800,
        "notes": "Deployment notes and changelog prepared",
        "prompt_text": (
            "Prepare deployment notes and changelog. Include:\n"
            "- Summary of changes\n"
            "- Migration steps (if any)\n"
            "- Configuration changes\n"
            "- Rollback plan"
        ),
        "response_text": (
            "# Deployment Notes\n\n"
            "## Summary\n"
            "New User Management REST API with full CRUD operations.\n\n"
            "## Migration Steps\n"
            "1. Run `alembic upgrade head` to create the `users` table\n"
            "2. Set `DATABASE_URL` environment variable\n"
            "3. Set `BCRYPT_COST_FACTOR=12` (or use default)\n\n"
            "## Configuration Changes\n"
            "- New env var: `DATABASE_URL` (required)\n"
            "- New env var: `BCRYPT_COST_FACTOR` (optional, default: 12)\n\n"
            "## Rollback Plan\n"
            "1. Run `alembic downgrade -1` to drop the `users` table\n"
            "2. Remove the new environment variables\n"
            "3. Redeploy previous version\n"
        ),
    },
    {
        "id": "done",
        "shape": "Msquare",
        "duration_ms": 0.2,
        "notes": "Pipeline complete: feature shipped",
        "prompt_text": None,
        "response_text": None,
    },
]

# ---------------------------------------------------------------------------
# Shared generation helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _build_manifest(
    graph_name: str, goal: str, start_time: datetime, nodes: list[dict], edge_count: int
) -> dict:
    return {
        "graph_name": graph_name,
        "goal": goal,
        "start_time": start_time.isoformat(),
        "node_count": len(nodes),
        "edge_count": edge_count,
    }


def _build_checkpoint(
    nodes: list[dict], goal: str, start_time: datetime, terminal_node: str
) -> dict:
    completed = {n["id"]: "success" for n in nodes}
    node_outcomes = {}
    for node in nodes:
        node_outcomes[node["id"]] = {
            "status": "success",
            "notes": node["notes"],
            "failure_reason": None,
            "preferred_label": None,
        }
    return {
        "current_node": terminal_node,
        "completed_nodes": completed,
        "context": {
            "graph.goal": goal,
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


def _generate_pipeline(
    output_dir: str,
    graph_name: str,
    goal: str,
    nodes: list[dict],
    dot_source: str,
    edge_count: int,
    terminal_node: str,
) -> None:
    """Generate a complete set of pipeline log files."""
    out = Path(output_dir)

    # Clean existing data
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    start_time = datetime.now(timezone.utc) - timedelta(minutes=5)

    # Write graph.dot
    _write_text(out / "graph.dot", dot_source)

    # Write manifest.json
    _write_json(
        out / "manifest.json",
        _build_manifest(graph_name, goal, start_time, nodes, edge_count),
    )

    # Write checkpoint.json
    _write_json(
        out / "checkpoint.json",
        _build_checkpoint(nodes, goal, start_time, terminal_node),
    )

    # Write per-node directories
    for node in nodes:
        node_dir = out / node["id"]
        node_dir.mkdir(exist_ok=True)

        # status.json (always present)
        _write_json(node_dir / "status.json", _build_node_status(node))

        # prompt.md (if node has a prompt)
        if node.get("prompt_text"):
            _write_text(node_dir / "prompt.md", node["prompt_text"])

        # response.md (if node has a response)
        if node.get("response_text"):
            _write_text(node_dir / "response.md", node["response_text"])

    # Write artifacts directory
    (out / "artifacts").mkdir(exist_ok=True)

    # Summary
    total_ms = sum(n["duration_ms"] for n in nodes)
    print(f"\n  Generated: {out}")
    print(f"    Graph: {graph_name} ({len(nodes)} nodes, {edge_count} edges)")
    print(f"    Goal:  {goal}")
    print(f"    Total: {total_ms:.0f}ms")
    print(f"    Nodes: {', '.join(n['id'] for n in nodes)}")


def _read_dot_file(path: Path) -> str:
    """Read a DOT file from disk, or return empty string if missing."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        print(f"  WARNING: Could not read {path}, using empty DOT")
        return ""


def generate_all() -> None:
    """Generate sample data for all three pipeline types."""
    print("Generating sample pipeline data for dashboard testing...")

    # Pipeline 1: Simple Linear
    _generate_pipeline(
        output_dir=SIMPLE_DIR,
        graph_name=SIMPLE_GRAPH_NAME,
        goal=SIMPLE_GOAL,
        nodes=SIMPLE_NODES,
        dot_source=_build_simple_dot(),
        edge_count=len(SIMPLE_NODES) - 1,
        terminal_node="done",
    )

    # Pipeline 2: Branching
    branch_dot = _read_dot_file(BRANCHING_DOT_PATH)
    _generate_pipeline(
        output_dir=BRANCH_DIR,
        graph_name=BRANCH_GRAPH_NAME,
        goal=BRANCH_GOAL,
        nodes=BRANCH_NODES,
        dot_source=branch_dot,
        edge_count=4,  # start->plan, plan->implement, implement->validate,
        # validate->gate, gate->exit, gate->implement = 6 edges,
        # but 4 unique edge connections in the chain
        terminal_node="exit",
    )

    # Pipeline 3: Full SDLC
    sdlc_dot = _read_dot_file(SDLC_DOT_PATH)
    _generate_pipeline(
        output_dir=SDLC_DIR,
        graph_name=SDLC_GRAPH_NAME,
        goal=SDLC_GOAL,
        nodes=SDLC_NODES,
        dot_source=sdlc_dot,
        edge_count=8,  # chain + conditional edges
        terminal_node="done",
    )

    print("\n" + "=" * 60)
    print("To start the dashboard with all three pipelines:")
    print("=" * 60)
    dirs = f"{SIMPLE_DIR},{BRANCH_DIR},{SDLC_DIR}"
    print(f"\n  PIPELINE_LOGS_DIR={dirs} \\")
    print("    uv run python -m amplifier_dashboard_attractor.server")
    print()


if __name__ == "__main__":
    generate_all()
