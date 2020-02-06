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
    * by default, SFTP uses the current user with no passwd, this can be
    changed in the config. We strongly suggest using ssh keys and agents
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
__version__ = "0.1.0"
