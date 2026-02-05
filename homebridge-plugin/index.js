const adhan = require('adhan');
const schedule = require('node-schedule');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

let Service, Characteristic;

module.exports = (api) => {
  Service = api.hap.Service;
  Characteristic = api.hap.Characteristic;
  api.registerPlatform('homebridge-rasppi-adhan', 'RasppiAdhan', RasppiAdhanPlatform);
};

class RasppiAdhanPlatform {
  constructor(log, config, api) {
    this.log = log;
    this.config = config || {};
    this.api = api;
    this.accessories = [];

    this.lat = this.config.latitude;
    this.lon = this.config.longitude;
    this.method = this.config.method || 'ISNA';
    this.playAudio = this.config.playAudio !== false; // Default true
    this.audioDevice = this.config.audioDevice || 'alsa/plughw:1,0';
    this.mediaPath = this.config.mediaPath || path.join(__dirname, '../media');

    // Map string method to Adhan constants
    this.calculationMethod = adhan.CalculationMethod[this.method] || adhan.CalculationMethod.NorthAmerica;

    if (!this.lat || !this.lon) {
      this.log.error('Latitude and Longitude are required!');
      return;
    }

    this.api.on('didFinishLaunching', () => {
      this.discoverDevices();
      this.schedulePrayers();
      // Reschedule every day at 1 AM
      schedule.scheduleJob('0 1 * * *', () => {
        this.schedulePrayers();
      });
    });
  }

  configureAccessory(accessory) {
    this.accessories.push(accessory);
  }

  discoverDevices() {
    const uuid = this.api.hap.uuid.generate('rasppi-adhan-device');
    const existingAccessory = this.accessories.find(accessory => accessory.UUID === uuid);

    if (existingAccessory) {
      this.setupAccessory(existingAccessory);
    } else {
      const accessory = new this.api.platformAccessory('Adhan Clock', uuid);
      this.setupAccessory(accessory);
      this.api.registerPlatformAccessories('homebridge-rasppi-adhan', 'RasppiAdhan', [accessory]);
    }
  }

  setupAccessory(accessory) {
    this.accessory = accessory;

    // Switch Service
    this.switchService = accessory.getService(Service.Switch) || accessory.addService(Service.Switch, 'Adhan Trigger');

    this.switchService.getCharacteristic(Characteristic.On)
      .on('get', callback => callback(null, false))
      .on('set', (value, callback) => {
        // Allow manual trigger
        if (value) {
           this.log.info('Adhan Triggered Manually');
           // We don't play audio on manual trigger by default unless we want to test?
           // Let's just set timeout to turn off.
           setTimeout(() => {
             this.switchService.updateCharacteristic(Characteristic.On, false);
           }, 5000);
        }
        callback();
      });

    accessory.on('identify', (paired, callback) => {
      this.log.info('Identifying Adhan Clock');
      callback();
    });
  }

  schedulePrayers() {
    this.log.info('Calculating prayer times for today...');
    const coordinates = new adhan.Coordinates(this.lat, this.lon);
    const date = new Date();
    const params = this.calculationMethod();

    const prayerTimes = new adhan.PrayerTimes(coordinates, date, params);

    const prayers = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha'];
    const now = new Date();

    prayers.forEach(prayer => {
      const time = prayerTimes[prayer];
      if (time > now) {
        this.log.info(`Scheduling ${prayer} at ${time.toLocaleTimeString()}`);
        schedule.scheduleJob(time, () => {
          this.triggerAdhan(prayer);
        });
      }
    });
  }

  triggerAdhan(prayerName) {
    this.log.info(`Time for ${prayerName}! Triggering Adhan...`);

    // Turn on the switch
    if (this.switchService) {
      this.switchService.updateCharacteristic(Characteristic.On, true);
      // Turn off after 5 minutes (standard adhan length approx)
      setTimeout(() => {
        this.switchService.updateCharacteristic(Characteristic.On, false);
      }, 5 * 60 * 1000);
    }

    // Play Audio if enabled
    if (this.playAudio) {
      this.playAdhanAudio(prayerName);
    }
  }

  playAdhanAudio(prayerName) {
    const isFajr = prayerName === 'fajr';
    const file = this.getRandomAdhanFile(isFajr);

    if (!file) {
      this.log.warn('No audio file found to play.');
      return;
    }

    const volume = 100; // Can be parameterized
    const cmd = `mpv --audio-device=${this.audioDevice} --volume=${volume} --no-video "${file}"`;

    this.log.info(`Playing: ${cmd}`);
    exec(cmd, (error, stdout, stderr) => {
      if (error) {
        this.log.error(`Error playing audio: ${error.message}`);
        return;
      }
      if (stderr) this.log.debug(`mpv stderr: ${stderr}`);

      // Play Dua after Adhan
      const duaFile = path.join(this.mediaPath, 'after-adhan-dua.mp3');
      if (fs.existsSync(duaFile)) {
         const duaCmd = `mpv --audio-device=${this.audioDevice} --volume=${volume} --no-video "${duaFile}"`;
         this.log.info('Playing Dua...');
         exec(duaCmd);
      }
    });
  }

  getRandomAdhanFile(isFajr) {
    try {
      const files = fs.readdirSync(this.mediaPath).filter(f => f.endsWith('.mp3') && f.startsWith('Adhan'));
      if (files.length === 0) return null;

      const fajrFiles = files.filter(f => f.toLowerCase().includes('fajr'));
      const regularFiles = files.filter(f => !f.toLowerCase().includes('fajr'));

      if (isFajr) {
        if (fajrFiles.length > 0) return path.join(this.mediaPath, fajrFiles[Math.floor(Math.random() * fajrFiles.length)]);
        if (regularFiles.length > 0) return path.join(this.mediaPath, regularFiles[Math.floor(Math.random() * regularFiles.length)]);
      } else {
        if (regularFiles.length > 0) return path.join(this.mediaPath, regularFiles[Math.floor(Math.random() * regularFiles.length)]);
        if (fajrFiles.length > 0) return path.join(this.mediaPath, fajrFiles[Math.floor(Math.random() * fajrFiles.length)]);
      }
      return path.join(this.mediaPath, files[0]); // Fallback
    } catch (e) {
      this.log.error(`Error accessing media directory: ${e.message}`);
      return null;
    }
  }
}
