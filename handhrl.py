import libtcodpy as libtcod

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
MAP_WIDTH = 80
MAP_HEIGHT = 45
LIMIT_FPS = 20

color_dark_wall = libtcod.Color(0,0,100)
color_dark_ground = libtcod.Color(50,50,150)

class Tile:
	#a tile of the map and its properties
	def __init__(self,blocked,block_sight = None):
		self.blocked = blocked
		
		#by default, if a tile is blocked, it also blocks sight
		if block_sight is None:	block_sight = blocked
		self.block_sight = block_sight

class Object:
	#this is a generic object: the player, a monster, an item, the stairs...
	#it's always represented by a character on the screen.
	def __init__(self,x,y,char,color):
		self.x = x
		self.y = y 
		self.char = char
		self.color = color
		
	def move(self,dx,dy):
		#move by the given amount
		if not map[self.x + dx][self.y + dy].blocked:
			self.x += dx
			self.y += dy
	
	def draw(self):
		#set the color and then draw the character that represents this object at its position
		libtcod.console_set_default_foreground(con, self.color)
		libtcod.console_put_char(con,self.x,self.y,self.char,libtcod.BKGND_NONE)
	
	def clear(self):
		#erase the character that represents this object
		libtcod.console_put_char(con,self.x,self.y,' ',libtcod.BKGND_NONE)
		
def handle_keys():
	global playerx,playery
	
	key = libtcod.console_wait_for_keypress(True)
	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
	elif key.vk == libtcod.KEY_ESCAPE:
		return True   #exit game
		
	#movement keys
	if libtcod.console_is_key_pressed(libtcod.KEY_UP):
		player.move(0,-1)
	elif libtcod.console_is_key_pressed(libtcod.KEY_DOWN):
		player.move(0,1)
	elif libtcod.console_is_key_pressed(libtcod.KEY_LEFT):
		player.move(-1,0)
	elif libtcod.console_is_key_pressed(libtcod.KEY_RIGHT):
		player.move(1,0)

def make_map():
	global map
	
	#fill map with "unblocked" tiles
	map = [[ Tile(False)
		for y in range(MAP_HEIGHT) ]
			for x in range(MAP_WIDTH) ]
	
	map[30][22].blocked = True
	map[30][22].block_sight = True
	map[50][22].blocked = True
	map[50][22].block_sight = True
	
def render_all():
	global color_light_wall
	global color_light_ground
	
	#go through all tiles, and set their background color
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			wall = map[x][y].block_sight
			if wall:
				libtcod.console_set_char_background(con,x,y,color_dark_wall,libtcod.BKGND_SET)
			else:
				libtcod.console_set_char_background(con,x,y,color_dark_ground,libtcod.BKGND_SET)
	
	#draw all objects in the list
	for object in objects:
		object.draw()
	
	#blit con to root console
	libtcod.console_blit(con,0,0,SCREEN_WIDTH,SCREEN_HEIGHT,0,0,0)
	

#############################################
# Initialization & Main Loop
#############################################
libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Hulks and Horrors', False)

con = libtcod.console_new(SCREEN_WIDTH,SCREEN_HEIGHT)

#create Player object
player = Object(SCREEN_WIDTH/2, SCREEN_HEIGHT/2, '@', libtcod.white)

#create an NPC
npc = Object(SCREEN_WIDTH/2 - 5, SCREEN_HEIGHT/2, '@', libtcod.yellow)

#list of objects
objects = [npc, player]

#generate map
make_map()

while not libtcod.console_is_window_closed():
	#draw all objects in the list
	render_all()
	
	libtcod.console_flush()
		
	#erase old object locations before they move
	for object in objects:
		object.clear()
	
	#handle keys and exit game if needed
	exit = handle_keys()
	if exit:
		break