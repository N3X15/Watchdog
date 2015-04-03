'''
Created on Apr 1st, 2015

@author: Rob
'''
import os, sys, yaml, re, tempfile

from watchdog.addon.source.base import SourceEngineAddon

from buildtools import http, os_utils
from buildtools.bt_logging import log
from buildtools.os_utils import Chdir, cmd
from watchdog.addon.source.alliedmoddersbase import AlliedModdersBase, AMOperatingSystem
from watchdog.steamtools.vdf import VDFFile
from watchdog.addon.base import AddonType

@AddonType('metamodsource')
class MetaModSource(AlliedModdersBase):
    MODID = 'MetaModSource'
    DROP_FORMAT = 'http://www.metamodsource.net/mmsdrop/{VERSION}/'

    def __init__(self, engine, id, cfg):
        super(MetaModSource, self).__init__(engine, id, cfg)
        
        self.DROP_FILE_EXPRESSION = re.compile('mmsource-(?P<version>[0-9\.]+)-git(?P<build>[0-9]+)-(?P<os>windows|linux|mac)\.[a-z\.]+')

        self.drop_ext = '.zip'
        if self.os == AMOperatingSystem.LINUX:
            self.drop_ext = '.tar.gz'
    
    def ForceUpdate(self):
        dirname = tempfile.mkdtemp(prefix='mmsupdate')
        with Chdir(dirname):
            cmd(['wget', '-O', 'mms' + self.drop_ext, self.update_url], echo=True, critical=True)
            cmd(['tar', 'xzvf', 'mms' + self.drop_ext], echo=True, critical=True)
            os.remove('mms' + self.drop_ext)
            
            rsync_flags = []
            # if os.path.isdir(os.path.join(self.destination, 'addons', 'sourcemod', 'configs')):
            #    rsync_flags += ['--exclude=sourcemod/configs']
            cmd(['rsync', '-zrav'] + rsync_flags + ['addons/', self.destination], echo=True, critical=True)
            # "../tf/addons/metamod/bin/server"
        vdfContent = {
            'Plugin': {
                'file': os.path.join(self.engine.gamedir, self.engine.game_content.game, 'addons', 'metamod', 'bin', 'server')
            }
        }
        VDFFile(vdfContent).Save(os.path.join(self.destination, 'metamod.vdf'))
        cmd(['rm', '-rf', dirname])
