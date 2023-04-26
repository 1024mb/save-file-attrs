Based on work by [Robert Knight][1]

## This script collects all the attributes from files and folders and stores them in a json-formatted file.

Dependencies
-------------------------
- [win32-setctime](https://github.com/Delgan/win32-setctime)

There are two modes:
-------------------------
- save
- restore


Save: 
-------------------------
```
usage: save-file-attrs.py save [-h] [-o [%OUTPUT%]] [-p [%PATH%]] [-ex [%NAME% ...]] [-ef [%FILE% ...]] [-ed [%DIRECTORY% ...]] [-r] [-np]

options:
  -h, --help            show this help message and exit
  -o [%OUTPUT%], --o [%OUTPUT%]
                        Set the output file (Optional, default is ".saved-file-attrs" in current dir)
  -p [%PATH%], --p [%PATH%]
                        Set the path to store attributes from (Optional, default is current path)
  -ex [%NAME% ...], --ex [%NAME% ...]
                        Match these strings indiscriminately and exclude them, program will exclude anything that includes these strings in their paths unless a full path is specified in which case it will be considered a directory and
                        everything inside will be excluded. (Optional)
  -ef [%FILE% ...], --ef [%FILE% ...]
                        Match all the paths that incorporates these strings and exclude them, strings are considered filenames unless a full path is given in which case only that file will be excluded. If the argument is given without
                        any value, all the files will be excluded. (Optional)
  -ed [%DIRECTORY% ...], --ed [%DIRECTORY% ...]
                        Match all the paths that incorporates these strings and exclude them, strings are considered directories unless a full path is given in which case it will exclude all the sub directories and files inside that
                        directory. (Optional)
  -r, --r               Store the paths as relative instead of full (Optional)
  -np, --np             Don't print excluded files and folders (Optional)
```

Restore:
-------------------------
```
usage: save-file-attrs.py restore [-h] [-i [%INPUT%]] [-wp [%PATH%]] [-np] [-cta] [-ifs]

options:
  -h, --help            show this help message and exit
  -i [%INPUT%], --i [%INPUT%]
                        Set the input file containing the attributes to restore (Optional, default is ".saved-file-attrs" in current dir)
  -wp [%PATH%], --wp [%PATH%]
                        Set the working path, the attributes will be applied to the contents of this path (Optional, default is the current directory)
  -np, --np             Don't print modified or skipped files and folders (Optional)
  -cta, --cta           Copy the creation dates to accessed dates (Optional)
  -ifs, --ifs           Ignore filesystem and don't modify creation dates, useful when working with non-NTFS network shares in Windows (Optional)
```

Exclusions:
-------------------------
Exclusion need more testing, specially on systems other than Windows, it currently works like this:

- `ex`: Matches the given strings indiscriminately -whether they are files or directories-, all paths including these strings will be excluded, like using regex `.*STRING.*`. If a full path is specified not only that file/folder will be excluded, every path that starts with the given string will be excluded, pretty much exactly like using `.\`. Read (1) below.  
Using `\` at the start of the string will match everything that starts with the string, using `.\` at the start will make it match only in the root directory.  

- `ed`: Matches all the paths -that are directories- that incorporate these strings, it will match all the directories that include these strings like using regex `.*STRING.*` unless a full path is given in which case it will only exclude said directory and all its subdirectories and files.  
Using `\` at the start of the string will match all the directories that start with the given string, using `.\` at the start will only match if the directory is located in the root.  

- `ef`: Matches all the paths -that are files- that incorporate these strings, strings are considered filenames and it works like using regex `.*STRING.*` unless a full path is given in which case only that file will be excluded. If `ef` is supplied without any value (either using only `--ef` or `--ef ""`) it will exclude all the files.  
Using `\` at the start of the string will match everything that starts with the string, using `.\` at the start will make it match only in the root dir.

<sup>(1)</sup> An example of `ex` is needed because it really is hungry.  
If you have a directory path `C:\tmp` that contains among other files these: `a`, `abc` and `a_1_2.json` and you use `-ex C:\tmp\a` all the previously mentioned files will be excluded, it will not only exclude the file `a`, if you want to do that you have to use the other types which do support specifying full paths.



Example:
-------------------------

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

And use (notice how the paths only need to contain the string):

`-ex "this"` -> the script will exclude:
```
dir A\dir B\this
dir A\dir B\also.this.txt
dir A\dir C\this.foo              <- directory
dir A\dir C\this.foo\file.json    <- file; because it's inside the "this.foo" directory
```

`-ed "this"` -> the script will exclude:
```
dir C\this.foo                    <- directory
dir C\this.foo\file.json          <- file; because it's inside the "this.foo" directory
```

`-ef "this"` -> the script will exclude:

```
dir A\dir B\this                  <- file
dir A\dir B\also.this.txt         <- file
```

`-ed ".\this"` -> the script will exclude:
```
dir C\this.foo                    <- directory
dir C\this.foo\file.json          <- file; because it's inside the "this.foo" directory
```
If you wanted to only exclude directories that are named only "this" you have to specify the full path, i.e.: `-ed "C:\dir C\this"`

`-ef ".\this"` -> the script will exclude:

```
**IT WILL EXCLUDE NOTHING BECAUSE THERE IS NO FILE IN THE ROOT**
```
   

:warning: EXCLUSIONS ARE CASE INSENSITIVE IF THE PLATFORM IS WINDOWS :warning:
-------------------------
Windows is not a case-sensitive OS so this most probably is intended, leaving this warning anyway.

Also note that excluding files and/or directories wont prevent the script from listing such items, they will be listed but their attributes wont be retrieved.

  [1]: https://github.com/robertknight/mandrawer
