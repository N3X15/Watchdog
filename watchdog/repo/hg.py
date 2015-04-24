'''
Created on Mar 31, 2015

@author: Rob
'''
import os
import sys
from watchdog import utils
from watchdog.repo.base import RepoDir, RepoType
from buildtools.repo.hg import HgRepository
from buildtools import os_utils, log
import traceback


@RepoType('hg')
class HgRepo(RepoDir):

    '''Addon stored in an hg repository.'''

    def __init__(self, addon, cfg, dest):
        super(HgRepo, self).__init__(addon, cfg, dest)
        self.remote = self.config['remote']
        self.branch = self.config.get('branch', 'master')
        if 'subdirs' in self.config:
            self.rootdir = os.path.dirname(self.destination)
            self.destination = os.path.join(utils.getCacheDir(), 'repos', self.addon.id)
        self._initRepo()

    def _initRepo(self):
        self.repo = HgRepository(self.destination, self.remote, noisy_clone=True, quiet=self.config.get('quiet', True), show_output=not self.config.get('quiet', True))

    def validate(self):
        return super(HgRepo, self).validate()

    def preload(self):
        if not os.path.isdir(self.destination):
            self.repo.GetRepoState()
            self.log.info('Addon %s hg repository on branch %s, revision %d.', self.addon.id, self.repo.current_branch, self.repo.current_rev)
        else:
            self.log.warn('Addon %s has not been cloned yet.', self.addon.id)

    def isUp2Date(self):
        try:
            return not self.repo.CheckForUpdates(branch=self.branch)
        except Exception as e:
            log.error(traceback.format_exc())
            return False

    def update(self):
        with log.info('Updating addon %s from an hg repository...', self.addon.id):
            cleanup = self.config.get('cleanup', False)
            try:
                self.repo.CheckForUpdates(branch=self.branch)
            except Exception as e:
                log.error('An issue occurred while checking the remote repository of %s for updates.', self.addon.id)
                log.error(traceback.format_exc())
                log.error('We will now attempt to re-clone %s.', self.addon.id)
                self.remove()
                if os.path.isdir(self.destination):
                    log.critical('UNABLE TO REMOVE %s!', self.destination)
                    sys.exit(-1)

            old_rev = self.repo.current_rev
            cloned = not os.path.isdir(self.destination)
            self.repo.Pull(branch=self.branch, cleanup=cleanup)
            # assert self.repo.current_commit == self.repo.remote_commit
            if cloned or old_rev != self.repo.current_rev:
                if 'subdirs' in self.config:
                    with log.info('New revision detected (%s vs. %s), updating filesystem...', old_rev, self.repo.current_rev):
                        for src, dest in self.config['subdirs'].items():
                            src = os.path.join(self.destination, src)
                            dest = os.path.join(self.rootdir, dest)
                            if cleanup:
                                os_utils.safe_rmtree(dest)
                            os_utils.copytree(src, dest)
                            log.info('Copied %s -> %s', src, dest)
                return True
        return False

    def remove(self):
        super(HgRepo, self).remove()
        if 'subdirs' in self.config:
            for src, dest in self.config['subdirs'].items():
                dest = os.path.join(self.rootdir, dest)
                if os.path.isdir(dest):
                    with os_utils.TimeExecution('Removed ' + dest):
                        os_utils.safe_rmtree(dest)
                else:
                    log.warn('Directory removal already done...?')
