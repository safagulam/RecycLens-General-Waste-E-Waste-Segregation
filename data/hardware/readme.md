
## Overview

This project is an automatic object sorting system using Arduino, a conveyor belt, and a camera. It detects objects, classifies them, and sorts them into different positions.

---

## Hardware Used

* Arduino Uno (2)
* IR Sensor
* Conveyor Belt + Motor Driver
* Stepper Motor
* Servo Motor
* Webcam
* Power Supply

---

## Working

1. Conveyor moves the object
2. IR sensor detects object and stops conveyor
3. Camera captures image
4. Python model classifies object
5. Stepper rotates to position
6. Servo pushes object
7. Conveyor starts again

---

## Setup

* Connect components as per circuit
* Upload Arduino code
* Run Python code
* Place object on conveyor

---

## Note

* Use external power for motors
* Do not keep motors directly on Arduino power

---

