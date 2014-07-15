"""
handhRL - message support routines

additional data functions for creating on screen messages
"""

import libtcodpy as libtcod
import time


# important note: these MUST MATCH THE ONES IN handhrl.py!
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50


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


def show_text_log(text, img=None, delay=True, center_first_line=False):
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
            if center_first_line and y == 0:
                libtcod.console_print_ex(0, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 5 + y * 2, libtcod.BKGND_NONE,
                                         libtcod.CENTER, text[y])
            else:
                libtcod.console_print_ex(0, SCREEN_WIDTH / 8, SCREEN_HEIGHT / 5 + y * 2, libtcod.BKGND_NONE,
                                         libtcod.LEFT, text[y])

            if delay:
                libtcod.console_flush()
                time.sleep(1.3)
                key = libtcod.console_check_for_keypress()
                if key.vk == libtcod.KEY_SPACE:
                    delay = False

    libtcod.console_set_default_foreground(0, libtcod.white)
    libtcod.console_print_ex(0, SCREEN_WIDTH / 2, SCREEN_HEIGHT - 2, libtcod.BKGND_NONE, libtcod.CENTER,
                             'Press any key to continue')
    libtcod.console_flush()
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


def help_screen():
    # display a message with information about available key commands
    help_text = [
        'Game Controls',
        '',
        'ESC - Exit to menu, saving game',
        'Alt+Enter - toggle fullscreen',
        'NumPad or Arrows - move character or attack adjacent',
        '5 or Space - wait one turn',
        'h or ? - display this help screen',
        's - shoot with ranged weapon if equipped',
        'a - check ammo of equipped ranged weapon',
        'g - get item beneath character',
        'i - inventory/use item',
        'd - drop item',
        'c - character status',
        '< - descend stairs'
    ]

    show_text_log(help_text, generate_screen(), delay=False, center_first_line=True)
