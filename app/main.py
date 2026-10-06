import os
import json
import math
import time
import asyncio
import logging
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime, timezone
from urllib.parse import urlparse
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Path, Body, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse, JSONResponse
from pydantic import BaseModel, Field

from app.models.schemas import (
    IoTSensorReading,
    WardStatus,
    HistoricalDisasterEvent,
    SlopeParameters,
    AIAdvisoryRequest,
    AIAdvisoryResponse,
    CitizenSOSRequest,
    CitizenSOSRecord,
    DispatchAlertRequest,
    DispatchAlertRecord,
    AIChatRequest,
    AIChatResponse,
    PhysicsSensitivityRequest
)
from app.models.physics import SlopeStabilityPhysics
from app.models.risk_engine import RiskEngine
from app.services.iot_simulator import iot_simulator_instance
from app.services.historical_db import HistoricalDBService
from app.services.gemini_advisor import GeminiAdvisorService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ndrf_prediction_system")

# ---------------------------------------------------------------------------
# Security configuration
# ---------------------------------------------------------------------------
ALLOWED_SCENARIOS = ("NORMAL", "CLOUDBURST", "SATURATION_SPIKE", "FLASH_SURGE", "GLOF")

# Locks the dashboard down to its own origin plus the CDN/tile providers it
# actually uses. Inline scripts were moved to /static/*.js so no 'unsafe-inline'
# is needed for script-src.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "script-src 'self' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com https://cdn.jsdelivr.net; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "img-src 'self' data: blob: https://*.tile.openstreetmap.org https://*.tile.opentopomap.org "
    "https://server.arcgisonline.com https://*.basemaps.cartocdn.com; "
    "connect-src 'self'; "
    "manifest-src 'self'; "
    "worker-src 'self' blob:"
)

# Simple in-memory sliding-window limiter for state-changing endpoints.
RATE_LIMIT_WINDOW_SEC = 60.0
RATE_LIMIT_MAX_MUTATIONS = int(os.environ.get("RATE_LIMIT_MAX_MUTATIONS", "300"))
_rate_limit_hits: Dict[str, List[float]] = {}
RATE_LIMIT_TRACKED_CLIENTS = 5000


def _rate_limit(client_key: str) -> bool:
    """Returns True when the client is over the mutation rate limit."""
    now = time.monotonic()
    hits = _rate_limit_hits.setdefault(client_key, [])
    cutoff = now - RATE_LIMIT_WINDOW_SEC
    while hits and hits[0] <= cutoff:
        hits.pop(0)
    if len(hits) >= RATE_LIMIT_MAX_MUTATIONS:
        return True
    hits.append(now)
    if len(_rate_limit_hits) > RATE_LIMIT_TRACKED_CLIENTS:
        # Bound memory: drop the oldest tracked clients wholesale.
        stale = [k for k, v in _rate_limit_hits.items() if not v or v[-1] <= cutoff]
        for k in stale:
            _rate_limit_hits.pop(k, None)
        if len(_rate_limit_hits) > RATE_LIMIT_TRACKED_CLIENTS:
            _rate_limit_hits.clear()
    return False


app = FastAPI(
    title="NDRF Flash Flood & Landslide Prediction System API",
    description="Hyper-local disaster prediction platform for hilly regions integrating multi-source IoT telemetry, geotechnical slope physics, and Gemini AI.",
    version="3.3.0",
    # Interactive API docs expose the full attack surface; disable in production
    # by setting DISABLE_DOCS=1.
    docs_url=None if os.environ.get("DISABLE_DOCS") == "1" else "/docs",
    redoc_url=None if os.environ.get("DISABLE_DOCS") == "1" else "/redoc",
    openapi_url=None if os.environ.get("DISABLE_DOCS") == "1" else "/openapi.json",
)


@app.middleware("http")
async def security_headers_and_rate_limit(request, call_next):
    """Adds hardening headers and throttles state-changing requests."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        client = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Only trust the first hop when behind a documented trusted proxy.
            client = forwarded.split(",")[0].strip() or client
        if _rate_limit(client):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded for state-changing requests. Try again shortly."},
                headers={"Retry-After": str(int(RATE_LIMIT_WINDOW_SEC))},
            )

    response = await call_next(request)
    headers = response.headers
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Referrer-Policy", "no-referrer")
    headers.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=(), payment=(), usb=()")
    headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")

    if request.url.path.startswith("/api/"):
        headers.setdefault("Cache-Control", "no-store")

    if headers.get("content-type", "").startswith("text/html"):
        headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def _json_safe(value: Any) -> Any:
    """Makes FastAPI validation errors JSON-serialisable.

    Non-finite floats (NaN/Infinity) appear verbatim in `exc.errors()['input']`,
    and Starlette's JSONResponse refuses to encode them — which would turn a
    clean 422 into a 500 crash.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": _json_safe(exc.errors())})

# Mount static folder for dashboard UI and assets
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_path = os.path.join(static_dir, "index.html")
    return FileResponse(index_path)

@app.get("/manifest.json")
async def serve_manifest():
    manifest_path = os.path.join(static_dir, "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/manifest+json")
    return {"name": "NDRF Flash Flood Prediction System"}

@app.get("/sw.js")
async def serve_service_worker():
    sw_path = os.path.join(static_dir, "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript")
    return PlainTextResponse("// Service Worker stub", media_type="application/javascript")

@app.get("/api/health")
async def health_check():
    return {
        "status": "HEALTHY",
        "system": "NDRF Flash Flood & Landslide Prediction Platform",
        "telemetry_stream": iot_simulator_instance.simulation_scenario,
        "active_wards_monitored": len(iot_simulator_instance.wards_data),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/wards", response_model=List[WardStatus])
async def get_all_wards():
    return iot_simulator_instance.get_all_ward_statuses()

@app.get("/api/wards/{ward_id}", response_model=WardStatus)
async def get_ward_by_id(ward_id: str = Path(..., min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_\-]+$")):
    wards = iot_simulator_instance.get_all_ward_statuses()
    for w in wards:
        if w.ward_id == ward_id:
            return w
    raise HTTPException(status_code=404, detail="Ward not found")

@app.get("/api/sensors", response_model=List[IoTSensorReading])
async def get_sensors():
    return iot_simulator_instance.get_latest_sensor_readings()

@app.get("/api/historical-events", response_model=List[HistoricalDisasterEvent])
async def get_historical_events():
    return HistoricalDBService.get_all_events()

@app.post("/api/predict")
async def predict_slope_stability(params: SlopeParameters):
    physics_res = SlopeStabilityPhysics.calculate_factor_of_safety(
        slope_angle_deg=params.slope_angle_deg,
        cohesion_kpa=params.cohesion_kpa,
        friction_angle_deg=params.friction_angle_deg,
        soil_depth_m=params.soil_depth_m,
        volumetric_water_content=params.volumetric_water_content,
        porosity_sat_vwc=params.saturation_vwc,
        soil_dry_weight_kn_m3=params.soil_unit_weight_kn_m3,
        root_cohesion_kpa=params.root_cohesion_kpa
    )
    return physics_res

@app.post("/api/physics/sensitivity")
async def calculate_physics_sensitivity(req: PhysicsSensitivityRequest):
    return SlopeStabilityPhysics.calculate_sensitivity_curve(
        slope_angle_deg=req.slope_angle_deg,
        cohesion_kpa=req.cohesion_kpa,
        friction_angle_deg=req.friction_angle_deg,
        soil_depth_m=req.soil_depth_m
    )

class ScenarioRequest(BaseModel):
    scenario: Literal["NORMAL", "CLOUDBURST", "SATURATION_SPIKE", "FLASH_SURGE", "GLOF"]
    ward_id: str = Field("W-UK-CHM-04", min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_\-]+$")
    custom_rainfall: Optional[float] = Field(None, ge=0.0, le=300.0, allow_inf_nan=False)

@app.post("/api/simulator/scenario")
async def set_simulator_scenario(req: ScenarioRequest):
    if req.ward_id not in iot_simulator_instance.ward_states:
        raise HTTPException(status_code=404, detail="Target ward does not exist")
    iot_simulator_instance.set_simulation_scenario(req.scenario, req.ward_id, req.custom_rainfall)
    return {
        "status": "SUCCESS",
        "active_scenario": req.scenario,
        "target_ward_id": req.ward_id,
        "message": f"Scenario {req.scenario} activated for {req.ward_id}"
    }

@app.post("/api/ai-advisory", response_model=AIAdvisoryResponse)
async def get_ai_advisory(req: AIAdvisoryRequest):
    wards = iot_simulator_instance.get_all_ward_statuses()
    target_ward = None
    for w in wards:
        if w.ward_id == req.ward_id:
            target_ward = w
            break
    
    if not target_ward and wards:
        target_ward = wards[0]

    if not target_ward:
        raise HTTPException(status_code=404, detail="No ward data available")

    return GeminiAdvisorService.generate_advisory(target_ward, req)

@app.post("/api/ai-chat", response_model=AIChatResponse)
async def ai_copilot_chat(req: AIChatRequest):
    wards = iot_simulator_instance.get_all_ward_statuses()
    return GeminiAdvisorService.chat_copilot(req, wards)

@app.post("/api/citizen/sos", response_model=CitizenSOSRecord)
async def submit_citizen_sos(req: CitizenSOSRequest):
    return iot_simulator_instance.add_citizen_sos(req)

@app.get("/api/citizen/sos", response_model=List[CitizenSOSRecord])
async def get_citizen_sos_list():
    return iot_simulator_instance.get_citizen_sos_list()

class SOSStatusUpdate(BaseModel):
    status: Literal["PENDING", "DISPATCHED", "RESOLVED"]

@app.post("/api/citizen/sos/{sos_id}/status")
async def update_sos_status(
    sos_id: str = Path(..., min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_\-]+$"),
    body: SOSStatusUpdate = Body(...),
):
    ok = iot_simulator_instance.update_sos_status(sos_id, body.status)
    if not ok:
        raise HTTPException(status_code=404, detail="SOS record not found")
    return {"status": "SUCCESS", "sos_id": sos_id, "new_status": body.status}

@app.post("/api/alerts/dispatch", response_model=DispatchAlertRecord)
async def dispatch_emergency_alert(req: DispatchAlertRequest):
    return iot_simulator_instance.add_dispatch_alert(req)

@app.get("/api/alerts/history", response_model=List[DispatchAlertRecord])
async def get_dispatch_history():
    return iot_simulator_instance.get_dispatch_history()

@app.get("/api/reports/iap", response_class=PlainTextResponse)
async def generate_incident_action_plan(ward_id: Optional[str] = "W-UK-CHM-04"):
    wards = iot_simulator_instance.get_all_ward_statuses()
    target_ward = next((w for w in wards if w.ward_id == ward_id), wards[0] if wards else None)
    now = datetime.now(timezone.utc).strftime("%d-%b-%Y %H:%M:%S UTC")

    if not target_ward:
        return "NO DATA AVAILABLE"

    lines = [
        "================================================================================",
        "          NATIONAL DISASTER RESPONSE FORCE (NDRF) - INCIDENT ACTION PLAN (IAP) ",
        "================================================================================",
        f"OPERATIONAL PERIOD: {now} | OPERATIONAL SECTOR: {target_ward.district.upper()}, {target_ward.state.upper()}",
        f"INCIDENT NAME     : FLASH FLOOD & LANDSLIDE PRE-DISASTER DEPLOYMENT",
        f"TARGET WARD       : {target_ward.ward_name} (ID: {target_ward.ward_id})",
        "--------------------------------------------------------------------------------",
        "1. CURRENT SITUATION & GEOTECHNICAL TELEMETRY",
        f"   - Hazard Alert Level   : {target_ward.risk_level} (Composite Risk Score: {target_ward.risk_score}/100)",
        f"   - Factor of Safety     : FoS = {target_ward.factor_of_safety} (Threshold < 1.0 = Critical)",
        f"   - Rainfall Rate        : 1-Hour: {target_ward.rainfall_1h_mm} mm/h | 24-Hour: {target_ward.rainfall_24h_mm} mm",
        f"   - Soil Moisture (VWC)  : {target_ward.soil_saturation_pct}% Saturation",
        f"   - River Water Level    : {target_ward.river_water_level_m} m (Danger Mark: {target_ward.river_danger_level_m} m)",
        f"   - Lead Time Remaining  : {target_ward.estimated_lead_time_min} MINUTES",
        "",
        "2. STRATEGIC OBJECTIVES",
        f"   a. Safely evacuate {target_ward.population} residents from {target_ward.ward_name} to designated shelters.",
        f"   b. Cordon off debris runout paths and low-lying riverbank sectors.",
        f"   c. Maintain comms via VHF Satellite Repeater Net-14.",
        "",
        "3. DESIGNATED EVACUATION TRACKS & RELIEF CENTERS",
        f"   - Primary Route: {target_ward.evacuation_routes[0] if target_ward.evacuation_routes else 'High Ridge Path'}",
        f"   - Primary Camp : {target_ward.shelter_locations[0] if target_ward.shelter_locations else 'Government Secondary School'}",
        "",
        "4. BATTALION ASSIGNMENTS & RESOURCE ALLOCATION",
        "   - Team Alpha : Ridge path traffic management & vulnerable citizen transport",
        "   - Team Bravo : River sector swiftwater rescue & ropeway bridging",
        "   - Heavy Plant: 2x JCB Earthmovers positioned at sector gateway",
        "   - Medical    : 1x Mobile Emergency Treatment Camp with 50-bed triage",
        "================================================================================",
        "APPROVED BY: COMMANDING OFFICER, NDRF 14TH BATTALION / DISTRICT DISASTER AUTHORITY",
        "================================================================================"
    ]
    return "\n".join(lines)

# WebSocket endpoint for real-time telemetry streaming
@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    # Cross-site WebSocket hijacking guard: browsers always send Origin,
    # so reject any origin that is not this exact deployment.
    origin = websocket.headers.get("origin")
    if origin:
        parsed = urlparse(origin)
        host = websocket.headers.get("host", "")
        if parsed.scheme not in ("http", "https") or parsed.netloc != host:
            logger.warning(f"Rejected telemetry WebSocket with foreign origin: {origin}")
            await websocket.close(code=1008)
            return

    await websocket.accept()
    logger.info("WebSocket telemetry client connected")
    try:
        while True:
            wards = iot_simulator_instance.get_all_ward_statuses()
            sensors = iot_simulator_instance.get_latest_sensor_readings()
            payload = {
                "scenario": iot_simulator_instance.simulation_scenario,
                "target_ward_id": iot_simulator_instance.target_ward_id,
                "wards": [w.model_dump() for w in wards],
                "sensors": [s.model_dump() for s in sensors],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(2.5)
    except WebSocketDisconnect:
        logger.info("WebSocket telemetry client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
