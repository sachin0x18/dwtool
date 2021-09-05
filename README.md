# dwtool

A linux utility to configure the Dragonwar ELE-G9 mouse.

### Capabilities:

- Set LED color using RGB hexcode: FFFFFF
- Set LED pattern
- Configure BUTTONS with [pre-defined actions](dwtool.py#L43)
- Configure BUTTONS with custom single-key shortcut

### TODO:
 - Record MACROs
 - Assign recorded MACROs to buttons

### Usage

#### Requirements
- Python 3+
- PyUSB (pip install pyusb)

Create a udev rule for the device, so as to not require root access to configure the mouse.
```
$ cat /etc/udev/rules.d/18-dragonwar.rules

# Dragonwar ELE-G9 mouse
SUBSYSTEM=="usb", ATTRS{idVendor}=="04d9", ATTRS{idProduct}=="a0ac", MODE="0666", GROUP="plugdev"
```

#### Commands
Configuring LEDs:

```
./dwtool.py led_config breathing 0000FF
```

Configuring mouse using config file:
```
./dwtool.py mouse_config profile.json
```

### How was this done ?
I fired up a Windows VM and connected the mouse to the VM. I then installed their official [config software](https://www.dragonwar.jp/product/item/43-G9+3200+DPI+LED+Macro+Gaming+Mouse#download) and started capturing USB packets using Wireshark (running on the host machine) while configuring the mouse using their application.

I analysed the USB command format and data payload in these captured USB packets and eventually reversed the data format for
- setting LED color and pattern
- assigning pre-defined actions to a button
- assigning custom shortcut to a button
- custom MACRO format (_yet to be implemented_)
- assigning custom MACRO to a button (_yet to be implemented_)
