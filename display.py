from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import time

LARGE_FONT = "./fonts/dejavu-sans/DejaVuSans-Bold.ttf"
MEDIUM_FONT = "./fonts/dejavu-sans/DejaVuSans-Bold.ttf"
SMALL_FONT = "./fonts/roboto/Roboto-Regular.ttf"


class DisplayManager:
    def __init__(self, device):
        self.device = device
        self.indicators = {
            "co2": {
                "min": 400,
                "max": 2000,
                "optimal": (400, 1000),
                "warning": (1000, 1500),
                "unit": "PPM",
                "name": "CO2",
            },
            "tvoc": {
                "min": 0,
                "max": 1000,
                "optimal": (0, 300),
                "warning": (300, 600),
                "unit": "PPB",
                "name": "TVOC",
            },
            "pm2.5": {
                "min": 0,
                "max": 50,
                "optimal": (0, 12),
                "warning": (12, 35),
                "unit": "UG/M3",
                "name": "PM2.5",
            },
        }

        try:
            # Much larger font for the main value
            self.large_font = ImageFont.truetype(LARGE_FONT, 36)
            # Medium font for labels
            self.font = ImageFont.truetype(MEDIUM_FONT, 16)
            # Smaller font for units and secondary info
            self.small_font = ImageFont.truetype(SMALL_FONT, 12)
        except Exception:
            self.large_font = ImageFont.load_default()
            self.font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()

    def _draw_horizontal_gauge(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        width: int,
        height: int,
        value: float,
        indicator_type: str,
    ) -> None:
        """Draw a horizontal gauge with normalized marker positions"""
        ranges = self.indicators[indicator_type]
        value_normalized = self._normalize_value(value, indicator_type)

        # Draw base gauge rectangle
        draw.rectangle((x, y, x + width, y + height), outline=1)

        # Draw current value fill
        current_width = int(value_normalized * width)
        draw.rectangle((x, y, x + current_width, y + height), fill=1)

        # Draw optimal and warning markers at fixed positions
        # Optimal marker at 33% and warning at 66% of width
        markers = [x + int(width * 0.33), x + int(width * 0.66)]

        # Draw marker lines
        for marker_x in markers:
            draw.line((marker_x, y, marker_x, y + height), fill=1)

        # Draw the "Good" and "Poor" labels with more spacing
        draw.text((x, y + height + 6), "Good", font=self.small_font, fill=1)
        poor_w = draw.textlength("Poor", font=self.small_font)
        draw.text(
            (x + width - poor_w, y + height + 6), "Poor", font=self.small_font, fill=1
        )

    def _normalize_value(self, value: float, indicator_type: str) -> float:
        """Normalize value to 0-1 range using a logarithmic scale"""
        ranges = self.indicators[indicator_type]
        min_val = ranges["min"]
        max_val = ranges["max"]

        # Clamp value to min/max range
        value = max(min(value, max_val), min_val)

        # Use logarithmic normalization for CO2 (which has a larger range)
        if indicator_type == "co2":
            import math

            min_log = math.log(min_val)
            max_log = math.log(max_val)
            value_log = math.log(value)
            return (value_log - min_log) / (max_log - min_log)

        # Linear normalization for other values
        return (value - min_val) / (max_val - min_val)

    def _draw_reading_page(
        self, draw: ImageDraw.ImageDraw, reading, indicator_type: str
    ) -> None:
        """Draw a single reading page with large value and gauge"""
        ranges = self.indicators[indicator_type]
        value = getattr(reading, indicator_type.replace(".", ""))

        # Draw the metric name at the top
        name_w = draw.textlength(ranges["name"], font=self.font)
        draw.text((64 - name_w / 2, 25), ranges["name"], font=self.font, fill=1)

        # Draw the large value in the center
        value_text = f"{int(value)}"
        value_w = draw.textlength(value_text, font=self.large_font)
        # Position the large value lower in the display
        draw.text((64 - value_w / 2, 40), value_text, font=self.large_font, fill=1)

        # Draw the unit below the value
        unit_w = draw.textlength(ranges["unit"], font=self.small_font)
        draw.text((64 - unit_w / 2, 80), ranges["unit"], font=self.small_font, fill=1)

        # Draw the gauge lower on the screen with more space above
        self._draw_horizontal_gauge(draw, 10, 95, 108, 10, value, indicator_type)

    def _draw_top_stats(self, draw: ImageDraw.ImageDraw, reading) -> None:
        """Draw the constant top stats (temp, humidity, time) in white"""
        # Temperature on left
        temp_str = f"{reading.temperature:.1f}°C"  # Using proper degree symbol
        draw.text((2, 2), temp_str, font=self.small_font, fill=1)

        # Time in center
        time_str = datetime.fromtimestamp(reading.timestamp).strftime("%H:%M")
        time_w = draw.textlength(time_str, font=self.small_font)
        draw.text((64 - time_w / 2, 2), time_str, font=self.small_font, fill=1)

        # Humidity on right
        humid_str = f"{reading.humidity:.0f}%"
        humid_w = draw.textlength(humid_str, font=self.small_font)
        draw.text((126 - humid_w, 2), humid_str, font=self.small_font, fill=1)

    def update(self, reading) -> None:
        """Update the display with new readings"""
        page = int(time.time() / 4) % 3  # Rotate between 3 pages every 4 seconds

        image = Image.new("1", (self.device.width, self.device.height), 0)
        draw = ImageDraw.Draw(image)

        # Draw stats at top
        self._draw_top_stats(draw, reading)

        # Draw divider line
        draw.line((0, 20, 128, 20), fill=1)

        # Draw the appropriate page based on current rotation
        if page == 0:
            self._draw_reading_page(draw, reading, "co2")
        elif page == 1:
            self._draw_reading_page(draw, reading, "tvoc")
        else:
            self._draw_reading_page(draw, reading, "pm2.5")

        self.device.display(image)
