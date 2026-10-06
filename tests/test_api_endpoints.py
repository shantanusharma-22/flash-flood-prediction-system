import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "telemetry_stream" in data
    assert data["active_wards_monitored"] >= 5

def test_get_wards_endpoint():
    response = client.get("/api/wards")
    assert response.status_code == 200
    wards = response.json()
    assert len(wards) >= 5
    first = wards[0]
    assert "ward_id" in first
    assert "risk_level" in first
    assert "factor_of_safety" in first
    assert "evacuation_routes" in first

def test_get_ward_by_id():
    response = client.get("/api/wards/W-UK-CHM-04")
    assert response.status_code == 200
    ward = response.json()
    assert ward["ward_id"] == "W-UK-CHM-04"
    assert "Raini" in ward["ward_name"]

def test_get_sensors_endpoint():
    response = client.get("/api/sensors")
    assert response.status_code == 200
    sensors = response.json()
    assert len(sensors) >= 8

def test_physics_prediction_endpoint():
    payload = {
        "slope_angle_deg": 45.0,
        "cohesion_kpa": 8.0,
        "friction_angle_deg": 25.0,
        "soil_unit_weight_kn_m3": 16.0,
        "soil_depth_m": 2.5,
        "volumetric_water_content": 0.40,
        "saturation_vwc": 0.45,
        "root_cohesion_kpa": 1.0
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "factor_of_safety" in data
    assert "stability_status" in data

def test_physics_sensitivity_endpoint():
    payload = {
        "slope_angle_deg": 40.0,
        "cohesion_kpa": 10.0,
        "friction_angle_deg": 28.0,
        "soil_depth_m": 2.5
    }
    response = client.post("/api/physics/sensitivity", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "sensitivity_curve" in data
    assert len(data["sensitivity_curve"]) > 5

def test_scenario_simulator_endpoint():
    payload = {
        "scenario": "CLOUDBURST",
        "ward_id": "W-UK-CHM-04",
        "custom_rainfall": 130.0
    }
    response = client.post("/api/simulator/scenario", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"

def test_ai_advisory_endpoint():
    payload = {
        "ward_id": "W-UK-CHM-04",
        "language": "Hindi"
    }
    response = client.post("/api/ai-advisory", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ward_id"] == "W-UK-CHM-04"
    assert len(data["tactical_ndrf_instructions"]) > 0
    assert "public_evacuation_broadcast" in data

def test_ai_chat_endpoint():
    payload = {
        "message": "What is the primary evacuation route?",
        "ward_id": "W-UK-CHM-04"
    }
    response = client.post("/api/ai-chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert len(data["suggested_actions"]) > 0

def test_citizen_sos_workflow():
    payload = {
        "ward_id": "W-UK-CHM-04",
        "citizen_name": "Test Citizen",
        "phone_number": "+91-99999-11111",
        "lat": 30.485,
        "lng": 79.698,
        "people_count": 3,
        "situation_desc": "Rising water in terrace field",
        "requires_medical": False
    }
    # Submit SOS
    post_res = client.post("/api/citizen/sos", json=payload)
    assert post_res.status_code == 200
    sos_record = post_res.json()
    assert "sos_id" in sos_record
    assert sos_record["citizen_name"] == "Test Citizen"

    # Get SOS list
    get_res = client.get("/api/citizen/sos")
    assert get_res.status_code == 200
    sos_list = get_res.json()
    assert any(s["sos_id"] == sos_record["sos_id"] for s in sos_list)

    # Update status
    status_res = client.post(f"/api/citizen/sos/{sos_record['sos_id']}/status", json={"status": "DISPATCHED"})
    assert status_res.status_code == 200
    assert status_res.json()["new_status"] == "DISPATCHED"

def test_emergency_alert_dispatch():
    payload = {
        "ward_id": "W-UK-CHM-04",
        "channels": ["SMS", "VHF_RADIO"],
        "custom_message": "Immediate drill evacuation test",
        "severity": "RED"
    }
    res = client.post("/api/alerts/dispatch", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "dispatch_id" in data
    assert data["recipients_count"] > 0

    history_res = client.get("/api/alerts/history")
    assert history_res.status_code == 200
    assert len(history_res.json()) > 0

def test_iap_report_endpoint():
    res = client.get("/api/reports/iap?ward_id=W-UK-CHM-04")
    assert res.status_code == 200
    assert "INCIDENT ACTION PLAN" in res.text
    assert "Raini" in res.text
