from distutils.core import setup

long_desc = """Python module for working with EXIF image data.

It does its work mainly though the command-line "exiftool", which is required for this module to work. Information on obtaining and installing exiftool are in the README file.
"""

setup(name="pyexif", version="0.2",
      url="https://leafe.com/pyexif",
      author="Ed Leafe",
      author_email="ed@leafe.com",
      description="Python module to read/write EXIF image data",
      long_description=long_desc,
      py_modules=["pyexif"])
