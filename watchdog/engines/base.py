import psutil, os, hashlib, time, sys

from buildtools.bt_logging import log
from watchdog.addon import CreateAddon
from watchdog.addon.git import GitAddon
from buildtools import os_utils
import logging
from buildtools.wrapper.git import GitRepository
from watchdog.steamtools.vdf import VDFFile
import yaml

class ConfigRepo(GitAddon):
    def __init__(self, cfg, finaldir):
        uid = hashlib.md5(finaldir).hexdigest()
        cfg={'repo':cfg}
        super(ConfigRepo, self).__init__('config', cfg, finaldir)
        self.rootdir = finaldir
        self.destination = os.path.expanduser('~/.smrepos/config-' + uid)
        self.repo = GitRepository(self.destination, self.remote)
        # print('CONFIG {} @ {}'.format(id, self.destination))
    
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
        
        self.addons = {}
        for id, acfg in self.config['addons'].items():
            dest = self.config['paths']['addons'][acfg['type']]
            addon = CreateAddon(id, acfg, dest)
            if addon.validate():
                self.addons[id] = addon
                
        self.configrepo = None
                
    def find_process(self):
        if self.process is None or not self.process.is_running():
            self.process = None
            for proc in psutil.process_iter():
                try:
                    if proc.name() == self.processName:
                        self.process = proc
                        log.info('Found gameserver running as process #%s', self.process.pid)
                        break
                except psutil.AccessDenied:
                    continue
            
    def end_process(self):
        with log.info('Killing server...'):
            while self.process is not None and self.process.is_running():
                log.info('Killing process #%d...', self.process.pid)
                self.process.kill()
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
