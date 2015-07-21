'''
Created on May 1, 2015

@author: Rob
'''
import collections

from watchdog.plugin.base import BasePlugin, PluginType
from buildtools.bt_logging import log
from buildtools.os_utils import cmd


@PluginType('update-script')
class UpdateScriptPlugin(BasePlugin):

    def __init__(self, engine, cfg):
        super(UpdateScriptPlugin, self).__init__(engine, cfg)

        self.engine.initialized.subscribe(self.onInitialize)

    def validate(self):
        if not self.config.get('run-on-update', None):
            log.error('plugins.update-script.run-on-update is not set.')
            return False
        return True

    def onInitialize(self):
        plName = self.__class__.__name__
        with log.info('Initializing %s...', plName):
            self.hookEvent(self.engine, 'updated', self.runOnUpdate)
            self.hookEvent(self.engine, 'addons_updated', self.runOnUpdate_AU)
        log.info('%s initialized.', plName)

    # Less duplicated code.
    def buildArgs(self, prefix, data, defaults):
        keys = []
        o = []
        # New list format:
        # [{'a','b'}] => ['+a','b']
        # ['a']       => ['+a']
        if isinstance(data, list):
            for value in data:
                if isinstance(value, (dict, collections.OrderedDict)):
                    for k, v in value.items():
                        keys.append(k)
                        o.append(prefix + k)
                        o.append(str(v))
                else:
                    keys.append(str(value))
                    o.append(prefix + str(value))
        # Old dict format.
        # {'a': 'b'}  => ['+a','b']
        # {'a': None} => <skipped>
        # {'a': ''}   => ['+a']
        elif isinstance(data, (dict, collections.OrderedDict)):
            for key, value in data.items():
                if value is None:
                    continue
                keys.append(key)
                o.append(prefix + key)
                if value != '':
                    o.append(str(value))
        else:
            log.warn('BUG: Unknown buildArgs data type: %r', type(data))
            log.warn('buildArgs only accepts dict, OrderedDict, or list.')

        additions = {k: v for k, v in defaults if k not in keys}
        if len(additions) > 0:
            o += self.buildArgs(prefix, additions, {})

        return o

    def runOnUpdate_AU(self, addon_names=None):
        return self.runOnUpdate()

    def runOnUpdate(self):
        with log.info('Running run-on-update script...'):
            cmdlist = self.config.get('run_on_update')
            if isinstance(cmdlist, (str, unicode)):
                cmdlist = cmdlist.split(' ')
            cmd(cmdlist, echo=True, show_output=True)
