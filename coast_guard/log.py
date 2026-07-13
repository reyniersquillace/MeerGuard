"""
Logging helpers for the CoastGuard/MeerGuard pipeline.

Provides per-process loggers (keyed by PID) and utilities for attaching a
file handler and adjusting group file permissions on log files.
"""
import os
import logging
import stat


levels = {'debug': logging.DEBUG, \
          'info': logging.INFO, \
          'warning': logging.WARNING, \
          'error': logging.ERROR, \
          'critical': logging.CRITICAL}


PERMS = {"w": stat.S_IWGRP,                 
         "r": stat.S_IRGRP,                 
         "x": stat.S_IXGRP}                 
def add_group_permissions(fn, perms=""):
    """Add group-level file permissions to a file.

        Inputs:
            fn: The name of the file to modify.
            perms: A string of permission characters to add for the
                group. Any of 'w' (write), 'r' (read) and 'x' (execute).
                (Default: add no permissions)

        Outputs:
            None
    """
    mode = os.stat(fn)[stat.ST_MODE]
    for perm in perms:
        mode |= PERMS[perm]
    os.chmod(fn, mode)


def get_logger():
    """Get a logger instance. The name of the logger
        is automatically determined using the current
        processes ID.

        Inputs:
            None

        Output:
            logger: A logging.Logger instance.
    """
    name = str(os.getpid())
    logger = logging.getLogger(name)
    return logger


def setup_logger(logfn):
    """Set up a logging.Logger instance for the current thread.
        Install a FileHandler using the file name provided.

        Input:
            logfn: File to receive log entries.

        Outputs:
            None
    """
    logger = get_logger()
    # Remove any existing handlers
    disconnect_logger() 
    # What gets logged is determined by if-clauses that 
    # check the current verbosity level and debugging state, 
    # not logging's level, so let everything be logged. 
    logger.setLevel(logging.DEBUG) 
    logfile = logging.FileHandler(filename=logfn)
    formatter = logging.Formatter(datefmt="%Y-%m-%d %H:%M:%S", \
                fmt="%(levelname)s - %(asctime)s\n%(message)s\n")
    logfile.setFormatter(formatter)
    logger.addHandler(logfile)
    try:
        add_group_permissions(logfn, "rw")
    except:
        pass


def disconnect_logger():
    """Disconnect logger from any handlers.

        Inputs:
            None

        Outputs:
            None
    """
    logger = get_logger()
    for handler in logger.handlers:
        logger.removeHandler(handler)


def log(msg, levelname):
    """Log a message at the named level using the current process's logger.

        Inputs:
            msg: The message to log.
            levelname: The name of the logging level. One of 'debug',
                'info', 'warning', 'error' or 'critical'.

        Outputs:
            None
    """
    logger = get_logger()
    logger.log(levels[levelname], msg)
