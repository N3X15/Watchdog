'''
Created on Mar 12, 2015

@author: Rob
'''
import os, sys, yaml, re, tempfile

from watchdog.addon.source.base import SourceEngineAddon

from buildtools import http, os_utils, timing
from buildtools.bt_logging import log
from buildtools.os_utils import Chdir

class AMOperatingSystem:
    WINDOWS = 'windows'
    LINUX = 'linux'
    MAC = 'mac'

timing.SetupYaml()

#@AddonType('sourcemod')
class AlliedModdersBase(SourceEngineAddon):
    '''Base for source engine mods released by Allied Modders (SourceMod, etc)'''
    MODID='base' # Unique ID of the mod.  Used for caches.
    CHECK_DELAY=60*5 # 5 minutes
    DROP_FORMAT='' # 'http://www.sourcemod.net/smdrop/{VERSION}/'
    DROP_FILE_EXPRESSION=None #re.compile('sourcemod-(?P<version>[0-9\.]+)-git(?P<build>[0-9]+)-(?P<os>windows|linux|osx)\.[a-z\.]+')
    def __init__(self, id, cfg, dest):
        super(AlliedModdersBase, self).__init__(id, cfg)

        self.os=''
        if sys.platform == 'win32':
            self.os = AMOperatingSystem.WINDOWS
        elif sys.platform == 'linux': 
            self.os = AMOperatingSystem.LINUX
        else:
            self.os = AMOperatingSystem.MAC
            
        self.versiongroup = cfg['version_group']
        
        self.cache_dir=os.path.join('cache',self.MODID)
        self.cache_data = os.path.join(self.cache_dir,'AlliedModdersBase.yml')
        os_utils.ensureDirExists(self.cache_dir, mode=755)
        
        self.updateCheckDelay = timing.SimpleDelayer(MODID+'.update',min_delay=self.CHECK_DELAY)
        self.destination=self.config.get('dir',self.gamedir)
        self.avail_versions={}
        
        self.current_version=None
        self.update_url=None
        
        self.preload()
        
    def preload(self):
        self.avail_versions = {
            SMOperatingSystem.LINUX: [],
            SMOperatingSystem.MAC: [],
            SMOperatingSystem.WINDOWS: [],
        }
        
        self.current_version = 0
        self.current_url = None
        
        if os.path.isfile('.smupdater'):
            cache = {}
            with open('.smupdater', 'r') as f:
                cache = yaml.load(f)
            if 'build' in cache:
                self.current_version = cache['build'] 
            if 'url' in cache:
                self.update_url = cache['url'] 
            if 'delay' in cache:
                self.updateCheckDelay = cache['delay']
                self.updateCheckDelay.minDelay=self.CHECK_DELAY 
                
    def SaveCache(self):
        cache={
            'build': self.current_version,
            'url': self.update_url,
            'delay': self.updateCheckDelay
        }
        with open('.smupdater', 'w') as f:
            yaml.dump(cache,f, default_flow_style=False)
        
    def isUp2Date(self):
        latestBuild, latestURL = self._updateCheck(stable)
        #log.info('Latest SM version: build %d',latestBuild,latestURL)
        #log.info('Current SM version: build %d',self.current_version)
        return self.current_version == latestBuild
        
        
    def _updateCheck(self, stable=True):
        self.base_uri = self.smdrop_format.format(VERSION=self.versiongroup)
        req = http.HTTPFetcher(self.base_uri)
        txt = req.GetString()
        for match in self.reg_smdrop_filefields.finditer(txt):
            version = (int(m.group('build')),self.base_uri+match.group(0))
            osID = m.group('os')
            if version not in self.avail_versions[osID]: 
                self.avail_versions[osID].append(version)
        latestStableBuild = 0
        latestStableURL = ''
        latestAnyBuild = 0
        latestAnyURL = ''
        for build, url in self.avail_versions[self.os]:
            if build > latestAnyBuild: 
                latestAnyBuild = build
                latestAnyURL = url
            if build in self.avail_versions[SMOperatingSystem.LINUX] and build in self.avail_versions[SMOperatingSystem.MAC] and build in self.avail_versions[SMOperatingSystem.WINDOWS]:
                if build > latestStableBuild: 
                    latestStableBuild = build
                    latestStableURL = url
        if stable:
            return latestStableBuild, latestStableURL
        else:
            return latestAnyBuild, latestAnyURL
    
    def ForceUpdate(self):
        dirname = tempfile.mkdtemp(prefix='smupdate')
        with Chdir(dirname):
            cmd(['wget','-O',self.MODID+'.tar.gz',self.update_url], echo=True, critical=True)
            cmd(['tar','xzvf',self.MODID+'.tar.gz'], echo=True, critical=True)
            os.remove(self.MODID+'.tar.gz')
            
            rsync_flags=[]
            if os.path.isdir(os.path.join(self.destdir,'addons','sourcemod','configs')):
                rsync_flags += ['--exclude=sourcemod/configs']
            cmd(['rsync','-zrav']+rsync_flags+['addons/',self.destdir], echo=True, critical=True)
        cmd(['rm','-rf',dirname])

    def Update(self, stable=True):
        with log.info('Searching for %s updates (%s):',self.MODID,self.versiongroup):
            latestBuild, latestURL = self._updateCheck(stable)
            log.info('Latest %s version: build %d',self.MODID,latestBuild,latestURL)
            log.info('Current %s version: build %d',self.MODID,self.current_version)
            if self.current_version != latestBuild:
                self.current_version=latestBuild
                self.update_url=latestURL
                self.SaveCache()
                self.ForceUpdate()