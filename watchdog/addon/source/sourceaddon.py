
import os
from buildtools import log
from watchdog.addon.base import BaseBasicAddon, AddonType, BasicAddon

@AddonType('source-addon')
class SourceAddon(BaseBasicAddon):

    '''
    Source Engine Addon (MM:S etc)
    '''

    def __init__(self, engine, aid, cfg):
        cfg['type'] = 'source-addon'
        super(SourceAddon, self).__init__(engine, aid, cfg)
        #self.destination = BasicAddon.ClassDestinations['source-addon']
        # config
        self.exclude_dirs = self.config.get('exclude-dirs', ['.git', '.hg', '.svn'])
        self.strip_ndirs = self.config.get('strip-ndirs', 0)
        
    def copyfile(self, src, destdir):
        if not os.path.isdir(destdir):
            os.makedirs(destdir)
            log.info('mkdir %s', destdir)
        _, filename = os.path.split(src)
        dest = os.path.join(destdir, filename)
        #print('{} -> {}'.format(src,dest))
        self.registerFile(src, dest, True)
        
    def update(self):
        if super(SourceAddon, self).update() or self.isBroken():
            self.clearInstallLog()
            skip_dirs = []#('scripting', 'languages', 'extensions', 'include', 'gamedata', 'plugins')
            with log.info('Installing SRCDS addon %s from %s...', self.id, self.repo_dir):
                for root, _, files in os.walk(self.repo_dir):
                    #log.info('Looking in %s...',root)
                    for f in files:
                        fullpath = os.path.join(root, f)
                        _, ext = os.path.splitext(f)
                        ext = ext.strip('.')
                        long_ext = '.'.join(f.split('.')[1:])

                        relpath = os.path.relpath(fullpath, self.repo_dir)

                        relpathparts = relpath.split(os.sep)

                        if self.strip_ndirs > 0:
                            log.info('Stripping %d from %s',self.strip_ndirs,relpath)
                            relpathparts = relpathparts[self.strip_ndirs:]
                        if relpathparts[0] in skip_dirs:
                            relpathparts = relpathparts[2:]

                        ignore = False
                        for relpathpart in relpathparts:
                            if relpathpart in self.exclude_dirs:
                                ignore = True
                        if ignore:
                            continue
                        relpath = '/'.join(relpathparts)
                        #log.info('Found %s',fullpath)
                        self.copyfile(fullpath, os.path.join(self.destination,os.sep.join(relpathparts[:-1])))
                self.forceFilesystemSync()
                self.unmarkBroken()
                self.saveFileCache()
                return True
        return False
                        
    