'''
Created on Apr 27, 2015

@author: Rob
'''
import os
import sys
import collections
from watchdog.steam import srcupdatecheck

from buildtools.config import Config
from buildtools.bt_logging import log
from buildtools.os_utils import cmd
from watchdog.engines.base import WatchdogEngine, ConfigAddon

STEAMCMD = ''


class SteamContent(object):
    All = []
    Lookup = {}

    Username = None
    Password = None
    SteamGuard = None

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

    @classmethod
    def GlobalConfigure(cls, cfg):
        global STEAMCMD
        cls.Username = cfg.get('auth.steam.username', None)
        cls.Password = cfg.get('auth.steam.password', None)
        cls.SteamGuard = cfg.get('auth.steam.steamguard', None)

        STEAMCMD = os.path.expanduser(os.path.join(cfg.get('paths.steamcmd'), 'steamcmd.sh'))

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
        self.forced_platform=None

    def Configure(self, cfg, args):
        if self.requires_login:
            if self.Username is None or self.Password is None:
                log.error('%s requires a username and password to access.', self.appName)
                sys.exit(1)
        self.validate = args.validate
        self.destination = os.path.expanduser(cfg.get('dir', '~/steam/content/{}'.format(self.appID)))
        self.forced_platform = cfg.get('force-platform',None)
        self.steamInf = None
        if self.game != '':
            self.steamInf = os.path.join(self.destination, self.game, 'steam.inf')

    def IsUpdated(self):
        'Returns false if outdated.'
        if self.validate or not self.steamInf:
            return False
        if not self.updatable:
            return os.path.isfile(self.steamInf)
        return not srcupdatecheck.CheckForUpdates(self.steamInf, quiet=True)

    def Update(self):
        with log.info('Updating content for %s (#%s)...', self.appName, self.appID):
            login = ['anonymous']
            if self.requires_login and self.Username and self.Password:
                login = [self.Username, self.Password]
                if self.SteamGuard:
                    login.append(self.SteamGuard)
            if self.forced_platform:
                login += ['+@sSteamCmdForcePlatformType', self.forced_platform]
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


class SteamBase(WatchdogEngine):

    def __init__(self, cfg, args):

        super(SteamBase, self).__init__(cfg, args)

        SteamContent.GlobalConfigure(cfg)

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
            #print(repr(appCfg))
            target = appCfg.get('target', None)
            if target is None:
                target = app.destination == self.gamedir
            elif target:
                    log.info('Game %r forced to be target game',app.appName)
            if target:
                self.game_content = app
                log.info('Found target game: %s', app.appName)

        if cfg.get('repos.config',None) is not None:
            self.configrepo = ConfigAddon(self, cfg.get('repos.config'), os.path.join(self.gamedir, self.game_content.game))

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

    def applyDefaultsTo(self, defaults, subject, message=None):
        for k, v in defaults.items():
            if isinstance(subject, (dict, collections.OrderedDict)):
                if k not in subject:
                    subject[k] = v
                    if message is not None:
                        log.info(message, key=k, value=v)
            elif isinstance(subject, list):
                for value in subject:
                    if isinstance(value, (dict, collections.OrderedDict)) and k in v:
                        value[k] = v
                        if message is not None:
                            log.info(message, key=k, value=v)

    # Less duplicated code.
    def buildArgs(self, prefix, data, defaults):
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
            log.warn('BUG: Unknown buildArgs data type: %r', type(data))
            log.warn('buildArgs only accepts dict, OrderedDict, or list.')

        additions = {k: v for k, v in defaults if k not in keys}
        if len(additions) > 0:
            o += self.buildArgs(prefix, additions, {})

        return o
