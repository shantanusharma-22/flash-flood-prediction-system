from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

class IoTSensorReading(BaseModel):
    sensor_id: str
    ward_id: str
    sensor_type: str  # 'rain_gauge', 'soil_moisture', 'pore_pressure', 'river_gauge', 'inclinometer'
    name: str
    lat: float
    lng: float
    value: float
    unit: str
    timestamp: str
    battery_level: float = 95.0
    rssi_dbm: int = -65
    status: str = "ONLINE"  # ONLINE, DEGRADED, OFFLINE

class SlopeParameters(BaseModel):
    # Bounds are physical plausibility limits; allow_inf_nan=False stops NaN/Infinity
    # (accepted by Python's JSON parser) from poisoning the physics engine output.
    slope_angle_deg: float = Field(..., ge=0.0, le=90.0, allow_inf_nan=False, description="Slope inclination in degrees")
    cohesion_kpa: float = Field(..., ge=0.0, le=500.0, allow_inf_nan=False, description="Effective soil cohesion in kPa")
    friction_angle_deg: float = Field(..., ge=0.0, le=90.0, allow_inf_nan=False, description="Soil internal friction angle in degrees")
    soil_unit_weight_kn_m3: float = Field(16.0, gt=0.0, le=100.0, allow_inf_nan=False, description="Unit weight of unsaturated soil in kN/m3")
    soil_depth_m: float = Field(..., ge=0.01, le=50.0, allow_inf_nan=False, description="Critical potential sliding depth in meters")
    volumetric_water_content: float = Field(..., ge=0.0, le=1.0, allow_inf_nan=False, description="Current soil moisture (0.0 to 1.0 VWC)")
    saturation_vwc: float = Field(0.45, gt=0.0, le=1.0, allow_inf_nan=False, description="Porosity / Saturated VWC")
    root_cohesion_kpa: float = Field(0.0, ge=0.0, le=100.0, allow_inf_nan=False, description="Additional root cohesion from forest cover in kPa")

class WardStatus(BaseModel):
    ward_id: str
    ward_name: str
    district: str
    state: str
    population: int
    elevation_m: float
    avg_slope_deg: float
    risk_level: str  # 'GREEN', 'YELLOW', 'ORANGE', 'RED'
    risk_score: float  # 0.0 to 100.0
    factor_of_safety: float  # Slope stability FoS
    rainfall_1h_mm: float
    rainfall_24h_mm: float
    soil_saturation_pct: float
    river_water_level_m: float
    river_danger_level_m: float
    estimated_lead_time_min: int
    historical_disasters_count: int
    recommended_action: str
    last_updated: str
    polygon: List[List[float]]  # GeoJSON coordinates [[lat, lng], ...]
    evacuation_routes: List[str] = []
    shelter_locations: List[str] = []

class HistoricalDisasterEvent(BaseModel):
    id: str
    location_name: str
    ward_id: str
    district: str
    state: str
    event_type: str  # 'Landslide', 'Flash Flood', 'Debris Flow', 'Cloudburst'
    date: str
    trigger_rainfall_mm: float
    casualties: int
    houses_damaged: int
    severity: str  # High, Critical, Moderate
    coordinates: List[float]  # [lat, lng]
    description: str

class AlertNotification(BaseModel):
    id: str
    ward_id: str
    ward_name: str
    severity: str  # 'GREEN', 'YELLOW', 'ORANGE', 'RED'
    title: str
    message: str
    suggested_lead_time_min: int
    evacuation_routes: List[str]
    shelter_locations: List[str]
    timestamp: str
    is_dispatched: bool = False

class AIAdvisoryRequest(BaseModel):
    ward_id: str = Field("W-UK-CHM-04", min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_\-]+$")
    scenario_notes: Optional[str] = Field(None, max_length=1000)
    language: str = Field("English", min_length=1, max_length=32)  # "English", "Hindi", "Garhwali", "Punjabi", "Malayalam", "Bengali"

class AIAdvisoryResponse(BaseModel):
    ward_id: str
    ward_name: str
    district: str
    current_risk_level: str
    situation_summary: str
    tactical_ndrf_instructions: List[str]
    public_evacuation_broadcast: str
    resource_allocation_plan: List[str]
    timestamp: str

class CitizenSOSRequest(BaseModel):
    # Citizen-submitted (untrusted) fields: length caps and coordinate bounds keep
    # the queue usable and reject nonsense before it reaches the command console.
    ward_id: Optional[str] = Field(None, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_\-]+$")
    citizen_name: str = Field(..., min_length=2, max_length=80)
    phone_number: str = Field(..., min_length=5, max_length=24, pattern=r"^[0-9+\-\s()]+$")
    lat: float = Field(..., ge=-90.0, le=90.0, allow_inf_nan=False)
    lng: float = Field(..., ge=-180.0, le=180.0, allow_inf_nan=False)
    people_count: int = Field(1, ge=1, le=999)
    situation_desc: str = Field(..., min_length=3, max_length=500)
    requires_medical: bool = False

class CitizenSOSRecord(BaseModel):
    sos_id: str
    ward_id: str
    ward_name: str
    citizen_name: str
    phone_number: str
    lat: float
    lng: float
    people_count: int
    situation_desc: str
    requires_medical: bool
    timestamp: str
    status: str = "PENDING"  # PENDING, DISPATCHED, RESOLVED

DispatchChannel = Literal["SMS", "VHF_RADIO", "PUBLIC_SIREN", "WHATSAPP"]
AlertSeverity = Literal["GREEN", "YELLOW", "ORANGE", "RED"]

class DispatchAlertRequest(BaseModel):
    ward_id: str = Field(..., min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_\-]+$")
    channels: List[DispatchChannel] = Field(
        ["SMS", "VHF_RADIO", "PUBLIC_SIREN", "WHATSAPP"], max_length=4
    )
    custom_message: Optional[str] = Field(None, max_length=500)
    severity: Optional[AlertSeverity] = None

class DispatchAlertRecord(BaseModel):
    dispatch_id: str
    ward_id: str
    ward_name: str
    severity: str
    message: str
    channels: List[str]
    recipients_count: int
    timestamp: str
    status: str = "DELIVERED"

class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    ward_id: Optional[str] = Field("W-UK-CHM-04", min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_\-]+$")
    history: Optional[List[Dict[str, str]]] = Field(None, max_length=20)

class AIChatResponse(BaseModel):
    reply: str
    suggested_actions: List[str] = []
    timestamp: str

class PhysicsSensitivityRequest(BaseModel):
    slope_angle_deg: float = Field(40.0, ge=0.0, le=90.0, allow_inf_nan=False)
    cohesion_kpa: float = Field(10.0, ge=0.0, le=500.0, allow_inf_nan=False)
    friction_angle_deg: float = Field(28.0, ge=0.0, le=90.0, allow_inf_nan=False)
    soil_depth_m: float = Field(2.5, ge=0.01, le=50.0, allow_inf_nan=False)
