import pytest
from app.models.physics import SlopeStabilityPhysics

def test_stable_slope_factor_of_safety():
    res = SlopeStabilityPhysics.calculate_factor_of_safety(
        slope_angle_deg=20.0,
        cohesion_kpa=15.0,
        friction_angle_deg=30.0,
        soil_depth_m=2.0,
        volumetric_water_content=0.15  # Low soil moisture
    )
    assert res["factor_of_safety"] > 1.5
    assert res["stability_status"] == "STABLE"
    assert res["failure_probability_pct"] < 20.0

def test_unstable_saturated_slope_factor_of_safety():
    res = SlopeStabilityPhysics.calculate_factor_of_safety(
        slope_angle_deg=48.0,
        cohesion_kpa=5.0,
        friction_angle_deg=22.0,
        soil_depth_m=3.0,
        volumetric_water_content=0.445  # Near 100% saturation
    )
    assert res["factor_of_safety"] < 1.0
    assert res["stability_status"] == "SLOPE_FAILURE_IMMINENT"
    assert res["failure_probability_pct"] > 80.0

def test_flat_ground_safety():
    res = SlopeStabilityPhysics.calculate_factor_of_safety(
        slope_angle_deg=0.0,
        cohesion_kpa=10.0,
        friction_angle_deg=25.0,
        soil_depth_m=2.0,
        volumetric_water_content=0.20
    )
    assert res["factor_of_safety"] == 99.0
    assert res["stability_status"] == "STABLE"
