import os
from .base import AddonType, BasicAddon
from .source.sourceaddon import SourceAddon
from .source.sourcepawn import SourcePawnAddon


def CreateAddon(engine, id, cfg, removing=False):
    addonclass = cfg.get('addon', 'basic')
    addon = AddonType.all[addonclass](engine, id, cfg)
    addon.removing = removing
    return addon
