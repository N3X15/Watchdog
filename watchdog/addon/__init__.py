import os
from .base import AddonType, BasicAddon
from .source.sourceaddon import SourceAddon
from .source.sourcepawn import SourcePawnAddon

def CreateAddon(engine, id, cfg):
    addonclass = cfg.get('addon', 'basic')
    addon = AddonType.all[addonclass](engine, id, cfg)
    if not addon.validate():
        return None
    return addon
