from typing import List, Dict, Any
from app.models.schemas import HistoricalDisasterEvent

HISTORICAL_EVENTS_DB: List[HistoricalDisasterEvent] = [
    HistoricalDisasterEvent(
        id="HIST-UK-2021-01",
        location_name="Rishi Ganga Gorge, Raini",
        ward_id="W-UK-CHM-04",
        district="Chamoli",
        state="Uttarakhand",
        event_type="Debris Flow / Flash Flood",
        date="2021-02-07",
        trigger_rainfall_mm=112.5,
        casualties=204,
        houses_damaged=85,
        severity="Critical",
        coordinates=[30.4850, 79.6980],
        description="Rock and ice avalanche triggered catastrophic flash flood in Rishi Ganga river, washing away NTPC Hydro Project."
    ),
    HistoricalDisasterEvent(
        id="HIST-HP-2023-04",
        location_name="Pandoh Dam Bypass Slope",
        ward_id="W-HP-MND-01",
        district="Mandi",
        state="Himachal Pradesh",
        event_type="Landslide & Floods",
        date="2023-07-09",
        trigger_rainfall_mm=165.0,
        casualties=18,
        houses_damaged=42,
        severity="High",
        coordinates=[31.6745, 77.0195],
        description="Continuous 72-hour monsoonal cloudburst caused massive slope failure along NH-21 and flooding in Beas river."
    ),
    HistoricalDisasterEvent(
        id="HIST-KL-2024-02",
        location_name="Chooralmala - Mundakkai",
        ward_id="W-KL-WYN-05",
        district="Wayanad",
        state="Kerala",
        event_type="Landslide",
        date="2024-07-30",
        trigger_rainfall_mm=372.0,
        casualties=350,
        houses_damaged=220,
        severity="Critical",
        coordinates=[11.5350, 76.1280],
        description="Unprecedented 24-hr torrential rainfall triggered massive slope failure in Vellarimala hills, destroying Chooralmala village."
    ),
    HistoricalDisasterEvent(
        id="HIST-UK-2023-08",
        location_name="Joshimath Upper Ridge",
        ward_id="W-UK-CHM-03",
        district="Chamoli",
        state="Uttarakhand",
        event_type="Land Subsidence & Slope Slide",
        date="2023-01-05",
        trigger_rainfall_mm=45.0,
        casualties=0,
        houses_damaged=860,
        severity="High",
        coordinates=[30.5540, 79.5680],
        description="Sub-surface piping and pore pressure increase led to widespread structural cracking and slow-moving mass wasting."
    ),
    HistoricalDisasterEvent(
        id="HIST-HP-2023-08",
        location_name="Aut Tunnel Slope Segment",
        ward_id="W-HP-MND-02",
        district="Mandi",
        state="Himachal Pradesh",
        event_type="Cloudburst & Debris Slide",
        date="2023-08-14",
        trigger_rainfall_mm=140.0,
        casualties=12,
        houses_damaged=18,
        severity="High",
        coordinates=[31.7340, 77.1250],
        description="Flash surge debris flow blocked highway tunnel portal and submerged lower agricultural terraces."
    )
]

class HistoricalDBService:
    @classmethod
    def get_all_events(cls) -> List[HistoricalDisasterEvent]:
        return HISTORICAL_EVENTS_DB

    @classmethod
    def get_events_by_ward(cls, ward_id: str) -> List[HistoricalDisasterEvent]:
        return [e for e in HISTORICAL_EVENTS_DB if e.ward_id == ward_id]

    @classmethod
    def get_events_by_district(cls, district: str) -> List[HistoricalDisasterEvent]:
        return [e for e in HISTORICAL_EVENTS_DB if e.district.lower() == district.lower()]
