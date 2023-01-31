import ez
import os

from setuptools import setup, find_packages

# setuptools expects to be invoked from within the directory of setup.py, but we
# want to allow `python3 path/to/setup.py install` to work as well:
os.chdir(os.path.dirname(os.path.abspath(__file__)))

setup(
    name = "ez",
    version = ez.__version__,
    author = ez.__author__,
    author_email = ez.__email__,
    url = 'http://echtzeit.dev',
    license = 'MIT',
    license_files = ['LICENSE.TXT'],
    description = "ez-clang Device Layer",
    long_description = "Python configuration layer for ez-clang device connections",
    keywords = "ez-clang bare-metal C++ REPL device layer",
    classifiers=[],
    packages = find_packages(),
    entry_points = {}
)
