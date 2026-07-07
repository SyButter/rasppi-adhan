#!/usr/bin/env python3
"""Play an adhan at prayer time.

Called by cron (installed via updateAzaanTimers.py). Picks a random adhan from
the enabled pool, plays it at the configured volume, then plays the dua.

Usage:
    play_adhan.py fajr       # fajr adhan (uses fajr volume + fajr pool)
    play_adhan.py regular    # any other prayer (default volume + regular pool)
    play_adhan.py surah      # Friday Surah Baqarah (uses surah volume)

Doing the random pick and volume lookup *here* (rather than baking them into the
cron command) means changes made in the web admin take effect immediately, with
no need to reinstall cron.
"""

import subprocess
import sys
from datetime import datetime
from os.path import join as pathjoin

import adhan_config as cfg

ROOT_DIR = cfg.ROOT_DIR
LOG_PATH = pathjoin(ROOT_DIR, "adhan.log")
DUA_PATH = pathjoin(cfg.MEDIA_DIR, "after-adhan-dua.mp3")
SURAH_PATH = pathjoin(cfg.MEDIA_DIR, "002-surah-baqarah-mishary.mp3")


def log(message):
    line = f"{datetime.now()} {message}"
    print(line)
    try:
        with open(LOG_PATH, "a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def play(path, volume, audio_device):
    """Play a single audio file with mpv. Returns True on success."""
    if not path:
        log("No audio file to play")
        return False
    cmd = [
        "mpv",
        f"--audio-device={audio_device}",
        f"--volume={volume}",
        "--no-video",
        path,
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        return result.returncode == 0
    except FileNotFoundError:
        log("mpv not found - is it installed?")
        return False


def main():
    prayer = (sys.argv[1] if len(sys.argv) > 1 else "regular").lower()
    settings = cfg.load_settings()
    device = settings["audio_device"]

    if prayer == "surah":
        log("Playing Surah Baqarah")
        play(SURAH_PATH, settings["surah_vol"], device)
        return

    is_fajr = prayer == "fajr"
    volume = settings["fajr_azaan_vol"] if is_fajr else settings["default_azaan_vol"]
    adhan_path = cfg.pick_adhan(is_fajr)

    log(f"Playing {'Fajr ' if is_fajr else ''}Azaan ({adhan_path})")
    if play(adhan_path, volume, device):
        log("Playing Dua")
        play(DUA_PATH, volume, device)


if __name__ == "__main__":
    main()
