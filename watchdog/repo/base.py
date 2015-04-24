'''
Created on Mar 13, 2015

@author: Rob
'''
import os
import yaml
import logging

from buildtools.bt_logging import log
from buildtools import os_utils
from watchdog.utils import FileFinder


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

        self.cache_dir = os.path.join(self.addon.engine.cache_dir, 'repo', self.addon.id)
        #os_utils.ensureDirExists(self.cache_dir, mode=0o755)

    def setDestination(self, dest):
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
    EXCLUDE_DIRS = []  # Control dirs (.git, etc)

    def __init__(self, addon, cfg, dest):
        Repo.__init__(self, addon, cfg, dest)

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

    def getRepoLocation(self):
        return self.destination

    def getRepoStatus(self):
        added = []
        changed = []
        removed = []

        VERSION = 0
        old_files = []
        with open(os.path.join(self.cache_dir, 'repo-status.yml'), 'r') as f:
            fileversion, body = yaml.load_all(f)
            if fileversion == VERSION:
                old_files = body

        for relpath, mtime in self.getDirContents():
            fullpath = os.path.abspath(self.getRepoLocation(), relpath)
            if not os.path.isfile(fullpath):
                removed.append(relpath)
            else:
                if relpath not in old_files:
                    added.append(relpath)
                elif old_files[relpath] != mtime:
                    changed.append(relpath)

    def getDirContents(self, path=None):
        '''
        Gets a list of files, along with their mtimes.
        :returns dict: filename: mtime
        '''
        out = {}

        if not path:
            path = self.destination

        ff = FileFinder(path)
        ff.exclude_dirs = self.EXCLUDE_DIRS + self.config.get('contents-exclude', [])
        for fileinfo in ff.getFiles():
            out[fileinfo.relpath] = os.stat(fileinfo.fullpath).mtime
        return out
