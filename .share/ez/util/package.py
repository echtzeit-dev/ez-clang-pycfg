
import os.path
import re
import sys
import subprocess

from abc import abstractmethod
from typing import List

def unique(items: List[str]):
    return list(dict.fromkeys(items)) # dict is insertion-ordered

def splitPaths(output: str, line_sep: str) -> str:
    return [os.path.normpath(path.strip(' ').strip('\t'))
        for path in output.split(line_sep)
            if len(path) > 0]

class CompilerPackage():
    def __init__(self, path: str):
        self.bin = path
    @abstractmethod
    def parseHeaderSearchPaths(self, extraArgs: List[str]):
        pass

class GCCPackage(CompilerPackage):
    def parseHeaderSearchPaths(self, extraArgs: List[str]) -> List[str]:
        command = [self.bin, '-xc++', '-E', '-v', '/dev/null'] + extraArgs
        try:
            byteOutput = subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=3)
            output = byteOutput.decode(sys.getfilesystemencoding())
            #print(output)
        except subprocess.CalledProcessError as e:
            print('exit code: {}'.format(e.returncode))
            print('stdout: {}'.format(e.output.decode(sys.getfilesystemencoding())))
            print('stderr: {}'.format(e.stderr.decode(sys.getfilesystemencoding())))
            exit(1)

        headerSearchPathsPattern = '#include "..." search starts here:' + '(.*)' + \
                                   '#include <...> search starts here:' + '(.*)' + \
                                   'End of search list'
        match = re.search(headerSearchPathsPattern, output, re.DOTALL)
        quotedIncludes = splitPaths(match.group(1), '\n')
        angleIncludes = splitPaths(match.group(2), '\n')
        return unique(quotedIncludes + angleIncludes)

class LibraryPackage():
    def __init__(self, path):
        assert os.path.isdir(path)
        self.path = path
    @abstractmethod
    def getHeaderSearchPaths(self):
        pass

class FrameworkArduinoSAM(LibraryPackage):
    def getHeaderSearchPaths(self):
        paths = [
            os.path.join(self.path, "cores", "arduino"),
            os.path.join(self.path, "system", "libsam"),
            os.path.join(self.path, "system", "CMSIS", "CMSIS", "Include"),
            os.path.join(self.path, "system", "CMSIS", "Device", "ATMEL"),
            os.path.join(self.path, "variants", "arduino_due_x"),
        ]
        for path in paths: assert os.path.isdir(path) # TODO: exception or so
        return paths

def findCompiler(name: str):
    isExecutable = lambda f: os.path.isfile(f) and os.access(f, os.X_OK)

    # Special handling for PlatformIO packages (should cover all none-eabi triples)
    if name.startswith("toolchain-gcc"):
        if name.startswith("toolchain-gccarmnoneeabi"):
            packageDir = os.path.expanduser(os.path.join("~", ".platformio", "packages", name))
            assert os.path.isdir(packageDir)
            execName = os.path.join(packageDir, "bin", "arm-none-eabi-g++")
            assert isExecutable(execName)
            return GCCPackage(execName)
        raise NotImplementedError("Not yet supported: " + name)

    # Check absolute file name or resolve from PATH
    fpath, fname = os.path.split(name)
    if fpath:
        if isExecutable(name):
            return GCCPackage(name)
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            candidate = os.path.join(path, name)
            if isExecutable(candidate):
                return GCCPackage(candidate)
    raise FileNotFoundError("Failed to find compiler: " + name)

def findLibrary(name: str):
    if name.startswith("framework-arduino-sam"):
        # In docker we ship a custom fork, built with Clang:
        import ez
        packageDir = "/" + os.path.join("usr", "lib", "ez-clang", ez.__version__, "packages", name)
        return FrameworkArduinoSAM(packageDir)
    else:
        packageDir = os.path.expanduser(os.path.join("~", ".platformio", "packages", name))
        return LibraryPackage(packageDir)

def findBossac():
    import os
    fileName = "/".join([os.environ['HOME'], ".platformio/packages/tool-bossac/bossac"])
    if not os.path.exists(fileName):
        raise FileNotFoundError("Upload tool 'bossac' not found: : " + fileName)
    return fileName

def findTeensyTool(fileName: str):
    import os
    fileName = "/".join([os.environ['HOME'], ".platformio/packages/tool-teensy", fileName])
    if not os.path.exists(fileName):
        raise FileNotFoundError("Teensy tool not found: : " + fileName)
    return fileName
