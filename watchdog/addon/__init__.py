import os
from .base import AddonType
from .git import GitAddon

def CreateAddon(id, cfg, root):
    cfg = cfg['repo']
    addon = AddonType.all[cfg['type']](id, cfg, os.path.join(root,id))
    if not addon.validate():
        return None
    return addon
