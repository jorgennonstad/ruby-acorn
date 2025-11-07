import json
from flask import Flask, Response
import os

app = Flask(__name__)
DATA_FILE = "data/games.json"


def generate_prometheus_metrics():
    if not os.path.exists(DATA_FILE):
        return ""

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    lines = []

    for game in data.get("games", []):
        # Labels: stable string fields only
        labels = {k: v for k, v in game.items() if isinstance(v, str) and k not in ["last_updated"]}
        label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())

        # Export numeric fields as Prometheus metrics
        for key, value in game.items():
            if isinstance(value, (int, float)):
                lines.append(f'game_{key}{{{label_str}}} {value}')

    return "\n".join(lines)


@app.route("/metrics")
def metrics():
    return Response(generate_prometheus_metrics(), mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
