'''
Created on Mar 13, 2015

@author: Rob
'''
import os
import logging
import yaml
import shutil

from buildtools.bt_logging import log
from buildtools import os_utils
from watchdog.repo import CreateRepo
from watchdog import utils
from watchdog.utils import FileFinder
import traceback


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
    FILECACHE_VERSION = 3

    def __init__(self, engine, aid, cfg, depends=[]):
        self.engine = engine
        self.id = aid
        self.config = cfg
        self.repo_config = self.config.get('repo', {})
        self.log = logging.getLogger('addon.' + aid)

        self.cache_dir = os.path.join(utils.getCacheDir(), 'addons', aid)
        os_utils.ensureDirExists(self.cache_dir)

        self.file_cache = os.path.join(self.cache_dir, 'files.yml')
        self.fileRegistry = {}

        self.dependencies = cfg.get('dependencies', []) + depends
        
        self.removing = False
        
        self.installed_files = {}
        self.new_files={}

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
                # log.info('Loading %s...',self.file_cache)
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

    def registerFile(self, source, destination, track):
        source=os.path.abspath(source)
        destination=os.path.abspath(destination)
        #self.installed_files[destination] = 
        self.new_files[destination] = {
            'source': source,
            'track': track,
            'addon': self.id
        }

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
    
    def forceFilesystemSync(self):
        self.commitInstall(self.engine.addon_files)
        self.engine.updateFiles(self.engine.old_files, new_only=True)
    
    def validateInstallation(self):
        if len(self.installed_files) == 0:
            self.loadFileCache()
        for dest, _ in self.installed_files.iteritems():
            if not os.path.isfile(dest):
                log.error('Missing file: %s', dest)
                self.markBroken()
                return

    def markBroken(self):
        if not self.isBroken():
            # traceback.print_stack()
            log.error('ADDON %s IS BROKEN!', self.id)
            self.engine.addons_dirty = True
            with open(os.path.join(self.cache_dir, 'BROKEN'), 'w') as f:
                f.write('')

    def unmarkBroken(self):
        brokefile = os.path.join(self.cache_dir, 'BROKEN')
        if os.path.isfile(brokefile):
            log.info('Addon %s is no longer broken.', self.id)
            os.remove(brokefile)
            self.engine.addons_dirty = True

    def isBroken(self):
        return os.path.isfile(os.path.join(self.cache_dir, 'BROKEN'))
    
    def clearInstallLog(self):
        self.installed_files = {}
        
    def commitInstall(self, globalFileRegistry):
            
        new={}
        modified={}
        deleted=[]
        for newfile, filemeta in self.new_files.iteritems():
            if newfile in self.installed_files:
                modified[newfile]=filemeta
            else:
                new[newfile]=filemeta
                #log.info('N {}'.format(newfile))
                
        for oldfile, filemeta in self.installed_files.iteritems():
            if oldfile not in self.new_files:
                deleted.append(oldfile)
                #log.info('D {}'.format(oldfile))
                
        
        for destfile, filemeta in self.new_files.iteritems():
            globalFileRegistry[destfile] = filemeta
        for destfile in deleted:
            globalFileRegistry[destfile] = None
            

    def installFile(self, src, dest, track=True):
        # if not os.path.isdir(dest):
        #    log.info('mkdir -p "%s"', dest)
        #    os.makedirs(dest)
        destfile = os.path.join(dest, os.path.basename(src))
        # if os_utils.canCopy(src, destfile):
        #    log.info('cp "%s" "%s"', src, dest)
        #    shutil.copy2(src, destfile)
        # if track:
        self.registerFile(src, destfile, track)
        
    def performInstallFile(self, source, destfile, track=True):
        destdir = os.path.dirname(destfile)
        if not os.path.isdir(destdir):
            log.info('mkdir -p "%s"', destdir)
            os.makedirs(destdir)
        if (os.path.isfile(destfile) and not os.path.islink(destfile)) or (os.path.islink(destfile) and os.readlink(destfile) != source):
            log.info('rm "%s"', destfile)
            os.remove(destfile)
        if not os.path.islink(destfile):
            log.info('symlink %s -> %s (%s)', destfile,source,self.id)
            os.symlink(source, destfile)
            

    def installFiles(self, src, dest, track=True):
        if os.path.isfile(src):
            self.installFile(src, dest, track)
        elif os.path.isdir(src):
            dirname = os.path.basename(src)
            ff = FileFinder(src)
            ff.import_config(self.config.get('install', {}))
            for fi in ff.getFiles():
                self.installFile(fi.fullpath, os.path.join(dest, dirname, os.path.dirname(fi.relpath)))
                
    def uninstallFiles(self):
        '''
        OBSOLETE
        '''
        pass


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
        self.repo_dir = os.path.join(utils.getCacheDir(),'addons',self.id,'staging')
        self.repo = None

    def validate(self):
        if self.clsType is not None and self.clsType not in BasicAddon.ClassDestinations:
            log.critical('Path for addon type %r is missing!', self.clsType)
            return False
        if self.config.get('repo', None) is None: 
            log.critical('Addon %r is missing its repository configuration!', self.clsType)
            return False
        if self.isBroken():
            log.warning('Addon %r is broken.', self.id)
        # print(repr(self.config['repo']))
        self.repo = CreateRepo(self, self.config['repo'], self.repo_dir)
        return True

    def preload(self):
        if not self.repo:
            self.validate()
        if not self.repo:
            return True
        return self.repo.preload()

    def isUp2Date(self):
        if not self.repo:
            self.validate()
        if not self.repo:
            return True
        return self.repo.isUp2Date()

    def update(self):
        if not self.repo:
            self.validate()
        if not self.repo:
            return True
        return self.repo.update()

    def remove(self):
        self.uninstallFiles()
        if self.repo:
            return self.repo.remove()
        else:
            return True


@AddonType('basic')
class BasicAddon(BaseBasicAddon):

    '''
    Just grabs from a repo. NBD.

    Used if `addon: basic` is specified. Also used by default.
    '''
    ClassDestinations = {}
