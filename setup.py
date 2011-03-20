from distutils.core import setup

long_desc = """Python module for working with EXIF image data.

It does its work mainly though the command-line "exiftool", which is required for this module to work. Information on obtaining and installing exiftool are in the README file.
"""

setup(
    name="pyexif", version="0.2",
    url="https://leafe.com/pyexif",
    author="Ed Leafe",
    author_email="ed@leafe.com",
    description="Python module to read/write EXIF image data",
    long_description=long_desc,
    license="Python Software Foundation License",
    keywords="exif image metadata photo",
    py_modules=["pyexif"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Utilities",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: Python Software Foundation License",
        ],
    )
