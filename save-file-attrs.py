#!/usr/bin/env python

# Utility script for saving and restore the modification times,
# owners and mode for all files in a tree.

import argparse
import json
import os
import platform
import re
import sys

if platform.system() == "Windows":
    from win32_setctime import setctime


def collect_file_attrs(path, exclusions, origpath, relative, exclusionsfile, exclusionsdir):
    dirs = os.walk(path)
    file_attrs = {}

    # exclusions setup start
    exclusions2 = []  # this is for exclusions that are full paths, so we can store the root directory
    if origpath != os.curdir:  # this doesn't indicate whether relative has been set because this also applies if -p
        # hasn't been used
        replacedpath = re.escape(origpath)  # path ready for regex
    if relative is False:
        if exclusions is not None:
            if origpath != os.curdir:
                if platform.system() == "Windows":
                    for i, s in enumerate(exclusions):
                        if re.match(replacedpath, s, flags=re.IGNORECASE) is None:
                            exclusions[i] = re.escape(s)
                        else:
                            r = s + os.path.sep  # adding a slash to the end of the path because the string is a
                            # directory, or at least that's how we consider it always when using --ex
                            exclusions[i] = re.escape(r)
                else:
                    for i, s in enumerate(exclusions):
                        if re.match(replacedpath, s) is None:
                            exclusions[i] = re.escape(s)
                        else:
                            r = s + os.path.sep  # adding a slash to the end of the path because the string is a
                            # directory, or at least that's how we consider it always when using --ex
                            exclusions[i] = re.escape(r)
            else:
                for i, s in enumerate(exclusions):
                    r = os.path.relpath(s)
                    exclusions[i] = re.escape(r)
            if len(exclusions2) != 0:
                regex_excl = "|".join(exclusions) + "|" + "|".join(exclusions2)
            else:
                regex_excl = "|".join(exclusions)
        if exclusionsfile is not None:
            if origpath != os.curdir:
                for i, s in enumerate(exclusionsfile):
                    exclusionsfile[i] = re.escape(s)
            else:
                for i, s in enumerate(exclusionsfile):
                    a = os.path.splitdrive(s)
                    if a[0] != "":
                        r = os.path.relpath(s)
                        exclusionsfile[i] = "^" + re.escape(os.curdir + os.path.sep + r) + "$"
                    else:
                        r = os.path.relpath(s)
                        exclusionsfile[i] = re.escape(r)
            regex_excl = "|".join(exclusionsfile)
        if exclusionsdir is not None:
            if origpath != os.curdir:
                for i, s in enumerate(exclusionsdir):
                    exclusionsdir[i] = re.escape(s)
            else:
                for i, s in enumerate(exclusionsdir):
                    r = os.path.relpath(s)
                    exclusionsdir[i] = re.escape(r)
            regex_excl_dirs = "|".join(exclusionsdir)
    else:  # if relative is true
        if exclusions is not None:
            for i, s in enumerate(exclusions):
                r = os.path.relpath(s)
                exclusions[i] = re.escape(r)
            regex_excl = "|".join(exclusions)
        if exclusionsfile is not None:
            for i, s in enumerate(exclusionsfile):
                a = os.path.splitdrive(s)
                if a[0] != "":
                    r = os.path.relpath(s)
                    exclusionsfile[i] = "^" + re.escape(os.curdir + os.path.sep + r) + "$"
                else:
                    r = os.path.relpath(s)
                    exclusionsfile[i] = re.escape(r)
            regex_excl = "|".join(exclusionsfile)
        if exclusionsdir is not None:
            for i, s in enumerate(exclusionsdir):
                r = os.path.relpath(s)
                exclusionsdir[i] = re.escape(r)
            regex_excl_dirs = "|".join(exclusionsdir)
    #  exclusions setup end

    for (dirpath, dirnames, filenames) in dirs:
        files = dirnames + filenames
        for file in files:
            try:
                if platform.system() == "Windows":  # Windows is a case-insensitive OS so adding the re.IGNORECASE flag
                    if exclusions is not None:
                        if re.search(".*(" + regex_excl + ").*", os.path.join(dirpath, file),
                                     flags=re.IGNORECASE) is None:
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
                        elif origpath == os.curdir or relative:
                            print("\"" + os.path.join(dirpath, file).replace(os.curdir + os.path.sep, os.getcwd() +
                                                                             os.path.sep, 1) + "\" has been skipped.")
                        else:
                            print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                    if exclusionsfile is not None and exclusionsdir is None:
                        if os.path.isfile(os.path.join(dirpath, file)):
                            if re.search(".*(" + regex_excl + ")([^" + re.escape(os.path.sep) + "]+$|$)",
                                         os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
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
                            elif origpath == os.curdir or relative:
                                print("\"" + os.path.join(dirpath, file).replace(os.curdir + os.path.sep, os.getcwd()
                                                                                 + os.path.sep, 1) + "\" has been "
                                                                                                     "skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                        else:
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
                    elif exclusionsdir is not None and exclusionsfile is None:
                        if os.path.isdir(os.path.join(dirpath, file)):
                            if re.search(".*(" + regex_excl_dirs + ")" + "(.*" + re.escape(os.path.sep) + "*.+|$)",
                                         os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
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
                            elif origpath == os.curdir or relative:
                                print("\"" + os.path.join(dirpath, file).replace(os.curdir + os.path.sep, os.getcwd()
                                                                                 + os.path.sep, 1) + "\" has been "
                                                                                                     "skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                        else:
                            if re.search(".*(" + regex_excl_dirs + ".*" + re.escape(os.path.sep) + ").*",
                                         os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
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
                            elif origpath == os.curdir or relative:
                                print("\"" + os.path.join(dirpath, file).replace(os.curdir + os.path.sep, os.getcwd()
                                                                                 + os.path.sep, 1) + "\" has been "
                                                                                                     "skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                    elif (exclusionsdir and exclusionsfile) is not None:
                        if os.path.isdir(os.path.join(dirpath, file)):
                            if re.search(".*(" + regex_excl_dirs + ")" + "(.*" + re.escape(os.path.sep) + "*.+|$)",
                                         os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
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
                            elif origpath == os.curdir or relative:
                                print("\"" + os.path.join(dirpath, file).replace(os.curdir + os.path.sep, os.getcwd()
                                                                                 + os.path.sep, 1) + "\" has been "
                                                                                                     "skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                        else:
                            if re.search(".*(" + regex_excl + ")([^" + re.escape(os.path.sep) + "]+$|$)",
                                         os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
                                if re.search(".*(" + regex_excl_dirs + ".*" + re.escape(os.path.sep) + ").*",
                                             os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
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
                                elif origpath == os.curdir or relative:
                                    print("\"" + os.path.join(dirpath, file).replace(os.curdir + os.path.sep,
                                                                                     os.getcwd() + os.path.sep, 1)
                                          + "\" has been skipped.")
                                else:
                                    print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                            elif origpath == os.curdir or relative:
                                print("\"" + os.path.join(dirpath, file).replace(os.curdir + os.path.sep, os.getcwd()
                                                                                 + os.path.sep, 1) + "\" has been "
                                                                                                     "skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                    elif (exclusions and exclusionsfile and exclusionsdir) is None:
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
                else:  # if platform is not Windows we are assuming is a case-sensitive OS
                    if exclusions is not None:
                        if re.search(".*(" + regex_excl + ").*", os.path.join(dirpath, file)) is None:
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
                        elif origpath == os.curdir or relative:
                            print("\"" + os.path.join(dirpath, file).replace(os.curdir + os.path.sep, os.getcwd()
                                                                             + os.path.sep, 1) + "\" has been skipped.")
                        else:
                            print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                    if exclusionsfile is not None and exclusionsdir is None:
                        if os.path.isfile(os.path.join(dirpath, file)):
                            if re.search(".*(" + regex_excl + ")([^" + re.escape(os.path.sep) + "]+$|$)",
                                         os.path.join(dirpath, file)) is None:
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
                            elif origpath == os.curdir or relative:
                                print("\"" + os.path.join(dirpath, file).replace(os.curdir + os.path.sep, os.getcwd() +
                                                                                 os.path.sep,
                                                                                 1) + "\" has been skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                        else:
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
                    elif exclusionsdir is not None and exclusionsfile is None:
                        if os.path.isdir(os.path.join(dirpath, file)):
                            if re.search(".*(" + regex_excl_dirs + ")" + "(.*" + re.escape(os.path.sep) + "*.+|$)",
                                         os.path.join(dirpath, file)) is None:
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
                            elif origpath == os.curdir or relative:
                                print("\"" + os.path.join(dirpath, file).replace(os.curdir + os.path.sep, os.getcwd() +
                                                                                 os.path.sep,
                                                                                 1) + "\" has been skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                        else:
                            if re.search(".*(" + regex_excl_dirs + ".*" + re.escape(os.path.sep) + ").*",
                                         os.path.join(dirpath, file)) is None:
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
                            elif origpath == os.curdir or relative:
                                print("\"" + os.path.join(dirpath, file).replace(os.curdir + os.path.sep, os.getcwd() +
                                                                                 os.path.sep,
                                                                                 1) + "\" has been skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                    elif (exclusionsdir and exclusionsfile) is not None:
                        if os.path.isdir(os.path.join(dirpath, file)):
                            if re.search(".*(" + regex_excl_dirs + ")" + "(.*" + re.escape(os.path.sep) + "*.+|$)",
                                         os.path.join(dirpath, file)) is None:
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
                            elif origpath == os.curdir or relative:
                                print("\"" + os.path.join(dirpath, file).replace(os.curdir + os.path.sep, os.getcwd() +
                                                                                 os.path.sep,
                                                                                 1) + "\" has been skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                        else:
                            if re.search(".*(" + regex_excl + ")([^" + re.escape(os.path.sep) + "]+$|$)",
                                         os.path.join(dirpath, file)) is None:
                                if re.search(".*(" + regex_excl_dirs + ".*" + re.escape(os.path.sep) + ").*",
                                             os.path.join(dirpath, file)) is None:
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
                                elif origpath == os.curdir or relative:
                                    print("\"" + os.path.join(dirpath, file).replace(os.curdir + os.path.sep,
                                                                                     os.getcwd() +
                                                                                     os.path.sep,
                                                                                     1) + "\" has been skipped.")
                                else:
                                    print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                            elif origpath == os.curdir or relative:
                                print("\"" + os.path.join(dirpath, file).replace(os.curdir + os.path.sep, os.getcwd() +
                                                                                 os.path.sep,
                                                                                 1) + "\" has been skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                    elif (exclusions and exclusionsfile and exclusionsdir) is None:
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
            except Exception as e:
                print(e)
                pass
    return file_attrs


def apply_file_attrs(attrs):
    proc = 0
    for path in sorted(attrs):
        attr = attrs[path]
        if platform.system() == "Windows":
            try:
                if os.path.lexists(path):
                    if not os.path.islink(path):
                        atime = attr["atime"]
                        mtime = attr["mtime"]
                        ctime = attr["ctime"]
                        mode = attr["mode"]

                        current_file_info = os.lstat(path)
                        mode_changed = current_file_info.st_mode != mode
                        atime_changed = current_file_info.st_atime != atime
                        mtime_changed = current_file_info.st_mtime != mtime
                        ctime_changed = current_file_info.st_ctime != ctime

                        if mode_changed:
                            print("Updating permissions for %s" % path)
                            os.chmod(path, mode)
                            proc = 1

                        if mtime_changed or ctime_changed or atime_changed:
                            print("Updating dates for %s" % path)
                            os.utime(path, (atime, mtime))
                            setctime(path, ctime)
                            proc = 1
                    else:
                        print("Skipping symbolic link %s" % path)  # Can't make utime not follow
                        # symbolic links in Windows, so we skip them or else the attributes of the resolved paths will
                        # be changed.
                else:
                    print("Skipping non-existent file %s" % path)
            except OSError as Err:
                print(Err)
                pass
        elif os.utime in os.supports_follow_symlinks is True:
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
                        print("Updating UID, GID for %s" % path)
                        os.chown(path, uid, gid, follow_symlinks=False)
                        proc = 1

                    if mode_changed:
                        print("Updating permissions for %s" % path)
                        os.chmod(path, mode, follow_symlinks=False)
                        proc = 1

                    if mtime_changed or atime_changed:
                        print("Updating mtime or atime for %s" % path)
                        os.utime(path, (atime, mtime), follow_symlinks=False)
                        proc = 1
                else:
                    print("Skipping non-existent file %s" % path)
            except OSError as Err:
                print(Err)
                pass
        else:
            try:
                if os.path.lexists(path):
                    atime = attr["atime"]
                    mtime = attr["mtime"]
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
                        print("Updating UID, GID for %s" % path)
                        os.chown(path, uid, gid)
                        proc = 1

                    if mode_changed:
                        print("Updating permissions for %s" % path)
                        os.chmod(path, mode)
                        proc = 1

                    if mtime_changed or atime_changed:
                        print("Updating mtime or atime for %s" % path)
                        os.utime(path, (atime, mtime))
                        proc = 1
                else:
                    print("Skipping non-existent file %s" % path)
            except OSError as Err:
                print(Err, file=sys.stderr)
                pass
    if proc == 0:
        print("Nothing to change.")
        sys.exit(0)


def save_attrs(pathtosave, output, relative, exclusions, exclusionsfile, exclusionsdir):
    if pathtosave.endswith('"'):
        pathtosave = pathtosave[:-1] + "\\"  # Windows escapes the quote if the command ends in \" so this fixes
        # that, or at least it does if this argument is the last one, otherwise the output argument will eat all the
        # next args
    if pathtosave.endswith(':'):
        pathtosave = pathtosave + os.path.sep
    if not os.path.exists(pathtosave):
        print("\nERROR: The specified path:\n\n%s\n\nDoesn't exist, aborting..." % pathtosave, file=sys.stderr)
        sys.exit(1)

    attr_file_name = output
    if attr_file_name.endswith('"'):
        attr_file_name = attr_file_name[:-1]  # Windows escapes the quote if the command ends in \" so this fixes
        # that, or at least it does if this argument is the last one, otherwise the output argument will eat all the
        # following args

    if attr_file_name.endswith(':'):
        attr_file_name = attr_file_name + os.path.sep

    if not os.path.dirname(attr_file_name) == "":  # if the root directory of attr_file_name is not an empty string
        if not os.path.exists(
                os.path.dirname(attr_file_name)):  # if the path of the root directory of attr_file_name doesn't exist
            os.makedirs(os.path.dirname(attr_file_name))  # create the path

    if os.path.basename(attr_file_name) == "":
        attr_file_name = os.path.join(attr_file_name, ".saved-file-attrs")

    reqstate = [relative is True,
                pathtosave != os.curdir,
                os.path.dirname(attr_file_name) == ""
                ]

    origpath = pathtosave
    if reqstate[0] & reqstate[1]:
        origdir = os.getcwd()
    if all(reqstate):
        attr_file_name = os.path.join(os.getcwd(), attr_file_name)
    if reqstate[0] & reqstate[1]:
        os.chdir(pathtosave)
        pathtosave = os.curdir

    try:
        attr_file = open(attr_file_name, "w", encoding="utf_8")
        attrs = collect_file_attrs(pathtosave, exclusions, origpath, relative, exclusionsfile, exclusionsdir)
        json.dump(attrs, attr_file, indent=2, ensure_ascii=False)
        print("Attributes saved to " + attr_file_name)
    except KeyboardInterrupt:
        if origdir in locals():
            os.chdir(origdir)
        print("Shutdown requested... exiting", file=sys.stderr)
        sys.exit(1)
    except OSError as ERR_W:
        if origdir in locals():
            os.chdir(origdir)
        print("ERROR: There was an error writing to the attribute file.\n\n", ERR_W, "\n", file=sys.stderr)
        sys.exit(1)

    if reqstate[0] & reqstate[1]:
        os.chdir(origdir)


def restore_attrs(inputfile):
    attr_file_name = inputfile
    if attr_file_name.endswith('"'):
        attr_file_name = attr_file_name[:-1] + "\\"  # Windows escapes the quote if the command ends in \" so this
        # fixes that
    if os.path.basename(attr_file_name) == "":
        attr_file_name = os.path.join(attr_file_name, ".saved-file-attrs")
    if not os.path.exists(attr_file_name):
        print("Saved attributes file \"%s\" not found" % attr_file_name, file=sys.stderr)
        sys.exit(1)
    attr_file_size = os.path.getsize(attr_file_name)

    if attr_file_size == 0:
        print("ERROR: The attribute file is empty!", file=sys.stderr)
        sys.exit(1)
    try:
        attr_file = open(attr_file_name, "r", encoding="utf_8")
        attrs = json.load(attr_file)
        if len(attrs) == 0:
            print("ERROR: The attribute file is empty!", file=sys.stderr)
            sys.exit(1)
        else:
            apply_file_attrs(attrs)
    except KeyboardInterrupt:
        print("Shutdown requested... exiting", file=sys.stderr)
        sys.exit(1)
    except OSError as ERR_R:
        print("ERROR: There was an error reading the attribute file, no date has been changed.\n\n", ERR_R, "\n",
              file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Save and restore file attributes in a directory tree")
    subparsers = parser.add_subparsers(dest="mode", help="Select the mode of operation")
    save_parser = subparsers.add_parser(
        "save", help="Save the attributes of files and folders in a directory tree"
    )
    save_parser.add_argument("--o", "-o", help="Set the output file (Optional, "
                                               "default is \".saved-file-attrs\" in current dir)",
                             metavar="%OUTPUT%", default=".saved-file-attrs", nargs="?")
    save_parser.add_argument("--p", "-p", help="Set the path to store attributes from (Optional, "
                                               "default is current path)",
                             metavar="%PATH%", default=os.curdir, nargs="?")
    save_parser.add_argument("--r", "-r", help="Store the paths as relative instead of full (Optional)",
                             action="store_true")
    save_parser.add_argument("--ex", "-ex", help="Match these strings indiscriminately and exclude them, program will "
                                                 "exclude anything that includes these strings in their paths unless a "
                                                 "full path is specified in which case it will be considered a "
                                                 "directory and everything inside will be excluded. (Optional)",
                             metavar="%NAME%", nargs="*")
    save_parser.add_argument("--ef", "-ef", help="Match all the paths that incorporates these strings and exclude "
                                                 "them, strings are considered filenames unless a full path is given "
                                                 "in which case only that file will be excluded. If the argument is "
                                                 "given without any value, all the files will be excluded. (Optional)",
                             metavar="%FILE%", nargs="*")
    save_parser.add_argument("--ed", "-ed", help="Match all the paths that incorporates these strings and exclude "
                                                 "them, strings are considered directories unless a full path is "
                                                 "given in which case it will exclude all the subdirs and files "
                                                 "inside that directory. (Optional)",
                             metavar="%DIRECTORY%", nargs="*")
    restore_parser = subparsers.add_parser(
        "restore", help="Restore saved file and folder attributes"
    )
    restore_parser.add_argument("--i", "-i", help="Set the input file containing the attributes to restore (Optional, "
                                                  "default is \".saved-file-attrs\" in current dir)",
                                metavar="%INPUT%", default=".saved-file-attrs", nargs="?")
    args = parser.parse_args()

    if args.mode == "save":
        if args.ed is not None:
            if len(args.ed) == 0 or "" in args.ed:
                print("ERROR: Directory exclusion can't be empty or else everything will be excluded, aborting...",
                      file=sys.stderr)
                sys.exit(3)
        elif args.ex is not None:
            if len(args.ex) == 0 or "" in args.ex:
                print("ERROR: Exclusion can't be empty or else everything will be excluded, aborting...",
                      file=sys.stderr)
                sys.exit(3)
        elif args.ex is not None and (args.ef or args.ed) is not None:
            print("ERROR: You can't use --ex with --ef or --ed, you should use --ef and --ed or use only one of them",
                  file=sys.stderr)
            sys.exit(3)
        else:
            save_attrs(args.p, args.o, args.r, args.ex, args.ef, args.ed)
    elif args.mode == "restore":
        restore_attrs(args.i)
    elif args.mode is None:
        print("You have to use either save or restore.\nSee the help.")
        sys.exit(3)
    else:
        print("Option not recognized...")
        sys.exit(3)


if __name__ == "__main__":
    main()
