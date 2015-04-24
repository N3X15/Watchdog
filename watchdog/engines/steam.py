import os
import time
import shutil
import sys

# This crap always triggers an import error in PEP8, ignore it.
from valve.source.a2s import ServerQuerier  # IGNORE:import-error
from valve.source.rcon import RCON  # IGNORE:import-error

from watchdog.engines.base import WatchdogEngine, ConfigAddon, EngineType
from watchdog.steam import srcupdatecheck
from buildtools.os_utils import cmd, Chdir, TimeExecution
from buildtools.bt_logging import log
from buildtools import os_utils, Config
from watchdog.utils import del_empty_dirs, LoggedProcess
import collections

STEAMCMD = ''
STEAMCMD_USERNAME = None
STEAMCMD_PASSWORD = None
STEAMCMD_STEAMGUARD = None


class SteamContent(object):
    All = []
    Lookup = {}

    @classmethod
    def LoadDefs(cls, dirname):
        yml = Config(None, template_dir='/')
        yml.LoadFromFolder(dirname)
        # pprint(yml.cfg))
        for appIdent, appConfig in yml.get('gamelist', {}).items():
            idents = [appIdent] + appConfig.get('aliases', [])
            app = cls(appConfig)
            app.aliases = idents
            cID = len(cls.All)
            cls.All.append(app)
            for ident in idents:
                cls.Lookup[ident] = cID
        # pprint(cls.Lookup)

    @classmethod
    def Find(cls, appIdent):
        cID = cls.Lookup.get(appIdent, -1)
        if cID == -1:
            return None
        return cls.All[cID]

    def __init__(self, cfg):
        self.appID = cfg['id']
        self.appName = cfg['name']
        self.game = cfg.get('game', '')
        self.config = cfg
        self.depots = cfg.get('depots', [])
        self.updatable = cfg.get('updatable', True)
        self.requires_login = cfg.get('requires-login', False)
        self.aliases = []
        self.destination = ''
        self.steamInf = ''
        self.validate = False

    def Configure(self, cfg, args):
        if self.requires_login:
            if STEAMCMD_USERNAME is None or STEAMCMD_PASSWORD is None:
                log.error('%s requires a username and password to access.', self.appName)
                sys.exit(1)
        self.validate = args.validate
        self.destination = os.path.expanduser(cfg.get('dir', '~/steam/content/{}'.format(self.appID)))
        self.steamInf = None
        if self.game != '':
            self.steamInf = os.path.join(self.destination, self.game, 'steam.inf')

    def IsUpdated(self):
        'Returns false if outdated.'
        if self.validate:
            return False
        if not self.updatable:
            return os.path.isfile(self.steamInf)
        return not srcupdatecheck.CheckForUpdates(self.steamInf, quiet=True)

    def Update(self):
        with log.info('Updating content for %s (#%s)...', self.appName, self.appID):
            login = ['anonymous']
            if self.requires_login and STEAMCMD_USERNAME and STEAMCMD_PASSWORD:
                login = [STEAMCMD_USERNAME, STEAMCMD_PASSWORD]
                if STEAMCMD_STEAMGUARD:
                    login.append(STEAMCMD_STEAMGUARD)
            shell_cmd = [
                STEAMCMD,
                '+login'] + login + [
                '+force_install_dir', self.destination,
                '+app_update', self.appID,
                'validate',
                '+quit'
            ]
            cmd(shell_cmd, echo=False, critical=True)
        if self.validate:
            self.validate = False


@EngineType('srcds')
class SourceEngine(WatchdogEngine):
    RESTART_ON_CHANGE = True
    FASTDL_PLUGIN_ID = 'fastdl'

    def __init__(self, cfg, args):
        global STEAMCMD, STEAMCMD_PASSWORD, STEAMCMD_STEAMGUARD, STEAMCMD_USERNAME  # IGNORE:global-statement Bite me.

        super(SourceEngine, self).__init__(cfg, args)

        STEAMCMD_USERNAME = cfg.get('auth.steam.username', None)
        STEAMCMD_PASSWORD = cfg.get('auth.steam.password', None)
        STEAMCMD_STEAMGUARD = cfg.get('auth.steam.steamguard', None)

        STEAMCMD = os.path.expanduser(os.path.join(cfg.get('paths.steamcmd'), 'steamcmd.sh'))
        
        self.gamedir = os.path.expanduser(cfg.get('paths.run'))

        self.content = {}
        self.game_content = None
        for appIdent, appCfg in cfg['content'].items():
            app = SteamContent.Find(appIdent)
            if app is None:
                log.warn('Unable to find app "%s". Skipping.', appIdent)
                continue
            app.Configure(appCfg, self.cmdline_args)
            self.content[app.appID] = app
            if app.destination == self.gamedir:
                self.game_content = app
                log.info('Found target game: %s', app.appName)

        if 'config' in cfg['git'] and 'repo' in cfg['git']['config']:
            self.configrepo = ConfigAddon(self, cfg.get('git.config'), os.path.join(self.gamedir, self.game_content.game))

        self.numPlayers = 0

        self.asyncProcess = None

        if self.config.get('fastdl', None) is not None:
            self.load_plugin(self.FASTDL_PLUGIN_ID)

        self.initialized.fire()

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

    def pingServer(self, noisy=False):
        if self.process is None or not self.process.is_running():
            return False

        maxtries = self.config.get('monitor.ping-tries', 3)
        for trynum in range(maxtries):
            if self._tryPing(trynum, maxtries, noisy):
                return True
            else:
                noisy = True  # PANIC
        return False

    def _tryPing(self, trynum, maxtries, noisy):
        ip, port = self.config.get('monitor.ip', '127.0.0.1'), self.config.get('monitor.port', 27015)
        timeout = self.config.get('monitor.timeout', 10)
        try:
            if noisy:
                log.info('Pinging %s:%d (try %d/%d)...', ip, port, trynum + 1, maxtries)
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

    def _applyDefaultsTo(self, defaults, subject, message=None):
        for k, v in defaults.items():
            if k not in subject:
                subject[k] = v
                if message is not None:
                    log.info(message, key=k, value=v)

    # Less duplicated code.
    def _buildArgs(self, prefix, data):
        o = []
        # Old dict format.
        # {'a': 'b'}  => ['+a','b']
        # {'a': None} => <skipped>
        # {'a': ''}   => ['+a']
        if isinstance(data, (dict, collections.OrderedDict)):
            for key, value in data.items():
                if value is None:
                    continue
                o.append(prefix + key)
                if value != '':
                    o.append(str(value))
        # New list format:
        # [{'a','b'}] => ['+a','b']
        # ['a']       => ['+a']
        elif isinstance(data, list):
            for value in data:
                if isinstance(value, (dict, collections.OrderedDict)):
                    for k, v in value.items():
                        o.append(prefix + k)
                        o.append(str(v))
                else:
                    o.append(prefix + str(value))
        else:
            log.warn('BUG: Unknown _buildArgs data type: %r', data)
            log.warn('_buildArgs only accepts dict, OrderedDict, or list.')
        return o

    def start_process(self):
        srcds_command = [os.path.join(self.gamedir, self.config.get('daemon.launcher', 'srcds_run'))]

        srcds_command.append('-norestart')

        # Goes to the daemon.
        daemon_required = {'ip': self.config.get('monitor.ip')}
        daemon_config = self.config.get('daemon.srcds_args', {})
        self._applyDefaultsTo(daemon_required, daemon_config, 'Configuration entry {key!r} is not present in daemon.srcds_args.  Default value {value!r} is set.')
        srcds_command += self._buildArgs('-', daemon_config)

        # Sent to Game_srv.so or whatever.
        game_required = {}
        game_args = self.config.get('daemon.game_args', {})
        self._applyDefaultsTo(game_required, game_args, 'Configuration entry {key!r} is not present in daemon.game_args.  Default value {value!r} is set.')
        srcds_command += self._buildArgs('+', game_args)

        niceness = self.config.get('daemon.niceness', 0)
        if niceness != 0:
            srcds_command = ['nice', '-n', niceness] + srcds_command

        with Chdir(self.gamedir):
            #cmd_daemonize(srcds_command, echo=True, critical=True)
            self.asyncProcess = LoggedProcess(srcds_command, 'srcds', echo=True, PTY=True, debug=False)
            self.asyncProcess.Start()

        self.find_process()

    def end_process(self):
        WatchdogEngine.end_process(self)
        if self.asyncProcess:
            self.asyncProcess.Stop()  # calls child.kill
            self.asyncProcess.WaitUntilDone()
