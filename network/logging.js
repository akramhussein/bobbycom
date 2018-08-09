'use strict';

const resolve = require('path').resolve;
const winston = require('winston');

winston.configure({
  transports: [
    new (winston.transports.Console)({
      level: 'verbose',
      prettyPrint: true,
      colorize: true,
      silent: false,
      exitOnError: false,
      label: "BLE",
      timestamp: true,
    })
  ]
});

module.exports = winston;
