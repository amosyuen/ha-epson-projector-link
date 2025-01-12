"""Const helpers of Epson projector module."""

from homeassistant.const import STATE_OFF
from homeassistant.const import STATE_ON

# Resources for ESC/VP format and codes
# https://support.atlona.com/hc/en-us/articles/360048888054-IP-Control-of-Epson-Projectors
# https://www.avsforum.com/threads/official-epson-5040ub-6040ub-owners-thread.2563857/page-680
# http://support.epson.com.tw/i-tech/%E6%8A%80%E8%A1%93%E6%96%87%E4%BB%B6/EB-L1070U_L1070_L1060U_Specification_EN.pdf


def invert_map(map):
    return {v: k for k, v in map.items()}


#
# Open Connection
#

TCP_PORT = 3629
TIMEOUT_CONNECT = 60
TIMEOUT_REQUEST = 10
TIMEOUT_POWER_ON_OFF = 60
RESPONSE_ERROR = "ERR"

ESCVPNETNAME = "ESC/VP.net"
# 10 bytes | protocol | "ESC/VP.net"
# 1 byte | version | 0x10
# 1 uchar | type | 0x03 (CONNECT)
# ushort | sequence number | 0x0
# 1 byte | status | 0x0
# 1 uchar | header count | 0x0"
ESCVPNET_CONNECT_COMMAND = f"{ESCVPNETNAME}\x10\x03\x00\x00\x00\x00"

STATUS_OK = 0x20
STATUS_CODE_MAP = {
    STATUS_OK: "OK",
    0x40: "Bad Request",
    0x41: "Unauthorized",
    0x43: "Forbidden",
    0x45: "Service Unavailable",
    0x55: "Protocol Version Not Supported",
}

#
# Properties
#
# Keep in sync with media_player.py PROPERTY_TO_ATTRIBUTE_NAME_MAP
PROPERTY_AUTO_IRIS_MODE = "IRIS"
PROPERTY_BRIGHTNESS = "BRIGHT"
PROPERTY_COLOR_MODE = "CMODE"
PROPERTY_ERR = "ERR"
PROPERTY_LAMP_HOURS = "LAMP"
PROPERTY_MUTE = "MUTE"
PROPERTY_POWER = "PWR"
PROPERTY_POWER_CONSUMPTION_MODE = "LUMINANCE"
PROPERTY_SOURCE = "SOURCE"
PROPERTY_SOURCE_LIST = "SOURCELIST"
PROPERTY_SERIAL_NUMBER = "SNO"
PROPERTY_VOLUME = "VOL"

#
# Commands
#
COMMAND_LOAD_LENS_MEMORY = "POPLP"
COMMAND_LOAD_PICTURE_MEMORY = "POPMEM"

COMMAND_MEDIA_PLAY = "KEY D1"
COMMAND_MEDIA_STOP = "KEY D2"
COMMAND_MEDIA_PAUSE = "KEY D3"
COMMAND_MEDIA_PREVIOUS = "KEY D4"
COMMAND_MEDIA_NEXT = "KEY D5"
COMMAND_MEDIA_MUTE = "KEY D8"
COMMAND_MEDIA_VOL_UP = "KEY 56"
COMMAND_MEDIA_VOL_DOWN = "KEY 57"

ON = "ON"
OFF = "OFF"

#
# Auto Iris
#
# Should keep in sync with epson_projector_link/services.yaml select_auto_iris_mode options
AUTO_IRIS_MODE_CODE_MAP = {
    "00": "Off",
    "01": "Normal",
    "02": "High",
}
AUTO_IRIS_MODE_CODE_INVERTED_MAP = invert_map(AUTO_IRIS_MODE_CODE_MAP)

#
# Color Modes
#
# Should keep in sync with epson_projector_link/services.yaml select_color_mode options
COLOR_MODE_CODE_MAP = {
    "00": "Auto",
    "05": "Theatre",
    "06": "Dynamic",
    "07": "Natural",
    "09": "Theatre Black 1/HD",
    "0A": "Theatre Black 2/Silver Screen",
    "0B": "x.v.Color",
    "0C": "Bright Cinema",
    "0D": "Game",
    "13": "THX",
    "15": "Cinema",
    "16": "Stage",
    "17": "3D Cinema",
    "18": "3D Dynamic",
    "19": "3D THX",
    "20": "B&W Cinema",
    "21": "Adobe RGB",
    "22": "Digital Cinema",
    "C1": "AutoColor",
}
COLOR_MODE_CODE_INVERTED_MAP = invert_map(COLOR_MODE_CODE_MAP)

#
# Errors
#
ERROR_NONE = "None"
PROPERTY_ERR_CODE_MAP = {
    "00": ERROR_NONE,
    "01": "Fan error",
    "03": "Lamp failure at power on",
    "04": "High internal temperature error",
    "06": "Lamp error",
    "07": "Open Lamp cover door error",
    "08": "Cinema filter error",
    "09": "Electric dual-layered capacitor is disconnected",
    "0A": "Auto iris error",
    "0B": "Subsystem Error",
    "0C": "Low air flow error",
    "0D": "Air filter air flow sensor error",
    "0E": "Power supply unit error (Ballast)",
    "0F": "Shutter error",
    "10": "Cooling system error (peltiert element)",
    "11": "Cooling system error (Pump)",
    "12": "Static iris error",
    "13": "Power supply unit error (Disagreement of Ballast)",
    "14": "Exhaust shutter error",
    "15": "Obstacle detection error",
    "16": "IF board discernment error",
    "17": "Communication error of stack projection function",
    "18": "I2C error",
    "1A": "Lens shift error",
    "1B": "Quarts N Polarizer error",
    "1C": "No lens error",
    "1D": "Subsystem error 2",
    "1E": "Power supply voltage error",
    "1F": "Other error",
}

#
# Power
#
STATE_COOLDOWN = "cooldown"
STATE_WARMUP = "warmup"

POWER_CODE_MAP = {
    "00": STATE_OFF,  # standby (network off)
    "01": STATE_ON,
    "02": STATE_WARMUP,
    "03": STATE_COOLDOWN,
    "04": STATE_OFF,  # standby (network on)
    "05": STATE_OFF,  # abnormal standby
    "09": STATE_OFF,  # A/V standby
}

#
# Power Consumption
#
# Should keep in sync with epson_projector_link/services.yaml select_power_consumption_mode options
POWER_CONSUMPTION_MODE_CODE_MAP = {
    "00": "High",
    "01": "ECO",
    "02": "Medium",
}
POWER_CONSUMPTION_MODE_CODE_INVERTED_MAP = invert_map(POWER_CONSUMPTION_MODE_CODE_MAP)

#
# Sources
#
SOURCE_CODE_MAP = {
    "10": "PC",
    "20": "PC2",
    "30": "HDMI1",
    "40": "VIDEO",
    "52": "USB",
    "53": "LAN",
    "56": "WiFi Direct",
    "A0": "HDMI2",
    "D0": "WirelessHD",
}
SOURCE_CODE_INVERTED_MAP = invert_map(SOURCE_CODE_MAP)

#
# Events
#
IMEVENT = "IMEVENT"
IMEVENT_STATUS_CODE_ABNORMAL = 0xFF
IMEVENT_STATUS_CODE_TO_POWER_MAP = {
    1: STATE_OFF,
    2: STATE_WARMUP,
    3: STATE_ON,
    4: STATE_COOLDOWN,
}
IMEVENT_WARNING_BIT_MAP = {
    0: "Lamp life",
    1: "No signal",
    2: "Unsupported signal",
    3: "Air filter",
    4: "High temperature",
}
IMEVENT_ALARM_BIT_MAP = {
    0: "Lamp ON failure",
    1: "Lamp lid",
    2: "Lamp burnout",
    3: "Fan",
    4: "Temperature sensor",
    5: "High temperature",
    6: "Interior (system)",
}
