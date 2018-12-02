#!/usr/bin/python3

import time

from gpiozero import LED

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
    "-": "g"
    }

ms = 1/1000
us = ms / 1000
ns = us / 1000

t_CLK = 1 * us
t_LE  = 1 * us

def initialise():
    controls = {}
    controls["CLK"] = LED(14)
    controls["SDI"] = LED(15)
    controls["LE"]  = LED(18)
    controls["OE"]  = LED(23)
    return controls

def sleep(duration):
    # May want to change this to be a busy wait.
    # time.sleep() is not very precice. 
    time.sleep(duration)

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
    control.on()
    time.sleep(duration)
    control.off()

def send_bit(bit, controls):
    controls["SDI"].value = bit
    pulse(controls["CLK"], t_CLK)

def send_serial(bits, controls):
    # Send the bits in reverse order as the first one in gets
    # shuffled all the way down to OUT7.
    reversed_bits = bits[::-1]
    for bit in reversed_bits:
        send_bit(bit, controls)

def latch_display(controls):
    pulse(controls["LE"], t_LE)

def update_display(text):
    # Starting with the last character, work out which
    # bits should be set, and send them through. Finally
    # latch the driver so that the display updates. 

    controls = initialise()

    logger.debug("Updating display: '" + text + "'")
    bits = []
    reversed_text = text[::-1]
    for char in reversed_text:
        send_serial(digit_to_bits(char), controls)
        
    latch_display(controls)



update_display("12x45")

