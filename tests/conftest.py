import builtins
import random
import string

import pytest

ALPHANUM = string.ascii_letters + string.digits
# pylint: disable=redefined-outer-name,unused-argument
@pytest.fixture()
def random_string_factory(random_unicode_factory):  # pylint: disable=redefined-outer-name
    """Returns a function that will generate random alphanumeric characters with an optional prefix."""

    def make_string(prefix=None, length=10):
        return random_unicode_factory(
            prefix=prefix, length=length, low=42, high=122, alphanum_only=True
        )

    return make_string


@pytest.fixture()
def random_unicode_factory():
    """Returns a function that will generate random unicode characters, with an optional prefix."""

    def make_unicode(prefix=None, length=10, low=123, high=111411, alphanum_only=False):
        prefix = prefix or ""
        ret = []
        rlength = length - len(prefix)
        while len(ret) < rlength:
            # Not all code points can be correctly encoded by Python, so we need to catch them and try again.
            char = chr(random.randrange(low, high))
            if alphanum_only and char not in ALPHANUM:
                continue
            try:
                char.encode("utf-8")
            except UnicodeEncodeError:
                continue
            ret.append(char)
        return f"{prefix}{''.join(ret)}"

    return make_unicode


@pytest.fixture()
def random_bytes_factory():
    """Returns a function that will generate random bytes in the unicode range"""

    def make_unicode(length=None):
        if not length:
            length = random.randrange(6, 25)
        ret = []
        while len(ret) < length:
            # Not all code points can be correctly encoded by Python, so we need to catch them and try again.
            try:
                ret.append(chr(random.randint(256, 1114111)).encode("utf-8"))
            except UnicodeEncodeError:
                pass
        return b"".join(ret)

    return make_unicode


@pytest.fixture
def print_mock(mocker):
    mocker.patch.object(builtins, "print")


if __name__ == "__main__":
    pytest.main([__file__])
