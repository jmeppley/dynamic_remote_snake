"""
functions to automatically download remote files that match given patterns

This allows a workflow to be designed to accept either remote or local files
from the configuration.

There are two mechanisms:

    1) protocol prefix
    If a file path looks like a remote path (eg starts with SFTP), then the
    appropriate remote is used. Works for SFTP, SCP, FTP, HTTP

    2) custom translator
    A user can supply a set of regular_expression patterns to identify paths
    that may be available remotely and translate them into remote urls

Important NOTES:

    * The workflow has to pass a file through remote wrapper for this to work
    * SFTP wildcards are expended with the SFTP module, but rsync is used to
    download (bc it does checksums)
    * by default, SFTP uses the 'readonly' user with no passwd, this can be
    changed in the config. We strongly suggest using ssh keys and agents    i
    to avoid putting passwords in config files!

Example custom config:

remote:
    mappings:
        - pattern: "(/mnt/([^/]+)/.+)"
          host_repl: "\\2.subnet.hawaii.edu"
          path_repl: "\\1"
    SFTP:
        default:
            username: jmeppley
"""
import re
import os
from snakemake import logger
from snakemake.remote.SFTP import RemoteProvider as sftp_rp
from snakemake.io import ancient
from snakemake.workflow import glob_wildcards


__version__ = "0.0.1"


URL_REXP = re.compile(r'^([A-Za-z]+)://(([^/]+)/.+)$')
#mnt_rexp = re.compile(r'^(/mnt/([a-z]+ine)/.+)$')

# cache redentials for known hosts
providers = {}
def get_provider(protocol, host, config):
    """
    Creates a unique RemoteProvider object for each (protocol, host) pair.

    Connection options taken from:
    config['remote'][protocol][host]

    With defaults from:
    config['remote'][protocol]['defaults']

    protocol must be one of SFTP, SCP, HTTP, HTTPS, FTP, but case can be
    different. Case is used when keying options, though, so be consistent in
    your configuration
    """

    provider_key = (protocol, host)
    protocol = protocol.upper()
    if provider_key not in providers:
        remote_defaults = config.get('remote', {}) \
                                .get(protocol, {}) \
                                .get('defaults', {})
        remote_options = config.get('remote', {}) \
                                .get(protocol, {}) \
                                .get(host, {})
        apply_defaults(remote_options, remote_defaults)
        logger.debug("Creating RemoteProvider for {protocol} "
                     "using:\n{remote_options}".format(**vars()))
        if protocol in ['SFTP', 'SCP']:
            providers[provider_key] = sftp_rp(**remote_options)
        elif protocol in ['HTTP', 'HTTPS']:
            from snakemake.remote.HTTP import RemoteProvider as http_rp
            providers[provider_key] = http_rp(**remote_options)
        elif protocol == 'FTP':
            from snakemake.remote.FTP import RemoteProvider as ftp_rp
            providers[provider_key] = ftp_rp(**remote_options)
        else:
            raise Exception("Remote protocol {} not yet supported"
                            .format(provider_key[0]))
    return providers[provider_key]

def path_up_to_wildcard(full_path):
    """ If a given path has a wildcard placeholder ( eg {sample} ),
    return the last directory before that point """
    path_fragment = full_path.split('{')[0]
    if path_fragment == full_path:
        return full_path
    if path_fragment.endswith(os.path.pathsep):
        return path_fragment[:-1]
    return os.path.dirname(path_fragment)

def infer_provider(source, config, glob=False):
    """
    Checks the file path to see if we need a remote provider
    """
    try:
        # is it an explicit url
        # (EG: SFTP://lys.soest.hawaii.edu/mnt/lysine/...)
        match = URL_REXP.search(source)
        if match is not None:
            logger.debug("EXPLICIT URL")
            # replace source file with a remote object
            protocol, source_path, host = match.groups()
            return get_provider(protocol, host, config), source_path

        if os.path.exists(path_up_to_wildcard(source) \
                          if glob else source):
            return None, source

        # special case: custom patterns
        for custom_patterns in config.get('mappings', []):
            mnt_rexp = re.compile(custom_patterns['pattern'])
            host_repl = custom_patterns['host_repl']
            path_repl = custom_patterns['path_repl']

            if not mnt_rexp.search(source):
                continue

            logger.debug("INFERRED URL")
            protocol = 'SFTP'
            config.setdefault('remote', {}) \
                  .setdefault(protocol, {}) \
                  .setdefault('defaults', {'username': 'readonly',
                                          })
            source_path = mnt_rexp.sub(source, path_repl)
            host = mnt_rexp.sub(source, host_repl)
            source_path = host + source_path
            return get_provider(protocol, host, config), source_path

    except Exception as exc:
        print("Error in remote check: " + repr(exc))
        raise exc

    return None, source

def remote_wrapper(source, config, glob=False):
    """
    if file is a remote url
         ( or a missing netowrk mount )
    return remote provider object for downloading
    or return wildcard lists if glob=True (using glob_wildcards)
    """
    provider, source = infer_provider(source, config, glob=glob)
    logger.debug("provider: {}\nsource: {}".format(provider, source))

    # handle wilcard glob strings
    if glob:
        if provider is None:
            return glob_wildcards(source)
        return provider.glob_wildcards(source)

    # other wise its a normal file

    # return input if it's not remote
    if provider is None:
        return source

    # return provider.remote(source), unless using rsync
    use_rsync_for_sftp = config.get('remote', {}) \
                             .get('SFTP', {}) \
                             .get('use_rsync', True)
    host, path = source.split("/", 1)
    full_path = "/" + path
    if isinstance(provider, sftp_rp) and use_rsync_for_sftp:
        # download with rsync
        local_path = ancient("rsync/" + source)
        config.setdefault('download_map', {})[source] = \
                {'host': host, 'remote_path': full_path,
                 'user': provider.kwargs['username']}
    else:
        # use remote()
        local_path = config.get('remote_path', 'remote') + '/' + source
        remote_file = provider.remote(source)
        if isinstance(remote_file, list):
            if len(remote_file) == 1:
                remote_file = remote_file[0]
            else:
                raise Exception("multiple file remote: " +
                                str(remote_file))
        config.setdefault('download_map', {})[source] = \
                {'remote': remote_file}
    return local_path


def get_dl_snakefile():
    """ attempt to locate downloads.snake """
    if "CONDA_PREFIX" in os.environ:
        return os.environ['CONDA_PREFIX'] + "/share/drs/snake/download.snake"

    # two dirs up from here if working from repo
    return os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))) + "/download.snake"



def apply_defaults(config, defaults):
    """ recursively appy defaults to nested dicts """
    for param, pdefaults in defaults.items():
        if isinstance(pdefaults, dict):
            apply_defaults(config.setdefault(param, {}), pdefaults)
        else:
            config.setdefault(param, pdefaults)
