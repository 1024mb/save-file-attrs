#!/usr/bin/env python

"""
Save and restore modified, accessed and created times, owners and mode for all files in a tree.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import re
import stat
import sys
from dataclasses import dataclass
from string import Template
from typing import Optional, List

from version import __version__

SYSTEM_PLATFORM = platform.system()

if SYSTEM_PLATFORM == "Windows":
    from win32_setctime import setctime

DEFAULT_ATTR_FILENAME = ".saved-file-attrs"


@dataclass
class ResultAttr:
    atime: float = 0
    mtime: float = 0
    ctime: float = 0
    mode: int = 0
    uid: int = 0
    gid: int = 0
    archive: int = 0
    hidden: int = 0
    readonly: int = 0
    system: int = 0
    mode_changed: bool = False
    atime_changed: bool = False
    mtime_changed: bool = False
    ctime_changed: bool = False
    uid_changed: bool = False
    gid_changed: bool = False
    archive_changed: bool = False
    readonly_changed: bool = False
    system_changed: bool = False
    hidden_changed: bool = False


def collect_file_attrs(working_path: str,
                       orig_working_path: str,
                       relative: bool,
                       exclusions: list,
                       exclusions_file: list,
                       exclusions_dir: list,
                       no_print: bool) -> dict:
    """
        :param working_path: Path where the attributes will be saved from.
            If relative is set to true then this should be a current dir pointer (commonly a dot ".")
        :param orig_working_path: Original path where the attributes will be save from
        :param relative: Whether to store the paths as relatives to the root drive
        :param exclusions: List of items to exclude
        :param exclusions_file: List of files to exclude
        :param exclusions_dir: List of directories to exclude
        :param no_print: Whether to print not found / skipped symlinks messages
    """

    print("\nCollecting attributes, please wait...", end="\n\n")

    curr_working_dir = re.escape(os.getcwd())

    if relative is False and orig_working_path == ".":
        dirs = os.walk(os.getcwd())
    else:
        dirs = os.walk(working_path)

    file_attrs = {}
    exclusions2 = []  # this is for exclusions that are full paths, so we can store the root directory

    # exclusions setup start
    regex_orig_working_path = None  # so I don't get annoyed by the IDE
    if orig_working_path != os.curdir:  # this doesn't indicate whether relative has been set because this also
        # applies if
        # --working-path hasn't been used
        regex_orig_working_path = re.escape(orig_working_path)  # path ready for regex
    if relative is False:  # all paths will be saved as full
        if exclusions is not None:
            exclusions, exclusions2, regex_excl = prepare_exclusions(exclusions=exclusions,
                                                                     exclusions2=exclusions2,
                                                                     orig_working_path=orig_working_path,
                                                                     regex_orig_working_path=regex_orig_working_path,
                                                                     curr_working_dir=curr_working_dir)
        if exclusions_file is not None:
            if orig_working_path != os.curdir:
                for i, s in enumerate(exclusions_file):
                    a = os.path.splitdrive(s)
                    if s.startswith(os.curdir + os.path.sep):
                        r = os.path.normpath(os.path.join(orig_working_path, s))
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
            if orig_working_path != os.curdir:
                for i, s in enumerate(exclusions_dir):
                    if s.startswith(os.curdir + os.path.sep):
                        r = os.path.normpath(os.path.join(orig_working_path, s))
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
                    if SYSTEM_PLATFORM == "Windows" and \
                            re.search(f".*({regex_excl}).*", os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
                        get_attrs(dirpath, file, file_attrs)
                    elif SYSTEM_PLATFORM != "Windows" and \
                            re.search(".*(" + regex_excl + ").*", os.path.join(dirpath, file)) is None:
                        get_attrs(dirpath, file, file_attrs)
                    elif not no_print:
                        if orig_working_path == os.curdir or relative:
                            print("\"" + os.path.abspath(os.path.join(dirpath, file)) + "\" has been skipped.")
                        else:
                            print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                if exclusions_file is not None and exclusions_dir is None:
                    if os.path.isfile(os.path.join(dirpath, file)):
                        if SYSTEM_PLATFORM == "Windows" and \
                                re.search(".*(" + regex_excl + ")([^" + re.escape(os.path.sep) + "]+$|$)",
                                          os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif SYSTEM_PLATFORM != "Windows" and \
                                re.search(".*(" + regex_excl + ")([^" + re.escape(os.path.sep) + "]+$|$)",
                                          os.path.join(dirpath, file)) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif not no_print:
                            if orig_working_path == os.curdir or relative:
                                print("\"" + os.path.abspath(os.path.join(dirpath, file)) + "\" has been skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                    else:
                        get_attrs(dirpath, file, file_attrs)
                elif exclusions_dir is not None and exclusions_file is None:
                    if os.path.isdir(os.path.join(dirpath, file)):
                        if current_system == "Windows" and \
                                re.search(".*(" + regex_excl_dirs + ")" + "(.*" + re.escape(os.path.sep) + "*.+|$)",
                        if SYSTEM_PLATFORM == "Windows" and \
                                re.search(".*(" + regex_excl_dirs + ")" + "(.*" + re.escape(os.path.sep) + "*.*|$)",
                                          os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif SYSTEM_PLATFORM != "Windows" and \
                                re.search(".*(" + regex_excl_dirs + ")" + "(.*" + re.escape(os.path.sep) + "*.+|$)",
                                          os.path.join(dirpath, file)) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif not no_print:
                            if orig_working_path == os.curdir or relative:
                                print("\"" + os.path.abspath(os.path.join(dirpath, file)) + "\" has been skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                    else:  # if is a file
                        if SYSTEM_PLATFORM == "Windows" and \
                                re.search(".*(" + regex_excl_dirs + ".*" + re.escape(os.path.sep) + ").*",
                                          os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif SYSTEM_PLATFORM != "Windows" and \
                                re.search(".*(" + regex_excl_dirs + ".*" + re.escape(os.path.sep) + ").*",
                                          os.path.join(dirpath, file)) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif not no_print:
                            if orig_working_path == os.curdir or relative:
                                print("\"" + os.path.abspath(os.path.join(dirpath, file)) + "\" has been skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                elif (exclusions_dir and exclusions_file) is not None:
                    if os.path.isdir(os.path.join(dirpath, file)):
                        if SYSTEM_PLATFORM == "Windows" and \
                                re.search(".*(" + regex_excl_dirs + ")" + "(.*" + re.escape(os.path.sep) + "*.+|$)",
                                          os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif SYSTEM_PLATFORM != "Windows" and \
                                re.search(".*(" + regex_excl_dirs + ")" + "(.*" + re.escape(os.path.sep) + "*.+|$)",
                                          os.path.join(dirpath, file)) is None:
                            get_attrs(dirpath, file, file_attrs)
                        elif not no_print:
                            if orig_working_path == os.curdir or relative:
                                print("\"" + os.path.abspath(os.path.join(dirpath, file)) + "\" has been skipped.")
                            else:
                                print("\"" + os.path.join(dirpath, file) + "\" has been skipped.")
                    else:
                        if SYSTEM_PLATFORM == "Windows" and \
                                re.search(".*(" + regex_excl + ")([^" + re.escape(os.path.sep) + "]+$|$)",
                                          os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
                            if re.search(".*(" + regex_excl_dirs + ".*" + re.escape(os.path.sep) + ").*",
                                         os.path.join(dirpath, file), flags=re.IGNORECASE) is None:
                                get_attrs(dirpath, file, file_attrs)
                        elif SYSTEM_PLATFORM != "Windows" and \
                                re.search(".*(" + regex_excl + ")([^" + re.escape(os.path.sep) + "]+$|$)",
                                          os.path.join(dirpath, file)) is None:
                            if re.search(".*(" + regex_excl_dirs + ".*" + re.escape(os.path.sep) + ").*",
                                         os.path.join(dirpath, file)) is None:
                                get_attrs(dirpath, file, file_attrs)
                        elif not no_print:
                            if orig_working_path == os.curdir or relative:
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
                print(f"\n{e}", end="\n\n")
                pass
    return file_attrs


def prepare_exclusions(exclusions: list,
                       exclusions2: list,
                       orig_working_path: str,
                       regex_orig_working_path: str,
                       curr_working_dir: str) -> tuple[list, list, str]:
    if orig_working_path != os.curdir:  # if origpath has a value other than .
        for i, exclusion in enumerate(exclusions):
            if exclusion.startswith(os.curdir + os.path.sep):
                normalized_path = os.path.normpath(os.path.join(orig_working_path, exclusion))
                exclusions[i] = re.escape(normalized_path)
            elif SYSTEM_PLATFORM == "Windows":
                if re.match(regex_orig_working_path, exclusion, flags=re.IGNORECASE) is not None:
                    normalized_path = exclusion + os.path.sep  # adding a slash to the end of the path because the
                    # string is a directory, or at least that's how we consider it always when using --ex and the
                    # exclusion's path contains the working path
                    exclusions[i] = re.escape(exclusion)
                    exclusions2.append(normalized_path)
            elif exclusion.startswith(orig_working_path):
                normalized_path = exclusion + os.path.sep  # adding a slash to the end of the path because the string
                # is a
                # directory, or at least that's how we consider it always when using --ex
                exclusions[i] = re.escape(exclusion)
                exclusions2.append(normalized_path)
            else:
                exclusions[i] = re.escape(exclusion)
    else:  # if is os.curdir
        for i, exclusion in enumerate(exclusions):
            if exclusion.startswith(os.curdir + os.path.sep):
                normalized_path = os.path.abspath(exclusion)
                exclusions[i] = re.escape(normalized_path)
            elif ((SYSTEM_PLATFORM == "Windows" and re.match(curr_working_dir,
                                                             exclusion,
                                                             flags=re.IGNORECASE) is not None) or
                  (SYSTEM_PLATFORM != "Windows" and exclusion.startswith(curr_working_dir))):
                normalized_path = exclusion + os.path.sep  # adding a slash to the end of the path because the string
                # is a
                # directory, or at least that's how we consider it always when using --ex
                exclusions[i] = re.escape(exclusion)
                exclusions2.append(re.escape(normalized_path))
            else:
                exclusions[i] = re.escape(exclusion)
    if len(exclusions2) != 0:
        regex_excl = "|".join(exclusions) + "|" + "|".join(exclusions2)
    else:
        regex_excl = "|".join(exclusions)

    return exclusions, exclusions2, regex_excl


def get_attrs(dirpath: str,
              file: str,
              file_attrs: dict):
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

    if SYSTEM_PLATFORM == "Windows":
        import stat

        file_attrs[path]["archive"] = bool(file_info.st_file_attributes & stat.FILE_ATTRIBUTE_ARCHIVE)
        file_attrs[path]["hidden"] = bool(file_info.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
        file_attrs[path]["readonly"] = bool(file_info.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)
        file_attrs[path]["system"] = bool(file_info.st_file_attributes & stat.FILE_ATTRIBUTE_SYSTEM)


def get_attr_for_restore(attr: dict,
                         path: str) -> ResultAttr:
    stored_data = ResultAttr()

    stored_data.atime = attr["atime"]
    stored_data.mtime = attr["mtime"]
    if SYSTEM_PLATFORM == "Windows":
        stored_data.ctime = attr["ctime"]
        stored_data.archive = attr["archive"]
        stored_data.hidden = attr["hidden"]
        stored_data.readonly = attr["readonly"]
        stored_data.system = attr["system"]
    else:
        stored_data.uid = attr["uid"]
        stored_data.gid = attr["gid"]
        stored_data.mode = attr["mode"]

    current_file_info = os.lstat(path)
    stored_data.mode_changed = current_file_info.st_mode != stored_data.mode
    stored_data.atime_changed = current_file_info.st_atime != stored_data.atime
    stored_data.mtime_changed = current_file_info.st_mtime != stored_data.mtime
    if SYSTEM_PLATFORM == "Windows":
        import stat
        cur_archive = bool(current_file_info.st_file_attributes & stat.FILE_ATTRIBUTE_ARCHIVE)
        cur_hidden = bool(current_file_info.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
        cur_readonly = bool(current_file_info.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)
        cur_system = bool(current_file_info.st_file_attributes & stat.FILE_ATTRIBUTE_SYSTEM)

        stored_data.archive_changed = cur_archive != stored_data.archive
        stored_data.hidden_changed = cur_hidden != stored_data.hidden
        stored_data.readonly_changed = cur_readonly != stored_data.readonly
        stored_data.system_changed = cur_system != stored_data.system

        stored_data.ctime_changed = current_file_info.st_ctime != stored_data.ctime

    else:
        stored_data.uid_changed = current_file_info.st_uid != stored_data.uid
        stored_data.gid_changed = current_file_info.st_gid != stored_data.gid

    return stored_data


def apply_file_attrs(attrs: dict,
                     no_print: bool,
                     c_to_a: bool,
                     ignore_fs: bool,
                     ignore_permissions: bool):
    proc = 0
    errored = []  # to store errored files/folders

    msg_uid_gid = "Updating UID, GID for \"%s\""
    msg_permissions = "Updating permissions for \"%s\""
    msg_3_dates = "Updating dates for \"%s\""
    msg_2_dates = "Updating mtime or atime for \"%s\""
    msg_copy_create = "Copying dates for \"%s\""
    msg_uid_gid = Template("Updating $changed_ids for \"$path\"")
    msg_permissions = Template("Updating permissions for \"$path\"")
    msg_dates = Template("Updating $dates timestamp(s) for \"$path\"")
    msg_win_attribs = Template("Updating $win_attribs attribute(s) for \"$path\"")

    for path in sorted(attrs):
        attr = attrs[path]
        path = os.path.abspath(path)
        try:
            if os.path.lexists(path):
                stored_data = get_attr_for_restore(attr, path)

                if not os.path.islink(path):
                    if SYSTEM_PLATFORM != "Windows":
                        changed_ids = []
                        if stored_data.uid_changed:
                            changed_ids.append("UID")
                        if stored_data.gid_changed:
                            changed_ids.append("GID")

                        if len(changed_ids) != 0:
                            if not no_print:
                                print(msg_uid_gid.substitute(path=path, changed_ids=" & ".join(changed_ids)))

                            os.chown(path, stored_data.uid, stored_data.gid)
                            proc = 1

                        # st_mode on Windows is pretty useless, so we only perform this if the current OS is not Windows
                        if stored_data.mode_changed and not ignore_permissions:
                            if not no_print:
                                print(msg_permissions.substitute(path=path))
                            os.chmod(path, stored_data.mode)
                            proc = 1

                    changed_times = []
                    if stored_data.mtime_changed:
                        changed_times.append("modification")
                    if stored_data.atime_changed:
                        changed_times.append("accessed")
                    if stored_data.ctime_changed:
                        changed_times.append("creation")

                    if len(changed_times) != 0:
                        if not no_print:
                            print(msg_dates.substitute(path=path, dates=" & ".join(changed_times)))

                        if stored_data.mtime_changed or stored_data.atime_changed:
                            os.utime(path, (stored_data.atime, stored_data.mtime))
                            proc = 1
                        if stored_data.ctime_changed and SYSTEM_PLATFORM == "Windows" and not ignore_fs:
                            setctime(path, stored_data.ctime)
                            proc = 1

                    if c_to_a and stored_data.ctime != stored_data.atime:
                        os.utime(path, (stored_data.ctime, stored_data.mtime))
                else:
                    if os.utime in os.supports_follow_symlinks:
                        if SYSTEM_PLATFORM != "Windows":
                            changed_ids = []
                            if stored_data.uid_changed:
                                changed_ids.append("UID")
                            if stored_data.gid_changed:
                                changed_ids.append("GID")

                            if len(changed_ids) != 0:
                                if not no_print:
                                    print(msg_uid_gid.substitute(path=path, changed_ids=" & ".join(changed_ids)))

                                os.chown(path, stored_data.uid, stored_data.gid, follow_symlinks=False)
                                proc = 1

                            if stored_data.mode_changed and not ignore_permissions:
                                if not no_print:
                                    print(msg_permissions.substitute(path=path))
                                os.chmod(path, stored_data.mode, follow_symlinks=False)
                                proc = 1

                        changed_times = []
                        if stored_data.mtime_changed:
                            changed_times.append("modification")
                        if stored_data.atime_changed:
                            changed_times.append("accessed")
                        if stored_data.ctime_changed:
                            changed_times.append("creation")

                        if len(changed_times) != 0:
                            if not no_print:
                                print(msg_dates.substitute(path=path, dates=" & ".join(changed_times)))

                            if stored_data.mtime_changed or stored_data.atime_changed:
                                os.utime(path, (stored_data.atime, stored_data.mtime), follow_symlinks=False)
                                proc = 1
                            if stored_data.ctime_changed and SYSTEM_PLATFORM == "Windows" and not ignore_fs:
                                setctime(path, stored_data.ctime, follow_symlinks=False)
                                proc = 1

                        if c_to_a and stored_data.ctime != stored_data.atime:
                            os.utime(path, (stored_data.ctime, stored_data.mtime), follow_symlinks=False)
                    elif not no_print:
                        print(f"Skipping symbolic link \"{path}\"")  # Python doesn't support
                        # not following symlinks in this OS so we skip them

                # Can't set attributes for symbolic links in Windows from Python
                if SYSTEM_PLATFORM == "Windows" and not os.path.islink(path):
                    changed_win_attribs: List[str] = []
                    attribs_to_set: int = 0
                    attribs_to_unset: int = 0

                    if stored_data.archive_changed:
                        changed_win_attribs.append("ARCHIVE")
                        if stored_data.archive:
                            attribs_to_set |= stat.FILE_ATTRIBUTE_ARCHIVE
                        else:
                            attribs_to_unset |= stat.FILE_ATTRIBUTE_ARCHIVE

                    if stored_data.hidden_changed:
                        changed_win_attribs.append("HIDDEN")
                        if stored_data.hidden:
                            attribs_to_set |= stat.FILE_ATTRIBUTE_HIDDEN
                        else:
                            attribs_to_unset |= stat.FILE_ATTRIBUTE_HIDDEN

                    if stored_data.readonly_changed:
                        changed_win_attribs.append("READ-ONLY")
                        if stored_data.readonly:
                            attribs_to_set |= stat.FILE_ATTRIBUTE_READONLY
                        else:
                            attribs_to_unset |= stat.FILE_ATTRIBUTE_READONLY

                    if stored_data.system_changed:
                        changed_win_attribs.append("SYSTEM")
                        if stored_data.system:
                            attribs_to_set |= stat.FILE_ATTRIBUTE_SYSTEM
                        else:
                            attribs_to_unset |= stat.FILE_ATTRIBUTE_SYSTEM

                    if len(changed_win_attribs) != 0:
                        proc = 1
                        if not no_print:
                            print(msg_win_attribs.substitute(path=path,
                                                             win_attribs=" & ".join(changed_win_attribs)))

                        if not modify_win_attribs(path=path,
                                                  attribs_to_set=attribs_to_set,
                                                  attribs_to_unset=attribs_to_unset):
                            print(f"Error setting Windows attributes for \"{path}\"")
                            errored.append(path)
            elif not no_print:
                print(f"Skipping non-existent item \"{path}\"")
        except OSError as Err:
            print(f"\n{Err}", end="\n\n", file=sys.stderr)
            errored.append(path)

    if len(errored) != 0:
        print("\nErrored files/folders:\n")
        for line in errored:
            print(line + "\n")
        print(f"\nThere were {len(errored)} errors while restoring the attributes.")
        sys.exit(1)
    elif proc == 0:
        print("Nothing to change.")

    sys.exit(0)


def modify_win_attribs(path: str,
                       attribs_to_set: int,
                       attribs_to_unset: int) -> bool:
    current_attribs = get_win_attributes(path=path)

    win_attribs = current_attribs | attribs_to_set
    win_attribs &= ~attribs_to_unset

    return_code = set_win_attributes(path=path, win_attributes=win_attribs)

    if return_code == 1:
        return True
    else:
        return False


def get_win_attributes(path: str) -> int:
    return ctypes.windll.kernel32.GetFileAttributesW(path)


def set_win_attributes(path: str,
                       win_attributes: int) -> int:
    return ctypes.windll.kernel32.SetFileAttributesW(path, win_attributes)


def save_attrs(working_path: str,
               output_file: str,
               relative: bool,
               exclusions: Optional[list],
               exclusions_file: Optional[list],
               exclusions_dir: Optional[list],
               no_print: bool) -> None:
    """
    :param working_path: Path where the attributes will be saved from
    :param output_file: Path to the file where to save the attributes to
    :param relative: Whether to store the paths as relatives to the root drive
    :param exclusions: List of items to exclude
    :param exclusions_file: List of files to exclude
    :param exclusions_dir: List of directories to exclude
    :param no_print: Whether to print not found / skipped symlinks messages
    """

    if working_path.endswith('"'):
        working_path = working_path[:-1] + os.path.sep  # Windows escapes the quote if the command ends in \" so this
        # fixes that, or at least it does if this argument is the last one, otherwise the output argument will eat
        # all the next args

    if working_path.endswith(':'):
        working_path += os.path.sep

    if not os.path.exists(working_path):
        print(f"\nERROR: The specified path:\n\n{working_path}\n\nDoesn't exist, aborting...", file=sys.stderr)
        sys.exit(1)

    has_drive = os.path.splitdrive(output_file)[0]
    if has_drive != "" and not os.path.exists(has_drive):
        print(f"\nERROR: The specified drive:\n\n{output_file}\n\nDoesn't exist, aborting...", file=sys.stderr)
        sys.exit(1)

    attr_file_name = output_file
    if attr_file_name.endswith('"'):
        attr_file_name = attr_file_name[:-1]  # Windows escapes the quote if the command ends in \" so this fixes
        # that, or at least it does if this argument is the last one, otherwise the output argument will eat all the
        # following args

    if attr_file_name.endswith(':'):
        attr_file_name += os.path.sep

    if os.path.basename(attr_file_name) != "" and os.path.isdir(attr_file_name):
        print("ERROR: The output filename you specified is the same one of a directory, a directory and a file "
              "with the same name can't exist within the same path, aborting...")
        sys.exit(1)

    if os.path.dirname(attr_file_name) != "":  # if the root directory of attr_file_name is not an empty string
        if os.path.isfile(os.path.dirname(attr_file_name)):
            print("ERROR: The output directory name you specified is the same one of a file, a directory and a file "
                  "with the same name can't exist within the same path, aborting...")
            sys.exit(1)

        os.makedirs(os.path.dirname(attr_file_name), exist_ok=True)
    else:
        if os.path.isdir(os.path.join(os.getcwd(), attr_file_name)):
            print("ERROR: The output filename you specified is the same one of a directory, a directory and a file "
                  "with the same name can't exist within the same path, aborting...")
            sys.exit(1)

    if os.path.basename(attr_file_name) == "":
        attr_file_name = os.path.join(attr_file_name, DEFAULT_ATTR_FILENAME)

    reqstate = [relative,
                working_path != os.curdir,
                os.path.dirname(attr_file_name) == ""]

    orig_working_path = working_path
    if all(reqstate):
        attr_file_name = os.path.join(os.getcwd(), attr_file_name)
    if reqstate[0] & reqstate[1]:
        os.chdir(working_path)
        working_path = os.curdir

    try:
        attr_file = open(attr_file_name, "w", encoding="utf-8", errors="surrogatepass")
        attrs = collect_file_attrs(working_path,
                                   orig_working_path,
                                   relative,
                                   exclusions,
                                   exclusions_file,
                                   exclusions_dir,
                                   no_print)
        json.dump(attrs, attr_file, indent=4, ensure_ascii=False)
        if os.path.splitdrive(attr_file_name)[0] == "":
            attr_file_name = os.path.join(os.getcwd(), attr_file_name)
        print(f"\nAttributes saved to \"{attr_file_name}\"")
    except KeyboardInterrupt:
        print("Shutdown requested... exiting", file=sys.stderr)
        sys.exit(1)
    except OSError as ERR_W:
        print("ERROR: There was an error writing to the attribute file.\n\n", ERR_W, file=sys.stderr)
        sys.exit(1)


def restore_attrs(input_file: str,
                  working_path: str,
                  no_print: bool,
                  c_to_a: bool,
                  ignore_fs: bool,
                  ignore_permissions: bool):
    attr_file_name = input_file

    if attr_file_name.endswith('"'):
        attr_file_name = attr_file_name[:-1] + os.path.sep  # Windows escapes the quote if the command ends in \" so
        # this fixes that
    if os.path.basename(attr_file_name) == "":
        attr_file_name = os.path.join(attr_file_name, DEFAULT_ATTR_FILENAME)
    if not os.path.exists(attr_file_name):
        print(f"ERROR: Saved attributes file \"{attr_file_name}\" not found", file=sys.stderr)
        sys.exit(1)
    if os.path.isdir(attr_file_name):
        print("ERROR: You have specified a directory for the input file, aborting...")
        sys.exit(1)

    attr_file_size = os.path.getsize(attr_file_name)

    if attr_file_size == 0:
        print("ERROR: The attribute file is empty!", file=sys.stderr)
        sys.exit(1)
    try:
        with open(attr_file_name, "r", encoding="utf-8", errors="backslashreplace") as attr_file:
            attrs = json.load(attr_file)
        if len(attrs) == 0:
            print("ERROR: The attribute file is empty!", file=sys.stderr)
            sys.exit(1)
        if working_path != os.curdir:
            os.chdir(working_path)
        apply_file_attrs(attrs, no_print, c_to_a, ignore_fs, ignore_permissions)
    except KeyboardInterrupt:
        print("Shutdown requested... exiting", file=sys.stderr)
        sys.exit(1)
    except OSError as ERR_R:
        print(f"ERROR: There was an error reading the attribute file, no attribute has been changed.\n\n{ERR_R}\n",
              file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Save and restore file attributes in a directory tree")
    parser.add_argument("--version", "-version",
                        action="version",
                        version=f"%(prog)s v{__version__}")
    subparsers = parser.add_subparsers(dest="mode",
                                       help="Select the mode of operation")

    save_parser = subparsers.add_parser("save",
                                        help="Save the attributes of files and folders in a directory tree")
    save_parser.add_argument("-o", "--output",
                             help="Set the output file (Optional, default is \".saved-file-attrs\" in current dir)",
                             metavar="%OUTPUT%",
                             default=DEFAULT_ATTR_FILENAME,
                             nargs="?")
    save_parser.add_argument("-p", "--working-path",
                             help="Set the path to store attributes from (Optional, default is current path)",
                             metavar="%PATH%",
                             default=os.curdir,
                             nargs="?")
    save_parser.add_argument("-ex", "--exclude",
                             help="Match these strings indiscriminately and exclude them, program will exclude "
                                  "anything that includes these strings in their paths unless a full path is "
                                  "specified in which case it will be considered a directory and everything inside "
                                  "will be excluded. (Optional)",
                             metavar="%NAME%",
                             nargs="*")
    save_parser.add_argument("-ef", "--exclude-file",
                             help="Match all the paths that incorporates these strings and exclude them, strings are "
                                  "considered filenames unless a full path is given in which case only that file will "
                                  "be excluded. If the argument is given without any value, all the files will be "
                                  "excluded. (Optional)",
                             metavar="%FILE%",
                             nargs="*")
    save_parser.add_argument("-ed", "--exclude-dir",
                             help="Match all the paths that incorporates these strings and exclude them, strings are "
                                  "considered directories unless a full path is given in which case it will exclude "
                                  "all the sub directories and files inside that directory. (Optional)",
                             metavar="%DIRECTORY%",
                             nargs="*")
    save_parser.add_argument("-r", "--relative",
                             help="Store the paths as relative instead of full (Optional)",
                             action="store_true")
    save_parser.add_argument("-np", "--no-print",
                             help="Don't print excluded files and folders (Optional)",
                             action="store_true")

    restore_parser = subparsers.add_parser("restore",
                                           help="Restore saved file and folder attributes")
    restore_parser.add_argument("-i", "--input",
                                help="Set the input file containing the attributes to restore (Optional, default is "
                                     "\".saved-file-attrs\" in current dir)",
                                metavar="%INPUT%",
                                default=DEFAULT_ATTR_FILENAME,
                                nargs="?")
    restore_parser.add_argument("-wp", "--working-path",
                                help="Set the working path, the attributes will be applied to the contents of this "
                                     "path (Optional, default is the current directory)",
                                metavar="%PATH%",
                                default=os.curdir,
                                nargs="?")
    restore_parser.add_argument("-np", "--no-print",
                                help="Don't print modified or skipped files and folders (Optional)",
                                action="store_true")
    restore_parser.add_argument("-cta", "--copy-to-access",
                                help="Copy the creation dates to accessed dates (Optional)",
                                action="store_true")
    restore_parser.add_argument("-ifs", "--ignore-filesystem",
                                help="Ignore filesystem and don't modify creation dates (Optional)",
                                action="store_true")
    restore_parser.add_argument("-ip", "--ignore-permissions",
                                help="Ignore permissions change (Optional)",
                                action="store_true")
    args = parser.parse_args()

    # Set args variables

    mode = args.mode

    if mode == "save":
        output_file = args.output  # type: str
        exclude = args.exclude  # type: Optional[list]
        exclude_file = args.exclude_file  # type: Optional[list]
        exclude_dir = args.exclude_dir  # type: Optional[list]
        relative = args.relative  # type: bool

    if mode == "restore":
        input_file = args.input  # type: str
        copy_to_access = args.copy_to_access  # type: bool
        ignore_filesystem = args.ignore_filesystem  # type: bool
        ignore_permissions = args.ignore_permissions  # type: bool

    working_path = args.working_path  # type: str
    no_print = args.no_print  # type: bool

    if mode == "save":
        if exclude is not None and (exclude_file is not None or exclude_dir is not None):
            print("ERROR: You can't use --exclude with --exclude-file or --exclude-dir, you should use --exclude-file "
                  "and --exclude-dir or use only one of them",
                  file=sys.stderr)
            sys.exit(3)

        if exclude_dir is not None and (len(exclude_dir) == 0 or "" in exclude_dir):
            print("ERROR: Directory exclusion can't be empty or have an empty value or else everything will be "
                  "excluded, aborting...",
                  file=sys.stderr)
            sys.exit(3)

        if exclude is not None and (len(exclude) == 0 or "" in exclude):
            print("ERROR: Exclusion can't be empty or have an empty value or else everything will be excluded, "
                  "aborting...",
                  file=sys.stderr)
            sys.exit(3)

        if exclude_file is not None and (len(exclude_file) == 0 or "" in exclude_file):
            print("\nWARNING: You have used an empty value for file exclusions, every file will be excluded.\n")

        save_attrs(working_path, output_file, relative, exclude, exclude_file, exclude_dir, no_print)
    elif mode == "restore":
        restore_attrs(input_file, working_path, no_print, copy_to_access, ignore_filesystem, ignore_permissions)
    elif mode is None:
        print("You have to use either save or restore.\nRead the help.")
        sys.exit(3)


if __name__ == "__main__":
    main()
