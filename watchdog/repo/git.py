'''
Created on Mar 13, 2015

@author: Rob
'''
import os, sys
from watchdog import utils
from watchdog.repo.base import RepoDir, RepoType
from buildtools.repo.git import GitRepository
from buildtools import os_utils, log
import traceback

@RepoType('git')
class GitRepo(RepoDir):
    '''Addon stored in a git repository.'''
    
    #: Control directory.
    EXCLUDE_DIRS=['.git']
    def __init__(self, addon, cfg, dest):
        super(GitRepo, self).__init__(addon, cfg, dest)
        self.remote = self.config['remote']
        self.branch = self.config.get('branch', 'master')
        if 'subdirs' in self.config:
            self.rootdir = os.path.dirname(self.destination)
            self.destination = os.path.join(utils.getCacheDir(), 'repos', self.addon.id,'gitrepo')
        self._initRepo()
            
    def _initRepo(self):
        self.repo = GitRepository(self.destination, self.remote, noisy_clone=True,quiet=self.config.get('quiet',True))
        
    def getRepoLocation(self):
        return self.destination
        
    def validate(self):
        return super(GitRepo, self).validate()
        
    def preload(self):
        if not os.path.isdir(self.destination):
            self.repo.GetRepoState()
            self.log.info('Addon {0} git repository on branch {1}, commit {2}.'.format(self.addon.id, self.repo.current_branch, self.repo.current_commit))
        else:
            self.log.warn('Addon %s has not been cloned yet.', self.addon.id)
    
    def isUp2Date(self):
        try:
            return not self.repo.CheckForUpdates(branch=self.branch)
        except Exception as e:
            log.error(traceback.format_exc())
            return False
    
    def update(self):
        with log.info('Updating addon %s from a git repository...', self.addon.id):
            cleanup = self.config.get('cleanup', False)
            try:
                self.repo.CheckForUpdates(branch=self.branch)
            except Exception as e:
                log.error('An issue occurred while checking the remote repository of %s for updates.',self.addon.id)
                log.error(traceback.format_exc())
                log.error('We will now attempt to re-clone %s.',self.addon.id)
                self.remove()
                if os.path.isdir(self.destination):
                    log.critical('UNABLE TO REMOVE %s!',self.destination)
                    sys.exit(-1)
                self._initRepo()
            
            old_commit = self.repo.current_commit
            cloned = not os.path.isdir(self.destination)
            self.repo.Pull(branch=self.branch, cleanup=cleanup)
            if cloned or old_commit != self.repo.remote_commit:
                if 'subdirs' in self.config:
                    with log.info('New commit detected (%s vs. %s), updating filesystem...',old_commit,self.repo.current_commit):
                        for src, dest in self.config['subdirs'].items():
                            src = os.path.join(self.destination, src)
                            dest = os.path.join(self.rootdir, dest)
                            if cleanup: os_utils.safe_rmtree(dest)
                            os_utils.copytree(src, dest)
                            log.info('Copied %s -> %s', src, dest)
                else:
                    log.info('Updated!')
                return True
        return False

    def remove(self):
        RepoDir.remove(self)
        if 'subdirs' in self.config:
            for src, dest in self.config['subdirs'].items():
                dest = os.path.join(self.rootdir, dest)
                if os.path.isdir(dest):
                    with os_utils.TimeExecution('Removed ' + dest):
                        os_utils.safe_rmtree(dest)
                else:
                    log.warn('Directory removal already done...?')
