import serial
import time
import json
import paho.mqtt.client as mqtt

PORT = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A5069RR4-if00-port0"
BROKER = "127.0.0.1"
MQTT_PORT = 1883
TOPIC = "anern_inverter/state"
COMMAND = b"QPIGS\xb7\xa9\r"

client = mqtt.Client()
client.connect_async(BROKER, MQTT_PORT, 60)
client.loop_start()

while True:
    try:
        # Отримуємо відповідь інвертора
        with serial.Serial(PORT, 2400, timeout=3) as ser:
            ser.reset_input_buffer()
            ser.write(COMMAND)
            time.sleep(0.5)
            response = ser.read_until(b"\r")

        # Перевіряємо початок відповіді
        start = response.find(b"(")
        if start < 0:
            raise ValueError("Немає початку відповіді QPIGS")

        fields = response[start + 1:].decode(
            "latin-1", errors="ignore"
        ).split()

        # Для наших сенсорів необхідні поля c[0] ... c[19]
        if len(fields) < 20:
            raise ValueError(
                f"Недостатньо полів QPIGS: {len(fields)}"
            )

        c = fields

        # Основні вимірювання
        ac_v = float(c[0])
        out_v = float(c[2])
        out_w = float(c[5])
        battery_v = float(c[8])
        pv_v = float(c[13])

        # Підтверджені за вимірюваннями поля
        battery_charge = int(c[9])
        battery_discharge = int(c[15])
        pv_power = int(c[19])

        # Розрахунковий струм PV, не пряме показання дисплея
        pv_current = round(pv_power / pv_v, 2) if pv_v > 0 else 0.0

        data = {
            "ac_input_voltage": ac_v,
            "ac_input_frequency": float(c[1]),
            "ac_output_voltage": out_v,
            "ac_output_frequency": float(c[3]),

            "output_apparent_power": int(c[4]),
            "output_active_power": int(c[5]),
            "ac_output_current": round(out_w / out_v, 2) if out_v > 0 else 0.0,
            "output_load_percent": int(c[6]),

            "bus_voltage": int(c[7]),
            "battery_voltage": battery_v,
            "battery_charge_current": battery_charge,
            "battery_capacity": int(c[10]),
            "temperature": int(c[11]),

            "pv_input_current": pv_current,
            "pv_input_voltage": pv_v,
            "battery_voltage_scc": float(c[14]),
            "battery_discharge_current": battery_discharge,

            "device_status": c[16],
            "pv_input_power": pv_power
        }

        # Публікуємо дані MQTT
        info = client.publish(
            TOPIC,
            json.dumps(data),
            retain=True
        )

        print(
            f"[OK] PV={pv_power} W, "
            f"Battery charge={battery_charge} A, "
            f"Battery discharge={battery_discharge} A"
        )

    except Exception as error:
        print("[LOOP ERR]", error)

    time.sleep(5)
