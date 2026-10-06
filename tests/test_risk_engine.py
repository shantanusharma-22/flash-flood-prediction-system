import pytest
from app.models.risk_engine import RiskEngine

def test_risk_evaluation_cloudburst_scenario():
    res = RiskEngine.evaluate_ward_risk(
        slope_angle_deg=47.5,
        cohesion_kpa=6.5,
        friction_angle_deg=22.0,
        soil_depth_m=3.1,
        volumetric_water_content=0.44,
        rainfall_1h_mm=118.0,  # Cloudburst
        rainfall_24h_mm=280.0,
        river_water_level_m=1988.5,
        river_danger_level_m=1980.0,
        historical_disasters_count=14,
        population=1240
    )
    assert res["risk_level"] == "RED"
    assert res["risk_score"] > 75.0
    assert res["estimated_lead_time_min"] <= 45

def test_risk_evaluation_normal_scenario():
    res = RiskEngine.evaluate_ward_risk(
        slope_angle_deg=25.0,
        cohesion_kpa=15.0,
        friction_angle_deg=32.0,
        soil_depth_m=2.0,
        volumetric_water_content=0.18,
        rainfall_1h_mm=4.0,
        rainfall_24h_mm=15.0,
        river_water_level_m=890.0,
        river_danger_level_m=895.0,
        historical_disasters_count=2,
        population=2000
    )
    assert res["risk_level"] == "GREEN"
    assert res["risk_score"] < 25.0
