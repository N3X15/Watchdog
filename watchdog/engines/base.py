import psutil
import os
import hashlib
import time
import yaml

from buildtools.bt_logging import log
from watchdog.addon import CreateAddon, BasicAddon
from buildtools import os_utils
from watchdog import utils
from watchdog.utils import Event
from watchdog.plugin import CreatePlugin
from collections import OrderedDict


class ConfigAddon(BasicAddon):

    def __init__(self, engine, cfg, finaldir):
        uid = hashlib.md5(finaldir).hexdigest()

        cfg['dir'] = os.path.join(utils.getCacheDir(), 'repos', 'config-' + uid)
        BasicAddon.ClassDestinations['config'] = cfg['dir']

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


class RestartPriority:  # IGNORE:no-init (It's an enum)
    ROUND_END = 0
    NOW = 1


class WatchdogEngine(object):
    Name = "Base"
    Version = 0000
    RestartOnChange = False

    def __init__(self, cfg, args):
        self.config = cfg
        self.cmdline_args = args

        self.process = None
        self.processName = cfg.get('monitor.image')

        self.working_dir = os.getcwd()
        self.cache_dir = os.path.join(self.working_dir, 'cache')
        os_utils.ensureDirExists(self.cache_dir)

        BasicAddon.ClassDestinations = {}
        for classID, classDest in self.config.get('paths.addons', {}).items():
            BasicAddon.ClassDestinations[classID] = classDest

        self.update_only = self.config.get('daemon.update-only', False)
        if self.update_only:
            with log.warn('Watchdog is in update-only mode.  The server will not be (re)started.'):
                log.warn('If this behavior is unintended, please set daemon.update-only to false.')

        self.addons = {}
        self.addon_files={}
        self.old_files={}
        self.addons_dirty = False
        self.loadAddons()
        for addon in self.addons.values():
            addon.validate()

        self.configrepo = None
        self.restartQueued = False

        self.plugins = {}
        self._initialized = False
        # : No args
        self.initialized = Event()

        for plid, plcfg in self.config.get('plugins', {}).items():
            self.load_plugin(plid, plcfg)

        # EVENTS
        ################

        # : No args.
        self.updated = Event()
        # : addon_names(list)
        self.addons_updated = Event()
        # : line(LogLine)
        self.log_received = Event()

    def load_plugin(self, plID, plCfg=None):
        plugin = CreatePlugin(plID, self, plCfg)
        if plugin:
            self.plugins[plID] = plugin
        else:
            log.error('Plugin %s failed to load.', plID)

    def loadAddons(self):
        self.addons = {}
        for aid, acfg in self.config.get('addons', {}).items():
            addon = CreateAddon(self, aid, acfg)
            if addon:
                self.addons[aid] = addon
            else:
                log.error('Addon %s failed to load.', aid)
        self.sort_addon_dependencies()
        self.addons_dirty = False

    def sort_addon_dependencies(self):
        new_addons = OrderedDict()
        broken_addons = []

        addonsLeft = len(self.addons)

        it = 0
        while addonsLeft > 0:
            it += 1
            for addonID, addon in self.addons.items():
                if addonID in new_addons:
                    continue
                if addonID in broken_addons:
                    continue
                deps = addon.dependencies
                if len(deps) == 0:
                    new_addons[addonID] = addon
                    addonsLeft -= 1
                    # log.info('[%d] Added %s (0 deps)',it, addonID)
                    continue

                defer = False
                for dep in deps:
                    if dep not in self.addons:
                        log.error('UNABLE TO ADD ADDON %s: DEPENDENCY %r IS NOT AVAILABLE.', addonID, dep)
                        #log.error('AVAILABLE: %r',self.addons.keys())
                        broken_addons.append(addonID)
                        addonsLeft -= 1
                        defer = True
                        break
                    if dep not in new_addons:
                        defer = True
                        break
                if defer:
                    continue
                new_addons[addonID] = addon
                addonsLeft -= 1
                # log.info('[%d] Added %s (%d deps)',it, addonID, len(deps))
        self.addons = new_addons

    def find_process(self):
        if not self.update_only and self.process is None or not self.process.is_running():
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
        while not self.update_only and self.process is not None and self.process.is_running():
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
        restartNeeded = False
        componentName = ''

        p = self.getRestartPriority(component, "NOW")
        log.info('Restart priority for %s: %s', component, "NOW" if p == RestartPriority.NOW else "ROUND_END")
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
            
    def updateFiles(self, oldfiles, new_only=False):
        with log.info('Installing new files...'):
            for destfile, filemeta in self.addon_files.iteritems():
                self.addons[filemeta['addon']].performInstallFile(filemeta['source'],destfile)
                if destfile in oldfiles:
                    oldfiles.remove(destfile)
        if not new_only:
            with log.info('Removing outdated files...'):
                for oldfile in oldfiles:
                    if os.path.isfile(oldfile) or os.path.islink(oldfile):
                        log.info('rm %s',oldfile)
                        os.remove(oldfile)

    def applyUpdates(self, restart=True):
        if restart and not self.update_only:
            self.end_process()

        restartComponent = None

        if self.updateContent():
            restartComponent = 'content'
        self.old_files=list(self.addon_files.keys())
        self.addon_files={}
        if self.updateAddons():
            restartComponent = 'addon'
        if self.updateConfig():
            restartComponent = 'config'
            
        self.updateFiles(self.old_files)

        if not self.update_only:
            if restartComponent is not None and not restart:
                # self.end_process()
                # restart=True
                self.restartIfNeeded(restartComponent)

            if restart:
                self.start_process()

    def updateAddons(self):
        '''Returns True when an addon has changed.'''
        changed = False
        updated_addons = []
        new_addons=[]
        with log.info('Updating addons...'):
            loadedAddons = {}
            foundAddons = {}
            addonInfoFile = os.path.join(self.cache_dir, 'addons.yml')
            if os.path.isfile(addonInfoFile):
                with open(addonInfoFile, 'r') as f:
                    loadedAddons = yaml.load(f)
            for aid, addon in self.addons.items():
                addon.loadFileCache()
                if addon.update():
                    log.info('%s has changed! Triggering restart.', aid)
                    changed = True
                    updated_addons.append(aid)
                elif aid not in loadedAddons:
                    #if addon.update(): - Breaks shit
                    log.info('%s is new! Triggering restart.', aid)
                    changed = True
                    new_addons.append(aid)
                addon.commitInstall(self.addon_files)
                foundAddons[aid] = addon.config
            for aid, addonCfg in loadedAddons.items():
                if aid not in foundAddons:
                    with log.info('Removing dead addon %r...', aid):
                        addon = CreateAddon(self, aid, addonCfg, removing=True)
                        addon.remove()
                        changed = True
            with open(addonInfoFile, 'w') as f:
                yaml.dump(foundAddons, f, default_flow_style=False)
        if self.addons_dirty:
            with log.info('Reloading addons...'):
                self.loadAddons()
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

    def tryPing(self, tryNum, maxTries, noisy):
        return False

    def pingServer(self, noisy=False):
        if self.process is None or not self.process.is_running():
            return False

        maxtries = self.config.get('monitor.ping-tries', 3)
        for trynum in range(maxtries):
            if self.tryPing(trynum, maxtries, noisy):
                return True
            else:
                noisy = True  # PANIC
        return False
