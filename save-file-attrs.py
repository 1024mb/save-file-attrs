#!/usr/bin/env python
from __future__ import annotations

# Utility script for saving and restore the modification times,
# owners and mode for all files in a tree.

import argparse
import json
import os
import platform
import re
import sys

from version import __version__

if platform.system() == "Windows":
    from win32_setctime import setctime


def collect_file_attrs(path: str, exclusions: list, origpath: str, relative: bool, exclusions_file: list,
                       exclusions_dir: list, no_print: bool) -> dict:
    print("\nCollecting attributes, please wait...\n")

    curr_working_dir = re.escape(os.getcwd())
    current_system = platform.system()

    if relative is False and origpath == ".":
        dirs = os.walk(os.getcwd())
    else:
        dirs = os.walk(path)

    file_attrs = {}
    exclusions2 = []  # this is for exclusions that are full paths, so we can store the root directory

    # exclusions setup start
    replacedpath = None  # so I don't get annoyed by the IDE
    if origpath != os.curdir:  # this doesn't indicate whether relative has been set because this also applies if -p
        # hasn't been used
        replacedpath = re.escape(origpath)  # path ready for regex
    if relative is False:  # all paths will be saved as full
        if exclusions is not None:
            if origpath != os.curdir:  # if origpath has a value other than .
                for i, s in enumerate(exclusions):
                    if s.startswith(os.curdir + os.path.sep):
                        r = os.path.normpath(os.path.join(origpath, s))
                        exclusions[i] = re.escape(r)
                    elif current_system == "Windows" and re.match(replacedpath, s, flags=re.IGNORECASE) is not None:
                        r = s + os.path.sep  # adding a slash to the end of the path because the string is a
                        # directory, or at least that's how we consider it always when using --ex
                        exclusions[i] = re.escape(s)
                        exclusions2.append(r)
                    elif current_system != "Windows" and s.startswith(origpath):
                        r = s + os.path.sep  # adding a slash to the end of the path because the string is a
                        # directory, or at least that's how we consider it always when using --ex
                        exclusions[i] = re.escape(s)
                        exclusions2.append(r)
                    else:
                        exclusions[i] = re.escape(s)
            else:  # if is os.curdir
                for i, s in enumerate(exclusions):
                    if s.startswith(os.curdir + os.path.sep):
                        r = os.path.abspath(s)
                        exclusions[i] = re.escape(r)
                    elif current_system == "Windows" and re.match(curr_working_dir, s, flags=re.IGNORECASE) is not None:
                        r = s + os.path.sep  # adding a slash to the end of the path because the string is a
                        # directory, or at least that's how we consider it always when using --ex
                        exclusions[i] = re.escape(s)
                        exclusions2.append(re.escape(r))
                    elif current_system != "Windows" and s.startswith(curr_working_dir):
                        r = s + os.path.sep  # adding a slash to the end of the path because the string is a
                        # directory, or at least that's how we consider it always when using --ex
                        exclusions[i] = re.escape(s)
                        exclusions2.append(re.escape(r))
                    else:
                        exclusions[i] = re.escape(s)
            if len(exclusions2) != 0:
                regex_excl = "|".join(exclusions) + "|" + "|".join(exclusions2)
            else:
                regex_excl = "|".join(exclusions)
        if exclusions_file is not None:
            if origpath != os.curdir:
                for i, s in enumerate(exclusions_file):
                    a = os.path.splitdrive(s)
                    if s.startswith(os.curdir + os.path.sep):
                        r = os.path.normpath(os.path.join(origpath, s))
                        exclusions_file[i] = re.escape(r)
                    elif a[0] != "":
                        exclusions_file[i] = "^" + re.escape(s) + "$"
                    else:
                        exclusions_file[i] = re.escape(s)
            else:
                for i, s in enumerate(exclusions_file):
                    a = os.path.splitdrive(s)
                    if s.startswith(os.curdir + os.path.sep):
                        r = os.path.abspath(s)
                        exclusions_file[i] = re.escape(r)
                    elif a[0] != "":
                        exclusions_file[i] = "^" + re.escape(s) + "$"
                    else:
                        exclusions_file[i] = re.escape(s)
            regex_excl = "|".join(exclusions_file)
        if exclusions_dir is not None:
            if origpath != os.curdir:
                for i, s in enumerate(exclusions_dir):
                    if s.startswith(os.curdir + os.path.sep):
                        r = os.path.normpath(os.path.join(origpath, s))
                        exclusions_dir[i] = re.escape(r)
                    else:
                        exclusions_dir[i] = re.escape(s)
            else:
                for i, s in enumerate(exclusions_dir):
                    if s.startswith(os.curdir + os.path.sep):
                        r = os.path.abspath(s)
                        exclusions_dir[i] = re.escape(r)
                    else:
                        exclusions_dir[i] = re.escape(s)
            regex_excl_dirs = "|".join(exclusions_dir)
    else:  # if relative is true
        if exclusions is not None:
            for i, s in enumerate(exclusions):
                a = os.path.splitdrive(s)
                if s.startswith(os.path.sep) or s.startswith(os.curdir + os.path.sep):
                    exclusions[i] = re.escape(s)
                elif a[0] != "":
                    r = os.path.relpath(s)
                    exclusions[i] = re.escape(r)
                else:
                    exclusions[i] = re.escape(s)
            regex_excl = "|".join(exclusions)
        if exclusions_file is not None:
            for i, s in enumerate(exclusions_file):
                a = os.path.splitdrive(s)
                if s.startswith(os.path.sep) or s.startswith(os.curdir + os.path.sep):
                    exclusions_file[i] = re.escape(s)
                elif a[0] != "":
                    r = os.path.relpath(s)
                    exclusions_file[i] = "^" + re.escape(r) + "$"
                else:
                    exclusions_file[i] = re.escape(s)
            regex_excl = "|".join(exclusions_file)
        if exclusions_dir is not None:
            for i, s in enumerate(exclusions_dir):
                a = os.path.splitdrive(s)
                if s.startswith(os.path.sep) or s.startswith(os.curdir + os.path.sep):
                    exclusions_dir[i] = re.escape(s)
                elif a[0] != "":
                    r = os.path.relpath(s)
                    exclusions_dir[i] = "^" + re.escape(r)
                else:
                    exclusions_dir[i] = re.escape(s)
            regex_excl_dirs = "|".join(exclusions_dir)
    #  exclusions setup end

    for (dirpath, dirnames, filenames) in dirs:
        files = dirnames + filenames
        for file in files:
            try:
                if exclusions is not None:
                    if current_system == "Windows" and \
                            re.search(".*(" + regex_excl + ").*", os.path.join(dirpath, file),
                                      flags=re.IGNORECASE) is None:
                        get_attrs(dirpath, file, file_attrs)
                    elif current_system != "Windows" and \
                            re.search(".*(" + regex_excl + ").*", os.path.join(dirpath, file)) is None:
                        get_attrs(dirpath, file, file_attrs)
                    elif no_print is False:
                        if origpath == os.curdir or relative:
                            print("\"" + os.path.abspath(os.path.join(dirpath, file)) + "\" has been skipped.")
                        else:
                            print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                if exclusions_file is not None and exclusions_dir is None:
                    if os.path.isfile(os.path.join(dirpath, file)):
                        if current_system == "Windows" and \
                                re.search(".*(" + regex_excl + ")([^" + re.escape(os.path.sep) + "]+$|$)",
                                          os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif current_system != "Windows" and \
                                re.search(".*(" + regex_excl + ")([^" + re.escape(os.path.sep) + "]+$|$)",
                                          os.path.join(dirpath, file)) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif no_print is False:
                            if origpath == os.curdir or relative:
                                print("\"" + os.path.abspath(os.path.join(dirpath, file)) + "\" has been skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                    else:
                        get_attrs(dirpath, file, file_attrs)
                elif exclusions_dir is not None and exclusions_file is None:
                    if os.path.isdir(os.path.join(dirpath, file)):
                        if current_system == "Windows" and \
                                re.search(".*(" + regex_excl_dirs + ")" + "(.*" + re.escape(os.path.sep) + "*.+|$)",
                                          os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif current_system != "Windows" and \
                                re.search(".*(" + regex_excl_dirs + ")" + "(.*" + re.escape(os.path.sep) + "*.+|$)",
                                          os.path.join(dirpath, file)) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif no_print is False:
                            if origpath == os.curdir or relative:
                                print("\"" + os.path.abspath(os.path.join(dirpath, file)) + "\" has been skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                    else:  # if is a file
                        if current_system == "Windows" and \
                                re.search(".*(" + regex_excl_dirs + ".*" + re.escape(os.path.sep) + ").*",
                                          os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif current_system != "Windows" and \
                                re.search(".*(" + regex_excl_dirs + ".*" + re.escape(os.path.sep) + ").*",
                                          os.path.join(dirpath, file)) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif no_print is False:
                            if origpath == os.curdir or relative:
                                print("\"" + os.path.abspath(os.path.join(dirpath, file)) + "\" has been skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                elif (exclusions_dir and exclusions_file) is not None:
                    if os.path.isdir(os.path.join(dirpath, file)):
                        if current_system == "Windows" and \
                                re.search(".*(" + regex_excl_dirs + ")" + "(.*" + re.escape(os.path.sep) + "*.+|$)",
                                          os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif current_system != "Windows" and \
                                re.search(".*(" + regex_excl_dirs + ")" + "(.*" + re.escape(os.path.sep) + "*.+|$)",
                                          os.path.join(dirpath, file)) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif no_print is False:
                            if origpath == os.curdir or relative:
                                print("\"" + os.path.abspath(os.path.join(dirpath, file)) + "\" has been skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                    else:
                        if current_system == "Windows" and \
                                re.search(".*(" + regex_excl + ")([^" + re.escape(os.path.sep) + "]+$|$)",
                                          os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
                            if re.search(".*(" + regex_excl_dirs + ".*" + re.escape(os.path.sep) + ").*",
                                         os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
                                get_attrs(dirpath, file, file_attrs)
                        elif current_system != "Windows" and \
                                re.search(".*(" + regex_excl + ")([^" + re.escape(os.path.sep) + "]+$|$)",
                                          os.path.join(dirpath, file)) is None:
                            if re.search(".*(" + regex_excl_dirs + ".*" + re.escape(os.path.sep) + ").*",
                                         os.path.join(dirpath, file)) is None:
                                get_attrs(dirpath, file, file_attrs)
                        elif no_print is False:
                            if origpath == os.curdir or relative:
                                print("\"" + os.path.abspath(os.path.join(dirpath, file)) + "\" has been skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                elif (exclusions and exclusions_file and exclusions_dir) is None:
                    get_attrs(dirpath, file, file_attrs)
            except KeyboardInterrupt:
                try:
                    print("\nShutdown requested... dumping what could be collected and exiting\n")
                    return file_attrs
                except KeyboardInterrupt:
                    print("Cancelling and exiting...")
            except Exception as e:
                print("\n %s \n" % e)
                pass
    return file_attrs


def get_attrs(dirpath: str, file: str, file_attrs: dict):
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


def get_attr_for_restore(attr: dict, path: str) -> tuple[str, str, str, str, bool, bool, bool, bool] | \
                                                   tuple[str, str, str, bool, bool, bool, str, str, bool, bool]:
    atime = attr["atime"]
    mtime = attr["mtime"]
    if platform.system() == "Windows":
        ctime = attr["ctime"]
    else:
        uid = attr["uid"]
        gid = attr["gid"]
    mode = attr["mode"]

    current_file_info = os.lstat(path)
    mode_changed = current_file_info.st_mode != mode
    atime_changed = current_file_info.st_atime != atime
    mtime_changed = current_file_info.st_mtime != mtime
    if platform.system() == "Windows":
        ctime_changed = current_file_info.st_ctime != ctime
    else:
        uid_changed = current_file_info.st_uid != uid
        gid_changed = current_file_info.st_gid != gid

    if platform.system() == "Windows":
        return atime, mtime, ctime, mode, mode_changed, atime_changed, mtime_changed, ctime_changed
    else:
        return atime, mtime, mode, mode_changed, atime_changed, mtime_changed, uid, gid, uid_changed, gid_changed


def apply_file_attrs(attrs: dict, no_print: bool, c_to_a: bool, ignore_fs: bool):
    proc = 0
    errored = []  # to store errored files/folders

    msg_uid_gid = "Updating UID, GID for \"%s\""
    msg_permissions = "Updating permissions for \"%s\""
    msg_3_dates = "Updating dates for \"%s\""
    msg_2_dates = "Updating mtime or atime for \"%s\""
    msg_copy_create = "Copying dates for \"%s\""

    for path in sorted(attrs):
        attr = attrs[path]
        try:
            if os.path.lexists(path):
                if not os.path.islink(path):
                    if platform.system() == "Windows":
                        atime, mtime, ctime, mode, mode_changed, atime_changed, mtime_changed, ctime_changed = \
                            get_attr_for_restore(attr, path)
                    else:
                        atime, mtime, mode, mode_changed, atime_changed, mtime_changed, uid, gid, uid_changed, \
                            gid_changed = get_attr_for_restore(attr, path)

                    if platform.system() != "Windows" and (uid_changed or gid_changed):
                        if no_print is False:
                            if os.path.splitdrive(path)[0] == "":
                                print(msg_uid_gid % os.path.abspath(path))
                            else:
                                print(msg_uid_gid % path)
                        os.chown(path, uid, gid)
                        proc = 1

                    if mode_changed:
                        if no_print is False:
                            if os.path.splitdrive(path)[0] == "":
                                print(msg_permissions % os.path.abspath(path))
                            else:
                                print(msg_permissions % path)
                        os.chmod(path, mode)
                        proc = 1

                    if platform.system() == "Windows" and ignore_fs is False:
                        if mtime_changed or ctime_changed or atime_changed:
                            if no_print is False:
                                if os.path.splitdrive(path)[0] == "":
                                    print(msg_3_dates % os.path.abspath(path))
                                else:
                                    print(msg_3_dates % path)
                            os.utime(path, (atime, mtime))
                            setctime(path, ctime)
                            proc = 1
                    else:
                        if mtime_changed or atime_changed:
                            if no_print is False:
                                if os.path.splitdrive(path)[0] == "":
                                    print(msg_2_dates % os.path.abspath(path))
                                else:
                                    print(msg_2_dates % path)
                            os.utime(path, (atime, mtime))
                            proc = 1
                    if c_to_a:
                        if no_print is False:
                            if os.path.splitdrive(path)[0] == "":
                                print(msg_copy_create % os.path.abspath(path))
                            else:
                                print(msg_copy_create % path)
                        os.utime(path, (ctime, mtime))
                else:
                    if os.utime in os.supports_follow_symlinks:
                        if platform.system() == "Windows":
                            atime, mtime, ctime, mode, mode_changed, atime_changed, mtime_changed, ctime_changed = \
                                get_attr_for_restore(attr, path)
                        else:
                            atime, mtime, mode, mode_changed, atime_changed, mtime_changed, uid, gid, uid_changed, \
                                gid_changed = get_attr_for_restore(attr, path)

                        if platform.system() != "Windows" and (uid_changed or gid_changed):
                            if no_print is False:
                                if os.path.splitdrive(path)[0] == "":
                                    print(msg_uid_gid % os.path.abspath(path))
                                else:
                                    print(msg_uid_gid % path)
                            os.chown(path, uid, gid, follow_symlinks=False)
                            proc = 1

                        if mode_changed:
                            if no_print is False:
                                if os.path.splitdrive(path)[0] == "":
                                    print(msg_permissions % os.path.abspath(path))
                                else:
                                    print(msg_permissions % path)
                            os.chmod(path, mode, follow_symlinks=False)
                            proc = 1

                        if platform.system() == "Windows" and ignore_fs is False:
                            if mtime_changed or ctime_changed or atime_changed:
                                if no_print is False:
                                    if os.path.splitdrive(path)[0] == "":
                                        print(msg_3_dates % os.path.abspath(path))
                                    else:
                                        print(msg_3_dates % path)
                                os.utime(path, (atime, mtime), follow_symlinks=False)
                                setctime(path, ctime, follow_symlinks=False)
                                proc = 1
                        else:
                            if mtime_changed or atime_changed:
                                if no_print is False:
                                    if os.path.splitdrive(path)[0] == "":
                                        print(msg_2_dates % os.path.abspath(path))
                                    else:
                                        print(msg_2_dates % path)
                                os.utime(path, (atime, mtime), follow_symlinks=False)
                                proc = 1
                        if c_to_a:
                            if no_print is False:
                                if os.path.splitdrive(path)[0] == "":
                                    print(msg_copy_create % os.path.abspath(path))
                                else:
                                    print(msg_copy_create % path)
                            os.utime(path, (ctime, mtime), follow_symlinks=False)
                    elif no_print is False:
                        if os.path.splitdrive(path)[0] == "":
                            print("Skipping symbolic link \"%s\"" % os.path.abspath(path))  # Python doesn't support
                            # not following symlinks in this OS so we skip them
                        else:
                            print("Skipping symbolic link \"%s\"" % path)  # Python doesn't support  not following
                            # symlinks in this OS so we skip them
            elif no_print is False:
                if os.path.splitdrive(path)[0] == "":
                    print("Skipping non-existent item \"%s\"" % os.path.abspath(path))
                else:
                    print("Skipping non-existent item \"%s\"" % path)
        except OSError as Err:
            print("\n%s\n" % Err, file=sys.stderr)
            if os.path.splitdrive(path)[0] == "":
                errored.append(os.path.abspath(path))
            else:
                errored.append(path)
            pass
    if len(errored) != 0:
        print("\nErrored files/folders:\n")
        for line in errored:
            print(line + "\n")
        print("\nThere were %s errors while restoring the attributes." % len(errored))
        sys.exit(1)
    elif proc == 0:
        print("Nothing to change.")
        sys.exit(0)


def save_attrs(path_to_save: str, output: str, relative: bool, exclusions: list | None, exclusions_file: list | None,
               exclusions_dir: list | None, no_print: bool):
    if path_to_save.endswith('"'):
        path_to_save = path_to_save[:-1] + os.path.sep  # Windows escapes the quote if the command ends in \" so this
        # fixes that, or at least it does if this argument is the last one, otherwise the output argument will eat
        # all the next args
    if path_to_save.endswith(':'):
        path_to_save = path_to_save + os.path.sep
    if os.path.exists(path_to_save) is False:
        print("\nERROR: The specified path:\n\n%s\n\nDoesn't exist, aborting..." % path_to_save, file=sys.stderr)
        sys.exit(1)

    has_drive = os.path.splitdrive(output)[0]
    if has_drive != "" and os.path.exists(has_drive) is False:
        print("\nERROR: The specified drive:\n\n%s\n\nDoesn't exist, aborting..." % output, file=sys.stderr)
        sys.exit(1)

    attr_file_name = output
    if attr_file_name.endswith('"'):
        attr_file_name = attr_file_name[:-1]  # Windows escapes the quote if the command ends in \" so this fixes
        # that, or at least it does if this argument is the last one, otherwise the output argument will eat all the
        # following args

    if attr_file_name.endswith(':'):
        attr_file_name = attr_file_name + os.path.sep

    if os.path.basename(attr_file_name) != "" and os.path.isdir(attr_file_name):
        print("ERROR: The output filename you specified is the same one of a directory, a directory and a file "
              "with the same name can't exist within the same path, aborting...")
        sys.exit(1)

    if os.path.dirname(attr_file_name) != "":  # if the root directory of attr_file_name is not an empty string
        if os.path.isfile(os.path.dirname(attr_file_name)):
            print("ERROR: The output directory name you specified is the same one of a file, a directory and a file "
                  "with the same name can't exist within the same path, aborting...")
            sys.exit(1)
        if os.path.exists(os.path.dirname(attr_file_name)) is False:  # if the path of the root directory of
            # attr_file_name doesn't exist
            os.makedirs(os.path.dirname(attr_file_name))  # create the path
    else:
        if os.path.isdir(os.path.join(os.getcwd(), attr_file_name)):
            print("ERROR: The output filename you specified is the same one of a directory, a directory and a file "
                  "with the same name can't exist within the same path, aborting...")
            sys.exit(1)

    if os.path.basename(attr_file_name) == "":
        attr_file_name = os.path.join(attr_file_name, ".saved-file-attrs")

    reqstate = [relative,
                path_to_save != os.curdir,
                os.path.dirname(attr_file_name) == ""
                ]

    origpath = path_to_save
    if reqstate[0] & reqstate[1]:
        origdir = os.getcwd()
    if all(reqstate):
        attr_file_name = os.path.join(os.getcwd(), attr_file_name)
    if reqstate[0] & reqstate[1]:
        os.chdir(path_to_save)
        path_to_save = os.curdir

    try:
        attr_file = open(attr_file_name, "w", encoding="utf-8", errors="surrogatepass")
        attrs = collect_file_attrs(path_to_save, exclusions, origpath, relative, exclusions_file, exclusions_dir,
                                   no_print)
        json.dump(attrs, attr_file, indent=2, ensure_ascii=False)
        if os.path.splitdrive(attr_file_name)[0] == "":
            attr_file_name = os.path.join(os.getcwd(), attr_file_name)
        print("\nAttributes saved to \"" + attr_file_name + "\"")
    except KeyboardInterrupt:
        if "origdir" in locals():
            os.chdir(origdir)
        print("Shutdown requested... exiting", file=sys.stderr)
        sys.exit(1)
    except OSError as ERR_W:
        if "origdir" in locals():
            os.chdir(origdir)
        print("ERROR: There was an error writing to the attribute file.\n\n", ERR_W, file=sys.stderr)
        sys.exit(1)

    if reqstate[0] & reqstate[1]:
        os.chdir(origdir)


def restore_attrs(input_file: str, working_path: str, no_print: bool, c_to_a: bool, ignore_fs: bool):
    attr_file_name = input_file

    if attr_file_name.endswith('"'):
        attr_file_name = attr_file_name[:-1] + os.path.sep  # Windows escapes the quote if the command ends in \" so
        # this fixes that
    if os.path.basename(attr_file_name) == "":
        attr_file_name = os.path.join(attr_file_name, ".saved-file-attrs")
    if not os.path.exists(attr_file_name):
        print("ERROR: Saved attributes file \"%s\" not found" % attr_file_name, file=sys.stderr)
        sys.exit(1)
    if os.path.isdir(attr_file_name):
        print("ERROR: You have specified a directory for the input file, aborting...")
        sys.exit(1)

    attr_file_size = os.path.getsize(attr_file_name)

    if attr_file_size == 0:
        print("ERROR: The attribute file is empty!", file=sys.stderr)
        sys.exit(1)
    try:
        attr_file = open(attr_file_name, "r", encoding="utf-8", errors="surrogatepass")
        attrs = json.load(attr_file)
        if len(attrs) == 0:
            print("ERROR: The attribute file is empty!", file=sys.stderr)
            sys.exit(1)
        if working_path != os.curdir:
            os.chdir(working_path)
        apply_file_attrs(attrs, no_print, c_to_a, ignore_fs)
    except KeyboardInterrupt:
        print("Shutdown requested... exiting", file=sys.stderr)
        sys.exit(1)
    except OSError as ERR_R:
        print("ERROR: There was an error reading the attribute file, no attribute has been changed.\n\n%s\n" % ERR_R,
              file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Save and restore file attributes in a directory tree")
    parser.add_argument("--version", "-version", action="version",
                        version='%(prog)s v{version}'.format(version=__version__))
    subparsers = parser.add_subparsers(dest="mode", help="Select the mode of operation")
    save_parser = subparsers.add_parser(
        "save", help="Save the attributes of files and folders in a directory tree"
    )
    save_parser.add_argument("-o", "--o", help="Set the output file (Optional, "
                                               "default is \".saved-file-attrs\" in current dir)",
                             metavar="%OUTPUT%", default=".saved-file-attrs", nargs="?")
    save_parser.add_argument("-p", "--p", help="Set the path to store attributes from (Optional, "
                                               "default is current path)",
                             metavar="%PATH%", default=os.curdir, nargs="?")
    save_parser.add_argument("-ex", "--ex", help="Match these strings indiscriminately and exclude them, program will "
                                                 "exclude anything that includes these strings in their paths unless a "
                                                 "full path is specified in which case it will be considered a "
                                                 "directory and everything inside will be excluded. (Optional)",
                             metavar="%NAME%", nargs="*")
    save_parser.add_argument("-ef", "--ef", help="Match all the paths that incorporates these strings and exclude "
                                                 "them, strings are considered filenames unless a full path is given "
                                                 "in which case only that file will be excluded. If the argument is "
                                                 "given without any value, all the files will be excluded. (Optional)",
                             metavar="%FILE%", nargs="*")
    save_parser.add_argument("-ed", "--ed", help="Match all the paths that incorporates these strings and exclude "
                                                 "them, strings are considered directories unless a full path is "
                                                 "given in which case it will exclude all the sub directories and "
                                                 "files inside that directory. (Optional)",
                             metavar="%DIRECTORY%", nargs="*")
    save_parser.add_argument("-r", "--r", help="Store the paths as relative instead of full (Optional)",
                             action="store_true")
    save_parser.add_argument("-np", "--np", help="Don't print excluded files and folders (Optional)",
                             action="store_true")
    restore_parser = subparsers.add_parser(
        "restore", help="Restore saved file and folder attributes"
    )
    restore_parser.add_argument("-i", "--i", help="Set the input file containing the attributes to restore (Optional, "
                                                  "default is \".saved-file-attrs\" in current dir)",
                                metavar="%INPUT%", default=".saved-file-attrs", nargs="?")
    restore_parser.add_argument("-wp", "--wp", help="Set the working path, the attributes will be applied to the "
                                                    "contents of this path (Optional, default is the current "
                                                    "directory)",
                                metavar="%PATH%", default=os.curdir, nargs="?")
    restore_parser.add_argument("-np", "--np", help="Don't print modified or skipped files and folders (Optional)",
                                action="store_true")
    restore_parser.add_argument("-cta", "--cta", help="Copy the creation dates to accessed dates (Optional)",
                                action="store_true")
    restore_parser.add_argument("-ifs", "--ifs", help="Ignore filesystem and don't modify creation dates, useful when "
                                                      "working with non-NTFS network shares in Windows (Optional)",
                                action="store_true")
    args = parser.parse_args()

    if args.mode == "save":
        if args.ex is not None and (args.ef or args.ed) is not None:
            print("ERROR: You can't use --ex with --ef or --ed, you should use --ef and --ed or use only one of them",
                  file=sys.stderr)
            sys.exit(3)
        if args.ed is not None and (len(args.ed) == 0 or "" in args.ed):
            print("ERROR: Directory exclusion can't be empty or have an empty value or else everything will be "
                  "excluded, aborting...",
                  file=sys.stderr)
            sys.exit(3)
        if args.ex is not None and (len(args.ex) == 0 or "" in args.ex):
            print("ERROR: Exclusion can't be empty or have an empty value or else everything will be excluded, "
                  "aborting...",
                  file=sys.stderr)
            sys.exit(3)
        if args.ef is not None and (len(args.ef) == 0 or "" in args.ef):
            print("\nWARNING: You have used an empty value for file exclusions, every file will be excluded.\n")
        save_attrs(args.p, args.o, args.r, args.ex, args.ef, args.ed, args.np)
    elif args.mode == "restore":
        restore_attrs(args.i, args.wp, args.np, args.cta, args.ifs)
    elif args.mode is None:
        print("You have to use either save or restore.\nSee the help.")
        sys.exit(3)


if __name__ == "__main__":
    main()
