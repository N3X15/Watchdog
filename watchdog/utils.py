import hashlib, os
from buildtools.bt_logging import log

script_dir=''

def getCacheDir():
    return os.path.join(script_dir,'cache')

def md5sum(filename):
    with open(filename, mode='rb') as f:
        d = hashlib.md5()
        while True:
            buf = f.read(4096)  # 128 is smaller than the typical filesystem block
            if not buf:
                break
            d.update(buf)
        return d.hexdigest().upper()

def del_empty_dirs(src_dir):
    ndeleted=-1
    totalDel=0
    while ndeleted!=0:
        ndeleted=0
        for dirpath, dirnames, filenames in os.walk(src_dir, topdown=False):  # Listing the files
            if dirpath == src_dir:
                break
            if len(filenames) == 0 and len(dirnames) == 0:
                log.info('Removing %s (empty)', dirpath)
                os.rmdir(dirpath)
                ndeleted += 1
                totalDel += 1
    return totalDel