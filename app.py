import os
import requests
from flask import Flask, render_template, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

VSPC_HOST = os.getenv("VSPC_HOST", "").rstrip("/")
VSPC_API_VERSION = os.getenv("VSPC_API_VERSION", "v3")
VSPC_USERNAME = os.getenv("VSPC_USERNAME")
VSPC_PASSWORD = os.getenv("VSPC_PASSWORD")
VSPC_VERIFY_SSL = os.getenv("VSPC_VERIFY_SSL", "true").lower() != "false"

BASE_URL = f"{VSPC_HOST}/api/{VSPC_API_VERSION}"


def get_token():
    resp = requests.post(
        f"{BASE_URL}/token",
        data={"grant_type": "password", "username": VSPC_USERNAME, "password": VSPC_PASSWORD},
        headers={"X-Client-Version": "3.6.2"},
        verify=VSPC_VERIFY_SSL,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_all(token, path):
    headers = {"Authorization": f"Bearer {token}", "X-Client-Version": "3.6.2"}
    results = []
    offset = 0
    limit = 500
    while True:
        resp = requests.get(
            f"{BASE_URL}{path}",
            params={"limit": limit, "offset": offset},
            headers=headers,
            verify=VSPC_VERIFY_SSL,
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        page = body.get("data", [])
        results.extend(page)
        meta = body.get("meta", {})
        total = meta.get("pagingInfo", {}).get("total", len(results))
        if len(results) >= total or not page:
            break
        offset += limit
    return results


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    try:
        token = get_token()
        alarms = fetch_all(token, "/alarms/active")
        organizations = fetch_all(token, "/organizations")
        org_map = {o["instanceUid"]: o for o in organizations}
        all_jobs = fetch_all(token, "/infrastructure/backupServers/jobs")
        failed_jobs = [j for j in all_jobs if j.get("status") in ("Failed", "Warning")]
        return jsonify({
            "alarms": alarms,
            "organizations": organizations,
            "org_map": org_map,
            "failed_jobs": failed_jobs,
        })
    except requests.HTTPError as e:
        return jsonify({"error": f"HTTP {e.response.status_code}: {e.response.text}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)
