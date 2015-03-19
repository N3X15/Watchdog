'''
Created on Mar 12, 2015

@author: Rob
'''
import os, sys, yaml, re, tempfile

from watchdog.addon.source.base import SourceEngineAddon

from buildtools import http, os_utils
from buildtools.bt_logging import log
from buildtools.os_utils import Chdir

class SMOperatingSystem:
    WINDOWS = 'windows'
    LINUX = 'linux'
    MAC = 'mac'

@AddonType('sourcemod')
class SourceMod(SourceEngineAddon):
    '''
    SourceMod itself.
    '''

    def __init__(self, id, cfg, dest):
        super(GitAddon, self).__init__(id, cfg)

        self.smdrop_format = 'http://www.sourcemod.net/smdrop/{VERSION}/'
        # sourcemod-1.7.1-git5157-windows.zip
        self.reg_smdrop_filefields = re.compile('sourcemod-(?P<version>[0-9\.]+)-git(?P<build>[0-9]+)-(?P<os>windows|linux|osx)\.[a-z\.]+')
        
        self.os=''
        if sys.platform == 'win32':
            self.os = SMOperatingSystem.WINDOWS
        elif sys.platform == 'linux': 
            self.os = SMOperatingSystem.LINUX
        else:
            self.os = SMOperatingSystem.MAC
            
        self.versiongroup = cfg['version_group']
        self.destination=self.config.get('dir',self.gamedir)
        self.avail_versions={}
        
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
                self.current_url = cache['url'] 
                
    def SaveCache(self):
        cache={
            'build': self.current_version,
            'url': self.current_url,
        }
        with open('.smupdater', 'w') as f:
            yaml.dump(cache,f, default_flow_style=False)
        
    def isUp2Date(self):
        
        
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
            cmd(['wget','-O','sourcemod.tar.gz',self.update_url], echo=True, critical=True)
            cmd(['tar','xzvf','sourcemod.tar.gz'], echo=True, critical=True)
            os.remove('sourcemod.tar.gz')
            
            rsync_flags=[]
            if os.path.isdir(os.path.join(self.destdir,'addons','sourcemod','configs')):
                rsync_flags += ['--exclude=sourcemod/configs']
            cmd(['rsync','-zrav']+rsync_flags+['addons/',self.destdir], echo=True, critical=True)
        cmd(['rm','-rf',dirname])

    def Update(self, stable=True):
        with log.info('Searching for SM updates (%s):',self.versiongroup):
            latestBuild, latestURL = self.FindLatest(stable)
            log.info('Latest SM version: build %d',latestBuild,latestURL)
            log.info('Current SM version: build %d',self.current_version)
            if self.current_version != latestBuild:
                self.current_version=latestBuild
                self.update_url=latestURL
                self.SaveCache()
                self.ForceUpdate()