#!/usr/bin/python
#
# Basic example of using Python-SMBus and a ADS1115

import smbus as smbus
import RPi.GPIO as GPIO
import time
import datetime

MINUTES_BETWEEN_SAMPLES = 30
# check the moisture levels, decide if water should be on or off, then wait this
# many minutes before checking again


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
    return datetime.datetime.today().strftime('INFO: %Y-%b-%d %H:%M:%S :')


# Pin Definitons:
RelayPin = 18 # Broadcom pin 18 (P1 pin 12)

# Pin Setup:
GPIO.setmode(GPIO.BCM) # Broadcom pin-numbering scheme
GPIO.setup(RelayPin, GPIO.IN)
# Note, I'm going to use the pin as an input when I don't want the Relay to
# trip, but then switch to output and pull it low when I want to trip the
# relay (i.e. have it closed)
#
# For now, I'm going to turn on the relay whenever any of the 3 conditions
# are met


# ADC sample loop definitions
ADC_FUNCS = ["VH400", "GROVE", "DIVIDER"]
ADCS = [MUX_ADC_IN3, MUX_ADC_IN2, MUX_ADC_IN1] #note, not using ADC0
TRIPS = [0.3, 1.1, 0.9]

print nowstr(), "Water Controller started"

# Main (and infinite) loop
waterIsOn = 0
while True:
    relayOnCount = 0
    for adci in range(0, len(ADCS)):
        triggerSample(ADCS[adci])
        time.sleep(0.5)
        sample = readSample(ADCS[adci])
        v = sample2Voltage(sample)
        #print ADC_FUNCS[adci], "voltage:", v
        if (v < TRIPS[adci]):
            relayOnCount += 1
            if (waterIsOn == 0):
                print nowstr(), "Turning on water because of", ADC_FUNCS[adci]
    if (relayOnCount > 0):
        GPIO.setup(RelayPin, GPIO.OUT)
        GPIO.output(RelayPin, GPIO.LOW)
        waterIsOn = 1
    else:
        if (waterIsOn == 1):
            print nowstr(),"Turning off water because all sensors show dry"
        GPIO.setup(RelayPin, GPIO.IN)
        waterIsOn = 0
    time.sleep(MINUTES_BETWEEN_SAMPLES*60.0)



