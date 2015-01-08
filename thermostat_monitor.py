import RPi.GPIO as GPIO
import datetime
import time

def cb_therm_status(channel):
        print str(datetime.datetime.now())
        if GPIO.input(channel):
                print "Rising edge detected. Looks like the heating turned OFF."
        else:
                print "Falling edge detected. Looks like the heating turned ON."

try:
	HCPL3700 = 11
	GPIO.setmode(GPIO.BOARD)
	GPIO.setup(HCPL3700, GPIO.IN, pull_up_down=GPIO.PUD_UP)
	
	print str(datetime.datetime.now())
	print "Monitoring the thermostat with the HCPL3700..."
	
	# Initially just poll once to get the status of the line
	print "Getting initial status:"
	cb_therm_status(HCPL3700)
	
	GPIO.add_event_detect(HCPL3700, GPIO.BOTH, callback=cb_therm_status, bouncetime=100)
	
	while True:
		# Event detection should take place in this never-ending loop
		print "Sleeping..."
		time.sleep(60)
except KeyboardInterrupt:
	pass
	# clean up GPIO on CTRL+C exit
finally:
	print "Cleaning up GPIO..."
	GPIO.cleanup()
