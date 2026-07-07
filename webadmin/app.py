#!/usr/bin/env python3
"""Flask management website for the Raspberry Pi Adhan clock.

Lets you edit location/method, volumes, Friday Surah Baqarah, upload/manage
adhan mp3s, control the random pool, preview audio, and re-install the cron
schedule -- all from a browser on your home network.

Run:
    cd webadmin
    pip3 install -r requirements.txt
    python3 app.py            # serves on http://0.0.0.0:8080

Password: set in settings.ini under [ADMIN] password (default "adhan").
"""

import os
import subprocess
import sys
from functools import wraps
from os.path import abspath, dirname, exists, join as pathjoin

from flask import (
    Flask, Response, jsonify, request, send_from_directory, render_template,
)
from werkzeug.utils import secure_filename

# Make the shared config module importable regardless of CWD.
ROOT_DIR = dirname(dirname(abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
import adhan_config as cfg  # noqa: E402

app = Flask(__name__, template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB per upload

UPDATE_SCRIPT = pathjoin(ROOT_DIR, "updateAzaanTimers.py")


# ---------------------------------------------------------------------------
# Auth (HTTP Basic against the password in settings.ini)
# ---------------------------------------------------------------------------

def check_auth(username, password):
    settings = cfg.load_settings()
    return username == settings["admin_username"] and password == settings["admin_password"]


def requires_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response(
                "Login required", 401,
                {"WWW-Authenticate": 'Basic realm="Adhan Admin"'},
            )
        return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
@requires_auth
def index():
    return render_template("admin.html")


# ---------------------------------------------------------------------------
# Settings API
# ---------------------------------------------------------------------------

@app.route("/api/settings", methods=["GET"])
@requires_auth
def get_settings():
    settings = cfg.load_settings()
    settings.pop("admin_username", None)  # never expose credentials
    settings.pop("admin_password", None)
    return jsonify({"settings": settings, "methods": cfg.CALC_METHODS})


@app.route("/api/settings", methods=["POST"])
@requires_auth
def post_settings():
    data = request.get_json(force=True, silent=True) or {}
    updates = {}

    if "lat" in data:
        try:
            updates["lat"] = float(data["lat"])
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid latitude"}), 400
    if "lon" in data:
        try:
            updates["lon"] = float(data["lon"])
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid longitude"}), 400
    if "method" in data:
        if data["method"] not in cfg.CALC_METHODS:
            return jsonify({"error": "Unknown calculation method"}), 400
        updates["method"] = data["method"]

    for key in ("default_azaan_vol", "fajr_azaan_vol", "surah_vol"):
        if key in data:
            try:
                vol = int(data[key])
            except (TypeError, ValueError):
                return jsonify({"error": f"Invalid value for {key}"}), 400
            updates[key] = max(0, min(130, vol))  # mpv sane range

    if "play_surah_baqarah" in data:
        updates["play_surah_baqarah"] = bool(data["play_surah_baqarah"])

    if "audio_device" in data and str(data["audio_device"]).strip():
        updates["audio_device"] = str(data["audio_device"]).strip()

    if isinstance(data.get("prayers"), dict):
        updates["prayers"] = {
            k: bool(v) for k, v in data["prayers"].items() if k in cfg.PRAYER_NAMES
        }

    saved = cfg.save_settings(updates)
    saved.pop("admin_username", None)
    saved.pop("admin_password", None)
    return jsonify({"settings": saved, "ok": True})


# ---------------------------------------------------------------------------
# Adhan pool API
# ---------------------------------------------------------------------------

@app.route("/api/adhans", methods=["GET"])
@requires_auth
def get_adhans():
    pool = cfg.load_pool()
    items = []
    for name, meta in pool.items():
        path = pathjoin(cfg.MEDIA_DIR, name)
        items.append({
            "name": name,
            "enabled": meta["enabled"],
            "category": meta["category"],
            "size_mb": round(os.path.getsize(path) / (1024 * 1024), 2) if exists(path) else 0,
        })
    return jsonify({"adhans": items})


@app.route("/api/adhans", methods=["POST"])
@requires_auth
def update_adhans():
    """Update pool metadata: {"name": {"enabled": bool, "category": "fajr|regular"}}."""
    data = request.get_json(force=True, silent=True) or {}
    pool = cfg.load_pool()
    for name, meta in data.items():
        if name not in pool:
            continue
        if "enabled" in meta:
            pool[name]["enabled"] = bool(meta["enabled"])
        if meta.get("category") in ("fajr", "regular"):
            pool[name]["category"] = meta["category"]
    saved = cfg.save_pool(pool)
    return jsonify({"ok": True, "pool": saved})


@app.route("/api/adhans/upload", methods=["POST"])
@requires_auth
def upload_adhan():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400
    if not file.filename.lower().endswith(".mp3"):
        return jsonify({"error": "Only .mp3 files are allowed"}), 400

    # Force the "Adhan" prefix so the file is picked up by the pool.
    name = secure_filename(file.filename)
    if not name.lower().startswith("adhan"):
        name = "Adhan-" + name
    dest = pathjoin(cfg.MEDIA_DIR, name)
    file.save(dest)

    # Register in the pool with a category guessed from the name.
    pool = cfg.load_pool()
    cfg.save_pool(pool)  # load_pool() already added the new file with defaults
    return jsonify({"ok": True, "name": name})


@app.route("/api/adhans/<path:name>", methods=["DELETE"])
@requires_auth
def delete_adhan(name):
    name = secure_filename(name)
    if name not in cfg.list_media_adhans():
        return jsonify({"error": "Not found"}), 404
    if len(cfg.list_media_adhans()) <= 1:
        return jsonify({"error": "Cannot delete the last adhan"}), 400
    try:
        os.remove(pathjoin(cfg.MEDIA_DIR, name))
    except OSError as exc:
        return jsonify({"error": str(exc)}), 500
    cfg.save_pool(cfg.load_pool())  # prune from adhans.json
    return jsonify({"ok": True})


@app.route("/media/<path:name>")
@requires_auth
def media(name):
    """Stream a media file for in-browser preview."""
    return send_from_directory(cfg.MEDIA_DIR, secure_filename(name))


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@app.route("/api/apply", methods=["POST"])
@requires_auth
def apply_cron():
    """Re-run updateAzaanTimers.py to recompute times and reinstall cron."""
    try:
        result = subprocess.run(
            ["python3", UPDATE_SCRIPT],
            cwd=ROOT_DIR, capture_output=True, text=True, timeout=120,
        )
        return jsonify({
            "ok": result.returncode == 0,
            "output": (result.stdout + result.stderr)[-4000:],
        })
    except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
        return jsonify({"ok": False, "output": str(exc)}), 500


@app.route("/api/play", methods=["POST"])
@requires_auth
def play_test():
    """Fire a test adhan on the Pi's speakers (fajr | regular | surah)."""
    data = request.get_json(force=True, silent=True) or {}
    prayer = data.get("prayer", "regular")
    if prayer not in ("fajr", "regular", "surah"):
        return jsonify({"error": "Invalid prayer"}), 400
    try:
        subprocess.Popen(
            ["python3", pathjoin(ROOT_DIR, "play_adhan.py"), prayer],
            cwd=ROOT_DIR,
        )
        return jsonify({"ok": True})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/stop", methods=["POST"])
@requires_auth
def stop_playback():
    """Stop any adhan/dua currently playing on the Pi's speakers."""
    # pkill returns exit code 1 when nothing matched; that's not an error here.
    subprocess.run(["pkill", "-f", "play_adhan.py"])
    subprocess.run(["pkill", "mpv"])
    return jsonify({"ok": True})


@app.route("/api/times", methods=["GET"])
@requires_auth
def prayer_times():
    """Return today's computed prayer times as a quick sanity check."""
    try:
        result = subprocess.run(
            ["python3", UPDATE_SCRIPT, "--dry-run"],
            cwd=ROOT_DIR, capture_output=True, text=True, timeout=60,
        )
        return jsonify({"ok": True, "output": result.stdout})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "output": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("ADHAN_ADMIN_PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
