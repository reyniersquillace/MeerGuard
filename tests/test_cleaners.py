"""Unit tests for coast_guard.cleaners registration and config plumbing.

These exercise cleaner registration, instantiation, and configuration-string
parsing. The actual RFI-excision logic (_clean methods) needs a live psrchive
Archive and is covered by integration tests, not here.

Note: importing this package pulls in coast_guard.cleaners.surgical which does
``import psrchive`` at module scope -- the conftest psrchive stub makes that
succeed.

Bug-fixes that require a live psrchive Archive are NOT unit-tested here (they
would need brittle mocks of the C-extension). They are exercised by integration
testing instead:
  * rcvrstd inclusive channel-interval zap (range(lochan, hichan + 1)).
  * bandwagon divide-by-zero guard for a fully-masked archive.
  * surgical fully-zeroed-profile detection (~data.any(axis=2)) and the
    per-cell mask assignment (data.mask[ii, jj, :] = True).
"""
import pytest

from coast_guard import cleaners
from coast_guard import errors
from coast_guard.cleaners import config_types


class TestRegistration:
    def test_registered_cleaners_list(self):
        assert set(cleaners.registered_cleaners) == \
            {'hotbins', 'surgical', 'rcvrstd', 'bandwagon'}

    def test_load_unknown_raises(self):
        with pytest.raises(errors.UnrecognizedValueError):
            cleaners.load_cleaner('does-not-exist')

    @pytest.mark.parametrize('name', ['hotbins', 'surgical', 'rcvrstd', 'bandwagon'])
    def test_load_returns_instance_with_matching_name(self, name):
        cleaner = cleaners.load_cleaner(name)
        assert isinstance(cleaner, cleaners.BaseCleaner)
        assert cleaner.name == name


class TestBaseCleaner:
    def test_clean_not_implemented(self):
        cleaner = cleaners.BaseCleaner()
        with pytest.raises(NotImplementedError):
            cleaner._clean(object())


class TestConfigurationsParsing:
    def test_parse_float_param(self):
        cleaner = cleaners.load_cleaner('bandwagon')
        cleaner.parse_config_string('badchantol=0.5,badsubtol=0.9')
        assert cleaner.configs['badchantol'] == pytest.approx(0.5)
        assert cleaner.configs['badsubtol'] == pytest.approx(0.9)

    def test_parse_via_attribute_access(self):
        cleaner = cleaners.load_cleaner('hotbins')
        cleaner.parse_config_string('threshold=7')
        # __getattr__ delegates to __getitem__
        assert cleaner.configs.threshold == pytest.approx(7.0)

    def test_parse_bool_and_intpairlist(self):
        cleaner = cleaners.load_cleaner('hotbins')
        cleaner.parse_config_string('fscrunchfirst=true,onpulse=10:20;30:40')
        assert cleaner.configs['fscrunchfirst'] is True
        assert cleaner.configs['onpulse'] == [(10, 20), (30, 40)]


class TestAddParam:
    def test_duplicate_name_raises(self):
        configs = cleaners.Configurations()
        configs.add_param('foo', config_types.IntVal)
        with pytest.raises(ValueError):
            configs.add_param('foo', config_types.IntVal)

    def test_non_configtype_raises(self):
        configs = cleaners.Configurations()

        class NotAConfigType:
            pass

        with pytest.raises(ValueError):
            configs.add_param('bar', NotAConfigType)

    def test_alias_normalisation(self):
        configs = cleaners.Configurations()
        configs.add_param('threshold', config_types.FloatVal, aliases=['thresh'])
        # Setting via the alias should populate the normalised key.
        configs['thresh'] = '3.5'
        assert configs['threshold'] == pytest.approx(3.5)


class TestConfigurationsToString:
    def test_to_string_round_trip(self):
        # Exercises Configurations.to_string(), which previously used the
        # Python-2-only dict.iteritems() and crashed on Python 3.
        configs = cleaners.Configurations()
        configs.add_param('alpha', config_types.IntVal)
        configs.add_param('beta', config_types.FloatVal)
        configs['alpha'] = '5'
        configs['beta'] = '2.5'
        # Sorted, normalised '<param>=<val>,...' string.
        assert configs.to_string() == 'alpha=5,beta=2.5'

    def test_str_delegates_to_to_string(self):
        configs = cleaners.Configurations()
        configs.add_param('alpha', config_types.IntVal)
        configs['alpha'] = '7'
        assert str(configs) == 'alpha=7'

    def test_cleaner_get_config_string(self):
        # BaseCleaner.get_config_string() routes through to_string(); make
        # sure a real cleaner's config serialises without error.
        cleaner = cleaners.load_cleaner('bandwagon')
        cfgstr = cleaner.get_config_string()
        assert 'badchantol=' in cfgstr
        assert 'badsubtol=' in cfgstr
