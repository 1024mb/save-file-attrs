Based on work by [Robert Knight][1]

## This script collects all the attributes from files and folders and stores them in a json-formatted file.

Dependencies
-------------------------

- [win32-setctime](https://github.com/Delgan/win32-setctime) (if on Windows)
- [PathSpec](https://github.com/cpburnz/python-pathspec)

There are two modes:
-------------------------

- save
- restore

Save:
-------------------------

```bash
usage: save-file-attrs.py save [-h] [-o [%OUTPUT%]] [-p [%PATH%]] [-ex [%PATTERN_RULE% ...]] [-ef [%IGNORE-FILE%]] [-eic] [-r] [-np]

options:
  -h, --help            show this help message and exit
  -o [%OUTPUT%], --output [%OUTPUT%]
                        Set the output file (Optional, default is ".saved-file-attrs" in current dir)
  -p [%PATH%], --working-path [%PATH%]
                        Set the path to store attributes from (Optional, default is current path)
  -ex [%PATTERN_RULE% ...], --exclude [%PATTERN_RULE% ...]
                        Pattern rules to exclude, same format as git ignore rules. (Optional)
  -ef [%IGNORE-FILE%], --ignore-file [%IGNORE-FILE%]
                        Ignore file containing pattern rules, same format as git ignore rules. (Optional)
  -eic, --exclusions-ignore-case
                        Ignore casing for exclusions.
  -r, --relative        Store the paths as relative instead of full (Optional)
  -np, --no-print       Don't print excluded files and folders (Optional)
```

Restore:
-------------------------

```bash
usage: save-file-attrs.py restore [-h] [-i [%INPUT%]] [-wp [%PATH%]] [-np] [-cta] [-ifs] [-ip] [-ex [%PATTERN_RULE% ...]] [-ef [%IGNORE-FILE%]] [-eic] [-sa] [-sh] [-sr] [-ss]

options:
  -h, --help            show this help message and exit
  -i [%INPUT%], --input [%INPUT%]
                        Set the input file containing the attributes to restore (Optional, default is ".saved-file-attrs" in current dir)
  -wp [%PATH%], --working-path [%PATH%]
                        Set the working path, the attributes will be applied to the contents of this path (Optional, default is the current directory)
  -np, --no-print       Don't print modified or skipped files and folders (Optional)
  -cta, --copy-to-access
                        Copy the creation dates to accessed dates (Optional)
  -ifs, --ignore-filesystem
                        Ignore filesystem and don't modify creation dates (Optional)
  -ip, --ignore-permissions
                        Ignore permissions change (Optional)
  -ex [%PATTERN_RULE% ...], --exclude [%PATTERN_RULE% ...]
                        Pattern rules to exclude, same format as git ignore rules. (Optional)
  -ef [%IGNORE-FILE%], --ignore-file [%IGNORE-FILE%]
                        Ignore file containing pattern rules, same format as git ignore rules. (Optional)
  -eic, --exclusions-ignore-case
                        Ignore casing for exclusions.
  -sa, --skip-archive   Skip setting the "archive" attribute.
  -sh, --skip-hidden    Skip setting the "hidden" attribute.
  -sr, --skip-readonly  Skip setting the "read-only" attribute.
  -ss, --skip-system    Skip setting the "system" attribute.
```

Exclusions:
-------------------------
Exclusion support now gitignore syntax for pattern rules. Individual patterns can be specified with `--exclude` or a
ignore file can be supplied with `--ignore-file`.  
By default exclusions are case-sensitive, using `--exclusions-ignore-case` will ignore the casing.

Note that excluding files and/or directories wont prevent the script from listing such items, they will be listed
but their attributes wont be retrieved.

Limitations:
-------------------------
Currently Python 3.12 doesn't support skipping symbolic links for certain operations on Windows (there may be other
operating systems), because of this symbolic links are skipped when restoring attributes.

[1]: https://github.com/robertknight/mandrawer
