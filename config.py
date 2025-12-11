import os

# ==================================================
# === RUN/TUNING PARAMETERS ===
# ==================================================
MAX_VMS = 9
PLAYERS_PER_VM = 3500
HOURLY_PRICE = 1.5
UPDATE_INTERVAL = 60*2  # sekunder mellom oppdatering av metrics
DEFAULT_SCALING = "normal"
MIN_MINUTES_TO_NEXT_HOUR_FOR_SHUTDOWN = 10

# ==================================================
# API / METRICS CONFIG
# ==================================================
API_URL = "http://10.196.242.62/metrics"
FILTER_FIELD = "publisher"
FILTER_VALUE = "Valve"

# ==================================================
# === OpenStack AUTH & CONFIG ===
# ==================================================
OS_AUTH_TYPE = "v3applicationcredential"
OS_AUTH_URL = "https://pegasus.sky.oslomet.no:5000"
OS_IDENTITY_API_VERSION = "3"
OS_REGION_NAME = "Pilestredet"
OS_INTERFACE = "public"
OS_APPLICATION_CREDENTIAL_ID = "51bec6c79e8948d1a778b20841593757"
OS_APPLICATION_CREDENTIAL_SECRET = "mkWSM2RiqtMINzZjcETtOAS2GFScHo5T6CtxW4cPW6s9lK4ajVrTd93q5tnNbCO7GO7FtzFZcvF5R3ghPZ5FGQ"

# ==================================================
# === SCALING STRATEGIES EXPLANATION ===
# ==================================================
# Denne configen styrer hvordan skaleringsalgoritmene oppfører seg per spill.
# 
# Parametere:
# - strategy: Hvilken type skaleringsstrategi som brukes:
#     "predictive" → basert på historisk mønster + forecast
#     "trend" → reagerer på økning/nedgang i spillere siden forrige intervall
#     "aggressive" → skaler raskere når kapasiteten begynner å bli full
#     "passive" → skaler mer konservativt
#     "normal" → standard opp-/nedskalering
#
# - time_offset_hours: (kun predictive) Justerer tidspunktet mot datasettet som er basert på normal dag/time.
# - lookahead_intervals: (kun predictive) Hvor mange 5-minutters intervaller frem i tid forecasten skal se.
# - buffer: (kun predictive) Hvor mange spillere som må være ledig på siste VM før systemet skalerer opp.
# - respect_current_load: (kun predictive/trend) Om algoritmen skal forhindre nedskalering under nåværende behov.
# - threshold_percent: (kunn trend) Hvor mange prosent av siste VM må være fylt før den skal skalere
# - max_hourly_budget: (valgfritt, funker på alle) Maksimalt hvor mye spillet godtar at serverkostnader kan være per time.
#
# Eksempel:
# Hvis buffer = 75 og det er mindre enn 75 plasser igjen på siste VM → skaler opp.
# time_offset_hours = -6 → datasettet som brukes til forecasting er 6 timer bak nåværende tid.
# lookahead_intervals = 3 → prediksjon for 3x5 minutter frem i tid (15 min totalt).
# respect_current_load = True → hindrer algoritmen fra å skalere ned under dagens spillerbehov.

GAME_SCALING_CONFIG = {
    "Counter Strike": {
        "strategy": "predictive",
        "time_offset_hours": -6,
        "lookahead_intervals": 3,
        "buffer": 75,
        "respect_current_load": True
    },
    "Counter Strike: Global Offensive": {
        "strategy": "trend",
        "threshold_percent": 0.4,
        "respect_current_load": True
    },
    "Team Fortress 2": {
        "strategy": "aggressive",
        "max_hourly_budget": 250
    },
    "Dota 2": {
        "strategy": "trend",
        "threshold_percent": 0.8,
        "max_hourly_budget": 4090
    },
    "Garrys Mod": {
        "strategy": "passive",
        "buffer": 5
    }
}

# Default config for spill som ikke har spesifikk strategi
DEFAULT_SCALING_CONFIG = {
    "strategy": "normal",
    "buffer": 1,
    "time_offset_hours": 0,
    "lookahead_intervals": 3,
    "respect_current_load": False
}



# Game to track for OpenStack scaling
TARGET_GAME = "Counter Strike"

# ==================================================
# === OpenStack VM TEMPLATE CONFIG ===
# ==================================================
IMAGE_ID = "b0f9447e-35f8-4667-8ed9-624119b6c9ab"      # Ubuntu 22.04-LTS (Jammy Jellyfish)
FLAVOR_ID = "2db2d811-a566-4438-b7ad-64735413c2db"     # aem.2c4r.50g
NETWORK_ID = "374240bf-b8c4-45cd-b377-e32a247beb43"    # ⚠️ bruk UUID
KEYPAIR_NAME = "jorgenkey"                             # SSH Keypair
SECURITY_GROUP = "default"                             # Standard sikkerhetsgruppe

# ==================================================
# === FILE PATHS / LOGGING ===
# ==================================================
DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "games.json")

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "vm_changes.log")
os.makedirs(LOG_DIR, exist_ok=True)
