"""Unit tests for pure-Python helpers in coast_guard.utils.

Functions that shell out (``execute``), touch psrchive, or hit the network
are not tested here. A couple of helpers still contain Python-2-only
constructs (``types.StringType``/``types.StringTypes``) and are marked xfail
with a note for the reviewer.
"""
import datetime

import numpy as np
import numpy.testing as npt
import pytest

from coast_guard import utils


# ---------------------------------------------------------------------------
# exclude_files
# ---------------------------------------------------------------------------
class TestExcludeFiles:
    def test_removes_listed_files(self):
        files = ['a.ar', 'b.ar', 'c.ar']
        assert utils.exclude_files(files, ['b.ar']) == ['a.ar', 'c.ar']

    def test_no_overlap_returns_all(self):
        files = ['a.ar', 'b.ar']
        assert utils.exclude_files(files, ['z.ar']) == ['a.ar', 'b.ar']

    def test_exclude_all(self):
        files = ['a.ar', 'b.ar']
        assert utils.exclude_files(files, files) == []

    def test_empty_input(self):
        assert utils.exclude_files([], ['a']) == []


# ---------------------------------------------------------------------------
# get_mode
# ---------------------------------------------------------------------------
class TestGetMode:
    def test_single_most_common(self):
        val, count = utils.get_mode([1, 1, 2, 3, 1])
        assert val == 1
        assert count == 3

    def test_strings(self):
        val, count = utils.get_mode(['x', 'y', 'y'])
        assert val == 'y'
        assert count == 2

    def test_all_unique_returns_count_one(self):
        val, count = utils.get_mode([5, 6, 7])
        assert count == 1
        assert val in (5, 6, 7)


# ---------------------------------------------------------------------------
# mjd_to_date / mjd_to_datetime
# ---------------------------------------------------------------------------
class TestMjdToDate:
    def test_j2000_epoch(self):
        # MJD 51544 == 2000-01-01
        year, month, day = utils.mjd_to_date(51544.0)
        assert int(year) == 2000
        assert int(month) == 1
        assert int(np.floor(day)) == 1

    def test_known_date(self):
        # MJD 58849 == 2020-01-01
        year, month, day = utils.mjd_to_date(58849.0)
        assert (int(year), int(month), int(np.floor(day))) == (2020, 1, 1)

    def test_array_input(self):
        years, months, days = utils.mjd_to_date([51544.0, 58849.0])
        npt.assert_array_equal(years, np.array([2000, 2020]))
        npt.assert_array_equal(months, np.array([1, 1]))

    def test_negative_jd_raises(self):
        with pytest.raises(ValueError):
            utils.mjd_to_date(-2400001.0)


class TestMjdToDatetime:
    def test_returns_datetime(self):
        dt = utils.mjd_to_datetime(51544.0)
        assert isinstance(dt, datetime.datetime)
        assert dt.year == 2000
        assert dt.month == 1
        assert dt.day == 1

    def test_fractional_day_adds_time(self):
        # 0.5 of a day == 12 hours
        dt = utils.mjd_to_datetime(51544.5)
        assert dt.year == 2000 and dt.month == 1 and dt.day == 1
        assert dt.hour == 12


# ---------------------------------------------------------------------------
# sort_by_keys
# ---------------------------------------------------------------------------
class TestSortByKeys:
    def test_empty_returns_input(self):
        # Early-return path avoids the Python-2 code below.
        assert utils.sort_by_keys([], ['x']) == []

    @pytest.mark.xfail(reason="sort_by_keys uses Python-2-only types.StringType; "
                              "raises AttributeError under Python 3 for non-empty "
                              "input (suspected code bug)",
                       raises=AttributeError, strict=True)
    def test_sort_numeric_values(self):
        data = [{'v': 3}, {'v': 1}, {'v': 2}]
        utils.sort_by_keys(data, ['v'])
        assert [d['v'] for d in data] == [1, 2, 3]
