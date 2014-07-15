'''
handhRL - message support routines

additional data functions for creating on screen messages
'''
import libtcodpy as libtcod


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