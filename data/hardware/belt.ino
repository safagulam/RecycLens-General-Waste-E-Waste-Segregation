// Motor Driver Pins
#define IN1 2
#define IN2 3
#define IN3 4
#define IN4 9
#define ENA 5
#define ENB 6

// IR Sensor
#define IR_SENSOR 8

int speedValue = 60;  // Adjust speed (0–255)

void setup() {
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  pinMode(ENA, OUTPUT);
  pinMode(ENB, OUTPUT);

  pinMode(IR_SENSOR, INPUT);

  Serial.begin(9600);
}

void loop() {
  int sensorState = digitalRead(IR_SENSOR);

  Serial.print("Sensor: ");
  Serial.println(sensorState);

  // MOST IR sensors → LOW when object detected
  if (sensorState == LOW) {
    stopMotors();   // Stop if object detected
  } 
  else {
    runConveyor();  // Run if no object
  }
}

// Function to RUN conveyor
void runConveyor() {
  // Motor A (2 motors)
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);

  // Motor B (2 motors opposite direction)
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);

  analogWrite(ENA, speedValue);
  analogWrite(ENB, speedValue);
}

// Function to STOP conveyor
void stopMotors() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);

  analogWrite(ENA, 0);
  analogWrite(ENB, 0);
}