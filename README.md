handhRL
=======

### Description
A simple roguelike based on the Hulks and Horrors tabletop RPG written with Python 2.7 and libtcod.

As of now the engine is complete, but additional work will be needed to build it up to a more accurate representation of the source. The eventual goal is to be as accurate a representation of the H&H rules as can be managed, allowing for adjustment to the form.

### Instructions
#### On Windows:

From source (requires Python 2.7 properly set in $path):

`python handhrl.py (or double-click handhrl.py)`

For binary releases, extract the zip and just run handhrl.exe.

#### On Linux
A convenient shell script has been provided to automatically select the correct version of libtcod, create symlinks to the right *.so files, and then run the game.

Just make sure that handh.sh is properly set to executable and run it from the handhRL directory.

```
chmod +x ./handh.sh
./handh.sh
```

Note that this need only be run once, after which you should be able to run it from the directory as normal with:

`python handhrl.py`

### Credits and Licensing
handhRL is currently maintained by John 'jarcane' Berry.

Code is based on the excellent tutorial here: http://www.roguebasin.com/index.php?title=Complete_Roguelike_Tutorial,_using_python%2Blibtcod

Hulks and Horrors is a tabletop roleplaying game inspired by classic Red Box, with a sci-fi reimagining. More on that here: http://www.bedroomwallpress.com/p/hulks-and-horrors.html

Screenshots are available on our official page at: http://www.bedroomwallpress.com/p/handhrl.html
Our RogueBasin page is here: http://www.roguebasin.com/index.php?title=HandhRL

libtcod is distributed under the BSD license. See LIBTCOD-LICENSE.txt. The SDL library is distributed according to the LGPL as mentioned in README-SDL.txt.

handhRL is Copyright 2014 by John S. Berry III. 

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
