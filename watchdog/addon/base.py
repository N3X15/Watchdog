'''
Created on Mar 13, 2015

@author: Rob
'''
import os, logging

from buildtools.bt_logging import log
from buildtools import os_utils
from watchdog.repo import CreateRepo

def _AddonType(_id=None):
    registry = {}
    def wrap(f):
        if _id is None:
            fname_p = f.__name__.split('_')
            _id = fname_p[1]
        registry[_id] = f
        # def wrapped_f(*args):
        #    return f(*args)
        # return wrapped_f
        return f
    wrap.all = registry
    return wrap

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
    
@AddonType('basic')
class BasicAddon(Addon):
    '''
    Just grabs from a repo. NBD.
    
    Used if `addon: basic` is specified. Also used by default.
    '''
    ClassDestinations = {}
    def __init__(self, engine, id, cfg):
        super(BasicAddon, self).__init__(engine, id, cfg)
        if 'dir' not in cfg: 
            self.clsType = cfg['type']
            root=BasicAddon.ClassDestinations[self.clsType]
            self.destination = os.path.join(root,id)
        else:
            self.destination=cfg['dir']
        if 'repo' not in cfg:
            log.critical('Addon %r is missing its repository configuration!')
        self.repo = CreateRepo(self, cfg['repo'], self.destination)
        
    def validate(self):
        return 'repo' in cfg and self.repo.validate()
        
    def preload(self):
        return self.repo.preload()
    
    def isUp2Date(self):
        return self.repo.isUp2Date()
    
    def update(self):
        return self.repo.update()
    
    def remove(self):
        return self.repo.remove()
    
