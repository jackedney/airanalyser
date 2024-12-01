from PIL import Image, ImageDraw, ImageFont, ImageTk
import tkinter as tk
from datetime import datetime
from typing import NamedTuple
from threading import Thread, Lock
import time
import random
from display import DisplayManager  # Import the actual display code


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


class MockDisplay:
    def __init__(
        self, width=128, height=128, i2c_port=1, rotate=2
    ):  # Match sh1106 params
        self.width = width
        self.height = height
        self.running = True

        # Create tkinter window
        self.root = tk.Tk()
        self.root.title("Air Quality Monitor Display Test")

        # Set a black background
        self.root.configure(bg="black")

        # Create frame with padding
        self.frame = tk.Frame(self.root, bg="black")
        self.frame.pack(padx=20, pady=20)

        # Create label for display
        self.label = tk.Label(self.frame, bg="black")
        self.label.pack()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        self.running = False
        self.root.quit()
        self.root.destroy()

    def display(self, image):
        if not self.running:
            return
        try:
            # Scale up the image for better visibility (4x)
            scaled_image = image.resize(
                (self.width * 4, self.height * 4), Image.NEAREST
            )

            # Convert monochrome to RGB
            rgb_image = Image.new("RGB", scaled_image.size)
            pixels = scaled_image.load()
            rgb_pixels = rgb_image.load()

            for y in range(scaled_image.size[1]):
                for x in range(scaled_image.size[0]):
                    if pixels[x, y] == 1:
                        rgb_pixels[x, y] = (255, 255, 255)  # White
                    else:
                        rgb_pixels[x, y] = (0, 0, 0)  # Black

            tk_image = ImageTk.PhotoImage(rgb_image)
            self.label.configure(image=tk_image)
            self.label.image = tk_image
            self.root.update()
        except tk.TclError:
            self.running = False


# Create the mock display and initialize the DisplayManager with it
mock_display = MockDisplay()
display_manager = DisplayManager(mock_display)


def run_test():
    try:
        while mock_display.running:
            # Generate mock reading
            reading = AirQualityReading(
                temperature=21.5 + random.uniform(-0.5, 0.5),
                humidity=45.0 + random.uniform(-2, 2),
                co2=800 + random.randint(-50, 50),
                tvoc=250 + random.randint(-20, 20),
                eco2=750 + random.randint(-50, 50),
                pm10=10.0 + random.uniform(-1, 1),
                pm25=15.0 + random.uniform(-1, 1),
                pm100=20.0 + random.uniform(-1, 1),
                timestamp=time.time(),
            )

            # Update the display using the actual DisplayManager
            display_manager.update(reading)

            # Print the values to terminal
            print("\033[2J\033[H")  # Clear terminal
            print(
                f"Air Quality Monitor Test - {datetime.fromtimestamp(reading.timestamp)}"
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
        print("\nStopping test...")
    finally:
        mock_display.on_closing()


if __name__ == "__main__":
    run_test()

