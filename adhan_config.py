#!/usr/bin/env python3
"""Shared configuration helpers for the Raspberry Pi Adhan clock.

This is the single source of truth for:
  - settings.ini    -> location, method, volumes, Friday surah, audio device, admin password
  - adhans.json     -> which adhan mp3s are in the random pool and their category (fajr/regular)

Used by play_adhan.py (play time), updateAzaanTimers.py (cron install) and
webadmin/app.py (the management website).

Volume note
-----------
Volumes are expressed as an mpv percentage (0-130), where 100 is normal.
This replaces the old behaviour where the mpv command hard-coded --volume=100
and the settings.ini volume values were read but never applied.
"""

import json
import os
import random
from configparser import ConfigParser
from os.path import abspath, dirname, exists, join as pathjoin

ROOT_DIR = dirname(abspath(__file__))
SETTINGS_PATH = pathjoin(ROOT_DIR, "settings.ini")
POOL_PATH = pathjoin(ROOT_DIR, "adhans.json")
MEDIA_DIR = pathjoin(ROOT_DIR, "media")
DISPLAY_CONFIG_PATH = pathjoin(ROOT_DIR, "adhan-display", "display_config.json")

DEFAULT_AUDIO_DEVICE = "alsa/plughw:1,0"
CALC_METHODS = ["MWL", "ISNA", "Egypt", "Makkah", "Karachi", "Tehran", "Jafari"]
ASR_METHODS = ["Standard", "Hanafi"]  # Standard = Shafi'i/Maliki/Hanbali; Hanafi = later Asr
PRAYER_NAMES = ["fajr", "dhuhr", "asr", "maghrib", "isha"]

# Reasonable defaults used when a key is missing from settings.ini.
_DEFAULTS = {
    "lat": 30.0,
    "lon": 30.0,
    "method": "MWL",
    "default_azaan_vol": 100,
    "fajr_azaan_vol": 100,
    "play_surah_baqarah": False,
    "surah_vol": 100,
    "audio_device": DEFAULT_AUDIO_DEVICE,
    "admin_username": "admin",
    "admin_password": "adhan",
    "fajr_angle": None,   # None = use the calculation method's default
    "isha_angle": None,   # None = use the calculation method's default
    "asr_method": "Standard",
}


def _to_bool(value, fallback=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return fallback
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _to_int(value, fallback):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def _to_float(value, fallback):
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _to_float_or_none(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_settings():
    """Read settings.ini into a plain dict with sane fallbacks."""
    config = ConfigParser()
    config.read(SETTINGS_PATH)

    def get(section, key, default=None):
        try:
            return config[section][key]
        except KeyError:
            return default

    return {
        "lat": _to_float(get("DEFAULT", "lat"), _DEFAULTS["lat"]),
        "lon": _to_float(get("DEFAULT", "lon"), _DEFAULTS["lon"]),
        "method": get("DEFAULT", "method", _DEFAULTS["method"]) or _DEFAULTS["method"],
        "default_azaan_vol": _to_int(get("VOLUME", "defaultAzaanVolume"), _DEFAULTS["default_azaan_vol"]),
        "fajr_azaan_vol": _to_int(get("VOLUME", "fajrAzaanVolume"), _DEFAULTS["fajr_azaan_vol"]),
        "play_surah_baqarah": _to_bool(get("FRIDAY", "playSurahBaqarah"), _DEFAULTS["play_surah_baqarah"]),
        "surah_vol": _to_int(get("FRIDAY", "surahVolume"), _DEFAULTS["surah_vol"]),
        "audio_device": get("AUDIO", "device", _DEFAULTS["audio_device"]) or _DEFAULTS["audio_device"],
        "admin_username": get("ADMIN", "username", _DEFAULTS["admin_username"]) or _DEFAULTS["admin_username"],
        "admin_password": get("ADMIN", "password", _DEFAULTS["admin_password"]) or _DEFAULTS["admin_password"],
        # Per-prayer sound toggle. Times still show on the display when muted;
        # only the adhan playback is skipped. Default: every prayer plays.
        "prayers": {p: _to_bool(get("PRAYERS", p), True) for p in PRAYER_NAMES},
        # Custom Fajr/Isha angles (None = method default) and Asr madhab.
        "fajr_angle": _to_float_or_none(get("CALC", "fajr_angle")),
        "isha_angle": _to_float_or_none(get("CALC", "isha_angle")),
        "asr_method": (get("CALC", "asr_method", _DEFAULTS["asr_method"]) or _DEFAULTS["asr_method"])
        if (get("CALC", "asr_method", _DEFAULTS["asr_method"]) or _DEFAULTS["asr_method"]) in ASR_METHODS
        else _DEFAULTS["asr_method"],
    }


def save_settings(values):
    """Persist a settings dict (as returned by load_settings) to settings.ini.

    Only known keys are written; missing keys keep their current/default value.
    Returns the merged settings dict that was written.
    """
    current = load_settings()

    # Merge the per-prayer toggle dict key-by-key so a partial update is fine.
    if isinstance(values.get("prayers"), dict):
        for name, on in values["prayers"].items():
            if name in current["prayers"]:
                current["prayers"][name] = bool(on)

    current.update({k: v for k, v in values.items() if k in current and k != "prayers"})

    config = ConfigParser()
    # Preserve any unrelated sections that might already exist.
    config.read(SETTINGS_PATH)

    config["DEFAULT"] = {
        "lat": str(current["lat"]),
        "lon": str(current["lon"]),
        "method": current["method"],
    }
    config["VOLUME"] = {
        "defaultAzaanVolume": str(current["default_azaan_vol"]),
        "fajrAzaanVolume": str(current["fajr_azaan_vol"]),
    }
    config["FRIDAY"] = {
        "playSurahBaqarah": str(current["play_surah_baqarah"]),
        "surahVolume": str(current["surah_vol"]),
    }
    config["AUDIO"] = {"device": current["audio_device"]}
    config["ADMIN"] = {
        "username": current["admin_username"],
        "password": current["admin_password"],
    }
    config["PRAYERS"] = {p: str(current["prayers"][p]) for p in PRAYER_NAMES}
    config["CALC"] = {
        "fajr_angle": "" if current["fajr_angle"] is None else str(current["fajr_angle"]),
        "isha_angle": "" if current["isha_angle"] is None else str(current["isha_angle"]),
        "asr_method": current["asr_method"],
    }

    with open(SETTINGS_PATH, "w") as fh:
        config.write(fh)

    write_display_config(current)
    return current


def write_display_config(settings=None):
    """Write the subset of settings the front-end display needs.

    This keeps the wall display and the audio scheduler in sync from one place.
    """
    if settings is None:
        settings = load_settings()
    payload = {
        "latitude": settings["lat"],
        "longitude": settings["lon"],
        "method": settings["method"],
        "fajr_angle": settings["fajr_angle"],
        "isha_angle": settings["isha_angle"],
        "asr_method": settings["asr_method"],
    }
    try:
        with open(DISPLAY_CONFIG_PATH, "w") as fh:
            json.dump(payload, fh, indent=2)
    except OSError:
        # Display folder may not exist in every deployment; not fatal.
        pass
    return payload


# ---------------------------------------------------------------------------
# Adhan pool (randomisation)
# ---------------------------------------------------------------------------

def list_media_adhans():
    """All 'Adhan*.mp3' files currently present in media/."""
    if not exists(MEDIA_DIR):
        return []
    return sorted(
        f for f in os.listdir(MEDIA_DIR)
        if f.startswith("Adhan") and f.lower().endswith(".mp3")
    )


def _default_category(filename):
    return "fajr" if "fajr" in filename.lower() else "regular"


def load_pool():
    """Return {filename: {enabled: bool, category: 'fajr'|'regular'}} for files
    that exist in media/. Files not yet in adhans.json get sensible defaults."""
    saved = {}
    if exists(POOL_PATH):
        try:
            with open(POOL_PATH) as fh:
                saved = json.load(fh)
        except (OSError, ValueError):
            saved = {}

    pool = {}
    for name in list_media_adhans():
        entry = saved.get(name, {})
        pool[name] = {
            "enabled": _to_bool(entry.get("enabled"), True),
            "category": entry.get("category") if entry.get("category") in ("fajr", "regular")
            else _default_category(name),
        }
    return pool


def save_pool(pool):
    """Persist the pool config, keeping only files that still exist."""
    valid = set(list_media_adhans())
    cleaned = {name: cfg for name, cfg in pool.items() if name in valid}
    with open(POOL_PATH, "w") as fh:
        json.dump(cleaned, fh, indent=2)
    return cleaned


def pick_adhan(is_fajr):
    """Pick a random adhan file path for the given prayer, honouring the pool.

    Falls back gracefully: fajr -> enabled fajr -> enabled regular -> any file;
    regular -> enabled regular -> enabled fajr -> any file.
    Returns an absolute path, or None if media/ has no adhan files at all.
    """
    pool = load_pool()
    enabled_fajr = [n for n, c in pool.items() if c["enabled"] and c["category"] == "fajr"]
    enabled_reg = [n for n, c in pool.items() if c["enabled"] and c["category"] == "regular"]
    any_file = list(pool.keys())

    if is_fajr:
        order = [enabled_fajr, enabled_reg, any_file]
    else:
        order = [enabled_reg, enabled_fajr, any_file]

    for candidates in order:
        if candidates:
            return pathjoin(MEDIA_DIR, random.choice(candidates))
    return None
