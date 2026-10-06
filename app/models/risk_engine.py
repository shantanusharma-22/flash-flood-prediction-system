from typing import Dict, Any, List
from app.models.physics import SlopeStabilityPhysics

class RiskEngine:
    """
    Multi-Source Disaster Risk Evaluation & Lead-Time Estimation Engine
    for Flash Floods and Landslides in Hilly Regions.
    """

    @classmethod
    def evaluate_ward_risk(
        cls,
        slope_angle_deg: float,
        cohesion_kpa: float,
        friction_angle_deg: float,
        soil_depth_m: float,
        volumetric_water_content: float,
        rainfall_1h_mm: float,
        rainfall_24h_mm: float,
        river_water_level_m: float,
        river_danger_level_m: float,
        historical_disasters_count: int,
        population: int
    ) -> Dict[str, Any]:
        """
        Calculates composite risk score (0-100), alert tier, and evacuation lead time.
        """
        # 1. Physics-based FoS evaluation
        physics = SlopeStabilityPhysics.calculate_factor_of_safety(
            slope_angle_deg=slope_angle_deg,
            cohesion_kpa=cohesion_kpa,
            friction_angle_deg=friction_angle_deg,
            soil_depth_m=soil_depth_m,
            volumetric_water_content=volumetric_water_content
        )
        fos = physics["factor_of_safety"]
        sat_ratio = physics["saturation_ratio"]

        # 2. Rainfall Intensity Score (0 - 35 points)
        # Cloudburst threshold in India is >= 100 mm/h. High rainfall > 30 mm/h.
        rain_score = min(35.0, (rainfall_1h_mm / 100.0) * 25.0 + (rainfall_24h_mm / 250.0) * 10.0)

        # 3. Soil Saturation Score (0 - 25 points)
        soil_score = sat_ratio * 25.0

        # 4. Geotechnical Slope Instability Score (0 - 25 points)
        if fos >= 2.0:
            slope_score = 0.0
        elif fos >= 1.0:
            slope_score = (2.0 - fos) * 25.0
        else:
            slope_score = 25.0 + min(10.0, (1.0 - fos) * 20.0)

        # 5. River Flood Score (0 - 10 points)
        river_diff = river_water_level_m - river_danger_level_m
        if river_diff > 0:
            river_score = min(10.0, 5.0 + (river_diff / 2.0) * 5.0)
        else:
            river_score = max(0.0, 5.0 + (river_diff / 3.0) * 5.0)

        # 6. Historical Susceptibility Score (0 - 5 points)
        hist_score = min(5.0, historical_disasters_count * 1.25)

        # Total Composite Risk Score (0 - 100)
        raw_score = rain_score + soil_score + slope_score + river_score + hist_score
        risk_score = round(min(max(raw_score, 0.0), 100.0), 1)

        # Determine Alert Level & Actionable Lead Time
        if risk_score >= 75.0 or fos <= 1.05 or rainfall_1h_mm >= 75.0:
            risk_level = "RED"
            # Emergency Evacuation Lead Time estimation
            if rainfall_1h_mm > 90:
                lead_time_min = max(15, int(60 - (rainfall_1h_mm - 90) * 1.5))
            else:
                lead_time_min = int(45 + (1.05 - min(fos, 1.05)) * 100)
            recommended_action = "CRITICAL EMERGENCY: Immediate Evacuation to Safe High-Ground Shelters! Activate NDRF Sirens."
        elif risk_score >= 50.0 or fos <= 1.3 or rainfall_1h_mm >= 40.0:
            risk_level = "ORANGE"
            lead_time_min = int(90 + (1.3 - fos) * 120)
            recommended_action = "HIGH WARNING: Prepare vulnerable villagers for evacuation. NDRF QRT teams on high alert."
        elif risk_score >= 25.0 or rainfall_1h_mm >= 15.0:
            risk_level = "YELLOW"
            lead_time_min = 240
            recommended_action = "WATCH & ADVISORY: Monitor IoT stream. Inform local ward pradhans and clear drainage channels."
        else:
            risk_level = "GREEN"
            lead_time_min = 720  # 12 hours normal watch
            recommended_action = "NORMAL: Conditions stable. All IoT telemetry active."

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "factor_of_safety": fos,
            "estimated_lead_time_min": max(15, lead_time_min),
            "recommended_action": recommended_action,
            "physics": physics,
            "sub_scores": {
                "rainfall_score": round(rain_score, 1),
                "soil_saturation_score": round(soil_score, 1),
                "slope_instability_score": round(slope_score, 1),
                "river_surge_score": round(river_score, 1),
                "historical_susceptibility_score": round(hist_score, 1)
            }
        }
