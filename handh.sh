#!/bin/bash
# Shell script to execute handhRL.py with the correct libraries for current Linux arch

echo Checking CPU architecture

if [ "$(uname -m)" == "i686" ]
then
	echo 32-bits found.
	ln -s ./linux32/libtcod.so ./libtcod.so 
	ln -s ./linux32/libtcodgui.so ./libtcodgui.so 
else
	if [ "$(uname -m)" == "x86_64" ]
	then
		echo 64-bits found.
		ln -s ./linux64/libtcod.so ./libtcod.so 
		ln -s ./linux64/libtcodgui.so ./libtcodgui.so 
	else
		echo "I'm sorry, handhRL only supports x86 architecture at this time."
		exit 1
	fi
fi

python handhrl.py

