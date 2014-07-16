"""
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
"""
import math
import textwrap
import shelve
import os
import operator
import random

import hhmessage
import libtcodpy as libtcod
import hhtable


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
LEVEL_UP_BASE = 300
LEVEL_UP_FACTOR = 200

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
                 equipment=None, placeable=None, seen_player=False, killed_by=None):
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

        self.placeable = placeable
        if self.placeable:
            self.placeable.owner = self

        self.seen_player = seen_player
        self.killed_by = killed_by


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
        # create and compute a path for the object to the target
        path = libtcod.path_new_using_map(fov_map)
        libtcod.path_compute(path, self.x, self.y, target_x, target_y)

        # get the target coords of the next spot on the path
        mx, my, = libtcod.path_walk(path, True)
        if mx is not None:
            dx = mx - self.x
            dy = my - self.y
            self.move(dx, dy)
            libtcod.path_delete(path)
        else:
            libtcod.path_delete(path)
            return

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
    def __init__(self, reusable=False, uses=1, use_function=None):
        self.use_function = use_function
        self.reusable = reusable
        self.uses = uses
        if self.use_function:
            self.use_function.owner = self

    def use(self, *args):
        # just call the use_function if it is defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        elif not self.reusable:
            if self.use_function.use(*args) != 'cancelled':
                inventory.remove(self.owner)  # destroy after use unless cancelled
        else:
            if self.use_function.use(*args) != 'cancelled':
                self.uses -= 1
                if self.uses < 1:
                    inventory.remove(self.owner)

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
    def __init__(self, slot, to_hit_bonus=0, damage_bonus=0, damage_roll=None, armor_bonus=0, max_hp_bonus=0,
                 ranged=False, ammo=None):
        self.to_hit_bonus = to_hit_bonus
        self.damage_bonus = damage_bonus
        self.damage_roll = damage_roll
        self.armor_bonus = armor_bonus
        self.max_hp_bonus = max_hp_bonus
        self.slot = slot
        self.is_equipped = False
        self.ranged = ranged
        self.ammo = ammo

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


class Placeable:
    # a class for 'placeables', interactive world objects that may be usable.
    def __init__(self, reusable=False, used=False, use_class=None):
        self.reusable = reusable
        self.used = used
        self.use_class = use_class
        if self.use_class:
            self.use_class.owner = self

    def use(self, *args):
        # interact with the object
        # just call the use_function if it is defined
        if self.use_class is None:
            message('The ' + self.owner.name + ' cannot be used.')
        if self.used and not self.reusable:
            message('You have already used that object!')
        else:
            if self.use_class.use(*args) != 'cancelled':
                self.used = True  # disable after use unless cancelled


class Fighter:
    # combat-related properties and methods (monster, player, npc)
    def __init__(self, hp, armor_class, to_hit, damage, damage_roll, xp, damage_resistance=0,
                 kills=0, death_function=None):
        self.base_max_hp = hp
        self.hp = hp
        self.base_armor_class = armor_class
        self.base_to_hit = to_hit
        self.base_damage = damage
        self.base_roll = damage_roll
        self.xp = xp
        self.damage_resistance = damage_resistance
        self.kills = kills
        self.death_function = death_function

    @property
    def to_hit(self):
        bonus = sum(equipment.to_hit_bonus for equipment in get_all_equipped(self.owner))
        return self.base_to_hit + bonus

    @property
    def armor_class(self):  # return actual defense, by summing up the bonuses from all equipped items
        bonus = sum(equipment.armor_bonus for equipment in get_all_equipped(self.owner))
        if bonus < -12:
            bonus = -12
        return self.base_armor_class + bonus

    @property
    def damage(self):  # return actual damage bonus, plus any special bonuses
        bonus = sum(equipment.damage_bonus for equipment in get_all_equipped(self.owner))
        return self.base_damage + bonus

    @property
    def damage_roll(self):  # return current damage roll or roll from equipment
        for equipment in get_all_equipped(self.owner):
            if equipment.damage_roll:
                return equipment.damage_roll
        return self.base_roll

    @property
    def max_hp(self):  # return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
        return self.base_max_hp + bonus

    def take_damage(self, damage, killed_by):
        # apply damage if possible
        if damage > 0:
            self.hp -= damage

        # check for death. if there's a death function, call it, and update 'killed_by' to name of attacker
        if self.hp <= 0:
            function = self.death_function
            if function is not None:
                self.owner.killed_by = killed_by
                function(self.owner)

            if self.owner != player:  # yield xp to player
                player.fighter.xp += self.xp
                player.fighter.kills += 1

    def heal(self, amount):
        # heal by the given amount, without going over max_hp
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

    def attack(self, target):
        # first check for to hit target, capped at 2 to 20
        to_hit_target = self.to_hit + target.fighter.armor_class + 5
        if to_hit_target > 20:
            to_hit_target = 20
        elif to_hit_target == 1:
            to_hit_target = 2

        # check of the target is attacking with a gun
        has_gun = False
        for i in get_all_equipped(self.owner):
            if i.is_equipped and i.ranged:
                has_gun = True
                gun = i

        # check if gun has ammo
        if has_gun:
            if gun.ammo > 0:
                gun.ammo -= 1
            else:
                message("You don't have any ammo!")
                return

        # use the right pronoun
        if target.ai is not None:
            pronoun = 'the '
        else:
            pronoun = ''

        # roll to hit
        if hhtable.rolldice(1, 20) >= to_hit_target:
            message(self.owner.name.title() + ' misses ' + pronoun + target.name + '.')
            return

        # now roll for damage (curr. using OD&D style)
        damage = (hhtable.rolldice(*self.damage_roll) + self.damage) - target.fighter.damage_resistance

        if damage > 0:
            # make the target take some damage
            message(self.owner.name.title() + ' hits ' + pronoun + target.name + ' for ' + str(damage) + ' hit points.',
                    libtcod.yellow)
            target.fighter.take_damage(damage, self.owner.name)
        else:
            message(self.owner.name.title() + ' hits ' + pronoun + target.name + ' but it has no effect!',
                    libtcod.grey)

    def shoot(self):
        # first check if the character is equipped with a ranged weapon
        has_gun = False
        for i in get_all_equipped(self.owner):
            if i.is_equipped and i.ranged:
                has_gun = True
                gun = i

        if not has_gun:
            message("You're not carrying a gun!", libtcod.red)
            return

        # check if the gun has ammo
        if gun.ammo is None or gun.ammo < 1:
            message("You're out of ammo in that gun!", libtcod.red)
            return

        # target a monster
        message('Left-click on a target monster, or right-click to cancel.')
        target = target_monster()
        if not target:
            return

        # calculate to-hit
        to_hit_target = self.to_hit + target.fighter.armor_class + 5
        if to_hit_target > 20:
            to_hit_target = 20
        elif to_hit_target == 1:
            to_hit_target = 2

        # deduct ammo
        gun.ammo -= 1

        # roll to hit
        if hhtable.rolldice(1, 20) >= to_hit_target:
            message(self.owner.name.title() + ' misses the ' + target.name + '.')
            return

        # now roll for damage (curr. using OD&D style)
        damage = (hhtable.rolldice(*self.damage_roll) + gun.damage_bonus) - target.fighter.damage_resistance

        if damage > 0:
            # make the target take some damage
            message(self.owner.name.title() + ' hits the ' + target.name + ' for ' + str(damage) + ' hit points.',
                    libtcod.yellow)
            target.fighter.take_damage(damage, self.owner.name)
        else:
            message(self.owner.name.title() + ' hits the ' + target.name + ' but it has no effect!',
                    libtcod.grey)


class BasicMonster:
    # AI for a basic monster
    def __init__(self):
        pass

    def take_turn(self):
        # a basic monster takes its turn. If you can see it, it can see you
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
            monster.seen_player = True

        if monster.seen_player:
            # move towards the player if far away
            if 2 <= monster.distance_to(player) <= 10:
                monster.move_towards(player.x, player.y)

            # close enough, attack!
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)


class FriendlyMonster:
    def __init__(self, max_range=10):
        self.max_range = max_range
        self.target = None

    def take_turn(self):
        # a monster that protects the player and attacks other monsters
        monster = self.owner
        if self.target is None:
            self.target = closest_monster(self.max_range)
        enemy = self.target
        if 2 <= monster.distance_to(enemy) <= self.max_range:
            monster.move_towards(enemy.x, enemy.y)

        elif enemy.fighter.hp > 0:
            monster.fighter.attack(enemy)

        if enemy.fighter.hp < 1:
            self.target = None


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

class Heal:
    # generic process for healing items
    def __init__(self, dice=HEAL_AMOUNT, max_boost=False, heal_all=False):
        self.dice = dice
        self.max_boost = max_boost
        self.heal_all = heal_all

    def use(self):
        # heal the player
        if player.fighter.hp == player.fighter.max_hp:
            message('You are already at full health.', libtcod.red)
            return 'cancelled'

        if self.heal_all:
            heal_roll = player.fighter.max_hp
        else:
            heal_roll = hhtable.rolldice(*self.dice)
        message('Your pain subsides, for now. You restore ' + str(heal_roll) + ' hit points.', libtcod.light_violet)
        player.fighter.heal(heal_roll)


class Buff:
    # generic process for items which permanently improve stats
    def __init__(self, max_hp=0, to_hit=0, damage=0, ac=0, xp=0, dr=0, desc=None):
        self.max_hp = max_hp
        self.to_hit = to_hit
        self.damage = damage
        self.ac = ac
        self.xp = xp
        self.dr = dr
        self.desc = desc

    def use(self):
        # apply all bonuses from the item
        player.fighter.max_hp += self.max_hp
        player.fighter.to_hit += self.to_hit
        player.fighter.damage += self.damage
        player.fighter.armor_class += self.ac
        player.fighter.xp += self.xp
        player.fighter.damage_resistance += self.dr
        if self.desc is None:
            message('A rush flows through you, and you feel improved!')
        else:
            message(self.desc)


class RandomDamage:
    # generic process for items that damage a random target
    def __init__(self, damage=LIGHTNING_DAMAGE, attackrange=LIGHTNING_RANGE):
        self.damage = damage
        self.attackrange = attackrange

    def use(self):
        # find closest enemy inside max range and damage it
        monster = closest_monster(self.attackrange)
        if monster is None:  # no enemy found within range
            message('No enemy is within arc range.')
            return 'cancelled'

        # zap it!
        damage = hhtable.rolldice(*self.damage)
        message('A bolt of electricity arcs into the ' + monster.name + ' with a loud ZZZAP! The damage is ' + str(
            damage) + ' hit points.', libtcod.light_blue)
        monster.fighter.take_damage(damage, 'electrical discharge')


class Grenade:
    # generic grenade throw function
    def __init__(self, damage=FIREBALL_DAMAGE, radius=FIREBALL_RADIUS, radius_damage=FIREBALL_DAMAGE, kills=False,
                 kills_radius=False):
        self.damage = damage
        self.radius = radius
        self.radius_damage = radius_damage
        self.kills = kills
        self.kills_radius = kills_radius

    def use(self):
        # ask the player for a target tile to throw a 'fireball' at (ie. grenade, AOE, etc)
        message('Left-click a target tile, or right-click to cancel.', libtcod.light_cyan)
        (x, y) = target_tile()
        if x is None:
            return 'cancelled'
        message('The device explodes, striking everything within ' + str(self.radius) + ' tiles!', libtcod.orange)

        for obj in objects:  # damage every fighter in range, including the player
            if obj.distance(x, y) == 0:
                if not self.kills:
                    damage_rolled = hhtable.rolldice(*self.damage)
                else:
                    damage_rolled = obj.fighter.hp
                message('The ' + obj.name + ' is at ground zero! Takes ' + str(damage_rolled) + ' hit points.',
                        libtcod.orange)
                obj.fighter.take_damage(damage_rolled, 'own grenade')
            elif obj.distance(x, y) <= self.radius and obj.fighter:
                if not self.kills_radius:
                    damage_rolled = hhtable.rolldice(*self.radius_damage)
                else:
                    damage_rolled = obj.fighter.hp
                message('The ' + obj.name + ' takes blast damage for ' + str(damage_rolled) + ' hit points.',
                        libtcod.orange)
                obj.fighter.take_damage(damage_rolled, 'own grenade')


class Confuse:
    # generic class for confusion items
    def __init__(self, duration=CONFUSE_NUM_TURNS, attackrange=CONFUSE_RANGE):
        self.duration = duration
        self.attackrange = attackrange

    def use(self):
        # ask for target and confuse it
        message('Left-click an enemy to confuse it, or right-click to cancel.', libtcod.light_cyan)
        monster = target_monster(self.attackrange)
        if monster is None:
            return 'cancelled'
        old_ai = monster.ai
        monster.ai = ConfusedMonster(old_ai, num_turns=self.duration)
        monster.ai.owner = monster  # tell the new component who owns it
        message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around!', libtcod.light_green)


class Detector:
    # generic class for a device that detects monster presences
    def __init__(self, detect_range=None):
        self.detect_range = detect_range

    def use(self):
        # flag all monsters within range as always_visible (or all monsters on map if detect_range=None)
        message('The machine goes "Ping!"')
        for obj in objects:
            if obj.fighter and self.detect_range is None:
                obj.always_visible = True
            elif obj.fighter and obj.distance(player.x, player.y) <= self.detect_range:
                obj.always_visible = True


class Summon:
    # summon a friendly monster
    def __init__(self, name, hitdice, color):
        self.name = name
        self.hitdice = hitdice
        self.color = color

    def use(self):
        x = player.x
        y = player.y
        summon = get_monster_from_hitdice(x, y, self.name, self.hitdice, self.color, friendly=True)
        objects.append(summon)


class Terminal:
    def __init__(self, type=None):
        self.type = type
        if self.type is None:
            self.type = random.choice(['log','hint'])

    def use(self):
        # get a random creepy message
        if self.type == 'log':
            hhmessage.creep_log()
        if self.type == 'hint':
            hhmessage.hint_message()


class RestPod:
    def __init__(self, heal_amount=(1, 6), heal_bonus=0):
        self.heal_bonus = heal_bonus
        self.heal_amount = heal_amount

    def use(self):
        # heal the player
        if player.fighter.hp == player.fighter.max_hp:
            message('You are already at full health.', libtcod.red)
            return 'cancelled'

        heal_roll = hhtable.rolldice(*self.heal_amount) + self.heal_bonus
        message('You relax inside the metal cocoon. You restore ' + str(heal_roll) + ' hit points.',
                libtcod.light_violet)
        player.fighter.heal(heal_roll)


class Teleporter:
    def __init__(self, new_level=None):
        self.new_level = new_level
        if self.new_level is None:
            self.new_level = libtcod.random_get_int(0, 1, 12)

    def use(self):
        global dungeon_level
        message('You feel a sudden jolt and find yourself staring at a completely different room.', libtcod.red)
        dungeon_level = self.new_level

        make_map()
        initialize_fov()


def main_menu(firstrun=False):
    # The main game menu.

    img = hhmessage.generate_starpic()

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
        choice = menu('', [newopt, 'Continue last save', 'Display high scores', 'Quit'], 26)

        if choice == 0:
            new_game(firstrun)
            firstrun = False
            play_game()

        if choice == 1:
            try:
                load_game()
            except:
                msgbox('\n No saved game to load.\n', 24)
                continue
            play_game()
        elif choice == 2:
            try:
                show_scores()
            except:
                msgbox('\n No high scores yet!\n', 24)
                continue
        elif choice == 3:
            break


def new_game(firstrun=False):
    global player, inventory, game_msgs, game_state, dungeon_level

    # play intro sequence if starting up
    if firstrun:
        hhmessage.intro_sequence()


    # create Player object
    # Assume Soldier class with 10 STR, 10 DEX, 10 CON
    fighter_component = Fighter(hp=hhtable.rolldice(3, 6) + hhtable.rolldice(1, 10),
                                armor_class=10, to_hit=1, damage=1,
                                damage_roll=[1, 3],
                                xp=0, death_function=player_death)
    player = Object(0, 0, chr(1), get_text_entry('What is your name, Ensign?', hhmessage.generate_screen()),
                    libtcod.white, blocks=True, fighter=fighter_component)
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
        if game_state == 'dead':
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


def new_score(player):
    # generate a new score from player and dungeon_level, save it to file, then ask to display it.
    score = player.fighter.kills * player.level * dungeon_level
    score_data = [score, player.name.title(), player.killed_by, str(dungeon_level)]

    scores = shelve.open('scorefile', 'c', writeback=True)
    if 'scores' in scores:
        list = scores['scores']
        list.append(score_data)
        scores['scores'] = list
    else:
        new_list = [score_data]
        scores['scores'] = new_list
    scores.close()

    choice = menu('Game Over\n', ['See your score', 'Return to main menu'], 22)
    if choice == 0:
        show_scores()


def show_scores():
    # load the score file, sort the list by score, then display
    score_file = shelve.open('scorefile', 'r')
    scores = score_file['scores']
    scores.sort(key=operator.itemgetter(0), reverse=True)
    score_list = ['High Scores']
    c = 0
    for i in scores:
        n_score = '{0: >3}'.format(str(c + 1)) + '. ' + '{0: >5}'.format(str(scores[c][0])) + '  ' + scores[c][1]
        n_score += ', killed by ' + scores[c][2] + ' on level ' + scores[c][3]
        score_list.append(n_score)
        c += 1
        if c > 10:
            break

    score_file.close()

    hhmessage.show_text_log(score_list, hhmessage.generate_starpic(), delay=False, center_first_line=True)


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

    hhmessage.show_text_log(ending, hhmessage.generate_starpic())
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
        elif key.vk == libtcod.KEY_KP5 or key.vk == libtcod.KEY_SPACE:
            pass  # do nothing ie wait for the monster to come to you
        else:
            # test for other keys
            key_char = chr(key.c)

            if key_char == 'a':
                has_gun = False
                for i in get_all_equipped(player):
                    if i.is_equipped and i.ranged:
                        has_gun = True
                        gun = i
                if has_gun:
                    message(gun.owner.name.capitalize() + ' has ' + str(gun.ammo) + ' shots remaining.')
            if key_char == 's':
                # shoot at someone
                player.fighter.shoot()
                # remove the target from the map until the next redraw
                for object in objects:
                    object.clear()
                return
            if key_char == 'g':
                # pick up an item
                for object in objects:
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        break
            if key_char == 'u':
                # use a placeable if present
                for object in objects:
                    if object.x == player.x and object.y == player.y and object.placeable:
                        object.placeable.use()
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
                try:
                    highest = 'H' + str(player.fighter.damage_roll[2])
                except:
                    highest = ''
                hhmessage.show_text_log([
                                  'Character Information',
                                  'Name: ' + player.name,
                                  'Level: ' + str(player.level),
                                  'Experience: ' + str(player.fighter.xp),
                                  'Experience to level up: ' + str(level_up_xp),
                                  'Maximum HP: ' + str(player.fighter.max_hp),
                                  'AC: ' + str(player.fighter.armor_class),
                                  'DR: ' + str(player.fighter.damage_resistance),
                                  'To-hit: +' + str(player.fighter.to_hit),
                                  'Damage Bonus: +' + str(player.fighter.damage),
                                  'Damage Roll: ' + str(player.fighter.damage_roll[0]) + 'd' + str(
                                      player.fighter.damage_roll[1]) + highest,
                              ], hhmessage.generate_screen(), delay=False)
            if key_char == 'h' or key_char == '?':
                hhmessage.help_screen()
            return 'didnt-take-turn'


def target_tile(max_range=None):
    # return the position of a tile left-clicked in player FOV (optionally in a range)
    # or return (None,None) if right clicked
    key = libtcod.Key()
    mouse = libtcod.Mouse()
    while True:
        # render the screen. this raises the inventory and shows the names of objects under the mouse
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
    if names:
        names = ', '.join(names)  # join the names, seperated by commas
        names = 'Under mouse: ' + names
    else:
        names = ''
    return names.title()


def get_names_under_player():
    names = [obj.name for obj in objects
             if obj.x == player.x and obj.y == player.y and obj.name != player.name]
    if names:
        names = ', '.join(names)  # join the names, seperated by commas
        names = 'Under player: ' + names
    else:
        names = ''
    return names.title()


def get_text_entry(header, img):
    timer = 0
    command = ""
    cursor = 0
    x = SCREEN_HEIGHT / 3
    y = (SCREEN_HEIGHT / 4) + 2

    libtcod.image_blit_2x(img, 0, 0, 0)
    libtcod.console_set_default_foreground(0, libtcod.green)

    libtcod.console_print_ex(0, SCREEN_WIDTH / 4, SCREEN_HEIGHT / 4, libtcod.BKGND_NONE, libtcod.LEFT, header)

    while not libtcod.console_is_window_closed():

        key = libtcod.console_check_for_keypress(libtcod.KEY_PRESSED)

        timer += 1
        if timer % (LIMIT_FPS // 4) == 0:
            if timer % (LIMIT_FPS // 2) == 0:
                timer = 0
                libtcod.console_set_char(0, cursor + x, y, "_")
                libtcod.console_set_char_foreground(0, cursor + x, y, libtcod.white)
            else:
                libtcod.console_set_char(0, cursor + x, y, " ")
                libtcod.console_set_char_foreground(0, cursor + x, y, libtcod.white)

        if key.vk == libtcod.KEY_BACKSPACE and cursor > 0:
            libtcod.console_set_char(0, cursor + x, y, " ")
            libtcod.console_set_char_foreground(0, cursor + x, y, libtcod.white)
            command = command[:-1]
            cursor -= 1
        elif key.vk == libtcod.KEY_ENTER:
            break
        elif key.vk == libtcod.KEY_ESCAPE:
            command = ""
            break
        elif key.c > 0:
            letter = chr(key.c)
            libtcod.console_set_char(0, cursor + x, y, letter)  # print new character at appropriate position on screen
            libtcod.console_set_char_foreground(0, cursor + x, y, libtcod.white)  # make it white or something
            command += letter  # add to the string
            cursor += 1

        libtcod.console_flush()

    return command


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


def get_monster_from_hitdice(x, y, name, hitdice, color, friendly=False):
    # generate monster object from number of hit dice
    # get tuple components
    num = hitdice[0]
    sides = hitdice[1]

    # determine to-hit from num and sides
    if sides == 12:
        to_hit = num
    elif 11 >= sides >= 8:
        to_hit = num / 2
    else:
        to_hit = num / 3

    # if sides >= 10, make letter a capital
    if sides >= 10:
        letter = name[0].capitalize()
    else:
        letter = name[0]

    # get number of damage dice from hitdice, making sure it's at least 1.
    if num / 2 < 1:
        roll = (1, sides)
    else:
        roll = (num / 2, sides)

    fighter_component = Fighter(hp=hhtable.rolldice(*hitdice), armor_class=10 - num, to_hit=to_hit,
                                damage=0, damage_roll=roll, xp=num * sides * 5, death_function=monster_death)
    if friendly:
        ai_component = FriendlyMonster()
    else:
        ai_component = BasicMonster()
    monster = Object(x, y, letter, name, color, blocks=True, fighter=fighter_component, ai=ai_component)

    return monster


def get_item(x, y):
    choice = random.choice(['heal', 'grenade', 'misc'])

    if choice == 'heal':
        # create a healing item
        heal_item = hhtable.make_heal_item()
        heal_component = Heal(dice=heal_item['roll'], heal_all=heal_item['heal_all'])
        item_component = Item(reusable=heal_item['reuse'], uses=heal_item['uses'], use_function=heal_component)
        item = Object(x, y, '!', heal_item['name'], libtcod.violet, item=item_component)
    elif choice == 'grenade':
        # create a grenade
        grenade = hhtable.make_grenade()
        grenade_component = Grenade(damage=grenade['damage'], radius=grenade['radius'],
                                    radius_damage=grenade['radius_damage'], kills=grenade['kills'],
                                    kills_radius=grenade['kills_radius'])
        item_component = Item(use_function=grenade_component)
        item = Object(x, y, '*', grenade['name'], libtcod.light_yellow, item=item_component)

    elif choice == 'misc':
        subchoice = random.choice(['confuse', 'buff', 'random_damage', 'detector', 'summon', 'vector'])

        if subchoice == 'random_damage':
            # create an arc lightning device
            random_damage_component = RandomDamage()
            item_component = Item(use_function=random_damage_component)
            item = Object(x, y, '#', 'Tesla arc device', libtcod.light_yellow, item=item_component)
        elif subchoice == 'confuse':
            # create a confuse item
            confuse_component = Confuse()
            item_component = Item(use_function=confuse_component)
            item = Object(x, y, '#', 'neural scrambler', libtcod.light_yellow, item=item_component)
        elif subchoice == 'buff':
            # create a buff item
            buff = hhtable.make_buff()
            buff_component = Buff(*buff['args'])
            item_component = Item(use_function=buff_component)
            item = Object(x, y, chr(167), buff['name'], libtcod.dark_magenta, item=item_component)
        elif subchoice == 'detector':
            # create a motion tracker
            detector_component = Detector(detect_range=10)
            item_component = Item(reusable=True, uses=hhtable.rolldice(1, 3), use_function=detector_component)
            item = Object(x, y, '#', 'motion tracker', libtcod.light_yellow, item=item_component)
        elif subchoice == 'summon':
            # create a friendly summonable monster
            summon_component = Summon(name='TED-3', hitdice=(4, 6), color=libtcod.sepia)
            item_component = Item(use_function=summon_component)
            item = Object(x, y, chr(12), 'TED-3', libtcod.sepia, item=item_component)
        elif subchoice == 'vector':
            # create the vector-jet harness
            harness = Equipment('back',armor_bonus=-1)
            item = Object(x, y, '%', 'vector-jet harness', libtcod.black, equipment=harness)

    return item


def get_weapon(x, y):
    weapon = hhtable.make_weapon()

    equipment_component = Equipment(slot='right hand', damage_roll=weapon['damage'], to_hit_bonus=weapon['bonus'],
                                    damage_bonus=weapon['bonus'], ranged=weapon['gun'], ammo=weapon['ammo'])
    item = Object(x, y, weapon['char'], weapon['name'], libtcod.brass, equipment=equipment_component)

    return item


def get_armor(x, y):
    armor = hhtable.make_armor()

    if armor['char'] == '[':
        armor_slot = 'shield'
    else:
        armor_slot = 'armor'

    equipment_component = Equipment(slot=armor_slot, armor_bonus=armor['ac'], damage_bonus=armor['str_bonus'],
                                    to_hit_bonus=armor['dex_bonus'])
    item = Object(x, y, armor['char'], armor['name'], libtcod.dark_gray, equipment=equipment_component)

    return item


def get_placeable(x, y):
    type = random.choice(['terminal', 'restpod', 'teleporter'])

    if type == 'terminal':
        terminal = Terminal()
        placeable = Placeable(use_class=terminal)
        obj = Object(x, y, chr(127), 'terminal', libtcod.silver, placeable=placeable)
    elif type == 'restpod':
        restpod = RestPod(heal_bonus=dungeon_level)
        placeable = Placeable(use_class=restpod)
        obj = Object(x, y, chr(239), 'rest pod', libtcod.purple, placeable=placeable)
    elif type == 'teleporter':
        teleport = Teleporter()
        placeable = Placeable(use_class=teleport)
        obj = Object(x, y, chr(23), 'teleporter', libtcod.dark_blue, placeable=placeable)

    return obj


def place_objects(room):
    # maximum number of monsters per room
    max_monsters = from_dungeon_level([[2, 1], [3, 4], [4, 6], [5, 8]])

    # monster table
    # key = name
    # dict entries:
    # key[0]: dungeon level appearing
    # key[1]: list[name, hitdice tuple, color]

    monster_table = hhtable.make_monster_table(dungeon_level)

    # max number of items per room
    max_items = from_dungeon_level([[1, 1], [2, 4]])

    # chance of each item
    # functions the same as the monster chances (weighted values, availability by level)
    # future revisions should break this down by type instead of individual item, resolving specific items in the
    # sub entries below.
    item_chances = ['item',
                    'armor',
                    'weapon',
                    'placeable']

    # choose random number of monsters
    num_monsters = libtcod.random_get_int(0, 0, max_monsters)

    for i in range(num_monsters):
        # choose random spot for this monster
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        # only place it if the tile is not blocked

        if not is_blocked(x, y):
            # pick a monster, then check if it's valid for this dungeon level
            choice = random.choice(monster_table.keys())
            monster = get_monster_from_hitdice(x, y, *monster_table[choice][1])
            objects.append(monster)

    # choose a random number of items
    num_items = libtcod.random_get_int(0, 0, max_items)

    for i in range(num_items):
        # choose a random spot for the item
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        # only place it if the tile is not blocked
        if not is_blocked(x, y):
            choice = random.choice(item_chances)
            if choice == 'item':
                item = get_item(x, y)
            elif choice == 'armor':
                item = get_armor(x, y)
            elif choice == 'weapon':
                item = get_weapon(x, y)
            elif choice == 'placeable':
                item = get_placeable(x, y)

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
    input_valid = False
    while not input_valid:
        key = libtcod.console_wait_for_keypress(True)
        if key.pressed:
            key = libtcod.console_wait_for_keypress(False)
            if not key.pressed:
                input_valid = True

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
    level_up_xp = LEVEL_UP_BASE + (player.level * LEVEL_UP_FACTOR)
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, libtcod.light_red, libtcod.darker_red)
    render_bar(1, 2, BAR_WIDTH, 'XP', player.fighter.xp, level_up_xp, libtcod.dark_green, libtcod.grey)
    libtcod.console_print_ex(panel, 1, 4, libtcod.BKGND_NONE, libtcod.LEFT, 'Exp. level ' + str(player.level))
    libtcod.console_print_ex(panel, 1, 5, libtcod.BKGND_NONE, libtcod.LEFT, 'Cave level ' + str(dungeon_level))
    libtcod.console_print_ex(panel, 1, 6, libtcod.BKGND_NONE, libtcod.LEFT, 'Kills: ' + str(player.fighter.kills))

    # display names of objects under mouse
    libtcod.console_set_default_foreground(panel, libtcod.light_gray)
    libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())

    # display names of objects under player on right side of panel
    libtcod.console_print_ex(panel, SCREEN_WIDTH - 2, 0, libtcod.BKGND_NONE, libtcod.RIGHT, get_names_under_player())

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
    message('You died!', libtcod.red)
    render_all()
    game_state = 'dead'

    # for added effect, transform player into a corpse!
    player.char = '%'
    player.color = libtcod.white
    new_score(player)


def monster_death(monster):
    # transform it into a nasty corpse! it doesn't block, can't be
    # attacked, and doesn't move
    message(monster.name.title() + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points.',
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

        # check player level, roll 1d10 for new HP if 6 or less, or just +3 (see H&H rulebook)
        if player.level <= 6:
            hit_die = hhtable.rolldice(1, 10)
        else:
            hit_die = 3
        player.fighter.max_hp += hit_die
        player.fighter.hp += hit_die

        # after level six, to_hit and damage only improve on even levels.
        if player.level <= 6 or player.level % 2 == 0:
            player.fighter.base_to_hit += 1
            player.fighter.base_damage += 1


# ############################################
# Initialization & Main Loop
# ############################################
libtcod.console_set_custom_font('terminal16x16_gs_ro.png',
                                libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_ASCII_INROW)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Hulks and Horrors', False)
libtcod.sys_set_fps(LIMIT_FPS)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)

main_menu(firstrun=True)