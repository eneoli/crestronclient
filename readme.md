# crestronclient

crestronclient is a Python library for connecting to crestron processors and simulating XPanel requests.
This lib is based on [stealthflyers work](https://github.com/stealthflyer/CrestronXPanelApp) who did the entire CIP stuff

## Usage

```python
# ip, port, pid
c = CrestronClient("127.0.0.1", 41794, 0x03)

# change digital joins
c.send_digital(80, True)

# change analog joins
c.send_analog(51, 5000)

# handle digital and analog join changes

def printme(join, value):
    print('join: ')
    print(join)
    print('value: ')
    print(value)


c.addDigitalCallback(printme)
c.addAnalogCallback(printme)
while True:
    c.poll()

```
