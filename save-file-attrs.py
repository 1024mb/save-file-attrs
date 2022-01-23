#!/usr/bin/python3

# Utility script for saving and restore the modification times,
# owners and mode for all files in a tree.

import argparse
import json
import os
import sys
import platform

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
        if os.path.lexists(path):
            if platform.system() == "Windows":
                if os.path.islink(path) == False:
                    atime = attr["atime"]
                    mtime = attr["mtime"]
                    ctime = attr['ctime']
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
                    print("Skipping symbolic link %s" % path, file=sys.stderr)
            else:
                atime = attr["atime"]
                mtime = attr["mtime"]
                ctime = attr['ctime']
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
    if proc == 0:
                print("Nothing to change")


def main():

    parser = argparse.ArgumentParser(
        "Save and restore file attributes in a directory tree"
    )
    subparsers = parser.add_subparsers(dest="mode", help="Select the mode of operation")
    save_parser = subparsers.add_parser(
        "save", help="Save the attributes of files in the directory tree"
    )
    save_parser.add_argument("--o", "-o", help="Set output file (Optional)", metavar="%OUTPUT%")
    restore_parser = subparsers.add_parser(
        "restore", help="Restore saved file attributes"
    )
    restore_parser.add_argument("--i", "-i", help="Set input file (Optional)", metavar="%INPUT%")
    args = parser.parse_args()

    if args.mode == "save":
        if args.o == None:
            ATTR_FILE_NAME = ".saved-file-attrs"
        else:
            ATTR_FILE_NAME = args.o
            if ATTR_FILE_NAME.endswith('"'):
                print("ERROR: It seems you are using CMD or Powershell on Windows, if so you should add another\nbackslash to the end of the path or use slashes instead, otherwise it wont work.\n\nExiting now...")
                sys.exit(1)
            if not os.path.dirname(ATTR_FILE_NAME) == "":
                if not os.path.exists(os.path.dirname(ATTR_FILE_NAME)):
                    os.makedirs(os.path.dirname(ATTR_FILE_NAME))
            if os.path.basename(ATTR_FILE_NAME) == "":
                ATTR_FILE_NAME = os.path.join(ATTR_FILE_NAME, ".saved-file-attrs")
        attr_file = open(ATTR_FILE_NAME, "w")
        attrs = collect_file_attrs(".")
        json.dump(attrs, attr_file, indent=2)
        print("Attributes saved to "+ATTR_FILE_NAME)

    elif args.mode == "restore":
        if args.i == None:
            ATTR_FILE_NAME = ".saved-file-attrs"
        else:
            ATTR_FILE_NAME = args.i
            if not os.path.dirname(ATTR_FILE_NAME) == "":
                if not os.path.exists(os.path.dirname(ATTR_FILE_NAME)):
                    os.makedirs(os.path.dirname(ATTR_FILE_NAME))
            if os.path.basename(ATTR_FILE_NAME) == "":
                ATTR_FILE_NAME = os.path.join(ATTR_FILE_NAME, ".saved-file-attrs")
        if not os.path.exists(ATTR_FILE_NAME):
            print(
                "Saved attributes file '%s' not found" % ATTR_FILE_NAME, file=sys.stderr
            )
            sys.exit(1)
        attr_file = open(ATTR_FILE_NAME, "r")
        attrs = json.load(attr_file)
        apply_file_attrs(attrs)

    elif args.mode == None:
        print("You have to use either save or restore.\nSee the help.")
        sys.exit(1)


if __name__ == "__main__":
    main()
