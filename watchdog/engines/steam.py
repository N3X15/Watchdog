import os, socket
from watchdog.engines.base import WatchdogEngine, ConfigRepo
from watchdog.steamtools import srcupdatecheck, sourcequery
from buildtools.os_utils import cmd, cmd_daemonize, Chdir
from buildtools.bt_logging import log
from buildtools import os_utils, ENV

class SteamContent(object):
    def __init__(self, appid, cfg):
        self.appID = appid
        self.appName = cfg['name']
        self.game = cfg.get('game','')
        self.config = cfg
        self.destination = os.path.expanduser(cfg.get('dir', '~/steam/content/{}'.format(appid)))
        self.steamInf = os.path.join(self.destination, cfg['game'], 'steam.inf')
        
    def IsUpdated(self):
        return not srcupdatecheck.CheckForUpdates(self.steamInf)
        
    def Update(self):
        with log.info('Updating content for %s (#%s)...', self.appName, self.appID):
            shell_cmd = [
                STEAMCMD,
                '+login', 'anonymous',
                '+force_install_dir', self.destination,
                '+app_update', self.appID,
                'validate',
                '+quit'
            ]
            cmd(shell_cmd, echo=True, critical=True)

class SourceEngine(WatchdogEngine):
    def __init__(self, cfg):
        global STEAMCMD
        super(SourceEngine, self).__init__(cfg)
        
        STEAMCMD = os.path.expanduser(os.path.join(cfg.get('paths.steamcmd'), 'steamcmd.sh'))
        self.gamedir = os.path.expanduser(cfg.get('paths.run'))
        
        self.content = {}
        self.game_content=None
        for appid, ccfg in cfg['content'].items():
            aID = int(appid)
            self.content[aID] = SteamContent(aID, ccfg)
            if ccfg.get('dir','') == self.gamedir:
                self.game_content=self.content[aID]
            
        self.configrepo = ConfigRepo(cfg.get('git.config', {}), os.path.join(self.gamedir,self.game_content.game))
        
    def pingServer(self):
        if self.process is not None and self.process.is_running():
            print(self.process.pid)
            return True
        return False

        ip, port = self.config.get('monitor.ip', '127.0.0.1'), self.config.get('monitor.port', 27015)
        try:
            log.info('Pinging %s:%d...',ip, port)
            server = sourcequery.SourceQuery(ip, port, timeout=30.0)
            info = server.info()
            if info is None:
                return False
            else:
                log.info('Received A2S_INFO reply in %ds', info['ping'])
                return True
        except socket.error as e:
            log.error(e)
            return False

    def checkForContentUpdates(self):
        for appID, content in self.content.items():
            if not content.IsUpdated():
                log.warn('AppID %s is out of date!',appID)
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
