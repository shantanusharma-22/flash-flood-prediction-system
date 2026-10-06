import os

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app.main as main
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    main._rate_limit_hits.clear()
    original = main.RATE_LIMIT_MAX_MUTATIONS
    yield
    main.RATE_LIMIT_MAX_MUTATIONS = original
    main._rate_limit_hits.clear()


def test_security_headers_present_on_json_responses():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "no-referrer"
    assert "geolocation=" in res.headers["Permissions-Policy"]
    assert res.headers["Cache-Control"] == "no-store"


def test_csp_and_hsts_on_html_dashboard():
    res = client.get("/")
    assert res.status_code == 200
    csp = res.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "script-src 'self'" in csp
    assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
    assert res.headers["Strict-Transport-Security"].startswith("max-age=")


def test_dashboard_ships_no_inline_scripts_and_pins_cdn_assets():
    html = client.get("/").text
    assert "<script src=" in html
    # Inline scripts would violate the CSP; everything must be served from /static.
    assert "<script>" not in html
    assert "lucide@latest" not in html
    assert "integrity=\"sha384-" in html


def test_scenario_rejects_unknown_values():
    res = client.post("/api/simulator/scenario", json={"scenario": "DROP_DATABASE"})
    assert res.status_code == 422

    res = client.post(
        "/api/simulator/scenario",
        json={"scenario": "CLOUDBURST", "ward_id": "../../etc/passwd"},
    )
    assert res.status_code == 422


def test_scenario_rejects_unknown_ward():
    res = client.post(
        "/api/simulator/scenario", json={"scenario": "CLOUDBURST", "ward_id": "W-NOPE-99"}
    )
    assert res.status_code == 404


def test_predict_rejects_nan_and_out_of_range_values():
    base = {
        "slope_angle_deg": 45.0,
        "cohesion_kpa": 8.0,
        "friction_angle_deg": 25.0,
        "soil_depth_m": 2.5,
        "volumetric_water_content": 0.4,
    }
    # Python's json parser accepts NaN; the model must not. Send it raw because
    # the test client itself refuses to serialize non-finite floats.
    import json as _json

    body = _json.dumps({**base, "cohesion_kpa": float("nan")})
    assert "NaN" in body
    res = client.post("/api/predict", content=body, headers={"Content-Type": "application/json"})
    assert res.status_code == 422

    res = client.post("/api/predict", json={**base, "slope_angle_deg": 900.0})
    assert res.status_code == 422


def test_sos_rejects_oversized_and_malicious_payload():
    res = client.post(
        "/api/citizen/sos",
        json={
            "citizen_name": "A" * 300,
            "phone_number": "+91-99999-11111",
            "lat": 30.4,
            "lng": 79.6,
            "situation_desc": "x" * 5000,
        },
    )
    assert res.status_code == 422

    res = client.post(
        "/api/citizen/sos",
        json={
            "citizen_name": "Test",
            "phone_number": "<script>alert(1)</script>",
            "lat": 30.4,
            "lng": 79.6,
            "situation_desc": "rising water",
        },
    )
    assert res.status_code == 422


def test_sos_status_rejects_arbitrary_values():
    created = client.post(
        "/api/citizen/sos",
        json={
            "citizen_name": "Test Citizen",
            "phone_number": "+91-99999-11111",
            "lat": 30.4,
            "lng": 79.6,
            "situation_desc": "rising water",
        },
    ).json()
    res = client.post(
        f"/api/citizen/sos/{created['sos_id']}/status", json={"status": "<img onerror=x>"}
    )
    assert res.status_code == 422


def test_sos_storage_is_bounded():
    from app.services.iot_simulator import iot_simulator_instance

    limit = iot_simulator_instance.MAX_SOS_RECORDS
    original = list(iot_simulator_instance.sos_records)
    try:
        iot_simulator_instance.sos_records = []
        for i in range(limit + 25):
            client.post(
                "/api/citizen/sos",
                json={
                    "citizen_name": "Flood Test",
                    "phone_number": "+91-99999-11111",
                    "lat": 30.4,
                    "lng": 79.6,
                    "situation_desc": f"burst {i}",
                },
            )
        assert len(iot_simulator_instance.sos_records) <= limit
    finally:
        iot_simulator_instance.sos_records = original


def test_rate_limit_blocks_mutation_flood():
    main.RATE_LIMIT_MAX_MUTATIONS = 5
    payload = {"scenario": "NORMAL", "ward_id": "W-UK-CHM-04"}
    codes = [
        client.post("/api/simulator/scenario", json=payload).status_code
        for _ in range(8)
    ]
    assert 429 in codes
    assert codes[0] == 200
    # Read endpoints are not throttled
    assert client.get("/api/health").status_code == 200


def test_websocket_rejects_foreign_origin():
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/ws/telemetry", headers={"origin": "https://evil.example"}
        ):
            pass


def test_websocket_accepts_same_origin():
    with client.websocket_connect(
        "/ws/telemetry", headers={"origin": "http://testserver"}
    ) as ws:
        payload = ws.receive_json()
        assert "wards" in payload
        assert "sensors" in payload
