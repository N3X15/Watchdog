import os
from .base import AddonType, BasicAddon
from .source.metamodsource import MetaModSource
from .source.sourcemod import SourceMod
from .source.sourcepawn import SourcePawnAddon
from .source.limetech import LimetechExt

def CreateAddon(engine, id, cfg):
    # print('{}: {}'.format(id,repr(cfg)))
    addonclass = cfg.get('addon', 'basic')
    addon = AddonType.all[addonclass](engine, id, cfg)
    if not addon.validate():
        return None
    return addon
