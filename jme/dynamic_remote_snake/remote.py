import re
import os
from snakemake import logger
from snakemake.remote.SFTP import RemoteProvider as sftp_rp
from snakemake.io import ancient
from snakemake.workflow import glob_wildcards
from jme.stagecache.util import parse_url
from jme.stagecache.main import cache_target
from jme.stagecache.cache import InsufficientSpaceError


__version__ = "0.0.5"


#URL_REXP = re.compile(r'^([A-Za-z]+)://(([^/]+)/.+)$')
#mnt_rexp = re.compile(r'^(/mnt/([a-z]+ine)/.+)$')

# cache redentials for known hosts
providers = {}
def get_provider(resource, config):
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

    protocol = resource.protocol
    host = resource.host
    user = resource.user
    provider_key = (protocol, host)
    protocol = protocol.upper()
    if provider_key not in providers:
        remote_defaults = config.get('remote', {}) \
                                .get(protocol, {}) \
                                .get('default', {})
        remote_options = config.get('remote', {}) \
                                .get(protocol, {}) \
                                .get(host, {})
        apply_defaults(remote_options, remote_defaults)
        if user is not None:
            remote_options['username'] = user
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
        elif protocol == 'file':
            return None
        else:
            raise Exception("Remote protocol {} not yet supported"
                            .format(provider_key[0]))
    return providers[provider_key]

def infer_provider(source, config, glob=False):
    """
    Checks the file path to see if we need a remote provider
    """
    try:
        # is it an explicit url
        # (EG: SFTP://lys.soest.hawaii.edu/mnt/lysine/...)
        resource = parse_url(source, config, use_local=True, has_wildcards=glob)
        if resource is not None:
            logger.debug("EXPLICIT URL")
            # replace source file with a remote object
            return (get_provider(resource, config),
                    resource.host + resource.path)


    except Exception as exc:
        print("Error in remote check: " + repr(exc))
        raise exc

    return None, source

def get_cache_path(remote_path, config):
    cache_data = config.get('remote', {}).get('cache', {})
    if 'path' not in cache_data:
        return None

    cache_path = cache_data['path']
    for exclude_pattern in cache_data.get('exclude', []):
        if re.search(exclude_pattern, remote_path):
            return None
    return cache_path

def remote_wrapper(raw_source, config, glob=False, **kwargs):
    """
    if file is a remote url
         ( or a missing netowrk mount )
    return remote provider object for downloading
    or return wildcard lists if glob=True (using glob_wildcards)
    """
    provider, source = infer_provider(raw_source, config, glob=glob)
    logger.debug("provider: {}\nsource: {}".format(provider, source))

    # handle wilcard glob strings
    if glob:
        if provider is None:
            return glob_wildcards(source)
        return provider.glob_wildcards(source)

    # otherwise it's a normal file

    # return input if it's not remote
    if provider is None:
        return source

    # return provider.remote(source), unless using rsync or cache
    use_rsync_for_sftp = config.get('remote', {}) \
                             .get('SFTP', {}) \
                             .get('use_rsync', True)
    cache_path = get_cache_path(source, config)
    host, path = source.split("/", 1)
    full_path = "/" + path
    if isinstance(provider, sftp_rp):
        if cache_path is not None:
            cache_time = config['remote']['cache'].get('time', None)
            try:
                local_path = cache_target(raw_source, cache_path,
                                          time=cache_time,
                                          dry_run=True)
            except InsufficientSpaceError as ise:
                # fall back to local rsync if the cache is full
                pass
            else:
                config.setdefault('download_map', {})[source] = \
                        {'url': raw_source}
                if 'atype' in kwargs:
                    config['download_map'][source]['atype'] = kwargs['atype']
                return local_path

        if use_rsync_for_sftp:
                # download with rsync
                config.setdefault('download_map', {})[source] = \
                        {'host': host, 'remote_path': full_path,
                         'user': provider.kwargs['username']}
                return ancient("rsync/" + source)

        # if neither, just use remote

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
    """ located in package dir """
    return os.path.dirname(os.path.abspath(__file__)) + "/download.snake"

    # old way (only worked for conda
    """
    if "CONDA_PREFIX" in os.environ:
        return os.environ['CONDA_PREFIX'] + "/share/dynamic_remote_snake/snake/download.snake"

    # two dirs up from here if working from repo
    return os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))) + "/download.snake"
    """

def apply_defaults(config, defaults):
    """ recursively appy defaults to nested dicts """
    for param, pdefaults in defaults.items():
        if isinstance(pdefaults, dict):
            apply_defaults(config.setdefault(param, {}), pdefaults)
        else:
            config.setdefault(param, pdefaults)

