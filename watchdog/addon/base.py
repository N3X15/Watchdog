'''
Created on Mar 13, 2015

@author: Rob
'''
import os, logging

from buildtools.bt_logging import log

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
    def __init__(self, id, cfg, dest):
        self.id = id
        self.config = cfg
        self.log = logging.getLogger('addon.' + id)
        self.destination = os.path.expanduser(dest)
        
    def validate(self):
        return False
        
    def preload(self):
        return False
    
    def isUp2Date(self):
        return False
    
    def update(self):
        return False
    
class AddonDir(Addon):
    def __init__(self, id, cfg, dest):
        super(AddonDir, self).__init__(id, cfg, dest)
    
    def validate(self):
        if os.path.isfile(self.destination):
            self.log.error('Addon %s\'s directory is actually a file!', self.id)
            return False
        return True
