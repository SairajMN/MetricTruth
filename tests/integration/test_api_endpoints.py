import httpx
import pytest
from backend.main import app
from scripts.seed_database import seed_all


@pytest.mark.asyncio
async def test_api_contracts_and_rbac():
    await seed_all(simulate_stale_hours=0, reset=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Overview endpoint returns live database KPIs
        ov = await client.get("/api/v1/analytics/overview")
        assert ov.status_code == 200
        ov_data = ov.json()
        assert ov_data["business_performance"]["paid_cac_usd"] == 37.50
        assert ov_data["business_performance"]["conversion_rate_pct"] == 4.82
        assert ov_data["business_performance"]["attributed_revenue_usd"] == 1420000.0
        assert ov_data["business_performance"]["new_customers"] == 4000

        # 2. Ask endpoint executes end-to-end CAC investigation
        ask_resp = await client.post(
            "/api/v1/analytics/ask",
            json={
                "question": "Why did our customer acquisition cost increase this month compared with last month? Identify which campaigns are responsible."
            },
        )
        assert ask_resp.status_code == 200
        run_data = ask_resp.json()
        run_id = run_data["run_id"]
        assert run_data["status"] == "COMPLETED"
        assert run_data["audit_bundle"]["overall_status"] == "VERIFIED"

        # 3. Inspect sub-resources (/report, /sql, /evidence, /events)
        for sub in ("report", "sql", "evidence", "events"):
            sub_resp = await client.get(f"/api/v1/analytics/runs/{run_id}/{sub}")
            assert sub_resp.status_code == 200

        # 4. RBAC: viewer cannot approve a draft metric; admin can
        forbidden_resp = await client.post(
            "/api/v1/metrics/fully_loaded_customer_acquisition_cost/approve",
            headers={"X-Role": "viewer"},
        )
        assert forbidden_resp.status_code == 403

        admin_resp = await client.post(
            "/api/v1/metrics/fully_loaded_customer_acquisition_cost/approve",
            headers={"X-Role": "admin"},
        )
        assert admin_resp.status_code == 200
        assert admin_resp.json()["metric"]["status"] == "approved"

