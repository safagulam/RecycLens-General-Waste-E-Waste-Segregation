
#include <Servo.h>
#include <Stepper.h>

// ===== SERVO =====
Servo pushServo;
int servoPin = 9;

// ===== STEPPER =====
const int stepsPerRevolution = 2048;   // 28BYJ-48
Stepper myStepper(stepsPerRevolution, 8, 10, 9, 11);

// Positions
int currentPos = 0;

void setup() {
  Serial.begin(9600);

  // Servo setup
  pushServo.attach(6);
  pushServo.write(0);

  // Stepper setup
  myStepper.setSpeed(10);

  Serial.println("System Ready");
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read();

    if (cmd == '1') {
      rotateTo(0);      // E-Waste
      pushWaste();
    }
    else if (cmd == '2') {
      rotateTo(90);    // Bio
      pushWaste();
    }
    else if (cmd == '3') {
      rotateTo(180);    // Non-Bio
      pushWaste();
    }
     else if (cmd == '4') {
      rotateTo(270);    // Non-Bio
      pushWaste();
    }
  }
}

void rotateTo(int targetAngle) {
  int stepMove = map(targetAngle - currentPos, -360, 360, -stepsPerRevolution, stepsPerRevolution);

  myStepper.step(stepMove);

  currentPos = targetAngle;

  delay(500);
}

void pushWaste() {
  pushServo.write(180);   // Push down
  delay(1000);

  pushServo.write(0);    // Back
  delay(1000);
}