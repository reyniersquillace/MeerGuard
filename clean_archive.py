#!/usr/bin/env python

"""
Command-line entry point for running MeerGuard on a single PSRCHIVE archive.

Loads an archive, applies the surgical and bandwagon cleaners with
user-specified thresholds, and writes out the cleaned archive.
"""

# For python3 and python2 compatibility
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

# Import CoastGuard
from coast_guard import cleaners
import argparse
import psrchive as ps
import os
import click

def apply_surgical_cleaner(ar, tmp, cthresh=7.0, sthresh=7.0, plot=False, aggressive=False, iterations=1):
    """Apply the surgical cleaner to an archive in place.

        Inputs:
            ar: The psrchive Archive object to clean.
            tmp: Path to the (optionally 2D) template file to use.
            cthresh: Channel threshold in sigma. (Default: 7.0)
            sthresh: Sub-int threshold in sigma. (Default: 7.0)
            plot: If True, produce diagnostic plots. (Default: False)
            aggressive: If True, use more aggressive cleaning thresholds
                and algorithms. (Default: False)
            iterations: Number of times to run the surgical cleaner.
                (Default: 1)

        Outputs:
            None - The archive is cleaned in place.
    """
    print("Applying the surgical cleaner")
    print("\t channel threshold = {0}".format(cthresh))
    print("\t  subint threshold = {0}".format(sthresh))
    print("\t  iterations = {0}".format(iterations))

    surgical_cleaner = cleaners.load_cleaner('surgical')
    surgical_parameters = "chan_numpieces=1,subint_numpieces=1,chanthresh={1},subintthresh={2},template={0},plot={3},aggressive={4},iterations={5}".format(tmp, cthresh, sthresh, plot, aggressive, iterations)
    surgical_cleaner.parse_config_string(surgical_parameters)
    surgical_cleaner.run(ar)

def apply_bandwagon_cleaner(ar, badchantol=0.95, badsubtol=0.95):
    """Apply the bandwagon cleaner to an archive in place.

        This de-weights whole sub-ints/channels once the fraction of
        already-masked profiles they contain exceeds the given tolerances.

        Inputs:
            ar: The psrchive Archive object to clean.
            badchantol: The fraction of bad channels tolerated before a
                sub-int is completely masked. (Default: 0.95)
            badsubtol: The fraction of bad sub-ints tolerated before a
                channel is completely masked. (Default: 0.95)

        Outputs:
            None - The archive is cleaned in place.
    """
    print("Applying the bandwagon cleaner")
    print("\t channel threshold = {0}".format(badchantol))
    print("\t  subint threshold = {0}".format(badsubtol))

    bandwagon_cleaner = cleaners.load_cleaner('bandwagon')
    bandwagon_parameters = "badchantol={0},badsubtol={1}".format(badchantol, badsubtol)
    bandwagon_cleaner.parse_config_string(bandwagon_parameters)
    bandwagon_cleaner.run(ar)

#switching to click for more versatility
@click.command(help="Run MeerGuard on input archive file")
#click will automatically send an error message if the user doesn't input -a and -T!
@click.option("-a", "--archive", "archive_path", type=str, required=True,
              help="REQUIRED: Path to the archive file")
@click.option("-T", "--template", "template_path", type=str, required=True,
              help="REQUIRED: Path to the 2D template file")
@click.option("-c", "--chanthresh", "chan_thresh", type=float, default=None,
              help="Channel threshold (in sigma) [default = 7.0 (5.0 with --aggressive)]")
@click.option("-s", "--subthresh", "subint_thresh", type=float, default=None,
              help="Subint threshold (in sigma) [default = 7.0 (5.0 with --aggressive)]")
@click.option("-bc", "--badchantol", "badchantol", type=float, default=None,
              help="Fraction of bad channels threshold [default = 0.95 (0.8 with --aggressive)]")
@click.option("-bs", "--badsubtol", "badsubtol", type=float, default=None,
              help="Fraction of bad subints threshold [default = 0.95 (0.8 with --aggressive)]")
@click.option("-o", "--outname", "output_name", type=str, default=None,
              help="Output archive name")
@click.option("-plot", "--plot", "plot", is_flag=True, default=False)
@click.option("-O", "--outpath", "output_path", type=str, default=os.getcwd(),
              help="Output path [default = CWD]")
@click.option("-ag", "--aggressive", "aggressive", is_flag=True, default=False,
              help="Whether to use more aggressive cleaning thresholds and algorithms")
@click.option("-i", "--iterations", "iterations", type=int, default=1,
              help="Number of iterations to run the surgical cleaner [default = 1]")

def main(archive_path, template_path, chan_thresh, subint_thresh, badchantol,
         badsubtol, output_name, plot, output_path, aggressive, iterations):
    
    # Resolve the cleaning thresholds. When --aggressive is given, any
    # threshold the user did NOT set explicitly on the command line falls
    # back to the documented aggressive value; otherwise it falls back to the
    # normal default. Explicit user overrides are preserved either way.
    
    if aggressive:
        threshold_defaults = {'chan_thresh': 5.0, 'subint_thresh': 5.0,
                              'badchantol': 0.8, 'badsubtol': 0.8}
    else:
        threshold_defaults = {'chan_thresh': 7.0, 'subint_thresh': 7.0,
                              'badchantol': 0.95, 'badsubtol': 0.95}
 
    if chan_thresh is None:
        chan_thresh = threshold_defaults['chan_thresh']
    if subint_thresh is None:
        subint_thresh = threshold_defaults['subint_thresh']
    if badchantol is None:
        badchantol = threshold_defaults['badchantol']
    if badsubtol is None:
        badsubtol = threshold_defaults['badsubtol']
 
    # Load an Archive file
    loaded_archive = ps.Archive_load(archive_path)
    archive_path_dir, archive_name = os.path.split(loaded_archive.get_filename())
    archive_name_pref = archive_name.split('.')[0]
    archive_name_suff = "".join(archive_name.split('.')[1:])
 
    # Renaming archive file with statistical thresholds
    if output_name is None:
        out_name = "{0}_ch{1}_sub{2}.ar".format(archive_name_pref, chan_thresh, subint_thresh)
    else:
        out_name = output_name
 
 
    apply_surgical_cleaner(loaded_archive, template_path, cthresh=chan_thresh, sthresh=subint_thresh, plot=plot, aggressive=aggressive, iterations=iterations)
    apply_bandwagon_cleaner(loaded_archive, badchantol=badchantol, badsubtol=badsubtol)
 
    # Unload the Archive file
    print("Unloading the cleaned archive: {0}".format(out_name))
    loaded_archive.unload(str(out_name))  # need to typecast to str here because otherwise Python converts to a unicode string which the PSRCHIVE library can't parse
 
 
if __name__ == "__main__":
    main()
