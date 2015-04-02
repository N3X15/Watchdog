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

@AddonType('sourcemod')
class SourceMod(AlliedModdersBase):
    '''
    SourceMod itself.
    '''
    
    MODID = 'SourceMod'
    DROP_FORMAT = 'http://www.sourcemod.net/smdrop/{VERSION}/'
    DROP_FILE_EXPRESSION = re.compile('sourcemod-(?P<version>[0-9\.]+)-git(?P<build>[0-9]+)-(?P<os>windows|linux|mac)\.[a-z\.]+')

    def __init__(self, engine, id, cfg):
        super(SourceMod, self).__init__(engine, id, cfg)

        self.drop_ext = '.zip'
        if self.os == AMOperatingSystem.LINUX:
            self.drop_ext = '.tar.gz'
    
    def ForceUpdate(self):
        dirname = tempfile.mkdtemp(prefix='smupdate')
        with Chdir(dirname):
            cmd(['wget', '-O', 'sourcemod' + self.drop_ext, self.update_url], echo=True, critical=True)
            cmd(['tar', 'xzvf', 'sourcemod' + self.drop_ext], echo=True, critical=True)
            os.remove('sourcemod' + self.drop_ext)
            
            rsync_flags = []
            if os.path.isdir(os.path.join(self.destination, 'addons', 'sourcemod', 'configs')):
                rsync_flags += ['--exclude=sourcemod/configs']
            cmd(['rsync', '-zrav'] + rsync_flags + ['addons/', self.destination], echo=True, critical=True)
        cmd(['rm', '-rf', dirname])
