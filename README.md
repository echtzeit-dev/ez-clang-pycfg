# ez-clang: Python Device Configuration Layer

Python implementation of the ez-clang RPC protocol, that handles all target device communication:
* Connectivity: device traversal, handshake, serialization
* Transport: USB serial, TCP sockets or pipes for a QEMU subprocess
* Configuration: target CPU, memory ranges, compile flags, libraries, etc.

Supported devices in release 0.0.6:
* USB Serial: Ardunio Due, Adafruit Metro M0, TeensyLC
* TCP Socket: Raspberry Pi Models 2b and 3b (in 32-bit mode)
* QEMU: Stellaris LM3S811

## Install

Clone project and install required packages as well as `ez` Python package from source tree:
```
> git clone https://github.com/echtzeit-dev/ez-clang-pycfg
> cd ez-clang-pycfg
> python3 --version
Python 3.8.10
> python3 -m pip install -e .share
> python3 -m pip install -r requirements.txt
```

## Test

Run tests against a device firmware:
```
> python3 due/test/run_all.py
Found compatible device at /dev/ttyACM2
Device unique identifier: 7503130343135130F0A0
Uploading firmware: /usr/lib/ez-clang/0.0.6/firmware/due/firmware.bin
Running tests from /usr/lib/ez-clang/0.0.6/pycfg/due/test
Selecting 8 out of 9 discovered tests
  [basics] connect ........................................ 4.51s
  [basics] setup .......................................... 4.52s
  [basics] connect_setup_repeat ........................... 9.02s
  [endpoints] ez.rpc.lookup ............................... 9.07s
  [endpoints] ez.rpc.commit ............................... 5.46s
  [endpoints] ez.rpc.execute .............................. 5.02s
  [endpoints] memory.read.cstr ............................ 5.43s
  [recovery] replace_firmware ............................. 19.96s

Testing Time: 88.65s
  Disabled: 1
  Excluded: 0
  Failed  : 0
  Passed  : 8

SUCCESS
```

Run a single test standalone:
```
> python3 due/test/00-basics/01-connect.py
Found compatible device at /dev/ttyACM0
> echo $?
0
```

Options:
```
$ python3 due/test/run_all.py --help
usage: run_all.py [-h] [--connect CONNECT] [--firmware FIRMWARE] [--no-firmware] [--timeout TIMEOUT] [--filter REGEX] [--filter-out REGEX]

optional arguments:
  -h, --help           show this help message and exit
  --connect CONNECT    Serial port of target device
  --firmware FIRMWARE  File name of the firmware image for the target device
  --no-firmware        Don't upload a new firmware image to the target device
  --timeout TIMEOUT    Maximum duration for running a single test
  --filter REGEX       Only run tests with paths matching the given regular expression
  --filter-out REGEX   Filter out tests with paths matching the given regular expression
```
