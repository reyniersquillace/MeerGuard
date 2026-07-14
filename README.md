# MeerGuard
The MeerTime copy of coast_guard: https://github.com/plazar/coast_guard

The code has been stripped for only RFI excision, and modified for use on wide-bandwidth data.

The surgical cleaner can now read in a template, which it subtracts from the data to form profile residuals. The template can be frequency-dependent if required (e.g. if there is substantial profile evolution) and is used to identify an off-pulse region. The statistics used by the surgical cleaner are calculated only using this off-pulse region.

The code can be installed using

```
python setup.py install
```

The MeerGuard pipeline needs at least three options to run: the archive file to clean, the output file name, and a 2D template archive file. The routine subtracts the template to avoid zapping bright scintles.

Example usage:

```
python clean_archive.py -a my_archive_file.rf -T my_template_file.rf -O my_clean_file.mg
```

