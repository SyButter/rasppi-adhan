# Homebridge Raspberry Pi Adhan

This Homebridge plugin turns your Raspberry Pi into a smart Adhan clock. It calculates prayer times and exposes a switch in HomeKit that turns on when it's time for Adhan. You can use this switch to trigger automations, such as playing the Adhan on your HomePod.

It also supports playing the Adhan audio locally on the Raspberry Pi (just like the original Python script).

## Installation

Since this plugin is part of the repository, you can install it by linking it to Homebridge.

1.  Navigate to the `homebridge-plugin` directory:
    ```bash
    cd /path/to/rasppi-adhan/homebridge-plugin
    ```
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Link the plugin to Homebridge:
    ```bash
    sudo npm link
    ```
    *Note: Depending on your Homebridge setup, you might not need `sudo`. If you are using the official Homebridge Raspberry Pi Image, you might need to install it in the global modules directory.*

4.  Add the platform to your Homebridge `config.json` (or use the UI):
    ```json
    {
      "platforms": [
        {
          "platform": "RasppiAdhan",
          "latitude": 30.1234,
          "longitude": -90.1234,
          "method": "NorthAmerica",
          "playAudio": true,
          "audioDevice": "alsa/plughw:1,0",
          "mediaPath": "/home/pi/rasppi-adhan/media"
        }
      ]
    }
    ```

## Configuration Options

*   `latitude`: Your location latitude.
*   `longitude`: Your location longitude.
*   `method`: Calculation method (e.g., `NorthAmerica`, `MuslimWorldLeague`, `Egyptian`, etc.).
*   `playAudio`: Set to `true` to play audio via the Pi's audio output (requires `mpv` installed).
*   `audioDevice`: The audio device string for `mpv` (default: `alsa/plughw:1,0`).
*   `mediaPath`: Path to the directory containing Adhan MP3 files.

## HomePod Integration (HomeKit Automation)

To play Adhan on your HomePod when the time comes:

1.  Open the **Apple Home** app.
2.  Go to the **Automation** tab.
3.  Tap **+** to add a new automation.
4.  Select **A Sensor Detects Something** (or **An Accessory is Controlled** if you see the switch).
    *   *Note: The plugin exposes a "Switch". If you don't see it as a sensor, choose "An Accessory is Controlled".*
5.  Select the **Adhan Trigger** switch.
6.  Choose **Turns On**.
7.  Tap **Next**.
8.  Select your **HomePod** (or multiple HomePods) as the accessory to control.
9.  Tap **Next**.
10. Under **Media**, choose **Play Audio**.
11. You can select **Choose Audio** to pick a specific track from Apple Music, or rely on a Shortcut.
    *   *Tip: For custom audio files, you might need to use "Convert to Shortcut" in the automation action, then use the "Get Contents of URL" and "Play Sound" actions, or add the Adhan audio to your Apple Music library.*

## Local Audio Playback

If `playAudio` is enabled, the plugin will attempt to play MP3 files from the `mediaPath`. It looks for files starting with `Adhan` and selects one randomly. It distinguishes between `Fajr` (filenames containing "fajr") and other prayers.

Ensure `mpv` is installed on your Raspberry Pi:
```bash
sudo apt install mpv
```
