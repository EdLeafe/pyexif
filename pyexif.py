#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import json
import os
import re
import subprocess
import sys


def _install_exiftool_info():
    print  """
Cannot find 'exiftool'.

The ExifEditor class requires that the 'exiftool' command-line
utility is installed in order to work. Information on obtaining
this excellent utility can be found at:

http://www.sno.phy.queensu.ca/~phil/exiftool/
"""


def _runproc(cmd, fpath=None):
    if not _EXIFTOOL_INSTALLED:
        _install_exiftool_info()
        raise RuntimeError("Running this class requires that exiftool is installed")
    pipe = subprocess.PIPE
    proc = subprocess.Popen([cmd], shell=True, stdin=pipe, stdout=pipe,
            stderr=pipe, close_fds=True)
    proc.wait()
    err = proc.stderr.read()
    if err:
        # See if it's a damaged EXIF directory. If so, fix it and re-try
        if err.startswith("Warning: Bad ExifIFD directory") and fpath is not None:
            fixcmd = """exiftool -overwrite_original_in_place -all= -tagsfromfile @ -all:all -unsafe "{fpath}" """.format(**locals())
            try:
                _runproc(fixcmd)
            except RuntimeError:
                # It will always raise a warning, so ignore it
                pass
            # Retry
            return _runproc(cmd, fpath)
        raise RuntimeError(err)
    else:
        return proc.stdout.read()


# Test that the exiftool is installed
_EXIFTOOL_INSTALLED = True
try:
    out = _runproc("exiftool some_dummy_name.jpg")
except RuntimeError as e:
    # If the tool is installed, the error should be 'File not found'.
    # Otherwise, assume it isn't installed.
    err = "{0}".format(e).strip()
    if "File not found:" not in err:
        _EXIFTOOL_INSTALLED = False
        _install_exiftool_info()



class ExifEditor(object):
    def __init__(self, photo=None, save_backup=False):
        self.save_backup = save_backup
        if not save_backup:
            self._optExpr = "-overwrite_original_in_place"
        else:
            self._optExpr = ""
        self.photo = photo
        # Tuples of (degrees, mirrored)
        self.rotations = {
                0: (0, 0),
                1: (0, 0),
                2: (0, 1),
                3: (180, 0),
                4: (180, 1),
                5: (90, 1),
                6: (90, 0),
                7: (270, 1),
                8: (270, 0)}
        self.invertedRotations = dict([[v, k] for k, v in self.rotations.items()])
        self.rotationStates = {0: (1, 2), 90: (5, 6),
                180: (3, 4), 270: (7, 8)}
        self.mirrorStates = (2, 4, 5, 7)
        # DateTime patterns
        self._datePattern = re.compile(r"\d{4}:[01]\d:[0-3]\d$")
        self._dateTimePattern = re.compile(r"\d{4}:[01]\d:[0-3]\d [0-2]\d:[0-5]\d:[0-5]\d$")
        self._badTagPat = re.compile(r"Warning: Tag '[^']+' does not exist")

        super(ExifEditor, self).__init__()


    def rotateCCW(self, num=1):
        """Rotate left in 90 degree incrementss"""
        self._rotate(-90 * num)


    def rotateCW(self, num=1):
        """Rotate right in 90 degree incrementss"""
        self._rotate(90 * num)


    def getOrientation(self):
        """Returns the current Orientation tag number."""
        return self.getTag("Orientation#", 1)


    def _rotate(self, deg):
        currOrient = self.getOrientation()
        currRot, currMirror = self.rotations[currOrient]
        dummy, newRot = divmod(currRot + deg, 360)
        newOrient = self.invertedRotations[(newRot, currMirror)]
        self.setOrientation(newOrient)


    def mirrorVertically(self):
        """Flips the image top to bottom."""
        # First, rotate 180
        self.rotateCW(2)
        currOrient = self.getOrientation()
        currRot, currMirror = self.rotations[currOrient]
        newMirror = currMirror ^ 1
        newOrient = self.invertedRotations[(currRot, newMirror)]
        self.setOrientation(newOrient)


    def mirrorHorizontally(self):
        """Flips the image left to right."""
        currOrient = self.getOrientation()
        currRot, currMirror = self.rotations[currOrient]
        newMirror = currMirror ^ 1
        newOrient = self.invertedRotations[(currRot, newMirror)]
        self.setOrientation(newOrient)


    def setOrientation(self, val):
        """Orientation codes:
               Rot    Img
            1:   0    Normal
            2:   0    Mirrored
            3: 180    Normal
            4: 180    Mirrored
            5: +90    Mirrored
            6: +90    Normal
            7: -90    Mirrored
            8: -90    Normal
        """
        cmd = """exiftool {self._optExpr} -Orientation#='{val}' "{self.photo}" """.format(**locals())
        _runproc(cmd, self.photo)


    def addKeyword(self, kw):
        """Add the passed string to the image's keyword tag, preserving existing keywords."""
        self.addKeywords([kw])


    def addKeywords(self, kws):
        """Add the passed list of strings to the image's keyword tag, preserving
        existing keywords.
        """
        kws = ["-iptc:keywords+={0}".format(kw.replace(" ", r"\ ")) for kw in kws]
        kwopt = " ".join(kws)
        cmd = """exiftool {self._optExpr} {kwopt} "{self.photo}" """.format(**locals())
        _runproc(cmd, self.photo)


    def getKeywords(self):
        """Returns the current keywords for the image as a list."""
        ret = self.getTag("Keywords")
        if not ret:
            return []
        if isinstance(ret, basestring):
            return [ret]
        return ret


    def setKeywords(self, kws):
        """Sets the image's keyword list to the passed list of strings. Any existing
        keywords are overwritten.
        """
        self.clearKeywords()
        self.addKeywords(kws)


    def clearKeywords(self):
        """Removes all keywords from the image."""
        self.setTag("Keywords", "")


    def getTag(self, tag, default=None):
        """Returns the value of the specified tag, or the default value
        if the tag does not exist.
        """
        cmd = """exiftool -j -d "%Y:%m:%d %H:%M:%S" -{tag} "{self.photo}" """.format(**locals())
        out = _runproc(cmd, self.photo)
        info = json.loads(out)[0]
        ret = info.get(tag, default)
        return ret


    def setTag(self, tag, val):
        """Sets the specified tag to the passed value. You can set multiple values
        for the same tag by passing those values in as a list.
        """
        if not isinstance(val, (list, tuple)):
            val = [val]
        vallist = ["-{0}={1}".format(tag, v) for v in val]
        valstr = " ".join(vallist)
        cmd = """exiftool {self._optExpr} {valstr} "{self.photo}" """.format(**locals())
        try:
            out = _runproc(cmd, self.photo)
        except RuntimeError as e:
            err = "{0}".format(e).strip()
            if self._badTagPat.match(err):
                print "Tag '{tag}' is invalid.".format(**locals())
            else:
                raise


    def getOriginalDateTime(self):
        """Get the image's original date/time value (i.e., when the picture
        was 'taken').
        """
        self._getDateTimeField("DateTimeOriginal")


    def setOriginalDateTime(self, dttm=None):
        """Set the image's original date/time (i.e., when the picture
        was 'taken') to the passed value. If no value is passed, set
        it to the current datetime.
        """
        return self._setDateTimeField("DateTimeOriginal", dttm)


    def getModificationDateTime(self):
        """Get the image's modification date/time value."""
        return self._getDateTimeField("FileModifyDate")


    def setModificationDateTime(self, dttm=None):
        """Set the image's modification date/time to the passed value.
        If no value is passed, set it to the current datetime (i.e.,
        like 'touch'.
        """
        self._setDateTimeField("FileModifyDate", dttm)


    def _getDateTimeField(self, fld):
        """Generic getter for datetime values."""
        # Convert to string format if needed
#         if isinstance(dttm, (datetime.datetime, datetime.date)):
#             dtstring = dttm.strftime("%Y:%m:%d %H:%M:%S")
#         else:
#             dtstring = self._formatDateTime(dttm)
        ret = self.getTag(fld)
        if ret is not None:
            # It will be a string in exif std datetime format
            ret = datetime.datetime.strptime(ret, "%Y:%m:%d %H:%M:%S")
        return ret


    def _setDateTimeField(self, fld, dttm):
        """Generic setter for datetime values."""
        if dttm is None:
            dttm = datetime.datetime.now()
        # Convert to string format if needed
        if isinstance(dttm, (datetime.datetime, datetime.date)):
            dtstring = dttm.strftime("%Y:%m:%d %H:%M:%S")
        else:
            dtstring = self._formatDateTime(dttm)
        cmd = """exiftool {self._optExpr} -{fld}='{dtstring}' "{self.photo}" """.format(**locals())
        _runproc(cmd, self.photo)


    def _formatDateTime(self, dt):
        """Accepts a string representation of a date or datetime,
        and returns a string correctly formatted for EXIF datetimes.
        """
        if self._datePattern.match(dt):
            # Add the time portion
            return "{0} 00:00:00".format(dt)
        elif self._dateTimePattern.match(dt):
            # Leave as-is
            return dt
        else:
            raise ValueError("Incorrect datetime value '{0}' received".format(dt))


def usage():
    print """
To use this module, create an instance of the ExifEditor class, passing
in a path to the image to be handled. You may also pass in whether you 
want the program to automatically keep a backup of your original photo
(default=False). If a backup is created, it will be in the same location
as the original, with "_ORIGINAL" appended to the file name.

Once you have an editor instance, you call its methods to get information
about the image, or to modify the image's metadata.
"""


if __name__ == "__main__":
    usage()
