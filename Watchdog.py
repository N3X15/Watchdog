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
from watchdog.engines import SourceEngine, GModEngine, GetEngine
from watchdog.engines.steam import SteamContent

from buildtools import *
from buildtools import os_utils
from buildtools.wrapper import Git
from buildtools.bt_logging import IndentLogger
from buildtools.wrapper.git import GitRepository
	
if __name__=='__main__':
	utils.script_dir=script_dir
	
	cfgPath = os.path.join(os.getcwd(),'watchdog.yml')
	if not os.path.isfile(cfgPath):
		print('ERROR: %s does not exist.  Please copy the desired configuration template from conf.templates, rename it to watchdog.yml, and edit it to taste.  Watchdog cannot start until this is done.', cfgPath)
		sys.exit(-1)
		
	config = Config(cfgPath, {}, template_dir='/', variables={
		'script_dir':script_dir,
		'home_dir'  :os.path.expanduser('~')
	})
	config.LoadFromFolder(os.path.join(os.getcwd(),'conf.d/'))
	config.set('paths.script',script_dir)
	
	#########################
	# Set up logging.
		
	logFormatter = logging.Formatter(fmt='%(asctime)s [%(levelname)-8s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')  # , level=logging.INFO, filename='crashlog.log', filemode='a+')
	log = logging.getLogger()
	
	logLevel = config.get('logging.level','INFO')
	if logLevel.upper() == 'INFO':
		log.setLevel(logging.INFO)
	elif logLevel.upper() == 'WARN' or logLevel.upper() == 'WARNING':
		log.setLevel(logging.WARN)
	elif logLevel.upper() == 'ERROR':
		log.setLevel(logging.ERROR)
	elif logLevel.upper() == 'DEBUG':
		log.setLevel(logging.DEBUG)
	
	LOGPATH = config.get('logging.log-path', os.path.join(os.getcwd(),'logs','watchdog.log'))
	LOGMAXSIZE = config.get('logging.max-size', 1024*1024*50)  # 50MB
	LOGNBACKUPS = config.get('logging.backup-count', 0)
	
	os_utils.ensureDirExists(os.path.dirname(LOGPATH), noisy=True)
	
	fileHandler = logging.handlers.RotatingFileHandler(LOGPATH, maxBytes=LOGMAXSIZE, backupCount=LOGNBACKUPS)
	fileHandler.setFormatter(logFormatter)
	log.addHandler(fileHandler)
		
	ldlp = os.environ.get('LD_LIBRARY_PATH', '')
	if ldlp == '':
		ldlp = []
	else:
		ldlp = ldlp.split(':')
	ENV.set('LD_LIBRARY_PATH', ':'.join(config.get('env.LD_LIBRARY_PATH', '').split(':') + ldlp))
	
	log = IndentLogger(log)
	# consoleHandler = logging.StreamHandler()
	# consoleHandler.setFormatter(logFormatter)
	# log.addHandler(consoleHandler)
	
	log.info('-' * 30)
	log.info('Watchdog: Started.')
	log.info('-' * 30)
	# send_nudge('Watchdog script restarted.')
	lastState = True
	failChain = 0
	firstRun = True
	waiting_for_next_commit = False
	
	SteamContent.LoadDefs(os.path.join(script_dir,'games.d/'))
	
	#engine = GModEngine(config)
	engine = GetEngine(config)
	
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
			engine.doUpdateCheck()
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
				engine.doUpdateCheck()
			lastState = True
			failChain = 0
		firstRun = False
		time.sleep(50)  # 50 seconds between "pings".
