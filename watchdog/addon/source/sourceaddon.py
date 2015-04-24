
import os
from watchdog.addon.base import BaseBasicAddon, AddonType


@AddonType('source-addon')
class SourceAddon(BaseBasicAddon):

    '''
    Source Engine Addon (MM:S etc)
    '''

    def __init__(self, engine, aid, cfg):
        cfg['type'] = 'source-addon'
        super(SourceAddon, self).__init__(engine, aid, cfg)
        if 'dir' not in cfg:
            self.destination = os.path.dirname(self.destination)
            self.repo_dir = self.destination
    