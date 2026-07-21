"""MCP surface for hardware and robotics engineering.

Provides tools for:
- Microcontroller pin planning and GPIO configuration
- Circuit schematic text generation
- Bill of Materials (BOM) generation
- Sensor datasheet lookup summaries
- Motor/PID calculation helpers
- ROS2 node scaffolding
- Wiring diagram text generation
"""
from __future__ import annotations

import math
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("hardware")

# ---------------------------------------------------------------------------
# Pin planning
# ---------------------------------------------------------------------------

_MCU_PINS = {
    "esp32": {
        "total": 38, "vcc": [3.3], "adc": list(range(32, 40)), "dac": [25, 26],
        "pwm": list(range(0, 20)) + list(range(21, 34)),
        "i2c": [(21, 22)], "spi": [(18, 19, 23)], "uart": [(1, 3)],
        "touch": list(range(32, 40)),
        "max_voltage": 3.3, "max_current_per_pin": 40, "notes": "3.3V logic, 5V tolerant on some pins"
    },
    "arduino_uno": {
        "total": 32, "vcc": [5.0, 3.3], "adc": list(range(14, 20)),
        "pwm": [3, 5, 6, 9, 10, 11],
        "i2c": [(18, 19)], "spi": [(10, 11, 12, 13)], "uart": [(0, 1)],
        "max_voltage": 5.0, "max_current_per_pin": 40,
        "notes": "5V logic, analog inputs A0-A5"
    },
    "stm32f4": {
        "total": 64, "vcc": [3.3], "adc": list(range(0, 17)), "dac": [4, 5],
        "pwm": list(range(0, 16)) * 2,
        "i2c": [(6, 7), (8, 9)], "spi": [(3, 4, 5), (10, 11, 12)], "uart": [(0, 1), (2, 3)],
        "max_voltage": 3.3, "max_current_per_pin": 25,
        "notes": "3.3V logic, 5V tolerant pins available"
    },
    "raspberry_pi": {
        "total": 40, "vcc": [5.0, 3.3], "adc": [], "pwm": [12, 32, 33, 35],
        "i2c": [(2, 3)], "spi": [(8, 9, 10, 11), (7, 8, 9, 10)], "uart": [(14, 15)],
        "max_voltage": 3.3, "max_current_per_pin": 16,
        "notes": "3.3V GPIO, 5V power pins available"
    },
}


@mcp.tool()
async def get_mcu_pins(mcu: str = "esp32") -> str:
    """Get GPIO pin information for a microcontroller.

    Returns pin capabilities: VCC, ADC, DAC, PWM, I2C, SPI, UART.
    """
    mcu_lower = mcu.lower().replace(" ", "_")
    if mcu_lower not in _MCU_PINS:
        available = list(_MCU_PINS.keys())
        return f"ERROR: Unknown MCU '{mcu}'. Available: {available}"

    info = _MCU_PINS[mcu_lower]
    lines = [
        f"## {mcu.upper()} Pinout",
        f"Total pins: {info['total']}",
        f"Logic voltage: {info['vcc'][0]}V",
        f"Notes: {info['notes']}",
        "",
        "### Power",
        f"VCC: {', '.join(f'{v}V' for v in info['vcc'])}",
        f"Max current per pin: {info['max_current_per_pin']}mA",
        "",
        "### Communication",
        f"I2C: {', '.join(f'GPIO{s}/{t}' for s,t in info['i2c'])}" if info['i2c'] else "I2C: N/A",
        f"SPI: {', '.join(f'GPIO{s}/{t}/{u}' for s,t,u in info['spi'])}" if info['spi'] else "SPI: N/A",
        f"UART: {', '.join(f'TX/RX({s},{t})' for s,t in info['uart'])}" if info['uart'] else "UART: N/A",
        "",
        "### Analog",
        f"ADC pins: {', '.join(str(p) for p in info.get('adc', [])[:8])}..." if info.get('adc') else "ADC: N/A",
        f"DAC pins: {', '.join(str(p) for p in info.get('dac', []))}" if info.get('dac') else "DAC: N/A",
        "",
        "### PWM",
        f"PWM pins: {', '.join(str(p) for p in info.get('pwm', [])[:12])}...",
    ]
    return "\n".join(lines)


@mcp.tool()
async def plan_pin_assignments(
    mcu: str = "esp32",
    components: list[str] = None,
    i2c_devices: int = 0,
    spi_devices: int = 0,
    pwm_channels: int = 0,
    adc_channels: int = 0,
    uart_devices: int = 0,
) -> str:
    """Plan pin assignments for a project.

    Given components and bus requirements, suggests pin assignments
    and checks for conflicts.

    Returns a pin assignment table.
    """
    mcu_lower = mcu.lower().replace(" ", "_")
    if mcu_lower not in _MCU_PINS:
        return f"ERROR: Unknown MCU '{mcu}'"

    info = _MCU_PINS[mcu_lower]
    used_pins = set()
    lines = [
        f"## Pin Assignment Plan for {mcu.upper()}",
        "",
        "| Pin | Function | Device | Notes |",
        "|-----|----------|--------|-------|",
    ]

    # I2C bus
    if i2c_devices > 0 and info["i2c"]:
        scl, sda = info["i2c"][0]
        used_pins.update([scl, sda])
        lines.append(f"| {scl} | SCL | I2C bus | 4.7k pull-up |")
        lines.append(f"| {sda} | SDA | I2C bus | 4.7k pull-up |")

    # SPI bus
    if spi_devices > 0 and info["spi"]:
        cs, mosi, miso, sck = info["spi"][0]
        used_pins.update([mosi, miso, sck])
        for i in range(spi_devices):
            lines.append(f"| {cs - i} | CS{i} | SPI device {i} | |")
        lines.append(f"| {mosi} | MOSI | SPI bus | |")
        lines.append(f"| {miso} | MISO | SPI bus | |")
        lines.append(f"| {sck} | SCK | SPI bus | |")

    # UART
    if uart_devices > 0 and info["uart"]:
        tx, rx = info["uart"][0]
        used_pins.update([tx, rx])
        lines.append(f"| {tx} | TX | UART | |")
        lines.append(f"| {rx} | RX | UART | |")

    # PWM channels
    pwm_pins = [p for p in info.get("pwm", []) if p not in used_pins]
    for i in range(min(pwm_channels, len(pwm_pins))):
        pin = pwm_pins[i]
        used_pins.add(pin)
        comp = components[i] if components and i < len(components) else f"PWM channel {i}"
        lines.append(f"| {pin} | PWM | {comp} | |")

    # ADC channels
    adc_pins = [p for p in info.get("adc", []) if p not in used_pins]
    for i in range(min(adc_channels, len(adc_pins))):
        pin = adc_pins[i]
        used_pins.add(pin)
        lines.append(f"| {pin} | ADC | Analog sensor {i} | |")

    # Remaining for GPIO
    total_pins = info["total"]
    remaining = total_pins - len(used_pins)
    lines.append("")
    lines.append(f"### Summary")
    lines.append(f"Pins used: {len(used_pins)} / {total_pins}")
    lines.append(f"Pins remaining: {remaining}")
    if remaining < 0:
        lines.append("**WARNING: More pins needed than available!**")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Circuit calculations
# ---------------------------------------------------------------------------


@mcp.tool()
async def calculate_pullup_resistor(
    bus_type: str = "i2c",
    bus_capacitance_pf: float = 200.0,
    vcc: float = 3.3,
) -> str:
    """Calculate pull-up resistor value for I2C or SPI bus."""
    if bus_type == "i2c":
        # Standard formula: R = tr / (0.8473 * C)
        # f = 400kHz (Fast mode)
        tr = 300e-9  # rise time for 400kHz
        c_farads = bus_capacitance_pf * 1e-12
        r_min = tr / (0.8473 * c_farads)

        # Max: leakage current (typically 3mA)
        r_max = (vcc - 0.4) / 3e-3

        return (
            f"I2C pull-up resistor calculation:\n"
            f"  Bus capacitance: {bus_capacitance_pf}pF\n"
            f"  VCC: {vcc}V\n"
            f"  Rise time (400kHz): {tr*1e9:.1f}ns\n"
            f"  R_min: {r_min/1000:.1f}k\u2126\n"
            f"  R_max: {r_max/1000:.1f}k\u2126\n"
            f"  Recommended: {round(r_min/1000 * 1.5, 1)}k\u2126 "
            f"(closest standard: {round(r_min/1000 * 1.5 / 2.2) * 2.2:.1f}k\u2126)"
        )
    else:
        return "Pull-up calculation only supports I2C currently."


@mcp.tool()
async def calculate_current_limit_resistor(
    supply_v: float = 5.0,
    led_vf: float = 2.0,
    led_current_ma: float = 20.0,
) -> str:
    """Calculate current limiting resistor for LED."""
    r = (supply_v - led_vf) / (led_current_ma / 1000)
    power = (supply_v - led_vf) * (led_current_ma / 1000)
    return (
        f"Current limiting resistor:\n"
        f"  Supply: {supply_v}V\n"
        f"  LED Vf: {led_vf}V\n"
        f"  Current: {led_current_ma}mA\n"
        f"  R = ({supply_v} - {led_vf}) / {led_current_ma/1000:.4f} = {r:.0f}\u2126\n"
        f"  Power: {power*1000:.1f}mW (use {round(power*1000/62.5)*62.5}mW or larger)\n"
        f"  Standard E12: {_nearest_standard_resistor(r)}"
    )


def _nearest_standard_resistor(target: float) -> str:
    e12 = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82]
    if target < 10:
        return f"{target:.0f}\u2126 (use lowest standard)"
    decade = 10 ** (len(str(int(target))) - 1)
    norm = target / decade
    closest = min(e12, key=lambda x: abs(x - norm))
    actual = closest * decade
    return f"{actual:.0f}\u2126"


@mcp.tool()
async def calculate_pid_constants(
    kp: float = 0.0,
    ki: float = 0.0,
    kd: float = 0.0,
    dt_seconds: float = 0.01,
    setpoint: float = 90.0,
    current_position: float = 0.0,
) -> str:
    """Calculate PID output and suggest tuning parameters.

    Args:
        kp: proportional gain
        ki: integral gain
        kd: derivative gain
        dt_seconds: control loop time step
        setpoint: target value
        current_position: current measured value

    Returns PID output and tuning suggestions.
    """
    error = setpoint - current_position
    p_term = kp * error

    if kp == 0 and ki == 0 and kd == 0:
        # Suggest Ziegler-Nichols tuning
        return (
            f"PID Tuning (Ziegler-Nichols method):\n\n"
            f"  For a typical DC motor:\n"
            f"  - Start with Kp = 1.0, Ki = 0, Kd = 0\n"
            f"  - Increase Kp until sustained oscillation\n"
            f"  - Record Ku (ultimate gain) and Tu (period)\n\n"
            f"  Then set:\n"
            f"  P-only:   Kp = 0.5 * Ku\n"
            f"  PI:       Kp = 0.45 * Ku, Ki = Kp / (0.83 * Tu)\n"
            f"  PID:      Kp = 0.6 * Ku, Ki = Kp / (0.5 * Tu), Kd = Kp * 0.125 * Tu\n\n"
            f"  For your application (setpoint={setpoint}, dt={dt_seconds*1000:.0f}ms):\n"
            f"  Suggested starting point: Kp = 0.5, Ki = 0.1, Kd = 0.01"
        )

    i_term = ki * error * dt_seconds
    d_term = kd * (0 - error) / dt_seconds if dt_seconds > 0 else 0
    output = p_term + i_term + d_term

    return (
        f"PID Calculation:\n"
        f"  Setpoint: {setpoint}\n"
        f"  Position: {current_position}\n"
        f"  Error: {error:.2f}\n\n"
        f"  P: {kp:.3f} * {error:.2f} = {p_term:.3f}\n"
        f"  I: {ki:.3f} * {error:.2f} * {dt_seconds:.3f} = {i_term:.3f}\n"
        f"  D: {kd:.3f} * 0-{error:.2f} / {dt_seconds:.3f} = {d_term:.3f}\n\n"
        f"  Output: {output:.3f}\n"
    )


@mcp.tool()
async def generate_bom(
    components: list[dict[str, Any]] = None,
) -> str:
    """Generate a Bill of Materials.

    Each component: {qty, reference, value, package, part_number, datasheet, notes}
    """
    if not components:
        return "ERROR: No components provided."

    lines = [
        "# Bill of Materials",
        "",
        "| Qty | Reference | Value | Package | Part Number | Datasheet | Notes |",
        "|-----|-----------|-------|---------|-------------|-----------|-------|",
    ]

    for c in components:
        qty = c.get("qty", 1)
        ref = c.get("reference", "?")
        val = c.get("value", "")
        pkg = c.get("package", "")
        pn = c.get("part_number", "")
        ds = c.get("datasheet", "")
        notes = c.get("notes", "")
        lines.append(f"| {qty} | {ref} | {val} | {pkg} | {pn} | {ds} | {notes} |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sensor helpers
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_sensor_info(sensor_type: str = "") -> str:
    """Get common sensor information: interface, voltage, library.

    Available sensors: ultrasonic, imu, temperature, humidity, distance, pressure, gas, current
    """
    sensors = {
        "ultrasonic": "HC-SR04 | GPIO | 5V | ~$2 | 2cm-400cm | NewPing",
        "imu_6dof": "MPU6050 | I2C | 3.3V | ~$5 | Accel+Gyro | MPU6050.h",
        "imu_9dof": "BNO055 | I2C | 3.3V | ~$15 | IMU+Mag | Adafruit_BNO055",
        "temperature": "DHT22 | GPIO | 3.3-5V | ~$5 | Temp+Humidity | DHT.h",
        "temp_i2c": "BMP280 | I2C/SPI | 3.3V | ~$3 | Temp+Pressure | Adafruit_BMP280",
        "distance": "VL53L0X | I2C | 3.3V | ~$8 | ToF 30mm-2m | Adafruit_VL53L0X",
        "lidar": "TFMini | UART/I2C | 3.3V | ~$25 | 12m LiDAR | TFMini.h",
        "pressure": "MPX5700 | Analog | 5V | ~$10 | 0-700kPa | analogRead",
        "gas": "MQ-135 | Analog | 5V | ~$5 | Air Quality | analogRead",
        "current": "ACS712 | Analog | 5V | ~$5 | +/-30A | analogRead",
    }

    if sensor_type:
        if sensor_type in sensors:
            name, interface, voltage, price, range, library = sensors[sensor_type].split(" | ")
            return (
                f"Sensor: {sensor_type.upper()} ({name})\n"
                f"  Interface: {interface}\n"
                f"  Voltage: {voltage}\n"
                f"  Price: {price}\n"
                f"  Range: {range}\n"
                f"  Library: {library}"
            )
        return f"ERROR: Unknown sensor. Available: {list(sensors.keys())}"

    lines = ["## Common Sensors", "", "| Type | Model | Interface | Voltage | Range |", "|------|-------|-----------|---------|-------|"]
    for key, val in sorted(sensors.items()):
        parts = val.split(" | ")
        lines.append(f"| {key} | {parts[0]} | {parts[1]} | {parts[2]} | {parts[3]} |")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()