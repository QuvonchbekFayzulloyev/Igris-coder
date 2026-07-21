---
name: hardware-robotics
description: Governs hardware and robotics engineering tasks: microcontroller programming, circuit design, sensor integration, motor control, ROS2, PCB design, embedded systems.
pipeline_stage: Execution
triggers: [hardware, robotics, microcontroller, arduino, esp32, stm32, raspberry, pi, sensor, motor, servo, stepper, pwm, i2c, spi, uart, gpio, circuit, schematic, pcb, ros2, ros, embedded, firmware, rtos]
defers_to: [ai-ml-engineering]
used_by: [reprompt-loop, skill-loader]
---

## Scope
Applies when the user requests hardware/robotics engineering work:
embedded programming, circuit design, sensor integration, motor control,
or robotic system architecture.

## Procedure
1. **Identify the platform**: Arduino, ESP32, STM32, Raspberry Pi, FPGA
2. **Pin mapping**: document all GPIO assignments, communication buses
3. **Circuit design**: schematics, BOM (Bill of Materials), power requirements
4. **Firmware**: C/C++/MicroPython code with proper timing analysis
5. **Communication protocols**: I2C, SPI, UART, CAN, PWM configuration
6. **Sensor integration**: calibration, filtering (Kalman, complementary)
7. **Motor control**: PID tuning, trajectory planning, safety limits
8. **ROS2 integration**: nodes, topics, services, actions

## Constraints
- Always specify operating voltage and current requirements
- Always include pull-up/pull-down resistors where needed
- Always document watchdog timer configuration
- Always include error handling for sensor read failures
- For motor control, always include emergency stop logic
- PCB designs must include decoupling capacitors near ICs

## Pin Documentation Format
```
Pin | Function | Device | Notes
----|----------|--------|------
D2  | INT      | IMU    | Interrupt pin
D3  | PWM      | Servo  | 50Hz
A4  | SDA      | I2C    | 4.7k pull-up
A5  | SCL      | I2C    | 4.7k pull-up
```

## Anti-patterns
- Using GPIO without checking voltage levels (3.3V vs 5V)
- Missing decoupling capacitors on power pins
- No watchdog timer in production firmware
- Blocking delays in real-time control loops
- Missing current limiting on motor drivers
- Not documenting wire colors and connector pinouts
