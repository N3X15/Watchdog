import os
import platform
import sys
import time

from buildtools import log, os_utils
from valve.rcon import RCON  # pylint: disable=import-error
from watchdog.engines.base import WatchdogEngine
from watchdog.utils import LoggedProcess, del_empty_dirs


class FactorioEngine(WatchdogEngine):

    def __init__(self, cfg, args):
        super(FactorioEngine, self).__init__(cfg, args)

        self.gamedir = os.path.expanduser(cfg.get('paths.run'))
        self.executable_name = 'Factorio.exe' if platform.system() == 'Windows' else 'factorio'
        self.save_path = self.config_required('paths.save', "{PATH} needs to be set to the path of an existing save in order for Factorio to start.  Please check watchdog.yml.")
        if not os.path.isfile(self.save_path) or not os.path.isdir(self.save_path):
            log.critical('paths.save in watchdog.yml does not point to an existing save. Aborting.')
            sys.exit(1)
        self.server_settings_path = self.config_required('paths.settings', "{PATH} needs to be set to the path of an existing save in order for Factorio to start.  Please check watchdog.yml.")
        self.mapgen_settings_path = cfg.get('paths.mapgen', None)

        self.asyncProcess = None

        log.warn('Watchdog does not handle Factorio as a Steam application due to headless installs not requiring Steam.')
        log.warn('This means YOU must determine when and how to update Factorio.')

    def config_required(self, path, error_message='{PATH} is not set in watchdog.yml.  Watchdog cannot continue with this option missing.'):
        a = self.config.get(path, None)
        if a is None:
            log.critical(error_message.format(PATH=path))
            sys.exit(1)
        return a

    def updateAlert(self, typeID=''):
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

    def start_process(self):
        executable = os.path.join(self.gamedir, 'bin', 'x64', self.executable_name)
        cmd = [executable, '--start-server', self.save_path, '--server-settings', self.server_settings_path]
        if self.mapgen_settings_path is not None:
            cmd += ['--map-gen-settings', self.mapgen_settings_path]

        with os_utils.Chdir(self.gamedir):
            #cmd_daemonize(srcds_command, echo=True, critical=True)
            self.asyncProcess = LoggedProcess(cmd, 'factorio', echo=True, PTY=False, debug=False)
            self.asyncProcess.Start()

        self.find_process()

    def end_process(self):
        WatchdogEngine.end_process(self)
        if self.asyncProcess:
            self.asyncProcess.Stop()  # calls child.kill
            self.asyncProcess.WaitUntilDone()
