from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import time


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
            self.font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16
            )
            self.small_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12
            )
        except Exception:
            self.font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()

    def _draw_vertical_gauge(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        width: int,
        height: int,
        value: float,
        indicator_type: str,
    ) -> None:
        """Draw a vertical gauge with markers for optimal and warning ranges"""
        ranges = self.indicators[indicator_type]
        min_val = ranges["min"]
        max_val = ranges["max"]

        # Normalize value to gauge height (bottom to top)
        def normalize(val):
            return height - ((val - min_val) / (max_val - min_val)) * height

        # Draw base gauge line
        draw.rectangle(
            (x + width // 2 - 1, y, x + width // 2 + 1, y + height), outline=1, fill=1
        )

        # Draw optimal range
        opt_start = normalize(ranges["optimal"][1])
        opt_end = normalize(ranges["optimal"][0])
        draw.rectangle((x, opt_start, x + width, opt_end), outline=1)

        # Draw warning range
        warn_start = normalize(ranges["warning"][1])
        warn_end = normalize(ranges["warning"][0])
        draw.rectangle((x, warn_start, x + width, warn_end), outline=1)

        # Draw current value marker (triangle pointing left)
        pos = normalize(min(max(value, min_val), max_val))
        draw.polygon(
            [(x + width + 4, pos), (x + width, pos - 4), (x + width, pos + 4)], fill=1
        )

        # Draw value text to the right
        value_text = f"{int(value)}"
        draw.text((x + width + 10, pos - 8), value_text, font=self.font, fill=1)
        draw.text(
            (x + width + 10, pos + 4), ranges["unit"], font=self.small_font, fill=1
        )

        # Draw label
        name_w = draw.textlength(ranges["name"], font=self.font)
        draw.text(
            (x + (width - name_w) // 2, y - 20), ranges["name"], font=self.font, fill=1
        )

    def _draw_top_stats(self, draw: ImageDraw.ImageDraw, reading) -> None:
        """Draw the constant top stats (temp, humidity, time) in white"""
        # Temperature on left
        temp_str = f"{reading.temperature:.1f}C"
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

        # Calculate vertical gauge positioning
        gauge_height = 80  # Taller gauge
        gauge_width = 20  # Narrower for vertical orientation
        gauge_x = 20  # More space for value text on right
        gauge_y = 30  # Below top stats

        # Draw the appropriate gauge based on current page
        if page == 0:
            self._draw_vertical_gauge(
                draw, gauge_x, gauge_y, gauge_width, gauge_height, reading.co2, "co2"
            )
        elif page == 1:
            self._draw_vertical_gauge(
                draw, gauge_x, gauge_y, gauge_width, gauge_height, reading.tvoc, "tvoc"
            )
        else:
            self._draw_vertical_gauge(
                draw, gauge_x, gauge_y, gauge_width, gauge_height, reading.pm25, "pm2.5"
            )

        self.device.display(image)

