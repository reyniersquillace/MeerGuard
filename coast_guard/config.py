"""
Configuration handling for CoastGuard/MeerGuard.

Reads configuration values from '.cfg' files (which are executed as Python)
and exposes them via a layered lookup (overrides, observation configs and
defaults). A thread-/process-aware manager (`cfg`) hands out per-process
configuration objects.
"""
import sys
import copy
import os


base_config_dir = os.path.join(os.path.dirname(__file__), 'configurations')
receiver_config_dir = os.path.join(base_config_dir, 'receivers')


# python3
with open(os.path.join(base_config_dir, "global.cfg")) as f:
    code = compile(f.read(), os.path.join(base_config_dir, "global.cfg"), 'exec')
    exec(code, {}, locals())

class ConfigDict(dict):
    """A dictionary of configuration values.

        Supports combining two configurations with '+' (returning a new
        dict where the right operand's values take precedence) and a
        readable string representation.
    """
    def __add__(self, other):
        """Return a new ConfigDict combining self with 'other'.
            Values in 'other' override those in self.
        """
        newcfg = copy.deepcopy(self)
        newcfg.update(other)
        return newcfg

    def __str__(self):
        """Return the configurations as sorted 'key: value' lines."""
        lines = []
        for key in sorted(self.keys()):
            lines.append("%s: %r" % (key, self[key]))
        return "\n".join(lines)


def read_file(fn, required=False):
    """Read a configuration file and return its contents.

        The file (which must end in '.cfg') is executed as Python and any
        names it defines become configuration entries.

        Inputs:
            fn: The path to the configuration file.
            required: If True, raise ValueError when the file is missing.
                (Default: False)

        Output:
            cfgdict: A ConfigDict of the values defined in the file
                (empty if the file does not exist and is not required).
    """
    cfgdict = ConfigDict()
    if os.path.isfile(fn):
        if not fn.endswith('.cfg'):
            raise ValueError("Coast Guard configuration files must "
                             "end with the extention '.cfg'.")
        key = os.path.split(fn)[-1][:-4]
        # python2
        #execfile(fn, {}, cfgdict)
        # python3
        with open(fn) as f:
            code = compile(f.read(), fn, 'exec')
            exec(code, {}, cfgdict)
    elif required:
            raise ValueError("Configuration file (%s) doesn't exist "
                             "and is required!" % fn)
    return cfgdict


class CoastGuardConfigs(object):
    """A layered set of CoastGuard configurations.

        Values are looked up in order of precedence: user overrides,
        observation-specific configs, then defaults.
    """
    def __init__(self, base_config_dir=base_config_dir):
        """Load the default configurations from 'base_config_dir'.

            Input:
                base_config_dir: Directory containing the configuration
                    files (must contain 'default.cfg').
        """
        self.base_config_dir = base_config_dir
        default_config_fn = os.path.join(self.base_config_dir, "default.cfg")

        self.defaults = read_file(default_config_fn, required=True)
        self.obsconfigs = ConfigDict()
        self.overrides = ConfigDict()

    def __getattr__(self, key):
        """Look up configuration 'key' via attribute access."""
        return self.__getitem__(key)

    def __getitem__(self, key):
        """Return the value for 'key', respecting the precedence order.
            Exits the program if the key cannot be found.
        """
        if key in self.overrides:
            val = self.overrides[key]
        elif key in self.obsconfigs:
            val = self.obsconfigs[key]
        elif key in self.defaults:
            val = self.defaults[key]
        else:
            print("The configuration {0} cannot be found!".format(key))
            sys.exit()
        return val

    def __str__(self):
        """Return a human-readable summary of all configuration layers."""
        allkeys = set.union(set(self.defaults.keys()),
                            set(self.obsconfigs.keys()),
                            set(self.overrides.keys()))
        lines = ["Current configurations:"]
        #for key in allkeys:
        #    lines.append("    %s: %s" % (key, self[key]))
        lines.append("    "+str(self.defaults+self.obsconfigs+self.overrides).replace("\n", "\n    "))
        lines.append("Overrides:")
        lines.append("    "+str(self.overrides).replace("\n", "\n     "))
        lines.append("Observation configurations:")
        lines.append("    "+str(self.obsconfigs).replace("\n", "\n    "))
        lines.append("Defaults:")
        lines.append("    "+str(self.defaults).replace("\n", "\n    "))
        return "\n".join(lines)

    def clear_obsconfigs(self):
        """Clear all observation-specific configurations."""
        self.obsconfigs.clear()

    def clear_overrides(self):
        """Clear all override configurations."""
        self.overrides.clear()

    def set_override_config(self, key, val):
        """Set an override configuration value for 'key' to 'val'."""
        self.overrides[key] = val

    def load_configs_for_archive(self, arfn):
        """Given a psrchive archive file set current configurations to the values
            pre-set for this observation, pulsar, backend, receiver, telescope.

            Inputs:
                fn: The psrchive archive to get configurations for.

            Outputs:
                None
        """
        self.clear_obsconfigs()

        config_files = []  # A list of configuration files to look for

        telescope = arfn['telname']
        precedence = [arfn['telname'].lower(),
                      arfn['rcvr'].lower(),
                      arfn['backend'].lower()]

        cfgdir = self.base_config_dir
        for dirname in precedence:
            cfgdir = os.path.join(cfgdir, dirname)
            config_files.append(os.path.join(cfgdir, 'configs.cfg'))

        #config_files.append(os.path.join(self.base_config_dir, 'telescopes',
        #                    "%s.cfg" % telescope.lower()))
        #config_files.append(os.path.join(self.base_config_dir, 'receivers',
        #                    "%s.cfg" % arfn['rcvr'].lower()))
        #config_files.append(os.path.join(self.base_config_dir, 'backends',
        #                    "%s.cfg" % arfn['backend'].lower()))
        #config_files.append(os.path.join(self.base_config_dir, 'pulsars',
        #                    "%s.cfg" % arfn['name'].upper()))
        #config_files.append(os.path.join(self.base_config_dir, 'observations',
        #                    "%s.cfg" % os.path.split(arfn.fn)[-1]))
        #msg = "\n    ".join(["Checking for the following configurations:"] + \
        #                        config_files)

        for fn in config_files:
            self.obsconfigs += read_file(fn)


class ConfigManager(object):
    """An object to hold and manage CoastCuardConfigs objects
        from multiple threads.

        This is important because each thread may require
        different configurations.
    """

    def __init__(self):
        """Create an empty manager (keyed by process ID)."""
        self.configs = {}

    def __contains__(self, name):
        """Return True if a config object exists for 'name' (a PID)."""
        return name in self.configs

    def get(self):
        """Return the CoastGuardConfigs object for the current process,
            creating one if necessary.
        """
        name = os.getpid()
        if name not in self:
            self.configs[name] = CoastGuardConfigs()
        return self.configs[name]

    def load_configs_for_archive(self, arf):
        """Load observation configs for 'arf' into this process's configs."""
        self.get().load_configs_for_archive(arf)

    def __getattr__(self, key):
        """Look up configuration 'key' for the current process."""
        val = self.get()[key]
        return val


cfg = ConfigManager()


def main():
    """Command-line demo: load and print configs for an archive."""
    from coast_guard import utils
    if len(sys.argv) > 1:
        arf = utils.ArchiveFile(sys.argv[1])
        cfg.set_override_config("something", 'newvalue!')
        cfg.load_configs_for_archive(arf)
    print(cfg.get())


if __name__ == '__main__':
    main()
