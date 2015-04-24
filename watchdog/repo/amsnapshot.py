from watchdog.repo.base import RepoType, RepoDir
import os
import sys
import yaml
import re

from buildtools import http, os_utils, timing
from buildtools.bt_logging import log
import tempfile
from buildtools.os_utils import cmd, Chdir
from urlparse import urlparse


class AMOperatingSystem:  # IGNORE:no-init (it's an enum, chucklefuck)
    WINDOWS = 'windows'
    LINUX = 'linux'
    MAC = 'mac'

timing.SetupYaml()

@RepoType('amsnapshot')
class AlliedModdersSnapshot(RepoDir):
    '''Base for source engine mods released by Allied Modders (SourceMod, etc)'''
    
    CHECK_DELAY = 60 * 5  # 5 minutes

    def __init__(self, addon, cfg, dest):
        super(AlliedModdersSnapshot, self).__init__(addon, cfg, dest)

        self.os = ''
        if sys.platform == 'win32':
            self.os = AMOperatingSystem.WINDOWS
        elif sys.platform.startswith('linux'):  # Because Debian thinks "linux2" is a good platform name.
            self.os = AMOperatingSystem.LINUX
        else:
            self.os = AMOperatingSystem.MAC

        # self.gamedir = os.path.expanduser(engine.config.get('paths.addons.source-addons'))

        self.versiongroup = cfg['version-group']
        self.drop_regex = re.compile(cfg['drop-regex'])
        self.drop_format = cfg['drop-format']
        self.copydirs = cfg.get('drop-format',['addons/'])

        self.cache_data = os.path.join(self.cache_dir, self.__class__.__name__ + '.yml')
        os_utils.ensureDirExists(self.cache_dir, mode=0o755)

        self.updateCheckDelay = timing.SimpleDelayer(self.addon.id + '.update', min_delay=self.CHECK_DELAY)
        self.avail_versions = {}

        self.current_version = None
        self.update_url = None
        self.base_uri = None

        self.preload()

    def validate(self):
        return RepoDir.validate(self)

    def preload(self):
        self.avail_versions = {
            AMOperatingSystem.LINUX: [],
            AMOperatingSystem.MAC: [],
            AMOperatingSystem.WINDOWS: [],
        }

        self.current_version = 0
        self.current_url = None
        self.current_destination = ''
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
            if 'destination' in cache:
                self.current_destination = cache['destination']

        if self.current_destination != self.destination:
            self.current_version = -1
            log.warn('Destination changed, forcing re-install.')

    def SaveCache(self):
        cache = {
            'build': self.current_version,
            'url': self.update_url,
            'delay': self.updateCheckDelay,
            'destination': self.destination
        }
        with open(self.cache_data, 'w') as f:
            yaml.dump(cache, f, default_flow_style=False)

    def isUp2Date(self):
        if self.updateCheckDelay.Check(quiet=True):
            return True
        latestBuild, _ = self._updateCheck()
        # log.info('Latest SM version: build %d',latestBuild,latestURL)
        # log.info('Current SM version: build %d',self.current_version)
        return self.current_version == latestBuild

    def _updateCheck(self):
        self.base_uri = self.drop_format.format(VERSION=self.versiongroup)
        with log.debug('Checking %s...', self.base_uri):
            req = http.HTTPFetcher(self.base_uri)
            # req.debug=True
            req.accept = ['*/*']
            req.useragent = 'Wget/1.16 (linux-gnu)'  # Fuck you, AM.
            req.referer = self.base_uri
            txt = req.GetString()
            for match in self.drop_regex.finditer(txt):
                version = int(match.group('build'))
                url = self.base_uri + match.group(0)
                osID = match.group('os')
                if version not in self.avail_versions[osID]:
                    self.avail_versions[osID].append((version, url))
                    #log.info('%s []= %s (%s)',osID,version,url)
            if len(self.avail_versions) == 0:
                with log.error('UNABLE TO FIND MATCHES FOR %s AT %s', self.drop_format, self.base_uri):
                    dbgFilename = os.path.join(self.cache_dir, 'recv.htm')
                    with open(dbgFilename, 'w') as f:
                        f.write(txt)
                    log.info('Wrote %s.', dbgFilename)
        latestStableBuild = 0
        #latestStableURL = ''
        latestAnyBuild = 0
        latestAnyURL = ''
        for build, url in self.avail_versions[self.os]:
            # print(build,url)
            if build > latestAnyBuild:
                latestAnyBuild = build
                latestAnyURL = url
            if build in self.avail_versions[AMOperatingSystem.LINUX] and build in self.avail_versions[AMOperatingSystem.MAC] and build in self.avail_versions[AMOperatingSystem.WINDOWS]:
                if build > latestStableBuild:
                    latestStableBuild = build
                    #latestStableURL = url
        assert latestAnyBuild > 0
        # if stable:
        # return latestStableBuild, latestStableURL
        # else:
        return latestAnyBuild, latestAnyURL

    def ForceUpdate(self):
        success = False
        with log.info('Updating addon %s from AlliedModders...', self.addon.id):
            dirname = tempfile.mkdtemp(prefix='amsnap')
            with Chdir(dirname):
                os_utils.ensureDirExists(self.destination)
                _, _, path, _, _, _ = urlparse(self.update_url)
                filename = path.split('/')[-1]
                cmd(['wget', '-O', filename, self.update_url], echo=True, critical=True)
                if filename.endswith('.tar.gz'):
                    cmd(['tar', 'xzf', filename], echo=True, critical=True)
                elif filename.endswith('.tar.bz'):
                    cmd(['tar', 'xjf', filename], echo=True, critical=True)
                elif filename.endswith('.tar.xz'):
                    cmd(['tar', 'xJf', filename], echo=True, critical=True)
                elif filename.endswith('.tar.7z'):
                    cmd(['7za', 'x', filename], echo=True, critical=True)
                    cmd(['tar', 'xf', filename[:-3]], echo=True, critical=True)
                    os.remove(filename[:-3])
                elif filename.endswith('.zip'):
                    cmd(['unzip', filename], echo=True, critical=True)
                os.remove(filename)

                rsync_flags = []
                
                for xdir in self.config.get('exclude', []):
                    rsync_flags.append('--exclude=' + xdir)
                rsync_flags += os_utils._cmd_handle_args(self.config.get('copy-from',['addons/*']))
                    
                cmd(['rsync', '-zrav'] + rsync_flags + [self.destination], echo=True, critical=True)

                self.SaveCache()
                success = True
            cmd(['rm', '-rf', dirname])
        return success

    def update(self):
        #super(AlliedModdersSnapshot, self).update()
        with log.info('Searching for %s updates (%s):', self.addon.id, self.versiongroup):
            latestBuild, latestURL = self._updateCheck()
            log.info('Latest %s version: build %r', self.addon.id, latestBuild)
            log.info('Current %s version: build %r', self.addon.id, self.current_version)
            if self.current_version != latestBuild:
                self.update_url = latestURL
                self.ForceUpdate()
                self.current_version = latestBuild
                self.SaveCache()
                return True
        return False
