# dev_utils/mock_sensors.py
from dataclasses import dataclass
from typing import Tuple, Optional
import random
import time


@dataclass
class AirQuality:
    equivalent_co2: int
    total_voc: int


class MockSGP30:
    def __init__(self):
        self._eco2_base = 400  # typical baseline for eCO2
        self._tvoc_base = 20  # typical baseline for TVOC
        self._warmup_time = 15  # simulated warmup time in seconds
        self._start_time = time.time()
        self._measuring = False

    def start_measurement(self) -> None:
        self._measuring = True

    def get_air_quality(self) -> AirQuality:
        if not self._measuring:
            return AirQuality(equivalent_co2=400, total_voc=0)

        # Add some realistic variation
        eco2 = int(self._eco2_base + random.gauss(0, 50))  # std dev of 50
        tvoc = int(self._tvoc_base + random.gauss(0, 5))  # std dev of 5

        return AirQuality(equivalent_co2=max(400, eco2), total_voc=max(0, tvoc))

    def command(self, cmd_name: str, args: list | None = None) -> None:
        if cmd_name == "set_humidity" and args:
            # Mock handling humidity compensation
            pass


class MockSCD4x:
    def __init__(self):
        self._co2_base = 400.0  # typical outdoor CO2 level
        self._temp_base = 21.0  # room temperature in Celsius
        self._humidity_base = 45.0  # typical indoor humidity
        self._measuring = False
        self._error_rate = 0.01

    def start_periodic_measurement(self) -> None:
        self._measuring = True

    def stop_periodic_measurement(self) -> None:
        self._measuring = False

    def measure(self) -> Optional[Tuple[int, float, float, float]]:
        if not self._measuring:
            return None

        if random.random() < self._error_rate:
            raise RuntimeError("Mock SCD4x read error")

        # Add realistic variations
        co2 = int(self._co2_base + random.gauss(0, 25))  # std dev of 25 ppm
        temp = self._temp_base + random.gauss(0, 0.5)  # std dev of 0.5°C
        humidity = self._humidity_base + random.gauss(0, 2)  # std dev of 2% RH
        timestamp = time.time()

        return (max(400, co2), temp, max(0, min(100, humidity)), timestamp)


@dataclass
class MockPMSData:
    pm_ug_per_m3: tuple = (12.0, 25.0, 45.0)  # PM1.0, PM2.5, PM10
    pm_per_1l_air: tuple = (1200, 2500, 4500)  # PM1.0, PM2.5, PM10
    raw_gt_point_three_um: int = 10000
    raw_gt_point_five_um: int = 8000
    raw_gt_one_um: int = 5000
    raw_gt_two_point_five_um: int = 2000
    raw_gt_five_um: int = 500
    raw_gt_ten_um: int = 100


class MockPMS5003:
    def __init__(self):
        self._data = MockPMSData()
        self._error_rate = 0.01  # 1% chance of read error

    def read(self) -> MockPMSData:
        if random.random() < self._error_rate:
            raise RuntimeError("Mock PMS5003 read error")

        # Add some random variation to make it more realistic
        variation = random.uniform(0.8, 1.2)
        return MockPMSData(
            pm_ug_per_m3=tuple(v * variation for v in self._data.pm_ug_per_m3),
            pm_per_1l_air=tuple(int(v * variation) for v in self._data.pm_per_1l_air),
            raw_gt_point_three_um=int(self._data.raw_gt_point_three_um * variation),
            raw_gt_point_five_um=int(self._data.raw_gt_point_five_um * variation),
            raw_gt_one_um=int(self._data.raw_gt_one_um * variation),
            raw_gt_two_point_five_um=int(
                self._data.raw_gt_two_point_five_um * variation
            ),
            raw_gt_five_um=int(self._data.raw_gt_five_um * variation),
            raw_gt_ten_um=int(self._data.raw_gt_ten_um * variation),
        )

