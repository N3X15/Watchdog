'''
Copyright (c)2015 Rob "N3X15" Nelson <nexisentertainment@gmail.com>

MIT License Goes Here
'''

import logging
import logging.handlers
import os
import sys
import time
import platform
import importlib
import traceback
import argparse

# pip package => module list
import_packages = {
    'yaml': ['yaml'],
    'psutil': ['psutil'],
    'pyparsing': ['pyparsing'],
    'Jinja2': ['jinja2'],
    'lxml': ['lxml']
}


failed=[]
for pkg, modules in import_packages.items():
    try:
        for module in modules:
            importlib.import_module(module)
    except:
        failed.append(pkg)
        
if len(failed)>0:
    all_failed={k:v for k,v in import_packages if k in failed}
    print('Failed to import modules {modules}, which means some packages are not installed.  Please run "sudo pip install {pkgs}".'.format(modules=', '.join(all_failed.values()), pkgs=' '.join(all_failed.keys())))
    sys.exit(-1)

script_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(script_dir, 'lib', 'buildtools'))
sys.path.append(os.path.join(script_dir, 'lib', 'valve'))
# print(repr(sys.path))

import yaml

from watchdog import utils
from watchdog.engines import GetEngine
from watchdog.engines.steambase import SteamContent

from buildtools import os_utils, ENV
from buildtools.config import Config
from buildtools.bt_logging import IndentLogger

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run, monitor, and auto-update your game daemon.')
    parser.add_argument('--validate', action='store_true', help="Validate games on startup.")
    args = parser.parse_args()

    utils.script_dir = script_dir
    utils.config_dir = os.path.abspath(os.getcwd())
    
    logging.getLogger("requests").setLevel(logging.WARNING)

    try:
        cfgPath = os.path.join(utils.config_dir, 'watchdog.yml')
        if not os.path.isfile(cfgPath):
            print('ERROR: %s does not exist.  Please copy the desired configuration template from conf.templates, rename it to watchdog.yml, and edit it to taste.  Watchdog cannot start until this is done.', cfgPath)
            sys.exit(-1)

        jinja_vars = {
            'script_dir': script_dir,
            'home_dir': os.path.expanduser('~')
        }
        config = Config(cfgPath, {}, template_dir='/', variables=jinja_vars)
        config.LoadFromFolder(os.path.join(os.getcwd(), 'conf.d/'), variables=jinja_vars)
        config.set('paths.script', script_dir)
        
        with open(os.path.join(utils.getCacheDir(),'configuration.yml'),'w') as f:
            yaml.dump(config.cfg,f)

        #########################
        # Set up logging.

        logFormatter = logging.Formatter(fmt='%(asctime)s [%(levelname)-8s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')  # , level=logging.INFO, filename='crashlog.log', filemode='a+')
        log = logging.getLogger()

        logLevel = config.get('logging.level', 'INFO')
        if logLevel.upper() == 'INFO':
            log.setLevel(logging.INFO)
        elif logLevel.upper() == 'WARN' or logLevel.upper() == 'WARNING':
            log.setLevel(logging.WARN)
        elif logLevel.upper() == 'ERROR':
            log.setLevel(logging.ERROR)
        elif logLevel.upper() == 'DEBUG':
            log.setLevel(logging.DEBUG)

        LOGPATH = config.get('logging.log-path', os.path.join(os.getcwd(), 'logs', 'watchdog.log'))
        LOGMAXSIZE = config.get('logging.max-size', 1024 * 1024 * 50)  # 50MB
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

        SteamContent.LoadDefs(os.path.join(script_dir, 'games.d/'))

        # engine = GModEngine(config)
        engine = GetEngine(config, args)

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
    except:
        with open(os.path.join(script_dir, 'EXCEPTION.log'), 'w') as f:
            f.write(traceback.format_exc())
        print('UNHANDLED EXCEPTION:')
        print(traceback.format_exc())
