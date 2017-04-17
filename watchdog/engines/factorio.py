import os
import platform
import sys
import time

from buildtools import log, os_utils
#from valve.rcon import RCON  # pylint: disable=import-error
from SourceRcon import SourceRcon
from watchdog.engines.base import EngineType, WatchdogEngine
from watchdog.utils import LoggedProcess, del_empty_dirs

DEFAULT_PORT=34197
DEFAULT_RCON_PORT=34198

@EngineType('factorio')
class FactorioEngine(WatchdogEngine):

    def __init__(self, cfg, args):
        super(FactorioEngine, self).__init__(cfg, args)

        self.gamedir = os.path.expanduser(cfg.get('paths.run'))
        self.executable_name = 'Factorio.exe' if platform.system() == 'Windows' else 'factorio'
        self.save_path = self.config_required('paths.save', "{PATH} needs to be set to the path of an existing save in order for Factorio to start.  Please check watchdog.yml.")
        if not os.path.isfile(self.save_path) and not os.path.isdir(self.save_path):
            log.critical('paths.save in watchdog.yml does not point to an existing save. Aborting.')
            sys.exit(1)
        self.server_settings_path = self.config_required('paths.settings', "{PATH} needs to be set to the path of an existing save in order for Factorio to start.  Please check watchdog.yml.")
        self.mapgen_settings_path = cfg.get('paths.mapgen', None)

        self.ip = self.config.get('auth.rcon.ip', self.config_required('monitor.ip'))
        self.rcon_port = self.config_required('auth.rcon.port')
        self.rcon_passwd = self.config_required('auth.rcon.password')
        self.rcon_passwd = self.config_required('auth.rcon.password')
        self.rcon_timeout = self.config.get('monitor.timeout', 10)

        self.asyncProcess = None
        self.numPlayers=0

        self._rcon = None

        log.warn('Watchdog does not handle Factorio as a Steam application due to headless installs not requiring Steam.')
        log.warn('This means YOU must determine when and how to update Factorio.')

    def _RCON(self):
        return None #return RCON((self.ip, self.rcon_port), self.rcon_passwd, timeout=self.rcon_timeout)

    def send_rcon(self, command):
        if self._rcon is None:
            self._rcon = SourceRcon(self.ip, int(self.rcon_port), self.rcon_passwd)
        return self._rcon.rcon(command)
        #with self._RCON() as rcon:
        #    return rcon.execute(command)

    def config_required(self, path, error_message='{PATH} is not set in watchdog.yml.  Watchdog cannot continue with this option missing.'):
        a = self.config.get(path, None)
        if a is None:
            log.critical(error_message.format(PATH=path))
            sys.exit(1)
        return a

    def updateAlert(self, typeID=''):
        wait = self.config.get('monitor.restart-wait', 30)
        with log.info('Sending warning via RCON to %s:%d...', self.ip, self.rcon_passwd):
            if self.process is None or not self.process.is_running():
                log.warn('Process is not running, skipping rcon warning.')
                return
            if not self.pingServer(noisy=True):
                log.warn('PING failed, skipping RCON warning.')
                return
            if self.numPlayers == 0:
                log.warn('0 players online, skipping RCON warning.')
                return
            #with self._RCON() as rcon:
            if wait > 0:
                self.send_rcon('[Watchdog] {type} update detected, restarting in {time} seconds.'.format(
                    type=typeID, time=wait))
                time.sleep(wait)
            self.send_rcon('[Watchdog] Restarting now to update {}.'.format(typeID))

    def queueRestart(self, typeID):
        WatchdogEngine.queueRestart(self, typeID)
        with log.info('Sending restart queue warning via RCON to %s:%d...', self.ip, self.rcon_port):
            if self.process is None or not self.process.is_running():
                log.warn('Process is not running, skipping rcon warning.')
                return
            if not self.pingServer(noisy=True):
                log.warn('PING failed, skipping RCON warning.')
                return
            if self.numPlayers == 0:
                log.warn('0 players online, skipping RCON warning.')
                return
            #with self._RCON() as rcon:
            self.send_rcon('[Watchdog] {} update detected, restarting at the end of the round, or when the server empties.'.format(typeID))

    def start_process(self):
        executable = os.path.join(self.gamedir, 'bin', 'x64', self.executable_name)
        cmd = [executable, '--start-server', self.save_path, '--server-settings', self.server_settings_path, '--rcon-password', self.rcon_passwd,  '--rcon-port', self.rcon_port]
        if self.mapgen_settings_path is not None:
            cmd += ['--map-gen-settings', self.mapgen_settings_path]

        with os_utils.Chdir(self.gamedir):
            #cmd_daemonize(srcds_command, echo=True, critical=True)
            with log.info('Writing factorio-launcher.sh...'):
                with open('factorio-launcher.sh', 'w') as f:
                    f.write('#!/bin/bash\n')
                    f.write((' '.join(['"' + str(x) + '"' for x in cmd])) + '\n')
                #os.chmod('factorio-launcher.sh', 0o755)
                with open('factorio-launcher.sh', 'r') as f:
                    for line in f:
                        log.info('> %s', line.strip())
            oldcmd = cmd
            cmd = ['bash', '-c', 'factorio-launcher.sh']
            log.info("Launching with cmd=%r", cmd)
            log.info("Wrapped cmd=%r", oldcmd)
            self.asyncProcess = LoggedProcess(cmd, 'factorio', echo=True, PTY=True, debug=False)
            self.asyncProcess.Start()
        time.sleep(5)
        self.find_process()

    def tryPing(self, trynum, maxtries, noisy):
        try:
            if noisy:
                log.info('Pinging %s:%d (try %d/%d)...', self.ip, self.rcon_port, trynum + 1, maxtries)
            with log:
                #with self._RCON() as rcon:
                response = self.send_rcon('/players') #.text
                self.numPlayers=0
                for line in response.splitlines():
                    if line.strip().endswith(' (online)'):
                        self.numPlayers += 1
                if noisy:
                    log.info('%d players connected.', self.numPlayers)
                if self.numPlayers == 0 and self.restartQueued:
                    log.info('RESTARTING!')
                    self.applyUpdates(True)
        except Exception as e:
            log.error(e)
            return False
        return True

    def end_process(self):
        WatchdogEngine.end_process(self)
        if self.asyncProcess:
            self.asyncProcess.Stop()  # calls child.kill
            self.asyncProcess.WaitUntilDone()
