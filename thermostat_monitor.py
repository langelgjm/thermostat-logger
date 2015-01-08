import RPi.GPIO as GPIO 
import datetime
GPIO.setmode(GPIO.BOARD)  
  
GPIO.setup(11, GPIO.IN, pull_up_down=GPIO.PUD_UP)  
print "Monitoring the thermostat through the HCPL3700...\n"
print str(datetime.datetime.now())
while True:
	try:  
		GPIO.wait_for_edge(11, GPIO.FALLING)  
		print str(datetime.datetime.now())
		print "\nFalling edge detected."  
		print " Looks like the heating turned on!"
		GPIO.wait_for_edge(11, GPIO.RISING)
		print str(datetime.datetime.now())
		print "\nRising edge detected."  
		print " Looks like the heating turned off!"
	except KeyboardInterrupt:  
		GPIO.cleanup()       # clean up GPIO on CTRL+C exit  
		print "\n"
GPIO.cleanup()           # clean up GPIO on normal exit  
