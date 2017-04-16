import os
import time
import shutil
import sys

# This crap always triggers an import error in PEP8, ignore it.
from valve.source.a2s import ServerQuerier  # IGNORE:import-error
#from valve.rcon import RCON

from watchdog.engines.base import WatchdogEngine, ConfigAddon, EngineType
from watchdog.steam import srcupdatecheck
from buildtools.os_utils import cmd, Chdir, TimeExecution
from buildtools.bt_logging import log
from buildtools import os_utils, Config
from watchdog.utils import del_empty_dirs, LoggedProcess
#from watchdog.steam.websocket_rcon import WSRcon
from watchdog.steam.SourceRcon import SourceRcon
import collections
from watchdog.engines.steambase import SteamBase


@EngineType('rust')
class RustEngine(SteamBase):
    RESTART_ON_CHANGE = True
    FASTDL_PLUGIN_ID = 'fastdl'

    def __init__(self, cfg, args):
        super(RustEngine, self).__init__(cfg, args)

        self.numPlayers = 0

        if self.config.get('fastdl', None) is not None:
            self.load_plugin(self.FASTDL_PLUGIN_ID)

        self.initialized.fire()

        self.asyncProcess=None

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
                rcon('say [Watchdog] Restarting now to update {}.'.format(typeID))

    def queueRestart(self, typeID):
        WatchdogEngine.queueRestart(self, typeID)

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

    def tryPing(self, trynum, maxtries, noisy):
        ip, port = self.config.get('monitor.ip', '127.0.0.1'), self.config.get('monitor.port', 28018)
        timeout = self.config.get('monitor.timeout', 10)
        passwd = self.config.get('auth.rcon.password',None)
        try:
            if noisy or True:
                log.info('Pinging %s:%d (try %d/%d)...', ip, port, trynum + 1, maxtries)
            with log:
                nPlayers=0
                #with RCON((ip, port), passwd) as rcon:
                #    result = rcon('players')
                rcon = SourceRcon(ip,port,passwd)
                result = rcon.rcon('players')
                rcon.disconnect()
                print(repr(result))
                for line in result.split('\n'):
                    nPlayers+=1
                    print(line.strip())
                # with TimeExecution('Ping'):
                self.numPlayers = nPlayers
                if noisy:
                    log.info('%d players connected.', self.numPlayers)
                if self.numPlayers == 0 and self.restartQueued:
                    log.info('RESTARTING!')
                    self.applyUpdates(True)
        except Exception as e:
            log.error(e)
            return False
        return True

    def checkForContentUpdates(self):
        for appID, content in self.content.items():
            if not content.IsUpdated():
                log.warn('AppID %s is out of date!', appID)
                return True
        return False

    def updateContent(self):
        for _, content in self.content.items():
            attempts = 0
            while not content.IsUpdated() and attempts < 3:
                content.Update()
                attempts += 1
        # Needed to fix a stupid steam bug that prevents the server from starting.
        appid_file = os.path.join(self.gamedir, 'steam_appid.txt')
        if not os.path.isfile(appid_file):
            with open(appid_file, 'w') as f:
                f.write(str(self.game_content.appID))
                log.info('Wrote steam_appid.txt')

    def _applyDefaultsTo(self, defaults, subject, message=None):
        for k, v in defaults.items():
            if isinstance(subject, (dict, collections.OrderedDict)):
                if k not in subject:
                    subject[k] = v
                    if message is not None:
                        log.info(message, key=k, value=v)
            elif isinstance(subject, list):
                found = False
                for value in subject:
                    if isinstance(value, (dict, collections.OrderedDict)) and k in v:
                        value[k] = v
                        if message is not None:
                            log.info(message, key=k, value=v)

    # Less duplicated code.
    def _buildArgs(self, prefix, data, defaults):
        keys = []
        o = []
        # New list format:
        # [{'a','b'}] => ['+a','b']
        # ['a']       => ['+a']
        if isinstance(data, list):
            for value in data:
                if isinstance(value, (dict, collections.OrderedDict)):
                    for k, v in value.items():
                        keys.append(k)
                        o.append(prefix + k)
                        o.append(str(v))
                else:
                    keys.append(str(value))
                    o.append(prefix + str(value))
        # Old dict format.
        # {'a': 'b'}  => ['+a','b']
        # {'a': None} => <skipped>
        # {'a': ''}   => ['+a']
        elif isinstance(data, (dict, collections.OrderedDict)):
            for key, value in data.items():
                if value is None:
                    continue
                keys.append(key)
                o.append(prefix + key)
                if value != '':
                    o.append(str(value))
        else:
            log.warn('BUG: Unknown _buildArgs data type: %r', type(data))
            log.warn('_buildArgs only accepts dict, OrderedDict, or list.')

        additions = {k: v for k, v in defaults.iteritems() if k not in keys}
        if len(additions) > 0:
            o += self._buildArgs(prefix, additions, {})

        return o

    def start_process(self):
        srcds_command = [os.path.join(self.gamedir, self.config.get('daemon.launcher', 'RustDedicated'))]
        srcds_command += [srcds_command[0]] # This is here because Unity is dumb and doesn't pass this shit properly.
        # Goes to the daemon.
        daemon_required = {}
        daemon_config = self.config.get('daemon.unity_args', {})
        #self._applyDefaultsTo(daemon_required, daemon_config, 'Configuration entry {key!r} is not present in daemon.srcds_args.  Default value {value!r} is set.')
        srcds_command += self._buildArgs('-', daemon_config, daemon_required)

        # Sent to Game_srv.so or whatever.
        ip, port = self.config.get('monitor.ip', '127.0.0.1'), self.config.get('monitor.port', 27015)
        ip, port = self.config.get('auth.rcon.ip', ip), self.config.get('auth.rcon.port', port)
        passwd = self.config.get('auth.rcon.password', None)
        game_required = {
            #'rcon.web': 1,
            'rcon.ip': ip,
            'rcon.port': port,
            'rcon.password': passwd
        }
        game_args = self.config.get('daemon.game_args', {})
        #self._applyDefaultsTo(game_required, game_args, 'Configuration entry {key!r} is not present in daemon.game_args.  Default value {value!r} is set.')
        srcds_command += self._buildArgs('+', game_args, game_required)

        with Chdir(self.gamedir):
            #cmd_daemonize(srcds_command, echo=True, critical=True)
            self.asyncProcess = LoggedProcess(srcds_command, srcds_command[0], echo=True, PTY=True, debug=False)
            self.asyncProcess.Start()

        self.find_process()

    def end_process(self):
        WatchdogEngine.end_process(self)
        if self.asyncProcess:
            self.asyncProcess.Stop()  # calls child.kill
            self.asyncProcess.WaitUntilDone()
