#!/usr/bin/python
import RPi.GPIO as GPIO
import datetime
import time
import os
import sys
import subprocess
import plotly.plotly as py
from plotly.graph_objs import Scatter, Data, Layout, XAxis, YAxis, Figure
import ConfigParser
from retrying import retry

# remember to add ability to set the I2C address to the configparser stuff

###############################################################################
def create_config_dict(config, section):
    "Returns a configuration dictionary for a given section, using a ConfigParser instance"
    d = {}
    options = config.options(section)
    for option in options:
        try:
            d[option] = config.get(section, option)
        except:
            print("Configuration exception for option %s." % option)
            d[option] = None
    return d

def get_config(config_file):
    "Return a dictionary of configuration options from the configuration file"
    # Create a ConfigParser instance
    config = ConfigParser.ConfigParser()
    # Try to read the configuration file
    try:
        with open(config_file) as f:
            config.readfp(f)
    except IOError:
        print("Couldn't open configuration file.")
        sys.exit("Exiting.")
    # Create an empty configuration dictionary, then update it with details
    # from the ConfigParser instance
    config_dict = {}
    config_dict.update(create_config_dict(config, 'secrets'))
    config_dict.update(create_config_dict(config, 'general'))
    # Change the natural language boolean to an actual boolean value
    config_dict['upload_graph'] = config.getboolean('general', 'upload_graph')
    config_dict['HCPL3700'] = config.getint('general', 'HCPL3700')
    return config_dict

# seconds to wait before looping (put in config file)
global nap
nap = 300

ADT7410_UNIT_13 = 0.0625
ADT7410_UNIT_16 = 0.0078

# Configure the Analog Devices ADT7410 temperature sensor
# These constants define the address registers
ADT7410_T_MSB = 0x00
ADT7410_T_LSB = 0x01
ADT7410_STATUS = 0x02
ADT7410_CONF = 0x03
ADT7410_T_HIGH_MSB = 0x04
ADT7410_T_HIGH_LSB = 0x05
ADT7410_T_LOW_MSB = 0x06
ADT7410_T_LOW_LSB = 0x07
ADT7410_T_CRIT_MSB = 0x08
ADT7410_T_CRIT_LSB = 0x09
ADT7410_T_HYST = 0x0A
ADT7410_ID = 0x0B
ADT7410_RESET = 0x2F

# Configuration modes: continuous, one-shot mode, 1 sample per second, or off
ADT7410_CONF_CON = 0x00
ADT7410_CONF_OSM = 0x20
ADT7410_CONF_SPS = 0x40
ADT7410_CONF_OFF = 0x60
 
# Possible I2C addresses
ADT7410_ADDR_00 = 0x48 # A0 and A1 ground
ADT7410_ADDR_01 = 0x49 # A0 ground, A1 Vdd
ADT7410_ADDR_10 = 0x4A # A0 Vdd, A1 ground
ADT7410_ADDR_11 = 0x4B # A0 and A1 Vdd

# Try to read bytes from the specified I2C address and register
# On failure, report the error code
# Note that I use hipi-i2c, rather than python-smbus because
# the latter is broken
def i2c_read(i2c_addr, register):
    try:
    	b = int(subprocess.check_output(["/usr/local/bin/hipi-i2c", "r", "1", "0x{:02X}".format(i2c_addr), "0x{:02X}".format(register)]))
    except subprocess.CalledProcessError as e:
	print "hipi-i2c subprocess error code: ", e.returncode
	print "hipi-i2c subprocess output: ", e.output
    if b is None:
        print "Error: I2C read error! No data returned"
        return None
    else:
        return b

# Check status register to see if the temperature registers are ready to be read
def is_temp_rdy(i2c_addr):
    status = i2c_read(i2c_addr, ADT7410_STATUS)
    # Discard all but MSB
    status = status >> 7
    # check if MSB is 1, which means NOT ready
    if status:
        print "Error: temperature registers not ready."
        return False
    else:
        return True

def twos_complement_13_bit(t):
	# check if MSB is 1
    if t & 0x1000:
        # Negative two's complement value
        # Negate the value, AND with 13 1s, and add 1; add a negative sign
        return -((~t & 0x1FFF) + 1)
    else:
        # Positive value
        return t

# Return a table with manufacturer ID and silicon revision
def get_dev_id(i2c_addr):
    dev_id = {}
    b = i2c_read(i2c_addr, ADT7410_ID)
    # print "DEBUG raw dev id byte: ", bin(b)
    # top 5 bits indicate manufacturer ID
    dev_id['manuf_id'] = b >> 3
    # lowest 3 bits indicate silicon revision
    dev_id['si_rev'] = b & 0x07
    return dev_id

# Return a byte with device configuration information
def get_dev_conf(i2c_addr):
    b = i2c_read(i2c_addr, ADT7410_CONF)
    return b

def read_13_bit_temp(i2c_addr):
    if is_temp_rdy(i2c_addr):
        # Return the number of ticks above/below 0 in ADT7410 13 bit increments
        temp_msb = i2c_read(i2c_addr, ADT7410_T_MSB)
	# print "DEBUG temp_msb: ", bin(temp_msb)
        temp_lsb = i2c_read(i2c_addr, ADT7410_T_LSB)
	# print "DEBUG temp_lsb: ", bin(temp_lsb)
        # Combine the two bytes into a word
        temp_raw = (temp_msb << 8) + temp_lsb
	#print "DEBUG temp_raw: ", bin(temp_raw)
        # Discard 3 LSBs, which indicate threshold faults in 13 bit mode and are unused here
        temp_raw = temp_raw >> 3
	#print "DEBUG temp_raw after discarding 3 lsbs: ", bin(temp_raw)
        # Convert from a 13 bit integer to a celsius temperature
        temp_raw = twos_complement_13_bit(temp_raw)
	#print "DEBUG temp_raw after 2s comp conversion: ", bin(temp_raw)
    else:
        temp_raw = None
    return temp_raw

def normal_temp_read(i2c_addr):
    # configure in one sample per second mode
    # FIXME
    #bus.write_byte_data(i2c_addr, ADT7410_CONF, ADT7410_CONF_SPS)
    time.sleep(0.5)
    # check if ready here
    # Return the number of ticks above/below 0 in ADT7410 13 bit increments
    temp_raw = read_13_bit_temp(i2c_addr)
    return temp_raw

def one_shot_temp_read(i2c_addr):
    # FIXME
    #bus.write_byte_data(i2c_addr, ADT7410_CONF, ADT7410_CONF_OSM)
    # ADT7410 datasheet says to wait at least 240 ms after setting OSM before reading
    time.sleep(0.5)
    temp_raw
    # Return the number of ticks above/below 0 in ADT7410 13 bit increments
    temp_raw = read_13_bit_temp(i2c_addr)
    return temp_raw

def report_temp(i2c_addr, mode):
    if mode == 0:
        temp_raw = normal_temp_read(i2c_addr)
    else:
        temp_raw = one_shot_temp_read(i2c_addr)
    
    if temp_raw is None:
    	print "Couldn't get temperature!"
    	return None, None
    else:		
		# multiply by 13 bit tick size
		temp_c = temp_raw * ADT7410_UNIT_13
		temp_f = temp_c * 1.8 + 32.0
		return temp_f

def cb_therm_status(channel, initial=False):
	t = datetime.datetime.now()
        print str(t)
	temp = report_temp(i2c_addr, mode)
	print temp, "F"
        if GPIO.input(channel):
                print "HVAC OFF"
                # append thermostat_status data point to plot
                # Need to pass it both the time and the value
		therm_status = 0
        else:
                print "HVAC ON"
                # append thermostat_status data point to plot
		therm_status = 1
        url = graph_therm(t, therm_status, temp, initial)
	global prev_therm_status
	prev_therm_status = therm_status 
        return t, therm_status, temp

def get_analog_value(channel):
  adc = spi.xfer2([1,(8+channel)<<4,0])
  data = ((adc[1]&3) << 8) + adc[2]
  return data

def get_temp_c(analog_value):
        voltage = (analog_value * 3.3) / 1023.0
        return voltage * 100.0

def convert_temp_f(temp_c):
        temp_f = temp_c * 1.8 + 32.0
        return temp_f

# Retry our request up to x=5 times, waiting 2^x * 1 minute after each retry
@retry(stop_max_attempt_number=5, wait_exponential_multiplier=60000)
def pyplot(fig, name):
    "py.plot with retrying. Pass in a figure and a name, returns a url."
    return py.plot(fig, filename=name, auto_open=False, fileopt='extend')

def graph_therm(timestamp, therm_status, temp, initial=False):
    if config_dict['upload_graph']:
        print('Appending data to Plotly graph...')
        py.sign_in(config_dict['plotly_userid'], config_dict['plotly_apikey'])
        # If this isn't the very first data point, create a pseudo-reading
	# that happens one second before the true reading, and has the previous thermostat status value 
	# I.e., when an interrupt occurs, graph the preceding value
	if initial == False:
		timestamp = [timestamp]
		timestamp.insert(0, timestamp[0] - datetime.timedelta(seconds=1))	
		temp = [temp]
		# Just duplicate the temperature
		temp.insert(0, temp)
		therm_status = [therm_status]
		therm_status.insert(0, prev_therm_status) 
	#
        scatter1 = Scatter(x=timestamp,
                   y=therm_status,
                   name='Thermostat Status')
        scatter2 = Scatter(x=timestamp,
                   y=temp,
                   name='Indoor Temperature', yaxis='y2')
        #
        data = Data([scatter1, scatter2])
        #
        layout = Layout(
                        title='Indoor Temperature and Thermostat Status',
                        yaxis=YAxis(title='Thermostat Status', range=[-1,2]),
                        yaxis2=YAxis(title='Indoor Temperature', range=[55, 85], overlaying='y', side='right'),
                        xaxis=XAxis(title='Date and Time')
                        )
        #
        fig = Figure(data=data, layout=layout)
        url1 = pyplot(fig, 'thermostat')
        print('Done uploading.')
        return url1

def main():
	try:
			# Change to the working directory, which is the directory of the script
			pathname = os.path.dirname(sys.argv[0])
			working_dir = os.path.abspath(pathname)
			try:
				os.chdir(working_dir)
			except:
				print("Couldn't change to script directory.")
				sys.exit("Exiting.")
			# Get configuration options
			global config_dict
			config_dict = get_config('thermostat_monitor.conf')
			GPIO.setmode(GPIO.BOARD)
			GPIO.setup(config_dict['HCPL3700'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
	
			# Set sensor's address
			global i2c_addr
			i2c_addr = ADT7410_ADDR_00
			# 0 is one sample per second, anything else is one shot mode
			global mode
			mode = 0
	
			# ADT7410 testing
			print "Getting ADT7410 info:"
			dev_id = get_dev_id(i2c_addr)
			print "Manufacturer ID: ", bin(dev_id['manuf_id'])
			print "Silicon revision: ", bin(dev_id['si_rev'])
			print "Device configuration: ", bin(get_dev_conf(i2c_addr))

			print str(datetime.datetime.now())
			print "Monitoring the thermostat with the HCPL3700..."
	
			# Initially just poll once to get the status of the line
			print "Getting initial status:"
			t, therm_status, temp = cb_therm_status(config_dict['HCPL3700'], initial=True)
			f = open('thermostat.log', 'a')
			f.write("{},{},{}\n".format(t, therm_status, temp))
			f.flush()

			print "Sleeping {} seconds.".format(nap)
			time.sleep(nap)
			print "Now detecting interrupts while sleeping/polling for temperature..."
			GPIO.add_event_detect(config_dict['HCPL3700'], GPIO.BOTH, callback=cb_therm_status, bouncetime=100)
	
			while True:
				# Event detection will take place in this never-ending loop
				# Note we call this with initial=True to avoid plotting the fake previous data point	
				t, therm_status, temp = cb_therm_status(config_dict['HCPL3700'], initial=True)
				f.write("{},{},{}\n".format(t, therm_status, temp))
				f.flush()
				time.sleep(nap)
	except KeyboardInterrupt:
			pass
			# clean up GPIO on CTRL+C exit
	finally:
			print "Cleaning up GPIO..."
			GPIO.cleanup()
			f.close()

if __name__ == "__main__":
    main()
