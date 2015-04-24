'''
Created on Mar 18, 2015

@author: Rob
'''
import os
from watchdog.addon.base import Addon, BasicAddon, AddonType
from watchdog.repo import CreateRepo

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
        else:
            self.destination=cfg['dir']
        if 'repo' in cfg:
            self.repo = CreateRepo(self, cfg.get('repo',{}), self.destination)
        else:
            self.repo = None