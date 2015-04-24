#!/bin/bash
for addon_name in "$@"
do
        rm $addon_name.yml
done

