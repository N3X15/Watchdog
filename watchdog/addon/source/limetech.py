'''
Created on Mar 12, 2015

@author: Rob
'''
import os, sys, yaml, re, tempfile

from watchdog.addon.source.base import SourceEngineAddon

from buildtools import http, os_utils
from buildtools.bt_logging import log
from buildtools.os_utils import Chdir, cmd
from watchdog.addon.source.alliedmoddersbase import AlliedModdersBase, AMOperatingSystem
from watchdog.addon.base import AddonType

@AddonType('limetech_ext')
class LimetechExt(AlliedModdersBase):
    
    MODID = 'LimetechExtensions'
    DROP_FORMAT = 'https://builds.limetech.org/files/'

    def __init__(self, engine, id, cfg):
        super(LimetechExt, self).__init__(engine, id, cfg)
        
        # steamtools-0.9.0-git170-2d26276-windows.zip
        self.DROP_FILE_EXPRESSION = re.compile(id+'-(?P<version>[0-9\.]+)-git(?P<build>[0-9]+)-[a-f0-9]+-(?P<os>windows|linux|mac)\.(?P<ext>[a-z\.]+)')

        self.drop_ext = '.zip'
        if self.os == AMOperatingSystem.LINUX:
            self.drop_ext = '.tar.gz'
    
    def ForceUpdate(self):
        dirname = tempfile.mkdtemp(prefix='limetech')
        with Chdir(dirname):
            if self.update_url.endswith('.zip'):
                self.drop_ext='.zip'
            else:
                self.drop_ext='.tar.gz'
            cmd(['wget', '-O', self.id + self.drop_ext, self.update_url], echo=True, critical=True)
            if self.drop_ext=='.tar.gz':
                cmd(['tar', 'xzvf', self.id + self.drop_ext], echo=True, critical=True)
            else:
                cmd(['unzip', self.id + self.drop_ext], echo=True, critical=True)
            os.remove(self.id + self.drop_ext)
            
            rsync_flags = []
            if os.path.isdir(os.path.join(self.destination, 'addons', 'sourcemod', 'configs')):
                rsync_flags += ['--exclude=sourcemod/configs']
            cmd(['rsync', '-zrav'] + rsync_flags + ['addons/', self.destination], echo=True, critical=True)
        cmd(['rm', '-rf', dirname])
