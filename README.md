## Dynamic Remote Snake
Provides a mechanism to dynamically set files as remote. It is usefule for workflows where files might sometimes come from remote locations and sometimes come from local disks depending on configuration

Additionally, it can replace SFTP downloads with rsync. This trades the ability to check the modification date (built into snakemake remotes) for checksum verification (built into rsync).

### Installation
Easy with conda:

```
conda install -c jmeppley
```

Latest code with python

```
git clone https://github.com/jmeppley/dynamic_remote_snake
cd dynamic_remote_snake
python setup.py install
```

### Using
First, include download.snake in your Snakefile with an includes: statement.

Then, pass any file names or wildcard_globs that may sometimes be remote through the remote_wrapper() function.

For file:

```
new_path = remote_wrapper(path, config)
```

For globs:
```
wildcards = remote_wrapper(glob_string, config, glob=True)
```

