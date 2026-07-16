# MeerGuard Code Review

Scope: `clean_archive.py`, `setup.py`, `coast_guard/*.py`, `coast_guard/cleaners/*.py`.
Branch: `dev`. Review date: 2026-07-13. Read-only review — no source was modified.

Verification note: every finding was checked against the actual source with `grep`/targeted
reads. Findings are marked **[confirmed]** (verified in code) or **[latent/speculative]**
(depends on runtime/data/version). Line numbers were re-confirmed with `grep -n` because the
project files are longer than an initial full-file read reported.

---

## 1. Bugs & Correctness Issues

### 1.1 `hotbins.py:48` — `errors` is not imported → `NameError` masks the real error **[confirmed]**
`hotbins.py` imports `config`, `cleaners`, `config_types`, `utils` but **not** `errors`.
When `fscrunchfirst` is requested on already-dedispersed data the code does:
```python
raise errors.CleanError('The "hotbins" cleaner "fscrunchfirst"' \
                        'an only be used on non-dedispersed data.')
```
- Failure: instead of a helpful `CleanError`, Python raises `NameError: name 'errors' is not
  defined`. The user never learns the actual problem.
- Secondary: the message is a broken string concatenation ("fscrunchfirst""an only be used" →
  `...fscrunchfirstan only be used...`), missing a space and the word "can".
- Fix: add `from coast_guard import errors` and repair the message string.

### 1.2 Python-2-only `types.*` / `string.*` constants used at runtime → `AttributeError` on Python 3 **[confirmed]**
`setup.py` declares `python_requires='>=3.7'`, but several live code paths use names removed in
Python 3 (`types.IntType`, `types.FloatType`, `types.TupleType`, `types.StringType`,
`types.StringTypes`, `string.lower`, `string.upper`):

| Location | Code | Impact |
|---|---|---|
| `cleaners/rcvrstd.py:140,162` | `type(tozap) is types.IntType` | `rcvrstd` crashes whenever `badsubints`/`badchans` contain real values |
| `cleaners/rcvrstd.py:186` | `type(tozap) is types.FloatType` | `rcvrstd` crashes whenever `badfreqs` is set |
| `cleaners/config_types.py:244,352` | `type(el) is types.TupleType` | `IntOrIntPairList`/`FloatOrFloatPairList._value_to_string` crash; this runs during `normalize_param_string`, i.e. when *setting* `badchans`/`badfreqs`, not just printing |
| `coast_guard/utils.py:718` | `if type(cmd) == types.StringType` | **`utils.execute()` crashes for every string command** (this branch runs unconditionally) |
| `coast_guard/utils.py:710,713` | `type(stdout/stderr) == types.StringType` | crash when redirecting to a filename |
| `coast_guard/utils.py:441` | `isinstance(par, types.StringTypes)` | `normalise_parfile` crashes |
| `coast_guard/utils.py:1272` | `types.StringType` | `sort_by_keys` crashes on string keys |
| `coast_guard/utils.py:1333,1336` | `string.lower` / `string.upper` | `ArchiveFile.__getitem__` crashes for `*_L`/`*_U` keys |
| `coast_guard/colour.py:88,96` | `type(fg) == types.IntType` | numeric colour codes crash `cset` |

- Fix: replace with builtins `int`/`float`/`tuple`/`str`, use `isinstance(..., str)`, and
  `str.lower`/`str.upper`. The `MeerGuard` primary entry point (`clean_archive.py`) avoids
  `rcvrstd`/`utils.execute`, which is why these have survived, but the `rcvrstd` and `hotbins`
  cleaners and most of `utils.py` are effectively broken on Python 3.

### 1.3 `cleaners/__init__.py:181` — `self.cfgstrs.iteritems()` → `AttributeError` on Python 3 **[confirmed]**
`Configurations.to_string()` uses the removed dict method `iteritems()`. This is reached from
`BaseCleaner.get_config_string()`, `Configurations.__str__`, and `BaseCleaner.__repr__`, so any
attempt to print/serialize a cleaner's config crashes. Fix: `.items()`.

### 1.4 `surgical.py:252` — nonsensical mask assignment that only works by accident **[confirmed]**
```python
data.mask[ii, jj, :] = True*np.shape(masked_template.mask)
```
`np.shape(...)` returns a **tuple** (e.g. `(nbin,)`); `True * (nbin,)` is `1 * (nbin,)` =
tuple repetition = `(nbin,)`. A length-1 tuple is then assigned to an `nbin`-length boolean
slice, and NumPy broadcasts the single truthy value to the whole slice. The net effect
("mask all bins in this profile") happens only incidentally and is fragile/unreadable. This is
on the main surgical-cleaning path (masking fully-zeroed profiles). Fix:
`data.mask[ii, jj, :] = True`.

### 1.5 `cleaners/rcvrstd.py:169` — channel-interval zap is off-by-one vs. the documented "inclusive" behavior **[confirmed]**
```python
# An (inclusive) interval of bad channels to zap
lochan, hichan = tozap
for xx in range(lochan, hichan):        # <-- excludes hichan
```
The comment (and the parallel sub-int path at `rcvrstd.py:144`, which correctly uses
`range(losubint, hisubint + 1)`) says intervals are inclusive, but the channel loop stops at
`hichan-1`. The last channel of every `badchans` interval is silently left un-zapped. Fix:
`range(lochan, hichan + 1)`.

### 1.6 `surgical.py` "aggressive" flag contradicts its documented behavior **[confirmed]**
The parameter help at `surgical.py:~99` promises:
> "…more aggressive cleaning thresholds and algorithms (chanthresh=5.0, subint_thresh=5.0,
> badchantol=0.8, badsubtol=0.8)"

But in code, `aggressive` only changes how diagnostics are combined in
`clean_utils.comprehensive_stats` (`np.max` of the 5 diagnostics instead of `np.mean` —
`clean_utils.py:83-88`). It does **not** change `chanthresh`/`subintthresh`, and it has no
effect on the `bandwagon` tolerances at all (those are separate CLI args in
`clean_archive.py`). Users passing `-ag` will not get the documented thresholds. Fix: either
implement the documented threshold changes or correct the documentation.

### 1.7 `clean_utils.py:180` — `scipy.linalg.lstsq` used without importing `scipy.linalg` **[latent]**
`clean_utils.py` imports only `scipy.stats` and `scipy.optimize`. `fit_poly` calls
`scipy.linalg.lstsq(...)`. `scipy.linalg` is usually importable as a side effect of importing
`scipy.optimize`, so this normally works — but it is not guaranteed and is version-dependent.
`fit_poly` sits on the **main** surgical path
(`comprehensive_stats → channel/subint_scaler → iterative_detrend → detrend → fit_poly`), so a
future SciPy that lazily loads submodules would break RFI excision. Fix: add
`import scipy.linalg`.

### 1.8 `clean.py` legacy functions reference undefined names (crash if ever called) **[confirmed]**
These functions in `clean.py` are never called anywhere (confirmed by grep) but are latent
crashes and should be removed or fixed:
- `clean_simple` (`clean.py:322`) and `clean_iterative` (`clean.py:337`) call
  `get_subint_stats(...)`, which is **not defined anywhere in the repo**, and call
  `get_chan_stats`/`zero_weight_subint`/`zero_weight_chan` unqualified (they live in
  `clean_utils`) → `NameError`.
- `power_wash` (`clean.py:158`) and `deep_clean` (`clean.py:221`) call
  `clean_utils.remove_profile_inplace(ar, template, None)`; `phs=None` then flows into
  `fft_rotate(template, None)` → `TypeError`.
- `clean_archive` (`clean.py:517`) does `for clnr in cleaners` where `cleaners` is the imported
  **module** (not iterable) → `TypeError`, then `eval(matching_cleaners[0])`.

### 1.9 `clean_utils.py:335` — `get_chan_stats` calls undefined `scale(...)` **[confirmed]**
`std = scale(data.std(axis=1), ...)` — there is no `scale` function (only `scale_chans`,
`scale_subints`, `scale_data`). `get_chan_stats` is only referenced by the dead `clean_simple`,
so it never runs, but it is broken. Fix: remove, or call the intended `scale_chans`.

### 1.10 `clean_utils.py:273,280` — `scale_data` iterates over an `int` **[confirmed]**
```python
nsubs, nchans, nbins = data.shape
for ichan in nchans:      # nchans is an int → TypeError
    for isub in nsubs:    # nsubs is an int → TypeError
```
`scale_data` is dead code but is broken; `range(...)` was clearly intended.

### 1.11 `bandwagon.py:35-36` — possible divide-by-zero **[latent]**
```python
sub_badfrac  = 1 - weights.sum(axis=1)/float(nchan - nchan_masked)
chan_badfrac = 1 - weights.sum(axis=0)/float(nsub  - nsub_masked)
```
If every channel is masked (`nchan_masked == nchan`) or every sub-int is masked, the
denominator is 0 → `inf`/`nan` and unpredictable masking. Guard against fully-masked archives
(common after aggressive upstream cleaning). Note: the `sub_badfrac > badchantol` /
`chan_badfrac > badsubtol` pairing is actually *correct* w.r.t. the parameter definitions
(a sub-int is judged by its fraction of bad channels), despite reading backwards at first
glance.

### 1.12 `default.cfg` surgical detrend orders are silently truncated by `zip` **[confirmed]**
`surgical_default_params` sets `subint_order=2;1` (two orders) but `subint_numpieces=1`
(one element). In `subint_scaler` (`clean_utils.py:134`):
```python
for order, brkpnts, numpcs in zip(orders, breakpoints, numpieces): ...
```
`zip` stops at the shortest sequence, so only the first detrend pass (order 2) ever runs; the
documented "multiple values → multiple sequential detrends" second pass (order 1) is dropped.
Either the default should provide matching-length lists, or the loop should use
`itertools.zip_longest` with sensible fill values.

### 1.13 `surgical.py:207` — zeroed-profile detection inspects only phase bin 0 **[latent]**
```python
weights[(data[:,:,0] == 0)] = 0  # Make sure that any zeroed data is masked
```
This decides a profile is "zero data" by looking at a single bin (`bin 0`). A genuinely good
profile whose first bin happens to be exactly 0 would be wrongly de-weighted; conversely a
zero-weighted profile with a nonzero bin 0 would be missed. Prefer `~data.any(axis=2)` (all bins
zero) to match the stated intent.

### 1.14 `surgical.py:130` — `try/except KeyError` around attribute access, and the branch is effectively dead **[confirmed, low severity]**
```python
try:
    if self.configs.plot is None: plot = False
    else: plot = self.configs.plot
except KeyError:
    print("Plot keyword not found. Plotting disabled"); plot = False
```
`self.configs.plot` routes through `Configurations.__getattr__ → __getitem__` (a dict lookup),
so a missing key surfaces as `KeyError` — the catch is technically valid, but `plot` always has
a default (`plot=None` in `surgical_default_params`), so the `except` is unreachable. It is also
re-evaluated on every iteration inside the `for ii in range(self.configs.iterations)` loop
(`surgical.py:122`). Hoist it out of the loop and drop the dead handler.

### 1.15 Mutable default arguments **[confirmed, low severity]**
- `clean.py:42` `clean_hotbins(..., onpulse=[])`
- `clean_utils.py:191` `detrend(..., bp=[], ...)`
- `cleaners/__init__.py:238` `add_param(..., aliases=[], ...)`

None of these are currently mutated in place, so no active bug, but they are latent traps. Use
`None` sentinels.

---

## 2. Refactoring Opportunities

- **`clean_archive.py:20` — positional-index config string building is brittle.**
  ```python
  surgical_parameters = "chan_numpieces=1,...,chanthresh={1},subintthresh={2},template={0},plot={3},aggressive={4},iterations={5}".format(tmp, cthresh, sthresh, plot, aggressive, iterations)
  ```
  The out-of-order `{0}..{5}` mapping is easy to break. Build from a dict and
  `",".join(f"{k}={v}" for k,v in params.items())`, or set the cleaner's configs
  programmatically.
- **`surgical.py::_clean` is ~180 lines** with template loading, phase-offset fitting, weight
  application, on-pulse masking, statistics, plotting, and weight-writing all inline. Decompose
  into helpers (`_load_template`, `_estimate_phase_offset`, `_build_offpulse_mask`,
  `_apply_mask_to_archive`). The `plot` diagnostics should also move to their own method.
- **Duplicated interval-formatting logic** in `clean_utils.write_psrsh_script` (the chan block
  and subint block at `clean_utils.py:650-679` are near-identical) and again in
  `write_ebpp_chan_zap_script`. Extract a `_format_zap_intervals(mask)` helper.
- **`clean.py` duplicates `rcvrstd` functionality.** `prune_band`, `trim_edge_channels`,
  `remove_bad_subints`, `remove_bad_channels` (all shelling out to `paz`) reimplement what the
  `rcvrstd` cleaner already does in-process. Delete the `clean.py` copies and keep one path.
- **Magic numbers** should become named constants: `1.4826` (MAD→σ) appears in
  `clean.py:84`, `clean_utils.py:114,139,147`, `hotbins.py:81`; the normality threshold `6.3`
  (`clean_utils.py:577`); the Savitzky–Golay window `savgol_filter(template, 5, 1)`
  (`surgical.py:156`); on-pulse cutoff fractions in `surgical.py`.
- **Inconsistent error handling in `config.py:67-68`:** `CoastGuardConfigs.__getitem__` does
  `print(...); sys.exit()` on a missing key. A library should `raise
  errors.ConfigurationError(...)`, not kill the interpreter.
- **`print(...)` everywhere instead of the existing logging.** `clean_archive.py`, `surgical.py`,
  `hotbins.py`, and `power_wash`/`deep_clean` use bare `print`, while the project already has
  `utils.print_info` + `log.py`. Route user-facing progress through the logging/verbosity system
  for consistency and quiet/verbose control.
- **`comprehensive_stats` ignores its `axis` argument.** `clean_utils.py:39` takes `axis`, but
  line 74 hardcodes `func(data, axis=2)`. Either honor the parameter or drop it.

---

## 3. Unused / Dead Code

### Dead functions (never referenced outside their own definition — confirmed by grep)
- `clean.py`: `dummy` (31), `clean_hotbins` (42), `surgical_scrub` (112), `power_wash` (158),
  `deep_clean` (221), `clean_simple` (322), `clean_iterative` (337), `prune_band` (363),
  `trim_edge_channels` (405), `remove_bad_subints` (438), `remove_bad_channels` (470),
  `clean_archive` (517). The only live entry in `clean.py` is `main()` + the argparse block.
  Much of this is legacy from upstream `coast_guard`.
- `clean_utils.py`: `scale_data` (270, also broken — see 1.10), `get_chan_stats` (332, broken —
  see 1.9), `fit_template` (405, only emits a warning), `freq_fraczap` (18, referenced only in a
  comment at `surgical.py:288`), `write_ebpp_chan_zap_script` (703). `get_subints`/`get_chans`/
  `clean_hot_bins`/`clean_subint`/`get_hot_bins` are reachable only from the dead `clean.py`
  functions and can likely go too.
- `colour.py`: `ColourizedOutput` (180) is broken — `write` references an undefined bare
  `colour` name and undefined `cargs`/`ckwargs` (should be `self.cargs`/`self.ckwargs`), and
  contains a leftover debug `print("Writing")` (192). `show_dictionary`/`show_colours`
  (152/156) are `NotImplementedError` stubs.

### Unused imports
- `clean.py:8,11,14,19` — `optparse`, `types`, `tempfile`, `scipy.stats` are imported but unused
  (confirmed: each name appears only on its import line).
- `coast_guard/utils.py` still imports `string` (line 19) solely for the broken
  `string.lower/upper` at 1333/1336.

### Unused variables / parameters
- `clean_utils.py:62` — `nsubs, nchans, ubbins = data.shape` is never used (and "ubbins" is a
  typo for "nbins").
- `clean_utils.py:143` — `get_robust_std(..., trimfrac=0.1)`: `trimfrac` is never used.
- `cleaners/rcvrstd.py:160,173` — the `nremoved` counters are incremented but never read or
  reported.
- `coast_guard/clean.py:180-182` — `power_wash` computes `std_sub_vs_chan` then `print(...shape)`
  and has a commented-out `mean_sub_vs_chan`; dead diagnostic scaffolding.

### Commented-out code to remove
- `surgical.py:188-189, 206` (old `leastsq`/lambda experiments), `surgical.py:288`
  (`#freq_fraczap = ...`).
- `clean_utils.py:426-428, 465-466` (old Python-2 lambda-tuple `leastsq` calls).
- `config.py:36, 120-131` (commented `execfile` and the old per-type config-file block).
- `coast_guard/utils.py:169` `main()` in `config.py` does `import utils` (bare) — a Python-2
  relative import that would fail on Python 3 (`from coast_guard import utils`).

---

## 4. Suggested Features & Improvements

1. **Real logging.** Replace `print` with the existing `log.py`/`utils.print_info`
   infrastructure and expose `-v/-q` on `clean_archive.py`. Right now progress goes to stdout
   unconditionally.
2. **Input validation in `clean_archive.py`.** `-a/--archive` and `-T/--template` are optional in
   argparse but required in practice; `ps.Archive_load(None)` will fail cryptically. Validate
   that the archive and template exist, that thresholds are positive, and that `0 <= badchantol,
   badsubtol <= 1`.
3. **Progress reporting.** The `nsub × nchan` (and, in `hotbins`, `× npol`) loops can be long;
   `utils.show_progress` already exists — wrap the outer loop in surgical/hotbins with it.
4. **Proper entry point.** `setup.py` uses `scripts=["clean_archive.py"]`. Prefer
   `entry_points={'console_scripts': ['meerguard = coast_guard.clean_archive:main']}` after
   wrapping the `__main__` block in a `main()` function. This also removes the `.py` from the
   installed command name.
5. **Tests + CI.** There are no tests and no CI config. Add `pytest` unit tests for the pure
   functions that don't need `psrchive` (`config_types` parsers, `fft_rotate`, `detrend`,
   `fit_poly`, `scale_chans`, `comprehensive_stats` on synthetic arrays) plus a GitHub Actions
   workflow running lint + tests. `psrchive` can be mocked for the cleaner classes.
6. **Reproducible plots & noise.** `np.random.normal(...)` in `surgical`/`hotbins`/`clean_subint`
   is non-deterministic; add a `--seed` option and seed the RNG so RFI replacement is
   reproducible. Diagnostic plots are hardcoded to filenames like `data_and_template.png`,
   `avg_test_results.png` in the CWD — parameterize an output directory / prefix so parallel runs
   don't clobber each other.
7. **Output naming.** `clean_archive.py:61` builds `"{pref}_ch{7.0}_sub{7.0}.ar"` embedding float
   thresholds (e.g. `ch7.0`). Support a user-supplied template (the project already has
   `utils.get_outfn`).
8. **Type hints** on the public functions in `clean_utils.py` and the cleaner classes would make
   the numpy array shapes/expectations explicit and catch some of the Python-2 issues via a type
   checker.
9. **Parallelization.** `remove_profile`/`remove_profile_inplace` already have an `nthreads`
   multiprocessing path (`clean_utils.py:442,477`), but the surgical cleaner always calls the
   `nthreads=1` in-process version. Wire `config.nthreads` through so large archives can use it.
10. **Modernize packaging.** Move to `pyproject.toml`, pin a tested `scipy`/`matplotlib`
    range, and declare `psrchive` as an explicitly-documented external (non-pip) dependency.

---

## 5. Summary — Prioritized Punch-List

1. **Fix Python-2 `types.*`/`string.*`/`iteritems` usages** (1.2, 1.3). These break `rcvrstd`,
   `hotbins`, most of `utils.py`, and any cleaner config serialization on the declared Python
   3.7+ target. Highest impact, mechanical fix.
2. **`hotbins.py` missing `import errors`** (1.1) — turns a guard clause into a confusing
   `NameError`; one-line fix.
3. **`surgical.py:252` mask assignment** (1.4) — replace `True*np.shape(...)` with `True`; it is
   on the core cleaning path and works only by accident.
4. **`rcvrstd.py:169` inclusive-interval off-by-one** (1.5) — last channel of each `badchans`
   interval is not zapped.
5. **`aggressive` flag vs. documentation** (1.6) — implement or correct the promised threshold
   behavior so `-ag` does what the help says.
6. **`import scipy.linalg` in `clean_utils.py`** (1.7) — remove the fragile implicit-import
   dependency on the main detrending path.
7. **Delete the dead/broken legacy code** (1.8-1.10, §3) — `clean.py`'s legacy cleaners and the
   broken `scale_data`/`get_chan_stats` in `clean_utils.py`; they are un-called and would crash,
   and they duplicate the cleaner classes.
8. **Add tests + CI and switch to a `console_scripts` entry point** (§4.4, §4.5) — there is
   currently no automated protection against regressions like items 1–2, which is why they went
   unnoticed.
