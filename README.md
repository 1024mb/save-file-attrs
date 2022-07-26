Based on work by [Robert Knight][1]

## This script collects all the attributes from files and folders and stores them in a json-formatted file.

###                 There are two modes:
- save
- restore


## Save: 

```
usage: save-file-attrs.py save [-h] [--o [%OUTPUT%]] [--p [%PATH%]] [--r] [--ex [EX ...]] [--ef [EF ...]]
                               [--ed [ED ...]]

options:
  -h, --help            show this help message and exit
  --o [%OUTPUT%], -o [%OUTPUT%]
                        Set output file (Optional, default is .saved-file-attrs)
  --p [%PATH%], -p [%PATH%]
                        Set path to store attributes from (Optional, default is current path)
  --r, -r               Store paths as relative instead of full (Optional)
  --ex [EX ...], -ex [EX ...]
                        Match these strings indiscriminately and exclude them, program will exclude anything that
                        includes these strings in their paths unless a full path is specified in which case it will be
                        considered adirectory and everything inside will be excluded (Optional)
  --ef [EF ...], -ef [EF ...]
                        Match all the paths that incorporates these strings and exclude them, strings are considered
                        filenames unless a full path is given in which case only that file will be excluded (Optional)
  --ed [ED ...], -ed [ED ...]
                        Match all the paths that incorporates these strings and exclude them, strings are considered
                        directories unless a full path is given in which case it will exclude all the subdirs and
                        files inside that directory (Optional)
```

## Restore:

```
usage: save-file-attrs.py restore [-h] [--i [%INPUT%]]

options:
  -h, --help            show this help message and exit
  --i [%INPUT%], -i [%INPUT%]
                        Set input file (Optional, default is .saved-file-attrs)
```

Exclusions need more testing, it currently works like this:

- `ex`: Matches the given strings not caring whether they are files or directories and excludes them, the program will exclude anything that includes these strings in their paths, like using regex `.*STRING.*` unless a full path is specified in which case it will always be considered a directory and everything inside will be excluded.
- `ed`: Matches all the paths -that are directories- that incorporate these strings and excludes them, it will match all the directories that have this like in `ex` (`.*STRING.*`) unless a full path is given in which case it will only exclude all the subdirs and files inside that directory, and said dir.
- `ef`: Matches all the paths that incorporates these strings and exclude them, strings are considered filenames and it works like `ex` (`.*STRING.*`) unless a full path is given in which case only that file will be excluded.


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
