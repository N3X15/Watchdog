'''
For sourcemod itself.
plugins:
  reservedslots: on/off
  
'''


import os
from buildtools import log
from watchdog.addon.base import AddonType, BasicAddon
from watchdog.addon.source.sourceaddon import SourceAddon

@AddonType('sourcemod')
class SourceModAddon(SourceAddon):

    '''
    Source Engine Addon (MM:S etc)
    '''

    def __init__(self, engine, aid, cfg):
        cfg['type']='source-addon'
        super(SourceModAddon, self).__init__(engine, aid, cfg)
        self.plugin_state=self.config.get('plugins',{})
        self.plugin_dir=os.path.join(BasicAddon.ClassDestinations['source-addon'],'sourcemod','plugins')

        
    def copyfile(self, src, destdir):
        if src.endswith('.smx'):
            relpath = os.path.relpath(destdir, self.plugin_dir)
            filename = os.path.basename(src)
            basefilename,ext = os.path.splitext(filename)
            currentstate = 'disabled' not in relpath
            newstate = self.plugin_state.get(basefilename,currentstate) 
            if currentstate != newstate:
                relpath = os.sep.join([d for d in relpath.split(os.sep) if d not in ('disabled')])
                destdir=''
                origdestdir=destdir
                if newstate:
                    destdir=self.plugin_dir
                    log.info('Enabling plugin %s (%s->%s)...',basefilename, src,destdir)
                else:
                    destdir=os.path.join(self.plugin_dir,'disabled')
                    log.info('Disabling plugin %s (%s->%s)...',basefilename, src,destdir)
            destdir=os.path.join(destdir,relpath)
        super(SourceModAddon, self).copyfile(src,destdir)
            