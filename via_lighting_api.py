"""
A Python API that encapsulates VIA lighting control,
following the VIA version 12 protocol.
"""

import hid
import colorsys
import argparse
import platform
from tools.keyboard_info_viewer import list_devices

"""Global constants"""
VERSION_NUM = '0.2.1'
VIA_INTERFACE_NUM = 1
RAW_HID_BUFFER_SIZE = 32

"""VIA commands"""
CUSTOM_SET_VALUE = 7
CUSTOM_SAVE = 9

"""VIA channels"""
CHANNEL_RGB_MATRIX = 3

"""VIA rgb matrix entries"""
RGB_MATRIX_VALUE_BRIGHTNESS = 1
RGB_MATRIX_VALUE_EFFECT = 2
RGB_MATRIX_VALUE_EFFECT_SPEED = 3
RGB_MATRIX_VALUE_COLOR = 4


class ViaLightingAPI:
    device_path = None

    """Color correction factor"""
    cor = None

    def __init__(self, vid, pid):
        """
        Initialize the API (find the device)
        :param vid: vendor id
        :param pid: product id (can be None if vendor id can uniquely identify the keyboard)
        """
        self.device_path = self.__find_device_path(vid, pid)
        if self.device_path is None:
            raise self.DeviceNotFoundError("Device not found or does not support VIA.")
        
        self.host_os = platform.system()

    @staticmethod
    def __find_device_path(vendor_id, product_id):
        """
        Find the device by vendor id and product id
        :param vendor_id: vendor id
        :param product_id: product id
        :return: path of the device
        """
        for device_dict in hid.enumerate():
            if device_dict['vendor_id'] == vendor_id:
                if product_id is None or device_dict['product_id'] == product_id:
                    if device_dict['interface_number'] == VIA_INTERFACE_NUM:
                        return device_dict['path']
        return None

    def _send(self, data):
        """
        Filling then sending the command to device via HID\n
        Warning:\n
        This function is not recommended.
        It will send the command directly to your device,
        which may cause unexpected result.
        Make sure you fully understand the meaning of the command before sending it.
        :param data: command bytes (array)
        :return: None
        """
        padded_data = ([0] if self.host_os == "Windows" else []) + data + [0] * (RAW_HID_BUFFER_SIZE - len(data))
        h = hid.device()
        h.open_path(self.device_path)
        try:
            h.write(padded_data)
        finally:
            h.close()

    def set_brightness(self, brightness):
        """
        Set lighting brightness
        :param brightness: target brightness (0-255)
        :return: None
        """
        command = [CUSTOM_SET_VALUE, CHANNEL_RGB_MATRIX, RGB_MATRIX_VALUE_BRIGHTNESS, brightness]
        self._send(command)

    def set_effect(self, effect):
        """
        Set lighting effect\n
        Commonly used effects by QMK default:\n
        0 - All off\n
        1 - Solid color\n
        5 - Breathing\n
        6 - Band Sat.\n
        7 - Band Val.\n
        12 - Cycle All\n
        13 - Cycle Left/Right\n
        14 - Cycle Up/Down\n
        15 - Rainbow Moving Chevron\n
        41 - Splash\n
        :param effect: target effect (0-44)
        :return: None
        """
        command = [CUSTOM_SET_VALUE, CHANNEL_RGB_MATRIX, RGB_MATRIX_VALUE_EFFECT, effect]
        self._send(command)

    def set_effect_speed(self, speed):
        """
        Set the speed of lighting effect
        :param speed: target speed (0-255)
        :return: None
        """
        command = [CUSTOM_SET_VALUE, CHANNEL_RGB_MATRIX, RGB_MATRIX_VALUE_EFFECT_SPEED, speed]
        self._send(command)

    def set_color(self, color):
        """
        Set lighting color, RGB and HSV formats supported
        :param color: [R, G, B] or [H, S]
        :return: None
        """
        hue, sat = None, None
        color_len = len(color)
        if color_len == 3:
            """RBG format"""
            hue, sat = self.__rgb_to_hsv(color)[:2]
        elif color_len == 2:
            """HSV format"""
            hue, sat = color
        command = [CUSTOM_SET_VALUE, CHANNEL_RGB_MATRIX, RGB_MATRIX_VALUE_COLOR, hue, sat]
        self._send(command)

    def set_color_abs(self, color):
        """
        Set absolute lighting color (adjust both HS color and brightness), RGB format supported\n
        The effect will be better only if your keyboard switch has a light-guiding design or
        the color saturation of the switch is low, because the color displayed will be greatly biased
        towards the color of the switch when the light brightness is low.
        If not, try out the color correction function.
        :param color: [R, G, B]
        :return: None
        """
        hue, sat, val = self.__rgb_to_hsv(
            [color[i] / self.cor[i] for i in range(len(color))]) if self.cor else self.__rgb_to_hsv(color)
        command_color = [CUSTOM_SET_VALUE, CHANNEL_RGB_MATRIX, RGB_MATRIX_VALUE_COLOR, hue, sat]
        command_brightness = [CUSTOM_SET_VALUE, CHANNEL_RGB_MATRIX, RGB_MATRIX_VALUE_BRIGHTNESS, val]
        self._send(command_color)
        self._send(command_brightness)

    def save(self):
        """
        Save current lighting settings to EEPROM
        :return: None
        """
        command = [CUSTOM_SAVE, CHANNEL_RGB_MATRIX]
        self._send(command)

    @staticmethod
    def __rgb_to_hsv(rgb):
        """
        Convert RGB to HSV
        :param rgb: [red (0-255), green (0-255), blue (0-255)]
        :return: HSV values
        """
        h, s, v = colorsys.rgb_to_hsv(*[value / 255.0 for value in rgb])
        return int(h * 255), int(s * 255), int(v * 255)

    class DeviceNotFoundError(Exception):
        pass

    def set_color_correction(self, true_white):
        """
        Enable color correction, which is useful when your keyboard switches do not have light guide designs,
        or they have highly saturated colors, and you want them to display accurate colors.
        To use it, you first need to test the RGB values of the light settings when your keyboard displays true white.\n
        This algorithm only applies to **set_color_abs()**.
        :param true_white: [red (0-255), green (0-255), blue (0-255)]
               - RGB value when the keyboard light displays a true white color
        :return: None
        """
        if isinstance(true_white, list) and len(true_white) == 3:
            self.cor = [255 / value for value in true_white]

    def disable_color_correction(self):
        """
        Disable color calibration
        :return: None
        """
        self.cor = None


def main():
    parser = argparse.ArgumentParser(description='VIA lighting API')
    parser.add_argument('-v', '--version', action='version', version=VERSION_NUM)
    parser.add_argument('--list-devices', action='store_true',
                        help="helps you find your keyboard's vendor id and product id")
    args = parser.parse_args()
    if args.list_devices:
        list_devices()
    else:
        print("Please use --list-devices to find your keyboard's vendor id and product id.")
