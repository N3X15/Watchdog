import os
from .base import AddonType, BasicAddon

def CreateAddon(id, cfg):
    #print('{}: {}'.format(id,repr(cfg)))
    #addon = AddonType.all[cfg['repo']['type']](id, cfg, os.path.join(root,id))
    addonclass=cfg.get('addon','basic')
    addon = AddonType.all[addonclass](id,cfg)
    if not addon.validate():
        return None
    return addon