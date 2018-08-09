# Bobbycom

Raspberry Pi app that continuously runs Google's Speech-to-Text Streaming API and relays it onwards via BTLE. Managed using MQTT.

This is a companion to the iOS app called `Subtitles`.

This was designed and tested to run on a [Raspberry Pi Zero W](https://www.raspberrypi.org/products/raspberry-pi-zero-w/) using a [ReSpeaker microphone array](http://wiki.seeed.cc/Respeaker_Mic_Array/).

## Requirements

* [Raspberry Pi Zero W](https://www.raspberrypi.org/products/raspberry-pi-zero-w/)

* [ReSpeaker microphone array](http://wiki.seeed.cc/Respeaker_Mic_Array/)

* [Google Cloud account](https://cloud.google.com/) - Sign up for Google Cloud `Speech API` and download a `google-credentials.json` file

* USB cable to connect the ReSpeaker to the Raspberry Pi Zero W

* Power for Raspberry Pi Zero W

## Getting Started

### Setup Rasperry Pi Zero W

#### Mac

To setup the Raspberry Pi Zero W, first download the appropriate image and flash it to the Micro SD card:

1. Download the Raspbian Stretch Lite image from [here](https://www.raspberrypi.org/downloads/raspbian/)

2. Download [Etcher](https://etcher.io/) and install.

3. Create an empty file with `touch` on the SD Card called `ssh`

e.g. `touch /Volumes/boot/ssh`

4. Create an empty file with `touch` on the SD Card called `wpa_supplicant.conf`

e.g. `/Volumes/boot/wpa_supplicant.conf`

5. Add your Wi-Fi details to `wpa_supplicant.conf`:

```
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="NETWORK-NAME"
    psk="NETWORK-PASSWORD"
}
```

6. Eject the SD card and insert in to the Pi Zero W. Boot up the machine and wait around 2 minutes.

For instructions on connecting to multiple Wi-Fi networks, see [here](https://www.thepolyglotdeveloper.com/2016/08/connect-multiple-wireless-networks-raspberry-pi/).

### SSH

To SSH in to the Pi Zero W

```
$ ssh-keygen -R raspberrypi.local

$ ssh pi@raspberrypi.local
```

Default password is `raspberry`, but it is advised you change this.

[Instructions](http://desertbot.io/setup-pi-zero-w-headless-wifi/)

### Installing Node.js for Raspberry Pi Zero W

The Raspberry Pi Zero uses a different ARM architecture (v6l) to the Raspberry Pi 2 & 3, therefore we need to install Node.js differently.

Remove any existing Node.js binaries and run the following commands:

```
$ wget https://nodejs.org/dist/v7.7.2/node-v7.7.2-linux-armv6l.tar.gz

$ tar -xzf node-v7.7.2-linux-armv6l.tar.gz

$ sudo cp -R node-v7.7.2-linux-armv6l/* /usr/local/

$ echo 'PATH=$PATH:/usr/local/bin' >>  ~/.profile

```

### Linux requirements

To ensure the Bluetooth works, please follow instructions [here for Linux](https://github.com/sandeepmistry/bleno#running-on-linux).

### Checkout and build from source

Due to the architecture difference, we cannot rely on `npm` to install the right C++ binaries.

Therefore, to build the `bobbycom` repo, do the following:

```
$ git clone https://github.com/akramhussein/bobbycom.git

$ cd bobbycom

$ cd network && npm install --build-from-source --save && cd ..

$ cd speech && pip install -r requirements.txt && cd ..

$ cd ui && pip install -r requirements.txt && cd ..

$ npm install -g forever

```

### Add Google Credentials

To authenticate and use the Google Speech-to-Text API, you need to download your project's credentials file and copy it to the Pi e.g. the `/home/pi/bobbycom` directory.

You can use `scp` to copy it across. For example:

`$ scp -r google-credentials.json pi@raspberrypi.local:/home/pi/bobbycom`

### Setup Microphone

To setup the ReSpeaker to work on the Raspberry Pi, create a file at `~/.asoundrc` (`$ touch ~/.asoundrc`) and then add the following:

```
pcm.!default {
    type asym
    playback.pcm {
        type plug
        slave.pcm "hw:0,0"
    }
    capture.pcm {
        type dsnoop
        ipc_key 5432
        slave {
            pcm "hw:1,0"
            buffer_size 96000
        }
    }
}
```

### Components

* Network - relays ASR results over BTLE and periodically checks Internet connection

* UI - handles UI control

* Speech - Indefinite processing and streaming of audio and ASR

## Usage

* MQTT is automatically started on the system.

* [Forever](https://www.npmjs.com/package/forever) is used to manage the processes.

### Manually start:

`$ sudo forever start /home/pi/bobbycom/forever.json &`

### Start at boot:

To start `bobbycom` at boot, copy the `rc.local` file to `/etc/rc.local`.

e.g. `$ cp rc.local /etc/rc.local`

### Running Forever commands

If you start Forever via `/etc/rc.local`, it will be run as `root`, therefore you need to use `sudo`:

`$ sudo forever <command>`

Otherwise, you can use:

`$ forever <command>`

### Logs

[forever.json](forever.json) defines the processes to be run by Forever and lists all the log destinations.

## UI

* Spinning GREEN LEDs = `loading`
* Solid YELLOW LEDs = `waiting for Internet connection`
* Solid BLUE LEDs = `waiting for Bluetooth connection`
* Solid RED LEDs = `error`, requires reboot
* Solid GREEN LEDs = `ready`, after they disappear, will be ready to recognize and relay speech.

### Notes about boot sequence

Between powering on the Pi and the UI initiating the `loading` sequence (see below), the ReSpeaker will acknowledge audio with the GREEN|BLUE|GREEN pattern showing on the direction it hears audio from. This is because the firmware of the ReSpeaker is difficult to override and therefore isn't controlled until later in the boot sequence. Until you see the GREEN LED solid pattern, it will not recognize and relay speech.

## License

Apache 2.0.
