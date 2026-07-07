#!/usr/bin/env python3

import datetime
import time
import sys
import os
import random
from os.path import dirname, abspath, join as pathjoin
import argparse
from configparser import ConfigParser


root_dir = dirname(abspath(__file__))
sys.path.insert(0, pathjoin(root_dir, 'crontab'))
from modules.praytimes import PrayTimes
PT = PrayTimes() 

from crontab import CronTab
import adhan_config

# HELPER FUNCTIONS
# ---------------------------------
# ---------------------------------
# Function to add azaan time to cron
def parseArgs():
    parser = argparse.ArgumentParser(description='Calculate prayer times and install cronjobs to play Adhan')
    parser.add_argument('--lat', type=float, dest='lat',
                        help='Latitude of the location, for example 30.345621')
    parser.add_argument('--lon', type=float, dest='lon',
                        help='Longitude of the location, for example 60.512126')
    parser.add_argument('--method', choices=['MWL', 'ISNA', 'Egypt', 'Makkah', 'Karachi', 'Tehran', 'Jafari'],
                        dest='method',
                        help='Method of calculation')
    parser.add_argument('--azaan-volume', type=int, dest='default_azaan_vol',
                        help='Volume for azaan (other than fajr) in millibels, 1500 is loud and -30000 is quiet (default 0)')
    parser.add_argument('--fajr-azaan-volume', type=int, dest='fajr_azaan_vol',
                        help='Volume for fajr azaan in millibels, 1500 is loud and -30000 is quiet (default 0)')
    parser.add_argument('--dry-run', action='store_true', dest='dry_run',
                        help='Print the cron jobs instead of installing them')
    parser.add_argument('--audio-device', type=str, dest='audio_device', default='alsa/plughw:1,0',
                        help='Audio device for mpv (default: alsa/plughw:1,0)')
    return parser

def getConfig():
    # Parse arguments
    parser = parseArgs()
    args = parser.parse_args()
    
    # Initialise and read config file if present
    config = ConfigParser()
    file_path = pathjoin(root_dir, 'settings.ini')
    config.read(file_path)

    lat = lon = method = fajr_azaan_vol = default_azaan_vol = surahBaqarah = surahVolume = None

    # Get mandatory data. First check args, if not present check settings.ini
    try:
        if args.lat:
            lat = float(args.lat)
            config['DEFAULT']['lat'] = str(lat)
        else:
            lat = float(config['DEFAULT']['lat'])
        
        if args.lon:
            lon = float(args.lon)
            config['DEFAULT']['lon'] = str(lon)
        else:
            lon = float(config['DEFAULT']['lon'])

        if args.method:
            method = args.method
            config['DEFAULT']['method'] = method
        else:
            method = config['DEFAULT']['method']
    except:
        print("Incorrect value or values not provided")
        lat = lon = method = None


    # Get optional data
    try:
        if args.default_azaan_vol:
            default_azaan_vol = int(args.default_azaan_vol)
        else:
            default_azaan_vol = int(config['VOLUME']['defaultAzaanVolume'])

        if args.fajr_azaan_vol:
            fajr_azaan_vol = int(args.fajr_azaan_vol)
        else:
            fajr_azaan_vol = int(config['VOLUME']['fajrAzaanVolume'])
    except:
        default_azaan_vol = 0
        fajr_azaan_vol = 0

        
    config["VOLUME"] = {
        "defaultAzaanVolume": str(default_azaan_vol), 
        "fajrAzaanVolume": str(fajr_azaan_vol)
        }


    # Setup Surah Baqarah on Fridays
    try:
        surahBaqarah = bool(config['FRIDAY']['playSurahBaqarah'])
        surahVolume = int(config['FRIDAY']['surahVolume'])
    except:
        surahBaqarah = False
        surahVolume = 0
        config["FRIDAY"] = {"playSurahBaqarah": str(surahBaqarah), "surahVolume": str(surahVolume)}
    

    # If any of the mandatory values not provided or configures in settings.ini, exit and show usage
    if not lat or not lon or not method:
        print("No values provided, please provide values as per below usage")
        parser.print_usage()
        sys.exit(1)

    # save values to settings.ini
    with open(file_path, 'w') as configfile:
        config.write(configfile)

    return lat, lon, method, fajr_azaan_vol, default_azaan_vol, surahBaqarah, surahVolume, args.dry_run, args.audio_device


def addAzaanTime (strPrayerName, strPrayerTime, objCronTab, strCommand, dry_run=False):
  if dry_run:
      print(f"[DRY-RUN] Would schedule '{strPrayerName}' at {strPrayerTime}: {strCommand}")
      return

  job = objCronTab.new(command=strCommand,comment=strPrayerName)  
  timeArr = strPrayerTime.split(':')
  hour = timeArr[0]
  min = timeArr[1]
  job.minute.on(int(min))
  job.hour.on(int(hour))
  job.set_comment(strJobComment)
  print(job)
  return

def addFriday(strSurahName, objCronTab, strCommand, dry_run=False):
  if dry_run:
      print(f"[DRY-RUN] Would schedule '{strSurahName}' on Fridays at 08:00: {strCommand}")
      return

  job = objCronTab.new(command=strCommand,comment=strSurahName)
  job.minute.on(0)
  job.hour.on(8)
  job.dow.on(5)
  job.set_comment(strJobComment)
  print(job)
  return

def addUpdateCronJob (objCronTab, strCommand, dry_run=False):
  if dry_run:
      print(f"[DRY-RUN] Would schedule update job daily at 03:15: {strCommand}")
      return

  job = objCronTab.new(command=strCommand)
  job.minute.on(15)
  job.hour.on(3)
  job.set_comment(strJobComment)
  print(job)
  return

def addClearLogsCronJob (objCronTab, strCommand, dry_run=False):
  if dry_run:
      print(f"[DRY-RUN] Would schedule clear logs job monthly: {strCommand}")
      return

  job = objCronTab.new(command=strCommand)
  job.day.on(1)
  job.minute.on(0)
  job.hour.on(0)
  job.set_comment(strJobComment)
  print(job)
  return

def get_command(prayer):
    # The random adhan pick and volume are resolved at play time by
    # play_adhan.py, so web-admin changes take effect without reinstalling cron.
    return f"python3 {root_dir}/play_adhan.py {prayer} >> {root_dir}/adhan.log 2>&1"

# ---------------------------------
# ---------------------------------
# HELPER FUNCTIONS END
# Merge args with saved values if any
lat, lon, method, fajr_azaan_vol, default_azaan_vol, surahBaqarah, surahVolume, dry_run, audio_device = getConfig()

# Keep the wall display in sync with the same location/method used here.
if not dry_run:
    adhan_config.write_display_config()

if dry_run:
    system_cron = None
    print("Running in DRY-RUN mode. No cron jobs will be installed.")
else:
    system_cron = CronTab(user=True)

# Set calculation method, utcOffset and dst here
# By default system timezone will be used
# --------------------
PT.setMethod(method)
# --------------------
utcOffset = -(time.timezone/float(3600))
isDst = time.localtime().tm_isdst

now = datetime.datetime.now()

strUpdateCommand = f"python3 {root_dir}/updateAzaanTimers.py >> {root_dir}/adhan.log 2>&1"
strClearLogsCommand = f"truncate -s 0 {root_dir}/adhan.log 2>&1"
strJobComment = "rpiAdhanClockJob"
strSurahBaqarahMP3Command = f"python3 {root_dir}/play_adhan.py surah >> {root_dir}/adhan.log 2>&1"
# Remove existing jobs created by this script
if not dry_run:
    system_cron.remove_all(comment=strJobComment)

# Calculate prayer times
times = PT.getTimes((now.year,now.month,now.day), (lat, lon), utcOffset, isDst)
print("---------------------------------")
print("Co-ordinates provided")
print("---------------------------------")
print(f"Latitude:   {lat} \nLongitude:  {lon} \nMethod:     {method}")
print("---------------------------------")
print()
print("---------------------------------")
print("Prayer Times")
print("---------------------------------")
print(f"Fajr:    {times['fajr']} hrs")
print(f"Dhuhr:   {times['dhuhr']} hrs")
print(f"Asr:     {times['asr']} hrs")
print(f"Maghrib: {times['maghrib']} hrs")
print(f"Isha:    {times['isha']} hrs")
print("---------------------------------")

# Add times to crontab
print()
print("---------------------------------")
print("Cron jobs scheduled")
print("---------------------------------")
print("Fajr:")
addAzaanTime('fajr',times['fajr'],system_cron,get_command('fajr'), dry_run)
print("---------------------------------")
print("Dhur:")
addAzaanTime('dhuhr',times['dhuhr'],system_cron,get_command('regular'), dry_run)
print("---------------------------------")
print("Asr:")
addAzaanTime('asr',times['asr'],system_cron,get_command('regular'), dry_run)
print("---------------------------------")
print("Maghrib:")
addAzaanTime('maghrib',times['maghrib'],system_cron,get_command('regular'), dry_run)
print("---------------------------------")
print("Isha:")
addAzaanTime('isha',times['isha'],system_cron,get_command('regular'), dry_run)
print("---------------------------------")
print("Friday Surah Baqarah:")
if surahBaqarah == True:
    addFriday('Surah Baqarah', system_cron, strSurahBaqarahMP3Command, dry_run)
print("---------------------------------")
print()
# Run this script again overnight
print("Update Azaan Timers(Daily @ night):")
addUpdateCronJob(system_cron, strUpdateCommand, dry_run)
print("---------------------------------")
print("Clear logs(Monthly):")
# Clear the logs every month
addClearLogsCronJob(system_cron,strClearLogsCommand, dry_run)
print("---------------------------------")
print()

if not dry_run:
    system_cron.write_to_user(user=True)
print('Script execution finished at: ' + str(now))

