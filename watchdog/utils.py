import hashlib
import logging
import os
from buildtools.bt_logging import log, logToFile
from buildtools.os_utils import AsyncCommand

script_dir = ''


def getCacheDir():
    return os.path.join(script_dir, 'cache')


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
        self.callbacks=[]
        
    def subscribe(self, callback):
        self.callbacks.append(callback)
        
    def unsubscribe(self, callback):
        self.callbacks.remove(callback)
        
    def fire(self,**kwargs):
        for cb in self.callbacks:
            cb(**kwargs)

class LoggedProcess(AsyncCommand):

    def __init__(self, command, logID, logSubDir=None, stdout=None, stderr=None, echo=False, env=None, PTY=False, debug=False):
        AsyncCommand.__init__(self, command, stdout=stdout, stderr=stderr, echo=echo, env=env, refName=logID, PTY=PTY, debug=debug)

        self.log = logToFile(logID, sub_dir=logSubDir, formatter=logging.Formatter(fmt='%(asctime)s [%(levelname)-8s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p'), announce_location=True, mode='a')
