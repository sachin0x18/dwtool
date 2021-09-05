#!/usr/bin/env python

# Copyright (c) 2021 sachin0x18
# SPDX-License-Identifier: MIT

import argparse
import binascii
from hid_scancodes import hid_scancodes
import json
import sys
import usb.core
import usb.util

__version__ = "1.0"

class ELE_G9():
    """
    Class for Dragonwar ELE-G9 Thor mouse
    """
    VENDOR_ID = 0x04D9
    PROD_ID = 0xA0AC
    INTERFACE = 2

    # Do NOT change the order of the entries.
    # Index of these entries also describe their location in command array
    button_json_keys = [
        "LEFT_BUTTON",
        "RIGHT_BUTTON",
        "SCROLL_BUTTON",
        "SIDE_BACKWARD_BUTTON",
        "SIDE_FORWARD_BUTTON",
        "DPI_BUTTON",
        "FIRE_BUTTON",
        "SCROLL_UP",
        "SCROLL_DOWN"
        ]

    led_json_keys = [
        "PATTERN",
        "COLOR"
        ]

    action_cmd = {
            "CLICK" :           [0x01, 0x00, 0xF0, 0x00],
            "MENU" :            [0x01, 0x00, 0xF1, 0x00],
            "WHEEL_CLICK" :     [0x01, 0x00, 0xF2, 0x00],
            "IE_BACKWARD" :     [0x01, 0x00, 0xF3, 0x00],
            "IE_FORWARD" :      [0x01, 0x00, 0xF4, 0x00],
            "STOP" :            [0x03, 0x00, 0xB7, 0x00],
            "PLAY/PAUSE" :      [0x03, 0x00, 0xCD, 0x00],
            "MUTE" :            [0x03, 0x00, 0xE2, 0x00],
            "VOLUME_UP" :       [0x03, 0x00, 0xE9, 0x00],
            "VOLUME_DOWN" :     [0x03, 0x00, 0xEA, 0x00],
            "SCROLL_UP" :       [0x04, 0x00, 0x01, 0x00],
            "SCROLL_DOWN" :     [0x04, 0x00, 0x02, 0x00],
            "DPI_CYCLE" :       [0x07, 0x00, 0x03, 0x00],
            "FIRE" :            [0x0A, 0xF0, 0x01, 0x00],
            "DOUBLE_CLICK" :    [0x0A, 0xF0, 0x32, 0x02],
            }

    mod_cmd = {
            'CTRL' :  0x01,
            'SHIFT' : 0x02,
            'ALT' :   0x04,
            'CMD' :   0x08,
            'WIN' :   0x08,
            }

    def __init__(self):
        self.dev = None
        self.reattach_kernel = False

    def pattern_to_cmd(self, pattern, is_all_color):
        if (pattern.lower() == 'off'):
            return [0x00, 0x00, 0x00]

        cmds = {
               'breathing': [0x02, 0x05],
               'full_bright': [0x01, 0x0a],
               }
        try:
            cmd = cmds[pattern.lower()]
        except KeyError:
            raise RuntimeError("[-] Invalid LED pattern: %s" % pattern)

        if (is_all_color):
            cmd.append(0x03)
        else:
            cmd.append(0x01)
        return cmd

    def action_to_cmd(self, action):
        action = action.upper()
        if action.startswith('SHORTCUT_'):
            cmd = [0x00] * 4
            single_key = False
            sc = action.split('SHORTCUT_', 1)[1]
            sc_list = list(sc.split('+'))

            if len(sc_list) > 5:
                raise Exception('[-] Shortcut too long. Shortcut only supports single key along with modifiers')

            for key in sc_list:
                if (key == 'SHIFT' or key == 'CTRL' or key == 'ALT' or key == 'CMD' or key == 'WIN'):
                    cmd[1] = cmd[1] | self.mod_cmd[key]
                else:
                    if (single_key):
                        raise Exception('[-] Multiple keys detected. Shortcut only supports single key along with modifiers')
                    try:
                        cmd[2] = hid_scancodes['KEY_' + key]
                    except KeyError:
                        raise Exception("[-] Invalid key: '%s'" % key)
                    single_key = True
            return cmd
        else:
            return self.action_cmd[action]

    def validate_json(self, config):
        button_config = config.get('BUTTONS')
        led_config = config.get('LED')

        def check_keys(config, keys):
            for key in keys:
                if key not in config:
                    raise ValueError("[-] %s key missing in the config file" % key)

        if (button_config):
            check_keys(button_config, self.button_json_keys)

        if (led_config):
            check_keys(led_config, self.led_json_keys)

    def generate_button_commands(self, button_config):
        cmd_1 = []
        for key in self.button_json_keys[:-2]:
            action = button_config[key]
            cmd_1 = cmd_1 + self.action_to_cmd(action)

        cmd_1 = cmd_1 + [0x00] * 4

        cmd_2 = [0x00] * 24
        for key in self.button_json_keys[-2: ]:
            action = button_config[key]
            cmd_2 = cmd_2 + self.action_to_cmd(action)

        return cmd_1, cmd_2

    def generate_led_commands(self, led_config):
        color_cmd = []
        pattern_cmd = []
        is_all_color = (led_config['COLOR'] == 'all')
        if (not is_all_color):
            try:
                color_cmd = binascii.unhexlify(led_config['COLOR'])
                if (len(color_cmd) != 3):
                    raise ValueError("Incorrect RGB hex code length")
            except Exception as e:
                raise RuntimeError("[-] Invalid RGB hex code: %s (%s)" % (led_config['COLOR'], e))

        pattern_cmd = self.pattern_to_cmd(led_config['PATTERN'], is_all_color)
        return color_cmd, pattern_cmd

    def open(self):
        self.dev = usb.core.find(idVendor=self.VENDOR_ID, idProduct=self.PROD_ID)
        if (not self.dev):
            raise RuntimeError("[-] ELE-G9 mouse not found")

    def acquire_control(self):
        try:
            if (self.dev.is_kernel_driver_active(self.INTERFACE)):
                self.dev.detach_kernel_driver(self.INTERFACE)
                self.reattach_kernel = True

            usb.util.claim_interface(self.dev, self.INTERFACE)
        except Exception as exp:
            raise RuntimeError("%s: %s" % (type(exp).__name__, exp))

    @staticmethod
    def _checksum(data):
        return ((sum(data) ^ 0xFF) & 0xFF)

    def set_led_pattern(self, pattern_cmd):
        cmd = [0x0D] + pattern_cmd + [0x00] * 3
        cmd.append(self._checksum(cmd))
        self.dev.ctrl_transfer(0x21, 0x09, 0x0300, 0x0002, cmd)

    def set_led_color(self, led_color):
        if (led_color is not None):
            cmd = [0x0C] + list(led_color) + [0x00] * 3
            cmd.append(self._checksum(cmd))
            self.dev.ctrl_transfer(0x21, 0x09, 0x0300, 0x0002, cmd)

    def set_button_config(self, cmd_1, cmd_2):
        cmd = [0x12, 0x01, 0x40, 0x00, 0x00, 0x00, 0x00, 0xAC]
        self.dev.ctrl_transfer(0x21, 0x09, 0x0300, 0x0002, cmd)
        self.dev.write(4, cmd_1, 1000)
        self.dev.write(4, cmd_2, 1000)

    def release_control(self):
        usb.util.release_interface(self.dev, self.INTERFACE)
        if (self.reattach_kernel):
            self.dev.attach_kernel_driver(self.INTERFACE)

    def close(self):
        self.dev.reset()
        self.dev = None


def led_config(args):
    led_config = { 'PATTERN' : args.pattern,
                   'COLOR'   : args.color,
                 }

    dev = ELE_G9()
    color_cmd, pattern_cmd = dev.generate_led_commands(led_config)
    dev.open()
    dev.acquire_control()
    dev.set_led_color(color_cmd)
    print("[+] LED color set: #%s" % args.color)
    dev.set_led_pattern(pattern_cmd)
    print("[+] LED pattern set: %s" % args.pattern)
    dev.release_control()
    dev.close()


def mouse_config(args):
    try:
        with open(args.config_file) as f:
            config_json = json.load(f)
    except Exception as e:
        raise RuntimeError(e)

    dev = ELE_G9()

    dev.validate_json(config_json)

    button_config = config_json.get('BUTTONS')
    led_config = config_json.get('LED')

    dev.open()
    dev.acquire_control()

    if (button_config):
        cmd1, cmd2 = dev.generate_button_commands(button_config)
        dev.set_button_config(cmd1, cmd2)
        print("[+] LED buttons configured")
    if (led_config):
        color_cmd, pattern_cmd = dev.generate_led_commands(led_config)
        dev.set_led_color(color_cmd)
        print("[+] LED color set: #%s" % led_config['COLOR'])
        dev.set_led_pattern(pattern_cmd)
        print("[+] LED pattern set: %s" % led_config['PATTERN'])

    dev.release_control()
    dev.close()


def main():
    parser = argparse.ArgumentParser(description='dwtool.py v%s - Dragonwar ELE-G9 config tool' % __version__,
            formatter_class=argparse.RawTextHelpFormatter)

    subparsers = parser.add_subparsers(
                    dest='configs',
                    help='Run dwtool.py {command} -h for additional help')

    led_config_parser = subparsers.add_parser(
                    'led_config',
                    help='Set LED pattern and LED color',
                    formatter_class=argparse.RawTextHelpFormatter)

    led_config_parser.add_argument('pattern',
                    help='LED pattern\n'
                         'Choose from:\n'
                         '- off\n'
                         '- breathing\n'
                         '- full_bright',
                    type=str,
                    default=None)

    led_config_parser.add_argument('color',
                    help='Color of the LEDs\n'
                         'Provide either:\n'
                         '- RGB hex code. (e.g 7f7f7f)\n'
                         '- all (Cycle through all pre-defined colors)\n',
                    type=str,
                    default=None)

    led_config_parser.set_defaults(func=led_config)

    mouse_config_parser = subparsers.add_parser('mouse_config', help='Config the buttons and LED on the mouse')

    mouse_config_parser.add_argument('config_file', help='JSON config file', type=str)

    mouse_config_parser.set_defaults(func=mouse_config)

    args = parser.parse_args()

    try:
        args.func(args)
    except AttributeError:
        parser.print_help()
        sys.exit(1)
    except Exception as error:
        raise SystemExit(error)

if __name__ == "__main__":
    main()
