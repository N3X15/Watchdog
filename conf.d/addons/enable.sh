#!/bin/bash
BASEDIR=`pwd`
for addon_name in "$@"
do
        if [ -f $BASEDIR/$addon_name.yml ]; then
                echo "E: $addon_name is already enabled."
        else
                ln -sfv $BASEDIR/$addon_name.yml.disabled $BASEDIR/$addon_name.yml
        fi
done

