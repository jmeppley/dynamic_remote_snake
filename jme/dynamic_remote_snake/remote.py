import re
import os
import logging
from snakemake import logger
from snakemake.remote.SFTP import RemoteProvider as sftp_rp
from snakemake.io import ancient
from snakemake.workflow import glob_wildcards
from jme.stagecache.util import parse_url
from jme.stagecache.main import cache_target
from jme.stagecache.cache import InsufficientSpaceError
from jme.stagecache.config import get_config, apply_defaults


__version__ = "0.0.5"

# propogate snakemake log level to code using logging module
logging.basicConfig(level=logger.logger.level)

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

def check_cache_config(config):
    " if a cache is configured, pull in default settings "

    if 'cache' in config.get('remote',{}) and "__cache_config" not in config:
        # fill in remote settings from stagecache, but don't overwrite
        # snakemake config

        try:
            # cache location should be in config:remote:cache:path 
            cache_path = config['remote']['cache']['path']
            if not isinstance(cache_path, str):
                raise Exception
        except:
            #  but we'll support two other cases:
            if isinstance(config['remote']['cache'],str):
                #    config:remote:cache is a string
                #      - assume string is path to cache
                cache_path = config['remote']['cache']
            else:
                #    config:remote:cache is anything else
                #      - use default cache location as configured by stagecache
                cache_path = None
                logger.warning("Can't make sense of config:remote:cache!! "
                               "config:remote:cache:path should be a string. "
                               "Using stagecache defaults instead.")
            #  in both cases, config:remote:cache gets overwritten
            del config['remote']['cache']

        logger.debug("cache path: cache_path")

        # get config for cache and merge with snakemake config
        apply_defaults(config['remote'], get_config(cache_path)['remote']) 

        # it only has to be done once per instance
        config['__cache_config'] = True


def remote_wrapper(raw_source, config, glob=False, **kwargs):
    """
    if file is a remote url
         ( or a missing netowrk mount )
    return remote provider object for downloading
    or return wildcard lists if glob=True (using glob_wildcards)
    """

    check_cache_config(config)

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
                                          atype=kwargs.get('atype', 'file'),
                                          dry_run=True)
            except InsufficientSpaceError as ise:
                # fall back to local rsync if the cache is full
                pass
            else:
                config.setdefault('download_map', {})[path] = \
                        {'url': raw_source}
                if 'atype' in kwargs:
                    config['download_map'][path]['atype'] = kwargs['atype']
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

