# openstack_utils.py
import openstack
import time
from openstack import exceptions
from datetime import datetime, timezone
import math
from config import (
    HOURLY_PRICE, IMAGE_ID, FLAVOR_ID, NETWORK_ID,
    KEYPAIR_NAME, SECURITY_GROUP,
    OS_AUTH_TYPE, OS_AUTH_URL, OS_APPLICATION_CREDENTIAL_ID,
    OS_APPLICATION_CREDENTIAL_SECRET, OS_REGION_NAME, OS_INTERFACE, MIN_MINUTES_TO_NEXT_HOUR_FOR_SHUTDOWN
)


def connect():
    """
    Connect to OpenStack using credentials from config.py
    """
    try:
        conn = openstack.connect(
            auth_type=OS_AUTH_TYPE,
            auth_url=OS_AUTH_URL,
            application_credential_id=OS_APPLICATION_CREDENTIAL_ID,
            application_credential_secret=OS_APPLICATION_CREDENTIAL_SECRET,
            region_name=OS_REGION_NAME,
            interface=OS_INTERFACE
        )
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to OpenStack: {e}")
        return None


def list_servers(conn):
    """
    List all VMs excluding manager and return info:
    - name
    - status
    - launched_at
    - uptime (timedelta)
    - paid_hours
    - cost
    """
    servers_info = []
    for server in conn.compute.servers():
        if "manager" in server.name.lower():
            continue

        # Handle missing launch info
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


def recommend_shutdown(servers_info):
    """
    Return VMs sorted by who is closest to next full hour.
    Marks which VMs are eligible for shutdown.
    Prints debug info showing uptime and recommendation.
    """

    recommendations = []
    for s in servers_info:
        if not s["uptime"]:
            continue
        total_minutes = s["uptime"].total_seconds() / 60
        minutes_past_hour = total_minutes % 60
        minutes_to_next_hour = 60 - minutes_past_hour
        can_shutdown = minutes_to_next_hour <= MIN_MINUTES_TO_NEXT_HOUR_FOR_SHUTDOWN

        recommendations.append({
            "name": s["name"],
            "uptime": s["uptime"],
            "minutes_to_next_hour": minutes_to_next_hour,
            "minutes_past_hour": minutes_past_hour,
            "recommend_shutdown": can_shutdown
        })

    # Sort by minutes to next hour (ascending)
    recommendations.sort(key=lambda x: x["minutes_to_next_hour"])

    # --- DEBUG PRINT ---
    print("\n🛠 Shutdown recommendations (for debugging, not deleting):")
    print(f"{'VM Name':25} {'Uptime':20} {'Past min':10} {'To next hour':13} {'Shutdown?':10}")
    print("-" * 85)
    for r in recommendations:
        uptime_str = str(r["uptime"]).split(".")[0]
        shutdown_str = "YES" if r["recommend_shutdown"] else "NO"
        print(f"{r['name']:25} {uptime_str:20} {r['minutes_past_hour']:10.0f} {r['minutes_to_next_hour']:13.0f} {shutdown_str:>10}")
    print("-" * 85)

    return recommendations



def start_vms(conn, count, base_name="GameVM"):
    """
    Start `count` VMs and generate names automatically.
    Returns list of started VM names.
    """
    started = []
    for i in range(count):
        vm_name = f"{base_name}-{int(time.time())}-{i}"
        try:
            server = conn.compute.create_server(
                name=vm_name,
                image_id=IMAGE_ID,
                flavor_id=FLAVOR_ID,
                networks=[{"uuid": NETWORK_ID}],
                key_name=KEYPAIR_NAME,
                security_groups=[{"name": SECURITY_GROUP}]
            )
            conn.compute.wait_for_server(server, status="ACTIVE", failures=["ERROR"], interval=5, wait=300)
            print(f"✅ VM '{vm_name}' started")
            started.append(vm_name)
        except exceptions.ForbiddenException as e:
            print(f"⚠️ Quota exceeded or permission denied for '{vm_name}': {e}")
        except exceptions.HttpException as e:
            print(f"❌ HTTP error while starting '{vm_name}': {e}")
        except Exception as e:
            print(f"❌ Unexpected error while starting '{vm_name}': {e}")
    return started


def stop_vms(conn, count):
    """
    Delete up to `count` VMs using recommendations.
    Never deletes manager VM.
    Returns list of deleted VM names.
    """

    all_vms = list_servers(conn)
    game_vms = [vm for vm in all_vms if "manager" not in vm["name"].lower()]
    if not game_vms or count <= 0:
        return []

    recs = recommend_shutdown(game_vms)
    candidates = [r for r in recs if r["recommend_shutdown"]]
    print(f"🛠 VMs recommended for deletion: {[r['name'] for r in candidates]}")

    if not candidates:
        print("ℹ️ No VMs eligible for deletion")
        return []

    to_delete = candidates[:count]
    deleted = []

    for r in to_delete:
        name = r["name"]
        server = conn.compute.find_server(name)
        if not server:
            print(f"⚠️ VM '{name}' not found, skipping")
            continue

        if "manager" in server.name.lower():
            print(f"⚙️ Skipping manager VM '{name}'")
            continue

        try:
            print(f"🗑 Deleting VM '{name}'...")
            conn.compute.delete_server(server)
            # Wait until server disappears
            for _ in range(60):  # max 5 minutes
                if not conn.compute.find_server(name):
                    print(f"✅ VM '{name}' deleted")
                    deleted.append(name)
                    break
                time.sleep(5)
            else:
                print(f"⚠️ Timeout waiting for VM '{name}' to be deleted")
        except Exception as e:
            print(f"❌ Failed to delete VM '{name}': {e}")

    return deleted



def count_vms(conn):
    """
    Return number of game VMs (excluding manager)
    """
    all_vms = list_servers(conn)
    game_vms = [vm for vm in all_vms if "manager" not in vm["name"].lower()]
    return len(game_vms)
