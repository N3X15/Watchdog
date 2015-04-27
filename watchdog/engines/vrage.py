import os
import time
import shutil
import sys

from watchdog.engines.base import EngineType
from watchdog.steam import srcupdatecheck
from buildtools.os_utils import cmd, Chdir, TimeExecution
from buildtools.bt_logging import log
from buildtools import os_utils, Config
from watchdog.utils import del_empty_dirs, LoggedProcess
import collections
from watchdog.engines.steambase import SteamBase

from valve.source.a2s import ServerQuerier  # IGNORE:import-error


@EngineType('vrage')
class VRageEngine(SteamBase):

    def __init__(self, cfg, args):
        super(VRageEngine, self).__init__(cfg, args)

        self.numPlayers = 0

        self.initialized.fire()

    def updateAlert(self, typeID=''):
        return
        '''
        ip, port = self.config.get('monitor.ip', '127.0.0.1'), self.config.get('monitor.port', 27015)
        ip, port = self.config.get('auth.rcon.ip', ip), self.config.get('auth.rcon.port', port)
        wait = self.config.get('monitor.restart-wait', 30)
        passwd = self.config.get('auth.rcon.password', None)
        if passwd is None:
            return
        with log.info('Sending warning via RCON to %s:%d...', ip, port):
            if self.process is None or not self.process.is_running():
                log.warn('Process is not running, skipping rcon warning.')
                return
            if not self.pingServer(noisy=True):
                log.warn('PING failed, skipping RCON warning.')
                return
            if self.numPlayers == 0:
                log.warn('0 players online, skipping RCON warning.')
                return
            with RCON((ip, port), passwd) as rcon:
                if wait > 0:
                    rcon('say [Watchdog] {type} update detected, restarting in {time} seconds.'.format(
                        type=typeID, time=wait))
                    time.sleep(wait)
                rcon(
                    'say [Watchdog] Restarting now to update {}.'.format(typeID))
        '''

    def queueRestart(self, typeID):
        super(VRageEngine, self).queueRestart(typeID)

        '''
        ip, port = self.config.get('monitor.ip', '127.0.0.1'), self.config.get('monitor.port', 27015)
        ip, port = self.config.get('auth.rcon.ip', ip), self.config.get('auth.rcon.port', port)
        passwd = self.config.get('auth.rcon.password', None)
        with log.info('Sending restart queue warning via RCON to %s:%d...', ip, port):
            if self.process is None or not self.process.is_running():
                log.warn('Process is not running, skipping rcon warning.')
                return
            if not self.pingServer(noisy=True):
                log.warn('PING failed, skipping RCON warning.')
                return
            if self.numPlayers == 0:
                log.warn('0 players online, skipping RCON warning.')
                return
            with RCON((ip, port), passwd) as rcon:
                rcon('say [Watchdog] {} update detected, restarting at the end of the round, or when the server empties.'.format(typeID))
        '''

    def tryPing(self, trynum, maxtries, noisy):
        ip, port = self.config.get('monitor.ip', '127.0.0.1'), self.config.get('monitor.port', 27015)
        timeout = self.config.get('monitor.timeout', 10)
        try:
            if noisy:
                log.info('Querying %s:%d (ping attempt %d/%d)...', ip, port, trynum + 1, maxtries)
            with log:
                server = ServerQuerier((ip, port), timeout=timeout)
                # with TimeExecution('Ping'):
                self.numPlayers = int(server.get_info()['player_count'])
                if noisy:
                    log.info('%d players connected.', self.numPlayers)
                if self.numPlayers == 0 and self.restartQueued:
                    log.info('RESTARTING!')
                    self.applyUpdates(True)
        except Exception as e:
            log.error(e)
            return False
        return True

    def start_process(self):
        command=[]
        
        runtime = self.config.get('daemon.runtime.executable', None)
        if runtime:
            command += [runtime]+self.config.get('daemon.runtime.args',[])
        
        command.append(os.path.join(self.gamedir, self.config.get('daemon.executable', 'SpaceEngineersDedicated.exe')))

        game_required = {'console': ''}
        game_args = self.config.get('daemon.game_args', {})
        #self.applyDefaultsTo(game_required, game_args, 'Configuration entry {key!r} is not present in daemon.game_args.  Default value {value!r} is set.')
        command += self.buildArgs('-', game_args, game_required)

        niceness = self.config.get('daemon.niceness', 0)
        if niceness != 0:
            command = ['nice', '-n', niceness] + command

        with Chdir(self.gamedir):
            self.asyncProcess = LoggedProcess(command, 'dedi', echo=True, PTY=False, debug=False)
            self.asyncProcess.Start()

        self.find_process()

    def end_process(self):
        super(VRageEngine, self).end_process()
        if self.asyncProcess:
            self.asyncProcess.Stop()  # calls child.kill
            self.asyncProcess.WaitUntilDone()
