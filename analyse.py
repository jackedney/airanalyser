from PIL import Image, ImageDraw
import time
from threading import Thread, Lock
from typing import NamedTuple
from datetime import datetime
from sgp30 import SGP30
from scd4x import SCD4X


class AirQualityReading(NamedTuple):
    """Container for all sensor readings"""

    temperature: float
    humidity: float
    co2: int
    tvoc: int
    eco2: int
    timestamp: float


class AirQualityMonitor:
    """Main class for monitoring air quality using SGP30 and SCD41 sensors"""

    def __init__(self, display_device, update_interval=1.0):
        """Initialize sensors and display

        Args:
            display_device: Display device from luma.core
            update_interval: How often to update readings in seconds
        """
        self.display = display_device
        self.update_interval = update_interval
        self.reading_lock = Lock()
        self.latest_reading = None
        self.running = False

        # Initialize sensors
        self.sgp30 = SGP30()  # Air quality sensor
        self.scd41 = SCD4X()  # CO2 sensor

        # Start SGP30 measurement
        print("Initializing SGP30 (15 seconds)...")
        self.sgp30.start_measurement()

        # Start SCD41 measurement
        print("Starting SCD41 periodic measurement...")
        self.scd41.start_periodic_measurement()

    def start(self):
        """Start the monitoring thread"""
        self.running = True
        self.monitor_thread = Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        self.display_thread = Thread(target=self._display_loop, daemon=True)
        self.display_thread.start()

    def stop(self):
        """Stop monitoring and clean up"""
        self.running = False
        self.monitor_thread.join()
        self.display_thread.join()
        self.scd41.stop_periodic_measurement()

    def _monitoring_loop(self):
        """Main monitoring loop - collects sensor readings"""
        while self.running:
            try:
                # Get SGP30 readings
                air_quality = self.sgp30.get_air_quality()

                # Get SCD41 readings (blocking call)
                results = self.scd41.measure()
                assert results is not None, "No results from SCD41"
                co2, temp, humidity, timestamp = results

                # Update humidity compensation on SGP30
                abs_humidity = self._calculate_absolute_humidity(temp, humidity)
                self.sgp30.command("set_humidity", abs_humidity)

                # Create new reading with lock
                with self.reading_lock:
                    self.latest_reading = AirQualityReading(
                        temperature=temp,
                        humidity=humidity,
                        co2=co2,
                        tvoc=air_quality.total_voc,
                        eco2=air_quality.equivalent_co2,
                        timestamp=timestamp,
                    )

                time.sleep(self.update_interval)

            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(1)

    def _display_loop(self):
        """Main display loop - updates the display with latest readings"""
        while self.running:
            try:
                with self.reading_lock:
                    reading = self.latest_reading

                if reading:
                    self._update_display(reading)

                time.sleep(0.1)  # Faster refresh rate for display

            except Exception as e:
                print(f"Error in display loop: {e}")
                time.sleep(1)

    def _update_display(self, reading: AirQualityReading):
        """Update the display with the current reading

        Creates a multi-page display that rotates through different metrics
        """
        # Calculate which page to show based on time
        page = int(time.time() / 2) % 3  # Rotate every 2 seconds

        # Create a new image with display dimensions
        image = Image.new("1", (self.display.width, self.display.height), 0)
        draw = ImageDraw.Draw(image)

        if page == 0:
            # Temperature and Humidity page
            self._draw_temp_humidity(draw, reading)
        elif page == 1:
            # CO2 page
            self._draw_co2(draw, reading)
        else:
            # VOC page
            self._draw_voc(draw, reading)

        self.display.display(image)

    def _draw_temp_humidity(self, draw, reading):
        """Draw temperature and humidity readings"""
        draw.text((0, 0), "Temp & Humidity", fill=1)
        draw.text((0, 16), f"{reading.temperature:.1f}°C", fill=1)
        draw.text((0, 32), f"{reading.humidity:.1f}%RH", fill=1)

    def _draw_co2(self, draw, reading):
        """Draw CO2 readings"""
        draw.text((0, 0), "CO2 Levels", fill=1)
        draw.text((0, 16), f"{reading.co2} ppm", fill=1)

        # Add warning if CO2 is too high
        if reading.co2 > 1000:
            draw.text((0, 32), "VENTILATE!", fill=1)

    def _draw_voc(self, draw, reading):
        """Draw VOC readings"""
        draw.text((0, 0), "Air Quality", fill=1)
        draw.text((0, 16), f"TVOC: {reading.tvoc} ppb", fill=1)
        draw.text((0, 32), f"eCO2: {reading.eco2} ppm", fill=1)

    def _calculate_absolute_humidity(self, temperature, relative_humidity):
        """Calculate absolute humidity for SGP30 compensation

        Formula from SGP30 datasheet
        """
        temp_k = temperature + 273.15
        # Calculate saturated vapor pressure first
        pvs = 6.112 * pow(2.71828, (17.62 * temperature) / (243.12 + temperature))
        # Calculate absolute humidity in g/m³
        abs_humidity = (relative_humidity * pvs * 2.1674) / temp_k
        # Convert to format needed by SGP30 (fixed point 8.8 bit)
        return int(abs_humidity * 256)


def create_monitor(display_device=None):
    """Factory function to create and configure a new monitor instance

    If no display device is provided, attempts to create one using
    demo settings from luma.core
    """
    if display_device is None:
        from display.demo_opts import get_device

        display_device = get_device()

    return AirQualityMonitor(display_device)


if __name__ == "__main__":
    try:
        monitor = create_monitor()
        monitor.start()

        # Keep main thread alive with status updates
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

            time.sleep(1)

    except KeyboardInterrupt:
        monitor.stop()
        print("\nMonitoring stopped.")
