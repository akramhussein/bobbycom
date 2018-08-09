#!/usr/bin/env python

import os
import time
import argparse

from raven import Client

import paho.mqtt.client as mqtt
import respeaker.usb_hid

RAVEN_DSN = os.environ.get('RAVEN_DSN', '')
client = Client(RAVEN_DSN)

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s (%(lineno)s) - %(levelname)s: %(message)s", datefmt='%Y.%m.%d %H:%M:%S')

MQTT_BROKER_IP = '127.0.0.1'
MQTT_BROKER_PORT = 1883

# Colors
RED = 0xFF0000
BLUE = 0x2196F3
GREEN = 0x00AF05
YELLOW = 0xFF9800
PURPLE = 0x9C27B0

# State
WIFI = False
BLUETOOTH = False
READY_SET = False

class PixelRing:
    mono_mode = 1
    listening_mode = 2
    spinning_mode = 3
    speaking_mode = 4

    def __init__(self):
        self.hid = respeaker.usb_hid.get()

    def off(self):
        self.set_color(rgb=0)

    def set_color(self, rgb=None, r=0, g=0, b=0):
        if rgb:
            self.write(0, [self.mono_mode, rgb & 0xFF, (rgb >> 8) & 0xFF, (rgb >> 16) & 0xFF])
        else:
            self.write(0, [self.mono_mode, b, g, r])

    def listen(self, direction=None):
        if direction is None:
            self.write(0, [7, 0, 0, 0])
        else:
            self.write(0, [2, 0, direction & 0xFF, (direction >> 8) & 0xFF])

    def spin(self, rgb=None, r=0, g=0, b=0):
        self.write(0, [self.spinning_mode, 0, 0, 0])

    def speak(self, strength, direction):
        self.write(0, [self.speaking_mode, strength, direction & 0xFF, (direction >> 8) & 0xFF])

    def set_volume(self, volume):
        self.write(0, [5, 0, 0, volume])

    @staticmethod
    def to_bytearray(data):
        if type(data) is int:
            array = bytearray([data & 0xFF])
        elif type(data) is bytearray:
            array = data
        elif type(data) is str:
            array = bytearray(data)
        elif type(data) is list:
            array = bytearray(data)
        else:
            raise TypeError('%s is not supported' % type(data))

        return array

    def write(self, address, data):
        data = self.to_bytearray(data)
        length = len(data)
        if self.hid:
            packet = bytearray([address & 0xFF, (address >> 8) & 0xFF, length & 0xFF, (length >> 8) & 0xFF]) + data
            self.hid.write(packet)

    def close(self):
        if self.hid:
            self.hid.close()

def on_connect(client, userdata, flags, rc):
    logger.info('Connected')
    mqtt_client.subscribe('#')
    pixel_ring.spin()
    pixel_ring.close()

def on_message(client, userdata, msg):
    def handle_network():
        global WIFI
        global BLUETOOTH
        global READY_SET

        logger.info('Wi-Fi:{}, Bluetooth: {}'.format(WIFI, BLUETOOTH))

        if WIFI and BLUETOOTH:
            if not READY_SET:
                # only run once
                pixel_ring.set_color(rgb=GREEN)
                time.sleep(4)
                pixel_ring.off()
                time.sleep(0.5)
                pixel_ring.listen()
                READY_SET = True
        elif not WIFI and BLUETOOTH:
            READY_SET = False
            pixel_ring.set_color(rgb=YELLOW)
        elif WIFI and not BLUETOOTH:
            READY_SET = False
            pixel_ring.set_color(rgb=BLUE)
        elif not WIFI and not BLUETOOTH:
            READY_SET = False
            pixel_ring.set_color(rgb=YELLOW)

    logger.info('{} - {}'.format(msg.topic, msg.payload))

    global WIFI
    global BLUETOOTH
    global READY_SET

    if msg.topic == 'system/off':
        pixel_ring.off()
    elif msg.topic == 'system/error':
        pixel_ring.set_color(rgb=RED)
    elif msg.topic == 'system/loading':
        pixel_ring.spin()
    elif msg.topic == 'system/reset':
        BLUETOOTH = False
        WIFI = False
        handle_network()
    elif msg.topic == 'ble/subscribed':
        BLUETOOTH = True
        handle_network()
    elif msg.topic == 'ble/unsubscribed':
        BLUETOOTH = False
        handle_network()
    elif msg.topic == 'wifi/connected':
        WIFI = True
        handle_network()
    elif msg.topic == 'wifi/disconnected':
        WIFI = False
        handle_network()
    elif msg.topic == 'speech/keyword':
        if len(msg.payload) > 0:
            colour = msg.payload
            hexColour = int(colour[1:], base=16)
            pixel_ring.set_color(rgb=hexColour)
            time.sleep(0.5)
            pixel_ring.listen()

    pixel_ring.close()

# Instances
pixel_ring = PixelRing()
mqtt_client = mqtt.Client()

def main():
    logger.info("Starting UI")
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_BROKER_IP, MQTT_BROKER_PORT)
    mqtt_client.loop_forever()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('o')
    args = parser.parse_args()

    if args.o == 'start':
        pixel_ring.spin()
        pixel_ring.close()
    elif args.o == 'mqtt':
        main()



