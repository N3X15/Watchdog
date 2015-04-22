import os
from watchdog.engines.steam import SourceEngine
from buildtools.bt_logging import log
from watchdog.steam.vdf import VDFFile  # IGNORE:import-error
from buildtools.os_utils import TimeExecution
from watchdog.engines.base import EngineType

@EngineType('garrysmod')
class GModEngine(SourceEngine):
    FASTDL_PLUGIN_ID = '_gmfastdl'

    def __init__(self, cfg, args):
        super(GModEngine, self).__init__(cfg, args)

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
            VDFFile({'mountcfg': mounts}).Save(self.mount_filename)

        with log.info('Writing %d game depot entries to mountdepots.txt...', len(depots)):
            VDFFile({'gamedepotsystem': depots}).Save(self.mountdepots_filename)
