import logging
import logging.handlers
import os
import sys
import argparse
import shutil

script_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(script_dir, 'lib', 'buildtools'))

from buildtools import os_utils
from buildtools.os_utils import cmd, Chdir

base_conf_dir = os.path.join(script_dir, 'conf.d')
local_conf_dir = os.path.join(os.getcwd(), 'conf.d')
base_addon_dir = os.path.join(base_conf_dir, 'addons')
local_addon_dir = os.path.join(local_conf_dir, 'addons')

base_template_dir = os.path.join(script_dir, 'conf.template')


def handle_enable(args):
    for module in args.module:
        if not enable_addon(module):
            break


def handle_disable(args):
    for module in args.module:
        if not disable_addon(module):
            break


def enable_addon(addon):
    addon = addon.split('.')[0]
    link = os.path.join(local_addon_dir, addon + '.yml')
    filename = os.path.join(base_addon_dir, addon + '.yml.disabled')
    if not os.path.isfile(filename):
        log.error("Addon %r doesn't exist.", addon)
        return False
    if os.path.islink(link):
        log.warn("Addon %r is already enabled.", addon)
        return True
    os_utils.ensureDirExists(os.path.dirname(link),mode=0o755)
    if cmd(['ln', '-sf', filename, link], show_output=False, critical=True):
        log.info('Addon %r enabled.', addon)
    return True


def disable_addon(addon):
    addon = addon.split('.')[0]
    link = os.path.join(local_addon_dir, addon + '.yml')
    filename = os.path.join(base_addon_dir, addon + '.yml.disabled')
    if not os.path.isfile(filename):
        log.error("Addon %r doesn't exist.", addon)
        return True
    if not os.path.islink(link):
        log.warn("Addon %r is already disabled.", addon)
        return False
    os.remove(link)
    log.info('OK: Addon %r disabled.', addon)
    return False


def cp(src, dest):
    if not os.path.isfile(dest):
        log.info('cp -p "%s" "%s"', src, dest)
        shutil.copy2(src, dest)


def handle_install(args):
    os_utils.ensureDirExists(args.directory, mode=0o700, noisy=True)
    with Chdir(args.directory):
        os_utils.ensureDirExists('conf.d', mode=0o700, noisy=True)
        os_utils.ensureDirExists('conf.d/addons', mode=0o700, noisy=True)
        os_utils.ensureDirExists('cache', mode=0o700, noisy=True)
        cp(os.path.join(base_conf_dir, 'fastdl.yml.disabled'), os.path.join(local_conf_dir, 'fastdl.yml.example'))
        if args.addon:
            for addon in args.addon:
                enable_addon(addon)
        log.info('Writing launch.sh...')
        with open('launch.sh', 'w') as f:
            f.write('#!/bin/bash\n')
            f.write('cd "{cwd}"\n'.format(cwd=os.path.realpath(args.directory)))
            f.write('python "{script}" $@\n'.format(script=os.path.join(script_dir, 'Watchdog.py')))
        log.info('chmod 700 launch.sh')
        os.chmod('launch.sh',0o700)
        cp(os.path.join(script_dir,'conf.templates',args.template), os.path.join(os.getcwd(), 'watchdog.yml'))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Configure addon modules.')
    subcmds = parser.add_subparsers()

    enable_cmd = subcmds.add_parser('enable', help='Enable addons in conf.d/addons/.')
    enable_cmd.add_argument('module', nargs='+', help="Module filename, relative to conf.d/addons, with no file extensions. (e.g. garrysmod/ulx)")
    enable_cmd.set_defaults(func=handle_enable)

    disable_cmd = subcmds.add_parser('disable', help='Disable addons in conf.d/addons/.')
    disable_cmd.add_argument('module', nargs='+', help="Module filename, relative to conf.d/addons, with no file extensions. (e.g. garrysmod/ulx)")
    disable_cmd.set_defaults(func=handle_disable)

    install_cmd = subcmds.add_parser('install', help="Create a run environment in a given directory.")
    install_cmd.add_argument('template', type=str, help="Which conf.template do you want to use for watchdog.yml?")
    install_cmd.add_argument('directory', type=str, help="Where to create the run directory?  (Cannot be the watchdog script directory).")
    install_cmd.add_argument('-a', '--addon', nargs='*', type=str, help="Enable an addon by the given name. (e.g. garrysmod/ulx)")
    install_cmd.set_defaults(func=handle_install)

    logFormatter = logging.Formatter(fmt='%(asctime)s [%(levelname)-8s]: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')  # , level=logging.INFO, filename='crashlog.log', filemode='a+')
    log = logging.getLogger()

    _args = parser.parse_args()
    print(repr(_args))
    _args.func(_args)
