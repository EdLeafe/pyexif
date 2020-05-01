#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import json
import os
import re
import six
import subprocess
import sys


INSTALL_EXIFTOOL_INFO = """
Cannot find 'exiftool'.

The ExifEditor class requires that the 'exiftool' command-line
utility is installed in order to work. Information on obtaining
this excellent utility can be found at:

https://exiftool.org
"""


def _runproc(cmd, fpath=None):
    pipe = subprocess.PIPE
    proc = subprocess.Popen([cmd], shell=True, stdin=pipe, stdout=pipe,
            stderr=pipe, close_fds=True)
    proc.wait()
    err = proc.stderr.read()
    if err:
        # See if it's a damaged EXIF directory. If so, fix it and re-try
        if (err.startswith("Warning: Bad ExifIFD directory")
                and fpath is not None):
            fixcmd = ('exiftool -overwrite_original_in_place -all= '
                    '-tagsfromfile @ -all:all -unsafe "{fpath}"'.format(
                    **locals()))
            try:
                _runproc(fixcmd)
            except RuntimeError:
                # It will always raise a warning, so ignore it
                pass
            # Retry
            return _runproc(cmd, fpath)
        elif "exiftool: command not found" in err:
            raise RuntimeError(INSTALL_EXIFTOOL_INFO)
        raise RuntimeError(err)
    else:
        result = proc.stdout.read()
        if isinstance(result, six.binary_type):
            result = result.decode("utf-8")
        return result


class ExifEditor(object):
    def __init__(self, photo=None, save_backup=False, extra_opts=None):
        self.save_backup = save_backup
        extra_opts = extra_opts or []
        if not save_backup:
            extra_opts.append("-overwrite_original_in_place")
        self._optExpr = " ".join(extra_opts)
        if not isinstance(photo, six.string_types):
            photo = photo.decode("utf-8")
        self.photo = photo
        # Tuples of (degrees, mirrored)
        self._rotations = {
                0: (0, 0),
                1: (0, 0),
                2: (0, 1),
                3: (180, 0),
                4: (180, 1),
                5: (90, 1),
                6: (90, 0),
                7: (270, 1),
                8: (270, 0)}
        self._invertedRotations = dict([[v, k] for k, v in self._rotations.items()])
        # DateTime patterns
        self._datePattern = re.compile(r"\d{4}:[01]\d:[0-3]\d$")
        self._dateTimePattern = re.compile(r"\d{4}:[01]\d:[0-3]\d [0-2]\d:[0-5]\d:[0-5]\d$")
        self._badTagPat = re.compile(r"Warning: Tag '[^']+' does not exist")

        super(ExifEditor, self).__init__()


    def rotateCCW(self, num=1, calc_only=False):
        """Rotate left in 90 degree increments"""
        return self._rotate(-90 * num, calc_only)


    def rotateCW(self, num=1, calc_only=False):
        """Rotate right in 90 degree increments"""
        return self._rotate(90 * num, calc_only)


    def getOrientation(self):
        """Returns the current Orientation tag number."""
        return self.getTag("Orientation#", 1)


    def _rotate(self, deg, calc_only=False):
        currOrient = self.getOrientation()
        currRot, currMirror = self._rotations[currOrient]
        dummy, newRot = divmod(currRot + deg, 360)
        currOrient = self.getOrientation()
        currRot, currMirror = self._rotations[currOrient]
        dummy, newRot = divmod(currRot + deg, 360)
        newOrient = self._invertedRotations[(newRot, currMirror)]
        if calc_only:
            return newOrient
        self.setOrientation(newOrient)


    def mirrorVertically(self):
        """Flips the image top to bottom."""
        # First, rotate 180
        currOrient = self.rotateCW(2, calc_only=True)
        currRot, currMirror = self._rotations[currOrient]
        newMirror = currMirror ^ 1
        newOrient = self._invertedRotations[(currRot, newMirror)]
        self.setOrientation(newOrient)


    def mirrorHorizontally(self):
        """Flips the image left to right."""
        currOrient = self.getOrientation()
        currRot, currMirror = self._rotations[currOrient]
        newMirror = currMirror ^ 1
        newOrient = self._invertedRotations[(currRot, newMirror)]
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
        if isinstance(ret, six.string_types):
            return [ret]
        return sorted(ret)


    def setKeywords(self, kws):
        """Sets the image's keyword list to the passed list of strings. Any
        existing keywords are overwritten.
        """
        self.clearKeywords()
        self.addKeywords(kws)


    def clearKeywords(self):
        """Removes all keywords from the image."""
        self.setTag("Keywords", "")


    def clearKeyword(self, kw):
        """Removes a single keyword from the image. If the keyword does not
        exist, this call is a no-op.
        """
        kws = self.getKeywords()
        try:
            kws.remove(kw)
        except ValueError:
            pass
        self.setKeywords(kws)


    def getTag(self, tag, default=None):
        """Returns the value of the specified tag, or the default value
        if the tag does not exist.
        """
        cmd = """exiftool -j -d "%Y:%m:%d %H:%M:%S" -{tag} "{self.photo}" """.format(**locals())
        out = _runproc(cmd, self.photo)
        info = json.loads(out)[0]
        ret = info.get(tag, default)
        return ret


    def getTags(self, just_names=False, include_empty=True):
        """Returns a list of all the tags for the current image."""
        cmd = """exiftool -j -d "%Y:%m:%d %H:%M:%S" "{self.photo}" """.format(**locals())
        out = _runproc(cmd, self.photo)
        info = json.loads(out)[0]
        if include_empty:
            if just_names:
                ret = list(info.keys())
            else:
                ret = list(info.items())
        else:
            # Exclude those tags with empty values
            if just_names:
                ret = [tag for tag in info.keys() if info.get(tag)]
            else:
                ret = [(tag, val) for tag, val in info.items() if val]
        return sorted(ret)


    def getDictTags(self, include_empty=True):
        """Returns a dict of all the tags for the current image, with the tag
        name as the key and the tag value as the value.
        """
        tags = self.getTags(include_empty=include_empty)
        return {k: v for k, v in tags}


    def setTag(self, tag, val):
        """Sets the specified tag to the passed value. You can set multiple values
        for the same tag by passing those values in as a list.
        """
        if not isinstance(val, (list, tuple)):
            val = [val]
        vallist = ['-{0}="{1}"'.format(tag,
            v.replace('"', '\\"') if isinstance(v, six.string_types) else v) for v in val]
        valstr = " ".join(vallist)
        cmd = """exiftool {self._optExpr} {valstr} "{self.photo}" """.format(**locals())
        try:
            out = _runproc(cmd, self.photo)
        except RuntimeError as e:
            err = "{0}".format(e).strip()
            if self._badTagPat.match(err):
                print("Tag '{tag}' is invalid.".format(**locals()))
            else:
                raise


    def setTags(self, tags_dict):
        """Sets the specified tags_dict ({tag: val, tag_n: val_n}) tag value combinations.
        Used to set more than one tag, val value in a single call.
        """
        if not isinstance(tags_dict, dict):
            raise TypeError('tags_dict is not instance of dict')
        vallist = []
        for tag in tags_dict:
            val = tags_dict[tag]
            # escape double quotes in case of string type
            if isinstance(val, six.string_types):
                val = val.replace('"', '\\"')
            vallist.append('-{0}="{1}"'.format(tag, val))
        valstr = " ".join(vallist)
        cmd = """exiftool {self._optExpr} {valstr} "{self.photo}" """.format(**locals())
        try:
            out = _runproc(cmd, self.photo)
        except RuntimeError as e:
            err = "{0}".format(e).strip()
            if self._badTagPat.match(err):
                print("Tag '{tag}' is invalid.".format(**locals()))
            else:
                raise


    def getOriginalDateTime(self):
        """Get the image's original date/time value (i.e., when the picture
        was 'taken').
        """
        return self._getDateTimeField("DateTimeOriginal")


    def setOriginalDateTime(self, dttm=None):
        """Set the image's original date/time (i.e., when the picture
        was 'taken') to the passed value. If no value is passed, set
        it to the current datetime.
        """
        self._setDateTimeField("DateTimeOriginal", dttm)


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
    print("""
To use this module, create an instance of the ExifEditor class, passing
in a path to the image to be handled. You may also pass in whether you 
want the program to automatically keep a backup of your original photo
(default=False). If a backup is created, it will be in the same location
as the original, with "_ORIGINAL" appended to the file name.

Once you have an editor instance, you call its methods to get information
about the image, or to modify the image's metadata.
""")


if __name__ == "__main__":
    usage()
