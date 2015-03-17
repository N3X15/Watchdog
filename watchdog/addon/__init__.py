import os
from .base import AddonType
from .git import GitAddon

def CreateAddon(id, cfg, root):
    #print('{}: {}'.format(id,repr(cfg)))
    addon = AddonType.all[cfg['repo']['type']](id, cfg, os.path.join(root,id))
    if not addon.validate():
        return None
    return addon
