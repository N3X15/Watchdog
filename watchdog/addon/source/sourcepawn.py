'''
Created on Apr 1, 2015

@author: Rob
'''
import os
import shutil
import yaml
from watchdog.addon.base import AddonType, BasicAddon, BaseBasicAddon
from buildtools import os_utils
from buildtools.bt_logging import log
from buildtools.os_utils import Chdir, cmd


@AddonType('sourcepawn')
class SourcePawnAddon(BaseBasicAddon):
    FILECACHE_VERSION = 4

    def __init__(self, engine, _id, cfg):
        cfg['type'] = 'source-addon'
        super(SourcePawnAddon, self).__init__(engine, _id, cfg, depends=['sourcemod'])

        self.sm_dir = os.path.join(BasicAddon.ClassDestinations['source-addon'], 'sourcemod')

        self.scripts_dir = os.path.join(self.sm_dir, 'scripting')
        self.includes_dir = os.path.join(self.sm_dir, 'scripting', 'include')
        self.include_from = os.path.join(self.repo_dir, self.config.get('path.include-from',os.path.join('scripting','include')))
        #self.smx_dir = os.path.join(self.sm_dir, 'scripting', 'compiled')
        self.smx_dir = os.path.join(self.sm_dir, 'plugins')
        self.languages_dir = os.path.join(self.sm_dir, self.config.get('destinations.languages','languages'))
        self.extensions_dir = os.path.join(self.sm_dir, 'extensions')
        self.gamedata_dir = os.path.join(self.sm_dir, 'gamedata')

        self.spcomp = os.path.join(self.scripts_dir, 'spcomp')

        self.copyable_exts = []
        self.copyable_long_exts = []
        self.extension_mappings = {}

        actions = {
            'script': self._handle_script,
            'compiled': self._handle_compiled,
            'include': self._handle_include,
            'language': self._handle_language,
            'extension': self._handle_extension,
            'gamedata': self._handle_gamedata,
            'skip': None
        }
        default_exts = {
            'script': ['sp'],
            'compiled': ['smx'],
            'include': ['inc'],
            'language': ['phrases.txt'],
            'extension': ['so', 'dll', 'autoload'],
            'gamedata': ['games.txt'],
        }
        for actionID, exts in self.config.get('ext-override', default_exts).items():
            for ext in exts:
                if ext.startswith('.'):
                    ext = ext[1:]
                if '.' in ext:
                    self.copyable_long_exts.append(ext)
                else:
                    self.copyable_exts.append(ext)
                self.extension_mappings[ext] = actions[actionID]
                #log.info('MAPPED %s -> %s',ext,actions[actionID].__name__)
                
        for ext, actionID in self.config.get('exts', {}).items():
            if ext.startswith('.'):
                ext = ext[1:]
            if '.' in ext:
                if ext not in self.copyable_long_exts: 
                    self.copyable_long_exts.append(ext)
            else:
                if ext not in self.copyable_exts:
                    self.copyable_exts.append(ext)
            self.extension_mappings[ext] = actions[actionID]
            

        # config
        self.exclude_dirs = self.config.get('exclude-dirs', ['.git', '.hg', '.svn'])
        self.exclude_files = self.config.get('exclude-files', [])
        self.strip_ndirs = self.config.get('strip-ndirs', 0)

        os_utils.ensureDirExists(self.cache_dir, mode=0o755)

        self.installed_files = {}
        self.compilable_files = {}

    def _isCompiled(self):
        for filename, destdir in self.compilable_files.items():
            _, filename = os.path.split(filename)
            naked_filename, _ = os.path.splitext(filename)
            dest = os.path.join(self.smx_dir, destdir, naked_filename + '.smx')
            if not os.path.isfile(dest):
                log.warn('%s is missing!', dest)
                return False
        return True

    def isUp2Date(self):
        if not BaseBasicAddon.isUp2Date(self):
            return False
        if not self._isCompiled():
            self.markBroken()
            return False
        return True

    def validate(self):
        #log.info('VALIDATING %s',self.__class__.__name__)
        #with log.info('Checking %s...', self.id):
        if not super(SourcePawnAddon, self).validate():
            return False

        if 'sourcemod' not in self.engine.addons:
            log.info('SourceMod not initialized.  Did you make %s dependent on it?',self.id)
            return False

        # Should not trigger a failed addon load.
        self.validateInstallation()
        
        if not os.path.isdir(self.sm_dir):
            log.error('SourceMod is not installed at %s.', self.sm_dir)
            self.engine.addons['sourcemod'].markBroken()
            return False

        if not os.path.isfile(self.spcomp):
            log.error('spcomp is missing from SourceMod.')
            self.engine.addons['sourcemod'].markBroken()
            return False

        return True

    def loadFileCache(self):
        try:
            if os.path.isfile(self.file_cache):
                log.info('Loading %s...', self.file_cache)
                with open(self.file_cache, 'r') as f:
                    version, data = yaml.load_all(f)
                    if version == self.FILECACHE_VERSION:
                        self.installed_files = data['installed']
                        self.compilable_files = data['compilable']
                    else:
                        return False
        except Exception as e:  # IGNORE:broad-except
            log.error(e)
            return False
        return True

    def saveFileCache(self):
        with open(self.file_cache, 'w') as f:
            yaml.dump_all([
                self.FILECACHE_VERSION,
                {
                    'installed': self.installed_files,
                    'compilable': self.compilable_files
                }
            ], f, default_flow_style=False)

    def registerCompilable(self, filename, destdir):
        if filename not in self.compilable_files:
            self.compilable_files[filename] = destdir

    def clearInstallLog(self):
        BaseBasicAddon.clearInstallLog(self)
        self.compilable_files = {}

    def _handle_compiled(self, src, destdir):
        return self.copyfile(src, os.path.join(self.smx_dir, destdir))

    def _handle_extension(self, src, destdir):
        return self.copyfile(src, os.path.join(self.extensions_dir, destdir))

    def _handle_include(self, src, destdir):
        return self.copyfile(src, os.path.join(self.includes_dir, destdir))

    def _handle_gamedata(self, src, destdir):
        return self.copyfile(src, os.path.join(self.gamedata_dir, destdir))

    def _handle_script(self, src, destdir):
        _, filename = os.path.split(src)
        dest = os.path.join(destdir, filename)
        self.registerCompilable(src, destdir)
        return self.copyfile(src, os.path.join(self.scripts_dir, destdir))

    def _handle_language(self, src, destdir):
        return self.copyfile(src, os.path.join(self.languages_dir, destdir))

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

    def _compile(self, src, destdir):
        destdir = os.path.join(self.smx_dir, destdir)
        if not os.path.isdir(destdir):
            os.makedirs(destdir)
            log.info('mkdir %s', destdir)
        _, filename = os.path.split(src)
        naked_filename, _ = os.path.splitext(filename)
        addon_dest=os.path.join(os.path.dirname(src),naked_filename+'.smx')
        final_dest = os.path.join(destdir, naked_filename + '.smx')
        includes=[self.include_from]
        for a in self.dependencies:
            addon = self.engine.addons[a]
            if isinstance(addon, SourcePawnAddon):
                if not os.path.isdir(addon.include_from):
                    log.warn('SPCOMP: %s is missing!',addon.include_from)
                else:
                    includes.append(addon.include_from)
        includes=['-i'+x for x in includes]
        with Chdir(self.repo_dir, quiet=True):
            if cmd([self.spcomp, src, '-o' + addon_dest]+includes, critical=False, echo=True, show_output=False):
                self.registerFile(addon_dest,final_dest,True)
                return True
        return False

    def update(self):
        if not self.isBroken() and not self._isCompiled():
            self.markBroken()
        if super(SourcePawnAddon, self).update() or self.isBroken():
            self.clearInstallLog()
            skip_dirs = ('scripting', 'languages', 'extensions', 'include', 'gamedata', 'plugins')
            with log.info('Installing %s from %s...', self.id, self.repo_dir):
                for root, _, files in os.walk(self.repo_dir):
                    log.debug('Looking in %s...',root)
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
                        if relpathparts[0] in skip_dirs:
                            relpathparts = relpathparts[2:]
                        if ext not in self.copyable_exts and long_ext not in self.copyable_long_exts:
                            #log.warn('%s (bad ext %s, %s)',relpath,ext,long_ext)
                            continue
                        relpath = '/'.join(relpathparts)
                        if os.sep.join(relpathparts[:-1]) in self.exclude_dirs:
                            continue
                        handler = None
                        if long_ext in self.extension_mappings:
                            handler = self.extension_mappings[long_ext]
                        elif ext in self.extension_mappings:
                            handler = self.extension_mappings[ext]
                        if handler is None:
                            continue
                        log.debug('Found %s',fullpath)
                        handler(fullpath, os.sep.join(relpathparts[:-1]))
                #self.forceFilesystemSync()
                try:
                    with log.info('Compiling...'):
                        for src, destdir in self.compilable_files.items():
                            if not self._compile(src, destdir):
                                self.saveFileCache()
                                self.markBroken()
                                return False
                except Exception as e:
                    self.saveFileCache()
                    self.markBroken()
                    raise e
                #self.forceFilesystemSync()
                self.unmarkBroken()
                self.saveFileCache()
                return True
        return False

    def remove(self):
        super(SourcePawnAddon, self).remove()
