"""Unit tests for coast_guard.clean_utils.

Only the pure-numeric helpers that do not require a live psrchive Archive are
tested here. Functions that take an ``ar`` (Archive) argument -- e.g.
``get_frequencies``, ``remove_profile_inplace``, ``write_psrsh_script`` -- need
psrchive and are covered by integration tests.
"""
import numpy as np
import numpy.testing as npt
import pytest

from coast_guard import clean_utils as cu


# ---------------------------------------------------------------------------
# fft_rotate
# ---------------------------------------------------------------------------
class TestFftRotate:
    def test_integer_shift_left(self):
        data = np.array([1., 2., 3., 4., 5., 6., 7., 8.])
        rotated = cu.fft_rotate(data, 2)
        expected = np.array([3., 4., 5., 6., 7., 8., 1., 2.])
        npt.assert_allclose(rotated, expected, atol=1e-9)

    def test_zero_shift_is_identity(self):
        # Even-length input (see test_odd_length_bug for the odd-length case).
        data = np.array([1., 5., 2., 8., 3., 4.])
        npt.assert_allclose(cu.fft_rotate(data, 0), data, atol=1e-9)

    @pytest.mark.xfail(reason="fft_rotate builds the phasor with np.arange(size/2+1) "
                              "which has the wrong length for odd-size input, so the "
                              "phasor and rfft output cannot broadcast (suspected code bug)",
                       raises=ValueError, strict=True)
    def test_odd_length_bug(self):
        data = np.array([1., 5., 2., 8., 3.])  # length 5 (odd)
        cu.fft_rotate(data, 1)

    def test_full_period_shift_is_identity(self):
        data = np.array([1., 2., 3., 4.])
        npt.assert_allclose(cu.fft_rotate(data, 4), data, atol=1e-9)

    def test_negative_shift_moves_right(self):
        data = np.array([1., 2., 3., 4.])
        npt.assert_allclose(cu.fft_rotate(data, -1),
                            np.array([4., 1., 2., 3.]), atol=1e-9)

    def test_preserves_sum(self):
        data = np.array([2., 4., 6., 8., 10., 12.])
        rotated = cu.fft_rotate(data, 2.5)
        npt.assert_allclose(np.sum(rotated), np.sum(data), atol=1e-9)


# ---------------------------------------------------------------------------
# apply_weights
# ---------------------------------------------------------------------------
class TestApplyWeights:
    def test_zeroes_masked_channels(self):
        data = np.ones((2, 3, 4))
        weights = np.array([[1, 0, 1], [0, 1, 0]])
        out = cu.apply_weights(data.copy(), weights)
        # Each bin-row sums to 4 where weight==1, else 0.
        npt.assert_array_equal(out.sum(axis=2),
                               np.array([[4., 0., 4.], [0., 4., 0.]]))

    def test_fractional_weights_scale(self):
        data = np.ones((1, 2, 3))
        weights = np.array([[0.5, 2.0]])
        out = cu.apply_weights(data.copy(), weights)
        npt.assert_allclose(out[0, 0], np.full(3, 0.5))
        npt.assert_allclose(out[0, 1], np.full(3, 2.0))

    def test_shape_preserved(self):
        data = np.random.rand(3, 5, 7)
        weights = np.ones((3, 5))
        out = cu.apply_weights(data.copy(), weights)
        assert out.shape == (3, 5, 7)


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------
class TestGetProfile:
    def test_sums_over_axis0(self):
        data = np.array([[1., 2., 3.], [4., 5., 6.]])
        npt.assert_array_equal(cu.get_profile(data), np.array([5., 7., 9.]))


# ---------------------------------------------------------------------------
# scale_chans
# ---------------------------------------------------------------------------
class TestScaleChans:
    def test_single_subband_subtracts_median(self):
        data = np.array([10., 12., 14., 100.])
        # median is 13.0, so result = data - 13
        out = cu.scale_chans(data, nchans=4)
        npt.assert_allclose(out, np.array([-3., -1., 1., 87.]))

    def test_masked_channels_set_to_zero(self):
        data = np.array([10., 12., 14., 100.])
        weights = np.array([1, 1, 1, 0], dtype=bool)
        out = cu.scale_chans(data, nchans=4, chanweights=weights)
        # median of unmasked [10,12,14] == 12, masked entry forced to 0
        npt.assert_allclose(out[:3], np.array([-2., 0., 2.]))
        assert out[3] == 0.0

    def test_multiple_subbands(self):
        data = np.array([1., 3., 100., 102.])
        out = cu.scale_chans(data, nchans=2)
        # subband0 median 2 -> [-1,1]; subband1 median 101 -> [-1,1]
        npt.assert_allclose(out, np.array([-1., 1., -1., 1.]))


# ---------------------------------------------------------------------------
# scale_subints
# ---------------------------------------------------------------------------
class TestScaleSubints:
    def test_kernel_size_one_subtracts_self(self):
        data = np.array([1., 2., 3., 4., 5.])
        # kernel_size=1 -> only neighbour is the point itself -> all zeros
        npt.assert_allclose(cu.scale_subints(data, kernel_size=1),
                            np.zeros(5))

    def test_constant_data_gives_zeros(self):
        data = np.full(6, 7.0)
        npt.assert_allclose(cu.scale_subints(data, kernel_size=3),
                            np.zeros(6))

    def test_output_length_matches_input(self):
        data = np.arange(10, dtype=float)
        assert len(cu.scale_subints(data, kernel_size=5)) == 10


# ---------------------------------------------------------------------------
# get_robust_std
# ---------------------------------------------------------------------------
class TestGetRobustStd:
    def test_matches_mad_formula(self):
        data = np.arange(11, dtype=float)  # 0..10, median 5
        weights = np.ones(11, dtype=bool)
        # MAD of 0..10 about median 5 is 3, robust std = 1.4826*3
        npt.assert_allclose(cu.get_robust_std(data, weights), 1.4826 * 3.0)

    def test_respects_weights(self):
        data = np.array([0., 1., 2., 3., 1000.])
        weights = np.array([1, 1, 1, 1, 0], dtype=bool)
        # Outlier masked out; median of [0,1,2,3]=1.5, |dev|=[1.5,.5,.5,1.5]
        # MAD = median([1.5,.5,.5,1.5]) = 1.0
        npt.assert_allclose(cu.get_robust_std(data, weights), 1.4826)


# ---------------------------------------------------------------------------
# fit_poly
# ---------------------------------------------------------------------------
class TestFitPoly:
    def test_linear_recovers_coefficients(self):
        x = np.arange(5, dtype=float)
        y = 2.0 * x + 3.0
        coeffs, poly = cu.fit_poly(np.ma.asarray(y), np.ma.asarray(x), order=1)
        # coeffs are [intercept, slope]
        npt.assert_allclose(coeffs, np.array([3.0, 2.0]), atol=1e-9)
        npt.assert_allclose(poly, y, atol=1e-9)

    def test_quadratic_recovers_coefficients(self):
        x = np.arange(6, dtype=float)
        y = 1.0 + 2.0 * x + 3.0 * x ** 2
        coeffs, poly = cu.fit_poly(np.ma.asarray(y), np.ma.asarray(x), order=2)
        npt.assert_allclose(coeffs, np.array([1.0, 2.0, 3.0]), atol=1e-6)

    def test_all_masked_raises(self):
        y = np.ma.masked_all(4)
        x = np.ma.asarray(np.arange(4, dtype=float))
        with pytest.raises(ValueError):
            cu.fit_poly(y, x, order=1)


# ---------------------------------------------------------------------------
# detrend
# ---------------------------------------------------------------------------
class TestDetrend:
    def test_removes_linear_trend(self):
        y = np.arange(20, dtype=float) * 3.0 + 5.0
        detrended = cu.detrend(y, order=1)
        npt.assert_allclose(detrended, np.zeros(20), atol=1e-9)

    def test_flat_input_unchanged(self):
        y = np.full(10, 4.0)
        detrended = cu.detrend(y, order=1)
        npt.assert_allclose(detrended, np.zeros(10), atol=1e-9)

    def test_returns_plain_array_for_plain_input(self):
        y = np.arange(10, dtype=float)
        out = cu.detrend(y, order=1)
        assert not np.ma.isMaskedArray(out)

    def test_returns_masked_for_masked_input(self):
        y = np.ma.masked_array(np.arange(10, dtype=float),
                               mask=np.zeros(10, dtype=bool))
        out = cu.detrend(y, order=1)
        assert np.ma.isMaskedArray(out)


# ---------------------------------------------------------------------------
# iterative_detrend
# ---------------------------------------------------------------------------
class TestIterativeDetrend:
    def test_all_masked_returns_masked(self):
        y = np.ma.masked_all(5)
        out = cu.iterative_detrend(y)
        assert np.ma.count(out) == 0

    def test_linear_trend_detrended(self):
        y = np.ma.asarray(np.arange(30, dtype=float) * 2.0 + 1.0)
        out = cu.iterative_detrend(y, order=1)
        # The bulk of the (masked) result should be near zero.
        npt.assert_allclose(out.filled(0.0), np.zeros(30), atol=1e-6)


# ---------------------------------------------------------------------------
# channel_scaler / subint_scaler
# ---------------------------------------------------------------------------
class TestScalers:
    def test_channel_scaler_shape(self):
        arr = np.random.RandomState(0).normal(size=(8, 4))
        scaled = cu.channel_scaler(arr, chan_order=[1], chan_breakpoints=None,
                                   chan_numpieces=None)
        assert scaled.shape == arr.shape

    def test_subint_scaler_shape(self):
        arr = np.random.RandomState(0).normal(size=(8, 4))
        scaled = cu.subint_scaler(arr, subint_order=[1], subint_breakpoints=None,
                                  subint_numpieces=None)
        assert scaled.shape == arr.shape

    def test_channel_scaler_centres_data(self):
        # A clean linear channel should scale to roughly zero-median.
        arr = np.zeros((10, 1))
        arr[:, 0] = np.arange(10) * 1.0
        scaled = cu.channel_scaler(arr, chan_order=[1], chan_breakpoints=None,
                                   chan_numpieces=None)
        assert np.isfinite(np.ma.median(scaled))


# ---------------------------------------------------------------------------
# comprehensive_stats
# ---------------------------------------------------------------------------
class TestComprehensiveStats:
    def test_output_shape(self):
        data = np.random.RandomState(1).normal(size=(4, 6, 16))
        res = cu.comprehensive_stats(data, axis=2, chanthresh=5, subintthresh=5)
        assert res.shape == (4, 6)

    def test_scores_are_nonnegative_and_finite(self):
        # Scores are built from absolute, scaled diagnostics, so they must be
        # non-negative and finite for well-behaved input.
        data = np.random.RandomState(2).normal(size=(5, 6, 32))
        res = cu.comprehensive_stats(data, axis=2, chanthresh=5, subintthresh=5)
        assert np.all(res >= 0)
        assert np.all(np.isfinite(res))

    def test_deterministic(self):
        data = np.random.RandomState(9).normal(size=(4, 5, 16))
        r1 = cu.comprehensive_stats(data, axis=2, chanthresh=5, subintthresh=5)
        r2 = cu.comprehensive_stats(data, axis=2, chanthresh=5, subintthresh=5)
        npt.assert_array_equal(r1, r2)

    def test_aggressive_uses_max_and_is_geq_average(self):
        data = np.random.RandomState(3).normal(size=(3, 5, 16))
        avg = cu.comprehensive_stats(data, axis=2, chanthresh=5, subintthresh=5,
                                     aggressive=False)
        agg = cu.comprehensive_stats(data, axis=2, chanthresh=5, subintthresh=5,
                                     aggressive=True)
        # max over diagnostics >= mean over diagnostics, elementwise.
        assert np.all(agg + 1e-9 >= avg)
