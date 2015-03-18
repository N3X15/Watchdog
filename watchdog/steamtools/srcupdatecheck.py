#!/usr/bin/python
# coding=utf8

# srcupdatecheck v15 - part of
# NemRun v1.8.7 - john@pointysoftware.net, 09/27/2012

# Copyright 2012 john@pointysoftware.net
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# MODIFIED TO INTEGRATE WITH THINGS. - N3X15
# MODIFIED TO HAVE LESS-HACKY ERROR HANDLING - N3X15

import time
import sys
import xml.dom.minidom
import re
import os

gSteamAPI = 'https://api.steampowered.com'

# This supports Python 2.4+ and 3.0+, which requires a few tricks,
# and different libraries

if (sys.hexversion < 0x03000000):
    gPy3k = False
    import urllib
    import urllib2
else:
    gPy3k = True
    import urllib.request
    import urllib.parse

# try:
from buildtools.bt_logging import log
# except:
#    import logging as log
#
# Steam API Call
#

class APICallError(Exception):
    def __init__(self, raw_req, raw_res):
        self.raw_request = raw_req
        self.raw_response = raw_res
        

class APICallErrorResponse(APICallError):
    def __init__(self, raw_req, raw_res):
        APICallError.__init__(self, raw_req, raw_res)
        self.message = raw_res['error']
        
    def __str__(self):
        return 'API responded with error: {!r}'.format(self.message)
        

class APICallKeyError(APICallError):
    def __init__(self, raw_req, raw_res, key):
        APICallError.__init__(self, raw_req, raw_res)
        self.key = key
        
    def __str__(self):
        return 'Expected key {!r} is missing from response.'.format(self.key)
    
class APICallBadResponse(APICallError):
    def __str__(self):
        return 'API responded with invalid XML.'
    

def expectKeyIn(key,raw_req,raw_res):
    if key not in raw_res:
        raise APICallError(raw_req,raw_res,key)
    
LAST_REQUEST=None
def SteamAPICall(path, rawargs={}):
    with log.debug('Steam API Call[%s: %s]', path, rawargs):
        args = rawargs
        args['format'] = 'xml'
        if gPy3k:
            args = '?%s' % (urllib.parse.urlencode(args))
        else:
            args = '?%s' % (urllib.urlencode(args))
        
        url = "%s/%s/%s" % (gSteamAPI, path, args)
        try:
            if gPy3k:
                raw = urllib.request.urlopen(url, timeout=10).read().decode()
            else:
                raw = urllib2.urlopen(url, timeout=10).read()
        except Exception:
            log.error("API Call failed. URL: %r", url)
            return False
        
        try:
            dom = xml.dom.minidom.parseString(raw)
        except Exception:
            raise APICallBadResponse(url, raw)
            # log.error("API Call - Failed to parse XML result\n\tURL:\t'%s'\n=== Raw ===\n%s\n===========",url, raw)
            return False
        
        response = dom.getElementsByTagName('response')
        if not len(response):
            return False
        
        ret = {}
        for c in response[0].childNodes:
            if c.nodeType == xml.dom.minidom.Node.ELEMENT_NODE:
                if not len(c.childNodes):
                    ret[c.nodeName] = ""
                elif c.childNodes[0].data.lower() == "true":
                    ret[c.nodeName] = True
                elif c.childNodes[0].data.lower() == "false":
                    ret[c.nodeName] = False
                else:
                    ret[c.nodeName] = c.childNodes[0].data
                    
        expectKeyIn('success', url, ret)
        LAST_REQUEST=url
        if ret['success'] != True:
            raise APICallErrorResponse(url, ret)
        return ret

# 1 Up to date, 0 not, -1 call failed
# Note that the json returns 'version_is_listable', but valve never uses this,
# optional updates don't bump their version # :(
def RunCheck(no, appid, ver):
    response = {}
    try:
        response = SteamAPICall('ISteamApps/UpToDateCheck/v0001', { 'appid': appid, 'version': ver })
        expectKeyIn('success', LAST_REQUEST, response)
        expectKeyIn('up_to_date', LAST_REQUEST, response)
    except APICallError as e:
        with log.error('[API Call #%u] %s', no, e):
            log.error("Raw Request: %s", e.raw_request)
            log.error("Raw Response: %s", e.raw_response)
        return -1
    if response['up_to_date']:
        log.debug("[%u] API returned up to date!" % (no))
        return 1
    else:
        log.warn("[%u] API returned out of date - Version %r vs. %r" % (no, ver.replace('.', ''), response['required_version']))
        return 0

# Rewrite of steam.inf parser - N3X

# Use for broken steam.infs
KNOWN_APPIDS = {
    'cstrike': 90,  # Doesn't specify appID.
}
def CheckForUpdates(steaminffile, quiet=False):
    if not os.path.isfile(steaminffile):
        log.error("File \"%s\" does not exist!" % steaminffile)
        return True  # Needs update

    vals = {}
    with open(steaminffile, 'r') as f:
        for line in f:
            line = line.strip()
            if '=' in line:
                name, value = line.split('=')
                vals[name] = value
    ver = ''
    appID = ''
    game = ''
    try:
        ver = vals['PatchVersion']
        game = vals['ProductName']
        appID = KNOWN_APPIDS[game] if game in KNOWN_APPIDS else vals['appID']
    except KeyError:
        log.error('INVALID steam.inf!')
        log.error(repr(vals))
        return True
    
    if not quiet: 
        log.info("Checking %s... - AppID: %s, Version: %s", game, appID, ver)
    with log:
        # According to Tony, this API call can sometimes return out of date incorrectly (yay!)
        # So we'll keep our stupid try-multiple-times logic
        lastattempt = -1
        attempt = 1
        while True:
            ret = RunCheck(attempt, appID, ver);
            if (ret != -1):
                if (ret == lastattempt):
                    if (ret == 1):
                        if not quiet: log.info("Up to date (Confirmed after %u requests)" % (attempt))
                        return False
                    else:
                        if not quiet: log.info("Outdated (Confirmed after %u requests)" % (attempt))
                        return True
            else:
                # In the case where we're chain-failing for some reason, don't hammer the API
                time.sleep(5)
            lastattempt = ret
            attempt += 1
    
if __name__ == '__main__':
    if not len(sys.argv) == 2:
        print("Usage: ./srcupdatecheck /path/to/steam.inf")
        sys.exit(-1)
     
    if CheckForUpdates(sys.argv[1]):
        sys.exit(7)
    else:
        sys.exit(0)
