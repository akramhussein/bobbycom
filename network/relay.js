#!/usr/bin/env node
'use strict';

const exec = require('child_process').exec;
const _mqtt = require('mqtt');
const _ble = require('./ble.js');
const _rpc = require('./rpc.js');
const logging = require('./logging');

const startRelay = (config) => {

    const mqtt = _mqtt.connect(config.mqtt);
    const ble = _ble.start(config.ble);

    const rpc = _rpc.makeRPC({
        postMQTT: (payload) => {
            const mqtt = new Promise((resolve, reject) => {
                mqtt.publish(payload.topic, new Buffer(payload.message, 'base64'), {}, (error, granted) => {
                    if (err) {
                        resolve({ error });
                    } else {
                        resolve({ success: 'success' });
                    }
                });
            })
        },
        print: (payload) => {
            return new Promise.resolve(console.log(payload))
        },
        shell: (payload) => {
            return new Promise((resolve, reject) => {
                console.log('execute shell');
                exec(payload, function(error, stdout, stderr) {
                    console.log('finished executing shell');
                    const result = { error, stdout, stderr }
                    console.log('result: ' + result);
                    resolve(result)
                });
            });
        }
    });


    ble.sendJSON = (response) => {
        const jsonText = JSON.stringify(response);
        const buff = new Buffer(jsonText);
        ble.sendMessage(buff);
    }

    ble.sendRPCResponse = (id, response) => {
        ble.sendJSON({ rpcResponse: { id, response } });
    }

    ble.sendMQTT = (topic, _message) => {
        const message = _message.toString('base64');
        ble.sendJSON({ mqtt: { topic, message } });
    }

		ble.sendSpeechToTextResult = (_message, final=false) => {
			logging.info(`sendSpeechToTextResult ${_message}, final: ${final}`);
			const message = _message.toString('base64');
			ble.sendJSON({ text: { message, final } });
		}

    ble.onMessage = function(buffer) {
        const message = JSON.parse(buffer);
        if ('message' in message) {
        logging.verbose(`Received message for: ${message.message}`);
        	const messageType = message.message;
        	if (messageType === 'phrases') {
        		const phrases = message.data.join(',');
        		mqtt.publish('speech/phrases', phrases);
        	} else if (messageType === 'keyword') {
        		const colour = message.data;
        		mqtt.publish('speech/keyword', colour);
        	}
        }
    };

    ble.getReadData = function() {
        return new Buffer('Read data');
    };

    ble.onSubscribe = () => {
    	logging.info('Client Subscribed');
    	mqtt.publish('ble/subscribed');
    }

    ble.onUnsubscribe = () => {
    	logging.info('Client Unsubscribed');
    	mqtt.publish('ble/unsubscribed');
    }

    mqtt.on('message', function (topic, message) {
    		logging.info(`topic: ${topic}, message: ${message}`);
        if (topic.includes('speech/text')) {
        	const json = JSON.parse(message);
          ble.sendSpeechToTextResult(json.message, json.final);
        }
    });

    mqtt.on('connect', function () {
        mqtt.subscribe('#');
    });
};

module.exports = { startRelay };
