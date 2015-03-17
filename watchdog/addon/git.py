'''
Created on Mar 13, 2015

@author: Rob
'''
import os
from watchdog.addon.base import AddonDir, AddonType
from buildtools.wrapper.git import GitRepository
from buildtools import os_utils, log

@AddonType('git')
class GitAddon(AddonDir):
    '''Addon stored in a git repository.
    '''

    def __init__(self, id, cfg, dest):
        super(GitAddon, self).__init__(id, cfg, dest)
        # self.repo = None
        #print(repr(self.repo_config))
        self.remote = self.repo_config['remote']
        self.branch = self.repo_config.get('branch', 'master')
        if 'subdirs' in self.repo_config:
            self.rootdir = os.path.dirname(self.destination)
            self.destination = os.path.join(os.path.expanduser('~'), '.smwd_rootprojects', id)
        self.repo = GitRepository(self.destination, self.remote)
        # print('ADDON {} @ {}'.format(id,dest))
        
    def validate(self):
        return super(GitAddon, self).validate()
        
    def preload(self):
        if not os.path.isdir(self.destination):
            self.repo.GetRepoState()
            self.log.info('Addon {0} git repository on branch {1}, commit {2}.'.format(self.id, self.repo.current_branch, self.repo.current_commit))
        else:
            self.log.warn('Addon {0} has not been cloned yet.', self.id)
    
    def isUp2Date(self):
        return not self.repo.CheckForUpdates(branch=self.branch)
    
    def update(self):
        cleanup=self.repo_config.get('cleanup', False)
        self.repo.CheckForUpdates(branch=self.branch)
        self.repo.Pull(cleanup=cleanup)
        #assert self.repo.current_commit == self.repo.remote_commit
        if 'subdirs' in self.repo_config:
            for src, dest in self.repo_config['subdirs'].items():
                src = os.path.join(self.destination, src)
                dest = os.path.join(self.rootdir, dest)
                if cleanup: os_utils.safe_rmtree(dest)
                os_utils.copytree(src, dest)
                log.info('Copied %s -> %s', src, dest)
        return True

    def remove(self):
        AddonDir.remove(self)
        if 'subdirs' in self.repo_config:
            for src, dest in self.repo_config['subdirs'].items():
                dest = os.path.join(self.rootdir, dest)
                if os.path.isdir(dest):
                    with os_utils.TimeExecution('Removed '+dest):
                        os_utils.safe_rmtree(dest)
                else:
                    log.warn('Directory removal already done...?')