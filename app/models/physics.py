import math
from typing import Dict, Any, List

class SlopeStabilityPhysics:
    """
    Geotechnical Physics Engine implementing the Infinite Slope Model 
    and Soil Water Characteristic Curve (SWCC) for slope stability evaluation.
    """
    
    GAMMA_WATER = 9.81  # kN/m3

    @classmethod
    def calculate_factor_of_safety(
        cls,
        slope_angle_deg: float,
        cohesion_kpa: float,
        friction_angle_deg: float,
        soil_depth_m: float,
        volumetric_water_content: float,
        porosity_sat_vwc: float = 0.45,
        soil_dry_weight_kn_m3: float = 16.0,
        root_cohesion_kpa: float = 0.0
    ) -> Dict[str, Any]:
        """
        Calculate Factor of Safety (FoS) based on Mohr-Coulomb failure criterion
        and dynamic moisture saturation ratio (m).
        """
        # Convert angles to radians
        theta = math.radians(slope_angle_deg)
        phi = math.radians(friction_angle_deg)

        # Avoid zero or negative slope angle
        if theta <= 0.001:
            return {
                "factor_of_safety": 99.0,
                "stability_status": "STABLE",
                "saturation_ratio": 0.0,
                "failure_probability_pct": 0.0,
                "driving_shear_stress_kpa": 0.0,
                "resisting_shear_stress_kpa": 999.0,
                "effective_normal_stress_kpa": 0.0
            }

        # Calculate saturation ratio m (0.0 to 1.0)
        m = min(max(volumetric_water_content / max(porosity_sat_vwc, 0.01), 0.0), 1.0)

        # Saturated unit weight of soil
        gamma_sat = soil_dry_weight_kn_m3 + (m * porosity_sat_vwc * cls.GAMMA_WATER)

        # Resisting forces (Shear Strength)
        # (c' + c_root) + (gamma_sat - m * gamma_w) * z * cos^2(theta) * tan(phi)
        effective_normal_stress = (gamma_sat - (m * cls.GAMMA_WATER)) * soil_depth_m * (math.cos(theta) ** 2)
        effective_normal_stress = max(effective_normal_stress, 0.0)
        
        total_cohesion = cohesion_kpa + root_cohesion_kpa
        resisting_stress = total_cohesion + (effective_normal_stress * math.tan(phi))

        # Driving forces (Shear Stress)
        # gamma_sat * z * sin(theta) * cos(theta)
        driving_stress = gamma_sat * soil_depth_m * math.sin(theta) * math.cos(theta)

        if driving_stress <= 0.0001:
            fos = 99.0
        else:
            fos = resisting_stress / driving_stress

        # Bound FoS reasonable range
        fos = round(float(fos), 3)

        # Determine stability classification
        if fos > 1.5:
            status = "STABLE"
            prob = max(1.0, round((2.0 - fos) * 10, 1))
        elif 1.2 < fos <= 1.5:
            status = "MODERATE_STABILITY"
            prob = round(15.0 + (1.5 - fos) * 50, 1)
        elif 1.0 < fos <= 1.2:
            status = "HIGH_RISK_WARNING"
            prob = round(45.0 + (1.2 - fos) * 150, 1)
        else:
            status = "SLOPE_FAILURE_IMMINENT"
            prob = min(99.9, round(85.0 + (1.0 - fos) * 100, 1))

        return {
            "factor_of_safety": max(0.1, fos),
            "stability_status": status,
            "saturation_ratio": round(m, 3),
            "failure_probability_pct": min(max(prob, 0.0), 99.9),
            "driving_shear_stress_kpa": round(driving_stress, 2),
            "resisting_shear_stress_kpa": round(resisting_stress, 2),
            "effective_normal_stress_kpa": round(effective_normal_stress, 2)
        }

    @classmethod
    def calculate_sensitivity_curve(
        cls,
        slope_angle_deg: float,
        cohesion_kpa: float,
        friction_angle_deg: float,
        soil_depth_m: float
    ) -> Dict[str, Any]:
        """
        Calculates FoS curve as Volumetric Water Content (VWC) varies from 0.10 to 0.45 (100% saturation).
        """
        vwc_steps = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.44, 0.45]
        curve = []
        for vwc in vwc_steps:
            res = cls.calculate_factor_of_safety(
                slope_angle_deg=slope_angle_deg,
                cohesion_kpa=cohesion_kpa,
                friction_angle_deg=friction_angle_deg,
                soil_depth_m=soil_depth_m,
                volumetric_water_content=vwc
            )
            curve.append({
                "vwc": vwc,
                "saturation_pct": round((vwc / 0.45) * 100, 1),
                "factor_of_safety": res["factor_of_safety"],
                "failure_probability_pct": res["failure_probability_pct"],
                "status": res["stability_status"]
            })
        return {"sensitivity_curve": curve}
