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
from coast_guard import config

import argparse
import psrchive as ps
import os
import click

def apply_rcvrstd_cleaner(ar):
    """This function applies the cleaner specified by a config file for the receiver."""
    
    print("Applying the receiver cleaner")
    rcvrstd_cleaner = cleaners.load_cleaner('rcvrstd')
    rcvrstd_cleaner.run(ar)

def apply_surgical_cleaner(ar, tmp, cthresh=None, sthresh=None, plot=False, aggressive=False, iterations=1):
    
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
    param_parts = [
        "template={0}".format(tmp),
        "plot={0}".format(plot),
        "aggressive={0}".format(aggressive),
        "iterations={0}".format(iterations),
    ]
    if cthresh is not None:
        param_parts.append("chanthresh={0}".format(cthresh))
    if sthresh is not None:
        param_parts.append("subintthresh={0}".format(sthresh))
    surgical_parameters = ",".join(param_parts)
    surgical_cleaner.parse_config_string(surgical_parameters)
    surgical_cleaner.run(ar)


def apply_bandwagon_cleaner(ar, badchantol=None, badsubtol=None):
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
    param_parts = []
    if badchantol is not None:
        param_parts.append("badchantol={0}".format(badchantol))
    if badsubtol is not None:
        param_parts.append("badsubtol={0}".format(badsubtol))
    if param_parts:
        bandwagon_cleaner.parse_config_string(",".join(param_parts))
    bandwagon_cleaner.run(ar)

#switching to click for more versatility
@click.command(help="Run MeerGuard on input archive file")
#click will automatically send an error message if the user doesn't input -a and -T!
@click.argument("archive_paths", nargs=-1, required=True)
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
@click.option("-e", "--extension", "extension", type=str, default=None,
              help="Output file extension")
@click.option("-plot", "--plot", "plot", is_flag=True, default=False)
@click.option("-O", "--outpath", "output_path", type=str, default=os.getcwd(),
              help="Output path [default = CWD]")
@click.option("-ag", "--aggressive", "aggressive", is_flag=True, default=False,
              help="Whether to use more aggressive cleaning thresholds and algorithms")
@click.option("-i", "--iterations", "iterations", type=int, default=1,
              help="Number of iterations to run the surgical cleaner [default = 1]")
@click.option("-C", "--config", "config_path", type=str, default=None,
              help="Custom config file for misbehaving receivers. Inputting UHF or L will "
              "automatically load the MeerKAT config files for those receivers. Inputting "
              "UWL will automatically load the config file for the Murriyang ultrawide "
              "low frequency receiver.")

def main(archive_paths, template_path, chan_thresh, subint_thresh, badchantol,
         badsubtol, output_name, extension, plot, output_path, aggressive, iterations,
         config_path):
    
    #raise error if user tries to write multiple input files to one output name
    #have to use extension for that option
    if output_name is not None and len(archive_paths) > 1:
        raise click.UsageError(
        "-o cannot be used with multiple files. Your options are:"
        "1. Use the -e option to replace extensions on each file."
        "2. Use default output file names."
        "3. Run on one archive file at a time."
        )

    #make sure there's either -o or -e, not both
    if output_name is not None and extension is not None:
        raise click.UsageError(
            "-o and -e cannot be used together. "
            "Please make your mind up... :)"
        )
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
    
        
    defer_to_config = (config_path is not None) and not aggressive

    if chan_thresh is None and not defer_to_config:
        chan_thresh = threshold_defaults['chan_thresh']
    if subint_thresh is None and not defer_to_config:
        subint_thresh = threshold_defaults['subint_thresh']
    if badchantol is None and not defer_to_config:
        badchantol = threshold_defaults['badchantol']
    if badsubtol is None and not defer_to_config:
        badsubtol = threshold_defaults['badsubtol']

    #grab custom config values if sent in with -C 
    if config_path is not None:

        if config_path in ('UHF', 'uhf'):
            config_path = os.path.join(config.base_config_dir, 'receivers', 'UHF_4K_MeerKAT.cfg')
        elif config_path in ('L', 'Lband', 'L-band'):
            config_path = os.path.join(config.base_config_dir, 'receivers', 'L-band_4K_MeerKAT.cfg')
        elif config_path in ('UWL', 'uwl'):
            config_path = os.path.join(config.base_config_dir, 'receivers', 'UWL_3K_Murriyang.cfg')

        config_overrides = config.read_file(config_path, required=True)
        cfg_obj = config.cfg.get()
        for key, val in config_overrides.items():
            cfg_obj.set_override_config(key, val)

    for archive_path in archive_paths:
        print("Processing archive: {0}".format(archive_path))


        # Load an Archive file
        loaded_archive = ps.Archive_load(archive_path)
        archive_path_dir, archive_name = os.path.split(loaded_archive.get_filename())
        archive_name_pref = archive_name.split('.')[0]
        archive_name_suff = "".join(archive_name.split('.')[1:])

        # Renaming archive file with statistical thresholds
        if output_name is not None:
            out_name = output_name
        elif extension is not None:
            out_name = "{0}.{1}".format(archive_name_pref, extension)
        else:
            out_name = "{0}_ch{1}_sub{2}.ar".format(
                archive_name_pref,
                chan_thresh if chan_thresh is not None else "cfg",
                subint_thresh if subint_thresh is not None else "cfg")

        apply_rcvrstd_cleaner(loaded_archive)
        apply_surgical_cleaner(loaded_archive, template_path, cthresh=chan_thresh, sthresh=subint_thresh, plot=plot, aggressive=aggressive, iterations=iterations)
        apply_bandwagon_cleaner(loaded_archive, badchantol=badchantol, badsubtol=badsubtol)

        # Unload the Archive file
        print("Unloading the cleaned archive: {0}".format(out_name))
        loaded_archive.unload(str(out_name))  # need to typecast to str here because otherwise Python converts to a unicode string which the PSRCHIVE library can't parse

if __name__ == "__main__":
    main()
