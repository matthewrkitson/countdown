#!/usr/bin/python3

import logging
from log import logger
logger.setLevel(logging.INFO)
logger.info("")
logger.info("")
logger.info("Countdown controller started")

logger.info("Importing python modules")
import time
import datetime
import itertools
import gpiozero
import threading
import subprocess


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

def poweroff():
    subprocess.check_call(["sudo", "poweroff"])

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

    logger.info("Initialising LED controller")
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

def time_delta(now, then, countdown):
    signed_delta = then - now if countdown else now - then
    delta = abs(signed_delta)
    days = delta.days
    hours, minsec = divmod(delta.seconds, 3600)
    mins, secs = divmod(minsec, 60)
    return days, hours, mins, secs, delta.microseconds, signed_delta.total_seconds()

def toggle_motivational_mode(controls, state):
    mode = state["motivation_mode"]
    if mode == "normal":
        state["motivation_mode"] = "motivational"
        code = [1, 1, 1, 1, 1, 1, 1, 1]
        set_brightness(code, controls)
        enable_display(controls)
    elif mode == "motivational":
#        code = [1, 1, 1, 1, 1, 1, 1, 1]
#        set_brightness(code, controls)
#        state["motivation_mode"] = "extra motivational"
#    else:
        code = [0, 0, 0, 0, 0, 0, 0, 0]
        set_brightness(code, controls)
        enable_display(controls)
        state["motivation_mode"] = "normal"

    print("State is now " + state["motivation_mode"])

def set_target(state, controls, buzzer):
    # Reset button only has any effect in fixed mode.
    if state["mode"] == "fixed":
        now = datetime.datetime.now()
        delta = state["duration"]
        target = now + delta
        state["target"] = target
        state["last_update"] = now
        state["running"] = False
        buzzer.off()
        enable_display(controls)

def toggle_running(state, controls, buzzer):
    # Start/stop button only has any effect in fixed mode.
    if state["mode"] == "fixed":
        state["running"] = not state["running"]
        if not state["running"]:
            buzzer.off()
            enable_display(controls)

controls = initialise()
set_brightness([0, 0, 0, 0, 0, 0, 0, 0], controls)
enable_display(controls)

now = datetime.datetime.now()
duration = datetime.timedelta(minutes = 6)
countdown_target = datetime.datetime(2023, 10, 13, 17, 40, 0)
mode = "targetted" # Can be "fixed" or "targetted"

state = { 
            "motivation_mode": "normal",
            "mode": mode,
            "running": True if mode == "targetted" else False,
            "countdown": True,    # True for countdown, false for countup
            "duration": duration,
            "target": countdown_target,
            "last_update": now,
        }

logger.info("Configuring GPIO")
button1 = gpiozero.Button(2)
button2 = gpiozero.Button(3)
button3 = gpiozero.Button(4)
button4 = gpiozero.Button(17)
button5 = gpiozero.Button(27)

buzzer = gpiozero.LED(24)
button1.when_pressed = buzzer.on
button1.when_released = buzzer.off

button2.when_pressed = lambda: toggle_motivational_mode(controls, state)

button3.when_pressed = lambda: set_target(state, controls, buzzer)

button4.when_pressed = lambda: toggle_running(state, controls, buzzer)

button5.when_pressed = lambda: poweroff()

set_target(state, controls, buzzer)

logger.info("Starting countdown loop")
logger.info("--> Press Ctrl+C to stop")
logger.info("")

current_display = ""
while True:
    now = datetime.datetime.now()
    last_update = state["last_update"]

    if not state["running"]:
        state["target"] = state["target"] + (now - last_update)
        
    target = state["target"]
    d, h, m, s, us, dt = time_delta(now, target, state["countdown"])
    if dt < 0:
        new_display = "  0.00.00.00"
    else:
        new_display = "{0:>3}.{1:02}.{2:02}.{3:02}".format(d, h, m, s)
    
    if new_display != current_display:
        update_display(new_display, controls)
        current_display = new_display
    
    if state["running"] and ((state["motivation_mode"] == "extra motivational") or (dt < 0)):
        if us <= 250e3 or (us > 500e3 and us <= 750e3):
            enable_display(controls)
            buzzer.on()
        else:
            disable_display(controls)
            buzzer.off()

    state["last_update"] = now

    if not state["running"]:
        time.sleep(0.01)
