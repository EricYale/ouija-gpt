#include <ESP32Servo.h>
#include <Stepper.h>

#define SERVO_PIN 25
#define STEPPER_PIN_1 12
#define STEPPER_PIN_2 14
#define STEPPER_PIN_3 27
#define STEPPER_PIN_4 26

#define SERVO_POS_MAYBE 105
#define SERVO_POS_NO 210
#define SERVO_POS_YES 0

#define STATE_LISTENING 'l'
#define STATE_THINKING 't'
#define STATE_STOPPED 's'

Stepper myStepper(2048, STEPPER_PIN_1, STEPPER_PIN_2, STEPPER_PIN_3, STEPPER_PIN_4);
Servo servo;

char spinnerState = STATE_STOPPED;

void setup() {
  Serial.begin(115200);
  myStepper.setSpeed(5);
  servo.attach(SERVO_PIN);
  servo.write(SERVO_POS_NO);
}

void loop() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    handleCommand(command);
  }

  runSpinner();
}

void handleCommand(char command) {
  switch (command) {
    case 'y':
      servo.write(SERVO_POS_YES);
      spinnerState = STATE_LISTENING;
      break;
    case 'n':
      servo.write(SERVO_POS_NO);
      spinnerState = STATE_LISTENING;
      break;
    case 'm':
      servo.write(SERVO_POS_MAYBE);
      spinnerState = STATE_LISTENING;
      break;
    case 'l':
      spinnerState = STATE_LISTENING;
      break;
    case 't':
      spinnerState = STATE_THINKING;
      break;
    case 's':
      spinnerState = STATE_STOPPED;
      break;
  }
}

void runSpinner() {
  switch (spinnerState) {
    case STATE_LISTENING:
      myStepper.setSpeed(5);
      myStepper.step(-10);
      break;
    case STATE_THINKING:
      myStepper.setSpeed(10);
      myStepper.step(-10);
      break;
    case STATE_STOPPED:
      // Do nothing
      break;
  }
  delay(10);
}
