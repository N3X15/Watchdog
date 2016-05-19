import hashlib
import logging
import os
from buildtools.bt_logging import log, logToFile
from buildtools.twisted_utils import AsyncCommand

script_dir = ''
config_dir = ''

def getCacheDir():
    return os.path.join(config_dir, 'cache')


def md5sum(filename):
    with open(filename, mode='rb') as f:
        d = hashlib.md5()
        while True:
            # 128 is smaller than the typical filesystem block
            buf = f.read(4096)
            if not buf:
                break
            d.update(buf)
        return d.hexdigest().upper()


def del_empty_dirs(src_dir):
    ndeleted = -1
    totalDel = 0
    while ndeleted != 0:
        ndeleted = 0
        # Listing the files
        for dirpath, dirnames, filenames in os.walk(src_dir, topdown=False):
            if dirpath == src_dir:
                break
            if len(filenames) == 0 and len(dirnames) == 0:
                log.info('Removing %s (empty)', dirpath)
                os.rmdir(dirpath)
                ndeleted += 1
                totalDel += 1
    return totalDel


class Event(object):

    def __init__(self):
        self.callbacks = []

    def subscribe(self, callback):
        self.callbacks.append(callback)

    def unsubscribe(self, callback):
        self.callbacks.remove(callback)

    def fire(self, **kwargs):
        for cb in self.callbacks:
            cb(**kwargs)


class LoggedProcess(AsyncCommand):

    def __init__(self, command, logID, logSubDir=None, stdout=None, stderr=None, echo=False, env=None, PTY=False, debug=False):
        AsyncCommand.__init__(self, command, stdout=stdout, stderr=stderr, echo=echo, env=env, refName=logID, PTY=PTY, debug=debug)

        self.log = logToFile(logID, sub_dir=logSubDir, formatter=logging.Formatter(fmt='%(asctime)s [%(levelname)-8s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p'), announce_location=True, mode='a')


class FileInfo(object):

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class FileFinder(object):

    '''
    Find relatively-pathed files, given a set of filters.
    '''

    def __init__(self, path):
        self.path = path
        self.skipped_dirs = []
        self.exclude_dirs = []
        self.include_ext = []
        self.include_long_exts = []
        self.include_files = []
        self.exclude_files = []

    def import_config(self, cfg):
        self.skipped_dirs = cfg.get('skipped-dirs', [])
        self.exclude_dirs = cfg.get('exclude-dirs', [])
        self.include_ext = cfg.get('include-ext', [])
        self.exclude_files = cfg.get('exclude-files', [])
        self.include_files = cfg.get('include-files', [])
        
    def _processFile(self, fullpath):
        _, ext = os.path.splitext(fullpath)

        ext = ext.strip('.')
        long_ext = '.'.join(fullpath.split('.')[1:])

        relpath = os.path.relpath(fullpath, self.path)

        relpathparts = relpath.split(os.sep)
        if relpathparts[0] in self.skipped_dirs:
            relpathparts = relpathparts[2:]

        ignore = False
        for relpathpart in relpathparts:
            if relpathpart in self.exclude_dirs:
                ignore = True
        if ignore:
            return None
        if len(self.include_ext) > 0 or len(self.include_long_exts) > 0:
            if ext not in self.include_ext and long_ext not in self.include_long_exts:
                #log.info('%s (bad ext %s, %s)',relpath,ext,long_ext)
                return None
        relpath = '/'.join(relpathparts)

        return FileInfo(fullpath=fullpath, relpath=relpath, ext=ext, long_ext=long_ext)

    def getFiles(self):
        for root, _, files in os.walk(self.path):
            for f in files:
                returned = self._processFile(os.path.join(root, f))
                if returned is not None:
                    yield returned
                
        for f in self.included_files:
            returned = os.path.abspath(os.path.join(os.getcwd(),f))
            if returned is not None:
                yield returned
