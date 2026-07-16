# MeerGuard `clean_archive.py` — Entry-Point Enhancement Suggestions

Scope: proposals for editing **`clean_archive.py`** (repo root) to expose functionality that
already exists in reachable code — the four registered cleaners
(`coast_guard/cleaners/{surgical,bandwagon,rcvrstd,hotbins}.py`) and their config params, plus
`config.py`, `utils.py`, and `log.py`. The legacy `clean.py` module is being deleted as dead
code and is deliberately ignored here.

Branch `dev`, date 2026-07-13. Read-only analysis — no source was modified; the only artifact is
this document.

## Background: what the CLI exposes today vs. what exists

`clean_archive.py` loads only two of the four registered cleaners
(`registered_cleaners = ['hotbins', 'surgical', 'rcvrstd', 'bandwagon']`,
`coast_guard/cleaners/__init__.py:14`) and hands them a subset of their parameters:

| Cleaner | Params defined in `_set_config_params` | Exposed on CLI today |
|---|---|---|
| `surgical` | `chanthresh`, `subintthresh`, `chan_order`, `chan_breakpoints`, `chan_numpieces`, `subint_order`, `subint_breakpoints`, `subint_numpieces`, `template`, `plot`, `aggressive`, `iterations` | `chanthresh` (`-c`), `subintthresh` (`-s`), `template` (`-T`), `plot`, `aggressive` (`-ag`), `iterations` (`-i`) |
| `bandwagon` | `badchantol`, `badsubtol` | `badchantol` (`-bc`), `badsubtol` (`-bs`) |
| `rcvrstd` | `response`, `trimnum`, `trimfrac`, `trimbw`, `badsubints`, `badchans`, `badfreqs` | **none — cleaner never loaded** |
| `hotbins` | `threshold`, `fscrunchfirst`, `tscrunchfirst`, `onpulse`, `iscal`, `calfrac` | **none — cleaner never loaded** |

So `rcvrstd` and `hotbins` are entirely unreachable from the entry point, and `surgical`'s
piecewise-detrending controls are hidden. Worse, `apply_surgical_cleaner`
(`clean_archive.py:43`) *hardcodes* `chan_numpieces=1,subint_numpieces=1`, silently overriding the
config-file defaults (`chan_numpieces=[4]`-style values in `default.cfg`) and defeating the
detrending machinery the surgical cleaner is built around.

Config-string mechanics (relevant to every wiring sketch below): cleaner params are set via a
single comma-separated `key=val,key2=val2` string parsed by `Configurations.set_from_string`
(`cleaners/__init__.py:222`), which splits on `,` then `=`. List/interval values therefore use
`;` and `:` as internal separators (see `config_types.py`), **never commas**, so user values can
be dropped straight into the config string safely.

---

## Suggestion 1 — Expose the `rcvrstd` cleaner (band pruning / edge trimming / manual zapping)

**What & where.** `coast_guard/cleaners/rcvrstd.py`. Params (`_set_config_params`,
`rcvrstd.py:25-60`):
- `response` (`FloatPair`, `rcvrstd.py:29`) — `lo:hi` MHz; channels outside are de-weighted.
- `trimnum` / `trimfrac` / `trimbw` (`rcvrstd.py:36-45`) — edge-channel trimming by count,
  fraction, or bandwidth; the cleaner takes the `max` of the three (`rcvrstd.py:117`).
- `badsubints` (`IntOrIntPairList`, `rcvrstd.py:46`) — e.g. `3;10:14`.
- `badchans` (`IntOrIntPairList`, `rcvrstd.py:51`) — e.g. `0;120;500:520`.
- `badfreqs` (`FloatOrFloatPairList`, `rcvrstd.py:56`) — e.g. `935.5;1200:1250` (MHz).

**Why useful.** MeerKAT UHF/L-band data routinely need static, known-bad zapping (persistent
satellite/GNSS/GSM bands, band-edge roll-off) that no statistical cleaner should be asked to
rediscover per-observation. This is the single most-requested capability that already exists in
the code but cannot be invoked. Manual `badfreqs` zapping in MHz is far more natural for an
observer than computing channel indices by hand.

**Argparse + wiring sketch.**
```python
# --- argparse ---
parser.add_argument("--rcvrstd", dest="use_rcvrstd", action="store_true", default=False,
                    help="Run the rcvrstd cleaner (band pruning / edge trim / manual zapping)")
parser.add_argument("--response", dest="response", type=str, default=None,
                    help="Receiver response band as LO:HI in MHz; channels outside are zapped")
parser.add_argument("--trimnum", dest="trimnum", type=int, default=0,
                    help="Number of channels to de-weight at each band edge [default = 0]")
parser.add_argument("--trimfrac", dest="trimfrac", type=float, default=0.0,
                    help="Fraction (0-0.5) of each band edge to de-weight [default = 0]")
parser.add_argument("--trimbw", dest="trimbw", type=float, default=0.0,
                    help="Bandwidth (MHz) of each band edge to de-weight [default = 0]")
parser.add_argument("--badsubints", dest="badsubints", type=str, default=None,
                    help="Bad subints/intervals, e.g. '3;10:14' (0-indexed, inclusive)")
parser.add_argument("--badchans", dest="badchans", type=str, default=None,
                    help="Bad channels/intervals, e.g. '0;120;500:520' (0-indexed, inclusive)")
parser.add_argument("--badfreqs", dest="badfreqs", type=str, default=None,
                    help="Bad frequencies/intervals in MHz, e.g. '935.5;1200:1250'")

# --- apply function (mirrors apply_bandwagon_cleaner) ---
def apply_rcvrstd_cleaner(ar, response=None, trimnum=0, trimfrac=0.0, trimbw=0.0,
                          badsubints=None, badchans=None, badfreqs=None):
    params = {"response": response if response is not None else "None",
              "trimnum": trimnum, "trimfrac": trimfrac, "trimbw": trimbw,
              "badsubints": badsubints if badsubints is not None else "None",
              "badchans":   badchans   if badchans   is not None else "None",
              "badfreqs":   badfreqs   if badfreqs   is not None else "None"}
    cleaner = cleaners.load_cleaner('rcvrstd')
    cleaner.parse_config_string(",".join("%s=%s" % kv for kv in params.items()))
    cleaner.run(ar)

# --- in main(), before/after surgical as appropriate ---
if args.use_rcvrstd:
    apply_rcvrstd_cleaner(loaded_archive, response=args.response, trimnum=args.trimnum,
                          trimfrac=args.trimfrac, trimbw=args.trimbw,
                          badsubints=args.badsubints, badchans=args.badchans,
                          badfreqs=args.badfreqs)
```
The `None`-string handling relies on the `nullable=True` params accepting the literal `"None"`
(handled in `BaseConfigType.get_param_value`, `config_types.py:31`).

**Risk / caveats.**
- **DEPENDS ON PARALLEL BUG FIXES.** `rcvrstd` is currently broken on Python 3: `badsubints`/
  `badchans` hit `types.IntType` (`rcvrstd.py:140,162`), `badfreqs` hits `types.FloatType`
  (`rcvrstd.py:186`), and setting `badchans`/`badfreqs` runs `IntOrIntPairList`/
  `FloatOrFloatPairList._value_to_string`, which use `types.TupleType`
  (`config_types.py:244,352`) — all `NameError`/`AttributeError` on Py3 (CODE_REVIEW 1.2). There
  is also an inclusive-interval off-by-one on `badchans` (`rcvrstd.py:169`, CODE_REVIEW 1.5). Do
  not expose `badchans`/`badfreqs`/`badsubints` on the CLI until those land; `response`/`trim*`
  alone are safe today (they don't touch the broken paths).
- Ordering matters: run `rcvrstd` *before* `surgical` so static zapping doesn't skew the
  statistics — see Suggestion 8 for user-selectable ordering.

---

## Suggestion 2 — Expose the `hotbins` cleaner (impulsive hot-bin replacement)

**What & where.** `coast_guard/cleaners/hotbins.py`. Params (`_set_config_params`,
`hotbins.py:22-51`):
- `threshold` / alias `thresh` (`FloatVal`, `hotbins.py:26`) — sigma cutoff for a bin to be
  replaced.
- `fscrunchfirst` / `tscrunchfirst` (`BoolVal`, `hotbins.py:30,34`) — detect hot bins in
  frequency- or time-scrunched data and replace across all channels/sub-ints.
- `onpulse` (`IntPairList`, `hotbins.py:38`) — `lo:hi[;lo:hi...]` bins excluded from off-pulse
  statistics.
- `iscal` / `calfrac` (`hotbins.py:42,49`) — calibrator-scan handling.

Hot bins deviating from the off-pulse MAD-derived sigma are replaced with matched Gaussian noise
(`__find_and_replace_hotbins`, `hotbins.py:91`).

**Why useful.** The surgical cleaner de-weights whole profiles; `hotbins` instead surgically
replaces individual bright *phase bins* (impulsive/narrow RFI, ADC spikes) while preserving the
rest of the profile — a complementary tool not otherwise reachable. `onpulse` protects the pulse
itself from being treated as an outlier.

**Argparse + wiring sketch.**
```python
parser.add_argument("--hotbins", dest="use_hotbins", action="store_true", default=False,
                    help="Run the hotbins cleaner (replace bright phase bins with noise)")
parser.add_argument("--hb-thresh", dest="hb_thresh", type=float, default=5.0,
                    help="Hotbins sigma threshold [default = 5.0]")
parser.add_argument("--hb-fscrunch", dest="hb_fscrunch", action="store_true", default=False,
                    help="Detect hot bins in f-scrunched data (non-dedispersed data only)")
parser.add_argument("--hb-tscrunch", dest="hb_tscrunch", action="store_true", default=False,
                    help="Detect hot bins in t-scrunched data")
parser.add_argument("--onpulse", dest="onpulse", type=str, default=None,
                    help="On-pulse bin regions to ignore, e.g. '480:540;900:930'")

def apply_hotbins_cleaner(ar, threshold=5.0, fscrunchfirst=False, tscrunchfirst=False,
                          onpulse=None):
    params = {"threshold": threshold, "fscrunchfirst": fscrunchfirst,
              "tscrunchfirst": tscrunchfirst,
              "onpulse": onpulse if onpulse is not None else ""}  # empty => no on-pulse region
    cleaner = cleaners.load_cleaner('hotbins')
    cleaner.parse_config_string(",".join("%s=%s" % kv for kv in params.items()))
    cleaner.run(ar)

if args.use_hotbins:
    apply_hotbins_cleaner(loaded_archive, threshold=args.hb_thresh,
                          fscrunchfirst=args.hb_fscrunch, tscrunchfirst=args.hb_tscrunch,
                          onpulse=args.onpulse)
```
Note `onpulse` defaults to the empty string in `default.cfg` (`onpulse=`), which
`IntPairList._string_to_value` parses to `[]` — so omitting it is valid.

**Risk / caveats.**
- **PARTIAL DEPENDENCE ON A PARALLEL BUG FIX.** The `fscrunchfirst` guard clause references
  `errors` without importing it (`hotbins.py:71`, CODE_REVIEW 1.1) — so `--hb-fscrunch` on
  already-dedispersed data raises a confusing `NameError` instead of a clean message. The
  threshold / `onpulse` / `tscrunchfirst` paths work today. Gate `--hb-fscrunch` on that
  one-line fix.
- Noise replacement is non-deterministic (`np.random.normal`, `hotbins.py:149`) — see
  Suggestion 5 (`--seed`).
- `iscal`/`calfrac` are intentionally omitted above (calibrator-specific); expose only if a cal
  workflow is needed.

---

## Suggestion 3 — Expose surgical piecewise-detrending params (and stop hardcoding numpieces)

**What & where.** `surgical.py:44-87` defines `chan_numpieces`/`subint_numpieces` (`IntList`),
`chan_order`/`subint_order` (`IntList`), and `chan_breakpoints`/`subint_breakpoints`
(`IntListList`). These flow into `clean_utils.comprehensive_stats`
(`surgical.py:266-276` → `clean_utils.py:50`), which detrends each channel/sub-int piecewise
before computing robust outlier statistics. **Today `apply_surgical_cleaner`
(`clean_archive.py:43`) hardcodes `chan_numpieces=1,subint_numpieces=1`**, overriding the
config-file defaults and forcing single-piece (whole-band / whole-observation) detrending.

**Why useful.** Piecewise detrending is the core mechanism that lets the surgical cleaner follow
bandpass/gain structure that varies across the band or the observation. Forcing `numpieces=1`
means a single polynomial must fit the entire channel/sub-int, which under-fits real MeerKAT
bandpass shape and either misses RFI or over-flags good data. Exposing these (and honoring the
config defaults instead of hardcoding) restores the intended behavior and lets users tune it.

**Argparse + wiring sketch.** Replace the hardcoded literals in `apply_surgical_cleaner` with
plumbed-through values (see Suggestion 7 for the dict-based builder this fits into):
```python
parser.add_argument("--chan-numpieces", dest="chan_numpieces", type=int, default=1,
                    help="Pieces per channel for piecewise detrending [default = 1]")
parser.add_argument("--subint-numpieces", dest="subint_numpieces", type=int, default=1,
                    help="Pieces per sub-int for piecewise detrending [default = 1]")
parser.add_argument("--chan-order", dest="chan_order", type=str, default="1",
                    help="Detrend polynomial order(s) per channel, e.g. '1' or '1;2'")
parser.add_argument("--subint-order", dest="subint_order", type=str, default="2;1",
                    help="Detrend polynomial order(s) per sub-int, e.g. '2;1'")

# inside apply_surgical_cleaner(...), extra kwargs chan_numpieces/subint_numpieces/
# chan_order/subint_order flow into the params dict:
params = {
    "template": tmp, "chanthresh": cthresh, "subintthresh": sthresh,
    "chan_numpieces": chan_numpieces, "subint_numpieces": subint_numpieces,
    "chan_order": chan_order, "subint_order": subint_order,
    "plot": plot, "aggressive": aggressive, "iterations": iterations,
}
```
`IntList` uses `;` as its separator, so `"2;1"` is a valid config value and comma-safe.

**Risk / caveats.**
- Default of `1`/`1` here preserves *today's* behavior; consider instead defaulting to the
  `default.cfg` values (`chan_numpieces=4`, `subint_numpieces=[2,4]`) so the cleaner behaves as
  its authors intended. That is a behavior change and should be validated against known data.
- `chan_order`/`subint_order`, `numpieces`, and `breakpoints` are zipped together in
  `clean_utils.subint_scaler`; mismatched lengths are silently truncated by `zip`
  (CODE_REVIEW 1.12). Keep the order-list length ≤ the numpieces-list length, or fix the zip.
- `chan_breakpoints`/`subint_breakpoints` (`IntListList`, `;;`-separated) are lower value and
  awkward on a CLI — recommend leaving them at their `None`/default rather than adding flags.

---

## Suggestion 4 — Configurable plot output location, and `-v/-q` verbosity via `log.py`

**What & where.**
- Verbosity: `utils.print_info` (`utils.py:373`) already gates on the module-level globals
  `config.verbosity` and `config.log_verbosity` (loaded from `global.cfg` into the `config`
  module at import, `config.py:19-21`; default `verbosity=0`). `BaseCleaner.run` already calls
  `utils.print_info(...)` (`cleaners/__init__.py:161`). Setting `config.verbosity` turns those on.
- Plots: `surgical.py` writes `data_and_template.png` and `avg_test_results.png` to the CWD
  (`surgical.py:259,284`).

**Why useful.** Progress currently goes to stdout unconditionally via bare `print` (see
CODE_REVIEW 2), with no quiet mode for batch/pipeline use and no verbose mode to surface the
`print_info` diagnostics that already exist inside the cleaners. Fixed plot filenames in the CWD
mean parallel runs clobber each other's diagnostics.

**Argparse + wiring sketch.**
```python
from coast_guard import config as cg_config   # module-level globals live here

parser.add_argument("-v", "--verbose", dest="verbosity", action="count", default=0,
                    help="Increase verbosity (repeatable: -v, -vv)")
parser.add_argument("-q", "--quiet", dest="quiet", action="store_true", default=False,
                    help="Suppress informational output")

# early in main():
cg_config.verbosity = 0 if args.quiet else args.verbosity
cg_config.log_verbosity = cg_config.verbosity
```
For plot location, the clean way is a new surgical config param (e.g. `plotname`/`plotdir`) —
but that requires a small parallel edit to `surgical.py` where the filenames are hardcoded. A
zero-source-change alternative reachable from `clean_archive.py` alone is to `os.chdir` into the
output directory (or a `--plot-dir`) before `.run()`:
```python
parser.add_argument("--plot-dir", dest="plot_dir", type=str, default=None,
                    help="Directory for diagnostic plots [default = CWD]")
# ...
if args.plot and args.plot_dir:
    os.makedirs(args.plot_dir, exist_ok=True)
    os.chdir(args.plot_dir)   # surgical writes PNGs to CWD
```

**Risk / caveats.**
- The cleaners still use bare `print` (CODE_REVIEW 2), so `-q` won't silence *all* output until
  those are routed through `print_info` — a parallel cleanup. The flag is still worth adding now
  because it controls the `print_info` diagnostics.
- The `os.chdir` trick affects relative output paths for the archive too; prefer resolving
  `args.output_path`/`args.output_name` to absolute paths first, or (better) add the
  `plotname`/`plotdir` param to `surgical.py`.

---

## Suggestion 5 — Reproducible RNG (`--seed`)

**What & where.** `surgical.py`/`hotbins.py` replace flagged data with `np.random.normal(...)`
(e.g. `hotbins.py:149`). No seeding today, so cleaned archives are not bit-reproducible.

**Why useful.** Reproducibility for regression tests, debugging, and publishable pipelines. One
seeding call at the top of `main()` covers every downstream `np.random` draw.

**Argparse + wiring sketch.**
```python
parser.add_argument("--seed", dest="seed", type=int, default=None,
                    help="Seed the RNG for reproducible noise replacement")
# early in main():
if args.seed is not None:
    import numpy as np
    np.random.seed(args.seed)
```

**Risk / caveats.** Uses the legacy global `np.random` state, which is process-global; fine for
this single-archive CLI. If the cleaners are later parallelized (`nthreads`, CODE_REVIEW 4.9),
per-worker seeding would be needed.

---

## Suggestion 6 — Input validation, output-name template, and a `console_scripts` entry point

**What & where.** `clean_archive.py:76-77` mark `-a/--archive` and `-T/--template` as optional,
but `ps.Archive_load(None)` (`clean_archive.py:91`) fails cryptically when omitted; there is no
range check on thresholds/tolerances. Output naming (`clean_archive.py:99`) hardcodes
`"{pref}_ch{chanthresh}_sub{subintthresh}.ar"`, embedding floats like `ch7.0`. `utils.get_outfn`
(`utils.py:1139`) already supports header-based templating. Packaging uses
`scripts=["clean_archive.py"]` (`setup.py:22-24`).

**Why useful.** Fail-fast validation replaces confusing PSRCHIVE tracebacks with actionable
errors; a proper entry point (`meerguard` instead of `clean_archive.py`) is the conventional,
installable interface and is a prerequisite for `-v/-q` and testability.

**Argparse + wiring sketch.**
```python
def main():
    parser = argparse.ArgumentParser(description="Run MeerGuard on input archive file")
    # ... all add_argument(...) calls ...
    args = parser.parse_args()

    # --- validation ---
    if not args.archive_path or not os.path.isfile(args.archive_path):
        parser.error("archive (-a/--archive) is required and must exist")
    if args.template_path is not None and not os.path.isfile(args.template_path):
        parser.error("template (-T/--template) does not exist: %s" % args.template_path)
    for name, val in (("chanthresh", args.chan_thresh), ("subthresh", args.subint_thresh)):
        if val <= 0:
            parser.error("%s must be positive" % name)
    for name, val in (("badchantol", args.badchantol), ("badsubtol", args.badsubtol)):
        if not (0.0 <= val <= 1.0):
            parser.error("%s must be in [0, 1]" % name)
    # ... run cleaners, unload ...

if __name__ == "__main__":
    main()
```
`setup.py`:
```python
entry_points={"console_scripts": ["meerguard = clean_archive:main"]},
# (drop scripts=[...]; or migrate the whole thing to pyproject.toml [project.scripts])
```
Note: `clean_archive.py` lives at the repo root, not inside the `coast_guard` package, so the
entry point is `clean_archive:main`. Moving the module into `coast_guard/` (→
`coast_guard.clean_archive:main`) is cleaner but is a larger change.

**Risk / caveats.**
- Wrapping in `main()` is a prerequisite for the entry point and for unit-testing argument
  handling (there are currently no tests — CODE_REVIEW 4.5).
- A full `get_outfn` template (`-o "%(name)s_%(mjd)s.ar"`) needs a `utils.ArchiveFile` wrapper
  (vap header lookup), which is heavier; a minimal first step is just to stop embedding the
  float thresholds in the default name.

---

## Suggestion 7 — Dict-based config-string builder (refactor of the brittle positional format)

**What & where.** `apply_surgical_cleaner` (`clean_archive.py:43`) builds the config string with
out-of-order positional fields:
```python
surgical_parameters = "chan_numpieces=1,subint_numpieces=1,chanthresh={1},subintthresh={2},template={0},plot={3},aggressive={4},iterations={5}".format(tmp, cthresh, sthresh, plot, aggressive, iterations)
```
The `{0}..{5}` mapping is easy to misalign, and it is exactly where the new surgical params from
Suggestion 3 need to be threaded in (CODE_REVIEW 2).

**Why useful.** A dict keyed by param name is self-documenting, order-independent, and the single
natural insertion point for every additional surgical param. It removes a whole class of
positional-index bugs and makes the wiring in Suggestions 3/4 trivial.

**Refactor sketch.**
```python
def apply_surgical_cleaner(ar, tmp, cthresh=7.0, sthresh=7.0, plot=False,
                           aggressive=False, iterations=1,
                           chan_numpieces=1, subint_numpieces=1,
                           chan_order="1", subint_order="2;1"):
    params = {
        "template": tmp if tmp is not None else "None",
        "chanthresh": cthresh, "subintthresh": sthresh,
        "chan_numpieces": chan_numpieces, "subint_numpieces": subint_numpieces,
        "chan_order": chan_order, "subint_order": subint_order,
        "plot": plot, "aggressive": aggressive, "iterations": iterations,
    }
    cfgstr = ",".join("%s=%s" % (k, v) for k, v in params.items())
    cleaner = cleaners.load_cleaner('surgical')
    cleaner.parse_config_string(cfgstr)
    cleaner.run(ar)
```

**Risk / caveats.**
- Behavior-preserving as long as the same keys/values are emitted. Watch the `template=None`
  case: today the code passes `template={0}` with `tmp` possibly `None`, producing the literal
  string `"template=None"`, which `nullable=True` handles correctly (`config_types.py:31`) — keep
  that mapping.
- Do not `str.format` user values that could contain `,` or `=`; the `%s` join is fine because
  list params use `;`/`:` separators.

---

## Suggestion 8 — User-selectable cleaner chain / order (`--cleaners`)

**What & where.** `cleaners.load_cleaner` (`cleaners/__init__.py:19`) can instantiate any of the
four registered cleaners by name. `clean_archive.py` currently hardwires the order
surgical → bandwagon (`clean_archive.py:104-105`).

**Why useful.** Different data need different pipelines: static zapping (`rcvrstd`) should run
*first*; some users want `hotbins` before `surgical`; others want `surgical` only. A single
`--cleaners` flag lets the observer compose and order the chain without code changes, and makes
the four cleaners genuinely first-class from the entry point.

**Argparse + wiring sketch.**
```python
parser.add_argument("--cleaners", dest="cleaners", type=str, default="surgical,bandwagon",
                    help="Comma-separated, ordered cleaner chain. "
                         "Choices: surgical,bandwagon,rcvrstd,hotbins "
                         "[default = surgical,bandwagon]")
# ...
apply_funcs = {
    "surgical":  lambda ar: apply_surgical_cleaner(ar, args.template_path,
                    cthresh=args.chan_thresh, sthresh=args.subint_thresh, plot=args.plot,
                    aggressive=args.aggressive, iterations=args.iterations,
                    chan_numpieces=args.chan_numpieces, subint_numpieces=args.subint_numpieces),
    "bandwagon": lambda ar: apply_bandwagon_cleaner(ar, badchantol=args.badchantol,
                    badsubtol=args.badsubtol),
    "rcvrstd":   lambda ar: apply_rcvrstd_cleaner(ar, response=args.response, ...),
    "hotbins":   lambda ar: apply_hotbins_cleaner(ar, threshold=args.hb_thresh, ...),
}
chain = [c.strip() for c in args.cleaners.split(",") if c.strip()]
unknown = [c for c in chain if c not in apply_funcs]
if unknown:
    parser.error("unknown cleaner(s): %s" % ", ".join(unknown))
for name in chain:
    apply_funcs[name](loaded_archive)
```

**Risk / caveats.**
- Validate names against `cleaners.registered_cleaners` / the local `apply_funcs` map and error
  early (shown above).
- `rcvrstd` and `hotbins` entries are only safe once their Python-3 bugs land (Suggestions 1, 2).
  Until then, either omit them from `apply_funcs` or gate their availability.
- Keep `surgical,bandwagon` as the default so existing behavior/scripts don't change.

---

## Prioritized shortlist (highest value / lowest risk first)

1. **Suggestion 7 — dict-based config builder.** Pure refactor, no bug dependency, unblocks 3/4;
   removes the brittle positional format. Do this first.
2. **Suggestion 6 — validation + `main()` + `console_scripts`.** No cleaner dependency; big
   usability win (fail-fast, installable `meerguard` command) and prerequisite for tests and for
   `-v/-q`. Low risk.
3. **Suggestion 3 — surgical detrending params (stop hardcoding numpieces).** Reachable, working
   code today; restores the cleaner's core intended behavior. Low risk if defaults preserve
   current behavior; medium if you switch to `default.cfg` values.
4. **Suggestion 4 & 5 — verbosity, plot location, `--seed`.** Small, orthogonal quality-of-life
   additions; verbosity/seed are trivially reachable. Plot-dir is cleanest with a small parallel
   `surgical.py` param addition.
5. **Suggestion 8 — `--cleaners` chain selection.** High value, but its full value depends on
   `rcvrstd`/`hotbins` being fixed; ship with `surgical,bandwagon` first, widen once 1/2 land.
6. **Suggestion 2 — expose `hotbins`.** Mostly works today; only `--hb-fscrunch`-on-dedispersed
   needs the one-line `import errors` fix (CODE_REVIEW 1.1).
7. **Suggestion 1 — expose `rcvrstd`.** Highest observer demand, but **blocked** on the Python-3
   `types.*` fixes (CODE_REVIEW 1.2) and the interval off-by-one (1.5). Expose `response`/`trim*`
   first (safe today); add `badchans`/`badfreqs`/`badsubints` only after the fixes land.

### Dependence on the parallel bug fixes
- **Suggestion 1 (rcvrstd `badchans`/`badfreqs`/`badsubints`)** — BLOCKED by CODE_REVIEW 1.2
  (`types.IntType`/`types.FloatType`/`types.TupleType`) and 1.5 (channel-interval off-by-one).
- **Suggestion 2 (`--hb-fscrunch`)** — BLOCKED by CODE_REVIEW 1.1 (`import errors` in
  `hotbins.py`); the rest of `hotbins` works now.
- **Suggestion 8 (`rcvrstd`/`hotbins` chain entries)** — inherits the above.
- **Suggestion 4 (`-q` silencing all output)** — partial; full effect needs the `print`→
  `print_info` cleanup (CODE_REVIEW 2). The `plotdir`/`plotname` variant needs a small
  `surgical.py` param addition.
- Suggestions 3, 5, 6, 7 have **no** bug-fix dependency and can proceed immediately.
