'''
This WOULD be a basic mod, but Factorio has some dumb directory rules I want to enforce.
'''

import os
from buildtools import log
from watchdog.addon.base import AddonType, BasicAddon, BaseBasicAddon

@AddonType('factorio')
class FactorioAddon(BaseBasicAddon):

    '''
    Source Engine Addon (MM:S etc)
    '''

    def __init__(self, engine, aid, cfg):
        cfg['type'] = 'factorio-mod'
        super(FactorioAddon, self).__init__(engine, aid, cfg)

        self.mod_state = self.config.get('plugins', {})
        self.mod_dir = os.path.join(BasicAddon.ClassDestinations['factorio-mod'], 'mods')

        self.exclude_dirs = self.config.get('exclude-dirs', ['.git', '.hg', '.svn'])
        self.exclude_files = self.config.get('exclude_files', ['README.md', 'README.txt'])
        self.skip_dirs = [] #('scripting', 'languages', 'extensions', 'include', 'gamedata', 'plugins')
        self.strip_ndirs = self.config.get('strip-ndirs', 0)

    def copyfile(self, src, destdir):
        if not os.path.isdir(destdir):
            os.makedirs(destdir)
            log.info('mkdir %s', destdir)
        _, filename = os.path.split(src)
        dest = os.path.join(destdir, filename)
        self.registerFile(src, dest, True)
        #if not os_utils.canCopy(src, dest):
        #    return False
        #log.info('cp %s %s', src, dest)
        #shutil.copy2(src, dest)
        return True

    def update(self):
        if super(FactorioAddon, self).update() or self.isBroken():
            self.clearInstallLog()
            with log.info('Installing %s from %s...', self.id, self.repo_dir):
                for root, _, files in os.walk(self.repo_dir):
                    for f in files:
                        fullpath = os.path.join(root, f)
                        _, ext = os.path.splitext(f)
                        ext = ext.strip('.')
                        long_ext = '.'.join(f.split('.')[1:])

                        relpath = os.path.relpath(fullpath, self.repo_dir)
                        #print(relpath)
                        if relpath in self.exclude_files:
                            continue

                        relpathparts = relpath.split(os.sep)

                        ignore = False
                        for relpathpart in relpathparts:
                            #print(relpathpart)
                            if relpathpart in self.exclude_dirs:
                                ignore = True
                        if ignore:
                            #print('Ignoring '+relpath)
                            continue

                        if self.strip_ndirs > 0:
                            log.debug('Stripping %d from %s',self.strip_ndirs,relpath)
                            relpathparts = relpathparts[self.strip_ndirs:]
                        if relpathparts[0] in self.skip_dirs:
                            relpathparts = relpathparts[2:]
                        #if ext not in self.copyable_exts and long_ext not in self.copyable_long_exts:
                        #    #log.warn('%s (bad ext %s, %s)',relpath,ext,long_ext)
                        #    continue
                        relpath = '/'.join(relpathparts)
                        if os.sep.join(relpathparts[:-1]) in self.exclude_dirs:
                            continue
                        log.debug('Found %s',fullpath)
                        self.copyfile(fullpath, os.sep.join(relpathparts[:-1]))
                #self.forceFilesystemSync()
                self.unmarkBroken()
                self.saveFileCache()
            return True
