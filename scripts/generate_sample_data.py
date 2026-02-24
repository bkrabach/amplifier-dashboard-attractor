#!/usr/bin/env python3
"""Generate consistent pipeline log files for dashboard testing.

Writes realistic pipeline data for five pipeline types so the dashboard
can display a variety of graph topologies: linear, branching, complex SDLC,
looping multi-provider (semport), and parallel fan-out consensus.

Usage:
    python scripts/generate_sample_data.py

Output directories (pass via PIPELINE_LOGS_DIR, comma-separated):
    /tmp/attractor-pipeline-simple      -- linear 5-node feature build
    /tmp/attractor-pipeline-branch      -- branching with conditional routing
    /tmp/attractor-pipeline-sdlc        -- full SDLC with human review gate
    /tmp/attractor-pipeline-semport     -- looping semantic port (partial run)
    /tmp/attractor-pipeline-consensus   -- parallel fan-out consensus task
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
SEMPORT_DOT_PATH = Path("/home/bkrabach/dev/semport.dot")
CONSENSUS_DOT_PATH = Path("/home/bkrabach/dev/consensus_task.dot")

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
# Pipeline 4: Semantic Port (semport) — partial run, currently executing
# ---------------------------------------------------------------------------

SEMPORT_DIR = "/tmp/attractor-pipeline-semport"
SEMPORT_GRAPH_NAME = "Workflow"
SEMPORT_GOAL = (
    "We want to intelligently track and port semantic changes from the upstream "
    "openai-agents-python repository to our Go implementation."
)

SEMPORT_NODES = [
    {
        "id": "Start",
        "shape": "circle",
        "duration_ms": 0,
        "node_status": "success",
        "notes": "Start node: entry point",
        "prompt_text": None,
        "response_text": None,
    },
    {
        "id": "FetchUpstreamSonnet",
        "shape": "box",
        "duration_ms": 15000,
        "node_status": "success",
        "notes": "Found commit a776d80 (2025-02-20) to process: 'nest handoff history by default'",
        "prompt_text": (
            "Our goal is: We want to intelligently track and port semantic "
            "changes from the upstream openai-agents-python repository to our "
            "Go implementation.\n\n"
            "---\n\n"
            "**CRITICAL: Use semport/ledger.py for all ledger operations.**\n\n"
            "1. Run `python3 semport/ledger.py earliest` to get the "
            "chronologically earliest commit with disposition='new'\n"
            "2. If a commit is found, write it to .ai/semport_new_commits.md "
            "and use outcome=process\n"
            "3. If NO 'new' commits exist, fetch upstream and check for new ones"
        ),
        "response_text": (
            "## Upstream Fetch Results\n\n"
            "Ran `python3 semport/ledger.py earliest`:\n"
            "```\n"
            "a776d80  2025-02-20T14:32:11Z  new\n"
            "```\n\n"
            "Found 1 unprocessed commit. Writing to `.ai/semport_new_commits.md`.\n\n"
            "### Commit a776d80\n"
            "**Date:** 2025-02-20\n"
            "**Message:** nest handoff history by default\n"
            "**Files changed:** `src/agents/handoff.py`, `src/agents/run.py`\n\n"
            "This commit changes how agent handoff history is stored \u2014 "
            "nesting it under the current agent context rather than keeping it flat.\n\n"
            "**outcome=process**"
        ),
    },
    {
        "id": "AnalyzePlanSonnet",
        "shape": "box",
        "duration_ms": 22000,
        "node_status": "success",
        "notes": "Decision: PORT. Handoff history nesting is semantically relevant to Go impl.",
        "prompt_text": (
            "Read .ai/semport_new_commits.md which contains a SINGLE commit "
            "to process. Examine commit a776d80 in inspiration/openai-agents-python "
            "using git show. Analyze the semantic changes.\n\n"
            "Decide if this change is relevant to our Go implementation or if "
            "it's Python-specific/docs-only/not-applicable.\n\n"
            "Write .ai/semport_plan_sonnet.md with: Commit Being Processed, "
            "Semantic Analysis, DECISION, Port Plan, and Disposition Recommendation."
        ),
        "response_text": (
            "# Semantic Port Plan: a776d80\n\n"
            "## Commit Being Processed\n"
            "- **SHA:** a776d80\n"
            "- **Summary:** nest handoff history by default\n\n"
            "## Semantic Analysis\n"
            "This commit restructures how handoff history is stored during "
            "agent-to-agent transfers. Instead of a flat list of all handoff "
            "events, the history is now nested under each agent's context. "
            "This improves:\n"
            "- Context isolation between agents\n"
            "- History traversal for debugging\n"
            "- Memory efficiency by avoiding duplication\n\n"
            "## DECISION: **PORT**\n"
            "This change is semantically relevant. Our Go `HandoffManager` "
            "currently uses a flat `[]HandoffEvent` slice. We should restructure "
            "to nest history under `AgentContext`.\n\n"
            "## Port Plan\n"
            "1. `pkg/agents/handoff.go:42-68` \u2014 Add `History []HandoffEvent` "
            "field to `AgentContext` struct\n"
            "2. `pkg/agents/handoff.go:105-120` \u2014 Update `Transfer()` to push "
            "events to nested history\n"
            "3. `pkg/agents/run.go:230-245` \u2014 Update history traversal to walk "
            "nested structure\n"
            "4. `pkg/agents/handoff_test.go` \u2014 Update test assertions\n\n"
            "**outcome=port**"
        ),
    },
    {
        "id": "FinalizePlanGPT",
        "shape": "box",
        "duration_ms": 18000,
        "node_status": "success",
        "notes": "Finalized port plan with concrete file:line references and acceptance criteria",
        "prompt_text": (
            "Perform a final editorial pass over .ai/semport_plan_sonnet.md "
            "and write .ai/semport_plan_finalized.md. Ensure each port task "
            "has concrete file:line references, clear acceptance criteria, and "
            "is directly executable. Remove vague language."
        ),
        "response_text": (
            "# Finalized Port Plan: a776d80\n\n"
            "## Task 1: Add nested history to AgentContext\n"
            "- **File:** `pkg/agents/handoff.go:42`\n"
            "- **Change:** Add `History []HandoffEvent` field\n"
            "- **Accept:** Struct compiles, existing tests pass\n\n"
            "## Task 2: Update Transfer() method\n"
            "- **File:** `pkg/agents/handoff.go:105-120`\n"
            "- **Change:** Push `HandoffEvent{From, To, Timestamp, Payload}` "
            "into `ctx.History` instead of global slice\n"
            "- **Accept:** `Transfer()` appends to nested history\n\n"
            "## Task 3: Update history traversal\n"
            "- **File:** `pkg/agents/run.go:230-245`\n"
            "- **Change:** Walk `agent.Context.History` instead of flat list\n"
            "- **Accept:** `GetFullHistory()` returns equivalent results\n\n"
            "## Task 4: Update tests\n"
            "- **File:** `pkg/agents/handoff_test.go`\n"
            "- **Change:** Assert on `ctx.History` instead of global\n"
            "- **Accept:** `go test ./pkg/agents/...` passes\n\n"
            "Written to `.ai/semport_plan_finalized.md`"
        ),
    },
    {
        "id": "ImplementPort",
        "shape": "box",
        "duration_ms": 45000,
        "node_status": "running",
        "notes": "Currently porting handoff history nesting to Go codebase...",
        "prompt_text": (
            "Follow the port plan in .ai/semport_plan_finalized.md. For each "
            "upstream commit, port the semantic changes to the Go codebase. "
            "Focus on semantic equivalence, not literal translation. Use Go "
            "idioms, respect existing architecture, and reference specific "
            "files/line ranges. Log all changes to .ai/semport_impl.log."
        ),
        "response_text": None,
    },
    {
        "id": "TestValidate",
        "shape": "box",
        "duration_ms": 0,
        "node_status": "pending",
        "notes": None,
        "prompt_text": None,
        "response_text": None,
    },
    {
        "id": "AnalyzeFailureSonnet",
        "shape": "box",
        "duration_ms": 0,
        "node_status": "pending",
        "notes": None,
        "prompt_text": None,
        "response_text": None,
    },
    {
        "id": "FinalizeAndUpdateLedger",
        "shape": "box",
        "duration_ms": 0,
        "node_status": "pending",
        "notes": None,
        "prompt_text": None,
        "response_text": None,
    },
    {
        "id": "Exit",
        "shape": "doublecircle",
        "duration_ms": 0,
        "node_status": "pending",
        "notes": None,
        "prompt_text": None,
        "response_text": None,
    },
]

# ---------------------------------------------------------------------------
# Pipeline 5: Consensus Task — complete execution with parallel fan-out
# ---------------------------------------------------------------------------

CONSENSUS_DIR = "/tmp/attractor-pipeline-consensus"
CONSENSUS_GRAPH_NAME = "Workflow"
CONSENSUS_GOAL = "Add rate limiting middleware to the API gateway"

CONSENSUS_NODES = [
    {
        "id": "Start",
        "shape": "circle",
        "duration_ms": 0,
        "node_status": "success",
        "notes": "Start node: entry point",
        "prompt_text": None,
        "response_text": None,
    },
    {
        "id": "CheckDoD",
        "shape": "diamond",
        "duration_ms": 3000,
        "node_status": "success",
        "notes": "No DoD provided \u2014 routing to DefineDoD (needs_dod)",
        "prompt_text": (
            "Check if definition of done provided.\n\n"
            "TASK: Add rate limiting middleware to the API gateway\n"
            "DOD: (empty)\n\n"
            "Write status.json with outcome=needs_dod if DOD is empty or "
            "just a placeholder, else outcome=has_dod."
        ),
        "response_text": (
            "## DoD Check Result\n\n"
            "The `$definition_of_done` variable is empty \u2014 no DoD was "
            "provided by the user.\n\n"
            "**outcome=needs_dod**\n\n"
            "Routing to parallel DoD definition phase."
        ),
    },
    {
        "id": "DefineDoD_Gemini",
        "shape": "box",
        "duration_ms": 18000,
        "node_status": "success",
        "notes": "Gemini proposed DoD with 8 acceptance criteria",
        "prompt_text": (
            "Propose definition of done.\n\n"
            "TASK: Add rate limiting middleware to the API gateway\n\n"
            "Write to .ai/dod_gemini.md"
        ),
        "response_text": (
            "# Definition of Done: Rate Limiting Middleware (Gemini)\n\n"
            "## Acceptance Criteria\n"
            "1. Middleware intercepts all incoming API requests\n"
            "2. Rate limits configurable per-endpoint and per-client\n"
            "3. Uses token bucket algorithm with configurable burst\n"
            "4. Returns 429 Too Many Requests with Retry-After header\n"
            "5. Rate limit state stored in Redis for distributed deployments\n"
            "6. Graceful degradation if Redis unavailable (fail-open)\n"
            "7. Request metrics exposed via Prometheus endpoint\n"
            "8. Unit and integration tests with >90% coverage\n\n"
            "Written to `.ai/dod_gemini.md`"
        ),
    },
    {
        "id": "DefineDoD_GPT",
        "shape": "box",
        "duration_ms": 22000,
        "node_status": "success",
        "notes": "GPT proposed DoD focusing on security and observability",
        "prompt_text": (
            "Propose definition of done.\n\n"
            "TASK: Add rate limiting middleware to the API gateway\n\n"
            "Write to .ai/dod_gpt.md"
        ),
        "response_text": (
            "# Definition of Done: Rate Limiting Middleware (GPT)\n\n"
            "## Acceptance Criteria\n"
            "1. Sliding window rate limiter with per-IP and per-API-key limits\n"
            "2. Configurable via YAML: window size, max requests, burst\n"
            "3. HTTP 429 response includes `Retry-After` and `X-RateLimit-*` "
            "headers\n"
            "4. Redis-backed for multi-instance deployments\n"
            "5. Circuit breaker for Redis failures (fail-open with local cache)\n"
            "6. Structured logging for rate limit events (client, endpoint, "
            "remaining)\n"
            "7. Prometheus metrics: `rate_limit_hits_total`, "
            "`rate_limit_remaining`\n"
            "8. Load test: sustain 10k req/s with <5ms p99 latency overhead\n"
            "9. Security: prevent rate limit bypass via header spoofing\n\n"
            "Written to `.ai/dod_gpt.md`"
        ),
    },
    {
        "id": "DefineDoD_Opus",
        "shape": "box",
        "duration_ms": 20000,
        "node_status": "success",
        "notes": "Opus proposed DoD with emphasis on operational excellence",
        "prompt_text": (
            "Propose definition of done.\n\n"
            "TASK: Add rate limiting middleware to the API gateway\n\n"
            "Write to .ai/dod_opus.md"
        ),
        "response_text": (
            "# Definition of Done: Rate Limiting Middleware (Opus)\n\n"
            "## Acceptance Criteria\n"
            "1. Token bucket rate limiter as Express/Fastify middleware\n"
            "2. Per-route and per-client configuration via gateway config\n"
            "3. Redis storage with automatic key expiry\n"
            "4. Standard rate limit headers (X-RateLimit-Limit, -Remaining, "
            "-Reset)\n"
            "5. 429 response body includes human-readable error message\n"
            "6. Fallback to in-memory limiter if Redis unreachable\n"
            "7. Admin endpoint to view/reset rate limit state\n"
            "8. Integration tests covering: normal flow, limit hit, burst, "
            "Redis failure\n"
            "9. Documentation in gateway README with configuration examples\n"
            "10. Runbook for ops team: monitoring alerts, manual overrides\n\n"
            "Written to `.ai/dod_opus.md`"
        ),
    },
    {
        "id": "ConsolidateDoD",
        "shape": "box",
        "duration_ms": 15000,
        "node_status": "success",
        "notes": "Synthesized 3 DoD proposals into consensus definition with 12 criteria",
        "prompt_text": (
            "Synthesize three DoD proposals.\n\n"
            "TASK: Add rate limiting middleware to the API gateway\n\n"
            "Read .ai/dod_*.md, write consensus to .ai/definition_of_done.md"
        ),
        "response_text": (
            "# Consolidated Definition of Done\n\n"
            "Synthesized from Gemini, GPT, and Opus proposals.\n\n"
            "## Core Requirements\n"
            "1. Token bucket rate limiter as gateway middleware\n"
            "2. Per-route and per-API-key configuration via YAML\n"
            "3. Redis-backed state for distributed deployments\n"
            "4. Graceful fallback to in-memory if Redis unavailable\n\n"
            "## HTTP Response\n"
            "5. 429 status with `Retry-After` header\n"
            "6. `X-RateLimit-Limit`, `-Remaining`, `-Reset` headers\n"
            "7. Human-readable error body\n\n"
            "## Observability\n"
            "8. Prometheus metrics: hits, remaining, latency overhead\n"
            "9. Structured logging for rate limit events\n\n"
            "## Quality\n"
            "10. Unit + integration tests with >90% coverage\n"
            "11. Load test: <5ms p99 overhead at 10k req/s\n"
            "12. Gateway README with config examples and ops runbook\n\n"
            "Written to `.ai/definition_of_done.md`"
        ),
    },
    {
        "id": "PlanGemini",
        "shape": "box",
        "duration_ms": 24000,
        "node_status": "success",
        "notes": "Gemini plan: 6 implementation phases with file-level breakdown",
        "prompt_text": (
            "Create implementation plan.\n\n"
            "TASK: Add rate limiting middleware to the API gateway\n"
            "DOD: .ai/definition_of_done.md\n\n"
            "Write to .ai/plan_gemini.md"
        ),
        "response_text": (
            "# Implementation Plan (Gemini)\n\n"
            "## Phase 1: Core Middleware\n"
            "- Create `src/middleware/rateLimiter.ts`\n"
            "- Token bucket implementation with configurable params\n"
            "- Request key extraction (IP + API key)\n\n"
            "## Phase 2: Redis Backend\n"
            "- `src/middleware/stores/redisStore.ts`\n"
            "- Atomic increment with TTL via Lua script\n"
            "- Connection pooling and health check\n\n"
            "## Phase 3: In-Memory Fallback\n"
            "- `src/middleware/stores/memoryStore.ts`\n"
            "- Circuit breaker for Redis failures\n\n"
            "## Phase 4: Configuration\n"
            "- YAML config schema in `config/rate-limits.yaml`\n"
            "- Per-route and per-key overrides\n\n"
            "## Phase 5: Observability\n"
            "- Prometheus counter and histogram metrics\n"
            "- Structured JSON logging\n\n"
            "## Phase 6: Testing\n"
            "- Unit tests for each store\n"
            "- Integration tests with Redis testcontainers\n"
            "- Load test with k6\n\n"
            "Written to `.ai/plan_gemini.md`"
        ),
    },
    {
        "id": "PlanGPT",
        "shape": "box",
        "duration_ms": 28000,
        "node_status": "success",
        "notes": "GPT plan: middleware-first approach with security hardening",
        "prompt_text": (
            "Create implementation plan.\n\n"
            "TASK: Add rate limiting middleware to the API gateway\n"
            "DOD: .ai/definition_of_done.md\n\n"
            "Write to .ai/plan_gpt.md"
        ),
        "response_text": (
            "# Implementation Plan (GPT)\n\n"
            "## Step 1: Middleware Skeleton\n"
            "Create the middleware entry point with request/response lifecycle "
            "hooks. Register in gateway pipeline.\n\n"
            "## Step 2: Token Bucket Algorithm\n"
            "Implement sliding window token bucket. Key = hash(clientIP + "
            "apiKey + routePattern). Configurable: tokens_per_window, "
            "window_size_ms, burst_size.\n\n"
            "## Step 3: Redis Store\n"
            "Lua script for atomic check-and-decrement. MULTI/EXEC for "
            "consistency. Automatic key expiry matching window size.\n\n"
            "## Step 4: Resilience\n"
            "Circuit breaker (half-open after 5s). Local LRU cache as "
            "fallback. Health check endpoint for Redis.\n\n"
            "## Step 5: Security\n"
            "Prevent X-Forwarded-For spoofing. Validate API key format "
            "before rate limit lookup. Rate limit the rate limiter "
            "(meta-limiting).\n\n"
            "## Step 6: Headers & Response\n"
            "Standard headers on every response (not just 429). "
            "JSON error body with retry guidance.\n\n"
            "Written to `.ai/plan_gpt.md`"
        ),
    },
    {
        "id": "PlanOpus",
        "shape": "box",
        "duration_ms": 25000,
        "node_status": "success",
        "notes": "Opus plan: operational focus with monitoring and runbook",
        "prompt_text": (
            "Create implementation plan.\n\n"
            "TASK: Add rate limiting middleware to the API gateway\n"
            "DOD: .ai/definition_of_done.md\n\n"
            "Write to .ai/plan_opus.md"
        ),
        "response_text": (
            "# Implementation Plan (Opus)\n\n"
            "## 1. Core Rate Limiter\n"
            "Express middleware in `src/middleware/rateLimit.ts`. Token bucket "
            "with per-route config loaded from `config/rate-limits.yaml`.\n\n"
            "## 2. Storage Layer\n"
            "Abstract `RateLimitStore` interface. Redis implementation with "
            "Lua scripts. Memory implementation for development/fallback.\n\n"
            "## 3. Gateway Integration\n"
            "Register middleware before auth in the pipeline. Config hot-reload "
            "via file watcher.\n\n"
            "## 4. Response Formatting\n"
            "429 with standard headers. Include `Retry-After` in seconds. "
            "JSON body: `{error, retryAfter, limit, remaining}`.\n\n"
            "## 5. Observability\n"
            "Prometheus metrics via `prom-client`. Grafana dashboard template "
            "in `monitoring/`. Alert rules for sustained 429 rate.\n\n"
            "## 6. Documentation & Ops\n"
            "README section with config examples. Runbook: how to adjust limits, "
            "reset a client, disable for debugging.\n\n"
            "Written to `.ai/plan_opus.md`"
        ),
    },
    {
        "id": "DebateConsolidate",
        "shape": "box",
        "duration_ms": 30000,
        "node_status": "success",
        "notes": "Consolidated 3 plans into final implementation plan",
        "prompt_text": (
            "Synthesize three plans.\n\n"
            "TASK: Add rate limiting middleware to the API gateway\n\n"
            "Read .ai/plan_*.md, write final to .ai/plan_final.md"
        ),
        "response_text": (
            "# Final Implementation Plan\n\n"
            "Synthesized from Gemini, GPT, and Opus proposals.\n\n"
            "## Architecture\n"
            "```\n"
            "Request -> rateLimitMiddleware -> [auth] -> [route handler]\n"
            "               |\n"
            "         RateLimitStore (interface)\n"
            "           /        \\\n"
            "     RedisStore   MemoryStore (fallback)\n"
            "```\n\n"
            "## Implementation Order\n"
            "1. `RateLimitStore` interface + `MemoryStore`\n"
            "2. Token bucket algorithm\n"
            "3. Middleware integration + response formatting\n"
            "4. `RedisStore` with Lua scripts\n"
            "5. Circuit breaker + fallback logic\n"
            "6. Configuration schema + hot-reload\n"
            "7. Prometheus metrics + structured logging\n"
            "8. Security hardening (X-Forwarded-For, key validation)\n"
            "9. Tests (unit, integration, load)\n"
            "10. Documentation + runbook\n\n"
            "Written to `.ai/plan_final.md`"
        ),
    },
    {
        "id": "Implement",
        "shape": "box",
        "duration_ms": 120000,
        "node_status": "success",
        "notes": "Implemented rate limiter: 12 files created, all compilation checks pass",
        "prompt_text": (
            "Execute plan.\n\n"
            "TASK: Add rate limiting middleware to the API gateway\n\n"
            "Follow .ai/plan_final.md. Log to .ai/implementation_log.md"
        ),
        "response_text": (
            "# Implementation Complete\n\n"
            "## Files Created/Modified\n"
            "- `src/middleware/rateLimit.ts` \u2014 Main middleware (87 lines)\n"
            "- `src/middleware/stores/types.ts` \u2014 RateLimitStore interface\n"
            "- `src/middleware/stores/redisStore.ts` \u2014 Redis impl with Lua\n"
            "- `src/middleware/stores/memoryStore.ts` \u2014 In-memory fallback\n"
            "- `src/middleware/stores/circuitBreaker.ts` \u2014 Redis circuit breaker\n"
            "- `src/middleware/rateLimitResponse.ts` \u2014 429 response formatter\n"
            "- `config/rate-limits.yaml` \u2014 Default config\n"
            "- `config/rate-limits.schema.json` \u2014 JSON Schema\n"
            "- `src/metrics/rateLimitMetrics.ts` \u2014 Prometheus counters\n"
            "- `tests/middleware/rateLimit.test.ts` \u2014 Unit tests (24 cases)\n"
            "- `tests/middleware/rateLimit.integration.ts` \u2014 Redis integration\n"
            "- `tests/middleware/rateLimit.load.ts` \u2014 k6 load test script\n\n"
            "## Test Results\n"
            "```\n"
            "24 unit tests passed\n"
            "8 integration tests passed\n"
            "Load test: 12.4k req/s, p99 = 3.2ms overhead\n"
            "Coverage: 96%\n"
            "```\n\n"
            "Logged to `.ai/implementation_log.md`"
        ),
    },
    {
        "id": "ReviewGemini",
        "shape": "box",
        "duration_ms": 14000,
        "node_status": "success",
        "notes": "Gemini review: PASS \u2014 clean implementation, good test coverage",
        "prompt_text": (
            "Review implementation.\n\n"
            "TASK: Add rate limiting middleware to the API gateway\n\n"
            "Write to .ai/review_gemini.md with PASS/FAIL"
        ),
        "response_text": (
            "# Code Review: Rate Limiting Middleware (Gemini)\n\n"
            "## Verdict: **PASS**\n\n"
            "### Strengths\n"
            "- Clean separation via `RateLimitStore` interface\n"
            "- Lua script for atomic Redis operations \u2014 correct approach\n"
            "- Circuit breaker with sensible defaults (5s half-open)\n"
            "- Comprehensive test coverage at 96%\n\n"
            "### Minor Suggestions\n"
            "- Consider adding `X-RateLimit-Policy` header for debugging\n"
            "- Config hot-reload could use debouncing\n\n"
            "Written to `.ai/review_gemini.md`"
        ),
    },
    {
        "id": "ReviewGPT",
        "shape": "box",
        "duration_ms": 16000,
        "node_status": "success",
        "notes": "GPT review: PASS \u2014 solid architecture, minor suggestions",
        "prompt_text": (
            "Review implementation.\n\n"
            "TASK: Add rate limiting middleware to the API gateway\n\n"
            "Write to .ai/review_gpt.md with PASS/FAIL"
        ),
        "response_text": (
            "# Code Review: Rate Limiting Middleware (GPT)\n\n"
            "## Verdict: **PASS**\n\n"
            "### Architecture\n"
            "The store interface pattern is well-designed. Redis Lua scripts "
            "are correct and atomic. Circuit breaker implementation follows "
            "standard patterns.\n\n"
            "### Security\n"
            "- X-Forwarded-For handling is correct (trusted proxy check)\n"
            "- API key validation before lookup prevents timing attacks\n\n"
            "### Performance\n"
            "- p99 at 3.2ms is well within the 5ms target\n"
            "- Memory store uses LRU eviction \u2014 good for bounded memory\n\n"
            "### Suggestions\n"
            "- Add distributed rate limit key prefix for multi-tenant\n"
            "- Consider adding a 'warm-up' period after Redis recovery\n\n"
            "Written to `.ai/review_gpt.md`"
        ),
    },
    {
        "id": "ReviewOpus",
        "shape": "box",
        "duration_ms": 15000,
        "node_status": "success",
        "notes": "Opus review: PASS \u2014 operationally sound, documentation complete",
        "prompt_text": (
            "Review implementation.\n\n"
            "TASK: Add rate limiting middleware to the API gateway\n\n"
            "Write to .ai/review_opus.md with PASS/FAIL"
        ),
        "response_text": (
            "# Code Review: Rate Limiting Middleware (Opus)\n\n"
            "## Verdict: **PASS**\n\n"
            "### Implementation Quality\n"
            "- Code is clean, well-documented, follows project conventions\n"
            "- Error handling is thorough (Redis timeout, connection loss, "
            "malformed config)\n"
            "- Middleware registration order is correct (before auth)\n\n"
            "### Operational Readiness\n"
            "- Prometheus metrics are properly labeled\n"
            "- Structured logging includes all context needed for debugging\n"
            "- Config schema validates at startup (fail-fast)\n\n"
            "### Documentation\n"
            "- README section is clear with practical examples\n"
            "- Runbook covers common scenarios\n"
            "- Grafana dashboard template included\n\n"
            "Written to `.ai/review_opus.md`"
        ),
    },
    {
        "id": "ReviewConsensus",
        "shape": "box",
        "duration_ms": 8000,
        "node_status": "success",
        "notes": "Consensus: PASS (3/3 reviewers approved)",
        "prompt_text": (
            "Reach consensus.\n\n"
            "Read .ai/review_*.md\n"
            "Write to .ai/review_consensus.md\n\n"
            "outcome=yes if PASS, outcome=retry if FAIL."
        ),
        "response_text": (
            "# Review Consensus\n\n"
            "## Result: **PASS** (unanimous)\n\n"
            "All three reviewers (Gemini, GPT, Opus) approved the "
            "implementation.\n\n"
            "### Summary\n"
            "- **Architecture:** Clean store interface, correct Redis usage\n"
            "- **Security:** Proper header handling, no bypass vectors\n"
            "- **Performance:** 3.2ms p99 overhead (target: <5ms)\n"
            "- **Quality:** 96% test coverage, comprehensive documentation\n\n"
            "### Minor suggestions collected (non-blocking):\n"
            "1. Add `X-RateLimit-Policy` header\n"
            "2. Debounce config hot-reload\n"
            "3. Distributed key prefix for multi-tenant\n"
            "4. Warm-up period after Redis recovery\n\n"
            "**outcome=yes**\n\n"
            "Written to `.ai/review_consensus.md`"
        ),
    },
    {
        "id": "Postmortem",
        "shape": "box",
        "duration_ms": 0,
        "node_status": "skipped",
        "notes": None,
        "prompt_text": None,
        "response_text": None,
    },
    {
        "id": "Exit",
        "shape": "doublecircle",
        "duration_ms": 0,
        "node_status": "success",
        "notes": "Pipeline complete: rate limiting middleware shipped",
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
    graph_name: str,
    goal: str,
    start_time: datetime,
    nodes: list[dict],
    edge_count: int,
    status: str = "complete",
) -> dict:
    return {
        "graph_name": graph_name,
        "goal": goal,
        "start_time": start_time.isoformat(),
        "node_count": len(nodes),
        "edge_count": edge_count,
        "status": status,
    }


def _build_checkpoint(
    nodes: list[dict],
    goal: str,
    start_time: datetime,
    terminal_node: str,
    current_node: str | None = None,
    pipeline_status: str = "complete",
) -> dict:
    # Only include nodes that actually completed
    completed = {}
    node_outcomes = {}
    for node in nodes:
        ns = node.get("node_status", "success")
        if ns == "success":
            completed[node["id"]] = "success"
            node_outcomes[node["id"]] = {
                "status": "success",
                "notes": node.get("notes", ""),
                "failure_reason": None,
                "preferred_label": None,
            }
        elif ns == "running":
            node_outcomes[node["id"]] = {
                "status": "running",
                "notes": node.get("notes", ""),
                "failure_reason": None,
                "preferred_label": None,
            }

    # Determine current_node
    if current_node is None:
        if pipeline_status == "running":
            # Find the running node
            for node in nodes:
                if node.get("node_status") == "running":
                    current_node = node["id"]
                    break
        if current_node is None:
            current_node = terminal_node

    context = {"graph.goal": goal}
    if pipeline_status == "complete":
        context["outcome"] = "success"

    return {
        "current_node": current_node,
        "completed_nodes": completed,
        "context": context,
        "node_outcomes": node_outcomes,
        "timestamp": start_time.isoformat(),
        "node_retries": {},
        "logs": [],
    }


def _build_node_status(node: dict) -> dict:
    ns = node.get("node_status", "success")
    return {
        "node_id": node["id"],
        "outcome": ns if ns != "running" else "running",
        "status": ns if ns != "running" else "running",
        "preferred_next_label": None,
        "suggested_next_ids": None,
        "context_updates": None,
        "duration_ms": node["duration_ms"],
        "notes": node.get("notes", ""),
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
    pipeline_status: str = "complete",
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
        _build_manifest(
            graph_name, goal, start_time, nodes, edge_count, pipeline_status
        ),
    )

    # Write checkpoint.json
    _write_json(
        out / "checkpoint.json",
        _build_checkpoint(
            nodes,
            goal,
            start_time,
            terminal_node,
            pipeline_status=pipeline_status,
        ),
    )

    # Write per-node directories (only for completed and running nodes)
    for node in nodes:
        ns = node.get("node_status", "success")
        if ns in ("pending", "skipped"):
            continue

        node_dir = out / node["id"]
        node_dir.mkdir(exist_ok=True)

        # status.json (always present for visited nodes)
        _write_json(node_dir / "status.json", _build_node_status(node))

        # prompt.md (if node has a prompt)
        if node.get("prompt_text"):
            _write_text(node_dir / "prompt.md", node["prompt_text"])

        # response.md (if node has a response — running nodes may not)
        if node.get("response_text"):
            _write_text(node_dir / "response.md", node["response_text"])

    # Write artifacts directory
    (out / "artifacts").mkdir(exist_ok=True)

    # Summary
    active_nodes = [n for n in nodes if n.get("node_status", "success") != "pending"]
    total_ms = sum(n["duration_ms"] for n in active_nodes)
    status_label = (
        f" [{pipeline_status.upper()}]" if pipeline_status != "complete" else ""
    )
    print(f"\n  Generated: {out}{status_label}")
    print(f"    Graph: {graph_name} ({len(nodes)} nodes, {edge_count} edges)")
    print(f"    Goal:  {goal[:80]}{'...' if len(goal) > 80 else ''}")
    print(f"    Total: {total_ms:.0f}ms")
    ids_with_status = []
    for n in nodes:
        ns = n.get("node_status", "success")
        if ns == "success":
            ids_with_status.append(n["id"])
        elif ns == "running":
            ids_with_status.append(f"*{n['id']}*")
        elif ns == "pending":
            ids_with_status.append(f"({n['id']})")
        elif ns == "skipped":
            ids_with_status.append(f"[{n['id']}]")
    print(f"    Nodes: {', '.join(ids_with_status)}")


def _read_dot_file(path: Path) -> str:
    """Read a DOT file from disk, or return empty string if missing."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        print(f"  WARNING: Could not read {path}, using empty DOT")
        return ""


def generate_all() -> None:
    """Generate sample data for all five pipeline types."""
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

    # Pipeline 4: Semantic Port (partial run — currently executing)
    semport_dot = _read_dot_file(SEMPORT_DOT_PATH)
    _generate_pipeline(
        output_dir=SEMPORT_DIR,
        graph_name=SEMPORT_GRAPH_NAME,
        goal=SEMPORT_GOAL,
        nodes=SEMPORT_NODES,
        dot_source=semport_dot,
        edge_count=11,  # all edges from the DOT file
        terminal_node="Exit",
        pipeline_status="running",
    )

    # Pipeline 5: Consensus Task (complete, parallel fan-out)
    consensus_dot = _read_dot_file(CONSENSUS_DOT_PATH)
    # Substitute $task in the DOT source with the actual goal
    consensus_dot = consensus_dot.replace("$task", CONSENSUS_GOAL)
    _generate_pipeline(
        output_dir=CONSENSUS_DIR,
        graph_name=CONSENSUS_GRAPH_NAME,
        goal=CONSENSUS_GOAL,
        nodes=CONSENSUS_NODES,
        dot_source=consensus_dot,
        edge_count=28,  # all edges including parallel fan-out/fan-in
        terminal_node="Exit",
    )

    print("\n" + "=" * 60)
    print("To start the dashboard with all five pipelines:")
    print("=" * 60)
    dirs = f"{SIMPLE_DIR},{BRANCH_DIR},{SDLC_DIR},{SEMPORT_DIR},{CONSENSUS_DIR}"
    print(f"\n  PIPELINE_LOGS_DIR={dirs} \\")
    print("    uv run python -m amplifier_dashboard_attractor.server")
    print()


if __name__ == "__main__":
    generate_all()
