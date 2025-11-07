import os

# === API CONFIG ===
API_URL = "http://10.196.242.62/metrics"
UPDATE_INTERVAL = 60*2  # in seconds
FILTER_FIELD = "publisher"
FILTER_VALUE = "Valve"
MAX_VMS = 999999999999
PLAYERS_PER_VM = 500
HOURLY_PRICE = 1.5

# === OpenStack CONFIG ===
OS_AUTH_TYPE = "v3applicationcredential"
OS_AUTH_URL = "https://pegasus.sky.oslomet.no:5000"
OS_IDENTITY_API_VERSION = "3"
OS_REGION_NAME = "Pilestredet"
OS_INTERFACE = "public"
OS_APPLICATION_CREDENTIAL_ID = "51bec6c79e8948d1a778b20841593757"
OS_APPLICATION_CREDENTIAL_SECRET = "mkWSM2RiqtMINzZjcETtOAS2GFScHo5T6CtxW4cPW6s9lK4ajVrTd93q5tnNbCO7GO7FtzFZcvF5R3ghPZ5FGQ"

# === FILE PATHS ===
DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "games.json")

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "vm_changes.log")
os.makedirs(LOG_DIR, exist_ok=True)









# === SCALING CONFIG ===
DEFAULT_SCALING = "normal"

# Per-game scaling strategies
GAME_SCALING_METHODS = {
    "Counter Strike: Global Offensive": "trend",
    "Counter Strike": "predictive",
    "Team Fortress 2": "aggressive",
    "Dota 2": "trend",
    # Others default to "normal"
}


