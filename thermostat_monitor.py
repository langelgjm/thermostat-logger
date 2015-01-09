import RPi.GPIO as GPIO
import datetime
import time
import os
import sys
import spidev
import plotly.plotly as py
from plotly.graph_objs import Scatter, Data, Layout, XAxis, YAxis, Figure
import ConfigParser
from retrying import retry

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

def cb_therm_status(channel, initial=False):
	t = datetime.datetime.now()
        print str(t)
        if GPIO.input(channel):
                print "Heating turned OFF."
                # append thermostat_status data point to plot
                # Need to pass it both the time and the value
		therm_status = 0
                url = graph_therm(t, therm_status, initial)
        else:
                print "Heating turned ON."
                # append thermostat_status data point to plot
		therm_status = 1
                url = graph_therm(t, therm_status, initial)
	global prev_therm_status
	prev_therm_status = therm_status 
        return therm_status

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

def graph_therm(timestamp, value, initial=False):
    if config_dict['upload_graph']:
        print('Appending data to Plotly graph...')
        py.sign_in(config_dict['plotly_userid'], config_dict['plotly_apikey'])
        # If this isn't the very first data point, create a pseudo-reading
	# that happens one second before the true reading, and has the previous thermostat status value 
	# I.e., when an interrupt occurs, graph the preceding value
	if initial == False:
		timestamp = [timestamp]
		timestamp.insert(0, timestamp[0] - datetime.timedelta(seconds=1))	
		value = [value]
		value.insert(0, prev_therm_status) 
        scatter1 = Scatter(x=timestamp,
                   y=value,
                   name='Thermostat Status')
        #
        data = Data([scatter1])
        #
        layout = Layout(
                        title='Indoor Temperature and Thermostat Status',
                        yaxis=YAxis(title='Thermostat Status', range=[-1,2]),
                        yaxis2=YAxis(title='Indoor Temperature', range=[50, 90], overlaying='y', side='right'),
                        xaxis=XAxis(title='Date and Time')
                        )
        #
        fig = Figure(data=data, layout=layout)
        url1 = pyplot(fig, 'thermostat')
        print('Done uploading.')
        return url1

def graph_temp(timestamp, value):
    if config_dict['upload_graph']:
        print('Appending data to Plotly graph...')
        py.sign_in(config_dict['plotly_userid'], config_dict['plotly_apikey'])
        #
        scatter2 = Scatter(x=timestamp,
                   y=value,
                   name='Indoor Temperature', yaxis='y2')
        #
        data = Data([scatter2])
        #
        layout = Layout(
                        title='Indoor Temperature and Thermostat Status',
                        yaxis=YAxis(title='Thermostat Status', range=[-1,2]),
                        yaxis2=YAxis(title='Indoor Temperature', range=[50, 90], overlaying='y', side='right'),
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
	
			global spi
			spi = spidev.SpiDev()
			spi.open(0,0)
	
			print str(datetime.datetime.now())
			print "Monitoring the thermostat with the HCPL3700..."
	
			# Initially just poll once to get the status of the line
			print "Getting initial status:"
			cb_therm_status(config_dict['HCPL3700'], initial=True)
	
			print "Now detecting interrupts while polling for temperature and sleeping..."
			GPIO.add_event_detect(config_dict['HCPL3700'], GPIO.BOTH, callback=cb_therm_status, bouncetime=100)
			value = 0
			reading = 1
	
			while True:
					# Event detection will take place in this never-ending loop
					if reading != 10:
							value += get_analog_value(0)
							reading += 1
					else:
							t = datetime.datetime.now()
							temp = convert_temp_f(get_temp_c((value / 10.0)))
							# My TMP35 sensor is broken :-(
							print t
							print temp + 12.0
							#graph_temp(t, temp + 12.0)
							value = 0
							reading = 1
					time.sleep(30)
	except KeyboardInterrupt:
			pass
			# clean up GPIO on CTRL+C exit
	finally:
			print "Cleaning up GPIO..."
			GPIO.cleanup()

if __name__ == "__main__":
    main()
