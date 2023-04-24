from machine import Pin, I2S, I2C
from vl53l0x import setup_tofl_device, TBOOT
import math
import struct
import time
import _thread
import utime

# Init. constants
TONE_FREQ_START = 200
TONE_FREQ_STEP = 100
TONE_FREQ_END = 3500 # --> 168 steps

CONV_VALUE = ((TONE_FREQ_END - TONE_FREQ_START) / TONE_FREQ_STEP) / 500
print(CONV_VALUE) # <-- DEBUG

SAMPLE_RATE = 44100
I2S_BUF = 30000 
BYTES_PER_SAMPLE = 2 # Normally 2 (16-bit), but could be 4 (32-bit)


# Init. variables
vol = 100
palm = 100
finger = 100

# TODO: Make vol part of AMPLITUDE
AMPLITUDE = 1000 # For 16-bit, max of 32767 (it'll clip around 30k)

vol_bytearray = bytearray()
palm_bytearray = bytearray()
finger_bytearray = bytearray()

# Init. Pins
SDA = Pin(17)
SCL = Pin(16)

vol_shutdown = Pin(25, Pin.OUT)
palm_shutdown = Pin(26, Pin.OUT)
finger_shutdown = Pin(27, Pin.OUT)

SCK_PIN0 = Pin(4) # Serial clock (BCLK on breakout)
WS_PIN0 = Pin(15) # Word select (LRCLK on breakout)
SD_PIN0 = Pin(2) # Serial data (DIN on breakout)

SCK_PIN1 = Pin(21) # Serial clock (BCLK on breakout)
WS_PIN1 = Pin(23) # Word select (LRCLK on breakout)
SD_PIN1 = Pin(22) # Serial data (DIN on breakout)

# Init. pin values
vol_shutdown.off()
palm_shutdown.off()
finger_shutdown.off()

# Set new addresses to the i2c bus devices
vol_shutdown.on()
utime.sleep_us(TBOOT)
vol_tofl =  setup_tofl_device(i2c, 40000, 12, 8)
vol_tofl.set_address(0x2B)

palm_shutdown.on()
utime.sleep_us(TBOOT)
palm_tofl = setup_tofl_device(i2c, 40000, 12, 8)
palm_tofl.set_address(0x2C)

finger_shutdown.on()
finger_tofl = setup_tofl_device(i2c, 40000, 12, 8)
utime.sleep_us(TBOOT)
finger_tofl.set_address(0x2D)

'''
distance value goes from 40 to 530
--> round((value - 40) * 0,3) = index
'''

dict_freq = {}

# Init. data buses
i2c = I2C(1, sda=SDA, scl=SCL)

audio0 = I2S(0, # This must be either 0 or 1 for ESP32
            sck=SCK_PIN0, ws=WS_PIN0, sd=SD_PIN0,
            mode=I2S.TX,
            bits=8*BYTES_PER_SAMPLE,
            format=I2S.MONO,
            rate=SAMPLE_RATE,
            ibuf=I2S_BUF)

audio1 = I2S(1, # This must be either 0 or 1 for ESP32
             sck=SCK_PIN1, ws=WS_PIN1, sd=SD_PIN1,
             mode=I2S.TX,
             bits=8*BYTES_PER_SAMPLE,
             format=I2S.MONO,
             rate=SAMPLE_RATE,
             ibuf=I2S_BUF)

# Calc. frequency data
freq = TONE_FREQ_START
while freq <= TONE_FREQ_END:
    n_samples = SAMPLE_RATE // freq
    buffer_size = n_samples * BYTES_PER_SAMPLE

    buf = bytearray(buffer_size)
    for i in range(n_samples):
        sample = int(AMPLITUDE * math.sin(2 * math.pi * i / n_samples))
        struct.pack_into("<h", buf, i*BYTES_PER_SAMPLE, sample)

    print(len(buf)) # <-- DEBUG
    dict_freq.update({freq: buf})
    freq = freq + TONE_FREQ_STEP

def first_i2s():
 #   global dict_freq
    global audio0
    global finger_bytearray

    while True:
        #audio0.write(dict_freq[finger])
        audio0.write(finger_bytearray)

def second_i2s():
#    global dict_freq
    global audio1
    global palm_bytearray
    
    while True:
        #audio1.write(dict_freq[palm])
        audio1.write(palm_bytearray)
        
def get_distance():
    global TONE_FREQ_STEP
    global CONV_VALUE
    global TONE_FREQ_START
    global TONE_FREQ_END
    
    #global vol
    #global palm
    #global finger
    global dict_freq

    global vol_bytearray
    global palm_bytearray
    global finger_bytearray
    
    vol_tmp = 0
    vol_mean = 0

    palm_tmp = 0
    palm_mean = 0
    
    finger_tmp = 0
    finger_mean = 0

    # Measure distance and calculate the key for dict_freq
    # NOTE: 40 is the value offset of the sensor
    while True:
        '''
        vol_tmp = vol_tofl.ping()
        vol_mean = (vol_mean + vol_tmp)/2
        vol_tmp = int((vol_mean - 40)*0.3) * 25

        if vol_tmp > (160*25):
            vol = 160*25   
        elif vol_tmp <= (1*25):
            vol = 1*25
        else:
            vol = vol_tmp

        vol_bytearray = dict_freq[vol]
        '''
        
        palm_tmp = palm_tofl.ping()
        palm_mean = (palm_mean + palm_tmp)/2
        palm_tmp = int((palm_mean - 40)*CONV_VALUE) * TONE_FREQ_STEP

        if palm_tmp > TONE_FREQ_END:
            palm = TONE_FREQ_END
        elif palm_tmp <= TONE_FREQ_START:
            palm = TONE_FREQ_START
        else:
            palm = palm_tmp

        palm_bytearray = dict_freq[palm]+dict_freq[palm]+dict_freq[palm]

        finger_tmp = finger_tofl.ping()
        finger_mean = (finger_mean + finger_tmp)/2 
        finger_tmp = int((finger_mean - 40)*CONV_VALUE) * TONE_FREQ_STEP

        if finger_tmp > TONE_FREQ_END:
            finger = TONE_FREQ_END   
        elif finger_tmp <= TONE_FREQ_START:
            finger = TONE_FREQ_START
        else:
            finger = finger_tmp

        finger_bytearray = dict_freq[finger]+dict_freq[finger]+dict_freq[finger]
        #time.sleep(0.2)


#_thread.start_new_thread(first_i2s,())        
#_thread.start_new_thread(second_i2s, ())
_thread.start_new_thread(get_distance,())

#index = TONE_FREQ_START
while True: #index <= TONE_FREQ_END:
    #print('   ',finger )
    audio0.write(finger_bytearray) # check to switch here the order
    audio1.write(palm_bytearray)
    #get_distance()
    #audio1.write(dict_freq[325])
    #audio1.write(buf1)

    #index = index + 100
    
audio0.deinit()
audio1.deinit()
