import openstack
from datetime import datetime, timezone
import math
import time
from config import (
    HOURLY_PRICE, PLAYERS_PER_VM, MAX_VMS,
    OS_AUTH_TYPE, OS_AUTH_URL, OS_APPLICATION_CREDENTIAL_ID,
    OS_APPLICATION_CREDENTIAL_SECRET, OS_REGION_NAME, OS_INTERFACE
)

def connect():
    """
    Oppretter forbindelse til OpenStack med credentials fra config.py
    """
    conn = openstack.connect(
        auth_type=OS_AUTH_TYPE,
        auth_url=OS_AUTH_URL,
        application_credential_id=OS_APPLICATION_CREDENTIAL_ID,
        application_credential_secret=OS_APPLICATION_CREDENTIAL_SECRET,
        region_name=OS_REGION_NAME,
        interface=OS_INTERFACE
    )
    return conn

def list_servers(conn):
    """
    Henter info om alle servere og returnerer en struktur med relevant info:
    - name
    - status
    - launched_at (datetime)
    - uptime (timedelta)
    - paid_hours
    - cost
    """
    servers_info = []

    for server in conn.compute.servers():
        if not server.launched_at:
            servers_info.append({
                "name": server.name,
                "status": server.status,
                "launched_at": None,
                "uptime": None,
                "paid_hours": 0,
                "cost": 0
            })
            continue

        try:
            started_at = datetime.fromisoformat(server.launched_at.replace("Z", "+00:00"))
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
        except Exception:
            servers_info.append({
                "name": server.name,
                "status": server.status,
                "launched_at": None,
                "uptime": None,
                "paid_hours": 0,
                "cost": 0
            })
            continue

        uptime = datetime.now(timezone.utc) - started_at
        paid_hours = math.ceil(uptime.total_seconds() / 3600)
        cost = paid_hours * HOURLY_PRICE

        servers_info.append({
            "name": server.name,
            "status": server.status,
            "launched_at": started_at,
            "uptime": uptime,
            "paid_hours": paid_hours,
            "cost": cost
        })
    return servers_info

def start_vm(vm_name, conn):
    """
    Starter en VM og venter til den er operativ.
    """
    # TODO: implementer faktisk API-kall
    operational = False
    while not operational:
        status = "ACTIVE"  # placeholder
        if status == "ACTIVE":
            operational = True
        else:
            time.sleep(1)
    return True

def stop_vm(vm_name, conn):
    """
    Stopper en VM og venter til den er stoppet.
    """
    # TODO: implementer faktisk API-kall
    stopped = False
    while not stopped:
        status = "SHUTOFF"  # placeholder
        if status == "SHUTOFF":
            stopped = True
        else:
            time.sleep(1)
    return True


def calculate_vm_count(player_count, players_per_vm=PLAYERS_PER_VM, max_vms=MAX_VMS):
    """
    Beregner antall VMer basert på antall spillere.
    """
    required_vms = max(1, (player_count + players_per_vm - 1) // players_per_vm)
    return min(required_vms, max_vms)




def print_servers(servers_info):
    """
    Printer info om servere i en tabell-lignende stil.
    """
    print("\n=== OpenStack VM Status ===")
    print(f"{'Name':25} {'Status':10} {'Uptime':15} {'Hours':>5} {'Cost($)':>7} {'Launched At':20}")
    print("-" * 90)
    
    for s in servers_info:
        name = s["name"][:25]
        status = s["status"]
        uptime = str(s["uptime"]).split(".")[0] if s["uptime"] else "-"
        paid_hours = s["paid_hours"]
        cost = f"{s['cost']:.2f}"
        launched_at = s["launched_at"].strftime("%Y-%m-%d %H:%M:%S") if s["launched_at"] else "-"
        
        print(f"{name:25} {status:10} {uptime:15} {paid_hours:5} {cost:7} {launched_at:20}")
    print("-" * 90)


def recommend_shutdown(servers_info, min_uptime_for_shutdown=50):
    """
    Lager en liste over VMer sortert etter hvor nærme de er neste hele time.
    Marker hvilke som kan shuttes ned.
    
    Args:
        servers_info: Liste med serverdata fra list_servers()
        min_uptime_for_shutdown: Minimum minutter over hele timer før shutdown kan vurderes
    
    Returns:
        List med dicts: name, uptime, minutes_to_next_hour, recommend_shutdown
    """
    recommendations = []

    for s in servers_info:
        if not s["uptime"]:
            # Ignorer servere uten uptime info
            continue

        total_minutes = s["uptime"].total_seconds() / 60
        minutes_past_hour = total_minutes % 60
        minutes_to_next_hour = 60 - minutes_past_hour

        # Kan shuttes ned hvis den har vært oppe mer enn min_uptime_for_shutdown minutter over hele timer
        can_shutdown = minutes_past_hour >= min_uptime_for_shutdown

        recommendations.append({
            "name": s["name"],
            "uptime": s["uptime"],
            "minutes_to_next_hour": minutes_to_next_hour,
            "minutes_past_hour": minutes_past_hour,
            "recommend_shutdown": can_shutdown
        })

    # Sorter etter hvor nærme neste hele time (minimale minutter_to_next_hour først)
    recommendations.sort(key=lambda x: x["minutes_to_next_hour"])
    
    # Print tabell
    print(f"\n{'Name':25} {'Uptime':15} {'Past min':>9} {'To next hour':>13} {'Shutdown?':>10}")
    print("-"*75)
    for r in recommendations:
        uptime_str = str(r["uptime"]).split(".")[0]
        shutdown_str = "YES" if r["recommend_shutdown"] else "NO"
        print(f"{r['name']:25} {uptime_str:15} {r['minutes_past_hour']:9.0f} {r['minutes_to_next_hour']:13.0f} {shutdown_str:>10}")
    print("-"*75)

    return recommendations
