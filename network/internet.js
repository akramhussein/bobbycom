'use strict';

const dns = require('dns');
const _mqtt = require('mqtt');
const logging = require('./logging');
const config = require('./config').config;

const CHECK_SECONDS = process.env.CHECK_SECONDS || 30;
const DOMAIN = process.env.DOMAIN || 'www.bbc.co.uk';

const mqtt = _mqtt.connect(config.mqtt);

mqtt.on('connect', function () {
	logging.info('[INTERNET CHECK]: Subscribed to mqtt, starting Internet connection check');

	setInterval(() => {
	  dns.resolve(DOMAIN, (err) => {
	    if (err) {
	      logging.error('No Internet connection');
	      mqtt.publish('wifi/disconnected');
	    } else {
	    	logging.error('Internet connection');
				mqtt.publish('wifi/connected');
	    }
	  });
	}, CHECK_SECONDS * 1000);

});
