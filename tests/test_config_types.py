"""Unit tests for coast_guard.cleaners.config_types.

These test the parsing / normalisation of cleaner config-string parameter
types. They are pure string<->value helpers with no psrchive dependency.
"""
import pytest

from coast_guard.cleaners import config_types as ct


# ---------------------------------------------------------------------------
# Scalar types
# ---------------------------------------------------------------------------
class TestIntVal:
    def test_parse(self):
        assert ct.IntVal()._string_to_value('42') == 42
        assert ct.IntVal()._string_to_value('-7') == -7

    def test_value_to_string(self):
        assert ct.IntVal()._value_to_string(42) == '42'

    def test_round_trip_normalize(self):
        assert ct.IntVal().normalize_param_string('42') == '42'

    def test_bad_input_raises(self):
        with pytest.raises(ValueError):
            ct.IntVal()._string_to_value('not-an-int')

    def test_nullable_none(self):
        assert ct.IntVal(nullable=True).get_param_value('none') is None
        assert ct.IntVal(nullable=True).get_param_value('None') is None
        assert ct.IntVal(nullable=True).normalize_param_string('NONE') == 'None'

    def test_non_nullable_none_raises(self):
        # 'none' should be parsed as an int (and fail) when not nullable
        with pytest.raises(ValueError):
            ct.IntVal(nullable=False).get_param_value('none')


class TestFloatVal:
    def test_parse(self):
        assert ct.FloatVal()._string_to_value('3.5') == 3.5

    def test_value_to_string_uses_g_format(self):
        # %g strips trailing zeros
        assert ct.FloatVal()._value_to_string(3.0) == '3'
        assert ct.FloatVal()._value_to_string(3.5) == '3.5'

    def test_normalize(self):
        assert ct.FloatVal().normalize_param_string('3.50') == '3.5'

    def test_bad_input_raises(self):
        with pytest.raises(ValueError):
            ct.FloatVal()._string_to_value('abc')


class TestBoolVal:
    @pytest.mark.parametrize('s', ['true', 'TRUE', '1', 'y', 'Yes', 'YES'])
    def test_truthy(self, s):
        assert ct.BoolVal()._string_to_value(s) is True

    @pytest.mark.parametrize('s', ['false', 'FALSE', '0', 'n', 'No', 'NO'])
    def test_falsey(self, s):
        assert ct.BoolVal()._string_to_value(s) is False

    def test_unrecognised_raises(self):
        with pytest.raises(ValueError):
            ct.BoolVal()._string_to_value('maybe')

    def test_value_to_string(self):
        assert ct.BoolVal()._value_to_string(True) == 'True'


class TestStrVal:
    def test_parse(self):
        assert ct.StrVal()._string_to_value('hello') == 'hello'

    def test_none_passthrough(self):
        assert ct.StrVal()._string_to_value(None) is None


# ---------------------------------------------------------------------------
# Module-level list helpers
# ---------------------------------------------------------------------------
class TestStrToIntList:
    def test_basic(self):
        assert ct._str_to_intlist('1;2;3') == [1, 2, 3]

    def test_single(self):
        assert ct._str_to_intlist('5') == [5]

    def test_empty(self):
        assert ct._str_to_intlist('') == []
        assert ct._str_to_intlist('   ') == []

    def test_bad_raises(self):
        with pytest.raises(ValueError):
            ct._str_to_intlist('1;x;3')


class TestStrToIntPair:
    def test_basic(self):
        assert ct._str_to_int_pair('4:5') == (4, 5)

    def test_wrong_count_raises(self):
        with pytest.raises(ValueError):
            ct._str_to_int_pair('1:2:3')
        with pytest.raises(ValueError):
            ct._str_to_int_pair('1')


class TestStrToFloatList:
    def test_basic(self):
        assert ct._str_to_floatlist('1.0;2.5') == [1.0, 2.5]

    def test_empty(self):
        assert ct._str_to_floatlist('') == []


class TestStrToFloatPair:
    def test_basic(self):
        assert ct._str_to_float_pair('1.5:2.5') == (1.5, 2.5)

    def test_wrong_count_raises(self):
        with pytest.raises(ValueError):
            ct._str_to_float_pair('1.0')


# ---------------------------------------------------------------------------
# List config types
# ---------------------------------------------------------------------------
class TestIntList:
    def test_parse(self):
        assert ct.IntList()._string_to_value('1;2;3') == [1, 2, 3]

    def test_empty(self):
        assert ct.IntList()._string_to_value('') == []

    def test_value_to_string(self):
        assert ct.IntList()._value_to_string([1, 2, 3]) == '1;2;3'

    def test_round_trip(self):
        assert ct.IntList().normalize_param_string('1;2;3') == '1;2;3'


class TestIntListList:
    def test_parse(self):
        assert ct.IntListList()._string_to_value('1;2;;3;4') == [[1, 2], [3, 4]]

    def test_single_list(self):
        assert ct.IntListList()._string_to_value('1;2;3') == [[1, 2, 3]]

    def test_empty(self):
        assert ct.IntListList()._string_to_value('') == []

    def test_value_to_string(self):
        assert ct.IntListList()._value_to_string([[1, 2], [3, 4]]) == '1;2;;3;4'

    def test_round_trip(self):
        assert ct.IntListList().normalize_param_string('1;2;;3;4') == '1;2;;3;4'


class TestIntPairList:
    def test_parse(self):
        assert ct.IntPairList()._string_to_value('1:2;3:4') == [(1, 2), (3, 4)]

    def test_empty(self):
        assert ct.IntPairList()._string_to_value('') == []

    def test_value_to_string(self):
        assert ct.IntPairList()._value_to_string([(1, 2), (3, 4)]) == '1:2;3:4'

    def test_round_trip(self):
        assert ct.IntPairList().normalize_param_string('1:2;3:4') == '1:2;3:4'


class TestFloatList:
    def test_parse(self):
        assert ct.FloatList()._string_to_value('1.0;2.5;3.25') == [1.0, 2.5, 3.25]

    def test_value_to_string(self):
        assert ct.FloatList()._value_to_string([1.0, 2.5]) == '1;2.5'


class TestFloatPair:
    def test_parse(self):
        assert ct.FloatPair()._string_to_value('1.5:2.5') == (1.5, 2.5)

    def test_value_to_string(self):
        assert ct.FloatPair()._value_to_string((1.5, 2.5)) == '1.5:2.5'

    def test_round_trip(self):
        assert ct.FloatPair().normalize_param_string('1.5:2.5') == '1.5:2.5'


class TestFloatPairList:
    def test_parse(self):
        assert ct.FloatPairList()._string_to_value('1.0:2.0;3.0:4.0') == \
            [(1.0, 2.0), (3.0, 4.0)]

    def test_empty(self):
        assert ct.FloatPairList()._string_to_value('') == []

    def test_value_to_string(self):
        assert ct.FloatPairList()._value_to_string([(1.0, 2.0)]) == '1:2'


class TestIntOrIntPairList:
    def test_parse_mixed(self):
        assert ct.IntOrIntPairList()._string_to_value('1;2:3;4') == [1, (2, 3), 4]

    def test_empty(self):
        assert ct.IntOrIntPairList()._string_to_value('') == []

    @pytest.mark.xfail(reason="_value_to_string uses Python-2-only types.TupleType; "
                              "raises AttributeError under Python 3 (suspected code bug)",
                       raises=AttributeError, strict=True)
    def test_value_to_string_bug(self):
        ct.IntOrIntPairList()._value_to_string([1, (2, 3)])


class TestFloatOrFloatPairList:
    def test_parse_mixed(self):
        assert ct.FloatOrFloatPairList()._string_to_value('1.0;2.0:3.0') == \
            [1.0, (2.0, 3.0)]

    @pytest.mark.xfail(reason="_value_to_string uses Python-2-only types.TupleType; "
                              "raises AttributeError under Python 3 (suspected code bug)",
                       raises=AttributeError, strict=True)
    def test_value_to_string_bug(self):
        ct.FloatOrFloatPairList()._value_to_string([1.0, (2.0, 3.0)])


# ---------------------------------------------------------------------------
# Base behaviour
# ---------------------------------------------------------------------------
class TestBaseConfigType:
    def test_string_to_value_not_implemented(self):
        with pytest.raises(NotImplementedError):
            ct.BaseConfigType()._string_to_value('x')

    def test_get_help_includes_type_name(self):
        helpstr = ct.BoolVal().get_help()
        assert helpstr.startswith('Type: bool')
        # BoolVal defines a description, which should be appended
        assert 'true' in helpstr

    def test_get_help_without_description(self):
        # IntVal has no description
        assert ct.IntVal().get_help() == 'Type: int'
