'''
Created on Mar 18, 2015

@author: Rob
'''
from watchdog.addon.base import Addon

class SourceEngineAddon(Addon):
    '''
    Source Engine Addon (MM:S etc)
    '''
    def __init__(self, id, cfg, dest):
        super(SourceEngineAddon, self).__init__(id, cfg, dest)
        if 'dir' not in cfg: 
            root=BasicAddon.ClassDestinations['source-addon']
            self.destination = os.path.join(root,id)
        else:
            self.destination=cfg['dir']
        self.repo = CreateRepo(self, cfg['repo'], self.destination)