Based on work by [Robert Knight][1]

## This script collects all the attributes from files and folders and stores them in a json-formatted file.

***

### Minimum python version is 3.12

***

Dependencies
-------------------------

- [win32-setctime](https://github.com/Delgan/win32-setctime) (if on Windows)
- [PathSpec](https://github.com/cpburnz/python-pathspec)
- [Pydantic](https://github.com/pydantic/pydantic)
- [orjson](https://github.com/ijl/orjson)

There are two modes:
-------------------------

- save
- restore

Save:
-------------------------

```shell
usage: save-file-attrs.py save [-h] [-o [%OUTPUT%]] [-wp [%PATH%]]
                               [-ex [%PATTERN_RULE% ...]]
                               [-if [%IGNORE-FILE% ...]] [-eic] [-r]
                               [--no-print-excluded]

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
                        Set the output file (Optional, default is ".saved-
                        file-attrs" in current dir)
  -wp [%PATH%], --working-path [%PATH%]
                        Set the path to store attributes from (Optional,
                        default is current path)
  -ex [%PATTERN_RULE% ...], --exclude [%PATTERN_RULE% ...]
                        Pattern rules to exclude, same format as git ignore
                        rules.
  -if [%IGNORE-FILE% ...], --ignore-file [%IGNORE-FILE% ...]
                        Ignore file containing pattern rules, same format as
                        git ignore rules.
  -eic, --exclusions-ignore-case
                        Ignore casing for exclusions.
  -r, --relative        Store the paths as relative instead of full
  --no-print-excluded   Don't print excluded files and folders
```

Restore:
-------------------------

```shell
usage: save-file-attrs.py restore [-h] [-i [%INPUT%]] [-wp [%PATH%]]
                                  [--no-print-modified] [--no-print-skipped]
                                  [--no-print-excluded] [-cta] [-sp] [-so]
                                  [-ex [%PATTERN_RULE% ...]]
                                  [-if [%IGNORE-FILE%]] [-eic] [-sa] [-sh]
                                  [-sr] [-ss] [-sc] [-sm] [-sac]

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
                        restore (Optional, default is ".saved-file-attrs" in
                        current dir)
  -wp [%PATH%], --working-path [%PATH%]
                        Set the working path, the attributes will be applied
                        to the contents of this path (Default is the current
                        directory)
  --no-print-modified   Don't print modified files and folders
  --no-print-skipped    Don't print skipped files and folders
  --no-print-excluded   Don't print excluded files and folders
  -cta, --copy-to-access
                        Copy the creation dates to accessed dates
  -sp, --skip-permissions
                        Skip setting permissions
  -so, --skip-owner     Skip setting ownership
  -ex [%PATTERN_RULE% ...], --exclude [%PATTERN_RULE% ...]
                        Pattern rules to exclude, same format as git ignore
                        rules.
  -if [%IGNORE-FILE%], --ignore-file [%IGNORE-FILE%]
                        Ignore file containing pattern rules, same format as
                        git ignore rules. (Optional)
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
```

Exclusions:
-------------------------
Exclusion support now gitignore syntax for pattern rules, it should behave exactly as git.
Individual patterns can be specified with `--exclude` or one or more ignore files can be supplied with
`--ignore-file`.  
By default exclusions are case-sensitive, using `--exclusions-ignore-case` will ignore the casing.

Excluding file/directories should prevent them from being read/listed.

Limitations:
-------------------------
Currently, Python 3.13 and below doesn't support skipping symbolic links for certain operations on Windows (there may be
other operating systems), because of this symbolic links are skipped when restoring attributes on these operating
systems.

[1]: https://github.com/robertknight/mandrawer
