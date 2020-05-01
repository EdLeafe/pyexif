from setuptools import setup

long_desc = """Python module for working with EXIF image data.

It does its work mainly though the command-line "exiftool", which is required
for this module to work. Information on obtaining and installing exiftool are
in the README file.
"""

setup(
    name="pyexif",
    version="0.9.0",
    url="https://github.com/EdLeafe/pyexif",
    download_url = "https://github.com/EdLeafe/pyexif/archive/0.9.0.tar.gz",
    author="Ed Leafe",
    author_email="ed@leafe.com",
    description="Python module to read/write EXIF image data",
    license="apache-2.0",
    keywords="exif image metadata photo photography",
    install_requires=["six"],
    packages=["pyexif"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Utilities",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Natural Language :: English",
        "Topic :: Multimedia :: Graphics",
        ],
    )
