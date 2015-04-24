'''
Created on Mar 13, 2015

@author: Rob
'''
import os
import logging
import yaml

from buildtools.bt_logging import log
from buildtools import os_utils
from watchdog.repo import CreateRepo
from watchdog import utils

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
    FILECACHE_VERSION = 1
    def __init__(self, engine, aid, cfg,depends=[]):
        self.engine = engine
        self.id = aid
        self.config = cfg
        self.repo_config = self.config.get('repo', {})
        self.log = logging.getLogger('addon.' + aid)
        
        self.cache_dir = os.path.join(utils.getCacheDir(),'addons',aid)
        os_utils.ensureDirExists(self.cache_dir)

        self.file_cache = os.path.join(self.cache_dir, 'files.yml')
        self.installed_files = []
        
        self.dependencies=cfg.get('dependencies',[])+depends
        
    def saveFileCache(self):
        with open(self.file_cache, 'w') as f:
            yaml.dump_all([
                self.FILECACHE_VERSION,
                {
                    'installed': self.installed_files,
                }
            ], f, default_flow_style=False)
    
    def loadFileCache(self):
        try:
            if os.path.isfile(self.file_cache):
                with open(self.file_cache, 'r') as f:
                    version, data = yaml.load_all(f)
                    if version == self.FILECACHE_VERSION:
                        self.installed_files = data['installed']
                    else:
                        return False
        except Exception as e:  # IGNORE:broad-except
            log.error(e)
            return False
        return True

    def registerFile(self, filename):
        if filename not in self.installed_files:
            self.installed_files.append(filename)

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
        for f in self.installed_files:
            if os.path.isfile(f):
                os.remove(f)
                log.info('rm %s', f)
        return False
    
    def markBroken(self):
        log.error('ADDON %s IS BROKEN!',self.id)
        with open(os.path.join(self.cache_dir,'BROKEN'),'w') as f:
            f.write('')
    
    def unmarkBroken(self):
        brokefile=os.path.join(self.cache_dir,'BROKEN')
        if os.path.isfile(brokefile):
            log.info('Addon %s is no longer broken.',self.id)
            os.remove(brokefile)
            
    def isBroken(self):
        return os.path.isfile(os.path.join(self.cache_dir,'BROKEN'))


class BaseBasicAddon(Addon):

    '''
    Just grabs from a repo. NBD.

    Used if `addon: basic` is specified. Also used by default.
    '''
    ClassDestinations = {}

    def __init__(self, engine, _id, cfg, **kwargs):
        super(BaseBasicAddon, self).__init__(engine, _id, cfg, **kwargs)
        self.clsType = cfg['type']
        if 'dir' not in cfg:
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
