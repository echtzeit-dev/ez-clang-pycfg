import ez.io
import ez.repl

import inject
import time
import serial

from abc import abstractmethod
from serial.tools.list_ports_linux import SysFS, comports
from overrides import override
from typing import List

class SerialHandshakeFailedException(ez.repl.HandshakeFailedException):
    def __init__(self, actual: bytes):
        self.actualReceived = " ".join([f"{byte:02x}" for byte in actual])

class Transport(ez.repl.Transport):
    def __init__(self):
        super().__init__()
        self.info = None
        self.stream = None
        self.timeout = 1

    @override(check_signature=False)
    def reset(self, info: SysFS = None) -> SysFS:
        if self.stream:
            self.stream.close()
        self.info = info or self.info
        self.stream = serial.Serial(self.info.device)
        self.stream.timeout = self.timeout
        return self.info

    def awaitToken(self, token: bytes):
        idx = 0
        actual = bytearray()
        while idx < len(token):
            byte = self.stream.read(1)
            if len(byte) == 0:
                raise SerialHandshakeFailedException(actual)
            actual += byte
            if byte[0] == token[idx]:
                idx += 1  # Match: receive next character
            else:
                idx = 0   # Mismatch: start from beginning
        return # Success

    @override
    def finalize(self) -> serial.Serial:
        self.stream.timeout = None
        return self.stream

    def awaitReconnect(self, threshold: float = 3.0) -> SysFS:
        ez.io.note("Await reconnect")
        serialNumber = self.info.serial_number
        port = self.info.device
        start = time.time()
        while time.time() - start < threshold:
            for info in comports():
                if info.serial_number == serialNumber:
                    if info.device == port:
                        # Port didn't change: wait and see
                        break
                    else:
                        # Port changed: reconnect immediately
                        ez.io.note(f"Detected device on new serial port {info.device}")
                        return self.reset(info)
            time.sleep(0.5)
        return self.reset() # Reconnect on same port (best guess)

class SoftResetException(Exception):
    def __init__(self, exitCode: int, commandLine: List[str], output: str):
        super().__init__(
            "Soft reset failed with exit code: " + str(exitCode) +
            "\nCommand line: " + " ".join(commandLine) +
            "\nOutput:\n" + output)

class SerialRecoveryFailedException(ez.repl.RecoveryFailedException):
    def __init__(self, deviceId: str, port: str):
        super().__init__("Failed to recover serial connection to " +
                        f"device at '{port}': {deviceId}")

class Recovery(ez.repl.Recovery):
    @inject.params(transport=ez.repl.Transport)
    def softReset(self, info: SysFS, transport: Transport):
        transport.reset(info)

    @inject.params(transport=ez.repl.Transport)
    def hardReset(self, info: SysFS, transport: Transport):
        with serial.Serial(info.device, 1200, write_timeout=4, timeout=4) as conn:
            ez.io.note("Forcing hard-reset")
            conn.setDTR(True)
            time.sleep(0.022)
            conn.setDTR(False)
        transport.awaitReconnect()

    @inject.params(transport=ez.repl.Transport)
    def awaitHandshake(self, transport: Transport, timeout: float = 5.0) -> bool:
        import sys
        reason = ""
        totalReceived = ""
        waiting = "Connecting: waiting for device response."
        start = time.time()
        while time.time() - start < timeout:
            try:
                transport.handshake()
                sys.stdout.write("\n") if len(waiting) == 1 else None
                return True
            except SerialHandshakeFailedException as ex:
                sys.stdout.write(waiting)
                sys.stdout.flush()
                waiting = "."
                reason = ex.message or reason
                if len(ex.actualReceived) > 0:
                    totalReceived += ex.actualReceived + " "
                continue
            except serial.SerialException as ex:
                break
        sys.stdout.write("\n") if len(waiting) == 1 else None
        message = (reason + "\n") if len(reason) > 0 else ""
        message += "Actual received bytes were: "
        message += totalReceived or "<none>"
        ez.io.error(message)
        return False

    @inject.params(transport=ez.repl.Transport)
    @override(check_signature=False)
    def attemptAutoRecovery(self, transport: Transport) -> bool:
        self.softReset(transport.info)
        return self.awaitHandshake()

    @inject.params(transport=ez.repl.Transport)
    @override(check_signature=False)
    def notifyAutoRecoveryFailed(self, deviceId: str, transport: Transport):
        port = transport.info.device
        ez.io.warning(f"Failed to connect device at '{port}': {deviceId}")

    @inject.params(transport=ez.repl.Transport)
    @override(check_signature=False)
    def negotiateRecovery(self, transport: Transport) -> bool:
        try:
            for attempt in [self.attemptManualReboot, self.attemptReplaceFirmware]:
                try:
                    if attempt(transport):
                        if self.awaitHandshake():
                            return True
                except serial.SerialException as ex:
                    ez.io.error(str(ex))
                    continue
        except ez.io.UserInterruptException as ex:
            ez.io.error(str(ex))
        return False

    @inject.params(transport=ez.repl.Transport)
    @override(check_signature=False)
    def raiseRecoveryFailedException(self, deviceId: str, transport: Transport):
        raise SerialRecoveryFailedException(deviceId, transport.info.device)

    def attemptManualReboot(self, transport: Transport):
        if ez.io.ask("Press reset button manually and try again"):
            transport.awaitReconnect()
            return True
        return False

    def attemptReplaceFirmware(self, transport: Transport):
        try:
            image = self.bundledFirmware()
        except FileNotFoundError as ex:
            ez.io.error(str(ex))
            return False
        if ez.io.ask("Flash bundled firmware and try again", 'ynq'):
            if ez.io.ask("This will delete all code and data from the connected device! Are you sure", 'ynq'):
                self.replaceDeviceFirmware(image)
                transport.awaitReconnect()
                return True
        return False

    @abstractmethod
    def replaceDeviceFirmware(self, image: str):
        raise NotImplementedError("Implement in derived classes")
