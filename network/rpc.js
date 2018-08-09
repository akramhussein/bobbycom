#!/usr/bin/env node
'use strict';

module.exports.makeRPC = (methods) => {
	return (functionName, argument) => {
		return methods[functionName](argument)
	}
}
