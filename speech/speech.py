#!/usr/bin/env python

# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Modified version of Google Cloud Speech API sample application using the streaming API."""

from __future__ import division

import argparse
import collections
import itertools
import re
import sys
import time
import json
import os

import grpc
import pyaudio
from six.moves import queue
import six

from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
from google import gax

from raven import Client

import transcribe_streaming_mic

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s (%(lineno)s) - %(levelname)s: %(message)s", datefmt='%Y.%m.%d %H:%M:%S')

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/home/pi/bobbycom/google-credentials.json'

RAVEN_DSN = 'https://8d9acbbbf8f849e3b513bc39de2045c6:41664f405fc543fabad525c2c7d2275a@sentry.io/255851' #os.environ.get('RAVEN_DSN', '')
client = Client(RAVEN_DSN)

import paho.mqtt.client as mqtt
MQTT_BROKER_IP = '127.0.0.1'
MQTT_BROKER_PORT = 1883

mqtt_client = mqtt.Client(client_id="speech", clean_session=False)

# globals
WIFI = False
BLUETOOTH = False
RECOGNIZE = False

PHRASES = []

RATE = 16000

def duration_to_secs(duration):
    return duration.seconds + (duration.nanos / float(1e9))


class ResumableMicrophoneStream(transcribe_streaming_mic.MicrophoneStream):
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate, chunk_size, max_replay_secs=5):
        super(ResumableMicrophoneStream, self).__init__(rate, chunk_size)
        self._max_replay_secs = max_replay_secs

        # Some useful numbers
        # 2 bytes in 16 bit samples
        self._bytes_per_sample = 2 * 1 #self._num_channels
        self._bytes_per_second = self._rate * self._bytes_per_sample

        self._bytes_per_chunk = (self._chunk * self._bytes_per_sample)
        self._chunks_per_second = (
                self._bytes_per_second / self._bytes_per_chunk)
        self._untranscribed = collections.deque(
                maxlen=self._max_replay_secs * self._chunks_per_second)

    def on_transcribe(self, end_time):
        while self._untranscribed and end_time > self._untranscribed[0][1]:
            self._untranscribed.popleft()

    def generator(self, resume=False):
        total_bytes_sent = 0
        if resume:
            # Make a copy, in case on_transcribe is called while yielding them
            catchup = list(self._untranscribed)
            # Yield all the untranscribed chunks first
            for chunk, _ in catchup:
                yield chunk

        for byte_data in super(ResumableMicrophoneStream, self).generator():
            # Populate the replay buffer of untranscribed audio bytes
            total_bytes_sent += len(byte_data)
            chunk_end_time = total_bytes_sent / self._bytes_per_second
            self._untranscribed.append((byte_data, chunk_end_time))

            yield byte_data



def _record_keeper(responses, stream):
    """Calls the stream's on_transcribe callback for each final response.

    Args:
        responses - a generator of responses. The responses must already be
            filtered for ones with results and alternatives.
        stream - a ResumableMicrophoneStream.
    """
    for r in responses:
        result = r.results[0]
        if result.is_final:
            top_alternative = result.alternatives[0]
            # Keep track of what transcripts we've received, so we can resume
            # intelligently when we hit the deadline
            stream.on_transcribe(duration_to_secs(top_alternative.words[-1].end_time))
        yield r


def listen_print_loop(responses, stream):
    """Iterates through server responses and prints them.

    Same as in transcribe_streaming_mic, but keeps track of when a sent
    audio_chunk has been transcribed.
    """
    with_results = (r for r in responses if (r.results and r.results[0].alternatives))

    for response in with_results:
        if not response.results:
            continue

        result = response.results[0]
        if not result.alternatives:
            continue

        transcript = result.alternatives[0].transcript
        logger.info("{}, final: {}".format(transcript, result.is_final))
        data = json.dumps({'message': transcript, 'final': result.is_final})
        mqtt_client.publish('speech/text', data)


def on_connect(client, userdata, flags, rc):
    logger.info('Connected to MQTT broker')
    mqtt_client.subscribe('#')

def on_message(client, userdata, msg):
    logger.info(' - {}'.format(msg.topic))

    def handle_network():
        global WIFI
        global BLUETOOTH
        global RECOGNIZE

        logger.info('Wi-Fi:{}, Bluetooth: {}'.format(WIFI, BLUETOOTH))
        RECOGNIZE = WIFI and BLUETOOTH

    global PHRASES
    global RECOGNIZE
    global BLUETOOTH
    global WIFI

    if msg.topic == 'speech/phrases':
        logger.info('Received new common phrases')
        if len(msg.payload) > 0:
            data = msg.payload
            PHRASES = data.split(',')
            logger.info('Updated common phrases: {}'.format(PHRASES))
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


def main():
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_BROKER_IP, MQTT_BROKER_PORT)
    mqtt_client.loop_start()

    logger.info("Starting Speech-to-Text")

    language_code = 'en-GB'  # a BCP-47 language tag
    client = speech.SpeechClient()
    logger.info("Google Speech-to-Text client setup")

    mic_manager = ResumableMicrophoneStream(RATE, int(RATE / 10))

    logger.info("Mic manager setup")

    with mic_manager as stream:
        resume = False
        global PHRASES
        global RECOGNIZE

        while True:

            if not RECOGNIZE:
                time.sleep(1)
            else:
                audio_generator = stream.generator(resume=resume)
                requests = (types.StreamingRecognizeRequest(audio_content=content)
                            for content in audio_generator)

                config = types.RecognitionConfig(
                    encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=RATE,
                    language_code=language_code,
                    max_alternatives=1,
                    enable_word_time_offsets=True,
                    speech_contexts=[types.SpeechContext(phrases=PHRASES)])

                streaming_config = types.StreamingRecognitionConfig(
                    config=config,
                    interim_results=True)

                responses = client.streaming_recognize(streaming_config, requests)

                try:
                    listen_print_loop(responses, stream)
                    break
                except grpc.RpcError, e:
                    if e.code() not in (grpc.StatusCode.INVALID_ARGUMENT,
                                        grpc.StatusCode.OUT_OF_RANGE):
                        raise
                    details = e.details()
                    if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                        if 'deadline too short' not in details:
                            logger.error(details)
                            raise
                    else:
                        if 'maximum allowed stream duration' not in details:
                            logger.error(details)
                            raise

                    logger.info('Resuming...')
                    resume = True
                except Exception, e:
                    logger.info(e)
                    mqtt_client.publish('system/error')

if __name__ == '__main__':
    main()

