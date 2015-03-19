import os, socket, time
from watchdog.engines.base import WatchdogEngine, ConfigAddon
from watchdog.steamtools import srcupdatecheck, sourcequery
from buildtools.os_utils import cmd, cmd_daemonize, Chdir, TimeExecution
from buildtools.bt_logging import log
from buildtools import os_utils, ENV, Config
from valve.source.a2s import ServerQuerier
from pprint import pprint
from valve.source.rcon import RCON
import shutil
from watchdog.steamtools.vdf import VDFFile
from watchdog.utils import md5sum, del_empty_dirs

STEAMCMD_USERNAME = None
STEAMCMD_PASSWORD = None
STEAMCMD_STEAMGUARD = None

class SteamContent(object):
    All = []
    Lookup = {}
    @classmethod
    def LoadDefs(cls, dir):
        yml = Config(None)
        yml.LoadFromFolder(dir)
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
        if cID == -1: return None
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
        
    def Configure(self, cfg):
        if self.requires_login:
            if STEAMCMD_USERNAME is None or STEAMCMD_PASSWORD is None:
                log.error('%s requires a username and password to access.', self.appName)
                sys.exit(1)
        self.destination = os.path.expanduser(cfg.get('dir', '~/steam/content/{}'.format(self.appID)))
        self.steamInf = None
        if self.game != '':
            self.steamInf = os.path.join(self.destination, self.game, 'steam.inf')
        
    def IsUpdated(self):
        'Returns false if outdated.'
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

class SourceEngine(WatchdogEngine):
    def __init__(self, cfg):
        global STEAMCMD, STEAMCMD_PASSWORD, STEAMCMD_STEAMGUARD, STEAMCMD_USERNAME
        
        super(SourceEngine, self).__init__(cfg)
        
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
            app.Configure(appCfg)
            self.content[app.appID] = app
            if app.destination == self.gamedir:
                self.game_content = app
                log.info('Found target game: %s', app.appName)
            
        self.configrepo = ConfigAddon(cfg.get('git.config', {}), os.path.join(self.gamedir, self.game_content.game))
        
    def updateAlert(self):
        ip, port = self.config.get('monitor.ip', '127.0.0.1'), self.config.get('monitor.port', 27015)
        ip, port = self.config.get('auth.rcon.ip', ip), self.config.get('auth.rcon.port', port)
        wait = self.config.get('monitor.restart-wait', 30)
        passwd = self.config.get('auth.rcon.password', None)
        if passwd is None: return
        with log.info('Sending warning via RCON to %s:%d...', ip, port):
            if self.process is None or not self.process.is_running():
                log.warn('Process is not running, skipping rcon warning.')
                return
            if not self.pingServer(noisy=True):
                log.warn('PING failed, skipping rcon warning.') 
                return
            with RCON((ip, port), passwd) as rcon:
                if wait > 0:
                    rcon('say [Watchdog] Update detected, restarting in {time} seconds.'.format(time=wait))
                    time.sleep(wait)
                rcon('say [Watchdog] Update detected, restarting now.')
                
    def compressFile(self, src, dest):
        destdir = os.path.dirname(dest)
        if not os.path.isdir(destdir):
            os.makedirs(destdir)
            log.info('Created %s', destdir)
        if not os_utils.canCopy(src, dest + '.bz2'):
            return False
        shutil.copy2(src, dest)
        level = str(self.config.get('fastdl.compression-level', 9))
        level = max(min(level, 1), 9)
        # -f = force overwrite
        # -z = compress
        # -q = quiet
        # -1-9 = compression level (fast-best)
        cmd(['bzip2', '-zfq' + str(level), dest], critical=True)
        return True
        
    def updateFastDL(self):
            self.fastDLPaths = []
            gamepath = os.path.join(self.gamedir, self.game_content.game)
            old_hashes = {}
            new_hashes = {}
            '''
            fastDLCache=os.path.join(self.cache_dir,'fastdl.vdf')
            if os.path.isfile(fastDLCache):
                try:
                    vdf = VDFFile()
                    vdf.Load(fastDLCache)
                    old_hashes = vdf.rootnode.children['checksums']
                except Exception as e:
                    log.error('Error loading checksum cache: %s', e)
            '''
                    
            destdir = self.config.get('fastdl.destination', '')
            exclude_dirs = self.config.get('fastdl.exclude-dirs', ['.git', '.svn'])
            include_exts = self.config.get('fastdl.include-exts', ["mdl", "vmt", "vtf", "wav", 'mp3', 'bsp']);
            addon_dirs = ['addons']  # , 'gamemodes']
            nScanned = 0
            nNew = 0
            nRemoved = 0
            with log.info('Updating FastDL for {}... (This may take a while)'.format(gamepath)):
                with TimeExecution('Updated files'):
                    for root, dirs, files in os.walk(gamepath):
                        for file in files:
                            nScanned += 1
                            fullpath = os.path.join(root, file)
                            _, ext = os.path.splitext(fullpath)
                            ext = ext.strip('.')
                            if ext not in include_exts:
                                continue
                            relpath = os.path.relpath(fullpath, gamepath)
                            relpathparts = relpath.split(os.sep)
                            if relpathparts[0] in addon_dirs:
                                relpathparts = relpathparts[2:]
                            else:
                                continue
                            ignore = False
                            for relpathpart in relpathparts:
                                if relpathpart in exclude_dirs:
                                    ignore = True
                            if ignore: continue
                            relpath = '/'.join(relpathparts)
                            self.fastDLPaths.append(relpath)
                            # md5 = md5sum(fullpath)
                            # new_hashes[relpath] = md5
                            # if fullpath in old_hashes and old_hashes[relpath] == md5:
                            destfile = os.path.join(destdir, os.sep.join(relpathparts))
                            if self.compressFile(fullpath, destfile):
                                nNew += 1
                # sys.exit(1)
                with TimeExecution('Removed dead files'):
                    for root, dirs, files in os.walk(destdir):
                        for file in files:
                            remove = False
                            fullpath = os.path.join(root, file)
                            realpath = fullpath
                            if fullpath.endswith('.bz2'):
                                fullpath = fullpath[:-4]
                            _, ext = os.path.splitext(fullpath)
                            ext = ext.strip('.')
                            if ext not in include_exts: 
                                remove = True
                            relpath = os.path.relpath(fullpath, destdir)
                            relpathparts = relpath.split(os.sep)
                            if relpathparts[0] in addon_dirs:
                                relpathparts = relpathparts[1:]
                            for relpathpart in relpathparts:
                                if relpathpart in exclude_dirs:
                                    remove = True
                            relpath = '/'.join(relpathparts)
                            if relpath not in self.fastDLPaths:
                                remove = True
                            if remove: 
                                log.info('Removing %s...', relpath)
                                os.remove(realpath)
                                nRemoved += 1
                with TimeExecution('Removed dead directories'):
                    del_empty_dirs(destdir)
                #VDFFile({'checksums':new_hashes}).Save(fastDLCache)
                log.info('Scanned: %d, Added: %d, Removed: %d', nScanned, nNew, nRemoved)
                
    def updateAddons(self):
        WatchdogEngine.updateAddons(self)
        
        # Update FastDL
        if self.config.get('fastdl.destination', None) is not None:
            self.updateFastDL()
            
    def pingServer(self, noisy=False):
        if self.process is None or not self.process.is_running():
            return False
        
        ip, port = self.config.get('monitor.ip', '127.0.0.1'), self.config.get('monitor.port', 27015)
        timeout = self.config.get('monitor.timeout', 30)
        try:
            if noisy: log.info('Pinging %s:%d...', ip, port)
            with log:
                server = ServerQuerier((ip, port), timeout=timeout)
                # with TimeExecution('Ping'):
                numplayers = server.get_info()['player_count']
                if noisy: log.info('%d players connected.', numplayers)
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
        for appid, content in self.content.items():
            attempts = 0
            while not content.IsUpdated() and attempts < 3:
                content.Update()
                attempts += 1
    
    def start_process(self):
        srcds_command = [os.path.join(self.gamedir, self.config.get('game.launcher', 'srcds_linux'))]
        
        for key, value in self.config.get('srcds.srcds_args', {}).items():
            if value is None: continue
            srcds_command.append('-' + key)
            if value != '':
                srcds_command.append(str(value))
                
        for key, value in self.config.get('srcds.game_args', {}).items():
            if value is None: continue
            srcds_command.append('+' + key)
            if value != '':
                srcds_command.append(str(value))
                
        niceness = self.config.get('srcds.niceness', 0)
        if niceness != 0:
            srcds_command = ['nice', '-n', niceness] + srcds_command
        
        with Chdir(self.gamedir):
            cmd_daemonize(srcds_command, echo=True, critical=True)
        
        self.find_process()
