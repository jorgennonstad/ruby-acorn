import time
from config import UPDATE_INTERVAL
from openstack_utils import connect, list_servers, recommend_shutdown
from metrics_fetcher import fetch_and_write_metrics

def main():
    conn = connect()  # connect once at start

    while True:
        fetch_and_write_metrics(conn=conn)

        time.sleep(UPDATE_INTERVAL)


if __name__ == "__main__":
    main()
