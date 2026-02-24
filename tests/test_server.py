"""Tests for the FastAPI server skeleton."""

import pytest
from httpx import ASGITransport, AsyncClient

from amplifier_dashboard_attractor.server import create_app


@pytest.mark.asyncio
async def test_health_endpoint():
    app = create_app(mock=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "mock" in body


@pytest.mark.asyncio
async def test_health_shows_mock_mode():
    app = create_app(mock=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.json()["mock"] is True


@pytest.mark.asyncio
async def test_cors_headers_present():
    app = create_app(mock=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers


@pytest.mark.asyncio
async def test_mock_mode_from_env_var(monkeypatch):
    """DASHBOARD_MOCK=true in environment should activate mock mode."""
    monkeypatch.setenv("DASHBOARD_MOCK", "true")

    from unittest.mock import patch

    with patch("sys.argv", ["server"]), patch("uvicorn.run") as mock_run:
        from amplifier_dashboard_attractor.server import main

        main()
        app = mock_run.call_args[0][0]
        assert app.state.mock is True


@pytest.mark.asyncio
async def test_mock_mode_env_var_case_insensitive(monkeypatch):
    """DASHBOARD_MOCK should accept 'TRUE', '1', 'yes' etc."""
    for value in ("TRUE", "1", "yes", "Yes"):
        monkeypatch.setenv("DASHBOARD_MOCK", value)

        from unittest.mock import patch

        with patch("sys.argv", ["server"]), patch("uvicorn.run") as mock_run:
            from amplifier_dashboard_attractor.server import main

            main()
            app = mock_run.call_args[0][0]
            assert app.state.mock is True, (
                f"DASHBOARD_MOCK={value!r} should activate mock"
            )


@pytest.mark.asyncio
async def test_cli_mock_flag_works(monkeypatch):
    """--mock CLI flag should activate mock mode regardless of env var."""
    monkeypatch.delenv("DASHBOARD_MOCK", raising=False)

    from unittest.mock import patch

    with patch("sys.argv", ["server", "--mock"]), patch("uvicorn.run") as mock_run:
        from amplifier_dashboard_attractor.server import main

        main()
        app = mock_run.call_args[0][0]
        assert app.state.mock is True


@pytest.mark.asyncio
async def test_no_mock_when_env_var_absent(monkeypatch):
    """Without --mock or DASHBOARD_MOCK, mock should be False."""
    monkeypatch.delenv("DASHBOARD_MOCK", raising=False)

    from unittest.mock import patch

    with patch("sys.argv", ["server"]), patch("uvicorn.run") as mock_run:
        from amplifier_dashboard_attractor.server import main

        main()
        app = mock_run.call_args[0][0]
        assert app.state.mock is False


@pytest.mark.asyncio
async def test_cxdb_url_from_env_var(monkeypatch):
    """CXDB_URL env var should override default when no CLI flag given."""
    monkeypatch.setenv("CXDB_URL", "http://cxdb.internal:9090")
    monkeypatch.setenv("DASHBOARD_MOCK", "true")  # avoid real CXDB connection

    from unittest.mock import patch

    with patch("sys.argv", ["server"]), patch("uvicorn.run"):
        with patch("amplifier_dashboard_attractor.server.create_app") as mock_create:
            mock_create.return_value = create_app(mock=True)
            from amplifier_dashboard_attractor.server import main

            main()
            _, kwargs = mock_create.call_args
            assert kwargs["cxdb_url"] == "http://cxdb.internal:9090"
