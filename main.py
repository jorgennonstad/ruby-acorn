import time
from config import UPDATE_INTERVAL
from openstack_utils import connect, list_servers, print_servers, recommend_shutdown
from metrics_fetcher import fetch_and_write_metrics

def main():
    conn = connect()
    servers = list_servers(conn)
    recommendations = recommend_shutdown(servers, min_uptime_for_shutdown=50)




    while True:
        fetch_and_write_metrics()
        time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    main()
