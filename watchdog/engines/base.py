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
        cfg['dir']=os.path.join(utils.getCacheDir(), 'repos', 'config-' + uid)
        BasicAddon.__init__(self, 'config', cfg)
        self.rootdir = finaldir
    
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
            
    def start_process(self):
        return
                
    def updateContent(self):
        return
    
    def applyUpdates(self, restart=True):
        if restart and self.process and self.process.is_running():
            self.updateAlert()
        if restart: self.end_process()
        self.updateContent()
        self.updateAddons()
        self.updateConfig()
        if restart: self.start_process()
        
    def updateAddons(self): 
        with log.info('Updating addons...'):
            loadedAddons = {}
            newAddons = {}
            addonInfoFile = os.path.join(self.cache_dir, 'addons.yml')
            if os.path.isfile(addonInfoFile):
                with open(addonInfoFile, 'r') as f:
                    loadedAddons = yaml.load(f)
            for id, addon in self.addons.items():
                addon.update()
                newAddons[id] = addon.config
            for id, addonCfg in loadedAddons.items():
                if id not in newAddons:
                    with log.info('Removing dead addon %r...', id):
                        dest = self.config['paths']['addons'][addonCfg['type']]
                        addon = CreateAddon(id, addonCfg, dest)
                        addon.remove()
            with open(addonInfoFile, 'w') as f:
                yaml.dump(newAddons, f, default_flow_style=False)
        
    def _checkAddonsForUpdates(self):
        for id, addon in self.addons.items():
            if not addon.isUp2Date():
                log.warn('Addon %s is out of date!', id)
                return True
        
        if not self.configrepo.isUp2Date():
            log.warn('Configuration is out of date!')
            return True
        
        return False
    
    def checkForUpdates(self):
        if self.checkForContentUpdates():
            return True
        if self._checkAddonsForUpdates():
            return True
        return False
    
    def updateConfig(self):
        if self.configrepo is not None:
            with log.info('Updating configuration...'):
                self.configrepo.update()
            
    def updateAlert(self):
        pass
    
    def pingServer(self):
        return False
