'''
Created on Apr 1, 2015

@author: Rob
'''
import os, shutil, yaml
from watchdog.addon.base import AddonType, BasicAddon, BaseBasicAddon
from buildtools import os_utils
from buildtools.bt_logging import log
from buildtools.os_utils import Chdir, cmd

@AddonType('sourcepawn')
class SourcePawnAddon(BaseBasicAddon): 
    FILECACHE_VERSION = 2
    def __init__(self, engine, id, cfg):
        cfg['type']='source-addon'
        super(SourcePawnAddon, self).__init__(engine, id, cfg)
        
        self.cache_dir = os.path.join(self.engine.cache_dir, 'SourcePawn', id)
        self.repo_dir = os.path.join(self.cache_dir, 'staging')
        
        self.sm_dir = os.path.join(BasicAddon.ClassDestinations['source-addon'], 'sourcemod')
        
        self.scripts_dir = os.path.join(self.sm_dir, 'scripting')
        self.includes_dir = os.path.join(self.sm_dir, 'scripting','include')
        
        self.spcomp = os.path.join(self.scripts_dir, 'spcomp')
        self.smx_dir = os.path.join(self.sm_dir, 'scripting', 'compiled')
        
        self.file_cache = os.path.join(self.cache_dir, 'files.yml')
        
        # config
        self.exclude_dirs = self.config.get('exclude-dirs', ['.git', '.hg', '.svn'])
        
        
        os_utils.ensureDirExists(self.cache_dir, mode=0o755)
        
        self.installed_files = []
        self.compilable_files = {}
        
    def validate(self):
        if not super(SourcePawnAddon, self).validate():
            return False
        
        if not os.path.isdir(self.sm_dir):
            log.error('SourceMod is not installed at %s.',self.sm_dir)
            return False
        
        if not os.path.isfile(self.spcomp):
            log.error('spcomp is missing from SourceMod.')
            return False
        try:
            if os.path.isfile(self.file_cache):
                with open(self.file_cache, 'r') as f:
                    version, data = yaml.load_all(f)
                    if version == self.FILECACHE_VERSION:
                        self.installed_files = data['installed-files']
        except Exception as e:
            log.error(e)
            return False
        return True
    
    def SaveState(self):
        with open(self.file_cache, 'w') as f:
            yaml.dump_all([
                self.FILECACHE_VERSION,
                {
                 'installed-files':self.installed_files
                }
            ], f, default_flow_style=False)
    
    def isUp2Date(self):
        return super(SourcePawnAddon, self).isUp2Date()
    
    def registerFile(self, filename):
        if filename not in self.installed_files:
            self.installed_files.append(filename)
    
    def registerCompilable(self, filename,destdir):
        if filename not in self.compilable_files:
            self.compilable_files[filename]=destdir
    
    def _handle_smx(self, src, destdir):
        return self.copyfile(src, os.path.join(self.smx_dir,destdir))
    
    def _handle_inc(self, src, destdir):
        return self.copyfile(src, os.path.join(self.scripts_dir,destdir))
    
    def _handle_sp(self, src, destdir):
        _, filename = os.path.split(src)
        dest = os.path.join(destdir, filename)
        self.registerCompilable(dest,destdir)
        return self.copyfile(src, os.path.join(self.scripts_dir,destdir))
    
    def copyfile(self,src,destdir):
        if not os.path.isdir(destdir):
            os.makedirs(destdir)
            log.info('mkdir %s', destdir)
        _, filename = os.path.split(src)
        dest = os.path.join(destdir, filename)
        self.registerFile(dest)
        if not os_utils.canCopy(src, dest):
            return False
        log.info('cp %s %s', src, dest)
        shutil.copy2(src, dest)
        return True
        
    def _compile(self,src,destdir):
        destdir = os.path.join(self.smx_dir,destdir)
        if not os.path.isdir(destdir):
            os.makedirs(destdir)
            log.info('mkdir %s', destdir)
        _, filename = os.path.split(src)
        naked_filename, _ = os.path.splitext(filename)
        dest = os.path.join(destdir, naked_filename + '.smx')
        self.registerFile(dest)
        with Chdir(self.scripts_dir,quiet=True):
            cmd([self.spcomp, src, '-o' + dest], critical=True, echo=True, show_output=False)
        return True
    
    def update(self):
        if super(SourcePawnAddon, self).update(): 
            with log.info('Installing %s from %s...',self.id,self.repo_dir):
                for root, dirs, files in os.walk(self.repo_dir):
                    #with log.info('Looking in %s...',root):
                    for file in files:
                        fullpath = os.path.join(root, file)
                        _, ext = os.path.splitext(file)
                        ext = ext.strip('.')
                        relpath = os.path.relpath(fullpath, self.repo_dir)
                        
                        relpathparts = relpath.split(os.sep)
                        # if relpathparts[0] in addon_dirs:
                        #    relpathparts = relpathparts[2:]
                        # #else:
                        # #    continue
                        #print(relpath)
                        ignore = False
                        for relpathpart in relpathparts:
                            if relpathpart in self.exclude_dirs:
                                ignore = True
                        if ignore: continue
                        if ext not in ('sp', 'smx', 'inc'):
                            #log.info('%s (bad ext %s)',relpath,ext)
                            continue
                        relpath = '/'.join(relpathparts)
                        
                        #self.fastDLPaths.append(relpath)
                        getattr(self, '_handle_' + ext)(fullpath, os.sep.join(relpathparts[:-1]))
                        #if getattr(self, '_handle_' + ext)(fullpath, fdestdir):
                        #    #self.nNew += 1
                with log.info('Compiling...'):
                    for src,destdir in self.compilable_files.items():
                        self._compile(src, destdir)
                self.SaveState()
                return True
        return False
    
    def remove(self):
        super(SourcePawnAddon, self).remove()
        for file in self.installed_files:
            if os.path.isfile(file):
                os.remove(file)
                log.info('rm %s', file)
