# scaling_algorithms.py
import json
import os
from datetime import datetime
from config import PLAYERS_PER_VM, LOG_FILE

def calculate_vm_count(player_count: int, threshold_percent: float) -> int:
    """Generic VM calculation based on threshold_percent remaining."""
    vm_count = max(1, (player_count + PLAYERS_PER_VM - 1) // PLAYERS_PER_VM)  # ceil division
    remaining_capacity_percent = 100 - (player_count / (vm_count * PLAYERS_PER_VM) * 100)
    
    if remaining_capacity_percent <= threshold_percent:
        vm_count += 1
    return vm_count

def calculate_aggressive(player_count: int) -> int:
    """Aggressive: scale when 10% remaining."""
    return calculate_vm_count(player_count, threshold_percent=10)

def calculate_normal(player_count: int) -> int:
    """Normal: scale when 5% remaining."""
    return calculate_vm_count(player_count, threshold_percent=5)

def calculate_passive(player_count: int) -> int:
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


# --- trend_based.py ---

def calculate_trend_vm_count(
    current_count: int,
    previous_count: int,
    current_vms: int = None,
    min_vms: int = 1,
    aggressive_threshold: float = 0.5,  # prosent av én VM
    PLAYERS_PER_VM: int = 500,
) -> int:
    """
    Trend + kapasitet-basert skalering:
    - Vurderer hvor mange spillere endringen tilsvarer i forhold til VM-kapasitet.
    - Små endringer under en viss prosent av én VM ignoreres (for å unngå støy).
    - Store endringer over flere VM-kapasiteter skalerer mer aggressivt.
    """

    if previous_count is None:
        previous_count = current_count

    if current_vms is None:
        current_vms = max(min_vms, (current_count + PLAYERS_PER_VM - 1) // PLAYERS_PER_VM)

    # Beregn endring
    diff = current_count - previous_count
    change_percent = ((diff) / previous_count * 100) if previous_count > 0 else 0

    # Hvor mye kapasitet er brukt
    capacity_percent_used = (current_count / (current_vms * PLAYERS_PER_VM)) * 100

    # Hvor mange "VM-er" utgjør endringen
    vm_equiv_change = diff / PLAYERS_PER_VM

    new_vms = current_vms
    decision = "ingen endring"

    # --- Skalering basert på VM-ekvivalent endring ---
    if vm_equiv_change >= aggressive_threshold:
        # Økning tilsvarer minst 0.5 VM → skaler raskere
        add_vms = int(round(vm_equiv_change))
        new_vms += max(1, add_vms)
        decision = f"⚡ Skalerer opp (+{max(1, add_vms)} VM)"
    elif vm_equiv_change <= -aggressive_threshold and capacity_percent_used < 60:
        # Nedgang tilsvarer minst 0.5 VM, og lav utnyttelse
        remove_vms = int(round(abs(vm_equiv_change)))
        new_vms = max(min_vms, new_vms - max(1, remove_vms))
        decision = f"🧊 Skalerer ned (-{max(1, remove_vms)} VM)"

    # --- Sikring mot over/underkapasitet ---
    if capacity_percent_used > 95:
        new_vms += 1
        decision = "🚨 Nød-skalering opp (+1 VM)"
    elif capacity_percent_used < 35 and new_vms > min_vms:
        new_vms -= 1
        decision = "🌙 Lav utnyttelse (-1 VM)"

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
    PLAYERS_PER_VM: int = 500,
    scale_up_threshold: float = 0.9,   # 90% full
    scale_down_threshold: float = 0.5  # 50% full
):
    """
    Predictive scaling med sikkerhetsmarginer.
    - Skalerer opp når forventet bruk > scale_up_threshold * kapasitet
    - Skalerer ikke ned før faktisk bruk er under scale_down_threshold
    - Aldri skaler ned basert på forventet nedgang før den faktisk skjer
    """

    print("\n───────────────────────────────")
    print("🧠  STARTER PREDICTIVE SCALING (nå-basert)")
    print("───────────────────────────────")
    print(f"📅 Dag: {current_day}, 🕓 Tidspunkt: {current_hour}:{current_minute}")
    print(f"👥 Spillere nå: {current_player_count}")
    print(f"🖥️ Aktive VMs nå: {current_vms}")

    adjusted_hour = (int(current_hour) + time_offset_hours) % 24
    adjusted_hour_str = f"{adjusted_hour:02d}"
    print(f"🕕 Bruker mønsterdata for time: {adjusted_hour_str}")

    # Hent forventet spillerantall for nå
    expected_now = get_expected_players(current_day, adjusted_hour_str, current_minute)
    if expected_now is None or expected_now <= 0:
        print("⚠️ Ingen historisk data for nåværende tidspunkt — ingen endring.")
        return current_vms, None, 0.0

    deviation_now = (current_player_count - expected_now) / expected_now
    print(f"📊 Forventet nå: {expected_now:.0f}")
    print(f"📏 Avvik nå: {(deviation_now * 100):+.1f}%")

    # Neste forventning (lookahead)
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

    corrected_future = expected_next * (1 + deviation_now)
    print(f"📈 Neste forventet: {expected_next:.0f}")
    print(f"🧮 Korrigert neste: {corrected_future:.0f}")

    # --- Kapasitetsberegning ---
    capacity_now = current_vms * PLAYERS_PER_VM
    avg_load_per_vm = current_player_count / current_vms
    utilization = current_player_count / capacity_now

    print(f"⚙️  Nåværende total utnyttelse: {utilization*100:.1f}% (kapasitet {capacity_now} spillere)")
    print(f"📦 Gjennomsnittlig last per VM: {avg_load_per_vm:.1f}/{PLAYERS_PER_VM} spillere")

    required_vms = current_vms  # default: ingen endring

    # --- Per-VM basert skalering opp basert på siste VM ---
    players_in_last_vm = current_player_count % PLAYERS_PER_VM
    if players_in_last_vm == 0:
        players_in_last_vm = PLAYERS_PER_VM  # siste VM er full

    remaining_capacity_last_vm = PLAYERS_PER_VM - players_in_last_vm
    per_vm_remaining_threshold = 100  # skaler når mindre enn 100 spillere igjen på siste VM

    print(f"📦 Ledig kapasitet siste VM: {remaining_capacity_last_vm} spillere")

    if remaining_capacity_last_vm <= per_vm_remaining_threshold:
        required_vms = current_vms + 1
        print(f"⬆️  Skalerer OPP: siste VM nærmer seg full (≤{per_vm_remaining_threshold} spillere igjen)")



    # --- Backup: fremtidsbasert oppskalering ---
    elif corrected_future > capacity_now * scale_up_threshold:
        base_vms = int((corrected_future + PLAYERS_PER_VM - 1) // PLAYERS_PER_VM)
        required_vms = max(current_vms + 1, base_vms)
        print(f"⬆️  Skalerer OPP (framtid): forventet {corrected_future:.0f} spillere > {scale_up_threshold*100:.0f}% terskel")

    # --- Ingen skalering opp ---
    else:
        print("⚖️  Ingen skalering opp nødvendig akkurat nå.")

    # --- Skalering ned (separer med egen if) ---
    if utilization < scale_down_threshold:
        target_vms = int((current_player_count + PLAYERS_PER_VM - 1) // PLAYERS_PER_VM)
        if target_vms < required_vms:
            required_vms = target_vms
            print(f"⬇️  Skalerer NED: faktisk bruk {utilization*100:.1f}% < {scale_down_threshold*100:.0f}% terskel")
        else:
            print("ℹ️  Nedskalering vurdert men ikke nødvendig.")


    # --- Logg endringen ---
    log_vm_change(
        game_name="CounterStrike",
        current_day=current_day,
        current_hour=current_hour,
        current_minute=current_minute,
        current_players=current_player_count,
        expected_now=expected_now,
        deviation_now=deviation_now,
        expected_next=expected_next,
        corrected_future=corrected_future,
        required_vms=required_vms
    )

    print(f"💡 Foreslått VM-antall: {required_vms}")
    print("───────────────────────────────\n")
    return required_vms, corrected_future, deviation_now
