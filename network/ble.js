'use strict';

const bleno = require('bleno');
const sdp = require('simple-datagram-protocol');

const logging = require('./logging');

let key = 255;
const nextKey = () => { key = (key + 1) % 255; return key }

const sendMessage = function(message, datagramSize, sendDatagram) {
  const datagramView = new sdp.DatagramView(message, nextKey(), datagramSize);
  for (let i = 0; i < datagramView.numberOfDatagrams; i++) {
    sendDatagram(datagramView.getDatagram(i));
  }
};

const _defaultSendMessage = (message) => {
  //jshint unused:false
  logging.warn('Can\'t send message, no devices subscribed.');
};

const start = (config) => {
  const ble = { config };

  ble.sendMessage = _defaultSendMessage;

  const onMessage = (message) => { ble.onMessage(message) };

  ble.messageManager = new sdp.MessageManager(onMessage);

  const characteristic = new bleno.Characteristic({
    value : null,
    uuid : config.characteristicUUID,
    properties : ['notify', 'read', 'write'],

    onSubscribe: function(maxValueSize, updateValueCallback) {
      logging.info('Device subscribed');
      logging.verbose('Datagram max size: ' + maxValueSize);
      ble.onSubscribe();

      ble.sendMessage = (message) => {
        sendMessage(message, maxValueSize, updateValueCallback);
      };
    },

    onUnsubscribe: function() {
      logging.info('Device unsubscribed');
      ble.onUnsubscribe();
      ble.sendMessage = _defaultSendMessage;
    },

    // Send a message back to the client with the characteristic's value
    onReadRequest: function(offset, callback) {
      logging.info('Read request received');
      callback(this.RESULT_SUCCESS, ble.onReadData())
      bleno.stopAdvertising();
    },

    // Accept a new value for the characterstic's value
    onWriteRequest: function(data, offset, withoutResponse, callback) {
      this.value = data;
      if (null !== data) {
        ble.messageManager.processDatagram(data);
      }
      logging.info('Write request: value = ' + this.value.toString('utf-8'));
      callback(this.RESULT_SUCCESS);
    }
  })

  const service = new bleno.PrimaryService({
    uuid: config.serviceUUID,
    characteristics: [characteristic]
  })

  // Once bleno starts, begin advertising our BLE address
  bleno.on('stateChange', function(state) {
    logging.info('State change: ' + state);
    if (state === 'poweredOn') {
      bleno.startAdvertising('Bobbycom', [config.serviceUUID], function(err) {
	      if (err) {
	      	logging.error(err);
	      	return;
	      }
	    });
    } else {
      bleno.stopAdvertising();
    }
  });

  // Notify the console that we've accepted a connection
  bleno.on('accept', function(clientAddress) {
    logging.info('Accepted connection from address: ' + clientAddress);
  });

  // Notify the console that we have disconnected from a client
  bleno.on('disconnect', function(clientAddress) {
    logging.info('Disconnected from address: ' + clientAddress);
  });

  // When we begin advertising, create a new service and characteristic
  bleno.on('advertisingStart', function(error) {
    if (error) {
      logging.error('Advertising start error:' + error);
      return;
    }
    logging.info('Advertising start success');
    bleno.setServices([service]);
  });

  return ble;
}

module.exports = { start };
