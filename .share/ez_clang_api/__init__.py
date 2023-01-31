"""ez-clang device connection embedded API"""

__author__ = 'Stefan Gränitz'
__email__ = 'stefan.graenitz@gmail.com'
__versioninfo__ = (0, 0, 6)
__version__ = '.'.join(str(v) for v in __versioninfo__) + 'dev'

from typing import List

# Fake definitions for code completion, testing and documentation.
# In embedded mode ez-clang injects actual definitions.
class Device:
    def __init__(self):
        self.name: str = None
        self.transport: str = None
        self.triple: str = None
        self.cpu: str = None
        self.page_size: int = 0
        self.default_alignment: int = 0
        self.flags: List[str] = []
        self.header_search_paths: List[str] = []
        self.archive_search_paths: List[str] = []
    def define(self, symbol: str, address: int):
        pass
    def setCodeBuffer(self, address: int, size: int):
        pass

class Host:
    @staticmethod
    def debugQemu():
        return False # Don't wait for debugger in tests
    @staticmethod
    def debugPython(debugable: bool):
        return False # Don't wait for debugger in tests
    @staticmethod
    def forwardIO():
        return False # Read/write to terminal in tests
    @staticmethod
    def readInput():
        raise NotImplementedError("Typically not needed in tests")
    @staticmethod
    def writeOutput():
        raise NotImplementedError("Typically not needed in tests")
    @staticmethod
    def verbose():
        return [ 'rpc_bytes', 'rpc_text' ]
    def addDevice(self, dev: Device) -> bool:
        dev.name = dev.name or "unknown-device"
        dev.triple = dev.name or "arm-none-eabi"
        dev.cpu = dev.name or "cortex-m3"
        dev.page_size = dev.page_size or 256
        dev.default_alignment = dev.default_alignment or 32
        dev.header_search_paths += [ "due/include" ]
        dev.archive_search_paths += [ "due/lib" ]
        return True
    def formatResult(self, mem: bytes):
        raise NotImplementedError("In tests override for specific type")
    def getResultDeclTypeAsString(self):
        raise NotImplementedError("In tests override for specific type")
    def timeoutConnect(self):
        return 1.0
