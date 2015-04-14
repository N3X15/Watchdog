import psutil, os, hashlib, time
import yaml

from buildtools.bt_logging import log
from watchdog.addon import CreateAddon, BasicAddon
from buildtools import os_utils
from watchdog import utils
from watchdog.utils import Event
from watchdog.plugin import CreatePlugin

class ConfigAddon(BasicAddon):
    def __init__(self, engine, cfg, finaldir):
        uid = hashlib.md5(finaldir).hexdigest()
        cfg['dir'] = os.path.join(utils.getCacheDir(), 'repos', 'config-' + uid)
        cfg['type'] = 'config'
        BasicAddon.__init__(self, engine, 'config', cfg)
        self.restartQueued = False
        
        self.validate()
        self.repo.rootdir = self.engine.config['paths']['config']

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
    
class RestartPriority: #IGNORE:no-init (It's an enum)
    ROUND_END = 0
    NOW = 1
    
class WatchdogEngine(object):
    Name = "Base"
    Version = 0000
    RestartOnChange=False
    
    def __init__(self, cfg):
        self.config = cfg
        
        self.process = None
        self.processName = cfg.get('monitor.image')
        
        self.working_dir = os.getcwd()
        self.cache_dir = os.path.join(self.working_dir, 'cache')
        os_utils.ensureDirExists(self.cache_dir)
        
        BasicAddon.ClassDestinations = {}
        for classID, classDest in self.config['paths']['addons'].items():
            BasicAddon.ClassDestinations[classID] = classDest
        
        self.addons = {}
        for aid, acfg in self.config['addons'].items():
            addon = CreateAddon(self, aid, acfg)
            if addon and addon.validate():
                self.addons[aid] = addon
            else:
                log.error('Addon %s failed to load.',aid)
                
        self.configrepo = None
        self.restartQueued = False
        
        self.plugins = {}
        self._initialized=False
        #: No args
        self.initialized = Event()
        for plid, plcfg in self.config.get('plugins',{}).items():
            self.load_plugin(plid,plcfg)
        
        # EVENTS
        ################
        
        #: No args.
        self.updated = Event()
        #: addon_names(list)
        self.addons_updated = Event()
        #: line(LogLine) 
        self.log_received = Event()
        
    def load_plugin(self,plID,plCfg=None):
        plugin = CreatePlugin(plID, self, plCfg)
        if plugin:
            self.plugins[plID] = plugin
        else:
            log.error('Plugin %s failed to load.',plID)
                
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
    
    def getRestartPriority(self, typeName, default='DELAY'):
        typeID = self.config.get('monitor.restart-type.' + typeName, default).upper()
        if typeID in ('DELAY', 'DELAYED', 'ROUND', 'ROUND END', 'ROUND_END'): 
            return RestartPriority.ROUND_END
        elif typeID in ('IMMEDIATE', 'NOW'): 
            return RestartPriority.NOW
        
    def queueRestart(self, _):
        self.restartQueued = True
        
    def doUpdateCheck(self):
        restartNeeded, component = self.checkForUpdates()
        if restartNeeded:
            self.restartIfNeeded(component)
            
    def restartIfNeeded(self, component):
        restartNeeded=False
        componentName = ''

        p = self.getRestartPriority(component, 'now')
        if p == RestartPriority.NOW: 
            restartNeeded = True
            componentName = component
            if componentName == 'content':
                componentName = 'game content'
        elif p == RestartPriority.ROUND_END and not self.restartQueued:
            self.queueRestart(component)
            restartNeeded = False
        
        if restartNeeded:
            # send_nudge('Updates detected, restarting.')
            log.warn('Updates detected')
            self.updateAlert(componentName)
            self.applyUpdates(restart=True)
    
    def applyUpdates(self, restart=True):
        if restart: 
            self.end_process()
        
        restartComponent = None
            
        if self.updateContent(): 
            restartComponent = 'content'
        if self.updateAddons(): 
            restartComponent = 'addon'
        if self.updateConfig(): 
            restartComponent = 'config'
        
        if restartComponent is not None and not restart:
            #self.end_process()
            #restart=True
            self.restartIfNeeded(restartComponent)
            
        if restart: 
            self.start_process()
        
    def updateAddons(self): 
        '''Returns True when an addon has changed.'''
        changed = False
        updated_addons=[]
        with log.info('Updating addons...'):
            loadedAddons = {}
            newAddons = {}
            addonInfoFile = os.path.join(self.cache_dir, 'addons.yml')
            if os.path.isfile(addonInfoFile):
                with open(addonInfoFile, 'r') as f:
                    loadedAddons = yaml.load(f)
            for aid, addon in self.addons.items():
                if addon.update():
                    log.info('%s has changed! Triggering restart.', aid)
                    changed = True
                    updated_addons.append(aid)
                if aid not in loadedAddons:
                    log.info('%s is new! Triggering restart.', aid)
                    changed = True
                newAddons[aid] = addon.config
            for aid, addonCfg in loadedAddons.items():
                if aid not in newAddons:
                    with log.info('Removing dead addon %r...', aid):
                        addon = CreateAddon(self, aid, addonCfg)
                        addon.remove()
                        changed = True
            with open(addonInfoFile, 'w') as f:
                yaml.dump(newAddons, f, default_flow_style=False)
        self.addons_updated.fire(addon_names=updated_addons)
        return changed
        
    def _checkAddonsForUpdates(self):
        for aid, addon in self.addons.items():
            if not addon.isUp2Date():
                log.warn('Addon %s is out of date!', aid)
                return True
        
        return False
    
    def checkForContentUpdates(self):
        return
    
    def checkForUpdates(self):
        if self.checkForContentUpdates():
            return True, 'content'
        if self._checkAddonsForUpdates():
            return True, 'addons'
        if self.configrepo and not self.configrepo.isUp2Date():
            return True, 'config'
        return False, None
    
    def updateConfig(self):
        if self.configrepo is not None:
            with log.info('Updating configuration...'):
                if self.configrepo.update():
                    return True
        return False
            
    def updateAlert(self, typeID=None):
        pass
    
    def pingServer(self):
        return False
