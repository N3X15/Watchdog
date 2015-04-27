from buildtools.bt_logging import log
from watchdog.engines.srcds import SourceEngine
from watchdog.engines.gmod import GModEngine
from watchdog.engines.base import EngineType
from watchdog.engines.vrage import VRageEngine


def GetEngine(globalCfg, arguments):
    engineID = globalCfg.get('daemon.engine', None)
    if engineID is None:
        log.error('daemon.engine is not specified in watchdog.yml.')
        return None
    engine = EngineType.all[engineID](globalCfg, arguments)
    return engine
