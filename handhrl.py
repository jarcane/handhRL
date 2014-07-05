import libtcodpy as libtcod
import math
import textwrap
import shelve
import time

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
MAP_WIDTH = 80
MAP_HEIGHT = 43
LIMIT_FPS = 20
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10
MAX_ROOM_MONSTERS = 3
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2 
MSG_HEIGHT = PANEL_HEIGHT - 1 
MAX_ROOM_ITEMS = 2 
INVENTORY_WIDTH = 50
HEAL_AMOUNT = 4 
LIGHTNING_DAMAGE = 20
LIGHTNING_RANGE = 5 
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8 
FIREBALL_DAMAGE = 12 
FIREBALL_RADIUS = 3 
MAX_MENU_STARS = 100

color_dark_wall = libtcod.Color(128,128,128)
color_light_wall = libtcod.Color(130,110,50)
color_dark_ground = libtcod.Color(192,192,192)
color_light_ground = libtcod.Color(200,180,50)

class Tile:
	#a tile of the map and its properties
	def __init__(self,blocked,block_sight = None):
		self.blocked = blocked
		
		#all tiles start unexplored
		self.explored = False
		
		#by default, if a tile is blocked, it also blocks sight
		if block_sight is None:	block_sight = blocked
		self.block_sight = block_sight

class Rect:
	#a rectangle on the map. used to characterize a room
	def __init__(self,x,y,w,h):
		self.x1 = x
		self.y1 = y 
		self.x2 = x + w 
		self.y2 = y + h 
	
	def center(self):
		center_x = (self.x1 + self.x2) / 2
		center_y = (self.y1 + self.y2) / 2
		return(center_x,center_y)
		
	def intersect(self,other):
		#return true if rectangle intersects with another one
		return (self.x1 <= other.x2 and self.x2 >= other.x1 and self.y1 <= other.y2 and self.y2 >= other.y1)

class Object:
	#this is a generic object: the player, a monster, an item, the stairs...
	#it's always represented by a character on the screen.
	def __init__(self,x,y,char,name,color,blocks=False, fighter=None, ai=None, item=None):
		self.x = x
		self.y = y 
		self.char = char
		self.name = name
		self.color = color
		self.blocks = blocks
		self.fighter = fighter
		if self.fighter:
			self.fighter.owner = self
		
		self.ai = ai
		if self.ai:
			self.ai.owner = self
		
		self.item = item
		if self.item:
			self.item.owner = self
	def move(self,dx,dy):
		#move by the given amount
		if not is_blocked(self.x + dx, self.y + dy):
			self.x += dx
			self.y += dy
	
	def draw(self):
		#set the color and then draw the character that represents this object at its position
		if libtcod.map_is_in_fov(fov_map,self.x,self.y):
			libtcod.console_set_default_foreground(con, self.color)
			libtcod.console_put_char(con,self.x,self.y,self.char,libtcod.BKGND_NONE)
	
	def clear(self):
		#erase the character that represents this object
		libtcod.console_put_char(con,self.x,self.y,' ',libtcod.BKGND_NONE)
		
	def move_towards(self, target_x, target_y):
		#vector from this object to the target, and distance
		dx = target_x - self.x 
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy ** 2)
		
		#normalise it to length 1 (preserving direction) then round it and
		#convert to integer so the movement is restricted to map grid
		dx = int(round(dx / distance))
		dy = int(round(dy / distance))
		self.move(dx, dy)
	
	def distance(self, x, y):
		#return the distance to some coordinates
		return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)
	
	def distance_to(self, other):
		#return the distance to another object
		dx = other.x - self.x 
		dy = other.y - self.y 
		return math.sqrt(dx ** 2 + dy ** 2)
	
	def send_to_back(self):
		#make this object be drawn first, so all others appear above it if they're in the same tile
		global objects
		objects.remove(self)
		objects.insert(0,self)

class Item:
	#an item that can be picked up and used.
	def __init__(self, use_function=None):
		self.use_function = use_function
	
	def use(self):
		#just call the use_function if it is defined
		if self.use_function is None:
			message('The ' + self.owner.name + ' cannot be used.')
		else:
			if self.use_function() != 'cancelled':
				inventory.remove(self.owner) #destroy after use unless cancelled
	
	def pick_up(self):
		#add to the player's inventory and remove from the map
		if len(inventory) >= 26:
			message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
		else:
			inventory.append(self.owner)
			objects.remove(self.owner)
			message('You picked up a ' + self.owner.name + '!', libtcod.green)
	
	def drop(self):
		#add to the map and remove from inventory. also, place at player coords
		objects.append(self.owner)
		inventory.remove(self.owner)
		self.owner.x = player.x
		self.owner.y = player.y 
		message('You dropped a ' + self.owner.name + '.', libtcod.yellow)
		

class Fighter:
	#combat-related properties and methods (monster, player, npc)
	def __init__(self, hp, defense, power, death_function=None):
		self.max_hp = hp
		self.hp = hp
		self.defense = defense
		self.power = power
		self.death_function = death_function
	
	def take_damage(self, damage):
		#apply damage if possible
		if damage > 0:
			self.hp -= damage
		
		#check for death. if there's a death function, call it
		if self.hp <= 0:
			function = self.death_function
			if function is not None:
				function(self.owner)
	
	def heal(self,amount):
		#heal by the given amount, without going over max_hp
		self.hp += amount
		if self.hp > self.max_hp:
			self.hp = self.max_hp		
	
	def attack(self, target):
		#a simple formula for attack damage
		damage = self.power - target.fighter.defense
		
		if damage > 0:
			#make the target take some damage
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.',libtcod.yellow)
			target.fighter.take_damage(damage)
		else:
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!', libtcod.normal_grey)

class BasicMonster:
	#AI for a basic monster
	def take_turn(self):
		#a basic monster takes its turn. If you can see it, it can see you
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			
			#move towards the player if far away
			if monster.distance_to(player) >= 2:
				monster.move_towards(player.x, player.y)
			
			#close enough, attack!
			elif player.fighter.hp > 0:
				monster.fighter.attack(player)

class ConfusedMonster:
	#AI for a temporarily confused monster (reverts to normal AI after a while)
	def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
		self.old_ai = old_ai
		self.num_turns = num_turns
	
	def take_turn(self):
		if self.num_turns > 0: #still confused
			#move in random direction and decrease confuse duration
			self.owner.move(libtcod.random_get_int(0,-1,1), libtcod.random_get_int(0,-1,1))
			self.num_turns -= 1 
		else: #restore previous AI
			self.owner.ai = self.old_ai
			message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)

def generate_starpic():
	img = libtcod.image_new(160,100)
	libtcod.image_clear(img, libtcod.black)
	colors = [libtcod.lightest_yellow, libtcod.lightest_grey, libtcod.white, libtcod.white, libtcod.light_orange, libtcod.darker_red]
	
	for x in range(MAX_MENU_STARS):
		x = libtcod.random_get_int(0,0,159)
		y = libtcod.random_get_int(0,0,99)
		c = libtcod.random_get_int(0,0,len(colors)-1)
		libtcod.image_put_pixel(img, x, y, colors[c])
	
	return img

def intro_sequence():
	libtcod.console_set_default_foreground(0,libtcod.green)
	intro_msg = [
		'*INITIATE COMM SEQUENCE EMERGENCY ALPHA-0x1*',
		'This is Guild Post Alpha Ceti calling GSS Ark-1.',
		'Ark-1, do you read?',
		'Captain Rogers, are you there?',
		'Can anyone read this?',
		'You must divert course, I repeat ...',
		'*LOSING SIGNAL*',
		'... collision course ...',
		'*MESSAGE CORRUPTED*',
		'... Gamma Crionis ...',
		'*26247525* class 4 *10040522* quarantine *21220104* highly unstable',
		'*23647515*',
		'We are sending help *21242056* stay alive.']
	
	for y in range(len(intro_msg)):
		key = libtcod.console_check_for_keypress()
		if key.vk == libtcod.KEY_ESCAPE:
			return
		else: 
			libtcod.console_print_ex(0, SCREEN_WIDTH/8, SCREEN_HEIGHT/5 + y*2,libtcod.BKGND_NONE,libtcod.LEFT,intro_msg[y])
			libtcod.console_flush()
			time.sleep(2)
	
	
def main_menu():
	global firstrun
	img = generate_starpic()
	
	#play intro sequence if starting up
	if firstrun:
		intro_sequence()
		firstrun = False
		
	while not libtcod.console_is_window_closed():
		#show the background image, at twice the regular resolution
		libtcod.image_blit_2x(img, 0,0,0)
							
		#show the game title and credits!
		libtcod.console_set_default_foreground(0,libtcod.light_yellow)
		libtcod.console_print_ex(0,SCREEN_WIDTH/2,SCREEN_HEIGHT/2-4,libtcod.BKGND_NONE,libtcod.CENTER,'HULKS AND HORRORS\nThe Roguelike')
		libtcod.console_print_ex(0, SCREEN_WIDTH/2,SCREEN_HEIGHT-2,libtcod.BKGND_NONE,libtcod.CENTER,'(c) 2014 by John \'jarcane\' Berry')
		
		#show options and wait for the player's choice
		choice = menu('',['Play a new game','Continue last game','Quit'],24)
		
		if choice == 0:
			new_game()
			play_game()
		if choice == 1:
			try:
				load_game()
			except:
				msgbox('\n No saved game to load.\n',24)
				continue
			play_game()
		elif choice == 2:
			break
			
def new_game():
	global player, inventory, game_msgs, game_state
	
	#create Player object
	fighter_component = Fighter(hp=30, defense=2, power=5, death_function=player_death)
	player = Object(0, 0, chr(1), 'player', libtcod.white, blocks=True, fighter=fighter_component)

	#generate map
	make_map()
	initialize_fov()
	
	game_state = 'playing'
	inventory = []
	
	#create the list of game messages and their colors, starts empty
	game_msgs = []
	
	# a warm welcoming message!
	message('You awaken from teleporter sickness in the bowels of an ancient hulk. You hear hissing in the distance.', libtcod.red)

def initialize_fov():
	global fov_recompute, fov_map
	fov_recompute = True
	libtcod.console_clear(con) #unexplored areas start black
	
	#create the FOV map according to the generated map
	fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

def play_game():
	global key, mouse
	
	player_action = None
	
	mouse = libtcod.Mouse()
	key = libtcod.Key()
	while not libtcod.console_is_window_closed():
		#render the screen
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
		render_all()
		
		libtcod.console_flush()
		
		#erase all objects at old locations before they move
		for object in objects:
			object.clear()
			
		#handle keys and exit game if needed
		player_action = handle_keys()
		if player_action == 'exit':
			msgbox('Game saved. Any key to continue.', 33)
			save_game()
			break
		
		#let monsters take their turn
		if game_state == 'playing' and player_action != 'didnt-take-turn':
			for object in objects:
				if object.ai:
					object.ai.take_turn()

def save_game():
	#open a new empty shelve (possibly rewriting old one) to write the game data
	file = shelve.open('savegame','n')
	file['map']	= map
	file['objects'] = objects
	file['player_index'] = objects.index(player)
	file['inventory'] = inventory
	file['game_msgs'] = game_msgs
	file['game_state'] = game_state
	file.close()

def load_game():
	#open the previous saved shelve and load the game data
	global map, objects, player, inventory, game_msgs, game_state
	
	file = shelve.open('savegame','r')
	map = file['map']
	objects = file['objects']
	player = objects[file['player_index']] # get index of player in objects list and access it
	inventory = file['inventory']
	game_msgs = file['game_msgs']
	game_state = file['game_state']
	file.close()
	
	initialize_fov()
	
def handle_keys():
	global key
	
	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
	elif key.vk == libtcod.KEY_ESCAPE:
		return 'exit'   #exit game
		
	#movement keys
	if game_state == 'playing':
		if key.vk == libtcod.KEY_UP:
			player_move_or_attack(0,-1)
		elif key.vk == libtcod.KEY_DOWN:
			player_move_or_attack(0,1)
		elif key.vk == libtcod.KEY_LEFT:
			player_move_or_attack(-1,0)
		elif key.vk == libtcod.KEY_RIGHT:
			player_move_or_attack(1,0)
		else:
			#test for other keys
			key_char = chr(key.c)
			
			if key_char == 'g':
				#pick up an item
				for object in objects:
					if object.x == player.x and object.y == player.y and object.item:
						object.item.pick_up()
						break
			if key_char == 'i':
				#show the inventory
				chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.use()
			if key_char == 'd':
				#show inventory, if an item is selected, drop it
				chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.drop()
			return 'didnt-take-turn'

def target_tile(max_range=None):
	#return the position of a tile left-clicked in player FOV (optionally in a range), or return (None,None) if right clicked
	global key, mouse
	while True:
		#render the screen. this reases the inventory and shows the names of objects under the mouse
		libtcod.console_flush()
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key, mouse)
		render_all()
		
		(x,y) = (mouse.cx, mouse.cy)
		
		if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map,x,y) and (max_range is None or player.distance(x,y) <= max_range)):
			return(x,y)
		if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
			return(None,None) #cancel on ESC or right clicked
		
def target_monster(max_range=None):
	#returns a clicked monster inside FOV up to a range, or None if right-clicked
	while True:
		(x,y) = target_tile(max_range)
		if x is None: #player cancelled
			return None
		
		#return first clicked monster, otherwise keep looping
		for obj in objects:
			if obj.x == x and obj.y == y and obj.fighter and obj != player: 
				return obj
		
def get_names_under_mouse():
	global mouse
	
	#return a string with the names of all objects under the mouse
	(x,y) = (mouse.cx, mouse.cy)
	
	#create a list with the names of all objects at the mouse's coordinates within FOV
	names = [obj.name for obj in objects
		if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
	names = ', '.join(names)  #join the names, seperated by commas
	return names.capitalize()
	
def player_move_or_attack(dx,dy):
	global fov_recompute
	global objects
	
	#the coordinates the player is moving to/attacking
	x = player.x + dx
	y = player.y + dy
	
	#try to find an attackable object there
	target = None
	for object in objects:
		if object.fighter and object.x == x and object.y == y:
			target = object
			break
	
	#attack if target found, move otherwise
	if target is not None:
		player.fighter.attack(target)
	else:
		player.move(dx, dy)
		fov_recompute=True
		
			
def create_room(room):
	global map
	#go through the tiles in the rectangle and make them passable
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = False
			map[x][y].block_sight = False
			
def place_objects(room):
	
	#choose random number of monsters
	num_monsters = libtcod.random_get_int(0,0, MAX_ROOM_MONSTERS)
	
	for i in range(num_monsters):
		#choose random spot for this monster
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		
		#only place it if the tile is not blocked
        
		if not is_blocked(x, y):
			if libtcod.random_get_int(0,0,100) < 80:
				#create a felix
				fighter_component = Fighter(hp=10, defense=0, power=3, death_function = monster_death)
				ai_component = BasicMonster()				
				monster = Object(x,y,'f', 'felix', libtcod.fuchsia, blocks=True, fighter=fighter_component, ai=ai_component)
			else:
				#create a lobsterman
				fighter_component = Fighter(hp=16, defense=1, power=4, death_function = monster_death)
				ai_component = BasicMonster()
				monster = Object(x,y,'L', 'lobsterman', libtcod.red, blocks=True, fighter=fighter_component, ai=ai_component)
			objects.append(monster)
	
	#choose a random number of items
	num_items = libtcod.random_get_int(0,0,MAX_ROOM_ITEMS)
	
	for i in range(num_items):
		#choose a random spot for the item
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		
		#only place it if the tile is not blocked
		if not is_blocked(x,y):
			dice = libtcod.random_get_int(0, 0, 100)
			if dice < 70:
				#create a healing item
				item_component = Item(use_function=cast_heal)
				item = Object(x, y, '!', 'dose of Opacaine', libtcod.violet, item=item_component)
			elif dice < 70+10:
				#create an arc lightning device 
				item_component = Item(use_function=cast_lightning)
				item = Object(x,y,'#','Tesla arc device', libtcod.light_yellow, item=item_component)
			elif dice < 70+10+10:
				#create a grenade
				item_component = Item(use_function=cast_fireball)
				item = Object(x,y,'#','inciendiary grenade', libtcod.light_yellow, item=item_component)
			else:
				#create a confuse item 
				item_component = Item(use_function=cast_confuse)
				item = Object(x,y,'#', 'neural scrambler', libtcod.light_yellow, item=item_component)
				
			objects.append(item)
			item.send_to_back() #items appear below other objects
			

def make_map():
	global map, objects
	
	#the list of objects with just the player
	objects = [player]
	
	#fill map with "unblocked" tiles
	map = [[ Tile(True)
		for y in range(MAP_HEIGHT) ]
			for x in range(MAP_WIDTH) ]
	
	#create two rooms
	rooms = []
	num_rooms = 0
	
	for r in range(MAX_ROOMS):
		#random width and height
		w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		#random position without leaving map
		x = libtcod.random_get_int(0,0, MAP_WIDTH - w - 1)
		y = libtcod.random_get_int(0,0, MAP_HEIGHT - h - 1)
		
		#"Rect" class makes rectangles easier to work with
		new_room = Rect(x,y,w,h)
		
		#run through the other rooms and see if they intersect with this one
		failed = False
		for other_room in rooms:
			if new_room.intersect(other_room):
				failed = True
				break
		
		if not failed:
			#this means there are no intersections so the room is valid
			
			#"paint" it to the map's tiles'
			create_room(new_room)
			place_objects(new_room)
			
			#center coordinates of new_room, will be useful later
			(new_x,new_y) = new_room.center()
			
			#print "room number" onto room (optional, not included in sample code)
			#remove later if issues arise, but I think it looks cool and H&H-y
			#room_no = Object(new_x,new_y,chr(65+num_rooms), 'room number', libtcod.white, blocks=False)
			#objects.insert(0,room_no)
			
			if num_rooms == 0:
				#this is the first room, where the player starts at
				player.x = new_x
				player.y = new_y
			else:
				#all rooms after the first:
				#connect it to the previous room with a tunnel
				
				#center coordinates of previous room
				(prev_x, prev_y) = rooms[num_rooms-1].center()
				
				if libtcod.random_get_int(0,0,1) == 1:
					#first move horizontally then vertically
					create_h_tunnel(prev_x,new_x,prev_y)
					create_v_tunnel(prev_y,new_y,new_x)
				else:
					#first move vertically then horizontally
					create_v_tunnel(prev_y,new_y,prev_x)
					create_h_tunnel(prev_x,new_x,new_y)
			
			#finally, append the new room to the list
			rooms.append(new_room)
			num_rooms += 1 
			
def menu(header, options, width):
	if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')
	
	#calculate total height for the header (after auto wrap) and one line per option
	header_height = libtcod.console_get_height_rect(con, 0,0,width,SCREEN_HEIGHT, header)
	if header == '':
		header_height = 0
	height = len(options) + header_height
	
	#create an off-screen console that represents the menu's window
	window = libtcod.console_new(width, height)
	
	#print the header with auto-wrap
	libtcod.console_set_default_foreground(window, libtcod.white)
	libtcod.console_print_rect_ex(window, 0,0,width, height,libtcod.BKGND_NONE,libtcod.LEFT,header)
	
	#print all the options
	y = header_height
	letter_index = ord('a')
	for option_text in options:
		text = '(' + chr(letter_index) + ')' + option_text
		libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
		y +=1
		letter_index += 1 
	
	#blit the contents of window to root console
	x = SCREEN_WIDTH/2 - width/2 
	y = SCREEN_HEIGHT/2 - height/2 
	libtcod.console_blit(window, 0,0,width,height,0,x,y,1.0,0.7)
	
	#present the root console to the player and wait for keypress
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)
	
	if key.vk == libtcod.KEY_ENTER and key.lalt: #special case, have to check for alt+enter for fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
	
	#convert the ASCII code to an index; if it corresponds to an option, return it
	index = key.c - ord('a')
	if index >= 0 and index < len(options): return index
	return None

def msgbox(text, width=50):
	menu(text,[],width) #use menu() as a sort of 'message box'
	
def inventory_menu(header):
	#show a menu of each item in the inventory as an option
	if len(inventory) == 0:
		options = ['Inventory is empty.']
	else:
		options = [item.name for item in inventory]
	
	index = menu(header,options, INVENTORY_WIDTH)
	
	#if an item was chosen, return it
	if index is None or len(inventory) == 0: return None
	return inventory[index].item 
			
def render_all():
	global color_light_wall
	global color_light_ground
	global fov_recompute
	
	if fov_recompute:
		#recompute FOV if needed
		fov_recompute = False
		libtcod.map_compute_fov(fov_map,player.x,player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
		
		#go through all tiles, and set their background color
		for y in range(MAP_HEIGHT):
			for x in range(MAP_WIDTH):
				visible = libtcod.map_is_in_fov(fov_map,x,y)
				wall = map[x][y].block_sight
				if not visible:
					#if it's not visible right now, the player can only see it if it's explored
					if map[x][y].explored:
						#it's out of the player FOV
						if wall:
							libtcod.console_set_char_background(con,x,y,color_dark_wall,libtcod.BKGND_SET)
						else:
							libtcod.console_set_char_background(con,x,y,color_dark_ground,libtcod.BKGND_SET)
						
				else:
					#it's visible
					if wall:
						libtcod.console_set_char_background(con,x,y,color_light_wall, libtcod.BKGND_SET)
					else:
						libtcod.console_set_char_background(con,x,y,color_light_ground, libtcod.BKGND_SET)
					map[x][y].explored = True
					
	#draw all objects in the list
	for object in objects:
		if object != player:
			object.draw()
	player.draw()
	
	#blit con to root console
	libtcod.console_blit(con,0,0,MAP_WIDTH,MAP_HEIGHT,0,0,0)
	
	#prepare to render the GUI panel
	libtcod.console_set_default_background(panel, libtcod.black)
	libtcod.console_clear(panel)
	
	#print the game messages, one line at a time
	y = 1
	for (line,color) in game_msgs:
		libtcod.console_set_default_foreground(panel, color)
		libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
		y += 1
		
	#show the player's stats
	render_bar(1,1,BAR_WIDTH,'HP', player.fighter.hp, player.fighter.max_hp, libtcod.light_red, libtcod.darker_red)
	
	#display names of objects under mouse
	libtcod.console_set_default_foreground(panel, libtcod.light_gray)
	libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())
	
	#blit the contents of "panel" to root console
	libtcod.console_blit(panel, 0,0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

def render_bar(x,y,total_width,name,value,maximum,bar_color, back_color):
	#render a bar (HP, XP, etc). first calculate width of bar
	bar_width = int(float(value) / maximum * total_width)
	
	#render background first
	libtcod.console_set_default_background(panel, back_color)
	libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)
	
	#now render the bar on top
	libtcod.console_set_default_background(panel, bar_color)
	if bar_width > 0:
		libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
	
	#finally, some centered text with the values
	libtcod.console_set_default_foreground(panel, libtcod.white)
	libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER, name + ': ' + str(value) + '/' + str(maximum))

def message(new_msg, color = libtcod.white):
	#split the message if necessary, among multiple lines
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
	
	for line in new_msg_lines:
		#if the bugger is full, remove the first line to make room for the new one.
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]
		
		#add the new line as a tuple, with the text and color
		game_msgs.append((line,color))
	
def create_h_tunnel(x1,x2,y):
	global map
	for x in range(min(x1,x2),max(x1,x2)+1):
		map[x][y].blocked = False
		map[x][y].block_sight = False
		
def create_v_tunnel(y1,y2,x):
	global map
	#vertical tunnel
	for y in range(min(y1,y2),max(y1,y2)+1):
		map[x][y].blocked = False
		map[x][y].block_sight = False

def is_blocked(x,y):
	global map
	global objects
	
	#first test the map tile
	if map[x][y].blocked:
		return True
	
	#now check for blocking objects
	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True
	
	return False

def closest_monster(max_range):
	#find closest enemy, up to a max range and in player FOV
	closest_enemy = None
	closest_dist = max_range + 1 #start with slightly more than max range
	
	for object in objects:
		if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
			#calculate distance between this object and the player
			dist = player.distance_to(object)
			if dist < closest_dist: #it's closer so remember it 
				closest_enemy = object
				closest_dist = dist 
	return closest_enemy
				
	
def player_death(player):
	#the game ended!
	global game_state
	message('You died!', libtcod.red)
	game_state = 'dead'
	
	#for added effect, transform player into a corpse!
	player.char = '%'
	player.color = libtcod.white

def monster_death(monster):
	#transform it into a nasty corpse! it doesn't block, can't be
	#attacked, and doesn't move
	message(monster.name.capitalize() + ' is dead!', libtcod.orange)
	monster.char = '%'
	monster.color = libtcod.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()

def cast_heal():
	#heal the player
	if player.fighter.hp == player.fighter.max_hp:
		message('You are already at full health.',libtcod.red)
		return 'cancelled'
	
	message('Your pain subsides, for now.',libtcod.light_violet)
	player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
	#find closest enemy inside max range and damage it
	monster = closest_monster(LIGHTNING_RANGE)
	if monster is None: #no enemy found within range
		message('No enemy is within arc range.')
		return 'cancelled'
	
	#zap it!
	message('A bolt of electricity arcs into the ' + monster.name + ' with a loud ZZZAP! The damage is ' + str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
	monster.fighter.take_damage(LIGHTNING_DAMAGE)

def cast_confuse():
	#ask for target and confuse it
	message('Left-click an enemy to confuse it, or right-click to cancel.', libtcod.light_cyan)
	monster = target_monster(CONFUSE_RANGE)
	if monster is None: return 'cancelled'
	old_ai = monster.ai
	monster.ai = ConfusedMonster(old_ai)
	monster.ai.owner = monster #tell the new component who owns it
	message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around!', libtcod.light_green)

def cast_fireball():
	#ask the player for a target tile to throw a 'fireball' at (ie. grenade, AOE, etc)
	message('Left-click a target tile, or right-click to cancel.', libtcod.light_cyan)
	(x,y) = target_tile()
	if x is None: return 'cancelled'
	message('The device explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!',libtcod.orange)
	
	for obj in objects: #damage every fighter in range, including the player
		if obj.distance(x,y) <= FIREBALL_RADIUS and obj.fighter:
			message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
			obj.fighter.take_damage(FIREBALL_DAMAGE)
	
#############################################
# Initialization & Main Loop
#############################################
libtcod.console_set_custom_font('terminal8x8_gs_ro.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_ASCII_INROW)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Hulks and Horrors', False)
libtcod.sys_set_fps(LIMIT_FPS)
panel = libtcod.console_new(SCREEN_WIDTH,PANEL_HEIGHT)
con = libtcod.console_new(MAP_WIDTH,MAP_HEIGHT)

firstrun = True

main_menu()