from distutils.core import setup
from os import path

long_desc = path.join(path.dirname(__file__), "README")

setup(name="pyexif", version="0.2",
      url="https://leafe.com/pyexif",
      author="Ed Leafe",
      author_email="ed@leafe.com",
      description="Python module for read/write of EXIF image data",
      long_description=long_desc,
      py_modules=["pyexif"])
