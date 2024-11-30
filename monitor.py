from typing import NamedTuple, Deque, Optional
from datetime import datetime
from threading import Thread, Lock
from collections import deque
import numpy as np
import time
import csv

from pms5003 import PMS5003
from sgp30 import SGP30
from scd4x import SCD4X
from luma.oled.device import sh1106
from display import DisplayManager


class AirQualityReading(NamedTuple):
    temperature: float
    humidity: float
    co2: int
    tvoc: int
    eco2: int
    pm10: float
    pm25: float
    pm100: float
    timestamp: float


class DataHistory:
    def __init__(self, max_history: int = 3600) -> None:
        self.max_history: int = max_history
        self.temperature: Deque[float] = deque(maxlen=max_history)
        self.humidity: Deque[float] = deque(maxlen=max_history)
        self.co2: Deque[int] = deque(maxlen=max_history)
        self.tvoc: Deque[int] = deque(maxlen=max_history)
        self.eco2: Deque[int] = deque(maxlen=max_history)
        self.pm10: Deque[float] = deque(maxlen=max_history)
        self.pm25: Deque[float] = deque(maxlen=max_history)
        self.pm100: Deque[float] = deque(maxlen=max_history)
        self.timestamps: Deque[float] = deque(maxlen=max_history)

        self.csv_file: str = (
            f"air_quality_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        self._init_csv()

    def _init_csv(self) -> None:
        with open(self.csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "temperature",
                    "humidity",
                    "co2",
                    "tvoc",
                    "eco2",
                    "pm10",
                    "pm25",
                    "pm100",
                ]
            )

    def add_reading(self, reading: AirQualityReading) -> None:
        self.temperature.append(reading.temperature)
        self.humidity.append(reading.humidity)
        self.co2.append(reading.co2)
        self.tvoc.append(reading.tvoc)
        self.eco2.append(reading.eco2)
        self.pm10.append(reading.pm10)
        self.pm25.append(reading.pm25)
        self.pm100.append(reading.pm100)
        self.timestamps.append(reading.timestamp)

        with open(self.csv_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    datetime.fromtimestamp(reading.timestamp),
                    reading.temperature,
                    reading.humidity,
                    reading.co2,
                    reading.tvoc,
                    reading.eco2,
                    reading.pm10,
                    reading.pm25,
                    reading.pm100,
                ]
            )


class AirQualityMonitor:
    def __init__(self, update_interval: float = 1.0) -> None:
        self.update_interval: float = update_interval
        self.reading_lock: Lock = Lock()
        self.latest_reading: Optional[AirQualityReading] = None
        self.running: bool = False
        self.history: DataHistory = DataHistory()

        # Initialize sensors
        self.sgp30: SGP30 = SGP30()
        self.scd41: SCD4X = SCD4X()
        self.pms5003: PMS5003 = PMS5003()

        # Initialize display
        oled = sh1106(width=128, height=128, i2c_port=1, rotate=2)
        self.display = DisplayManager(oled)

        self.sgp30.start_measurement()
        self.scd41.start_periodic_measurement()

    def start(self) -> None:
        self.running = True
        self.monitor_thread = Thread(target=self._monitoring_loop, daemon=True)
        self.display_thread = Thread(target=self._display_loop, daemon=True)
        self.monitor_thread.start()
        self.display_thread.start()

    def stop(self) -> None:
        self.running = False
        self.monitor_thread.join()
        self.display_thread.join()
        self.scd41.stop_periodic_measurement()

    def _calculate_absolute_humidity(
        self, temperature: float, relative_humidity: float
    ) -> int:
        temp_k = temperature + 273.15
        pvs = 6.112 * np.exp((17.62 * temperature) / (243.12 + temperature))
        abs_humidity = (relative_humidity * pvs * 2.1674) / temp_k
        return int(abs_humidity * 256)

    def _display_loop(self) -> None:
        while self.running:
            try:
                with self.reading_lock:
                    reading = self.latest_reading

                if reading:
                    self.display.update(reading)

                time.sleep(0.1)

            except Exception as e:
                print(f"Display error: {e}")
                time.sleep(1)

    def _monitoring_loop(self) -> None:
        while self.running:
            try:
                air_quality = self.sgp30.get_air_quality()
                results = self.scd41.measure()
                pms_data = self.pms5003.read()

                if results is None:
                    raise ValueError("No results from SCD41")

                co2, temp, humidity, timestamp = results

                abs_humidity = self._calculate_absolute_humidity(temp, humidity)
                self.sgp30.command("set_humidity", [abs_humidity])

                reading = AirQualityReading(
                    temperature=temp,
                    humidity=humidity,
                    co2=co2,
                    tvoc=air_quality.total_voc,
                    eco2=air_quality.equivalent_co2,
                    pm10=pms_data.pm_ug_per_m3(1.0),
                    pm25=pms_data.pm_ug_per_m3(2.5),
                    pm100=pms_data.pm_ug_per_m3(10),
                    timestamp=timestamp,
                )

                with self.reading_lock:
                    self.latest_reading = reading
                    self.history.add_reading(reading)

                time.sleep(self.update_interval)

            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(1)


if __name__ == "__main__":
    monitor = AirQualityMonitor()
    monitor.start()

    try:
        while True:
            with monitor.reading_lock:
                reading = monitor.latest_reading

            if reading:
                print("\033[2J\033[H")  # Clear terminal
                print(
                    f"Air Quality Monitor - {datetime.fromtimestamp(reading.timestamp)}"
                )
                print("-" * 50)
                print(f"Temperature: {reading.temperature:.1f}°C")
                print(f"Humidity: {reading.humidity:.1f}%")
                print(f"CO2: {reading.co2} ppm")
                print(f"TVOC: {reading.tvoc} ppb")
                print(f"eCO2: {reading.eco2} ppm")
                print(f"PM1.0: {reading.pm10} µg/m³")
                print(f"PM2.5: {reading.pm25} µg/m³")
                print(f"PM10: {reading.pm100} µg/m³")

            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        monitor.stop()

