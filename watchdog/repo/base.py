'''
Created on Mar 13, 2015

@author: Rob
'''
import os, logging

from buildtools.bt_logging import log
from buildtools import os_utils

class RepoType(object):
    all = {}
    def __init__(self, _id=None):
        self.id = _id
    def __call__(self, f):
        if self.id is None:
            fname_p = f.__name__.split('_')
            self.id = fname_p[1].lower()
        log.info('Adding {0} as repo type {1}.'.format(f.__name__, self.id))
        RepoType.all[self.id] = f
        return f

class Repo(object):
    def __init__(self, addon, cfg, dest):
        self.addon = addon
        self.config = cfg
        self.log = logging.getLogger('repo.' + self.addon.id)
        self.destination = os.path.expanduser(dest)

    def setDestination(self,dest):
        self.destination = dest
    
    def getDestination(self):
        return self.destination
        
    def validate(self):
        return False
        
    def preload(self):
        return False
    
    def isUp2Date(self):
        return False
    
    def update(self):
        return False
    
    def remove(self):
        return False

class RepoDir(Repo):
    def validate(self):
        if os.path.isfile(self.destination):
            self.log.error('Addon %s\'s directory is actually a file!', self.addon.id)
            return False
        return True
    
    def remove(self):
        if os.path.isdir(self.destination):
            with os_utils.TimeExecution('Removed ' + self.destination):
                os_utils.safe_rmtree(self.destination)
                os.rmdir(self.destination)
        else:
            log.warn('Directory removal already done...?')
