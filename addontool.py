import logging
import logging.handlers
import os
import sys
import argparse

script_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(script_dir, 'lib', 'buildtools'))

from buildtools.os_utils import cmd

script_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(script_dir, 'lib', 'buildtools'))
sys.path.append(os.path.join(script_dir, 'lib', 'valve'))
# print(repr(sys.path))

conf_dir=os.path.join(os.getcwd(),'conf.d','addons')

def handle_enable(args):
    for module in args.module:
        module = module.split('.')[0]
        link = os.path.join(conf_dir,module+'.yml')
        filename = os.path.join(conf_dir,module+'.yml.disabled')
        if not os.path.isfile(filename):
            log.error("Module %r doesn't exist.",module)
            return
        if os.path.islink(link):
            log.warn("Module %r is already enabled.",module)
            continue
        if cmd(['ln','-sf',filename,link],show_output=False,critical=True):
            log.info('Module %r enabled.',module)

def handle_disable(args):
    for module in args.module:
        module = module.split('.')[0]
        link = os.path.join(conf_dir,module+'.yml')
        filename = os.path.join(conf_dir,module+'.yml.disabled')
        if not os.path.isfile(filename):
            log.error("Module %r doesn't exist.",module)
            return
        if not os.path.islink(link):
            log.warn("Module %r is already disabled.",module)
            continue
        os.remove(link)
        log.info('OK: Module %r disabled.',module)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Configure addon modules.')
    subcmds = parser.add_subparsers()
    
    enable_cmd = subcmds.add_parser('enable',help='Enable addons in conf.d/addons/.')
    enable_cmd.add_argument('module',nargs='+',help="Module filename, relative to conf.d/addons, with no file extensions.")
    enable_cmd.set_defaults(func=handle_enable)
    
    disable_cmd = subcmds.add_parser('disable',help='Disable addons in conf.d/addons/.')
    disable_cmd.add_argument('module',nargs='+',help="Module filename, relative to conf.d/addons, with no file extensions.")
    disable_cmd.set_defaults(func=handle_disable)

    logFormatter = logging.Formatter(fmt='%(asctime)s [%(levelname)-8s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')  # , level=logging.INFO, filename='crashlog.log', filemode='a+')
    log = logging.getLogger()
    
    _args = parser.parse_args()
    _args.func(_args)