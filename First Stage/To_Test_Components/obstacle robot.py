#Include the library files
from machine import Pin,PWM
import time

servo = PWM(Pin(0))#Include the servo motor pin
servo.freq(50)#Set the frequency

Trig = Pin(2,Pin.OUT)#Include the Trig pin
Echo = Pin(3,Pin.IN)#Include the Echo pin

#Motor driver pins
ENA = PWM(Pin(4))
IN1 = Pin(5,Pin.OUT)
IN2 = Pin(6,Pin.OUT)
IN3 = Pin(7,Pin.OUT)
IN4 = Pin(8,Pin.OUT)
ENB = PWM(Pin(9))

ENA.freq(1000)
ENB.freq(1000)

speed = 30000 #Speed of this robot

def forward():
    ENA.duty_u16(speed)
    IN1.value(0)
    IN2.value(1)
    ENB.duty_u16(speed)
    IN3.value(1)
    IN4.value(0)
    
def backward():
    ENA.duty_u16(speed)
    IN1.value(1)
    IN2.value(0)
    ENB.duty_u16(speed)
    IN3.value(0)
    IN4.value(1)
    
def left():
    ENA.duty_u16(speed)
    IN1.value(1)
    IN2.value(0)
    ENB.duty_u16(speed)
    IN3.value(1)
    IN4.value(0)
    
def right():
    ENA.duty_u16(speed)
    IN1.value(0)
    IN2.value(1)
    ENB.duty_u16(speed)
    IN3.value(0)
    IN4.value(1)

def stop():
    ENA.duty_u16(0)
    IN1.value(0)
    IN2.value(0)
    ENB.duty_u16(0)
    IN3.value(0)
    IN4.value(0)
    
#Get the distance
def distance():
    Trig.value(0)
    time.sleep_us(4)
    Trig.value(1)
    time.sleep_us(10)
    Trig.value(0)
      
    while Echo.value() == 0:
       low = time.ticks_us()
       
    while Echo.value() == 1:
       high = time.ticks_us()
       
    t = high - low
    cm = t/29/2#Time convert to the cm
#     time.sleep(0.1)
    return cm

def servoLeft():
    servo.duty_u16(7000) #1500-8500
    
def servoRight():
    servo.duty_u16(3000) #1500-8500
    
def servoStart():
    servo.duty_u16(5400) #1500-8500

while True:
    dis = distance()
    if(dis<10):
        stop()
        time.sleep(1)
        servoLeft()
        time.sleep(1)
        leftDis = distance()
        time.sleep(0.5)
        print(leftDis)
        servoStart()
        time.sleep(1)
        servoRight()
        time.sleep(1)
        rightDis = distance()
        time.sleep(0.5)
        print(rightDis)
        servoStart()
        time.sleep(1)
        if(leftDis > rightDis):
            print("Turn Left")
            left()            
            time.sleep(0.5)
            stop()
            time.sleep(1)
        elif(leftDis < rightDis):
            print("Turn Right")
            right()
            time.sleep(0.5)
            stop()
            time.sleep(1)
    else:
        leftDis = 0
        rightDis = 0
        forward()
        
                

