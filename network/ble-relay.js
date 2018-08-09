#!/usr/bin/env node
'use strict';

const startRelay = require('./relay.js').startRelay;
const config = require('./config').config;
const Raven = require('raven');

const RAVEN_DSN = process.env.RAVEN_DSN || '';
Raven.config(RAVEN_DSN).install();

startRelay({ mqtt: config.mqtt, ble: config.ble });
