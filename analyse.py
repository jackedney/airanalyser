from PIL import Image, ImageDraw
from typing import NamedTuple, Deque, Tuple, Dict, Optional
from datetime import datetime
from threading import Thread, Lock
from collections import deque
import matplotlib.pyplot as plt
import numpy as np
import time
import csv

"""
from pms5003 import PMS5003
from sgp30 import SGP30
from scd4x import SCD4X
from luma.oled.device import sh1106
"""

from dev_utils.mock_sensors import (
    MockSGP30 as SGP30,
    MockPMS5003 as PMS5003,
    MockSCD4x as SCD4X,
)

from dev_utils.mock_display import MockSH1106 as SH1106


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
        self.display = SH1106(width=128, height=128, i2c_port=1, rotate=2)
        self.update_interval: float = update_interval
        self.reading_lock: Lock = Lock()
        self.latest_reading: Optional[AirQualityReading] = None
        self.running: bool = False
        self.history: DataHistory = DataHistory()

        self.sgp30: SGP30 = SGP30()
        self.scd41: SCD4X = SCD4X()
        self.pms5003: PMS5003 = PMS5003()

        self.indicators: Dict[str, Dict[str, Tuple[float, float]]] = {
            "co2": {
                "good": (0, 800),
                "warning": (800, 1200),
                "bad": (1200, float("inf")),
            },
            "tvoc": {
                "good": (0, 220),
                "warning": (220, 660),
                "bad": (660, float("inf")),
            },
            "pm2.5": {
                "good": (0, 12),
                "warning": (12, 35),
                "bad": (660, float("inf")),
            },
        }

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

    def _get_status(self, value: float, indicator_type: str) -> str:
        ranges = self.indicators[indicator_type]
        for status, (min_val, max_val) in ranges.items():
            if min_val <= value < max_val:
                return status
        return "bad"

    def _draw_trend_arrow(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        current: float,
        history: Deque,
        threshold: float = 5,
    ) -> None:
        if len(history) < 2:
            return

        recent_avg = sum(list(history)[-5:]) / 5
        if abs(current - recent_avg) < threshold:
            draw.line((x, y, x + 10, y), fill=1)
            draw.line((x + 7, y - 3, x + 10, y), fill=1)
            draw.line((x + 7, y + 3, x + 10, y), fill=1)
        elif current > recent_avg:
            draw.line((x + 5, y - 5, x + 5, y + 5), fill=1)
            draw.line((x + 2, y - 2, x + 5, y - 5), fill=1)
            draw.line((x + 8, y - 2, x + 5, y - 5), fill=1)
        else:
            draw.line((x + 5, y - 5, x + 5, y + 5), fill=1)
            draw.line((x + 2, y + 2, x + 5, y + 5), fill=1)
            draw.line((x + 8, y + 2, x + 5, y + 5), fill=1)

    def _draw_progress_bar(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        width: int,
        value: float,
        max_value: float,
    ) -> None:
        bar_height = 6
        draw.rectangle((x, y, x + width, y + bar_height), outline=1)
        fill_width = int((min(value, max_value) / max_value) * width)
        draw.rectangle((x + 1, y + 1, x + fill_width - 1, y + bar_height - 1), fill=1)

    def _draw_temp_humidity(
        self, draw: ImageDraw.ImageDraw, reading: AirQualityReading
    ) -> None:
        draw.text((2, 2), "Environment", fill=1)

        draw.text((2, 20), f"{reading.temperature:.1f}°C", fill=1)
        self._draw_trend_arrow(
            draw, 60, 25, reading.temperature, self.history.temperature
        )
        self._draw_progress_bar(draw, 2, 35, 124, reading.temperature, 40)

        draw.text((2, 45), f"{reading.humidity:.1f}%RH", fill=1)
        self._draw_trend_arrow(draw, 60, 50, reading.humidity, self.history.humidity)
        self._draw_progress_bar(draw, 2, 60, 124, reading.humidity, 100)

    def _draw_co2(self, draw: ImageDraw.ImageDraw, reading: AirQualityReading) -> None:
        status = self._get_status(reading.co2, "co2")

        draw.text((2, 2), "CO2 Levels", fill=1)
        draw.text((2, 20), f"{reading.co2} ppm", fill=1)

        if status == "bad":
            draw.text((2, 40), "VENTILATE!", fill=1)

        self._draw_trend_arrow(draw, 90, 25, reading.co2, self.history.co2)
        self._draw_progress_bar(draw, 2, 60, 124, min(reading.co2, 2000), 2000)

    def _draw_voc(self, draw: ImageDraw.ImageDraw, reading: AirQualityReading) -> None:
        status = self._get_status(reading.tvoc, "tvoc")

        draw.text((2, 2), "Air Quality", fill=1)
        draw.text((2, 20), f"TVOC: {reading.tvoc} ppb", fill=1)
        self._draw_trend_arrow(draw, 90, 25, reading.tvoc, self.history.tvoc)

        if status == "bad":
            draw.text((2, 40), "VENTILATE!", fill=1)

        draw.text((2, 40), f"eCO2: {reading.eco2} ppm", fill=1)
        self._draw_trend_arrow(draw, 90, 45, reading.eco2, self.history.eco2)

        self._draw_progress_bar(draw, 2, 60, 124, min(reading.tvoc, 1000), 1000)

    def _draw_pms(self, draw: ImageDraw.ImageDraw, reading: AirQualityReading) -> None:
        status = self._get_status(reading.pm25, "pm2.5")

        draw.text((2, 1), "Particulates", fill=1)
        draw.text((2, 15), f"PM2.5: {reading.pm25:.1f}", fill=1)
        self._draw_trend_arrow(draw, 90, 20, reading.pm25, self.history.pm25)

        if status == "bad":
            draw.text((2, 30), "VENTILATE!", fill=1)

        draw.text((2, 35), f"PM10: {reading.pm100:.1f}", fill=1)
        self._draw_trend_arrow(draw, 90, 40, reading.pm100, self.history.pm100)
        self._draw_progress_bar(draw, 2, 45, 124, min(reading.pm25, 50), 50)

    def _update_display(self, reading: AirQualityReading) -> None:
        page = int(time.time() / 4) % 4

        image = Image.new("1", (self.display.width, self.display.height), 0)
        draw = ImageDraw.Draw(image)

        time_str = datetime.fromtimestamp(reading.timestamp).strftime("%H:%M")
        draw.text((80, 2), time_str, fill=1)

        if page == 0:
            self._draw_temp_humidity(draw, reading)
        elif page == 1:
            self._draw_co2(draw, reading)
        elif page == 2:
            self._draw_voc(draw, reading)
        else:
            self._draw_pms(draw, reading)

        self.display.display(image)

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
                    self._update_display(reading)

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
                    pm10=pms_data.pm_ug_per_m3[0],
                    pm25=pms_data.pm_ug_per_m3[1],
                    pm100=pms_data.pm_ug_per_m3[2],
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
    try:
        monitor = AirQualityMonitor()
        monitor.start()

        plt.ion()

        while True:
            with monitor.reading_lock:
                reading = monitor.latest_reading

            if reading:
                print("\033[2J\033[H")
                print(
                    f"Air Quality Monitor - {datetime.fromtimestamp(reading.timestamp)}"
                )
                print("-" * 50)
                print(f"Temperature: {reading.temperature:.1f}°C")
                print(f"Humidity: {reading.humidity:.1f}%")
                print(f"CO2: {reading.co2} ppm")
                print(f"TVOC: {reading.tvoc} ppb")
                print(f"eCO2: {reading.eco2} ppm")

            time.sleep(1)

    except KeyboardInterrupt:
        monitor.stop()
        print(f"\nMonitoring stopped. Data saved to: {monitor.history.csv_file}")
