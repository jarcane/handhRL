'''
handhRL
Hulks and Horrors: The Roguelike

Copyright 2014 by John S. Berry III

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
'''

import libtcodpy as libtcod
import math
import textwrap
import shelve
import time
import os

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
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1
INVENTORY_WIDTH = 50
HEAL_AMOUNT = [1, 4]
LIGHTNING_DAMAGE = [2, 12]
LIGHTNING_RANGE = 5
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
FIREBALL_DAMAGE = [1, 6]
FIREBALL_RADIUS = 3
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150
LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30

color_dark_wall = libtcod.Color(128, 128, 128)
color_light_wall = libtcod.Color(130, 110, 50)
color_dark_ground = libtcod.Color(192, 192, 192)
color_light_ground = libtcod.Color(200, 180, 50)


class Tile:
    # a tile of the map and its properties
    def __init__(self, blocked, block_sight=None):
        self.blocked = blocked

        # all tiles start unexplored
        self.explored = False

        # by default, if a tile is blocked, it also blocks sight
        if block_sight is None:
            block_sight = blocked
        self.block_sight = block_sight


class Rect:
    # a rectangle on the map. used to characterize a room
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def center(self):
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return center_x, center_y

    def intersect(self, other):
        # return true if rectangle intersects with another one
        return self.x1 <= other.x2 and self.x2 >= other.x1 and self.y1 <= other.y2 and self.y2 >= other.y1


class Object:
    # this is a generic object: the player, a monster, an item, the stairs...
    # it's always represented by a character on the screen.
    def __init__(self, x, y, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, item=None,
                 equipment=None):
        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.color = color
        self.blocks = blocks
        self.always_visible = always_visible
        self.fighter = fighter
        if self.fighter:
            self.fighter.owner = self

        self.ai = ai
        if self.ai:
            self.ai.owner = self

        self.item = item
        if self.item:
            self.item.owner = self

        self.equipment = equipment
        if self.equipment:  # let the equipment component know who owns it
            self.equipment.owner = self

            # there must be an item component for the equipment component to work properly
            self.item = Item()
            self.item.owner = self


    def move(self, dx, dy):
        # move by the given amount
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

    def draw(self):
        # set the color and then draw the character that represents this object at its position
        if libtcod.map_is_in_fov(fov_map, self.x, self.y) or (self.always_visible and map[self.x][self.y].explored):
            libtcod.console_set_default_foreground(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

    def clear(self):
        # erase the character that represents this object
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

    def move_towards(self, target_x, target_y):
        # vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        # normalise it to length 1 (preserving direction) then round it and
        # convert to integer so the movement is restricted to map grid
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx, dy)

    def distance(self, x, y):
        # return the distance to some coordinates
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def distance_to(self, other):
        # return the distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def send_to_back(self):
        # make this object be drawn first, so all others appear above it if they're in the same tile
        global objects
        objects.remove(self)
        objects.insert(0, self)


class Item:
    # an item that can be picked up and used.
    def __init__(self, use_function=None):
        self.use_function = use_function

    def use(self):
        # just call the use_function if it is defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner)  # destroy after use unless cancelled

        # special case: if object has equipment component, the use option is to equip/dequip
        if self.owner.equipment:
            self.owner.equipment.toggle_equip()
            return

    def pick_up(self):
        # add to the player's inventory and remove from the map
        if len(inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '!', libtcod.green)

        # special case: automatically equip, if corresponding slot is unused
        equipment = self.owner.equipment
        if equipment and get_equipped_in_slot(equipment.slot) is None:
            equipment.equip()

    def drop(self):
        # special case: if equipped item, remove before dropping
        if self.owner.equipment:
            self.owner.equipment.dequip()

        # add to the map and remove from inventory. also, place at player coords
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.', libtcod.yellow)


class Equipment:
    # an object that can be equipped, yielding bonuses. automatically adds the item component.
    def __init__(self, slot, to_hit_bonus=0, damage_bonus=0, damage_roll=None, armor_bonus=0, max_hp_bonus=0):
        self.to_hit_bonus = to_hit_bonus
        self.damage_bonus = damage_bonus
        self.damage_roll = damage_roll
        self.armor_bonus = armor_bonus
        self.max_hp_bonus = max_hp_bonus
        self.slot = slot
        self.is_equipped = False

    def toggle_equip(self):  # toggle equip/dequip state
        if self.is_equipped:
            self.dequip()
        else:
            self.equip()

    def equip(self):
        # if the slot is already being used, dequip whatever is there first
        old_equipment = get_equipped_in_slot(self.slot)
        if old_equipment is not None:
            old_equipment.dequip()

        # equip an object and show a message about it
        self.is_equipped = True
        message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)

    def dequip(self):
        # dequip object and show a message about it.
        if not self.is_equipped:
            return
        self.is_equipped = False
        message('Dequipped ' + self.owner.name + ' from ' + self.slot + '.', libtcod.light_yellow)


class Fighter:
    # combat-related properties and methods (monster, player, npc)
    def __init__(self, hp, armor_class, to_hit, damage, damage_roll, xp, death_function=None):
        self.base_max_hp = hp
        self.hp = hp
        self.base_armor_class = armor_class
        self.base_to_hit = to_hit
        self.base_damage = damage
        self.base_roll = damage_roll
        self.xp = xp
        self.death_function = death_function

    @property
    def to_hit(self):
        bonus = sum(equipment.to_hit_bonus for equipment in get_all_equipped(self.owner))
        return self.base_to_hit + bonus

    @property
    def armor_class(self):  # return actual defense, by summing up the bonuses from all equipped items
        bonus = sum(equipment.armor_bonus for equipment in get_all_equipped(self.owner))
        return self.base_armor_class + bonus

    @property
    def damage(self): # return actual damage bonus, plus any special bonuses
        bonus = sum(equipment.damage_bonus for equipment in get_all_equipped(self.owner))
        return self.base_damage + bonus

    @property
    def damage_roll(self): # return current damage roll or roll from equipment
        for equipment in get_all_equipped(self.owner):
            if equipment.damage_roll:
                return equipment.damage_roll
        return self.base_roll

    @property
    def max_hp(self):  # return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
        return self.base_max_hp + bonus

    def take_damage(self, damage):
        # apply damage if possible
        if damage > 0:
            self.hp -= damage

        # check for death. if there's a death function, call it
        if self.hp <= 0:
            function = self.death_function
            if function is not None:
                function(self.owner)

            if self.owner != player:  # yield xp to player
                player.fighter.xp += self.xp

    def heal(self, amount):
        # heal by the given amount, without going over max_hp
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

    def attack(self, target):
        # first check for successful attack
        to_hit_target = self.to_hit + target.fighter.armor_class + 5
        if rolldice(1, 20) >= to_hit_target:
            message(self.owner.name.capitalize() + ' misses the ' + target.name + '.')
            return

        # now roll for damage (curr. using OD&D style)
        damage = rolldice(*self.damage_roll) + self.damage

        if damage > 0:
            # make the target take some damage
            message(self.owner.name.capitalize() + ' hits the ' + target.name + ' for ' + str(damage) + ' hit points.',
                    libtcod.yellow)
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' hits the ' + target.name + ' but it has no effect!',
                    libtcod.normal_grey)


class BasicMonster:
    # AI for a basic monster
    def __init__(self):
        pass

    def take_turn(self):
        # a basic monster takes its turn. If you can see it, it can see you
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):

            # move towards the player if far away
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)

            # close enough, attack!
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)


class ConfusedMonster:
    # AI for a temporarily confused monster (reverts to normal AI after a while)
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self):
        if self.num_turns > 0:  # still confused
            # move in random direction and decrease confuse duration
            self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
            self.num_turns -= 1
        else:  # restore previous AI
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)


def generate_starpic():
    # Generates a random starfield pattern and stores it in img
    img = libtcod.image_new(160, 100)
    libtcod.image_clear(img, libtcod.black)
    colors = [libtcod.lightest_yellow, libtcod.lightest_grey, libtcod.white, libtcod.white, libtcod.light_orange,
              libtcod.darker_red]

    for x in range(100):
        x = libtcod.random_get_int(0, 0, 159)
        y = libtcod.random_get_int(0, 0, 99)
        c = libtcod.random_get_int(0, 0, len(colors) - 1)
        libtcod.image_put_pixel(img, x, y, colors[c])

    return img


def generate_screen():
    # create 'computer screen' backdrop and store in screen_img
    screen_img = libtcod.image_new(160, 100)
    for x in range(124):
        for y in range(68):
            libtcod.image_put_pixel(screen_img, x + 16, y + 16, libtcod.grey)
    for x in range(120):
        for y in range(60):
            libtcod.image_put_pixel(screen_img, x + 18, y + 18, libtcod.darkest_green)
    for x in range(3):
        libtcod.image_put_pixel(screen_img, x + 132, 80, libtcod.red)
    return screen_img


def show_text_log(text, img=None, delay=True):
    # takes list of text and displays it line by line against a black screen
    # optional parameters: img = an image based in libtcod.image format, defaults to None (black screen)
    # delay = whether to use the text delay, defaults to True (for cinematic style sequences)
    if img is None:
        img = libtcod.image_new(160, 100)
    libtcod.image_blit_2x(img, 0, 0, 0)

    libtcod.console_set_default_foreground(0, libtcod.green)

    for y in range(len(text)):
        key = libtcod.console_check_for_keypress()
        if key.vk == libtcod.KEY_ESCAPE:
            return
        else:
            libtcod.console_print_ex(0, SCREEN_WIDTH / 8, SCREEN_HEIGHT / 5 + y * 2, libtcod.BKGND_NONE, libtcod.LEFT,
                                     text[y])
            libtcod.console_flush()
            if delay == True:
                time.sleep(1.5)

    libtcod.console_wait_for_keypress(True)


def intro_sequence():
    # Shows a text intro 'cinematic' sequence for starting up a new game.

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
        '*26247525* class 4 *10040522* quarantine ...',
        '... *21220104* highly unstable ...',
        '*23647515*',
        'We are sending help *21242056* stay alive.']

    show_text_log(intro_msg, generate_screen())


def main_menu():
    # The main game menu.

    img = generate_starpic()

    while not libtcod.console_is_window_closed():
        # show the background image, at twice the regular resolution
        libtcod.image_blit_2x(img, 0, 0, 0)

        # show the game title and credits!
        libtcod.console_set_default_foreground(0, libtcod.light_yellow)
        libtcod.console_print_ex(0, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 4, libtcod.BKGND_NONE, libtcod.CENTER,
                                 'HULKS AND HORRORS\nThe Roguelike')
        libtcod.console_print_ex(0, SCREEN_WIDTH / 2, SCREEN_HEIGHT - 2, libtcod.BKGND_NONE, libtcod.CENTER,
                                 '(c) 2014 by John \'jarcane\' Berry')

        # Change menu options to match state of 'savegame'
        if os.path.isfile('savegame'):
            newopt = 'Overwrite current save'
        else:
            newopt = 'Play a new game'

        # show options and wait for the player's choice
        choice = menu('', [newopt, 'Continue last save', 'Quit'], 26)

        if choice == 0:
            new_game()
            play_game()

        if choice == 1:
            try:
                load_game()
            except:
                msgbox('\n No saved game to load.\n', 24)
                continue
            play_game()
        elif choice == 2:
            break


def new_game():
    global player, inventory, game_msgs, game_state, firstrun, dungeon_level

    # play intro sequence if starting up
    if firstrun:
        intro_sequence()
        firstrun = False

    # create Player object
    # Assume Soldier class with 10 STR, 10 DEX, 10 CON
    fighter_component = Fighter(hp=rolldice(3,6)+rolldice(1,10), armor_class=10, to_hit=1, damage=1, damage_roll=[1, 3],
                                xp=0, death_function=player_death)
    player = Object(0, 0, chr(1), 'player', libtcod.white, blocks=True, fighter=fighter_component)
    player.level = 1

    # generate map
    dungeon_level = 1
    make_map()
    initialize_fov()

    game_state = 'playing'
    inventory = []

    # create the list of game messages and their colors, starts empty
    game_msgs = []

    # a warm welcoming message!
    message('You awaken in a damp cave beneath the surface of Gamma Crionis IV. The ground rumbles beneath you.',
            libtcod.red)

    # initial equipment: a knife
    equipment_component = Equipment(slot='right hand', damage_roll=[1, 4])
    obj = Object(0, 0, '-', 'combat knife', libtcod.sky, equipment=equipment_component)
    inventory.append(obj)
    equipment_component.equip()
    obj.always_visible = True


def initialize_fov():
    global fov_recompute, fov_map
    fov_recompute = True
    libtcod.console_clear(con)  # unexplored areas start black

    # create the FOV map according to the generated map
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)


def play_game():
    player_action = None

    mouse = libtcod.Mouse()
    key = libtcod.Key()
    while not libtcod.console_is_window_closed():
        # render the screen
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
        render_all()

        libtcod.console_flush()
        check_level_up()

        # erase all objects at old locations before they move
        for object in objects:
            object.clear()

        # handle keys and exit game if needed
        player_action = handle_keys(key, mouse)
        if player_action == 'exit' and game_state == 'dead':
            try:
                os.remove('savegame')
            except:
                break
        elif player_action == 'exit':
            save_game()
            break

        # let monsters take their turn
        if game_state == 'playing' and player_action != 'didnt-take-turn':
            for object in objects:
                if object.ai:
                    object.ai.take_turn()


def save_game():
    # open a new empty shelve (possibly rewriting old one) to write the game data
    file = shelve.open('savegame', 'n')
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player)
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['stairs_index'] = objects.index(stairs)
    file['dungeon_level'] = dungeon_level
    file.close()


def load_game():
    # open the previous saved shelve and load the game data
    global map, objects, player, inventory, game_msgs, game_state, stairs, dungeon_level

    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']]  # get index of player in objects list and access it
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    stairs = objects[file['stairs_index']]
    dungeon_level = file['dungeon_level']
    file.close()

    initialize_fov()


def end_game():
    ending = [
        '*INITIATE COMM SEQUENCE EMERGENCY ALPHA-0x1*',
        'Calling Guild Post Alpha Ceti.',
        'Come in Guild Post Alpha Ceti.',
        'This is the last survivor of the Ark-1.',
        'Requesting immediate evacuation.',
        'Please respond.',
        'Can anyone hear me?',
        '... Is there anybody out there?',
        '...',
        '*silence*'
    ]

    show_text_log(ending, generate_starpic())
    os.remove('savegame')
    main_menu()


def handle_keys(key, mouse):
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        # Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit'  # exit game

        # movement keys
    if game_state == 'playing':
        if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
            player_move_or_attack(0, -1)
        elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
            player_move_or_attack(0, 1)
        elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
            player_move_or_attack(-1, 0)
        elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
            player_move_or_attack(1, 0)
        elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
            player_move_or_attack(-1, -1)
        elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
            player_move_or_attack(1, -1)
        elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
            player_move_or_attack(-1, 1)
        elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
            player_move_or_attack(1, 1)
        elif key.vk == libtcod.KEY_KP5:
            pass  # do nothing ie wait for the monster to come to you
        else:
            # test for other keys
            key_char = chr(key.c)

            if key_char == 'g':
                # pick up an item
                for object in objects:
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        break
            if key_char == 'i':
                # show the inventory
                chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.use()
            if key_char == 'd':
                # show inventory, if an item is selected, drop it
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()
            if key_char == '<':
                # go down stairs, if the player is on them
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()
            if key_char == 'c':
                # show character information
                level_up_xp = LEVEL_UP_BASE + (player.level * LEVEL_UP_FACTOR)
                if player.fighter.damage_roll[2]:
                    highest = 'H' + str(player.fighter.damage_roll[2])
                show_text_log([
                    'Character Information',
                    'Level: ' + str(player.level),
                    'Experience: ' + str(player.fighter.xp),
                    'Experience to level up: ' + str(level_up_xp),
                    'Maximum HP: ' + str(player.fighter.max_hp),
                    'To-hit: +' + str(player.fighter.to_hit),
                    'Damage: ' + str(player.fighter.damage_roll[0]) + 'd' + str(player.fighter.damage_roll[1]) + highest,
                    'Damage Bonus: +' + str(player.fighter.damage),
                    'AC: ' + str(player.fighter.armor_class),
                    ], generate_screen(), delay=False)
            return 'didnt-take-turn'


def target_tile(max_range=None):
    # return the position of a tile left-clicked in player FOV (optionally in a range)
    # or return (None,None) if right clicked
    key = libtcod.Key()
    mouse = libtcod.Mouse()
    while True:
        # render the screen. this reases the inventory and shows the names of objects under the mouse
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
        render_all()

        (x, y) = (mouse.cx, mouse.cy)

        if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and (
                        max_range is None or player.distance(x, y) <= max_range)):
            return x, y
        if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
            return None, None  # cancel on ESC or right clicked


def target_monster(max_range=None):
    # returns a clicked monster inside FOV up to a range, or None if right-clicked
    while True:
        (x, y) = target_tile(max_range)
        if x is None:  # player cancelled
            return None

        # return first clicked monster, otherwise keep looping
        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj


def get_names_under_mouse():
    key = libtcod.Key()
    mouse = libtcod.Mouse()
    libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
    # return a string with the names of all objects under the mouse
    (x, y) = (mouse.cx, mouse.cy)

    # create a list with the names of all objects at the mouse's coordinates within FOV
    names = [obj.name for obj in objects
             if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
    names = ', '.join(names)  # join the names, seperated by commas
    return names.capitalize()


def player_move_or_attack(dx, dy):
    global fov_recompute
    global objects

    # the coordinates the player is moving to/attacking
    x = player.x + dx
    y = player.y + dy

    # try to find an attackable object there
    target = None
    for object in objects:
        if object.fighter and object.x == x and object.y == y:
            target = object
            break

    # attack if target found, move otherwise
    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True


def create_room(room):
    global map
    # go through the tiles in the rectangle and make them passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False


def random_choice(chances_dict):
    # choose one option from dictionary of chances, returning its key
    chances = chances_dict.values()
    strings = chances_dict.keys()

    return strings[random_choice_index(chances)]


def random_choice_index(chances):  # choose one option from a list of chances and return its index
    dice = libtcod.random_get_int(0, 1, sum(chances))
    # go through all chances, keep sum so far
    running_sum = 0
    choice = 0
    for w in chances:
        running_sum += w

        # see if the dice landed in the part that corresponds to this choice
        if dice <= running_sum:
            return choice
        choice += 1


def rolldice(num, sides, highest=0):
    # rolls a given number of dice and returns their total
    # args: num = number of dice, sides = number of sides on each die,
    # highest (optional) = if != 0, returns only the sum of the highest number of dice given
    # Ex. (using H&H notation): 4d6 = rolldice(4,6); 3d6H2 = rolldice(3,6,highest=2)

    roll = []
    total = 0
    if highest != 0:
        for x in range(num):
            roll.append(libtcod.random_get_int(0, 1, sides))
        roll.sort(reverse=True)
        for x in range(highest):
            total += roll[x]
        return total
    else:
        for x in range(num):
            roll.append(libtcod.random_get_int(0, 1, sides))
        total = sum(roll)
        return total


def from_dungeon_level(table):
    # returns a value that depends on level. the table specifies what value occurs after each level, default is 0
    for (value, level) in reversed(table):
        if dungeon_level >= level:
            return value
    return 0


def from_player_level(table):
    # returns a value dependent on level. Table specifies what value occurs after each level, default is 0
    for (value, level) in reversed(table):
        if player.level >= level:
            return value
    return 0


def place_objects(room):
    # maximum number of monsters per room
    max_monsters = from_dungeon_level([[2, 1], [3, 4], [4, 6], [5, 8]])

    # chances of each monster
    # First value in each tuple is weighted value relative to all other items available at that level
    # Second value is the dungeon_level at which they become available
    # As H&H monster tables are flat, we simply use 1 here
    monster_chances = {'felix': 1,
                       'lobsterman': 1,
                       'nagahide': from_dungeon_level([[1, 3]]),
                       'hiverbug': from_dungeon_level([[1, 5]]),
                       'paleworm': from_dungeon_level([[1, 7]]),
                       'centipod': from_dungeon_level([[1, 9]]),
                       'living_weapon': from_dungeon_level([[1, 11]]),
                       'megaworm': from_dungeon_level([[1, 13]])}

    # max number of items per room
    max_items = from_dungeon_level([[1, 1], [2, 4]])

    # chance of each item
    # functions the same as the monster chances (weighted values, availability by level)
    # future revisions should break this down by type instead of individual item, resolving specific items in the
    # sub entries below.
    item_chances = {'opacaine': 1,
                    'vacc_suit': 1,
                    'tesla': 1,
                    'grenade': 1,
                    'confuse': 1,
                    'laser_sword': 1,
                    'plexsteel_shield': 1}

    # choose random number of monsters
    num_monsters = libtcod.random_get_int(0, 0, max_monsters)

    for i in range(num_monsters):
        # choose random spot for this monster
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        # only place it if the tile is not blocked

        if not is_blocked(x, y):
            choice = random_choice(monster_chances)
            if choice == 'felix':
                # create a felix
                fighter_component = Fighter(hp=rolldice(1, 4), armor_class=8, to_hit=0, damage=0, damage_roll=[1, 4],
                                            xp=35, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'f', 'felix', libtcod.light_azure, blocks=True, fighter=fighter_component,
                                 ai=ai_component)
            elif choice == 'lobsterman':
                fighter_component = Fighter(hp=rolldice(1, 6), armor_class=8, to_hit=0, damage=0, damage_roll=[1, 6],
                                            xp=50, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'l', 'lobsterman', libtcod.red, blocks=True, fighter=fighter_component,
                                 ai=ai_component)
            elif choice == 'nagahide':
                # create a nagahide
                fighter_component = Fighter(hp=rolldice(2, 12), armor_class=7, to_hit=2, damage=0, damage_roll=[1, 12],
                                            xp=100, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'N', 'nagahide', libtcod.dark_green, blocks=True, fighter=fighter_component,
                                 ai=ai_component)
            elif choice == 'hiverbug':
                fighter_component = Fighter(hp=rolldice(3, 8), armor_class=7, to_hit=1, damage=0, damage_roll=[1, 8],
                                            xp=100, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'h', 'hiverbug', libtcod.yellow, blocks=True, fighter=fighter_component,
                                 ai=ai_component)
            elif choice == 'paleworm':
                fighter_component = Fighter(hp=rolldice(5, 6), armor_class=6, to_hit=2, damage=0, damage_roll=[2, 6],
                                            xp=150, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'P', 'paleworm', libtcod.pink, blocks=True, fighter=fighter_component,
                                 ai=ai_component)
            elif choice == 'centipod':
                fighter_component = Fighter(hp=rolldice(5, 6), armor_class=4, to_hit=1, damage=0, damage_roll=[2, 6],
                                            xp=200, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'c', 'centipod', libtcod.black, blocks=True, fighter=fighter_component,
                                 ai=ai_component)
            elif choice == 'living_weapon':
                fighter_component = Fighter(hp=rolldice(6, 12), armor_class=2, to_hit=6, damage=0, damage_roll=[3, 12],
                                            xp=300, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'L', 'living weapon', libtcod.dark_gray, blocks=True, fighter=fighter_component,
                                 ai=ai_component)
            elif choice == 'megaworm':
                fighter_component = Fighter(hp=rolldice(8, 10), armor_class=2, to_hit=4, damage=0, damage_roll=[4, 10],
                                            xp=500, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'M', 'megaworm', libtcod.silver, blocks=True, fighter=fighter_component,
                                 ai=ai_component)
            objects.append(monster)

    # choose a random number of items
    num_items = libtcod.random_get_int(0, 0, max_items)

    for i in range(num_items):
        # choose a random spot for the item
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        # only place it if the tile is not blocked
        if not is_blocked(x, y):
            choice = random_choice(item_chances)
            if choice == 'opacaine':
                # create a healing item
                item_component = Item(use_function=cast_heal)
                item = Object(x, y, '!', 'dose of Opacaine', libtcod.violet, item=item_component)
            elif choice == 'tesla':
                # create an arc lightning device
                item_component = Item(use_function=cast_lightning)
                item = Object(x, y, '#', 'Tesla arc device', libtcod.light_yellow, item=item_component)
            elif choice == 'grenade':
                # create a grenade
                item_component = Item(use_function=cast_fireball)
                item = Object(x, y, '#', 'inciendiary grenade', libtcod.light_yellow, item=item_component)
            elif choice == 'confuse':
                # create a confuse item
                item_component = Item(use_function=cast_confuse)
                item = Object(x, y, '#', 'neural scrambler', libtcod.light_yellow, item=item_component)
            elif choice == 'laser_sword':
                # create a sword
                equipment_component = Equipment(slot='right hand', damage_roll=[2, 10, 1])
                item = Object(x, y, '/', 'laser sword', libtcod.sky, equipment=equipment_component)
            elif choice == 'plexsteel_shield':
                # create a shield
                equipment_component = Equipment(slot='left hand', armor_bonus=-1)
                item = Object(x, y, '[', 'plexsteel shield', libtcod.darker_orange, equipment=equipment_component)
            elif choice == 'vacc_suit':
                # create vacc suit armor
                equipment_component = Equipment(slot='armor', armor_bonus=-2)
                item = Object(x, y, ']', 'vacc suit', libtcod.silver, equipment=equipment_component)
            objects.append(item)
            item.send_to_back()  # items appear below other objects


def make_map():
    global map, objects, stairs

    # the list of objects with just the player
    objects = [player]

    # fill map with "unblocked" tiles
    map = [[Tile(True)
            for y in range(MAP_HEIGHT)]
           for x in range(MAP_WIDTH)]

    # create two rooms
    rooms = []
    num_rooms = 0

    for r in range(MAX_ROOMS):
        # random width and height
        w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        # random position without leaving map
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)

        # "Rect" class makes rectangles easier to work with
        new_room = Rect(x, y, w, h)

        # run through the other rooms and see if they intersect with this one
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break

        if not failed:
            # this means there are no intersections so the room is valid

            # "paint" it to the map's tiles'
            create_room(new_room)
            place_objects(new_room)

            # center coordinates of new_room, will be useful later
            (new_x, new_y) = new_room.center()

            # print "room number" onto room (optional, not included in sample code)
            # remove later if issues arise, but I think it looks cool and H&H-y
            # room_no = Object(new_x,new_y,chr(65+num_rooms), 'room number', libtcod.white, blocks=False)
            # objects.insert(0,room_no)

            if num_rooms == 0:
                # this is the first room, where the player starts at
                player.x = new_x
                player.y = new_y
            else:
                # all rooms after the first:
                # connect it to the previous room with a tunnel

                # center coordinates of previous room
                (prev_x, prev_y) = rooms[num_rooms - 1].center()

                if libtcod.random_get_int(0, 0, 1) == 1:
                    # first move horizontally then vertically
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    # first move vertically then horizontally
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)

            # finally, append the new room to the list
            rooms.append(new_room)
            num_rooms += 1

            # create stairs at the center of the last room
    stairs = Object(new_x, new_y, '<', 'stairs', libtcod.white, always_visible=True)
    objects.append(stairs)
    stairs.send_to_back()  # so it draws below monsters


def next_level():
    global dungeon_level

    if dungeon_level >= 13:
        message('At last, you find an escape to the surface. You crawl up the narrow passage in search of rescue.',
                libtcod.yellow)
        end_game()

    # advance to the next level
    message('You take a moment to rest, and recover your strength.', libtcod.yellow)
    player.fighter.heal(player.fighter.max_hp / 2)  # heal player by 50%

    message('After a rare moment of peace, you descend further into the cave.', libtcod.red)
    dungeon_level += 1

    make_map()
    initialize_fov()


def menu(header, options, width):
    if len(options) > 26:
        raise ValueError('Cannot have a menu with more than 26 options.')

    # calculate total height for the header (after auto wrap) and one line per option
    header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    if header == '':
        header_height = 0
    height = len(options) + header_height

    # create an off-screen console that represents the menu's window
    window = libtcod.console_new(width, height)

    # print the header with auto-wrap
    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)

    # print all the options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ')' + option_text
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        y += 1
        letter_index += 1

    # blit the contents of window to root console
    x = SCREEN_WIDTH / 2 - width / 2
    y = SCREEN_HEIGHT / 2 - height / 2
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

    # present the root console to the player and wait for keypress
    libtcod.console_flush()
    key = libtcod.console_wait_for_keypress(True)

    if key.vk == libtcod.KEY_ENTER and key.lalt:  # special case, have to check for alt+enter for fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

    # convert the ASCII code to an index; if it corresponds to an option, return it
    index = key.c - ord('a')
    if 0 <= index < len(options):
        return index
    return None


def msgbox(text, width=50):
    menu(text, [], width)  # use menu() as a sort of 'message box'


def inventory_menu(header):
    # show a menu of each item in the inventory as an option
    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = []
        for item in inventory:
            text = item.name
            # show additional information if equipped
            if item.equipment and item.equipment.is_equipped:
                text = text + ' (on ' + item.equipment.slot + ')'
            options.append(text)

    index = menu(header, options, INVENTORY_WIDTH)

    # if an item was chosen, return it
    if index is None or len(inventory) == 0:
        return None
    return inventory[index].item


def render_all():
    global color_light_wall
    global color_light_ground
    global fov_recompute

    if fov_recompute:
        # recompute FOV if needed
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

        # go through all tiles, and set their background color
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = libtcod.map_is_in_fov(fov_map, x, y)
                wall = map[x][y].block_sight
                if not visible:
                    # if it's not visible right now, the player can only see it if it's explored
                    if map[x][y].explored:
                        # it's out of the player FOV
                        if wall:
                            libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
                        else:
                            libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)

                else:
                    # it's visible
                    if wall:
                        libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET)
                    else:
                        libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET)
                    map[x][y].explored = True

                    # draw all objects in the list
    for object in objects:
        if object != player:
            object.draw()
    player.draw()

    # blit con to root console
    libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)

    # prepare to render the GUI panel
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_clear(panel)

    # print the game messages, one line at a time
    y = 1
    for (line, color) in game_msgs:
        libtcod.console_set_default_foreground(panel, color)
        libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
        y += 1

    # show the player's stats
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, libtcod.light_red, libtcod.darker_red)
    libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, 'Cave level ' + str(dungeon_level))

    # display names of objects under mouse
    libtcod.console_set_default_foreground(panel, libtcod.light_gray)
    libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())

    # blit the contents of "panel" to root console
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)


def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    # render a bar (HP, XP, etc). first calculate width of bar
    bar_width = int(float(value) / maximum * total_width)

    # render background first
    libtcod.console_set_default_background(panel, back_color)
    libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)

    # now render the bar on top
    libtcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)

    # finally, some centered text with the values
    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER,
                             name + ': ' + str(value) + '/' + str(maximum))


def message(new_msg, color=libtcod.white):
    # split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

    for line in new_msg_lines:
        # if the bugger is full, remove the first line to make room for the new one.
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]

        # add the new line as a tuple, with the text and color
        game_msgs.append((line, color))


def create_h_tunnel(x1, x2, y):
    global map
    for x in range(min(x1, x2), max(x1, x2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False


def create_v_tunnel(y1, y2, x):
    global map
    # vertical tunnel
    for y in range(min(y1, y2), max(y1, y2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False


def is_blocked(x, y):
    global map
    global objects

    # first test the map tile
    if map[x][y].blocked:
        return True

    # now check for blocking objects
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True

    return False


def closest_monster(max_range):
    # find closest enemy, up to a max range and in player FOV
    closest_enemy = None
    closest_dist = max_range + 1  # start with slightly more than max range

    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            # calculate distance between this object and the player
            dist = player.distance_to(object)
            if dist < closest_dist:  # it's closer so remember it
                closest_enemy = object
                closest_dist = dist
    return closest_enemy


def player_death(player):
    # the game ended!
    global game_state
    message('You died! Press Esc to return to the main menu.', libtcod.red)
    game_state = 'dead'

    # for added effect, transform player into a corpse!
    player.char = '%'
    player.color = libtcod.white


def monster_death(monster):
    # transform it into a nasty corpse! it doesn't block, can't be
    # attacked, and doesn't move
    message(monster.name.capitalize() + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points.',
            libtcod.orange)
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()


def get_equipped_in_slot(slot):
    for obj in inventory:
        if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
            return obj.equipment
    return None


def get_all_equipped(obj):
    if obj == player:
        equipped_list = []
        for item in inventory:
            if item.equipment and item.equipment.is_equipped:
                equipped_list.append(item.equipment)
        return equipped_list
    else:
        return []  # other objects have no equipment


def check_level_up():
    # see if the player's experience is enough to level-up
    level_up_xp = LEVEL_UP_BASE + (player.level * LEVEL_UP_FACTOR)
    if player.fighter.xp >= level_up_xp:
        # it is! *ding* level up
        player.level += 1
        player.fighter.xp -= level_up_xp
        message('Your battle experience has hardened you further. You reached level ' + str(player.level) + '!',
                libtcod.yellow)
        render_all()  # re-render console so that message plays before menu

        hit_die = rolldice(1, 10)
        player.fighter.max_hp += hit_die
        player.fighter.hp += hit_die

        player.fighter.base_to_hit += 1

        player.fighter.base_damage += 1


def cast_heal():
    # heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', libtcod.red)
        return 'cancelled'

    heal_roll = rolldice(*HEAL_AMOUNT)
    message('Your pain subsides, for now. You restore ' + str(heal_roll) + ' hit points.', libtcod.light_violet)
    player.fighter.heal(heal_roll)


def cast_lightning():
    # find closest enemy inside max range and damage it
    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None:  # no enemy found within range
        message('No enemy is within arc range.')
        return 'cancelled'

    # zap it!
    message('A bolt of electricity arcs into the ' + monster.name + ' with a loud ZZZAP! The damage is ' + str(
        LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
    monster.fighter.take_damage(rolldice(*LIGHTNING_DAMAGE))


def cast_confuse():
    # ask for target and confuse it
    message('Left-click an enemy to confuse it, or right-click to cancel.', libtcod.light_cyan)
    monster = target_monster(CONFUSE_RANGE)
    if monster is None:
        return 'cancelled'
    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster  # tell the new component who owns it
    message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around!', libtcod.light_green)


def cast_fireball():
    # ask the player for a target tile to throw a 'fireball' at (ie. grenade, AOE, etc)
    message('Left-click a target tile, or right-click to cancel.', libtcod.light_cyan)
    (x, y) = target_tile()
    if x is None:
        return 'cancelled'
    message('The device explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)

    for obj in objects:  # damage every fighter in range, including the player
        if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
            damage_rolled = rolldice(*FIREBALL_DAMAGE)
            message('The ' + obj.name + ' gets burned for ' + str(damage_rolled) + ' hit points.', libtcod.orange)
            obj.fighter.take_damage(damage_rolled)

# ############################################
# Initialization & Main Loop
# ############################################
libtcod.console_set_custom_font('terminal8x8_gs_ro.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_ASCII_INROW)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Hulks and Horrors', False)
libtcod.sys_set_fps(LIMIT_FPS)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)

firstrun = True

main_menu()