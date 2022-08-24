#!/usr/bin/env python
# -*- coding: utf-8 -*-

import copy
import datetime
import json
import re
from subprocess import Popen, PIPE


INSTALL_EXIFTOOL_INFO = """
Cannot find 'exiftool'.

The ExifEditor class requires that the 'exiftool' command-line
utility is installed in order to work. Information on obtaining
this excellent utility can be found at:

https://exiftool.org
"""


def _runproc(cmd, fpath=None, wait=True, retry=True):
    """Runs the specified `cmd` in a separate process. If `wait` is False, returns the process
    immediately. If `wait` is True, it waits for the process to complete, and returns the content of
    stdout.
    """
    kwargs = dict(stdin=PIPE, stdout=PIPE, stderr=PIPE) if wait else {}
    # pylint: disable=consider-using-with
    proc = Popen(cmd, shell=True, close_fds=True, **kwargs)
    if wait:
        stdout_bytes, stderr_bytes = proc.communicate()
        stdout = stdout_bytes.decode("utf-8")
        stderr = stderr_bytes.decode("utf-8")
        if stderr:
            # See if it's a damaged EXIF directory. If so, fix it and re-try
            if stderr.startswith("Warning: Bad ExifIFD directory") and fpath is not None and retry:
                fixcmd = (
                    "exiftool -overwrite_original_in_place -all= -tagsfromfile @ -all:all "
                    f'-unsafe "{fpath}"'
                )
                try:
                    _runproc(fixcmd, retry=False)
                except RuntimeError:
                    # It will always raise a warning, so ignore it
                    pass
                # Retry
                return _runproc(cmd, fpath, retry=False)
            if stderr.startswith("Warning:"):
                # Ignore
                print(stderr)
                stderr = ""
            elif "exiftool: command not found" in stderr:
                raise RuntimeError(INSTALL_EXIFTOOL_INFO) from None
    if stderr:
        raise RuntimeError(stderr) from None
    return stdout


class ExifEditor:
    def __init__(self, photo=None, save_backup=False, extra_opts=None):
        self.save_backup = save_backup
        extra_opts = extra_opts or []
        if isinstance(extra_opts, str):
            extra_opts = [extra_opts]
        ops = copy.deepcopy(extra_opts)
        if not save_backup:
            ops.append("-overwrite_original_in_place")
        self._optExpr = " ".join(ops)
        if isinstance(photo, bytes):
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
            8: (270, 0),
        }
        self._invertedRotations = {v: k for k, v in self._rotations.items()}
        # DateTime patterns
        self._datePattern = re.compile(r"\d{4}:[01]\d:[0-3]\d$")
        self._dateTimePattern = re.compile(r"\d{4}:[01]\d:[0-3]\d [0-2]\d:[0-5]\d:[0-5]\d$")
        self._badTagPat = re.compile(r"Warning: Tag '[^']+' does not exist")

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
        if deg % 90:
            raise ValueError(f"Rotations must be multiples of 90 degrees, got {deg}")
        currOrient = self.getOrientation()
        currRot, currMirror = self._rotations[currOrient]
        _, newRot = divmod(currRot + deg, 360)
        newOrient = self._invertedRotations[(newRot, currMirror)]
        if calc_only:
            return newOrient
        self.setOrientation(newOrient)
        return None

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
        cmd = f"""exiftool {self._optExpr} -Orientation#='{val}' "{self.photo}" """
        _runproc(cmd, fpath=self.photo)

    def addKeyword(self, kw):
        """Add the passed string to the image's keyword tag, preserving existing keywords."""
        self.addKeywords([kw])

    def addKeywords(self, kws):
        """Add the passed list of strings to the image's keyword tag, preserving existing keywords."""

        def esc_space(val):
            return val.replace(" ", r"\ ").replace("&", r"\&")

        kws = [f"-iptc:keywords+={esc_space(kw)}" for kw in kws]
        kwopt = " ".join(kws)
        cmd = f'exiftool {self._optExpr} {kwopt} "{self.photo}" '
        _runproc(cmd, fpath=self.photo)

    def getKeywords(self):
        """Returns the current keywords for the image as a list."""
        ret = self.getTag("Keywords")
        if not ret:
            return []
        if isinstance(ret, str):
            return [ret]
        return sorted([str(kw) for kw in ret])

    def setKeywords(self, kws):
        """Sets the image's keyword list to the passed list of strings. Any existing keywords are
        overwritten.
        """
        self.clearKeywords()
        self.addKeywords(kws)

    def clearKeywords(self):
        """Removes all keywords from the image."""
        self.setTag("Keywords", "")

    def removeKeyword(self, kw):
        """Remove a single keyword from the image. If the keyword does not exist, this call is a
        no-op.
        """
        self.removeKeywords([kw])

    def removeKeywords(self, kws):
        """Removes multiple keywords from the image. If any keyword does not exist, it is
        ignored.
        """
        curr = self.getKeywords()
        for kw in kws:
            try:
                curr.remove(kw)
            except ValueError:
                pass
        self.setKeywords(curr)

    def getTag(self, tag, default=None):
        """Returns the value of 'tag', or the default value if the tag does not exist."""
        cmd = f'exiftool -j -d "%Y:%m:%d %H:%M:%S" -{tag} "{self.photo}" '
        out = _runproc(cmd, fpath=self.photo)
        info = json.loads(out)[0]
        ret = info.get(tag, default)
        return ret

    def getTags(self, just_names=False, include_empty=True):
        """Returns a list of all the tags for the current image."""
        cmd = f'exiftool -j -d "%Y:%m:%d %H:%M:%S" "{self.photo}" '
        out = _runproc(cmd, fpath=self.photo)
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
        """Returns a dict of all the tags for the current image, with the tag name as the key and
        the tag value as the value.
        """
        tags = self.getTags(include_empty=include_empty)
        return dict(tags)

    def setTag(self, tag, val):
        """Sets the specified tag to the passed value. You can set multiple values for the same tag
        by passing those values in as a list.
        """
        if not isinstance(val, (list, tuple)):
            val = [val]

        def esc_quote(val):
            return val.replace('"', '\\"') if isinstance(val, str) else val

        vallist = [f'-{tag}="{esc_quote(v)}"' for v in val]
        valstr = " ".join(vallist)
        cmd = f'exiftool {self._optExpr} {valstr} "{self.photo}" '
        try:
            _runproc(cmd, fpath=self.photo)
        except RuntimeError as e:
            err = f"{e}".strip()
            if self._badTagPat.match(err):
                print(f"Tag '{tag}' is invalid.")
            else:
                raise

    def setTags(self, tags_dict):
        """Sets the specified tags_dict ({tag: val, tag_n: val_n}) tag value combinations. Used to
        set more than one tag, val value in a single call.
        """
        if not isinstance(tags_dict, dict):
            raise TypeError("'tags_dict' parameter is not instance of dict")
        vallist = []
        for tag in tags_dict:
            val = tags_dict[tag]
            # escape double quotes in case of string type
            if isinstance(val, str):
                val = val.replace('"', '\\"')
            vallist.append(f'-{tag}="{val}"')
        valstr = " ".join(vallist)
        cmd = f'exiftool {self._optExpr} {valstr} "{self.photo}" '
        try:
            _runproc(cmd, fpath=self.photo)
        except RuntimeError as e:
            err = f"{e}".strip()
            if self._badTagPat.match(err):
                print(f"Tag '{tag}' is invalid.")
            else:
                raise

    def getOriginalDateTime(self):
        """Get the image's original date/time value (i.e., when the picture was 'taken')."""
        return self._getDateTimeField("DateTimeOriginal")

    def setOriginalDateTime(self, dttm=None):
        """Set the image's original date/time (i.e., when the picture was 'taken') to the passed
        value. If no value is passed, set it to the current datetime.
        """
        self._setDateTimeField("DateTimeOriginal", dttm)

    def getModificationDateTime(self):
        """Get the image's modification date/time value."""
        return self._getDateTimeField("FileModifyDate")

    def setModificationDateTime(self, dttm=None):
        """Set the image's modification date/time to the passed value. If no value is passed, set
        it to the current datetime (i.e., like 'touch'.
        """
        self._setDateTimeField("FileModifyDate", dttm)

    def _getDateTimeField(self, fld):
        """Generic getter for datetime values."""
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
        cmd = f"""exiftool {self._optExpr} -{fld}='{dtstring}' "{self.photo}" """
        _runproc(cmd, fpath=self.photo)

    def _formatDateTime(self, dt):
        """Accepts a string representation of a date or datetime, and returns a string correctly
        formatted for EXIF datetimes.
        """
        if self._datePattern.match(dt):
            # Add the time portion
            return f"{dt} 00:00:00"
        if self._dateTimePattern.match(dt):
            # Leave as-is
            return dt
        raise ValueError(f"Incorrect datetime value '{dt}' received") from None


def usage():
    print(
        """
To use this module, create an instance of the ExifEditor class, passing
in a path to the image to be handled. You may also pass in whether you
want the program to automatically keep a backup of your original photo
(default=False). If a backup is created, it will be in the same location
as the original, with "_ORIGINAL" appended to the file name.

Once you have an editor instance, you call its methods to get information
about the image, or to modify the image's metadata.
"""
    )


if __name__ == "__main__":
    usage()
