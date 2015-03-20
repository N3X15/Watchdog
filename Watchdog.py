'''
Copyright (c)2015 Rob "N3X15" Nelson <nexisentertainment@gmail.com>

MIT License Goes Here
'''

import cPickle
import json
import logging
import logging.handlers
import os
import psutil
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib
import platform
import importlib

# pip package => module list
import_packages={
	'yaml':['yaml'],
	'psutil':['psutil'],
	'pyparsing':['pyparsing'],
	'Jinja2':['jinja2']
}

for pkg,modules in import_packages.items():
	try:
		for module in modules:
			importlib.import_module(module)
	except:
		print('Failed to import {module}, which means {pkg} is not installed.  Please run "pip install {pkg}".'.format(module=module,pkg=pkg))
		sys.exit(-1)

script_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(script_dir, 'lib', 'buildtools'))
sys.path.append(os.path.join(script_dir, 'lib', 'valve'))
#print(repr(sys.path))

from watchdog import utils 
from watchdog.engines import SourceEngine, GModEngine
from watchdog.engines.steam import SteamContent

from buildtools import *
from buildtools import os_utils
from buildtools.wrapper import Git
from buildtools.bt_logging import IndentLogger
from buildtools.wrapper.git import GitRepository

utils.script_dir=script_dir

# @formatting:off
default_config = {
	'monitor':{
		'ip':'127.0.0.1',
		'port': 27015,
		'timeout': 30.0,
		'max-fails': 3,
		# 'wait-for-ready': True,
		'threads': False,
		'image': 'srcds_linux',
	},
	'paths': {
		'steamcmd':       '~/steamcmd',
		'stats':          'stats.json',
		'crashlog':       '~/steam/crashlogs/',
		'cores':          '~/steam/cores/',
		'run':            '~/garrysmod',
		'config':         '~/garrysmod/garrysmod/cfg',
		'addons': {
			'lua':       '~/garrysmod/garrysmod/addons',
			'sourcemod': '~/garrysmod/garrysmod/addons/sourcemod',
			'metamod':   '~/garrysmod/garrysmod/addons',
		},
	},
	'env': {
		'LD_LIBRARY_PATH': '/home/gmod/garrysmod:/home/gmod/garrysmod/bin',
	},
	'srcds': {
		'launcher': 'srcds_linux',
		'srcds_args':{
			'game': 'garrysmod',
			'authkey': None,
			'autoupdate': '',
		},
		'game_args':{
			'map': 'gm_flatgrass',
			'maxplayers': '32',
			'host_workshop_collection': None,
			'gamemode': 'sandbox',
		}
	},
	'content':{
		'4020': {
			'name': "Garry's Mod Dedicated",
			'dir': '~/garrysmod',
			'game': 'garrysmod',
		},
		'90': {
			'name': "CS:S 1.6 Dedicated Server",
			# 'dir': '~/content/css/',
			'game': 'cstrike',
		},
		'232370': {
			'name': "HL2:DM Dedicated Server",
			# 'dir': '~/content/hl2dm/',
			'game': 'hl2mp',
		},
		'232250': {
			'name': "TF2 Dedicated Server",
			# 'dir': '~/content/tf2/',
			'game': 'tf',
		},
	},
	'addons': {
		'WireMod': {
			'type': 'lua',
			'repo': {
				'type':'git',
				'remote': 'https://github.com/wiremod/wire.git',
				# 'branch': 'master',
			}
		},
		'advduplicator': {
			'type': 'lua',
			'repo': {
				'type':'git',
				'remote': 'https://github.com/wiremod/advduplicator.git',
				# 'branch': 'master',
			}
		},
		'wire-extras': {
			'type': 'lua',
			'repo': {
				'type':'git',
				'remote': 'https://github.com/wiremod/wire-extras.git',
				# 'branch': 'master',
			}
		},
	},
	'git': {
		'config': {
			'remote': 'git@git.nexisonline.net:N3X15/gmod_config.git',
			'branch': 'master',
			'dirs': {
				'lua': 'lua',
				'cfg': 'cfg',
			}
		},
	},
	'nudge': {
		'id':'Test Server',
		'ip': 'localhost',
		'port': 45678,
		'key': 'my secret passcode'
	}
}
# @formatting:on

config = Config(os.path.join(os.getcwd(),'watchdog.yml'), default_config, template_dir='/', variables={
	'script_dir':script_dir,
	'home_dir':os.path.expanduser('~')
})
config.LoadFromFolder(os.path.join(os.getcwd(),'conf.d/'))
config.set('paths.script',script_dir)

LOGPATH = config.get('paths.crashlog', 'logs')

if not os.path.isdir(LOGPATH):
	os.makedirs(LOGPATH)
	
ldlp = os.environ.get('LD_LIBRARY_PATH', '')
if ldlp == '':
	ldlp = []
else:
	ldlp = ldlp.split(':')
ENV.set('LD_LIBRARY_PATH', ':'.join(config.get('env.LD_LIBRARY_PATH', '').split(':') + ldlp))
	
logFormatter = logging.Formatter(fmt='%(asctime)s [%(levelname)-8s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')  # , level=logging.INFO, filename='crashlog.log', filemode='a+')
log = logging.getLogger()
log.setLevel(logging.INFO)

fileHandler = logging.handlers.RotatingFileHandler(os.path.join(LOGPATH, 'crash.log'), maxBytes=1024 * 1024 * 50, backupCount=0)  # 50MB
fileHandler.setFormatter(logFormatter)
log.addHandler(fileHandler)

log = IndentLogger(log)
# consoleHandler = logging.StreamHandler()
# consoleHandler.setFormatter(logFormatter)
# log.addHandler(consoleHandler)

log.info('-' * 30)
log.info('Watchdog: Started.')
# send_nudge('Watchdog script restarted.')
lastState = True
failChain = 0
firstRun = True
waiting_for_next_commit = False

SteamContent.LoadDefs(os.path.join(script_dir,'games.d/'))

engine = GModEngine(config)

MAX_FAILURES = config.get('monitor.max-fails')

is_posix = platform.system() != 'Windows'

engine.find_process()
engine.applyUpdates(restart=False)
	
while True:
	if waiting_for_next_commit:
		engine.checkForUpdates()
		if waiting_for_next_commit:
			time.sleep(50)
			continue
	if not engine.pingServer():
		# try to start the server again
		if engine.checkForUpdates():
			# send_nudge('Updates detected, restarting.')
			log.warn('Updates detected')
			engine.applyUpdates(restart=False)
		failChain += 1
		if lastState == False:
			if failChain > MAX_FAILURES:
				# send_nudge('Script has failed to restart the server.')
				log.error('Too many failures, quitting!')
				sys.exit(1)
			log.error('Try {0}/{1}...'.format(failChain, MAX_FAILURES))
			# send_nudge('Try {0}/{1}...'.format(failChain, MAX_FAILURES))
		else:
			log.error("Detected a problem, attempting restart ({0}/{1}).".format(failChain, MAX_FAILURES))
			# send_nudge('Attempting restart ({0}/{1})...'.format(failChain, MAX_FAILURES))
		engine.end_process()
		engine.start_process()
		time.sleep(5)  # Sleep 50 seconds for a total of almost 2 minutes before we ping again.
		lastState = False
	else:
		if lastState == False:
			log.info('Server is confirmed to be back up and running.')
			# send_nudge('Server is back online and responding to queries.')
		if firstRun:
			log.info('Server is confirmed to be up and running.')
			# send_nudge('Server is online and responding to queries.')
		else:
			if engine.checkForUpdates():
				# send_nudge('Updates detected, restarting.')
				log.warn('Updates detected')
				engine.applyUpdates(restart=True)
		lastState = True
		failChain = 0
	firstRun = False
	time.sleep(50)  # 50 seconds between "pings".