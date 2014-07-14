'''
handhRL - table functions

This file contains the table functions needed for main.

'''

import libtcodpy as libtcod
import random


def make_monster_table(dungeon_level):
    # generate the dict table for the monster generation

    # monster table
    # key = name
    # dict entries:
    # key[0]: dungeon level appearing
    # key[1]: list[name, hitdice tuple, color]

    monster_table = {'crewman': [1, ['deranged crewmember', (dungeon_level, 8), libtcod.light_red]],
                     'felix': [1, ['felix', (1, 4), libtcod.light_azure]],
                     'skinless': [1, ['skinless', (1, 6), libtcod.darker_pink]],
                     'skeletal': [1, ['skeletal', (1, 10), libtcod.lightest_sepia]],
                     'lobsterman': [1, ['lobsterman', (1, 6), libtcod.red]],
                     'cave_mushroom': [1, ['cave mushroom', (1, 6), libtcod.lightest_han]],
                     'anthropophagi': [1, ['anthropophagi', (1, 8), libtcod.peach]],
                     'capyfolk': [1, ['capyfolk', (1, 6), libtcod.light_sepia]],
                     'nagahide': [3, ['nagahide', (2, 12), libtcod.dark_green]],
                     'clawman': [3, ['clawman', (2, 12), libtcod.black]],
                     'hiverbug': [5, ['hiverbug', (3, 8), libtcod.yellow]],
                     'seeker_drone': [5, ['seeker drone', (3, 12), libtcod.silver]],
                     'neurovore': [7, ['neurovore', (1, 6), libtcod.Color(130, 110, 50)]],
                     'paleworm': [7, ['paleworm', (5, 6), libtcod.dark_pink]],
                     'gulper': [9, ['gulper', (5, 8), libtcod.lightest_grey]],
                     'centipod': [9, ['centipod', (5, 6), libtcod.darkest_red]],
                     'blind_troll': [9, ['blind_troll', (5, 10), libtcod.darkest_green]],
                     'scumsucker': [11, ['scumsucker', (6, 8), libtcod.peach]],
                     'living_weapon': [11, ['living weapon', (6, 12), libtcod.black]],
                     'megaworm': [13, ['megaworm', (8, 10), libtcod.silver]]}

    adjust_table = {k: v for k, v in monster_table.iteritems() if v[0] <= dungeon_level}

    return adjust_table


def make_weapon():
    # generate a weapon name and damage

    # table entries for modern are lists: character, name, rolldice tuple (or list if Highest X)

    modern_weapon = [['-', 'shiv', (1, 3)],
                     ['-', 'combat knife', (1, 4)],
                     ['-', 'vibro-blade', (1, 6)],
                     ['/', 'cutlass', (1, 8)],
                     ['/', 'vibro-sword', (1, 10)],
                     ['/', 'laser sword', [2, 10, 1]],
                     [')', 'laser pistol', [2, 6, 1]],
                     [')', 'slug pistol', (1, 8)],
                     [')', 'particle beamer', (1, 10)],
                     ['}', 'pulse rifle', [3, 6, 2]],
                     ['}', 'plasma rifle', (2, 6)],
                     ['}', 'bolt rifle', (2, 10)],
                     ['=', 'naval pumpgun', (2, 6)],
                     ['=', 'sonic wavegun', (2, 8)],
                     ['=', 'plasma burster', (2, 12)],
                     ['&', 'minigun', [4, 6, 3]],
                     ['&', 'flamethrower', [1, 8]],
                     ['&', 'microrocket gun', (3, 8)]]

    ancient_types = ['dagger', 'sword', 'pistol', 'rifle', 'shotgun', 'heavy']

    ancient_names = {'dagger': ['monomolecular', 'phasic', 'plasma', 'hard light', 'synthdiamond', 'chitin'],
                     'sword': ['monomolecular', 'phasic', 'plasma', 'hard light', 'synthdiamond', 'chitin'],
                     'pistol': ['neutron slug', 'disintegrator', 'electric arc', 'quark accelerator',
                                'pain ray', 'dark matter beam'],
                     'rifle': ['neutron slug', 'disintegrator', 'electric arc', 'quark accelerator',
                               'pain ray', 'dark matter beam'],
                     'shotgun': ['graviton wave gun', 'spatial distruptor', 'field projector', 'waveform collapser',
                                 'superfluid blast emitter', 'molecular vibrator'],
                     'heavy': ['existential dequantifier', 'remote fusion launcher', 'antimatter pod launcher',
                               'matter melter', 'uncertainty resolver', 'polarity reverser']}

    ancient_char = {'dagger': '-',
                    'sword': '/',
                    'pistol': ')',
                    'rifle': '}',
                    'shotgun': '=',
                    'heavy': '&'}

    ancient_damage = {'dagger': [(1, 4), (1, 6), (1, 8), (1, 10), [2, 10, 1]],
                      'sword': [(1, 8), (1, 10), (1, 12), [2, 12, 1], [3, 12, 1]],
                      'pistol': [(1, 8), (1, 10), (1, 12), (2, 8), (2, 10)],
                      'rifle': [(2, 8), (2, 10), [3, 10, 2], (2, 12), (3, 6)],
                      'shotgun': [(2, 6), (2, 8), (2, 10), (2, 12), [3, 10, 2]],
                      'heavy': [(3, 8), (3, 10), (3, 12), (4, 8), (4, 10)]}

    # determine if ancient or modern
    age = libtcod.random_get_int(0, 1, 4)
    if age < 4:
        # return modern weapon
        char, name, damage = random.choice(modern_weapon)
    else:
        # choose type of ancient weapon
        type = random.choice(ancient_types)

        # get the weapon's character
        char = ancient_char[type]

        # name the weapon
        if type == 'heavy' or type == 'shotgun':
            name = random.choice(ancient_names[type])
        else:
            name = random.choice(ancient_names[type]) + type

        # get the weapon's damage
        damage = random.choice(ancient_damage[type])

    # roll bonus
    bonus = libtcod.random_get_int(0, 1, 3) - 1

    # append bonus to name if non-zero
    if bonus > 0:
        name = name + ' +' + str(bonus)

    # put it together
    weapon = {'char': char,
              'name': name,
              'damage': damage,
              'bonus': bonus}

    return weapon