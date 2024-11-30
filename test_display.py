from PIL import ImageTk
import tkinter as tk
import time
from typing import NamedTuple
import random


# Mock air quality reading for demo
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


# Mock display device
class MockDisplay:
    def __init__(self, width=128, height=128):
        self.width = width
        self.height = height

        # Create tkinter window
        self.root = tk.Tk()
        self.root.title("Air Quality Monitor Display Demo")
        self.label = tk.Label(self.root)
        self.label.pack(padx=20, pady=20)

    def display(self, image):
        # Scale up the image for better visibility (4x)
        scaled_image = image.resize((self.width * 4, self.height * 4))
        # Convert to Tkinter format
        tk_image = ImageTk.PhotoImage(scaled_image)
        self.label.configure(image=tk_image)
        self.label.image = tk_image
        self.root.update()


# Demo script
def run_demo():
    from display import DisplayManager

    # Create mock display and display manager
    mock_display = MockDisplay()
    display_manager = DisplayManager(mock_display)

    try:
        while True:
            # Generate mock reading with some variation
            current_time = time.time()
            reading = AirQualityReading(
                temperature=23.5 + random.uniform(-0.5, 0.5),
                humidity=45.0 + random.uniform(-2, 2),
                co2=800 + random.randint(-100, 100),
                tvoc=250 + random.randint(-50, 50),
                eco2=750 + random.randint(-50, 50),
                pm10=10.0 + random.uniform(-1, 1),
                pm25=15.0 + random.uniform(-1, 1),
                pm100=20.0 + random.uniform(-1, 1),
                timestamp=current_time,
            )

            # Update display
            display_manager.update(reading)
            time.sleep(0.1)

    except KeyboardInterrupt:
        mock_display.root.destroy()


if __name__ == "__main__":
    run_demo()
