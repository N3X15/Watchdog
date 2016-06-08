'''
Created on Mar 18, 2015

@author: Rob
'''
import os
from buildtools import os_utils
from watchdog.addon.base import Addon, BasicAddon, AddonType
from watchdog.repo import CreateRepo
from watchdog import utils

@AddonType('source')
class SourceEngineAddon(Addon):
    '''
    Source Engine Addon (MM:S etc)
    '''
    def __init__(self, engine, id, cfg):
        super(SourceEngineAddon, self).__init__(engine, id, cfg)
        if 'dir' not in cfg: 
            root=BasicAddon.ClassDestinations['source-addon']
            self.destination = os.path.join(root,id)
            if self.id=='sourcemod':
                print(self.destination)
                assert self.destination == '/home/nexis/tf2/tf/addons/sourcemod'
        else:
            self.destination=cfg['dir']
        if 'repo' in cfg:
            os_utils.ensureDirExists(self.repo_dir,mode=0o755)
            self.repo = CreateRepo(self, cfg.get('repo',{}), self.repo_dir)
        else:
            self.repo = None