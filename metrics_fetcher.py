import requests
import re
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from scaling_algorithms import get_scaling_function, get_expected_players
from config import (
    API_URL, FILTER_FIELD, FILTER_VALUE, UPDATE_INTERVAL,
    DATA_DIR, OUTPUT_FILE, GAME_SCALING_METHODS, DEFAULT_SCALING, HOURLY_PRICE
)

os.makedirs(DATA_DIR, exist_ok=True)

def fetch_and_write_metrics():
    start_time = datetime.now(ZoneInfo("Europe/Oslo"))

    # Hent eksisterende data hvis den finnes
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r") as f:
            try:
                old_data = json.load(f)
                old_games = {g["name"]: g for g in old_data.get("games", [])}
            except json.JSONDecodeError:
                old_games = {}
    else:
        old_games = {}

    # Hent data fra API
    response = requests.get(API_URL)
    lines = response.text.splitlines()

    games = []
    any_changed = False  # flagg for å sjekke om minst ett spill har endret seg

    for line in lines:
        if f'{FILTER_FIELD}="{FILTER_VALUE}"' in line:
            title_match = re.search(r'title="([^"]+)"', line)
            count_match = re.search(r'\s(\d+)$', line)
            if title_match and count_match:
                title = title_match.group(1)
                player_count = int(count_match.group(1))

                # Hvis player_count er 0 → behold gammel verdi om den finnes
                if player_count == 0 and title in old_games:
                    player_count = old_games[title].get("player_count", 0)

                previous_count = old_games.get(title, {}).get("player_count", 0)

                # Sjekk om dette spillet har endret seg
                if player_count != previous_count:
                    any_changed = True

                # Beregn VM-er, kostnader osv
                strategy = GAME_SCALING_METHODS.get(title, DEFAULT_SCALING)
                scaling_func = get_scaling_function(strategy)

                if strategy == "trend":
                    vm_count = scaling_func(player_count, previous_count)
                elif strategy == "predictive":
                    now = datetime.now(ZoneInfo("Europe/Oslo"))
                    current_day = now.strftime("%A").lower()
                    current_hour = int(now.hour)
                    current_minute = f"{(now.minute // 5) * 5:02d}"
                    current_vms = old_games.get(title, {}).get("vm_count", 1)

                    # Juster time -6 timer for historiske data
                    adjusted_hour = (current_hour - 6) % 24
                    adjusted_hour_str = f"{adjusted_hour:02d}"

                    # Hent forventet spillerantall basert på justert time
                    previous_expected = get_expected_players(current_day, adjusted_hour_str, current_minute)
                    previous_actual = old_games.get(title, {}).get("player_count")

                    vm_count, corrected_future, previous_scaling = scaling_func(
                        current_day, f"{current_hour:02d}", current_minute,
                        player_count, current_vms
                    )



                else:
                    vm_count = scaling_func(player_count)

                hourly_cost = HOURLY_PRICE * vm_count
                daily_cost = hourly_cost * 24

                games.append({
                    "name": title,
                    "developer": FILTER_VALUE,
                    "player_count": player_count,
                    "expected_players": corrected_future,
                    "previous_scaling": previous_scaling,
                    "vm_count": vm_count,
                    "scaling_strategy": strategy,
                    "vms": [],
                    "hourly_cost": hourly_cost,
                    "daily_cost": daily_cost,
                    "last_updated": start_time.isoformat() + "Z"
                })

    # --- Only write if any game changed ---
    if any_changed:
        data = {"games": games}
        with open(OUTPUT_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\n✅ Oppdatert alle spill i {OUTPUT_FILE}")
    else:
        print("\nℹ️ Ingen endringer – beholdt eksisterende fil uendret")


    next_run = start_time + timedelta(seconds=UPDATE_INTERVAL)
    print(f"⏱ Neste oppdatering klokken {next_run.strftime('%Y-%m-%d %H:%M:%S')} (Norsk tid)")



    print(f"\n✅ Wrote {len(games)} games to {OUTPUT_FILE}")

    next_run = start_time + timedelta(seconds=UPDATE_INTERVAL)
    print(f"⏱ Neste oppdatering klokken {next_run.strftime('%Y-%m-%d %H:%M:%S')} (Norsk tid)")
