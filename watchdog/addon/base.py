'''
Created on Mar 13, 2015

@author: Rob
'''
import os
import logging

from buildtools.bt_logging import log
from buildtools import os_utils
from watchdog.repo import CreateRepo

class AddonType(object):
    all = {}

    def __init__(self, _id=None):
        self.id = _id

    def __call__(self, f):
        if self.id is None:
            fname_p = f.__name__.split('_')
            self.id = fname_p[1].lower()
        log.info('Adding {0} as addon type {1}.'.format(f.__name__, self.id))
        AddonType.all[self.id] = f
        return f


class Addon(object):

    def __init__(self, engine, id, cfg):
        self.engine = engine
        self.id = id
        self.config = cfg
        self.repo_config = self.config.get('repo', {})
        self.log = logging.getLogger('addon.' + id)

    def validate(self):
        return False

    def preload(self):
        return False

    def isUp2Date(self):
        return False

    def update(self):
        '''Returns true if the state of the repo/addon changed. (Restarts server)'''
        return False

    def remove(self):
        return False


class BaseBasicAddon(Addon):

    '''
    Just grabs from a repo. NBD.

    Used if `addon: basic` is specified. Also used by default.
    '''
    ClassDestinations = {}

    def __init__(self, engine, _id, cfg):
        super(BaseBasicAddon, self).__init__(engine, _id, cfg)
        self.clsType=None
        if 'dir' not in cfg:
            self.clsType = cfg['type']
            if self.clsType not in BasicAddon.ClassDestinations:
                return
            root = BasicAddon.ClassDestinations[self.clsType]
            self.destination = os.path.join(root, _id)
        else:
            self.destination = cfg['dir']
        self.repo_dir = self.destination
        if 'repo' not in cfg:
            log.critical('Addon %r is missing its repository configuration!')
        self.repo = None

    def validate(self):
        if self.clsType is not None and self.clsType not in BasicAddon.ClassDestinations:
            log.critical('Path for addon type %r is missing!', self.clsType)
            return False
        if 'repo' not in self.config:
            log.critical('Addon %r is missing its repository configuration!', self.clsType)
            return False
        self.repo = CreateRepo(self, self.config['repo'], self.repo_dir)
        return True

    def preload(self):
        return self.repo.preload()

    def isUp2Date(self):
        return self.repo.isUp2Date()

    def update(self):
        return self.repo.update()

    def remove(self):
        return self.repo.remove()


@AddonType('basic')
class BasicAddon(BaseBasicAddon):

    '''
    Just grabs from a repo. NBD.

    Used if `addon: basic` is specified. Also used by default.
    '''
    ClassDestinations = {}
