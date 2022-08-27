Introduction
============
Images can contain **EXIF** metadata that describes information about the
image, such as creation date, the device used to create the image,
exposure data, GPS geotagging, keywords, compression, flash info, and
lots more. In addition to the standard tags defined by camera
manufacturers, you can also add your own tags with information as
key/value pairs.

NOTE: This module requires that the "exiftool" command-line tool is
installed on the system running pyexif. It is freely available at: 
http://www.sno.phy.queensu.ca/~phil/exiftool/

If exiftool is not installed, a warning message will be printed to
stdout, and the module will not work.


Common Actions
    Please note that any of the write operations *immediately* affect
    the image file. Please operate on a copy of the original.


Keyword Manipulation
====================
    get_keywords(): returns a list of all keywords.
    set_keywords(list of keywords): accepts a list of strings, and sets
        the keywords for that image to that list. Any existing keywords
        are overwritten.
    add_keyword(word): Appends the passed keyword to the image's
        keywords.
    add_keyword(list of words): Convenience method for adding several
        keywords at once.
    clear_keywords(): Removes all current keywords.

Date Functions
==============
    get_original_date_time(): Returns the datetime for the image's creation,
		or None if not set.
    set_original_date_time(dttm): Sets the image's original datetime to the
        passed datetime value.
    get_modification_date_time(): Returns the modification datetime for the
		image, or None if not set.
    set_modification_date_time(dttm): Sets the image's modification
        datetime to the passed datetime value.


Image Manipulation
==================
    rotate_CW(num=1): Rotates the image clockwise for 'num' 90-degree
        steps.
    rotate_CCW(num=1): Rotates the image counter-clockwise for 'num'
        90-degree steps.
    mirror_vertically(): Flips the image top to bottom.
    mirror_horizontally: Flips the image left to right.

Tag Manipulation
================
    get_tag(tag): returns the current value of the specified tag, or None
        if the tag does not exist.
    set_tag(tag, val): sets the specified tag to the specified value.
