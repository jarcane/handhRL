'''
handhRL - table functions

This file contains the table functions needed for main.

'''


import libtcodpy as libtcod


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

    return monster_table