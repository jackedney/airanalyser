from PIL import Image, ImageDraw
from pathlib import Path
import time
from typing import Optional, Union


class MockSH1106:
    """
    Mock implementation of SH1106 display driver.
    Simulates the display by saving the output as PNG files for visual inspection during development.
    """

    def __init__(self, port=0, address=0x3C, width=128, height=64, i2c_port=1, rotate=1):
        self.width = width
        self.height = height
        self.address = address
        self.port = port
        self._image = Image.new(
            "1", (width, height), "black"
        )  # 1-bit pixels, black background
        self._draw = ImageDraw.Draw(self._image)
        self._contrast = 255
        self._inverted = False

        # Create directory for debug output
        self.debug_dir = Path("debug_display")
        self.debug_dir.mkdir(exist_ok=True)
        self.frame_count = 0

    def display(self, image: Optional[Image.Image] = None) -> None:
        """Update the display with the latest image."""
        if image:
            # Ensure image is in 1-bit mode
            if image.mode != "1":
                image = image.convert("1")
            self._image = image

        # Save the current display state as a PNG for debugging
        debug_image = self._image.copy()
        if self._inverted:
            debug_image = debug_image.point(lambda x: not x)

        # Scale up the image for better visibility in debug output
        scale = 4
        debug_image = debug_image.resize(
            (self.width * scale, self.height * scale), Image.Resampling.NEAREST
        )

        timestamp = int(time.time() * 1000)
        filename = self.debug_dir / f"display_frame_{self.frame_count}_{timestamp}.png"
        debug_image.save(filename)
        self.frame_count += 1

        # Keep only the last 10 frames to avoid filling up disk space
        frames = sorted(self.debug_dir.glob("display_frame_*.png"))
        if len(frames) > 10:
            for frame in frames[:-10]:
                frame.unlink()

    def command(self, *cmd: Union[int, bytes]) -> None:
        """Mock implementation of sending commands to the display."""
        pass

    def data(self, data: Union[bytes, bytearray]) -> None:
        """Mock implementation of sending data to the display."""
        pass

    def clear(self) -> None:
        """Clear the display."""
        self._draw.rectangle((0, 0, self.width, self.height), fill="black")
        self.display()

    def contrast(self, level: int) -> None:
        """Set display contrast."""
        self._contrast = max(0, min(255, level))

    def invert(self, value: bool) -> None:
        """Invert display colors."""
        self._inverted = value
        self.display()

    def show(self) -> None:
        """Alternative name for display() method."""
        self.display()


class MockI2CInterface:
    """Mock I2C interface for the display."""

    def __init__(self, port=1):
        self.port = port

    def command(self, *cmd):
        pass

    def data(self, data):
        pass


class device:
    """
    Mock implementation of luma.oled device factory.
    This matches the luma.oled.device interface.
    """

    @staticmethod
    def sh1106(serial_interface=None, width=128, height=64, rotate=0):
        if serial_interface is None:
            serial_interface = MockI2CInterface()
        return MockSH1106(width=width, height=height)


# Helper function to create a device with default settings
def create_mock_display(width=128, height=64, rotate=0):
    """Create a mock display device with the specified settings."""
    return device.sh1106(width=width, height=height, rotate=rotate)
