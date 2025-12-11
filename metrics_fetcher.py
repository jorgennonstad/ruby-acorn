import requests
import re
import json
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from scaling_algorithms import get_scaling_function, get_expected_players
from openstack_utils import connect, list_servers, start_vms, stop_vms, count_vms
from config import (
    API_URL, FILTER_FIELD, FILTER_VALUE, UPDATE_INTERVAL,
    DATA_DIR, OUTPUT_FILE, GAME_SCALING_CONFIG, DEFAULT_SCALING_CONFIG,
    HOURLY_PRICE, TARGET_GAME
)


# Make sure data folder exists
os.makedirs(DATA_DIR, exist_ok=True)



def enforce_hourly_budget(vm_count: int, hourly_price: float, max_budget: float | None) -> int:
    """
    Checks if the VM count exceeds the hourly budget.
    If it does, returns the maximum VMs allowed within the budget.
    If no budget is set (None), returns the original vm_count.
    """
    if max_budget is None:
        return vm_count
    max_vms = max(1, int(max_budget // hourly_price))  # ensure at least 1 VM
    if vm_count > max_vms:
        print(f"⚠️ Hourly budget exceeded: {vm_count * hourly_price:.2f} > {max_budget:.2f}, "
              f"limiting to {max_vms} VM(s).")
        return max_vms
    return vm_count


def fetch_and_write_metrics(conn):
    # 🕓 Record when this run started
    start_time = datetime.now(ZoneInfo("Europe/Oslo"))

    # =========================================================
    # STEP 1 — Load existing JSON data (previous state)
    # =========================================================
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r") as f:
            try:
                old_data = json.load(f)
                # Convert games into a dictionary by name for easy lookup
                old_games = {g["name"]: g for g in old_data.get("games", [])}
            except json.JSONDecodeError:
                old_games = {}
    else:
        old_games = {}

    # =========================================================
    # STEP 2 — Fetch current metrics from API
    # =========================================================
    response = requests.get(API_URL)
    lines = response.text.splitlines()  # each line = 1 metric
    games = []                          # will hold all updated game data
    any_changed = False                 # track if anything actually changed

    # =========================================================
    # STEP 3 — Parse each metric line
    # =========================================================
    for line in lines:
        # Only include metrics for our chosen developer/filter
        if f'{FILTER_FIELD}="{FILTER_VALUE}"' not in line:
            continue

        # Extract game title and player count using regex
        title_match = re.search(r'title="([^"]+)"', line)
        count_match = re.search(r'\s(\d+)$', line)
        if not (title_match and count_match):
            continue

        title = title_match.group(1)
        player_count = int(count_match.group(1))

        # If player_count == 0, use previous value (to prevent resets)
        if player_count == 0 and title in old_games:
            player_count = old_games[title].get("player_count", 0)

        previous_count = old_games.get(title, {}).get("player_count", 0)

        # Check if player count actually changed
        if player_count != previous_count:
            any_changed = True

        # =========================================================
        # STEP 4 — Determine which scaling strategy to use
        # =========================================================
        game_conf = GAME_SCALING_CONFIG.get(title, DEFAULT_SCALING_CONFIG)

        strategy = game_conf.get("strategy", DEFAULT_SCALING_CONFIG["strategy"])
        time_offset_hours = game_conf.get("time_offset_hours", DEFAULT_SCALING_CONFIG["time_offset_hours"])
        lookahead_intervals = game_conf.get("lookahead_intervals", DEFAULT_SCALING_CONFIG["lookahead_intervals"])
        buffer = game_conf.get("buffer", DEFAULT_SCALING_CONFIG["buffer"])
        respect_current_load = game_conf.get("respect_current_load", False)  # 👈 nytt


        scaling_func = get_scaling_function(strategy)
        
        corrected_future = None  # used only for predictive

        # ---------------------------------------------------------
        # 🧠 PREDICTIVE — Uses expected player forecast + deviation
        # ---------------------------------------------------------
        if strategy == "predictive":
            now = datetime.now(ZoneInfo("Europe/Oslo"))
            current_day = now.strftime("%A").lower()
            current_hour = f"{now.hour:02d}"
            current_minute = f"{(now.minute // 5) * 5:02d}"
            current_vms = old_games.get(title, {}).get("vm_count", 1)

            # scaling_func = calculate_predictive_scaling(...)
            vm_count, corrected_future, _ = scaling_func(
                current_day, current_hour, current_minute,
                player_count, current_vms, buffer=buffer,  respect_current_load=respect_current_load,
            )

        # ---------------------------------------------------------
        # 📈 TREND — Reacts to recent change in player count
        # ---------------------------------------------------------
        elif strategy == "trend":
            current_vms = old_games.get(title, {}).get("vm_count", 1)

            vm_count = scaling_func(
                current_count=player_count,
                previous_count=previous_count,
                current_vms=current_vms,
                threshold_percent=game_conf.get("threshold_percent", 95.0),  # 👈 fetch from config
                respect_current_load=respect_current_load,
            )



        # ---------------------------------------------------------
        # ⚙️ NORMAL / PASSIVE / AGGRESSIVE — Static threshold rules
        # ---------------------------------------------------------
        else:
            vm_count = scaling_func(player_count) + buffer

        # =========================================================
        # STEP 5 — Calculate costs for this game
        # =========================================================
        max_budget = game_conf.get("max_hourly_budget", None)
        vm_count = enforce_hourly_budget(vm_count, HOURLY_PRICE, max_budget)
        hourly_cost = HOURLY_PRICE * vm_count
        daily_cost = hourly_cost * 24

        # =========================================================
        # STEP 6 — Manage actual OpenStack VMs (for target game only)
        # =========================================================
        if title == TARGET_GAME:
            if conn is None:
                raise ValueError("OpenStack connection required for target game management")

            # Get current VMs for this game
            current_vm_count = count_vms(conn)

            # Determine how many VMs to start or stop
            delta_vms = int(vm_count) - int(current_vm_count)

            if delta_vms > 0:
                # Scale up
                print(f"🟢 Scaling up: starting {delta_vms} VMs...")
                started = start_vms(conn, delta_vms, base_name=TARGET_GAME.replace(" ", ""))
                print(f"✅ Started VMs: {started}")

            elif delta_vms < 0:
                # Scale down
                to_stop = abs(delta_vms)
                print(f"🔴 Scaling down: stopping {to_stop} VMs...")
                stopped = stop_vms(conn, to_stop)
                print(f"✅ Stopped VMs: {stopped}")

            # Refresh VMs info after scaling
            all_vms = list_servers(conn)
            game_vms = [vm for vm in all_vms if "manager" not in vm["name"].lower()]
            vm_count = len(game_vms)

            # Collect VM info for JSON
            vms_info = [
                {
                    "name": vm["name"],
                    "status": vm["status"],
                    "uptime": str(vm["uptime"]).split(".")[0] if vm.get("uptime") else None,
                    "paid_hours": vm.get("paid_hours", 0),
                    "cost": vm.get("cost", 0)
                }
                for vm in game_vms
            ]


        # =========================================================
        # STEP 7 — Build entry for JSON output
        # =========================================================
        games.append({
            "name": title,
            "developer": FILTER_VALUE,
            "player_count": player_count,
            "expected_players": corrected_future if strategy == "predictive" else None,
            "vm_count": vm_count,
            "scaling_strategy": strategy,
            "vms": vms_info,
            "hourly_cost": hourly_cost,
            "daily_cost": daily_cost,
            "last_updated": start_time.isoformat() + "Z"
        })

    # =========================================================
    # STEP 8 — Write new data to JSON if something changed
    # =========================================================
    if any_changed:
        data = {"games": games}
        with open(OUTPUT_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\n✅ Oppdatert alle spill i {OUTPUT_FILE}")
    else:
        print("\nℹ️ Ingen endringer – beholdt eksisterende fil uendret")

    # =========================================================
    # STEP 9 — Print next scheduled update
    # =========================================================
    next_run = start_time + timedelta(seconds=UPDATE_INTERVAL)
    print(f"\n✅ Wrote {len(games)} games to {OUTPUT_FILE}")
    print(f"⏱ Neste oppdatering klokken {next_run.strftime('%Y-%m-%d %H:%M:%S')} (Norsk tid)")
