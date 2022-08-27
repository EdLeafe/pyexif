from datetime import datetime
import json
import random
from unittest.mock import ANY, MagicMock

import pytest

from pyexif import pyexif


def test_runproc_ok(mocker, random_bytes_factory):
    mock_proc = MagicMock()
    mock_response = random_bytes_factory()
    mock_proc.communicate = MagicMock(return_value=(mock_response, b""))
    mocker.patch.object(pyexif, "Popen", return_value=mock_proc)
    # pylint: disable=protected-access
    result = pyexif._runproc("dummy")
    assert result == mock_response.decode("utf-8")


# pylint: disable=unused-argument
def test_runproc_err_dir(mocker, random_string_factory, print_mock):
    mock_proc = MagicMock()
    mock_proc.communicate = MagicMock(return_value=(b"", b"Warning: Bad ExifIFD directory blah"))
    mock_popen = mocker.patch.object(pyexif, "Popen", return_value=mock_proc)
    fpath = random_string_factory()
    cmd = random_string_factory()
    # pylint: disable=protected-access
    pyexif._runproc(cmd, fpath=fpath)
    # Original, fix, retry
    assert mock_popen.call_count == 3
    call0, call1, call2 = mock_popen.call_args_list
    assert call0[0][0] == cmd
    assert call1[0][0].startswith("exiftool -overwrite_original_in_place")
    assert call2[0][0] == cmd


def test_runproc_not_installed(mocker, random_string_factory):
    mock_proc = MagicMock()
    mock_proc.communicate = MagicMock(return_value=(b"", b"exiftool: command not found"))
    mocker.patch.object(pyexif, "Popen", return_value=mock_proc)
    fpath = random_string_factory()
    cmd = random_string_factory()
    # pylint: disable=protected-access
    with pytest.raises(RuntimeError, match=pyexif.INSTALL_EXIFTOOL_INFO):
        pyexif._runproc(cmd, fpath=fpath)


@pytest.mark.parametrize(
    "opts, exp_opts", [(None, ""), ("", ""), ("aa", "aa"), (["aa", "bb"], "aa bb")]
)
@pytest.mark.parametrize("save", [True, False])
@pytest.mark.parametrize("photo", [None, "photo", b"photo"])
def test_exif_init(photo, save, opts, exp_opts):
    ed = pyexif.ExifEditor(photo=photo, save_backup=save, extra_opts=opts)
    assert ed.save_backup == save
    if not save:
        if exp_opts:
            exp_opts = f"{exp_opts} -overwrite_original_in_place"
        else:
            exp_opts = "-overwrite_original_in_place"
    # pylint: disable=protected-access
    assert ed._opt_expr == exp_opts
    exp_photo = photo.decode("utf-8") if isinstance(photo, bytes) else photo
    assert ed.photo == exp_photo


def test_rotate_CCW(mocker):
    ed = pyexif.ExifEditor()
    mock_rotate = mocker.patch.object(ed, "_rotate")
    ed.rotate_CCW()
    mock_rotate.assert_called_once_with(-90, False)


def test_rotate_CW(mocker):
    ed = pyexif.ExifEditor()
    mock_rotate = mocker.patch.object(ed, "_rotate")
    ed.rotate_CW()
    mock_rotate.assert_called_once_with(90, False)


def test_rotate_CCW_mult(mocker):
    ed = pyexif.ExifEditor()
    mock_rotate = mocker.patch.object(ed, "_rotate")
    num = random.randrange(1, 20)
    ed.rotate_CCW(num)
    mock_rotate.assert_called_once_with(-90 * num, False)


def test_rotate_CW_mult(mocker):
    ed = pyexif.ExifEditor()
    mock_rotate = mocker.patch.object(ed, "_rotate")
    num = random.randrange(1, 20)
    ed.rotate_CW(num)
    mock_rotate.assert_called_once_with(90 * num, False)


def test_get_orientation(mocker, random_string_factory):
    ed = pyexif.ExifEditor()
    orient = random_string_factory()
    mocker.patch.object(pyexif, "_runproc", return_value=json.dumps([{"Orientation": orient}]))
    result = ed.get_orientation()
    assert result == orient


@pytest.mark.parametrize("orient", [1, 2, 3, 4])
def test_get_orientation_tag(mocker, orient):
    ed = pyexif.ExifEditor()
    mocker.patch.object(pyexif, "_runproc", return_value=json.dumps([{"Orientation#": orient}]))
    result = ed.get_orientation_tag()
    assert result == orient


def test_rotate(mocker):
    ed = pyexif.ExifEditor()
    mocker.patch.object(ed, "get_orientation_tag", return_value=1)
    mocker.patch.object(ed, "set_orientation")
    rot_values = {0: 1, 1: 6, 2: 3, 3: 8}
    # pylint: disable=protected-access
    for num in range(16):
        result = ed._rotate(num * 90, True)
        norm = num % 4
        assert result == rot_values[norm]


@pytest.mark.parametrize("degrees", [13, 46, 12345, -91])
def test_rotate_bad_val(degrees):
    ed = pyexif.ExifEditor()
    # pylint: disable=protected-access
    with pytest.raises(ValueError, match="must be multiples of 90 degrees"):
        ed._rotate(degrees, True)


@pytest.mark.parametrize(
    "start, result", [(1, 2), (2, 1), (3, 4), (4, 3), (5, 6), (6, 5), (7, 8), (8, 7)]
)
def test_mirror_vertically(mocker, start, result):
    ed = pyexif.ExifEditor()
    mocker.patch.object(ed, "rotate_CW", return_value=start)
    mock_set = mocker.patch.object(ed, "set_orientation")
    ed.mirror_vertically()
    mock_set.assert_called_once_with(result)


@pytest.mark.parametrize(
    "start, result", [(1, 2), (2, 1), (3, 4), (4, 3), (5, 6), (6, 5), (7, 8), (8, 7)]
)
def test_mirror_horizontally(mocker, start, result):
    ed = pyexif.ExifEditor()
    mocker.patch.object(ed, "get_orientation_tag", return_value=start)
    mock_set = mocker.patch.object(ed, "set_orientation")
    ed.mirror_horizontally()
    mock_set.assert_called_once_with(result)


def test_set_orientation(mocker, random_string_factory):
    photo = random_string_factory()
    ed = pyexif.ExifEditor(photo=photo, save_backup=True)
    mock_run = mocker.patch.object(pyexif, "_runproc")
    val = random.randrange(1, 9)
    ed.set_orientation(val)
    mock_run.assert_called_once_with(f"exiftool  -Orientation#='{val}' \"{photo}\" ", fpath=photo)


def test_add_keyword(mocker, random_string_factory):
    ed = pyexif.ExifEditor()
    kw = random_string_factory()
    mock_kws = mocker.patch.object(ed, "add_keywords")
    ed.add_keyword(kw)
    mock_kws.assert_called_once_with([kw])


def test_add_keywords(mocker, random_string_factory):
    photo = random_string_factory()
    ed = pyexif.ExifEditor(photo=photo)
    kw1 = random_string_factory()
    kw2 = random_string_factory()
    mock_run = mocker.patch.object(pyexif, "_runproc")
    ed.add_keywords([kw1, kw2])
    mock_run.assert_called_once_with(ANY, fpath=photo)
    call_args = mock_run.call_args[0][0]
    assert "exiftool " in call_args
    assert f"-iptc:keywords+={kw1}" in call_args
    assert f"-iptc:keywords+={kw2}" in call_args


def test_get_keywords(mocker, random_string_factory):
    ed = pyexif.ExifEditor()
    # Make the keywords sort in reverse
    kw1 = random_string_factory(prefix="ZZ")
    kw2 = random_string_factory(prefix="AA")
    mocker.patch.object(ed, "get_tag", return_value=[kw1, kw2])
    result = ed.get_keywords()
    assert result == [kw2, kw1]


def test_set_keywords(mocker, random_string_factory):
    ed = pyexif.ExifEditor()
    kw1 = random_string_factory()
    kw2 = random_string_factory()
    mock_clear = mocker.patch.object(ed, "clear_keywords")
    mock_add = mocker.patch.object(ed, "add_keywords")
    ed.set_keywords([kw1, kw2])
    mock_clear.assert_called_once_with()
    mock_add.assert_called_once_with([kw1, kw2])


def test_clear_keywords(mocker):
    ed = pyexif.ExifEditor()
    mock_set = mocker.patch.object(ed, "set_tag")
    ed.clear_keywords()
    mock_set.assert_called_once_with("Keywords", "")


def test_remove_keyword(mocker, random_string_factory):
    ed = pyexif.ExifEditor()
    mock_remove = mocker.patch.object(ed, "remove_keywords")
    kw = random_string_factory()
    ed.remove_keyword(kw)
    mock_remove.assert_called_once_with([kw])


def test_remove_keywords(mocker, random_string_factory):
    ed = pyexif.ExifEditor()
    kw1 = random_string_factory()
    kw2 = random_string_factory()
    bad_kw1 = random_string_factory()
    bad_kw2 = random_string_factory()
    mocker.patch.object(ed, "get_keywords", return_value=[kw1, bad_kw1, kw2, bad_kw2])
    mock_set = mocker.patch.object(ed, "set_keywords")
    ed.remove_keywords([bad_kw1, bad_kw2])
    mock_set.assert_called_once_with([kw1, kw2])


def test_get_tag(mocker, random_string_factory):
    photo = random_string_factory()
    tag_name = random_string_factory()
    tag_val = random_string_factory()
    ed = pyexif.ExifEditor(photo=photo)
    resp_dict = {tag_name: tag_val}
    mock_run = mocker.patch.object(pyexif, "_runproc", return_value=json.dumps([resp_dict]))
    result = ed.get_tag(tag_name)
    assert result == tag_val
    mock_run.assert_called_once_with(
        f'exiftool -j -d "%Y:%m:%d %H:%M:%S" -{tag_name} "{photo}" ', fpath=photo
    )


def test_get_tag_default(mocker, random_string_factory):
    photo = random_string_factory()
    tag_name = random_string_factory()
    tag_val = random_string_factory()
    bad_name = random_string_factory()
    default = random_string_factory()
    ed = pyexif.ExifEditor(photo=photo)
    resp_dict = {tag_name: tag_val}
    mock_run = mocker.patch.object(pyexif, "_runproc", return_value=json.dumps([resp_dict]))
    result = ed.get_tag(bad_name, default=default)
    assert result == default
    mock_run.assert_called_once_with(
        f'exiftool -j -d "%Y:%m:%d %H:%M:%S" -{bad_name} "{photo}" ', fpath=photo
    )


@pytest.mark.parametrize("include_empty", [True, False])
@pytest.mark.parametrize("just_names", [True, False])
def test_get_tags(mocker, random_string_factory, just_names, include_empty):
    photo = random_string_factory()
    # ensure that they sort in order
    tag1 = random_string_factory(prefix="at1")
    val1 = random_string_factory(prefix="bv1")
    tag2 = random_string_factory(prefix="ct2")
    val2 = ""
    tag3 = random_string_factory(prefix="et3")
    val3 = random_string_factory(prefix="fv3")
    resp_dict = {tag1: val1, tag2: val2, tag3: val3}
    mock_run = mocker.patch.object(pyexif, "_runproc", return_value=json.dumps([resp_dict]))
    ed = pyexif.ExifEditor(photo=photo)
    result = ed.get_tags(just_names=just_names, include_empty=include_empty)
    mock_run.assert_called_once_with(f'exiftool -j -d "%Y:%m:%d %H:%M:%S" "{photo}" ', fpath=photo)
    if just_names:
        if include_empty:
            assert result == [tag1, tag2, tag3]
        else:
            assert result == [tag1, tag3]
    else:
        if include_empty:
            assert result == [(tag1, val1), (tag2, val2), (tag3, val3)]
        else:
            assert result == [(tag1, val1), (tag3, val3)]


@pytest.mark.parametrize("include_empty", [True, False])
def test_get_dict_tags(mocker, random_string_factory, include_empty):
    photo = random_string_factory()
    # ensure that they sort in order
    tag1 = random_string_factory(prefix="at1")
    val1 = random_string_factory(prefix="bv1")
    tag2 = random_string_factory(prefix="ct2")
    val2 = ""
    tag3 = random_string_factory(prefix="et3")
    val3 = random_string_factory(prefix="fv3")
    resp_dict = {tag1: val1, tag2: val2, tag3: val3}
    mock_run = mocker.patch.object(pyexif, "_runproc", return_value=json.dumps([resp_dict]))
    ed = pyexif.ExifEditor(photo=photo)
    result = ed.get_dict_tags(include_empty=include_empty)
    mock_run.assert_called_once_with(f'exiftool -j -d "%Y:%m:%d %H:%M:%S" "{photo}" ', fpath=photo)
    if include_empty:
        assert result == {tag1: val1, tag2: val2, tag3: val3}
    else:
        assert result == {tag1: val1, tag3: val3}


def test_set_tags(mocker, random_string_factory):
    photo = random_string_factory()
    # ensure that they sort in order
    tag1 = random_string_factory(prefix="at1")
    val1 = random_string_factory(prefix="bv1")
    tag2 = random_string_factory(prefix="ct2")
    val2 = random_string_factory(prefix="dv2")
    tag3 = random_string_factory(prefix="et3")
    val3 = random_string_factory(prefix="fv3")
    tag_dict = {tag1: val1, tag2: val2, tag3: val3}
    mock_run = mocker.patch.object(pyexif, "_runproc")
    ed = pyexif.ExifEditor(photo=photo)
    ed.set_tags(tag_dict)
    exp_cmd = f'exiftool -overwrite_original_in_place -{tag1}="{val1}" -{tag2}="{val2}" -{tag3}="{val3}" "{photo}" '
    mock_run.assert_called_once_with(exp_cmd, fpath=photo)


def test_set_tag_bad_tag(capsys, mocker, random_string_factory):
    photo = random_string_factory()
    ed = pyexif.ExifEditor(photo=photo)
    tag = random_string_factory()
    val = random_string_factory()
    mocker.patch.object(
        pyexif, "_runproc", side_effect=RuntimeError(f"Warning: Tag '{tag}' does not exist")
    )
    ed.set_tag(tag, val)
    out, _ = capsys.readouterr()
    assert f"Tag '{tag}' is invalid." in out


def test_set_tags_bad_type(random_string_factory):
    photo = random_string_factory()
    bad_dict = "not a dict"
    ed = pyexif.ExifEditor(photo=photo)
    with pytest.raises(TypeError, match="is not instance of dict"):
        ed.set_tags(bad_dict)


def test_set_tags_bad_tag(capsys, mocker, random_string_factory):
    photo = random_string_factory()
    ed = pyexif.ExifEditor(photo=photo)
    tag = random_string_factory()
    val = random_string_factory()
    mocker.patch.object(
        pyexif, "_runproc", side_effect=RuntimeError(f"Warning: Tag '{tag}' does not exist")
    )
    ed.set_tags({tag: val})
    out, _ = capsys.readouterr()
    assert f"Tag '{tag}' is invalid." in out


def test_get_original_date_time(mocker):
    ed = pyexif.ExifEditor()
    mock_get = mocker.patch.object(ed, "_get_date_time_field")
    ed.get_original_date_time()
    mock_get.assert_called_once_with("DateTimeOriginal")


def test_set_original_date_time(mocker, random_string_factory):
    ed = pyexif.ExifEditor()
    dttm = random_string_factory()
    mock_set = mocker.patch.object(ed, "_set_date_time_field")
    ed.set_original_date_time(dttm)
    mock_set.assert_called_once_with("DateTimeOriginal", dttm)


def test_get_modified_date_time(mocker):
    ed = pyexif.ExifEditor()
    mock_get = mocker.patch.object(ed, "_get_date_time_field")
    ed.get_modification_date_time()
    mock_get.assert_called_once_with("FileModifyDate")


def test_set_modified_date_time(mocker, random_string_factory):
    ed = pyexif.ExifEditor()
    dttm = random_string_factory()
    mock_set = mocker.patch.object(ed, "_set_date_time_field")
    ed.set_modification_date_time(dttm)
    mock_set.assert_called_once_with("FileModifyDate", dttm)


def test_get_datetime_field(mocker, random_string_factory):
    ed = pyexif.ExifEditor()
    fld = random_string_factory()
    now = datetime.utcnow()
    # Need to trim the milliseconds
    exp_date = datetime(now.year, now.month, now.day, now.hour, now.minute, now.second)
    fmt_now = now.strftime("%Y:%m:%d %H:%M:%S")
    mocker.patch.object(ed, "get_tag", return_value=fmt_now)
    # pylint: disable=protected-access
    result = ed._get_date_time_field(fld)
    assert result == exp_date


def test_set_datetime_field(mocker, random_string_factory):
    photo = random_string_factory(prefix="PHO")
    ed = pyexif.ExifEditor(photo=photo)
    fld = random_string_factory(prefix="FLD")
    now = datetime.utcnow()
    fmt_now = now.strftime("%Y:%m:%d %H:%M:%S")
    mock_run = mocker.patch.object(pyexif, "_runproc")
    # pylint: disable=protected-access
    ed._set_date_time_field(fld, now)
    exp_cmd = f"""exiftool -overwrite_original_in_place -{fld}='{fmt_now}' "{photo}" """
    mock_run.assert_called_once_with(exp_cmd, fpath=photo)


@pytest.mark.parametrize(
    "dt_str, ok",
    [
        ("1999:09:08", True),
        ("1999:09:08 21:44:33", True),
        ("1999999:09:08", False),
        ("1999:55:08", False),
        ("1999999:09:123", False),
        ("fred", False),
    ],
)
def test_format_date_time(dt_str, ok):
    # pylint: disable=protected-access
    ed = pyexif.ExifEditor()
    if not ok:
        with pytest.raises(ValueError, match="Incorrect datetime value"):
            ed._format_date_time(dt_str)
    else:
        # No exception should be raised
        ed._format_date_time(dt_str)
