import os, re, grp, pwd
from collections import namedtuple
from configparser import ConfigParser
from prints import errmsg, debugmsg, infomsg

def enum(enum):
    return enum.replace(" ", "").split(",")

def parse_loglevel(log_level):
    allowed = [10, 20, 40]
    log_level = enum(log_level)[0]
    try:
        if int(log_level) in allowed: return int(log_level)
        else: errmsg("Invalid log level in config"); exit()
    except ValueError:
        errmsg("Invalid log level in config"); exit()

def parse_dig(dig, imin, imax):
    ''' Parse a digit '''

    dig = enum(dig)[0]
    try:
        if imin <= int(dig) <= imax: return int(dig)
        else: errmsg("Invalid digit in config"); exit()
    except ValueError:
        errmsg("Invalid digit in config"); exit()

def parse_hostadmin(username):
    ''' Parse the host admin username from config '''
    try:
        gid = pwd.getpwnam(username).pw_gid
        uid = pwd.getpwnam(username).pw_uid
    except KeyError:
        errmsg("Configured host admin does not exist", "Parsing", (username,)); exit()
    return (uid, gid)

def parse_language(language):
    allowed = ["DE", "EN"]
    language = enum(language)[0]
    try:
        if language in allowed: return language
        else: errmsg("Invalid language in config"); exit()
    except ValueError:
        errmsg("Invalid language in config"); exit()

def parse_strlist(strlist, paths=False):
    ''' Parse a stringlist which may be a list of paths '''
    try:
        strlist = list(filter(None, strlist.split(',')))
        strlist = [s.strip() for s in strlist]
    except ValueError:
        errmsg("Invalid string list in config"); exit()
    if not strlist:
        errmsg("Invalid string list in config"); exit()
    if paths:
        paths = [p.rstrip(os.sep).lstrip() for p in strlist]
        non_paths = [p for p in paths if not os.path.isdir(p)]
        paths = [p for p in paths if os.path.isdir(p)]
        if not paths:
            infomsg("Config contains list of non-existent file paths", "Parsing", (paths,))
        if non_paths:
            infomsg("Config contains path which does not exist", "Parsing", (non_paths,))
        return paths
    return strlist

def parse_docker_mappings():
    ''' Get all mounts of a docker container '''
    ## Get all mounts of the docker container
    import subprocess
    ps = subprocess.Popen(('mount'), stdout=subprocess.PIPE)
    output = subprocess.check_output(('grep', '^/dev/'), stdin=ps.stdout)
    ps.wait()

    ## Parse the output of the mount command
    mounts = [l for l in output.decode().split("\n") if len(l) > 0]
    mounts = [m for m in mounts if "/etc/" not in m.split(" ")[2] and m.split(" ")[2] != "/"]
    mounts = [m for m in mounts if "@docker" not in m]
    mounts = [(m.split()[2], m.split(",")[-1][:-1]) for m in mounts]
    mounts = [(m[0], m[1].split("=")[-1]) for m in mounts]
    mounts = [(m[0], m[1].replace("@syno", "volume1")) for m in mounts]
    return mounts

def parse_cfg_transmission(cfg, scope):

    mapping, host_admin, host_watch_dir = (None for _ in range(3))

    ## Parse the config in case the script is running within a docker container
    if (scope == "docker"):
        mapping = parse_docker_mappings()
        handbrake = [m[0] for m in mapping if "handbrake" in m[0]]
        if (len(handbrake) > 0):
            handbrake = handbrake[0]
        else:
            errmsg("Define the handbrake mount in the container settings"); exit()

    ## [Hostsystem] Parse the config in case the script is running in host system
    else:
        handbrake = parse_strlist(cfg.get("Host", "host_handbrake"), True)[0]
        host_watch_dir = parse_strlist(cfg.get("Host", "host_watch_dir"), True)
        host_admin = parse_hostadmin(cfg.get("Host", "host_admin"))

    codecs = enum(cfg.get("Transmission", "codecs"))
    extensions = enum(cfg.get("Transmission", "extensions"))
    port = parse_dig(cfg.get("SynoIndex", "synoindex_port"), 1, 65535)
    handbrake_exclude = parse_strlist(cfg.get("Handbrake", "handbrake_exclude"))
    handbrake_4k = parse_dig(cfg.get("Handbrake", "handbrake_4k"), 1, 2)
    log_level = parse_loglevel(cfg.get("Logging", "log_level"))
    log_dir = parse_strlist(cfg.get("Logging", "log_dir"))[0]

    return (mapping, codecs, extensions, port,
            handbrake, host_watch_dir, host_admin,
            handbrake_exclude, handbrake_4k,
            log_level, log_dir)

def parse_cfg_handbrake(cfg, scope):

    mapping = None

    ## Parse the config in case the script is running within a docker container
    if (scope == "docker"):
        mapping = parse_docker_mappings()

    ## Get the different episode and movie paths
    handbrake_movies = enum(cfg.get("Handbrake", "handbrake_movies"))
    handbrake_series = enum(cfg.get("Handbrake", "handbrake_series"))
    handbrake_original = parse_dig(cfg.get("Handbrake", "handbrake_original"), 0, 3)
    handbrake_language = parse_language(cfg.get("Handbrake", "handbrake_language"))
    port = parse_dig(cfg.get("SynoIndex", "synoindex_port"), 1, 65535)
    log_level = parse_loglevel(cfg.get("Logging", "log_level"))
    log_dir = parse_strlist(cfg.get("Logging", "log_dir"))[0]
    return (mapping, handbrake_movies, handbrake_series, handbrake_original,
            handbrake_language, port, log_level, log_dir)

def parse_cfg(config_file, config_type, scope):
    ''' Parse all configuration options of the config file. '''

    ## Read the config file
    config = ConfigParser()
    config.read(config_file)

    ## VS-Handbrake
    if (config_type == "vs-handbrake"):
        sections = ["Handbrake", "SynoIndex", "Logging"]
        fields = ["mapping", "movies", "series", "original", "language",
                  "port", "log_level", "log_dir"]

    ## VS-Transmission
    elif (config_type == "vs-transmission"):
        sections = ["Transmission", "SynoIndex", "Handbrake", "Host", "Logging"]
        fields =   ["mapping", "codecs", "extensions", "port",
                    "handbrake", "watch_directories", "host_admin",
                    "exclude", "hb_4k", "log_level", "log_dir"]
    else:
        errmsg("Config type not supported"); exit()

    ## Check whether all sections are present and initialize config Namespace
    _ = [exit('Error: Section (%s) missing' % s) for s in sections if not config.has_section(s)]
    cfg = namedtuple('cfg', " ".join(fields))
    cfg.__new__.__defaults__ = (None,) * len(cfg._fields)

    ## VS-Handbrake
    if (config_type == "vs-handbrake"):
        (mpg, movies, series, original, lang, port, level, log) = parse_cfg_handbrake(config, scope)
        parsed_cfg = cfg(mpg, movies, series, original, lang, port, level, log)

    ## VS-Transmission
    elif (config_type == "vs-transmission"):
        (mpg, cds, exts, port, hb, dirs, had, excls, h4k, lvl, log) = parse_cfg_transmission(config, scope)
        parsed_cfg = cfg(mpg, cds, exts, port, hb, dirs, had, excls, h4k, lvl, log)

    return parsed_cfg