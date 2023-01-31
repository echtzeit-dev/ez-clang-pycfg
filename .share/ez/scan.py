from os import path, listdir
from serial.tools.list_ports_linux import comports
from ez.util.script import Script

import ez.io

def scan(input: str) -> Script:
  if '@' in input:
    id, transport = input.split('@')

    if transport == "qemu":
      return runQemu(id)

    # ez-clang --connect="due@localhost:10819"
    elif ':' in transport:
      if len(transport.split(':')) != 2:
        ez.io.error(f"Invalid network address: {transport}")
        return None
      return scanSocket(id, transport)

    # ez-clang --connect="due@/dev/ttyACM0"
    elif path.exists(transport):
      return scanSerial(id, transport)

  # ez-clang --connect="qemu" (we have only one implementation right now)
  elif input == "qemu":
    return runQemu("lm3s811")

  # ez-clang --connect="/dev/ttyACM0"
  elif path.exists(input):
    return scanSerialFindPort(input)

  # ez-clang --connect="due"
  else:
    return scanSerialFindId(input)

def resourceDir():
  from pathlib import Path
  resdir = Path(__file__).parent.parent.parent.resolve()
  assert '.share' in listdir(resdir), "Device resource directory invalid"
  return resdir

# Special-case fallback for teensy devices. After hard reset they happen to come
# back as HID devices. We won't find them via regular port scanning. However,
# the teensy-specific loader knows how to do it.
# TODO: Find a better way or ask the user for permission!
def pokeTeensy(id: str):
    # Construct command line for loader
    firmware = path.join(resourceDir(), id, "firmware.hex")
    if not path.exists(firmware):
        return
    import ez.util.package
    tool = ez.util.package.findTeensyTool('teensy_loader_cli')
    upload = [tool, '-mmcu=mkl26z64', '-w', '-s', '-v', firmware]

    # Run the loader *fingers-crossed*
    import subprocess
    try:
        ez.io.note("Uploading new firmware")
        subprocess.run(upload, capture_output=True, check=True)
    except subprocess.CalledProcessError as ex:
        raise ez.repl.ReplaceFirmwareException(ex.returncode, upload,
                                              ex.output.decode())

# E.g. "/dev/ttyACM0"
def scanSerialFindPort(port: str):
  infos = [dev for dev in comports() if dev.device == port]
  if len(infos) == 0:
    ez.io.error(f"Cannot open serial port: {port}")
    return None
  resdir = resourceDir()
  subdirs = filter(path.isdir, [path.join(resdir, f) for f in listdir(resdir)])
  for id in subdirs:
    file = path.join(id, "serial.py")
    if path.exists(file) and path.isfile(file):
      script = Script(file, f"{id}.serial")
      if script.accept(infos[0]):
        return script
  ez.io.error(f"Unknown device: {infos[0]}")
  return None

# E.g. "due"
def scanSerialFindId(id: str):
  file = path.join(resourceDir(), id, "serial.py")
  if path.exists(file) and path.isfile(file):
    script = Script(file, f"{id}.serial")
    for info in comports():
      if script.accept(info):
        return script
  # Special-case fallback for teensy devices
  if id == 'teensylc':
    pokeTeensy(id)
    for info in comports():
      if script.accept(info):
        return script
  ez.io.error(f"Failed to find device ID: {id}")
  return None

# E.g. "due", "/dev/ttyACM0"
def scanSerial(id: str, port: str):
  file = path.join(resourceDir(), id, "serial.py")
  if not path.exists(file):
    ez.io.error(f"Cannot find script for serial connection: {file}")
    return None
  if not path.isfile(file):
    ez.io.error(f"Path to serial connection script is not a file: {file}")
    return None
  infos = [dev for dev in comports() if dev.device == port]
  if len(infos) == 0:
    ez.io.error(f"Cannot open serial port: {port}")
    return None
  script = Script(file, f"{id}.serial")
  if not script.accept(infos[0]):
    ez.io.error(f"Serial connection script {file} rejected port: {port}")
    return None
  return script

# E.g. "due", "localhost:10819"
def scanSocket(id: str, address: str):
  file = path.join(resourceDir(), id, "socket.py")
  if not path.exists(file):
    ez.io.error(f"Cannot find script for socket connection: {file}")
    return None
  if not path.isfile(file):
    ez.io.error(f"Path to socket connection script is not a file: {file}")
    return None
  script = Script(file, f"{id}.socket")
  return script if script.accept(address) else None

# E.g. "lm3s811"
def runQemu(id: str):
  file = path.join(resourceDir(), id, "qemu.py")
  if not path.exists(file):
    ez.io.error(f"Cannot find script for qemu session: {file}")
    return None
  if not path.isfile(file):
    ez.io.error(f"Path to qemu script is not a file: {file}")
    return None
  script = Script(file, f"{id}.qemu")
  if not script.accept(id):
    ez.io.error(f"Device ID {id} rejected from qemu script: {file}")
    return None
  return script
