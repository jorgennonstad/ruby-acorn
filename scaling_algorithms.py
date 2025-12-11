# scaling_algorithms.py
import json
import os
from datetime import datetime
from config import PLAYERS_PER_VM, LOG_FILE

def calculate_vm_count(player_count: int, threshold_percent: float) :
    """Generic VM calculation based on threshold_percent remaining."""
    vm_count = max(1, (player_count + PLAYERS_PER_VM - 1) // PLAYERS_PER_VM)  # ceil division
    remaining_capacity_percent = 100 - (player_count / (vm_count * PLAYERS_PER_VM) * 100)
    
    if remaining_capacity_percent <= threshold_percent:
        vm_count += 1
    return vm_count

def calculate_aggressive(player_count: int) :
    """Aggressive: scale when 10% remaining."""
    return calculate_vm_count(player_count, threshold_percent=10)

def calculate_normal(player_count: int) :
    """Normal: scale when 5% remaining."""
    return calculate_vm_count(player_count, threshold_percent=5)

def calculate_passive(player_count: int) :
    """Passive: scale when 2% remaining."""
    return calculate_vm_count(player_count, threshold_percent=2)

def get_scaling_function(strategy: str):
    mapping = {
        "normal": calculate_normal,
        "aggressive": calculate_aggressive,
        "passive": calculate_passive,
        "trend": calculate_trend_vm_count,
        "predictive": calculate_predictive_scaling
    }
    return mapping.get(strategy, calculate_normal)


# --- trend_based ---

def calculate_trend_vm_count(
    current_count: int,
    previous_count: int,
    current_vms: int = None,
    min_vms: int = 1,
    threshold_percent: float = 95.0,
    respect_current_load: bool = True,
) :

    print("\n───────────────────────────────")
    print("🧠 CALCULATE TREND VM COUNT DEBUG (v2)")
    print(f"📊 current_count: {current_count}, previous_count: {previous_count}, current_vms: {current_vms}")
    print(f"⚙ respect_current_load: {respect_current_load}, min_vms: {min_vms}, threshold%: {threshold_percent}")

    if current_vms is None:
        current_vms = max(min_vms, (current_count + PLAYERS_PER_VM - 1) // PLAYERS_PER_VM)
        print(f"ℹ️ current_vms var None → kalkulert: {current_vms}")

    # Predict
    diff = current_count - previous_count
    next_trend_count = current_count + diff
    print(f"📈 Predicted next count: {next_trend_count} (diff: {diff})")

    # Capacity calculation
    last_vm_capacity = int(PLAYERS_PER_VM * threshold_percent)
    safe_total_capacity = (current_vms - 1) * PLAYERS_PER_VM + last_vm_capacity
    print(f"📦 Safe capacity @ {current_vms} VMs: {safe_total_capacity} (last VM: {last_vm_capacity})")

    new_vms = current_vms
    decision = "ingen endring"

    # ---------------- SCALE UP ---------------- #
    if next_trend_count > safe_total_capacity:
        print("⚠️ Skal opp: predicted > safe capacity")

        extra_players = next_trend_count - ((current_vms - 1) * PLAYERS_PER_VM)
        needed_vms_est = current_vms - 1 + int(-(-extra_players // last_vm_capacity))
        new_vms = max(min_vms, needed_vms_est)

        print(f"🔄 Før sikkerhetsjekk: {new_vms} VMs ønsket")

        # Safety check loop
        while True:
            safe_cap_check = (new_vms - 1) * PLAYERS_PER_VM + last_vm_capacity
            print(f"  ➤ Sjekker {new_vms} VMs → {safe_cap_check} safe")

            if next_trend_count <= safe_cap_check:
                break
            print("  ❌ Ikke trygt → +1 VM")
            new_vms += 1

        decision = f"⚡ Oppskalering → {new_vms} VMs"

    # ---------------- SCALE DOWN ---------------- #
    elif next_trend_count < current_count:
        print("📉 Potensial for nedskalering")

        # Direct right-sizing using actual load
        ideal_vms = max(
            min_vms,
            int(-((current_count - last_vm_capacity) // -PLAYERS_PER_VM)) + 1
            if current_count > last_vm_capacity else 1
        )

        print(f"🧮 Beregnet ideell VMs for faktisk load: {ideal_vms}")

        if respect_current_load:
            safe_current_cap = (ideal_vms - 1) * PLAYERS_PER_VM + last_vm_capacity
            print(f"   🔐 Sikker sjekk mot threshold → {safe_current_cap}")

        if ideal_vms < current_vms:
            new_vms = ideal_vms
            decision = f"🧊 Nedskalering → {new_vms} VMs"

    # Final logging
    safe_final_cap = (new_vms - 1) * PLAYERS_PER_VM + last_vm_capacity
    print(f"🔥 Final VMs: {new_vms}, Safe capacity: {safe_final_cap}")
    print(f"➡️ Decision: {decision}")
    print("───────────────────────────────\n")

    return new_vms










# --- predictive_scaling ---
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

_last_logged = {}  # store last logged values per game/time

def log_vm_change(game_name, current_day, current_hour, current_minute,
                  current_players, expected_now, deviation_now,
                  expected_next, corrected_future, required_vms):
    """
    Logs predictive scaling calculations only when something changed.
    """
    global _last_logged
    timestamp = datetime.now().isoformat()

    # Build current state tuple
    current_state = (current_players, int(corrected_future), required_vms)

    # Key per game + time
    key = f"{game_name}_{current_day}_{current_hour}:{current_minute}"

    # Check if last logged state is the same
    if key in _last_logged and _last_logged[key] == current_state:
        return  # nothing changed, skip logging

    # Save current state for future checks
    _last_logged[key] = current_state

    # Format deviation
    deviation_percent = deviation_now * 100
    deviation_str = f"{deviation_percent:+.1f}%"

    line = (
        f"{timestamp} | {game_name} | {current_day} {current_hour}:{current_minute} | "
        f"Current: {current_players} | Expected Now: {expected_now} | "
        f"Deviation: {deviation_str} | Next Expected: {expected_next} | "
        f"Corrected Future: {corrected_future:.0f} | Calculated VMs: {required_vms}\n"
    )

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line)






# --- Last inn mønsterdata én gang ---
PLAYER_PATTERN_FILE = "data/player_pattern.json"
if os.path.exists(PLAYER_PATTERN_FILE):
    with open(PLAYER_PATTERN_FILE) as f:
        player_patterns = json.load(f)
else:
    player_patterns = []  # fallback

# --- Funksjon for å hente forventet spillerantall ---
def get_expected_players(day: str, hour: str, minute: str):
    for entry in player_patterns:
        if entry["day"] == day and entry["hour"] == hour and entry["minute"] == minute:
            return entry["avg_playercount"]
    return None


def calculate_predictive_scaling(
    current_day: str,
    current_hour: str,
    current_minute: str,
    current_player_count: int,
    current_vms: int,
    time_offset_hours: int = -6,
    lookahead_intervals: int = 3,
    PLAYERS_PER_VM: int = PLAYERS_PER_VM,
    buffer: int = 75,
    respect_current_load: bool = False,
):
    """
    Predictive scaling basert på nåværende avvik.
    - Sammenligner faktisk spillerantall med forventet (nå)
    - Beregner neste forventning justert med nåværende avvik (%)
    - Returnerer nytt VM-forslag og korrigert neste forventning
    """

    print("\n───────────────────────────────")
    print("🧠  STARTER PREDICTIVE SCALING (nå-basert)")
    print("───────────────────────────────")
    print(f"📅 Dag: {current_day}, 🕓 Tidspunkt: {current_hour}:{current_minute}")
    print(f"👥 Spillere nå: {current_player_count}")
    print(f"🖥️ Aktive VMs nå: {current_vms}")

    # Juster time for mønsterdata (timezone/historikk)
    adjusted_hour = (int(current_hour) + time_offset_hours) % 24
    adjusted_hour_str = f"{adjusted_hour:02d}"
    print(f"🕕 Bruker mønsterdata for time: {adjusted_hour_str}")

    # Hent forventet spillerantall for nå
    expected_now = get_expected_players(current_day, adjusted_hour_str, current_minute)
    if expected_now is None or expected_now <= 0:
        print("⚠️ Ingen historisk data for nåværende tidspunkt — ingen endring.")
        return current_vms, None, 0.0

    # Beregn prosentvis avvik nå
    deviation_now = (current_player_count - expected_now) / expected_now
    print(f"📊 Forventet nå: {expected_now:.0f}")
    print(f"📏 Avvik nå: {(deviation_now * 100):+.1f}%")

    # Finn neste forventning (lookahead)
    total_minutes_ahead = 5 * lookahead_intervals
    next_minute_total = int(current_minute) + total_minutes_ahead
    next_hour = (adjusted_hour + next_minute_total // 60) % 24
    next_minute = next_minute_total % 60
    next_hour_str = f"{next_hour:02d}"
    next_minute_str = f"{next_minute:02d}"

    expected_next = get_expected_players(current_day, next_hour_str, next_minute_str)
    if expected_next is None:
        print("⚠️ Ingen data for neste intervall — ingen endring.")
        return current_vms, None, deviation_now

    # Korriger neste forventning med nåværende avvik
    corrected_future = expected_next * (1 + deviation_now)
    print(f"📈 Neste forventet: {expected_next:.0f}")
    print(f"🧮 Korrigert neste: {corrected_future:.0f} (avvik {deviation_now*100:+.1f}%)")

    # --- Beregn nødvendige VMer basert på forecast og buffer ---
    required_vms = max(1, (corrected_future + PLAYERS_PER_VM - 1) // PLAYERS_PER_VM)

    players_on_last_vm = corrected_future % PLAYERS_PER_VM
    if players_on_last_vm == 0:
        players_on_last_vm = PLAYERS_PER_VM

    remaining_capacity = PLAYERS_PER_VM - players_on_last_vm

    print(f"📦 Forecast: {corrected_future} spillere, kapasitet på siste VM: {remaining_capacity}")

    if remaining_capacity < buffer:
        required_vms += 1
        print(f"⬆️ Skalerer opp: mindre enn {buffer} plasser igjen på siste VM")


     # --- 👇 Sikring mot underkapasitet (valgfritt) ---
    if respect_current_load:
        min_required = (current_player_count + PLAYERS_PER_VM - 1) // PLAYERS_PER_VM
        if required_vms < min_required:
            print(f"⚠️ Forhindrer nedskalering: behold {min_required} VMs (nåværende behov).")
            required_vms = min_required

    print(f"💡 Totalt foreslått VM-antall: {required_vms}")

    
    # Legg til logging:
    log_vm_change(
        game_name="CounterStrike",  # du må sende inn spillets navn til funksjonen
        current_day=current_day,
        current_hour=current_hour,
        current_minute=current_minute,
        current_players=current_player_count,
        expected_now=expected_now,
        expected_next=expected_next,
        required_vms=required_vms,
        corrected_future=corrected_future,
        deviation_now=deviation_now
    )


    print(f"💡 Foreslått VM-antall: {required_vms}")

    print("───────────────────────────────\n")
    return required_vms, corrected_future, deviation_now






