from PIL import ImageDraw, Image
import numpy as np
from threading import Thread
from typing import NamedTuple, Deque
from datetime import datetime
from threading import Lock
from collections import deque
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import time
import csv

# Try to import hardware dependencies, fall back to mock implementations for development
from pms5003 import PMS5003
from sgp30 import SGP30
from scd4x import SCD4X
from luma.oled.device import sh1106
from luma.core.interface.serial import i2c

USING_HARDWARE = True

print("Running with", "hardware" if USING_HARDWARE else "mock", "sensors")


class AirQualityReading(NamedTuple):
    """Data structure for air quality sensor readings"""

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
    """Manages historical sensor data and CSV logging"""

    def __init__(self, max_history: int = 3600):
        self.max_history = max_history
        self.temperature = deque(maxlen=max_history)
        self.humidity = deque(maxlen=max_history)
        self.co2 = deque(maxlen=max_history)
        self.tvoc = deque(maxlen=max_history)
        self.eco2 = deque(maxlen=max_history)
        self.pm10 = deque(maxlen=max_history)
        self.pm25 = deque(maxlen=max_history)
        self.pm100 = deque(maxlen=max_history)
        self.timestamps = deque(maxlen=max_history)

        self.csv_file = f"air_quality_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._init_csv()

    def _init_csv(self) -> None:
        """Initialize CSV file with headers"""
        headers = [
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
        with open(self.csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    def add_reading(self, reading: AirQualityReading) -> None:
        """Add a new reading to history and CSV file"""
        # Update deques
        self.temperature.append(reading.temperature)
        self.humidity.append(reading.humidity)
        self.co2.append(reading.co2)
        self.tvoc.append(reading.tvoc)
        self.eco2.append(reading.eco2)
        self.pm10.append(reading.pm10)
        self.pm25.append(reading.pm25)
        self.pm100.append(reading.pm100)
        self.timestamps.append(reading.timestamp)

        # Write to CSV
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
    """Main class for air quality monitoring system"""

    def __init__(self, update_interval: float = 1.0):
        # Initialize display
        try:
            serial = i2c(port=1)
            self.display = sh1106(
                serial_interface=serial, width=128, height=64, rotate=0
            )
            self.display.clear()
            self.display.show()
            print("Display initialized successfully")
        except Exception as e:
            print(f"Display initialization error: {e}")
            raise

        # Initialize other components
        self.update_interval = update_interval
        self.reading_lock = Lock()
        self.latest_reading = None
        self.running = False
        self.history = DataHistory()

        # Initialize sensors
        try:
            self.sgp30 = SGP30()
            self.scd41 = SCD4X()
            self.pms5003 = PMS5003()
            print("Sensors initialized successfully")
        except Exception as e:
            print(f"Sensor initialization error: {e}")
            raise

        # Define air quality thresholds
        self.indicators = {
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
            "pm25": {
                "good": (0, 12),
                "warning": (12, 35),
                "bad": (35, float("inf")),
            },
        }

        self.sgp30.start_measurement()
        print("SGP30 measurement started")

    def _calculate_absolute_humidity(
        self, temperature: float, relative_humidity: float
    ) -> int:
        """Calculate absolute humidity for SGP30 compensation"""
        temp_k = temperature + 273.15
        pvs = 6.112 * np.exp((17.62 * temperature) / (243.12 + temperature))
        abs_humidity = (relative_humidity * pvs * 2.1674) / temp_k
        return int(abs_humidity * 256)

    def _get_status(self, value: float, indicator_type: str) -> str:
        """Determine air quality status based on thresholds"""
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
        """Draw trend arrow indicating value change direction"""
        if len(history) < 2:
            return

        recent_avg = sum(list(history)[-5:]) / 5
        if abs(current - recent_avg) < threshold:
            # Horizontal arrow
            draw.line((x, y, x + 10, y), fill=1)
            draw.line((x + 7, y - 3, x + 10, y), fill=1)
            draw.line((x + 7, y + 3, x + 10, y), fill=1)
        elif current > recent_avg:
            # Up arrow
            draw.line((x + 5, y - 5, x + 5, y + 5), fill=1)
            draw.line((x + 2, y - 2, x + 5, y - 5), fill=1)
            draw.line((x + 8, y - 2, x + 5, y - 5), fill=1)
        else:
            # Down arrow
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
        """Draw progress bar with current value"""
        bar_height = 4
        draw.rectangle((x, y, x + width, y + bar_height), outline=1)
        fill_width = int((min(value, max_value) / max_value) * width)
        if fill_width > 0:
            draw.rectangle(
                (x + 1, y + 1, x + fill_width - 1, y + bar_height - 1), fill=1
            )

    def _draw_temp_humidity(
        self, draw: ImageDraw.ImageDraw, reading: AirQualityReading
    ) -> None:
        """Draw temperature and humidity page"""
        draw.text((2, 1), "Environment", fill=1)

        # Temperature
        draw.text((2, 15), f"{reading.temperature:.1f}°C", fill=1)
        self._draw_trend_arrow(
            draw, 60, 20, reading.temperature, self.history.temperature
        )
        self._draw_progress_bar(draw, 2, 25, 124, reading.temperature, 40)

        # Humidity
        draw.text((2, 35), f"{reading.humidity:.1f}%RH", fill=1)
        self._draw_trend_arrow(draw, 60, 40, reading.humidity, self.history.humidity)
        self._draw_progress_bar(draw, 2, 45, 124, reading.humidity, 100)

    def _draw_co2(self, draw: ImageDraw.ImageDraw, reading: AirQualityReading) -> None:
        """Draw CO2 levels page"""
        status = self._get_status(reading.co2, "co2")

        draw.text((2, 1), "CO2 Levels", fill=1)
        draw.text((2, 15), f"{reading.co2} ppm", fill=1)

        if status == "bad":
            draw.text((2, 30), "VENTILATE!", fill=1)

        self._draw_trend_arrow(draw, 90, 20, reading.co2, self.history.co2)
        self._draw_progress_bar(draw, 2, 45, 124, min(reading.co2, 2000), 2000)

    def _draw_voc(self, draw: ImageDraw.ImageDraw, reading: AirQualityReading) -> None:
        """Draw VOC levels page"""
        status = self._get_status(reading.tvoc, "tvoc")

        draw.text((2, 1), "Air Quality", fill=1)
        draw.text((2, 15), f"TVOC: {reading.tvoc} ppb", fill=1)
        self._draw_trend_arrow(draw, 90, 20, reading.tvoc, self.history.tvoc)

        if status == "bad":
            draw.text((2, 30), "VENTILATE!", fill=1)

        draw.text((2, 35), f"eCO2: {reading.eco2} ppm", fill=1)
        self._draw_trend_arrow(draw, 90, 40, reading.eco2, self.history.eco2)
        self._draw_progress_bar(draw, 2, 45, 124, min(reading.tvoc, 1000), 1000)

    def _draw_pm(self, draw: ImageDraw.ImageDraw, reading: AirQualityReading) -> None:
        """Draw particulate matter page"""
        status = self._get_status(reading.pm25, "pm25")

        draw.text((2, 1), "Particulate", fill=1)
        draw.text((2, 15), f"PM2.5: {reading.pm25:.1f}", fill=1)
        self._draw_trend_arrow(draw, 90, 20, reading.pm25, self.history.pm25)

        if status == "bad":
            draw.text((2, 30), "VENTILATE!", fill=1)

        draw.text((2, 35), f"PM10: {reading.pm100:.1f}", fill=1)
        self._draw_trend_arrow(draw, 90, 40, reading.pm100, self.history.pm100)
        self._draw_progress_bar(draw, 2, 45, 124, min(reading.pm25, 50), 50)

    def _display_loop(self) -> None:
        """Main display update loop"""
        while self.running:
            try:
                with self.reading_lock:
                    reading = self.latest_reading

                if reading:
                    # Create new image
                    image = Image.new("1", (self.display.width, self.display.height), 0)
                    draw = ImageDraw.Draw(image)

                    # Draw time
                    time_str = datetime.fromtimestamp(reading.timestamp).strftime(
                        "%H:%M"
                    )
                    draw.text((80, 1), time_str, fill=1)

                    # Rotate through pages every 6 seconds
                    page = int(time.time() / 6) % 4
                    if page == 0:
                        self._draw_temp_humidity(draw, reading)
                    elif page == 1:
                        self._draw_co2(draw, reading)
                    elif page == 2:
                        self._draw_voc(draw, reading)
                    else:
                        self._draw_pm(draw, reading)

                    # Update display
                    try:
                        self.display.display(image)
                    except Exception as e:
                        print(f"Display update error: {e}")

                time.sleep(0.1)

            except Exception as e:
                print(f"Display loop error: {e}")
                time.sleep(1)

    def _monitoring_loop(self) -> None:
        """Main sensor monitoring loop"""
        while self.running:
            try:
                # Get readings from all sensors
                air_quality = self.sgp30.get_air_quality()
                results = self.scd41.measure()
                pms_data = self.pms5003.read()

                if results is None:
                    raise ValueError("No results from SCD41")

                co2, temp, humidity, timestamp = results

                # Update SGP30 humidity compensation
                abs_humidity = self._calculate_absolute_humidity(temp, humidity)
                self.sgp30.command("set_humidity", [abs_humidity])

                # Create reading
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

                # Update latest reading and history
                with self.reading_lock:
                    self.latest_reading = reading
                    self.history.add_reading(reading)

                time.sleep(self.update_interval)

            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(1)
                try:
                    self.scd41.start_periodic_measurement()
                except Exception as e:
                    print(f"Error restarting SCD41: {e}")

    def start(self) -> None:
        """Start monitoring threads"""
        self.running = True
        self.monitor_thread = Thread(target=self._monitoring_loop, daemon=True)
        self.display_thread = Thread(target=self._display_loop, daemon=True)

        print("Starting monitoring thread...")
        self.monitor_thread.start()
        print("Starting display thread...")
        self.display_thread.start()
        print("Monitor started successfully")

    def stop(self) -> None:
        """Stop monitoring threads"""
        print("Stopping monitor...")
        self.running = False
        if hasattr(self, "monitor_thread"):
            self.monitor_thread.join()
        if hasattr(self, "display_thread"):
            self.display_thread.join()
        try:
            self.scd41.stop_periodic_measurement()
            print("Stopped SCD41 measurement")
        except Exception as e:
            print(f"Error stopping SCD41: {e}")
        print("Monitor stopped")


def create_plots(history: DataHistory) -> Figure:
    """Create matplotlib figure with air quality trends"""
    plt.style.use("dark_background")
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("Air Quality Trends")

    # Convert timestamps to datetime objects
    times = [datetime.fromtimestamp(t) for t in history.timestamps]

    # Temperature and Humidity plot
    ax1.plot(times, history.temperature, "r-", label="Temperature (°C)")
    ax1_twin = ax1.twinx()
    ax1_twin.plot(times, history.humidity, "b-", label="Humidity (%)")
    ax1.set_title("Temperature & Humidity")
    ax1.legend(loc="upper left")
    ax1_twin.legend(loc="upper right")

    # CO2 plot
    ax2.plot(times, history.co2, "g-")
    ax2.axhline(y=1000, color="r", linestyle="--", label="Warning Level")
    ax2.set_title("CO₂ (ppm)")
    ax2.legend()

    # PM2.5 plot
    ax3.plot(times, history.pm25, "y-")
    ax3.set_title("PM2.5 (μg/m³)")
    ax3.axhline(y=12, color="y", linestyle="--", label="WHO Guideline")
    ax3.axhline(y=35, color="r", linestyle="--", label="Warning Level")
    ax3.legend()

    # eCO2 plot
    ax4.plot(times, history.eco2, "m-")
    ax4.set_title("eCO₂ (ppm)")

    # Adjust layout
    plt.tight_layout()
    return fig


if __name__ == "__main__":
    # Initialize monitor
    monitor = None
    try:
        print("Initializing Air Quality Monitor...")
        monitor = AirQualityMonitor()

        print("Starting monitor...")
        monitor.start()

        # Enable interactive plotting
        plt.ion()

        # Main loop
        while True:
            # Get latest reading
            with monitor.reading_lock:
                reading = monitor.latest_reading

            if reading:
                # Clear screen
                print("\033[2J\033[H")

                # Print readings
                print(
                    f"Air Quality Monitor - {datetime.fromtimestamp(reading.timestamp)}"
                )
                print("-" * 50)
                print(f"Temperature: {reading.temperature:.1f}°C")
                print(f"Humidity: {reading.humidity:.1f}%")
                print(f"CO2: {reading.co2} ppm")
                print(f"TVOC: {reading.tvoc} ppb")
                print(f"eCO2: {reading.eco2} ppm")
                print(f"PM1.0: {reading.pm10:.1f} μg/m³")
                print(f"PM2.5: {reading.pm25:.1f} μg/m³")
                print(f"PM10.0: {reading.pm100:.1f} μg/m³")

                # Add status indicators
                print("\nStatus:")
                co2_status = monitor._get_status(reading.co2, "co2")
                tvoc_status = monitor._get_status(reading.tvoc, "tvoc")
                pm25_status = monitor._get_status(reading.pm25, "pm25")

                print(f"CO2 Level: {co2_status.upper()}")
                print(f"Air Quality: {tvoc_status.upper()}")
                print(f"Particulate Matter: {pm25_status.upper()}")

                if "bad" in [co2_status, tvoc_status, pm25_status]:
                    print("\nVENTILATION RECOMMENDED")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        if monitor:
            monitor.stop()
        print("Shutdown complete")
