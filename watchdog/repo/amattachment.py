'''
Created on Apr 22, 2015

@author: Rob
'''
import os
import re
import tempfile
from lxml import etree
from watchdog.repo.base import RepoType, RepoDir
from buildtools.http import HTTPFetcher
import yaml
from buildtools import os_utils
from buildtools.bt_logging import log
from buildtools.os_utils import cmd, Chdir, decompressFile
import sys
from buildtools.timing import SimpleDelayer
from lxml.html.soupparser import fromstring
import requests

#(immunityreserveslots_src.sp - 290 views - 33.2 KB)
REG_PLUGIN_META = re.compile(r'\(([^ ]+) \- (\d+) views \- ([0-9\.]+ [A-Z]+)\)')
# (13.5 KB, 267 views) 
REG_FILE_META = re.compile(r'\(([0-9\.]+ [A-Z]+), (\d+) views\)')

ALLIEDMODDERS_BASEURL='https://forums.alliedmods.net/'
@RepoType('amattachment')
class AMAttachment(RepoDir):

    '''
    Attachment in an AlliedModders forum post.

    pattern: str - Regex matching the attachment filename.
    thread:  int - ID of the thread.
    post:    int - ID of the post.

    <a href="attachment.php?attachmentid=83286&d=1299423920">
        socket_3.0.1.zip
    </a>

    Example rule:

    ```
    repo:
      type: amattachment
      # https://forums.alliedmods.net/showthread.php?t=96670
      post: 96670
      # post: (implied to be 96670)
      files:
        - remote.sp
        - remote.inc
        - ztf2_grab.sp
        - ztf2_grab.inc
    '''

    VERSION = 1

    def __init__(self, addon, cfg, dest):
        RepoDir.__init__(self, addon, cfg, dest)
        self.postID = self.config['post']

        self.attachment_cache_file = os.path.join(self.cache_dir, 'amattachment.yml')
        self.staging_dir = os.path.join(self.cache_dir, 'staging')
        os_utils.ensureDirExists(self.staging_dir, mode=0o755)

        self.url = 'https://forums.alliedmods.net/showpost.php?p={0}&postcount=1'.format(self.postID)
        self.headers = {
            'user-agent': 'Watchdog/0.0.1',
        }
        #self.http = HTTPFetcher(self.url)
        #self.http.method = 'GET'
        #self.http.useragent = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:46.0) Gecko/20100101 Firefox/46.0'
        #self.http.referer = 'https://forums.alliedmods.net'

        self.delay = SimpleDelayer('threadcheck', min_delay=self.config.get('threadcheck-delay', 5) * 60)

        self.local_files = {}
        self.remote_files = {}

        self.expressions = []

    def validate(self):
        if not RepoDir.validate(self):
            return False
        for expr in self.config['files']:
            self.expressions.append(re.compile(expr))
        return True

    def clearCache(self):
        self.local_files = {}

    def preload(self):
        self.local_files = {}
        if os.path.isfile(self.attachment_cache_file):
            with open(self.attachment_cache_file, 'r') as f:
                loaded_version, body = yaml.load_all(f)
                if self.VERSION == loaded_version:
                    self.local_files = body['local-files']
                    self.remote_files = body['remote-files']
                    self.delay.lastCheck = body['last-check']

    def saveFileCache(self):
        with open(self.attachment_cache_file, 'w') as f:
            yaml.dump_all([self.VERSION, {
                'local-files': self.local_files,
                'remote-files': self.remote_files,
                'last-check': self.delay.lastCheck
            }], f, default_flow_style=False)

    def findFileMatch(self, filename):
        for regex in self.expressions:
            if regex.match(filename):
                return True
        return False

    def _checkThread(self):
        def add_file(filename, url, size):
            log.debug('Scraped %s (%s) from alliedmods forums.', filename, url)
            if self.findFileMatch(filename):
                self.remote_files[filename]=[url,size]
                log.debug('MATCH!')
        if self.delay.Check(quiet=True):
            self.delay.Reset()
            self.saveFileCache()
            self.remote_files = {}
            with log.debug("Checking %s...",self.url):
                #received=self.http.GetString()
                response = requests.get(self.url, headers=self.headers)
                received = response.text
                if 'Invalid Post specified. If you followed a valid link' in received:
                    log.critical('Invalid post %r specified in addon %s.',self.postID,self.addon.id)
                    sys.exit(1)
                with open('cache/TEST.htm','w') as f:
                    f.write(received)
                tree = fromstring(received)
                # for a in tree.xpath("id('td_post_{THREAD}')//a[starts-with(@href,'attachment.php')]".format(THREAD=self.postID)):
                for tr in tree.xpath("id('td_post_{THREAD}')//fieldset/table//tr".format(THREAD=self.postID)):  # Attachments.
                    if len(tr) == 2:
                        td = tr[1]
                        alist = td.findall('a')
                                
                        #with log.info('alist:'):
                        #    for i in range(len(alist)):
                        #        log.info('[%d] %r',i,etree.tostring(alist[i]))
                        
                        #with log.info('td:'):
                        #    for i in range(len(td)):
                        #        log.info('[%d] %r',i,etree.tostring(td[i]))
                        if len(alist) == 1:
                            # [0] '<a href="attachment.php?s=5b98916f4860ea6c76e445f1f97fa750&amp;attachmentid=99645&amp;d=1361802056">immunityreserveslots_cbase.smx</a> (13.5 KB, 267 views)&#13;\n\t\t\t&#13;\n\t\t&#13;\n\t'
                            a = alist[0]
                            metadata = a.tail.strip()
                            m = REG_FILE_META.search(metadata)
                            if m:
                                filename = a.text.strip()
                                size = m.group(1)
                                url = a.attrib['href']
                                add_file(filename, url, size)
                                
                        if len(alist) == 2:
                            # [0] '<a href="http://www.sourcemod.net/vbcompiler.php?file_id=99644"><strong>Get Plugin</strong></a> or&#13;\n\t\t\t\t'
                            # [1] '<a href="attachment.php?s=5b98916f4860ea6c76e445f1f97fa750&amp;attachmentid=99644&amp;d=1361802050">Get Source</a> (immunityreserveslots_src.sp - 290 views - 33.2 KB)&#13;\n\t\t\t&#13;\n\t\t&#13;\n\t'
                            found_compiled=''
                            for a in alist:
                                context=''
                                if a.text:
                                    context = a.text.strip()
                                else:
                                    context = a[0].text.strip()
                                if context == 'Get Source':
                                    metadata = a.tail.strip()
                                    m = REG_PLUGIN_META.search(metadata)
                                    if m:
                                        filename = m.group(1)
                                        size = m.group(3)
                                        url = a.attrib['href']
                                        add_file(filename, url, size)
                                        
                                        
                                        compiled_filename = '.'.join(filename.split('.')[:-1] + ['smx']) 
                                        if found_compiled!='' and compiled_filename not in self.remote_files:
                                            add_file(compiled_filename, found_compiled, size)
                                if context == 'Get Plugin': # Skip, since we can't get the size.
                                    found_compiled=a.attrib['href']

        for filename, fileinfo in self.remote_files.items():
            _, size = fileinfo
            if filename not in self.local_files:
                return False
            elif self.local_files[filename][1] != size:
                return False
        return True

    def isUp2Date(self):
        return self._checkThread()

    def update(self):
        self._checkThread()
        success = False
        change = False
        with log.info('Updating addon %s from an AlliedModders forum attachment...', self.addon.id):
            with Chdir(self.staging_dir):
                os_utils.ensureDirExists(self.destination)

                installTargets = self.config.get('install-targets', ['addons'])

                for filename, fileinfo in self.remote_files.iteritems():
                    url, size = fileinfo
                    url=ALLIEDMODDERS_BASEURL+url
                    print(filename,url,size)
                    dl = False
                    if filename not in self.local_files:
                        dl = True
                    elif self.local_files[filename][1] != size:
                        dl = True
                    if dl:
                        if not cmd(['wget', '-O', filename, url.strip()], echo=True, critical=True, globbify=False):
                            return False
                        if decompressFile(filename):
                            os.remove(filename)
                        change = True
                        self.local_files[filename] = (url, size)

                for src in installTargets:
                    fullpath = os.path.join(os.getcwd(), src)
                    self.addon.installFiles(fullpath, self.destination)
                self.addon.saveFileCache()

                if change:
                    self.saveFileCache()
                    success = True
        return success

    def remove(self):
        return True
