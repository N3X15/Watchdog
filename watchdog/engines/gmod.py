import os
from watchdog.engines.steam import SourceEngine
from buildtools.bt_logging import log
from watchdog.steamtools.vdf import VDFFile
from buildtools.os_utils import TimeExecution

class GModEngine(SourceEngine):
    def __init__(self, cfg):
        super(GModEngine, self).__init__(cfg)
        
        self.mount_filename = os.path.join(self.gamedir, self.game_content.game, 'cfg', 'mount.cfg')
        self.mountdepots_filename = os.path.join(self.gamedir, self.game_content.game, 'cfg', 'mountdepots.txt')
        
    def updateConfig(self):
        SourceEngine.updateConfig(self)
        
        depots = {}
        mounts = {}
        
        for appid, content in self.content.items():
            # :type content SteamContent:
            if appid == self.game_content.appID: 
                continue
            mounts[content.game] = content.destination
            
            for depotid in content.depots:
                depots[depotid] = '1'
        
        with log.info('Writing %d content entries to mount.cfg...', len(mounts)):
            VDFFile({'mountcfg':mounts}).Save(self.mount_filename)
            
        with log.info('Writing %d game depot entries to mountdepots.txt...', len(depots)):
            VDFFile({'gamedepotsystem':depots}).Save(self.mountdepots_filename)

    def updateFastDL(self):
        SourceEngine.updateFastDL(self)

        luaResources = self.config.get('fastdl.lua', 'lua/autorun/server/fastdl.lua')
        luaResources= os.path.join(self.gamedir, self.game_content.game, luaResources)
        destdir=os.path.dirname(luaResources)
        with log: # Re-indent ;)
            if not os.path.isdir(destdir):
                os.makedirs(destdir)
                log.info('Created %s',destdir)
            with TimeExecution('Wrote {}'.format(luaResources)):
                with open(luaResources, 'w') as f:
                    f.write('-- Automatically generated by watchdog.py ({} - {})\n'.format(__name__, self.__class__.__name__))
                    f.write('-- DO NOT EDIT BY HAND.\n')
                    f.write('if (SERVER) then\n')
                    for file in self.fastDLPaths:
                        f.write('\tresource.AddFile("{}")\n'.format(file))
                    f.write('end\n')
