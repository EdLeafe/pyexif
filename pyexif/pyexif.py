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
        self._opt_expr = " ".join(ops)
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
        self._inverted_rotations = {v: k for k, v in self._rotations.items()}
        # DateTime patterns
        self._date_pattern = re.compile(r"\d{4}:[01]\d:[0-3]\d$")
        self._date_time_pattern = re.compile(r"\d{4}:[01]\d:[0-3]\d [0-2]\d:[0-5]\d:[0-5]\d$")
        self._bad_tag_pat = re.compile(r"Warning: Tag '[^']+' does not exist")

    def rotate_CCW(self, num=1, calc_only=False):
        """Rotate left in 90 degree increments"""
        return self._rotate(-90 * num, calc_only)

    def rotate_CW(self, num=1, calc_only=False):
        """Rotate right in 90 degree increments"""
        return self._rotate(90 * num, calc_only)

    def get_orientation_tag(self):
        """Returns the current Orientation tag number."""
        return self.get_tag("Orientation#", 1)

    def get_orientation(self):
        """Returns the current Orientation string."""
        return self.get_tag("Orientation", 1)

    def _rotate(self, deg, calc_only=False):
        if deg % 90:
            raise ValueError(f"Rotations must be multiples of 90 degrees, got {deg}")
        curr_orient = self.get_orientation_tag()
        curr_rot, curr_mirror = self._rotations[curr_orient]
        _, new_rot = divmod(curr_rot + deg, 360)
        new_orient = self._inverted_rotations[(new_rot, curr_mirror)]
        if calc_only:
            return new_orient
        self.set_orientation(new_orient)
        return None

    def mirror_vertically(self):
        """Flips the image top to bottom."""
        # First, rotate 180
        curr_orient = self.rotate_CW(2, calc_only=True)
        curr_rot, curr_mirror = self._rotations[curr_orient]
        new_mirror = curr_mirror ^ 1
        new_orient = self._inverted_rotations[(curr_rot, new_mirror)]
        self.set_orientation(new_orient)

    def mirror_horizontally(self):
        """Flips the image left to right."""
        curr_orient = self.get_orientation_tag()
        curr_rot, curr_mirror = self._rotations[curr_orient]
        new_mirror = curr_mirror ^ 1
        new_orient = self._inverted_rotations[(curr_rot, new_mirror)]
        self.set_orientation(new_orient)

    def set_orientation(self, val):
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
        cmd = f"""exiftool {self._opt_expr} -Orientation#='{val}' "{self.photo}" """
        _runproc(cmd, fpath=self.photo)

    def add_keyword(self, kw):
        """Add the passed string to the image's keyword tag, preserving existing keywords."""
        self.add_keywords([kw])

    def add_keywords(self, kws):
        """Add the passed list of strings to the image's keyword tag, preserving existing keywords."""

        def esc_space(val):
            return val.replace(" ", r"\ ").replace("&", r"\&")

        kws = [f"-iptc:keywords+={esc_space(kw)}" for kw in kws]
        kwopt = " ".join(kws)
        cmd = f'exiftool {self._opt_expr} {kwopt} "{self.photo}" '
        _runproc(cmd, fpath=self.photo)

    def get_keywords(self):
        """Returns the current keywords for the image as a list."""
        ret = self.get_tag("Keywords")
        if not ret:
            return []
        if isinstance(ret, str):
            return [ret]
        return sorted([str(kw) for kw in ret])

    def set_keywords(self, kws):
        """Sets the image's keyword list to the passed list of strings. Any existing keywords are
        overwritten.
        """
        self.clear_keywords()
        self.add_keywords(kws)

    def clear_keywords(self):
        """Removes all keywords from the image."""
        self.set_tag("Keywords", "")

    def remove_keyword(self, kw):
        """Remove a single keyword from the image. If the keyword does not exist, this call is a
        no-op.
        """
        self.remove_keywords([kw])

    def remove_keywords(self, kws):
        """Removes multiple keywords from the image. If any keyword does not exist, it is
        ignored.
        """
        curr = self.get_keywords()
        for kw in kws:
            try:
                curr.remove(kw)
            except ValueError:
                pass
        self.set_keywords(curr)

    def get_tag(self, tag, default=None):
        """Returns the value of 'tag', or the default value if the tag does not exist."""
        cmd = f'exiftool -j -d "%Y:%m:%d %H:%M:%S" -{tag} "{self.photo}" '
        out = _runproc(cmd, fpath=self.photo)
        info = json.loads(out)[0]
        ret = info.get(tag, default)
        return ret

    def get_tags(self, just_names=False, include_empty=True):
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

    def get_dict_tags(self, include_empty=True):
        """Returns a dict of all the tags for the current image, with the tag name as the key and
        the tag value as the value.
        """
        tags = self.get_tags(include_empty=include_empty)
        return dict(tags)

    def set_tag(self, tag, val):
        """Sets the specified tag to the passed value. You can set multiple values for the same tag
        by passing those values in as a list.
        """
        if not isinstance(val, (list, tuple)):
            val = [val]

        def esc_quote(val):
            return val.replace('"', '\\"') if isinstance(val, str) else val

        vallist = [f'-{tag}="{esc_quote(v)}"' for v in val]
        valstr = " ".join(vallist)
        cmd = f'exiftool {self._opt_expr} {valstr} "{self.photo}" '
        try:
            _runproc(cmd, fpath=self.photo)
        except RuntimeError as e:
            err = f"{e}".strip()
            if self._bad_tag_pat.match(err):
                print(f"Tag '{tag}' is invalid.")
            else:
                raise

    def set_tags(self, tags_dict):
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
        cmd = f'exiftool {self._opt_expr} {valstr} "{self.photo}" '
        try:
            _runproc(cmd, fpath=self.photo)
        except RuntimeError as e:
            err = f"{e}".strip()
            if self._bad_tag_pat.match(err):
                print(f"Tag '{tag}' is invalid.")
            else:
                raise

    def get_original_date_time(self):
        """Get the image's original date/time value (i.e., when the picture was 'taken')."""
        return self._get_date_time_field("DateTimeOriginal")

    def set_original_date_time(self, dttm=None):
        """Set the image's original date/time (i.e., when the picture was 'taken') to the passed
        value. If no value is passed, set it to the current datetime.
        """
        self._set_date_time_field("DateTimeOriginal", dttm)

    def get_modification_date_time(self):
        """Get the image's modification date/time value."""
        return self._get_date_time_field("FileModifyDate")

    def set_modification_date_time(self, dttm=None):
        """Set the image's modification date/time to the passed value. If no value is passed, set
        it to the current datetime (i.e., like 'touch'.
        """
        self._set_date_time_field("FileModifyDate", dttm)

    def _get_date_time_field(self, fld):
        """Generic getter for datetime values."""
        ret = self.get_tag(fld)
        if ret is not None:
            # It will be a string in exif std datetime format
            ret = datetime.datetime.strptime(ret, "%Y:%m:%d %H:%M:%S")
        return ret

    def _set_date_time_field(self, fld, dttm):
        """Generic setter for datetime values."""
        if dttm is None:
            dttm = datetime.datetime.now()
        # Convert to string format if needed
        if isinstance(dttm, (datetime.datetime, datetime.date)):
            dtstring = dttm.strftime("%Y:%m:%d %H:%M:%S")
        else:
            dtstring = self._format_date_time(dttm)
        cmd = f"""exiftool {self._opt_expr} -{fld}='{dtstring}' "{self.photo}" """
        _runproc(cmd, fpath=self.photo)

    def _format_date_time(self, dt):
        """Accepts a string representation of a date or datetime, and returns a string correctly
        formatted for EXIF datetimes.
        """
        if self._date_pattern.match(dt):
            # Add the time portion
            return f"{dt} 00:00:00"
        if self._date_time_pattern.match(dt):
            # Leave as-is
            return dt
        raise ValueError(f"Incorrect datetime value '{dt}' received") from None

    # Compatibility with previous versions. If you have code that used method names with the older,
    # non-Pythonic names, these will ensure that it continues to work
    # pylint: disable=
    rotateCCW = rotate_CCW
    rotateCW = rotate_CW
    getOrientation = get_orientation_tag
    mirrorVertically = mirror_vertically
    mirrorHorizontally = mirror_horizontally
    setOrientation = set_orientation
    addKeyword = add_keyword
    addKeywords = add_keywords
    getKeywords = get_keywords
    setKeywords = set_keywords
    clearKeywords = clear_keywords
    removeKeyword = remove_keyword
    removeKeywords = remove_keywords
    getTag = get_tag
    getTags = get_tags
    getDictTags = get_dict_tags
    setTag = set_tag
    setTags = set_tags
    getOriginalDateTime = get_original_date_time
    setOriginalDateTime = set_original_date_time
    getModificationDateTime = get_modification_date_time
    setModificationDateTime = set_modification_date_time
    _getDateTimeField = _get_date_time_field
    _setDateTimeField = _set_date_time_field
    _formatDateTime = _format_date_time


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
