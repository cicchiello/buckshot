#!/usr/bin/python
#
# Basic example of using Python-SMBus, ADS1115 and Sainsmart 5V Relay via GPIO

import smbus as smbus
import RPi.GPIO as GPIO
import time
import datetime

MINUTES_BETWEEN_SAMPLES = 30
# check the moisture levels, decide if water should be on or off, then wait this
# many minutes before checking again

WATER_ON_TIME_MINUTES = 5
# when it's determined that the water should be on, run it for this many minutes

GROVE_min_volts = 0.0  # when sensor is out of the soil and dry
GROVE_max_volts = 3.3  # when sensor area is completely submerged in water
VH400_min_volts = 0.05 # when sensor is out of the soil and dry
VH400_max_volts = 2.8  # when sensor area is completely submerged in water

bus = smbus.SMBus(1)

# default address of the ADS1115 (as found by i2cdetect)
#    If desired, can be modified by wiring the module a bit differently,
#    but it's an unusual approach (presumably to save pins).  See datasheet.
address = 0x48  

config_reg = 0x01
conversion_reg = 0x00

# Config register layout:
#  b[15]: OS: Operational status: always 0b1 for our use (begin single-shot)
#  b[14:12]: MUX[2:0]: specifies which input (0b111=AIN3, single-ended for us)
#  b[11:9]: PGA[2:0]: FS (0b001 for input range to 4.096V)
#  b[8]: MODE: always 0b1 for our use (single-shot mode)
#  b[7:5]: DR[2:0]: 0b100 use default 128SPS
#  b[4]: COMP_MODE: 0b0 for traditional comparator mode
#  b[3]: COMP_POL: 0b0 not using ALERT feature
#  b[2]: COMP_LAT: 0b0 not using ALERT feature
#  b[1:0]: COMP_QUE: 0b11 to disable ALERT feature
base_config_b0 = 0b10000011
base_config_b1 = 0b10000011

MUX_ADC_IN3 = 0b01110000  # tied to Vegetronic VH400
MUX_ADC_IN2 = 0b01100000  # tied to Seedstudio Grove moisture sensor
MUX_ADC_IN1 = 0b01010000  # tied to resistor divider (3.3V*4.7K/(4.7K+10K) ~= 1.055V)
                          #   1.055V on scale 0->4.096 = 0.25759
                          #   0.25759 of full (positive) scale for 16bits --> 8440
                          #   (of course, resistors are both +/- 5%)
MUX_ADC_IN0 = 0b01000000  # currently unused


def triggerSample(mux):
    b0 = base_config_b0 | mux
    bus.write_i2c_block_data( address, config_reg, [b0, base_config_b1]);
    

def readSample(mux):
    v = bus.read_word_data(address, conversion_reg)
    #note, result is interpreted by Python as little-endian, but it's actually
    #big-endian -- so swap the bytes
    bh = (v>>8)&0xff
    bl = v&0xff
    v = (bl<<8)|bh
    if (v > 0x8000):
        v = 0
    return v


def sample2Voltage(sample):
    return sample/32767.0*4.096


def nowstr():
    fmt = 'INFO: %Y-%b-%d %H:%M:%S :'
    return datetime.datetime.today().strftime(fmt)


# Pin Definitons:
Relay1Pin = 17 # Broadcom pin 17 (P1 pin 11)
Relay2Pin = 18 # Broadcom pin 18 (P1 pin 12)

# Pin Setup:
GPIO.setmode(GPIO.BCM) # Broadcom pin-numbering scheme
GPIO.setup(Relay1Pin, GPIO.IN)
GPIO.setup(Relay2Pin, GPIO.IN)
# Note, I'm going to use the pins as inputs when I don't want the Relays to
# trip, but then switch to output and pull low when I want to trip the
# relay (i.e. have it closed)

# ADC sample loop definitions
ADC_FUNCS = ["VH400", "GROVE", "DIVIDER"]
ADCS = [MUX_ADC_IN3, MUX_ADC_IN2, MUX_ADC_IN1] #note, not using ADC0
RELAYS = [Relay1Pin, Relay2Pin, 0]
TRIPS = [0.3, 1.1, 0.9]

print nowstr(), "Water Controller started"

# Main (and infinite) loop
while True:
    relayOnCount = 0
    for adci in range(0, len(ADCS)):
        triggerSample(ADCS[adci])
        time.sleep(0.5)
        sample = readSample(ADCS[adci])
        v = sample2Voltage(sample)
        #print ADC_FUNCS[adci], "voltage:", v
        if ((v < TRIPS[adci]) and (RELAYS[adci] > 0)):
            relayOnCount += 1
            print nowstr(), "Turning on water because of", ADC_FUNCS[adci]
            GPIO.setup(RELAYS[adci], GPIO.OUT)
            GPIO.output(RELAYS[adci], GPIO.LOW)
    if (relayOnCount > 0):
        time.sleep(WATER_ON_TIME_MINUTES*60.0)
        print nowstr(),"Turning off water"
        for i in range(0, len(RELAYS)):
            GPIO.setup(RELAYS[i], GPIO.IN)
    time.sleep(MINUTES_BETWEEN_SAMPLES*60.0)

