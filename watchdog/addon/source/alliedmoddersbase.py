'''
Created on Mar 12, 2015

@author: Rob
'''
import os, sys, yaml, re, tempfile

from watchdog.addon.source.base import SourceEngineAddon
from watchdog.addon.base import BasicAddon

from buildtools import http, os_utils, timing
from buildtools.bt_logging import log
from buildtools.os_utils import Chdir

class AMOperatingSystem:
    WINDOWS = 'windows'
    LINUX = 'linux'
    MAC = 'mac'

timing.SetupYaml()

# @AddonType('sourcemod')
class AlliedModdersBase(SourceEngineAddon):
    '''Base for source engine mods released by Allied Modders (SourceMod, etc)'''
    MODID = 'base'  # Unique ID of the mod.  Used for caches. CHECK getID(), NOT THIS.
    CHECK_DELAY = 60 * 5  # 5 minutes
    DROP_FORMAT = ''  # 'http://www.sourcemod.net/smdrop/{VERSION}/'
    def getID(self):
        return self.MODID
    def __init__(self, engine, id, cfg):
        super(AlliedModdersBase, self).__init__(engine, id, cfg)
        
        self.DROP_FILE_EXPRESSION = None

        self.os = ''
        if sys.platform == 'win32':
            self.os = AMOperatingSystem.WINDOWS
        elif sys.platform.startswith('linux'):  # Because Debian thinks "linux2" is a good platform name.
            self.os = AMOperatingSystem.LINUX
        else:
            self.os = AMOperatingSystem.MAC
            
        # self.gamedir = os.path.expanduser(engine.config.get('paths.addons.source-addons'))
            
        self.versiongroup = cfg['version_group']
        
        self.cache_dir = os.path.join(self.engine.cache_dir,self.getID())  # os.path.join(self.engine.gamedir, 'cache', self.getID())
        self.cache_data = os.path.join(self.cache_dir, 'AlliedModdersBase.yml')
        os_utils.ensureDirExists(self.cache_dir, mode=0o755)
        
        self.updateCheckDelay = timing.SimpleDelayer(self.getID() + '.update', min_delay=self.CHECK_DELAY)
        self.destination = BasicAddon.ClassDestinations['source-addon']
        self.avail_versions = {}
        
        self.current_version = None
        self.update_url = None
        
        self.preload()
        
    def validate(self):
        return True
        
    def preload(self):
        self.avail_versions = {
            AMOperatingSystem.LINUX: [],
            AMOperatingSystem.MAC: [],
            AMOperatingSystem.WINDOWS: [],
        }
        
        self.current_version = 0
        self.current_url = None
        
        if os.path.isfile(self.cache_data):
            cache = {}
            with open(self.cache_data, 'r') as f:
                cache = yaml.load(f)
            if 'build' in cache:
                self.current_version = cache['build'] 
            if 'url' in cache:
                self.update_url = cache['url'] 
            if 'delay' in cache:
                self.updateCheckDelay = cache['delay']
                self.updateCheckDelay.minDelay = self.CHECK_DELAY 
                
    def SaveCache(self):
        cache = {
            'build': self.current_version,
            'url': self.update_url,
            'delay': self.updateCheckDelay
        }
        with open(self.cache_data, 'w') as f:
            yaml.dump(cache, f, default_flow_style=False)
        
    def isUp2Date(self):
        if self.updateCheckDelay.Check(quiet=True): return True
        latestBuild, latestURL = self._updateCheck(stable)
        # log.info('Latest SM version: build %d',latestBuild,latestURL)
        # log.info('Current SM version: build %d',self.current_version)
        return self.current_version == latestBuild
        
        
    def _updateCheck(self):
        self.base_uri = self.DROP_FORMAT.format(VERSION=self.versiongroup)
        with log.info('Checking %s...',self.base_uri):
            req = http.HTTPFetcher(self.base_uri)
            #req.debug=True
            req.accept=['*/*']
            req.useragent='Wget/1.16 (linux-gnu)' # Fuck you, AM.
            req.referer = self.base_uri
            txt = req.GetString()
            for match in self.DROP_FILE_EXPRESSION.finditer(txt):
                version = int(match.group('build'))
                url = self.base_uri + match.group(0)
                osID = match.group('os')
                if version not in self.avail_versions[osID]: 
                    self.avail_versions[osID].append((version,url))
                    #log.info('%s []= %s (%s)',osID,version,url)
            if len(self.avail_versions)==0:
                with log.error('UNABLE TO FIND MATCHES FOR %s AT %s',self.DROP_FILE_EXPRESSION,self.base_uri):
                    dbgFilename=os.path.join(self.cache_dir,'recv.htm')
                    with open(dbgFilename,'w') as f:
                        f.write(txt)
                    log.info('Wrote %s.',dbgFilename)
        latestStableBuild = 0
        latestStableURL = ''
        latestAnyBuild = 0
        latestAnyURL = ''
        for build, url in self.avail_versions[self.os]:
            #print(build,url)
            if build > latestAnyBuild: 
                latestAnyBuild = build
                latestAnyURL = url
            if build in self.avail_versions[AMOperatingSystem.LINUX] and build in self.avail_versions[AMOperatingSystem.MAC] and build in self.avail_versions[AMOperatingSystem.WINDOWS]:
                if build > latestStableBuild: 
                    latestStableBuild = build
                    latestStableURL = url
        assert latestAnyBuild > 0
        # if stable:
        #return latestStableBuild, latestStableURL
        # else:
        return latestAnyBuild, latestAnyURL
    
    def ForceUpdate(self):
        return

    def update(self):
        with log.info('Searching for %s updates (%s):', self.getID(), self.versiongroup):
            latestBuild, latestURL = self._updateCheck()
            log.info('Latest %s version: build %r', self.getID(), latestBuild)
            log.info('Current %s version: build %r', self.getID(), self.current_version)
            if self.current_version != latestBuild:
                self.update_url = latestURL
                self.ForceUpdate()
                self.current_version = latestBuild
                self.SaveCache()
