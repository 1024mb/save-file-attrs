Based on work by [Robert Knight][1]

## This script collects all the attributes from files and folders and stores them in a json-formatted file.

###                 There are two modes:
- save
- restore


## Save: 

```
usage: save-file-attrs.py save [-h] [--o [%OUTPUT%]] [--p [%PATH%]] [--r] [--ex [%NAME% ...]] [--ef [%FILE% ...]] [--ed [%DIRECTORY% ...]]

options:
  -h, --help            show this help message and exit
  --o [%OUTPUT%], -o [%OUTPUT%]
                        Set the output file (Optional, default is ".saved-file-attrs" in current dir)
  --p [%PATH%], -p [%PATH%]
                        Set the path to store attributes from (Optional, default is current path)
  --r, -r               Store the paths as relative instead of full (Optional)
  --ex [%NAME% ...], -ex [%NAME% ...]
                        Match these strings indiscriminately and exclude them, program will exclude anything that
                        includes these strings in their paths unless a full path is specified in which case it will be
                        considered a directory and everything inside will be excluded. (Optional)
  --ef [%FILE% ...], -ef [%FILE% ...]
                        Match all the paths that incorporates these strings and exclude them, strings are considered
                        filenames unless a full path is given in which case only that file will be excluded. If the
                        argument is given without any value, all the files will be excluded. (Optional)
  --ed [%DIRECTORY% ...], -ed [%DIRECTORY% ...]
                        Match all the paths that incorporates these strings and exclude them, strings are considered
                        directories unless a full path is given in which case it will exclude all the subdirs and
                        files inside that directory. (Optional)
```

## Restore:

```
usage: save-file-attrs.py restore [-h] [--i [%INPUT%]] [--wp [%PATH%]]

options:
  -h, --help            show this help message and exit
  --i [%INPUT%], -i [%INPUT%]
                        Set the input file containing the attributes to restore (Optional, default is ".saved-file-
                        attrs" in current dir)
  --wp [%PATH%], -wp [%PATH%]
                        Set the working path, the attributes will be applied to the contents of this path (Optional,
                        default is the current directory)
```

Exclusions need more testing, it currently works like this:

- `ex`: Matches the given strings not caring whether they are files or directories and excludes them, the program will exclude anything that includes these strings in their paths, like using regex `.*STRING.*` unless a full path is specified in which case it will always be considered a directory and everything inside will be excluded.
- `ed`: Matches all the paths -that are directories- that incorporate these strings and excludes them, it will match all the directories that have this like in `ex` (`.*STRING.*`) unless a full path is given in which case it will only exclude all the subdirs and files inside that directory, and said dir.  
From 0.4.1+ if the argument is given with a string starting with `.\` it will consider the folder to be located at the root directory and will match every folder that starts with the given string, if starts with `\` it will match all the directories that starts with the given string not necessarily in the root directory.
- `ef`: Matches all the paths that incorporates these strings and exclude them, strings are considered filenames and it works like `ex` (`.*STRING.*`) unless a full path is given in which case only that file will be excluded. If `ef` is supplied without any value it will exclude all the files.


If we have this:

```
dir A\
      dir B\
            this                  <- file
            that                  <- file
            also.this.txt         <- file
      dir C\
            this.foo\
                     file.json    <- file
```

And use:

`-ex "this"` -> the script will exclude:
```
dir A\dir B\this
dir A\dir B\also.this.txt
dir A\dir C\this.foo              <- directory
dir A\dir C\this.foo\file.json    <- file; because it's inside the "this" directory
```

`-ed "this"` -> the script will exclude:
```
dir C\this.foo                    <- directory
dir C\this.foo\file.json          <- file
```

`-ef "this"` -> the script will exclude:

```
dir A\dir B\this                  <- file
dir A\dir B\also.this.txt         <- file
```
   
   
##
## :warning: EXCLUSIONS ARE CASE INSENSITIVE IF THE PLATFORM IS WINDOWS!!! :warning:  
Windows is not a case-sensitive OS so this most probably is intended, leaving this warning anyway.



  [1]: https://github.com/robertknight/mandrawer
