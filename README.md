Based on work by [Robert Knight][1]

## This script collects all the attributes from files and folders and stores them in a json-formatted file.

###                 There are two modes:
- save
- restore


## Save: 

```
usage: save-file-attrs.py save [-h] [--o [%OUTPUT%]] [--p [%PATH%]] [--r]

options:
  -h, --help            show this help message and exit
  --o [%OUTPUT%], -o [%OUTPUT%]
                        Set output file (Optional, default is .saved-file-attrs)
  --p [%PATH%], -p [%PATH%]
                        Set path to store attributes from (Optional, default is current path)
  --r, -r               Store paths as relative instead of full (Optional)
```

## Restore:

```
usage: save-file-attrs.py restore [-h] [--i [%INPUT%]]

options:
  -h, --help            show this help message and exit
  --i [%INPUT%], -i [%INPUT%]
                        Set input file (Optional, default is .saved-file-attrs)
```



  [1]: https://github.com/robertknight/mandrawer
