import psutil, os, hashlib, time, sys

from buildtools.bt_logging import log
from watchdog.addon import CreateAddon, BasicAddon
from buildtools import os_utils
import logging
from buildtools.wrapper.git import GitRepository
from watchdog.steamtools.vdf import VDFFile
import yaml
import traceback
from watchdog import utils

class ConfigAddon(BasicAddon):
    def __init__(self, cfg, finaldir):
        uid = hashlib.md5(finaldir).hexdigest()
        cfg['dir'] = os.path.join(utils.getCacheDir(), 'repos', 'config-' + uid)
        BasicAddon.__init__(self, 'config', cfg)
        self.rootdir = finaldir
        self.restartQueued = False
        
def _EngineType(_id=None):
    registry = {}
    def wrap(f):
        if _id is None:
            fname_p = f.__name__.split('_')
            _id = fname_p[1]
        registry[_id] = f
        # def wrapped_f(*args):
        #    return f(*args)
        # return wrapped_f
        return f
    wrap.all = registry
    return wrap

class EngineType(object):
    all = {}
    def __init__(self, _id=None):
        self.id = _id
    def __call__(self, f):
        if self.id is None:
            fname_p = f.__name__.split('_')
            self.id = fname_p[1].lower()
        log.info('Adding {0} as engine type {1}.'.format(f.__name__, self.id))
        EngineType.all[self.id] = f
        return f
    
class RestartPriority:
    ROUND_END = 0
    NOW = 1
    
class WatchdogEngine(object):
    Name = "Base"
    Version = 0000
    
    def __init__(self, cfg):
        self.config = cfg
        
        self.process = None
        self.processName = cfg.get('monitor.image')
        
        self.working_dir = os.getcwd()
        self.cache_dir = os.path.join(self.working_dir, 'cache')
        os_utils.ensureDirExists(self.cache_dir, mode=0700)
        
        BasicAddon.ClassDestinations = {}
        for classID, classDest in self.config['paths']['addons'].items():
            BasicAddon.ClassDestinations[classID] = classDest
        
        self.addons = {}
        for id, acfg in self.config['addons'].items():
            addon = CreateAddon(id, acfg)
            if addon.validate():
                self.addons[id] = addon
                
        self.configrepo = None
                
    def find_process(self):
        if self.process is None or not self.process.is_running():
            self.process = None
            for proc in psutil.process_iter():
                try:
                    if proc.name() == self.processName:
                        if proc.status() == psutil.STATUS_ZOMBIE:
                            log.warn('Detected zombie process #%s, skipping.', self.process.pid)
                            continue
                        self.process = proc
                        log.info('Found gameserver running as process #%s', self.process.pid)
                        break
                except psutil.AccessDenied:
                    continue
            
    def end_process(self):
        while self.process is not None and self.process.is_running():
            with log.info('Ending process #%d...', self.process.pid):
                self.process.terminate()
                self.process.wait(timeout=10)
                if self.process.is_running():
                    with log.warn('Process failed to close in a timely manner, sending kill signal...'):
                        self.process.kill()
                        self.process.wait(timeout=10)  # To clean up zombies
                self.process = None
                time.sleep(1)
                self.find_process()
        self.process = None
        self.restartQueued = False
            
    def start_process(self):
        return
                
    def updateContent(self):
        '''True when content has changed.'''
        return False
    
    def getRestartPriority(self, type, default='DELAY'):
        typeID = self.config.get('monitor.restart-type.' + type, 'delay').upper()
        if typeID in ('DELAY', 'DELAYED', 'ROUND', 'ROUND END', 'ROUND_END'): 
            return RestartPriority.ROUND_END
        elif typeID in ('IMMEDIATE', 'NOW'): 
            return RestartPriority.NOW
        
    def queueRestart(self):
        self.restartQueued = True
        
    def doUpdateCheck(self):
        restartNeeded, component=self.checkForUpdates()
        componentName=''
        if restartNeeded:
            p = self.getRestartPriority(component, defaultDelayType)
            if p == RestartPriority.NOW: 
                restartNeeded = True
                componentName = component
                if componentName == 'content':
                    componentName='game content'
            elif p == RestartPriority.ROUND_END and not self.restartQueued:
                self.queueRestart(component)
                restartNeeded=False
        
        if restartNeeded:
            # send_nudge('Updates detected, restarting.')
            log.warn('Updates detected')
            engine.updateAlert(componentName)
            engine.applyUpdates(restart=False)
    
    def applyUpdates(self, restart=True):
        if restart and self.process and self.process.is_running():
            self.updateAlert()
        if restart: self.end_process()
        
        restartNeeded = False
            
        if self.updateAddons(): restartNeeded=True
        if self.updateContent(): restartNeeded=True
        if self.updateConfig(): restartNeeded=True
        
        if restartNeeded and not restart:
            self.end_process()
            
        if restart: self.start_process()
        
    def updateAddons(self): 
        changed = False
        with log.info('Updating addons...'):
            loadedAddons = {}
            newAddons = {}
            addonInfoFile = os.path.join(self.cache_dir, 'addons.yml')
            if os.path.isfile(addonInfoFile):
                with open(addonInfoFile, 'r') as f:
                    loadedAddons = yaml.load(f)
            for id, addon in self.addons.items():
                if addon.update():
                    log.info('%s has changed! Triggering restart.', id)
                    changed = True
                if id not in loadedAddons:
                    log.info('%s is new! Triggering restart.', id)
                newAddons[id] = addon.config
            for id, addonCfg in loadedAddons.items():
                if id not in newAddons:
                    with log.info('Removing dead addon %r...', id):
                        addon = CreateAddon(id, addonCfg)
                        addon.remove()
                        changed = True
            with open(addonInfoFile, 'w') as f:
                yaml.dump(newAddons, f, default_flow_style=False)
        return changed
        
    def _checkAddonsForUpdates(self):
        for id, addon in self.addons.items():
            if not addon.isUp2Date():
                log.warn('Addon %s is out of date!', id)
                return True
        
        return False
    
    def checkForUpdates(self):
        if self.checkForContentUpdates():
            return True, 'content'
        if self._checkAddonsForUpdates():
            return True, 'addons'
        if not self.configrepo.isUp2Date():
            return True, 'config'
        return False, None
    
    def updateConfig(self):
        if self.configrepo is not None:
            with log.info('Updating configuration...'):
                if self.configrepo.update():
                    return True
        return False
            
    def updateAlert(self, typeID):
        pass
    
    def pingServer(self):
        return False
