Based on work by [Robert Knight][1]

## This script collects all the attributes from files and folders and stores them in a json-formatted file.

***

### Minimum python version is 3.12

***

Dependencies
-------------------------

- [PathSpec](https://github.com/cpburnz/python-pathspec)
- [Pydantic](https://github.com/pydantic/pydantic)
- [orjson](https://github.com/ijl/orjson)
- [loguru](https://github.com/Delgan/loguru)

There are two modes:
-------------------------

- save
- restore

Save:
-------------------------

```shell
usage: save-file-attrs.py save [-h] [-o [%OUTPUT%]] [-wp [%PATH%]]
                               [-ex [%PATTERN_RULE% ...]]
                               [-if [%IGNORE-FILE% ...]] [-eic] [-r] [-sl]
                               [--no-print-excluded] [--no-print-skipped]

Save file and directory attributes in a directory tree

Exit code:
    0: Success
    1: User interrupted
    2: Generic error
    3: File related error
    10: Attribute file related error

options:
  -h, --help            show this help message and exit
  -o [%OUTPUT%], --output [%OUTPUT%]
                        Set the output file. (Default is ".saved-file-attrs"
                        in the current directory)
  -wp [%PATH%], --working-path [%PATH%]
                        Set the path to store attributes from. (Default is the
                        current path)
  -ex [%PATTERN_RULE% ...], --exclude [%PATTERN_RULE% ...]
                        Pattern rules to exclude, same format as git ignore
                        rules.
  -if [%IGNORE-FILE% ...], --ignore-file [%IGNORE-FILE% ...]
                        File(s) containing pattern rules, same format as git
                        ignore rules.
  -eic, --exclusions-ignore-case
                        Ignore casing for exclusions.
  -r, --relative        Store the paths as relative instead of full paths.
  -sl, --skip-links     Skip symbolic links and junctions.
  --no-print-excluded   Don't print excluded files and folders.
  --no-print-skipped    Don't print skipped files and folders.
```

Restore:
-------------------------

```shell
usage: save-file-attrs.py restore [-h] [-i [%INPUT%]] [-wp [%PATH%]]
                                  [--no-print-modified] [--no-print-skipped]
                                  [--no-print-excluded] [-cta] [-sp] [-so]
                                  [-ex [%PATTERN_RULE% ...]]
                                  [-if [%IGNORE-FILE%]] [-eic] [-sa] [-sh]
                                  [-sr] [-ss] [-sc] [-sm] [-sac] [-sl]

Restore file and directory attributes in a directory tree

Exit code:
    0: Success
    1: User interrupted
    2: Generic error
    3: File related error
    10: Attribute file related error

options:
  -h, --help            show this help message and exit
  -i [%INPUT%], --input [%INPUT%]
                        Set the input file containing the attributes to
                        restore. (Default is ".saved-file-attrs" in the
                        current directory)
  -wp [%PATH%], --working-path [%PATH%]
                        Set the working path. The attributes will be applied
                        to the contents of this path if they are relative,
                        ignored otherwise. (Default is the current directory)
  --no-print-modified   Don't print modified files and folders.
  --no-print-skipped    Don't print skipped files and folders.
  --no-print-excluded   Don't print excluded files and folders.
  -cta, --copy-to-access
                        Copy the creation dates to the accessed date.
  -sp, --skip-permissions
                        Skip setting permissions.
  -so, --skip-owner     Skip setting ownership.
  -ex [%PATTERN_RULE% ...], --exclude [%PATTERN_RULE% ...]
                        Pattern rules to exclude, same format as git ignore
                        rules.
  -if [%IGNORE-FILE%], --ignore-file [%IGNORE-FILE%]
                        File(s) containing pattern rules, same format as git
                        ignore rules.
  -eic, --exclusions-ignore-case
                        Ignore casing for exclusions.
  -sa, --skip-archive   Skip setting the "archive" attribute.
  -sh, --skip-hidden    Skip setting the "hidden" attribute.
  -sr, --skip-readonly  Skip setting the "read-only" attribute.
  -ss, --skip-system    Skip setting the "system" attribute.
  -sc, --skip-creation  Skip setting the "creation" timestamp.
  -sm, --skip-modified  Skip setting the "modified" timestamp.
  -sac, --skip-accessed
                        Skip setting the "accessed" timestamp.
  -sl, --skip-links     Skip symbolic links and junctions.
```

Exclusions:
-------------------------
Exclusion support gitignore syntax for pattern rules, it should behave exactly as git.
Individual patterns can be specified with `--exclude` and/or one or more ignore files can be supplied with
`--ignore-file`.  
By default exclusions are case-sensitive, using `--exclusions-ignore-case` will ignore the casing.

Excluding file/directories should prevent them from being read/listed.

Limitations:
-------------------------
Currently, Python doesn't support skipping symbolic links for certain operations on some operating
systems, because of this symbolic links are skipped when restoring attributes on these operating
systems.
While Windows is one of them, we use a custom module to set the timestamps in this OS so this doesn't apply to Windows.

[1]: https://github.com/robertknight/mandrawer
