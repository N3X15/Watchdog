'''
Created on Apr 13, 2015

@author: Rob
'''
import os
import shutil

from watchdog.plugin.base import BasePlugin, PluginType
from buildtools.bt_logging import log
from buildtools import os_utils
from watchdog.utils import del_empty_dirs
from buildtools.os_utils import DeferredLogEntry


@PluginType('fastdl')
class FastDLPlugin(BasePlugin):

    def __init__(self, engine, cfg):
        super(FastDLPlugin, self).__init__(engine, cfg)

        self.config = self.engine.config.get('fastdl', {})

        self.engine.initialized.subscribe(self.onInitialize)

        self.fastDLPaths = {}
        self.nScanned = 0
        self.nNew = 0
        self.nRemoved = 0

    def validate(self):
        if not self.config.get('destination', None):
            log.error('fastdl.destination is not set.')
            return False
        return True

    def onInitialize(self):
        plName = self.__class__.__name__
        with log.info('Initializing %s...', plName):
            self.hookEvent(self.engine, 'updated', self.updateFastDL)
            self.hookEvent(self.engine, 'addons_updated', self.updateFastDL_AU)
        log.info('%s initialized.', plName)

    def compressFile(self, src, dest):
        #log.info('bz2 %s %s',src,dest)
        destdir = os.path.dirname(dest)
        if not os.path.isdir(destdir):
            os.makedirs(destdir)
            log.info('Created %s', destdir)
        if not os_utils.canCopy(src, dest + '.bz2'):
            return False
        shutil.copy2(src, dest)
        level = str(self.config.get('compression-level', 9))
        level = max(min(level, 1), 9)
        # -f = force overwrite
        # -z = compress
        # -q = quiet
        # -1-9 = compression level (fast-best)
        os_utils.cmd(['bzip2', '-zfq' + str(level), dest], critical=True)
        return True

    def updateFastDL_AU(self, addon_names=None):
        return self.updateFastDL()

    def updateFastDL(self):
        self.fastDLPaths = {}
        gamepath = os.path.join(self.engine.gamedir, self.engine.game_content.game)

        '''
        old_hashes = {}
        new_hashes = {}
        fastDLCache=os.path.join(self.cache_dir,'fastdl.vdf')
        if os.path.isfile(fastDLCache):
            try:
                vdf = VDFFile()
                vdf.Load(fastDLCache)
                old_hashes = vdf.rootnode.children['checksums']
            except Exception as e:
                log.error('Error loading checksum cache: %s', e)
        '''

        destdir = self.config.get('destination', '')
        exclude_dirs = self.config.get('exclude-dirs', ['.git', '.svn', '.hg'])
        include_exts = self.config.get('include-exts', ["mdl", "vmt", "vtf", "wav", 'mp3', 'bsp'])
        forced_files = self.config.get('files', [])
        addon_dirs = self.config.get('addon-dirs', ['addons'])
        scan_dirs = self.config.get('scan-dirs', ['addons', 'maps'])

        self.nScanned = 0
        self.nNew = 0
        self.nRemoved = 0

        def processFile(fullpath):
            #global nScanned,nNew,nRemoved
            self.nScanned += 1
            _, ext = os.path.splitext(fullpath)
            ext = ext.strip('.')
            if ext not in include_exts:
                return
            relpath = os.path.relpath(fullpath, gamepath)
            relpathparts = relpath.split(os.sep)
            if relpathparts[0] in addon_dirs:
                relpathparts = relpathparts[2:]
            # else:
            #    return
            ignore = False
            for relpathpart in relpathparts:
                if relpathpart in exclude_dirs:
                    ignore = True
            if ignore:
                return
            vfspath = '/'.join(relpathparts)
            self.fastDLPaths[vfspath] = relpath
            # md5 = md5sum(fullpath)
            # new_hashes[relpath] = md5
            # if fullpath in old_hashes and old_hashes[relpath] == md5:
            destfile = os.path.join(destdir, os.sep.join(relpathparts))
            if self.compressFile(fullpath, destfile):
                self.nNew += 1

        with log.info('Updating FastDL for {}... (This may take a while)'.format(gamepath)):
            with os_utils.TimeExecution(DeferredLogEntry('Completed in {elapsed}s - Updated {nfiles} files')) as t:
                for scan_dir in scan_dirs:
                    log.info('Scanning %s...', scan_dir)
                    for root, _, files in os.walk(os.path.join(gamepath, scan_dir)):
                        for f in files:
                            processFile(os.path.join(root, f))
                for f in forced_files:
                    processFile(f)
                t.vars['nfiles'] = self.nNew

            with os_utils.TimeExecution(DeferredLogEntry('Completed in {elapsed}s - Removed {nfiles} dead files')) as t:
                for root, _, files in os.walk(destdir):
                    for f in files:
                        remove = False
                        fullpath = os.path.join(root, f)
                        realpath = fullpath
                        if fullpath.endswith('.bz2'):
                            fullpath = fullpath[:-4]
                        _, ext = os.path.splitext(fullpath)
                        ext = ext.strip('.')
                        if ext not in include_exts:
                            remove = True
                        relpath = os.path.relpath(fullpath, destdir)
                        relpathparts = relpath.split(os.sep)
                        if relpathparts[0] in addon_dirs:
                            relpathparts = relpathparts[1:]
                        for relpathpart in relpathparts:
                            if relpathpart in exclude_dirs:
                                remove = True
                        relpath = '/'.join(relpathparts)
                        if relpath not in self.fastDLPaths:
                            remove = True
                        if remove:
                            log.info('Removing %s...', relpath)
                            os.remove(realpath)
                            self.nRemoved += 1
                t.vars['nfiles'] = self.nRemoved

            with os_utils.TimeExecution(DeferredLogEntry('Completed in {elapsed}s - Removed {ndirs} dead directories')) as t:
                t.vars['ndirs'] = del_empty_dirs(destdir)

            # VDFFile({'checksums':new_hashes}).Save(fastDLCache)
            log.info('Scanned: %d, Added: %d, Removed: %d', self.nScanned, self.nNew, self.nRemoved)


@PluginType('_gmfastdl')
class GModFastDLPlugin(FastDLPlugin):

    def __init__(self, engine, cfg):
        FastDLPlugin.__init__(self, engine, cfg)

    def updateFastDL(self):
        FastDLPlugin.updateFastDL(self)

        luaResources = self.config.get('lua', 'lua/autorun/server/fastdl.lua')
        luaIncludePaths = self.config.get('lua-include', [])

        luaResources = os.path.join(self.engine.gamedir, self.engine.game_content.game, luaResources)
        destdir = os.path.dirname(luaResources)
        with log:  # Re-indent ;)
            if not os.path.isdir(destdir):
                os.makedirs(destdir)
                log.info('Created %s', destdir)
            with os_utils.TimeExecution(DeferredLogEntry('Completed in {elapsed}s - Wrote {num} entries to {filename}.')) as t:
                with open(luaResources, 'w') as f:
                    f.write('-- Automatically generated by watchdog.py ({}.{})\n'.format(__name__, self.__class__.__name__))
                    f.write('-- DO NOT EDIT BY HAND.\n')
                    f.write('if (SERVER) then\n')
                    nEntries = 0
                    for vfspath, relpath in self.fastDLPaths.items():
                        for incl in luaIncludePaths:
                            if relpath.startswith('./'):
                                relpath = relpath[2:]
                            if relpath.startswith(incl):
                                f.write('\tresource.AddSingleFile("{}") -- {}\n'.format(vfspath, relpath))
                                nEntries += 1
                                break
                    t.vars['num'] = nEntries
                    t.vars['filename'] = luaResources
                    f.write('end\n')
