'''
Does things in reaction to Engine/Addon triggers.
Created on Apr 13, 2015

@author: Rob
'''

from buildtools.bt_logging import log

class PluginType(object):
    all = {}

    def __init__(self, _id=None):
        self.id = _id

    def __call__(self, f):
        if self.id is None:
            fname_p = f.__name__.split('_')
            self.id = fname_p[1].lower()
        log.info('Adding {0} as plugin type {1}.'.format(f.__name__, self.id))
        PluginType.all[self.id] = f
        return f

class BasePlugin(object):
    def __init__(self, engine, cfg):
        '''
        Constructor
        '''
        self.engine=engine
        self.config=cfg
        
    def validate(self):
        return False
        
    def hookEvent(self,subject,hook,handler):
        log.info('Hooking %s<%s>...',subject.__class__.__name__,hook)
        getattr(subject,hook).subscribe(handler)