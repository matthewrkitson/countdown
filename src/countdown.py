#!/usr/bin/python3

import time
import datetime
import itertools
import logging
import gpiozero
import threading

from log import logger

#              a     
#           -------  
#          /      /  
#      f  /      / b 
#        /  g   /    
#       /------/     
#      /      /      
#   e /      / c     
#    /  d   /        
#    -------  (.) P  
#

segments = { 
    "0": "abcdef",
    "1": "bc",
    "2": "abged",
    "3": "abgcd",
    "4": "fgbc",
    "5": "afgcd",
    "6": "afedcg",
    "7": "fabc",
    "8": "abcdefg",
    "9": "gfabcd",
    "-": "g",
    " ": ""
    }

ms = 1/1000
us = ms / 1000
ns = us / 1000

t_CLK = 10 * ms
t_LE  = 10 * ms

def initialise():
    # I happen to have the following coloured wires attached
    # to my PCB, and wire them to the Pi in the following order
    #
    # Orange   Vdd   3.3V
    # Yellow    NC      -
    # Green   Vled     5V
    # Blue     GND    GND
    # 
    # Purple   CLK   GPIO 14
    # Grey     SDI   GPIO 15
    # White     LE   GPIO 18
    # Black     OE   GPIO 23
    # 

    controls = {}
    controls["lock"] = threading.Lock()
    controls["CLK"] = gpiozero.LED(14)
    controls["SDI"] = gpiozero.LED(15)
    controls["LE"]  = gpiozero.LED(18)
    controls["OE"]  = gpiozero.LED(23)

    # OE is active low, so turn on to disable all lights to start with. 
    controls["OE"].on()
    
    return controls

def sleep(duration):
    # May want to change this to be a busy wait.
    # time.sleep() is not very precice. 
    # time.sleep(duration)
    pass

def digit_to_bits(digit):
    logger.debug("Converting '" + digit + "' to bits.")
    if digit not in segments:
        logger.debug("'" + digit + "' not displayable. Ignoring.")
        return []

    # Bit array corresponding to desired output on OUT0, OUT1, etc
    # on TLC5916. bits[0] = OUT0. 
    bits = [False, False, False, False, False, False, False, False]
    segments_to_light = segments[digit]
    bits[0] = "b" in segments_to_light
    bits[1] = "g" in segments_to_light
    bits[2] = "c" in segments_to_light
    bits[3] = "P" in segments_to_light
    bits[4] = "d" in segments_to_light
    bits[5] = "e" in segments_to_light
    bits[6] = "f" in segments_to_light
    bits[7] = "a" in segments_to_light

    logger.debug(str(bits))
    return bits

def pulse(control, duration):
    logger.debug("Pulse " + control)
    sleep(duration / 2)
    controls[control].on()
    sleep(duration)
    controls[control].off()
    sleep(duration / 2)

def send_bit(bit, controls):
    logger.debug("SDI = " + str(bit))
    controls["SDI"].value = bit
    pulse("CLK", t_CLK)

def send_serial(bits, controls):
    # Send the bits in reverse order as the first one in gets
    # shuffled all the way down to OUT7.
    reversed_bits = bits[::-1]
    for bit in reversed_bits:
        send_bit(bit, controls)

def latch_display(controls):
    pulse("LE", t_LE)
    # pass

def update_display(text, controls):
    # Starting with the last character, work out which
    # bits should be set, and send them through. Finally
    # latch the driver so that the display updates. 

    with controls["lock"]:
        logger.debug("Updating display: '" + text + "'")
        bits = []
        reversed_text = text[::-1]
        for char in reversed_text:
            send_serial(digit_to_bits(char), controls)
        
        latch_display(controls)

def switch_mode(mode, controls):
    old_oe = controls["OE"].value
    controls["LE"].off()
    controls["OE"].on()
    pulse("CLK", t_CLK)
    controls["OE"].off()
    pulse("CLK", t_CLK)
    controls["OE"].on()
    pulse("CLK", t_CLK)
    if mode == "special":
        controls["LE"].on()
    else:
        controls["LE"].off()
    pulse("CLK", t_CLK)
    controls["LE"].off()
    pulse("CLK", t_CLK)
    controls["OE"].value = old_oe

def set_brightness(configuration_code, controls):
    with controls["lock"]:
        old_oe = controls["OE"].value
        switch_mode("special", controls)
        controls["OE"].on()
        send_serial(configuration_code, controls)
        send_serial(configuration_code, controls)
        send_serial(configuration_code, controls)
        send_serial(configuration_code, controls)
        send_serial(configuration_code, controls)
        send_serial(configuration_code, controls)
        send_serial(configuration_code, controls)
        send_serial(configuration_code, controls)
        send_serial(configuration_code, controls)
        latch_display(controls)
        controls["OE"].value = old_oe
        switch_mode("normal", controls)

def enable_display(controls):
    with controls["lock"]:
        controls["OE"].off()

def disable_display(controls):
    with controls["lock"]:
        controls["OE"].on()

def time_delta(now, then):
    delta = then - now
    days = delta.days
    hours, minsec = divmod(delta.seconds, 3600)
    mins, secs = divmod(minsec, 60)
    return days, hours, mins, secs, delta.microseconds

def toggle_motivational_mode(controls, state):
    mode = state["motivation_mode"]
    if mode == "normal":
        state["motivation_mode"] = "motivational"
        code = [1, 1, 1, 1, 1, 1, 1, 1]
        set_brightness(code, controls)
        enable_display(controls)
    elif mode == "motivational":
        code = [1, 1, 1, 1, 1, 1, 1, 1]
        set_brightness(code, controls)
        state["motivation_mode"] = "extra motivational"
    else:
        code = [0, 0, 0, 0, 0, 0, 0, 0]
        set_brightness(code, controls)
        enable_display(controls)
        state["motivation_mode"] = "normal"

    print("State is now " + state["motivation_mode"])

def set_target(state):
    now = datetime.datetime.now()
    delta = datetime.timedelta(minutes = 6)
    target = now + delta
    state["target"] = target
    state["running"] = False

logger.setLevel(logging.INFO)
controls = initialise()
set_brightness([0, 0, 0, 0, 0, 0, 0, 0], controls)
enable_display(controls)

state = { "motivation_mode": "normal" }

button1 = gpiozero.Button(2)
button2 = gpiozero.Button(3)
button3 = gpiozero.Button(4)
button4 = gpiozero.Button(17)
button5 = gpiozero.Button(27)

buzzer = gpiozero.LED(24)
button1.when_pressed = buzzer.on
button1.when_released = buzzer.off

button2.when_pressed = lambda: toggle_motivational_mode(controls, state)

button3.when_pressed = lambda: set_target(state)

# target = datetime.datetime(2019, 3, 29, 17, 0, 0)
set_target(state)

current_display = ""
while True:
    now = datetime.datetime.now()
    target = state["target"]
    d, h, m, s, us = time_delta(now, target)
    ds = int(us / 10000)
    if d < 0:
        new_display = "000.00.00.00"
    else:
        new_display = "{0:03}.{1:02}.{2:02}.{3:02}".format(h, m, s, ds)
    if new_display != current_display:
        # logger.info(display)
        update_display(new_display, controls)
        current_display = new_display
    if (state["motivation_mode"] == "extra motivational") or (d < 0):
        if us <= 250e3 or (us > 500e3 and us <= 750e3):
            enable_display(controls)
        else:
            disable_display(controls)
    # time.sleep(0.001)
