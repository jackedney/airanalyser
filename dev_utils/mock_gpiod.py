class MockLine:
    def __init__(self, offset=0):
        self.offset = offset
        self.value = 0
        self.direction = "input"

    def get_value(self):
        return self.value

    def set_value(self, value):
        self.value = value


class MockChip:
    def __init__(self, path="/dev/gpiochip0"):
        self.path = path
        self.lines = {}
        self.opened = False

    def __enter__(self):
        self.opened = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.opened = False

    def get_line(self, offset):
        if offset not in self.lines:
            self.lines[offset] = MockLine(offset)
        return self.lines[offset]


class MockLineRequest:
    def __init__(self, consumer="mock", request_type="input", flags=0):
        self.consumer = consumer
        self.request_type = request_type
        self.flags = flags


def mock_exception(msg):
    raise Exception(f"GPIO Mock Exception: {msg}")


class ChipNotFoundError(Exception):
    pass


class LineRequestError(Exception):
    pass


def find_line(name):
    """Mock implementation of find_line"""
    return MockLine()


def line_info(path, offset):
    """Mock implementation of line_info"""
    return {
        "offset": offset,
        "name": f"mock_gpio{offset}",
        "consumer": "mock",
        "direction": "input",
        "active_state": "active-high",
        "used": False,
    }


LINE_REQ_DIR_IN = "input"
LINE_REQ_DIR_OUT = "output"
LINE_REQ_EV_FALLING_EDGE = "falling-edge"
LINE_REQ_EV_RISING_EDGE = "rising-edge"
LINE_REQ_EV_BOTH_EDGES = "both-edges"
