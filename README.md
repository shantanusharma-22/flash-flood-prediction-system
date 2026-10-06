# Flash Flood & Landslide Prediction System for Hilly Regions

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![NDRF / MHA](https://img.shields.io/badge/Organization-NDRF%20%7C%20MHA-orange.svg)](https://ndrf.gov.in/)
[![Gemini AI Powered](https://img.shields.io/badge/AI-Gemini%203.7%20Flash-indigo.svg)](https://ai.google.dev/)

A predictive hyper-local early warning platform designed for the **National Disaster Response Force (NDRF)** and the **Ministry of Home Affairs (MHA), Government of India**. 

This platform integrates real-time IoT weather and soil telemetry, physics-based slope stability models, historical disaster inventories, interactive GIS topographic mapping, and **Google Gemini AI** to provide actionable lead-time warnings (15 to 45+ minutes) for village and ward level evacuation in vulnerable hilly states (e.g., Himachal Pradesh, Uttarakhand, Kerala's Western Ghats, Sikkim).

---

## 📌 Problem Statement Background

Hilly states in India are highly vulnerable to sudden landslides, cloudbursts, and flash floods triggered by short-duration, high-intensity rainfall. Existing regional warning systems lack hyper-local spatial resolution (at the village/ward level) and geotechnical slope stability integration, resulting in minimal lead times for emergency evacuation.

### Expected Solution
An end-to-end multi-source predictive platform that:
- Integrates rainfall gauges, volumetric soil moisture probes ($VWC\%$), river level sensors, and slope parameters.
- Dynamically evaluates slope failure risk using geotechnical physics (**Infinite Slope Model**).
- Computes village/ward level **Actionable Evacuation Lead Times** (in minutes).
- Generates automated tactical deployment blueprints for NDRF battalions using **Gemini AI**.
- Provides a real-time **Disaster Scenario Simulator** to inject cloudburst and saturation conditions for emergency drills.

---

## 🏛 System Architecture

```
                                  +---------------------------------------+
                                  |  IoT Sensors / Weather Telemetry      |
                                  |  (Rainfall, Soil Moisture, Suction)   |
                                  +-------------------+-------------------+
                                                      |
                                                      v
+-------------------------------+  Dynamic Data   +---------------------------------------+
|  Historical Landslide DB     | -------------> |  FastAPI Python Backend Engine        |
|  & Slope Stability Physics    |                  |  - Infinite Slope Stability Model     |
+-------------------------------+                  |  - Multi-Criteria Risk Scoring        |
                                                   |  - Lead-Time Estimation Engine        |
                                                   |  - Live Telemetry WebSocket Stream    |
                                                   |  - Gemini AI Response Generator       |
                                                   +-------------------+-------------------+
                                                                       |
                                                                       v
                                                   +---------------------------------------+
                                                   |  Interactive GIS Command Center UI    |
                                                   |  - Leaflet Topo & Ward Risk Overlays  |
                                                   |  - Live Telemetry & Trend Charts      |
                                                   |  - Actionable Lead-Time Counter       |
                                                   |  - SMS / Broadcast Dispatcher         |
                                                   +---------------------------------------+
```

---

## 🧮 Geotechnical Physics & Risk Formulation

### 1. Infinite Slope Factor of Safety ($FoS$)
The geotechnical physics module evaluates the Mohr-Coulomb failure criterion for unsaturated/saturated slope failure:

$$FoS = \frac{c' + (\gamma_{sat} - m \cdot \gamma_w) \cdot z \cdot \cos^2\theta \cdot \tan\phi'}{\gamma_{sat} \cdot z \cdot \sin\theta \cdot \cos\theta}$$

where:
- $c'$: Effective soil cohesion ($\text{kPa}$)
- $\phi'$: Effective internal friction angle ($\text{degrees}$)
- $\theta$: Slope inclination angle ($\text{degrees}$)
- $z$: Critical shear plane failure depth ($\text{meters}$)
- $m$: Soil saturation ratio ($VWC / VWC_{sat}$)
- $\gamma_{sat}$: Saturated soil unit weight ($\text{kN/m}^3$)
- $\gamma_w$: Unit weight of water ($9.81 \, \text{kN/m}^3$)

**Stability Tiers:**
- $FoS > 1.5$: **STABLE (Green)**
- $1.0 < FoS \le 1.3$: **HIGH RISK WARNING (Yellow / Orange)**
- $FoS \le 1.0$: **SLOPE FAILURE IMMINENT (Red)**

### 2. Multi-Criteria Composite Risk Matrix
$$\text{Risk Score} = 0.35 \times R_{\text{intensity}} + 0.25 \times S_{\text{moisture}} + 0.25 \times (1.5 - FoS) \times 25 + 0.15 \times \text{Hist}_{\text{susceptibility}}$$

---

## ✨ Key Features

- **Interactive GIS Topographic Map**: Visualizes ward polygons color-coded by hazard risk level (**GREEN**, **YELLOW**, **ORANGE**, **RED**) with live sensor tooltips.
- **Real-Time Telemetry Analytics**: Chart.js graphs displaying rainfall intensity ($mm/h$), soil moisture ($VWC\%$), river level ($m$), and $FoS$ degradation trends.
- **Actionable Lead-Time Counter**: Dynamic countdown timer computing remaining minutes before failure for pre-disaster evacuation.
- **Gemini AI Command Copilot**: Synthesizes real-time field data using `gemini-3.7-flash` to output NDRF deployment instructions and local language advisories.
- **Disaster Scenario Simulator**: Allows emergency managers to trigger simulated **Cloudburst (120 mm/h)**, **Soil Saturation Spikes**, or **River Flash Surges**.

---

## 🛠 Tech Stack

- **Backend**: Python 3.10+, FastAPI, Pydantic, NumPy, SciPy, WebSockets, `google-genai` SDK.
- **Frontend**: Single-Page Application (SPA), HTML5, Tailwind CSS, Leaflet GIS, Chart.js, Lucide Icons.
- **Testing**: Pytest.
- **Deployment**: Uvicorn, Docker, Cloud Run / Render / Heroku configurations.

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10 or higher
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/flash-flood-prediction-system.git
cd flash-flood-prediction-system
```

### 2. Set Up Virtual Environment & Install Dependencies
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 3. Set Gemini API Key (Optional for AI Copilot)
```bash
# Windows (PowerShell)
$env:GEMINI_API_KEY="your-gemini-api-key"

# Linux/macOS
export GEMINI_API_KEY="your-gemini-api-key"
```

### 4. Run the Server
```bash
python run.py
```
Open your browser and navigate to:
- **Command Dashboard**: `http://localhost:8000`
- **Swagger API Docs**: `http://localhost:8000/docs`

---

## 🧪 Running Unit Tests

Run the test suite covering physical slope calculations and multi-criteria risk scoring:

```bash
python -m pytest
```

Output:
```text
tests/test_physics.py ...                                                [ 60%]
tests/test_risk_engine.py ..                                             [100%]
============================== 5 passed in 0.03s ==============================
```

---

## 📡 REST API Reference

| Endpoint | Method | Description |
|---|---|---|
| `GET /` | `GET` | Serves the interactive GIS Command Dashboard |
| `GET /api/health` | `GET` | Health check endpoint |
| `GET /api/wards` | `GET` | Returns real-time hazard status for all active village/wards |
| `GET /api/sensors` | `GET` | Returns latest IoT sensor telemetry readings |
| `GET /api/historical-events` | `GET` | Returns disaster inventory records |
| `POST /api/predict` | `POST` | Calculates $FoS$ and failure probability for custom slope parameters |
| `POST /api/simulator/scenario` | `POST` | Triggers disaster scenarios (`CLOUDBURST`, `SATURATION_SPIKE`, `FLASH_SURGE`) |
| `POST /api/ai-advisory` | `POST` | Generates Gemini AI situation report and NDRF deployment plan |
| `WS /ws/telemetry` | `WebSocket` | Live telemetry stream websocket |

---

## 🐳 Docker Deployment

Build and run using Docker:

```bash
# Build Docker image
docker build -t ndrf-flash-flood-system .

# Run container
docker run -d -p 8000:8000 -e GEMINI_API_KEY="your_key" ndrf-flash-flood-system
```

---

## 📄 License & Acknowledgments

- **License**: MIT License.
- **Organization**: Prepared for National Disaster Response Force (NDRF), Disaster Management Division, Ministry of Home Affairs, Government of India.
