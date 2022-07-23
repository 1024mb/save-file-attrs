#!/usr/bin/python3

# Utility script for saving and restore the modification times,
# owners and mode for all files in a tree.

import argparse
import json
import os
import sys
import platform
import re

if platform.system() == "Windows":
    from win32_setctime import setctime

def collect_file_attrs(path):
    dirs = os.walk(path)
    file_attrs = {}

    for (dirpath, dirnames, filenames) in dirs:
        files = dirnames + filenames
        for file in files:
            try:
                path = os.path.join(dirpath, file)
                file_info = os.lstat(path)
                file_attrs[path] = {
                    "mode": file_info.st_mode,
                    "ctime": file_info.st_ctime,
                    "mtime": file_info.st_mtime,
                    "atime": file_info.st_atime,
                    "uid": file_info.st_uid,
                    "gid": file_info.st_gid,
                }
            except KeyboardInterrupt:
                print("Shutdown requested... exiting")
                sys.exit(1)
            except:
                pass
    return file_attrs

def apply_file_attrs(attrs):
    proc = 0
    for path in sorted(attrs):
        attr = attrs[path]
        if platform.system() == "Windows":
            try:
                if os.path.lexists(path):
                    if os.path.islink(path) == False:
                        atime = attr["atime"]
                        mtime = attr["mtime"]
                        ctime = attr["ctime"]
                        uid = attr["uid"]
                        gid = attr["gid"]
                        mode = attr["mode"]

                        current_file_info = os.lstat(path)
                        mode_changed = current_file_info.st_mode != mode
                        atime_changed = current_file_info.st_atime != atime
                        mtime_changed = current_file_info.st_mtime != mtime
                        ctime_changed = current_file_info.st_ctime != ctime
                        uid_changed = current_file_info.st_uid != uid
                        gid_changed = current_file_info.st_gid != gid

                        if mode_changed:
                            print("Updating permissions for %s" % path, file=sys.stderr)
                            os.chmod(path, mode)
                            proc = 1

                        if mtime_changed or ctime_changed or atime_changed:
                            print("Updating dates for %s" % path, file=sys.stderr)
                            os.utime(path, (atime, mtime))
                            setctime(path, ctime)
                            proc = 1
                    else:
                        print("Skipping symbolic link %s" % path, file=sys.stderr) # Can't make utime not follow symbolic links in WIndows so we skip them or else the attributes of the resolved paths will be changed.
                else:
                    print("Skipping non-existent file %s" % path, file=sys.stderr)
            except OSError as Err:
                print(Err)
                pass
        elif os.utime in os.supports_follow_symlinks == True:
            try:
                if os.path.lexists(path):
                    atime = attr["atime"]
                    mtime = attr["mtime"]
                    ctime = attr["ctime"]
                    uid = attr["uid"]
                    gid = attr["gid"]
                    mode = attr["mode"]

                    current_file_info = os.lstat(path)
                    mode_changed = current_file_info.st_mode != mode
                    atime_changed = current_file_info.st_atime != atime
                    mtime_changed = current_file_info.st_mtime != mtime
                    uid_changed = current_file_info.st_uid != uid
                    gid_changed = current_file_info.st_gid != gid

                    if uid_changed or gid_changed:
                        print("Updating UID, GID for %s" % path, file=sys.stderr)
                        os.chown(path, uid, gid, follow_symlinks=False)
                        proc = 1

                    if mode_changed:
                        print("Updating permissions for %s" % path, file=sys.stderr)
                        os.chmod(path, mode, follow_symlinks=False)
                        proc = 1

                    if mtime_changed or atime_changed:
                        print("Updating mtime or atime for %s" % path, file=sys.stderr)
                        os.utime(path, (atime, mtime), follow_symlinks=False)
                        proc = 1
                else:
                    print("Skipping non-existent file %s" % path, file=sys.stderr)
            except OSError as Err:
                print(Err)
                pass
        else:
            try:
                if os.path.lexists(path):
                    atime = attr["atime"]
                    mtime = attr["mtime"]
                    ctime = attr["ctime"]
                    uid = attr["uid"]
                    gid = attr["gid"]
                    mode = attr["mode"]

                    current_file_info = os.lstat(path)
                    mode_changed = current_file_info.st_mode != mode
                    atime_changed = current_file_info.st_atime != atime
                    mtime_changed = current_file_info.st_mtime != mtime
                    uid_changed = current_file_info.st_uid != uid
                    gid_changed = current_file_info.st_gid != gid

                    if uid_changed or gid_changed:
                        print("Updating UID, GID for %s" % path, file=sys.stderr)
                        os.chown(path, uid, gid)
                        proc = 1

                    if mode_changed:
                        print("Updating permissions for %s" % path, file=sys.stderr)
                        os.chmod(path, mode)
                        proc = 1

                    if mtime_changed or atime_changed:
                        print("Updating mtime or atime for %s" % path, file=sys.stderr)
                        os.utime(path, (atime, mtime))
                        proc = 1
                else:
                    print("Skipping non-existent file %s" % path, file=sys.stderr)
            except OSError as Err:
                print(Err)
                pass
    if proc == 0:
                print("Nothing to change.")
                sys.exit(0)

def main():

    parser = argparse.ArgumentParser(
        "Save and restore file attributes in a directory tree"
    )
    subparsers = parser.add_subparsers(dest="mode", help="Select the mode of operation")
    save_parser = subparsers.add_parser(
        "save", help="Save the attributes of files in the directory tree"
    )
    save_parser.add_argument("--o", "-o", help="Set output file (Optional)", metavar="%OUTPUT%", default=".saved-file-attrs")
    save_parser.add_argument("--p", "-p", help="Set path to store attributes from (Optional)", metavar="%PATH%", default=".")
    save_parser.add_argument("--r", "-r", help="Stores paths as relatives instead of full", action="store_true")
    restore_parser = subparsers.add_parser(
        "restore", help="Restore saved file attributes"
    )
    restore_parser.add_argument("--i", "-i", help="Set input file (Optional)", metavar="%INPUT%", default=".saved-file-attrs")
    args = parser.parse_args()

    if args.mode == "save":
        if args.p.endswith('"'):
            args.p = args.p[:-1] + "\\" # Windows escapes the quote if the command ends in \" so this fixes that, or at least it does if this argument is the last one, otherwise the output argument will eat all the next args 
        if args.p.endswith(':'):
            args.p = args.p + "\\"
        if not os.path.exists(args.p):
                print("\nERROR: The specified path:\n\n%s\n\nDoesn't exist, aborting..." % args.p)
                sys.exit(1)
        
        ATTR_FILE_NAME = args.o
        if ATTR_FILE_NAME.endswith('"'):
            ATTR_FILE_NAME = ATTR_FILE_NAME[:-1] + "\\" # Windows escapes the quote if the command ends in \" so this fixes that, or at least it does if this argument is the last one, otherwise the output argument will eat all the next args

        if ATTR_FILE_NAME.endswith(':'):
            ATTR_FILE_NAME = ATTR_FILE_NAME + "\\"

        if not os.path.dirname(ATTR_FILE_NAME) == "":  # if the root directory of ATTR_FILE_NAME is not an empty string
            if not os.path.exists(os.path.dirname(ATTR_FILE_NAME)): # if the path of the root directory of ATTR_FILE_NAME doesn't exist
                os.makedirs(os.path.dirname(ATTR_FILE_NAME)) # create the path
                
        if os.path.basename(ATTR_FILE_NAME) == "":
            ATTR_FILE_NAME = os.path.join(ATTR_FILE_NAME, ".saved-file-attrs")
        
        reqstate = [args.r == True,
                    args.p != ".",
                    os.path.dirname(ATTR_FILE_NAME) == ""
                    ]
                    
        if (reqstate[0] & reqstate[1]):
            origdir = os.getcwd()
        if all(reqstate):
            ATTR_FILE_NAME = os.path.join(os.getcwd(), ATTR_FILE_NAME)
        if (reqstate[0] & reqstate[1]):
            os.chdir(args.p)
            args.p = "."
        
        try:
            attr_file = open(ATTR_FILE_NAME, "w")
            attrs = collect_file_attrs(args.p)
            json.dump(attrs, attr_file, indent=2)
            print("Attributes saved to "+ATTR_FILE_NAME)
        except KeyboardInterrupt:
            if not origdir == None:
                os.chdir(origdir)
            print("Shutdown requested... exiting")
            sys.exit(1)
        except OSError as ERR_W:
            if not origdir == None:
                os.chdir(origdir)
            print("ERROR: There was an error writting to the attribute file.\n\n", ERR_W, "\n")
            sys.exit(1)
        
        if not origdir == None:
            os.chdir(origdir)


    elif args.mode == "restore":
        ATTR_FILE_NAME = args.i
        if ATTR_FILE_NAME.endswith('"'):
            ATTR_FILE_NAME = ATTR_FILE_NAME[:-1] + "\\" # Windows escapes the quote if the command ends in \" so this fixes that
        if os.path.basename(ATTR_FILE_NAME) == "":
            ATTR_FILE_NAME = os.path.join(ATTR_FILE_NAME, ".saved-file-attrs")
        if not os.path.exists(ATTR_FILE_NAME):
            print(
                "Saved attributes file '%s' not found" % ATTR_FILE_NAME, file=sys.stderr
            )
            sys.exit(1)
        ATTR_FILE_SIZE = os.path.getsize(ATTR_FILE_NAME)
        if ATTR_FILE_SIZE == 0:
            print("ERROR: The attibute file is empty!")
            sys.exit(1)
        try:
            attr_file = open(ATTR_FILE_NAME, "r")
            attrs = json.load(attr_file)
            apply_file_attrs(attrs)
        except KeyboardInterrupt:
                print("Shutdown requested... exiting")
                sys.exit(1)
        except OSError as ERR_R:
            print("ERROR: There was an error reading the attribute file, no date has been changed.\n\n", ERR_R, "\n")
            sys.exit(1)

    elif args.mode == None:
        print("You have to use either save or restore.\nSee the help.")
        sys.exit(3)


if __name__ == "__main__":
    main()
