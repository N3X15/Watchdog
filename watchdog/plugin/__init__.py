from watchdog.plugin.base import PluginType
from watchdog.plugin.fastdl import *

def CreatePlugin(plID, engine, cfg):
    p = PluginType.all[plID](engine, cfg)
    if not p.validate():
        return None
    return p