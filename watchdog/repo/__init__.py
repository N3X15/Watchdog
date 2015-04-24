import os
from .base import RepoType
from .git import GitRepo
from .hg import HgRepo
from .amsnapshot import AlliedModdersSnapshot

def CreateRepo(addon, cfg, root):
    repoclass = cfg.get('type', 'basic')
    repo = RepoType.all[repoclass](addon, cfg, root)
    if not repo.validate():
        return None
    return repo
