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
import sys
from dataclasses import dataclass
from string import Template
from typing import Optional, List, Iterator, Tuple, Dict

from pathspec import PathSpec

from version import __version__

SYSTEM_PLATFORM = platform.system()

if SYSTEM_PLATFORM == "Windows":
    import stat
    from win32_setctime import setctime

DEFAULT_ATTR_FILENAME = ".saved-file-attrs"


@dataclass
class ResultAttr:
    atime: int | float = 0
    mtime: int | float = 0
    ctime: int | float = 0
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
                       exclusions: Optional[List[str]],
                       exclusions_file: Optional[List[str]],
                       no_print: bool,
                       exclusions_ignore_case: bool) -> dict:
    """
        :param working_path: Path where the attributes will be saved from.
            If relative is set to true, then this should be a current dir pointer (commonly a dot ".")
        :param orig_working_path: Original path where the attributes will be saved from
        :param relative: Whether to store the paths as relatives to the root drive
        :param exclusions: List of pattern rules to exclude.
        :param exclusions_file: List of paths of ignore-files.
        :param no_print: Whether to print not found / skipping messages.
        :param exclusions_ignore_case: Ignore casing with exclusion rules.
    """

    print("\nCollecting attributes, please wait...", end="\n\n")

    if relative is False and orig_working_path == ".":
        dirs: Iterator[Tuple[str, list, list]] = os.walk(os.getcwd())
    else:
        dirs = os.walk(working_path)

    file_attrs: Dict[str, dict] = {}

    compiled_rules: Optional[PathSpec] = compile_ignore_rules(exclusions_file=exclusions_file,
                                                              exclusions=exclusions,
                                                              exclusions_ignore_case=exclusions_ignore_case)

    for (dir_path, dir_names, filenames) in dirs:
        items = dir_names + filenames
        for item in items:
            item_path = os.path.join(dir_path, item)
            item_path_orig = item_path
            try:
                if compiled_rules is not None:
                    if exclusions_ignore_case:
                        item_path = item_path.lower()
                    if compiled_rules.match_file(item_path):
                        if not no_print:
                            if orig_working_path == os.curdir or relative:
                                print(f"Skipping excluded path \"{os.path.abspath(item_path_orig)}\"")
                            else:
                                print(f"Skipping excluded path \"{item_path_orig}\"")
                        continue

                get_attrs(item_path_orig, file_attrs)
            except KeyboardInterrupt:
                try:
                    print("\nShutdown requested... dumping what could be collected and exiting\n")
                    return file_attrs
                except KeyboardInterrupt:
                    print("Cancelling and exiting...")
            except Exception as e:
                print(f"\n{e}", end="\n\n")

    return file_attrs


def compile_ignore_rules(exclusions_file: Optional[List[str]],
                         exclusions: Optional[List[str]],
                         exclusions_ignore_case: bool) -> Optional[PathSpec]:
    pattern_rules = []

    if exclusions_file is not None:
        for ignore_file in exclusions_file:
            with open(ignore_file, "r", encoding="utf8", errors="backslashreplace") as stream:
                if exclusions_ignore_case:
                    pattern_rules += [pattern.lower() for pattern in stream.read().splitlines()]
                else:
                    pattern_rules += stream.read().splitlines()

    if exclusions is not None:
        if exclusions_ignore_case:
            exclusions = [pattern.lower() for pattern in exclusions]
        pattern_rules += exclusions

    if len(pattern_rules) != 0:
        return PathSpec.from_lines("gitwildmatch", pattern_rules)
    else:
        return None


def get_attrs(path: str,
              file_attrs: dict):
    file_info = os.lstat(path)

    if sys.version_info >= (3, 12):
        creation_time_attr = "st_birthtime_ns"
    else:
        creation_time_attr = "st_ctime_ns"

    file_attrs[path] = {
        "mode": file_info.st_mode,
        "ctime": getattr(file_info, creation_time_attr),
        "mtime": file_info.st_mtime_ns,
        "atime": file_info.st_atime_ns,
        "uid": file_info.st_uid,
        "gid": file_info.st_gid,
    }

    if SYSTEM_PLATFORM == "Windows":
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
        try:
            stored_data.archive = attr["archive"]
            stored_data.hidden = attr["hidden"]
            stored_data.readonly = attr["readonly"]
            stored_data.system = attr["system"]
        except KeyError:
            stored_data.archive = -1
            stored_data.hidden = -1
            stored_data.readonly = -1
            stored_data.system = -1
    else:
        stored_data.uid = attr["uid"]
        stored_data.gid = attr["gid"]
        stored_data.mode = attr["mode"]

    current_file_info = os.lstat(path)

    if type(stored_data.mtime) is int:
        m_attr = "st_mtime_ns"
        a_attr = "st_atime_ns"
        c_attr = "st_birthtime_ns"
    else:
        m_attr = "st_mtime"
        a_attr = "st_atime"
        # Since nanosecond precision has been added at the same time that birthtime began to be used we use ctime here
        c_attr = "st_ctime"

    stored_data.atime_changed = getattr(current_file_info, a_attr) != stored_data.atime
    stored_data.mtime_changed = getattr(current_file_info, m_attr) != stored_data.mtime
    if SYSTEM_PLATFORM == "Windows":

        if -1 not in (stored_data.archive, stored_data.hidden, stored_data.readonly, stored_data.system):
            cur_archive = bool(current_file_info.st_file_attributes & stat.FILE_ATTRIBUTE_ARCHIVE)
            cur_hidden = bool(current_file_info.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
            cur_readonly = bool(current_file_info.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)
            cur_system = bool(current_file_info.st_file_attributes & stat.FILE_ATTRIBUTE_SYSTEM)

            stored_data.archive_changed = cur_archive != stored_data.archive
            stored_data.hidden_changed = cur_hidden != stored_data.hidden
            stored_data.readonly_changed = cur_readonly != stored_data.readonly
            stored_data.system_changed = cur_system != stored_data.system

        if stored_data.ctime > 0:
            stored_data.ctime_changed = getattr(current_file_info, c_attr) != stored_data.ctime
    else:
        stored_data.mode_changed = current_file_info.st_mode != stored_data.mode
        stored_data.uid_changed = current_file_info.st_uid != stored_data.uid
        stored_data.gid_changed = current_file_info.st_gid != stored_data.gid

    return stored_data


def apply_file_attrs(attrs: dict,
                     no_print: bool,
                     copy_to_access: bool,
                     ignore_filesystem: bool,
                     ignore_permissions: bool,
                     exclusions: Optional[List[str]],
                     exclusions_file: Optional[List[str]],
                     exclusions_ignore_case: bool,
                     skip_archive: bool,
                     skip_hidden: bool,
                     skip_readonly: bool,
                     skip_system: bool):
    processed: bool = False
    errored: List[str] = []  # to store errored files/folders
    optional_args: dict[str, bool] = {}
    symlink_support = os.utime in os.supports_follow_symlinks

    msg_uid_gid = Template("Updating $changed_ids for \"$path\"")
    msg_permissions = Template("Updating permissions for \"$path\"")
    msg_dates = Template("Updating $dates timestamp(s) for \"$path\"")
    msg_win_attribs = Template("Updating $win_attribs attribute(s) for \"$path\"")

    if symlink_support:
        optional_args["follow_symlinks"] = False

    compiled_rules: Optional[PathSpec] = compile_ignore_rules(exclusions_file=exclusions_file,
                                                              exclusions=exclusions,
                                                              exclusions_ignore_case=exclusions_ignore_case)

    for item_path in sorted(attrs):
        attr: dict = attrs[item_path]
        item_path_orig = item_path
        item_path: str = os.path.abspath(item_path)

        if exclusions_ignore_case:
            item_path = item_path.lower()

        if compiled_rules is not None and compiled_rules.match_file(item_path):
            if not no_print:
                print(f"Skipping excluded path \"{os.path.abspath(item_path)}\"")
            continue

        try:
            if not os.path.lexists(item_path):
                if not no_print:
                    print(f"Skipping non-existent item \"{item_path}\"")
                continue

            stored_data = get_attr_for_restore(attr, item_path)

            if (not os.path.islink(item_path) or
                    (os.path.islink(item_path) and symlink_support)):
                if SYSTEM_PLATFORM != "Windows":
                    # Does nothing in Windows
                    if set_uid_gid(item_path=item_path,
                                   stored_data=stored_data,
                                   no_print=no_print,
                                   msg_uid_gid=msg_uid_gid,
                                   optional_arg=optional_args):
                        processed = True

                    # st_mode on Windows is pretty useless, so we only perform this if the current OS is not Windows
                    if set_permissions(item_path_orig=item_path,
                                       stored_data=stored_data,
                                       no_print=no_print,
                                       ignore_permissions=ignore_permissions,
                                       msg_permissions=msg_permissions,
                                       optional_arg=optional_args):
                        processed = True
                else:
                    if process_win_attributes(item_path=item_path,
                                              stored_data=stored_data,
                                              skip_archive=skip_archive,
                                              skip_hidden=skip_hidden,
                                              skip_readonly=skip_readonly,
                                              skip_system=skip_system,
                                              no_print=no_print,
                                              errored=errored,
                                              msg_win_attribs=msg_win_attribs):
                        processed = True

                if set_timestamps(item_path=item_path,
                                  stored_data=stored_data,
                                  no_print=no_print,
                                  msg_dates=msg_dates,
                                  ignore_filesystem=ignore_filesystem,
                                  optional_arg=optional_args):
                    processed = True

                if copy_creation_to_accessed(item_path=item_path,
                                             stored_data=stored_data,
                                             copy_to_access=copy_to_access,
                                             optional_arg=optional_args):
                    processed = True
            elif not no_print:
                print(f"Skipping symbolic link \"{item_path}\"")  # Python doesn't support
                # not following symlinks in this OS so we skip them
        except OSError as Err:
            print(f"\n{Err}", end="\n\n", file=sys.stderr)
            errored.append(item_path)

    if len(errored) != 0:
        print("\nErrored files/folders:\n")
        for line in errored:
            print(line)
        print(f"\nThere were {len(errored)} errors while restoring the attributes.")
        sys.exit(1)
    elif not processed:
        print("Nothing to change.")

    sys.exit(0)


def set_timestamps(item_path: str,
                   stored_data: ResultAttr,
                   no_print: bool,
                   msg_dates: Template,
                   ignore_filesystem: bool,
                   optional_arg: dict[str, bool]) -> bool:
    changed_times = []
    something_changed = False

    if stored_data.mtime_changed:
        changed_times.append("modification")
    if stored_data.atime_changed:
        changed_times.append("accessed")
    if stored_data.ctime_changed:
        changed_times.append("creation")

    if len(changed_times) != 0:
        if not no_print:
            print(msg_dates.substitute(path=item_path, dates=" & ".join(changed_times)))

        if stored_data.mtime_changed or stored_data.atime_changed:
            if type(stored_data.mtime) is int:
                os.utime(item_path, ns=(stored_data.atime, stored_data.mtime), **optional_arg)
            else:
                os.utime(item_path, (stored_data.atime, stored_data.mtime), **optional_arg)

            something_changed = True

        if stored_data.ctime_changed and SYSTEM_PLATFORM == "Windows" and not ignore_filesystem:
            # setctime doesn't support ns timestamps
            try:
                if type(stored_data.ctime) is int:
                    setctime(item_path, stored_data.ctime / 1_000_000_000, **optional_arg)
                else:
                    setctime(item_path, stored_data.ctime, **optional_arg)

                something_changed = True
            except WindowsError as e:
                print("An error occurred while restoring the creation times.")
                print(e)

    return something_changed


def copy_creation_to_accessed(item_path: str,
                              stored_data: ResultAttr,
                              copy_to_access: bool,
                              optional_arg: dict[str, bool]):
    if copy_to_access and stored_data.ctime != stored_data.atime:
        if type(stored_data.mtime) is int:
            os.utime(item_path, ns=(stored_data.ctime, stored_data.mtime), **optional_arg)
        else:
            os.utime(item_path, (stored_data.ctime, stored_data.mtime), **optional_arg)
        return True
    else:
        return False


def process_win_attributes(item_path: str,
                           stored_data: ResultAttr,
                           skip_archive: bool,
                           skip_hidden: bool,
                           skip_readonly: bool,
                           skip_system: bool,
                           no_print: bool,
                           msg_win_attribs: Template,
                           errored: List[str]) -> bool:
    """
    Returns True if attributes have been processed.
    """

    # Can't set attributes for symbolic links in Windows from Python
    if SYSTEM_PLATFORM == "Windows" and not os.path.islink(item_path):
        changed_win_attribs: List[str] = []
        attribs_to_set: int = 0
        attribs_to_unset: int = 0

        if -1 in (stored_data.archive, stored_data.hidden, stored_data.readonly, stored_data.system):
            return False

        if stored_data.archive_changed and not skip_archive:
            changed_win_attribs.append("ARCHIVE")
            if stored_data.archive:
                attribs_to_set |= stat.FILE_ATTRIBUTE_ARCHIVE
            else:
                attribs_to_unset |= stat.FILE_ATTRIBUTE_ARCHIVE

        if stored_data.hidden_changed and not skip_hidden:
            changed_win_attribs.append("HIDDEN")
            if stored_data.hidden:
                attribs_to_set |= stat.FILE_ATTRIBUTE_HIDDEN
            else:
                attribs_to_unset |= stat.FILE_ATTRIBUTE_HIDDEN

        if stored_data.readonly_changed and not skip_readonly:
            changed_win_attribs.append("READ-ONLY")
            if stored_data.readonly:
                attribs_to_set |= stat.FILE_ATTRIBUTE_READONLY
            else:
                attribs_to_unset |= stat.FILE_ATTRIBUTE_READONLY

        if stored_data.system_changed and not skip_system:
            changed_win_attribs.append("SYSTEM")
            if stored_data.system:
                attribs_to_set |= stat.FILE_ATTRIBUTE_SYSTEM
            else:
                attribs_to_unset |= stat.FILE_ATTRIBUTE_SYSTEM

        if len(changed_win_attribs) != 0:
            if not no_print:
                print(msg_win_attribs.substitute(path=item_path,
                                                 win_attribs=" & ".join(changed_win_attribs)))

            if not modify_win_attribs(path=item_path,
                                      attribs_to_set=attribs_to_set,
                                      attribs_to_unset=attribs_to_unset):
                print(f"Error setting Windows attributes for \"{item_path}\"")
                errored.append(item_path)

            return True


def set_uid_gid(item_path: str,
                stored_data: ResultAttr,
                no_print: bool,
                msg_uid_gid: Template,
                optional_arg: dict[str, bool]) -> bool:
    changed_ids = []
    if stored_data.uid_changed:
        changed_ids.append("UID")
    if stored_data.gid_changed:
        changed_ids.append("GID")

    if len(changed_ids) != 0:
        if not no_print:
            print(msg_uid_gid.substitute(path=item_path, changed_ids=" & ".join(changed_ids)))

        os.chown(item_path, stored_data.uid, stored_data.gid, **optional_arg)
        return True
    else:
        return False


def set_permissions(item_path_orig: str,
                    stored_data: ResultAttr,
                    no_print: bool,
                    ignore_permissions: bool,
                    msg_permissions: Template,
                    optional_arg: dict[str, bool]) -> bool:
    if stored_data.mode_changed and not ignore_permissions:
        if not no_print:
            print(msg_permissions.substitute(path=item_path_orig))
        os.chmod(item_path_orig, stored_data.mode, **optional_arg)

        return True

    return False


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
               exclusions: Optional[List[str]],
               exclusions_file: Optional[List[str]],
               no_print: bool,
               exclusions_ignore_case: bool) -> None:
    """
    :param working_path: Path where the attributes will be saved from
    :param output_file: Path to the file where to save the attributes to
    :param relative: Whether to store the paths as relatives to the root drive
    :param exclusions: List of pattern rules to exclude
    :param exclusions_file: List of paths of ignore-files.
    :param no_print: Whether to print not found / skipped symlinks messages
    :param exclusions_ignore_case: Ignore casing with exclusion rules.
    """

    if working_path.endswith("\""):
        working_path = working_path[:-1] + os.path.sep  # Windows escapes the quote if the command ends in '\"' so this
        # fixes that, or at least it does if this argument is the last one, otherwise the output argument will eat
        # all the next args

    if working_path.endswith(":"):
        working_path += os.path.sep

    if not os.path.exists(working_path):
        print(f"\nERROR: The specified path:\n\n{working_path}\n\nDoesn't exist, aborting...", file=sys.stderr)
        sys.exit(1)

    has_drive: str = os.path.splitdrive(output_file)[0]
    if has_drive != "" and not os.path.exists(has_drive):
        print(f"\nERROR: The specified drive:\n\n{output_file}\n\nDoesn't exist, aborting...", file=sys.stderr)
        sys.exit(1)

    attr_file_name = output_file
    if attr_file_name.endswith("\""):
        attr_file_name = attr_file_name[:-1]  # Windows escapes the quote if the command ends in \" so this fixes
        # that, or at least it does if this argument is the last one, otherwise the output argument will eat all the
        # following args

    if attr_file_name.endswith(":"):
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

    reqstate: List[bool] = [relative,
                            working_path != os.curdir,
                            os.path.dirname(attr_file_name) == ""]

    orig_working_path: str = working_path
    if all(reqstate):
        attr_file_name = os.path.join(os.getcwd(), attr_file_name)
    if reqstate[0] & reqstate[1]:
        os.chdir(working_path)
        working_path = os.curdir

    try:
        attrs = collect_file_attrs(working_path=working_path,
                                   orig_working_path=orig_working_path,
                                   relative=relative,
                                   exclusions=exclusions,
                                   exclusions_file=exclusions_file,
                                   no_print=no_print,
                                   exclusions_ignore_case=exclusions_ignore_case)
        with open(attr_file_name, "w", encoding="utf-8", errors="backslashreplace") as attr_file:
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
                  copy_to_access: bool,
                  ignore_filesystem: bool,
                  ignore_permissions: bool,
                  exclusions: Optional[List[str]],
                  exclusions_file: Optional[List[str]],
                  exclusions_ignore_case: bool,
                  skip_archive: bool,
                  skip_hidden: bool,
                  skip_readonly: bool,
                  skip_system: bool):
    if input_file.endswith('"'):
        input_file = input_file[:-1] + os.path.sep  # Windows escapes the quote if the command ends in \" so
        # this fixes that
    if os.path.basename(input_file) == "":
        input_file = os.path.join(input_file, DEFAULT_ATTR_FILENAME)
    if not os.path.exists(input_file):
        print(f"ERROR: Saved attributes file \"{input_file}\" not found", file=sys.stderr)
        sys.exit(1)
    if os.path.isdir(input_file):
        print("ERROR: You have specified a directory for the input file, aborting...")
        sys.exit(1)

    attr_file_size: int = os.path.getsize(input_file)

    if attr_file_size == 0:
        print("ERROR: The attribute file is empty!", file=sys.stderr)
        sys.exit(1)

    try:
        with open(input_file, "r", encoding="utf-8", errors="backslashreplace") as attr_file:
            attrs: dict = json.load(attr_file)

        if len(attrs) == 0:
            print("ERROR: The attribute file is empty!", file=sys.stderr)
            sys.exit(1)

        if working_path != os.curdir:
            os.chdir(working_path)

        apply_file_attrs(attrs=attrs,
                         no_print=no_print,
                         copy_to_access=copy_to_access,
                         ignore_filesystem=ignore_filesystem,
                         ignore_permissions=ignore_permissions,
                         exclusions=exclusions,
                         exclusions_file=exclusions_file,
                         exclusions_ignore_case=exclusions_ignore_case,
                         skip_archive=skip_archive,
                         skip_hidden=skip_hidden,
                         skip_readonly=skip_readonly,
                         skip_system=skip_system)
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
                             help="Pattern rules to exclude, same format as git ignore rules. (Optional)",
                             metavar="%PATTERN_RULE%",
                             nargs="*")
    save_parser.add_argument("-ef", "--ignore-file",
                             help="Ignore file containing pattern rules, same format as git ignore rules. (Optional)",
                             metavar="%IGNORE-FILE%",
                             nargs="*")
    save_parser.add_argument("-eic", "--exclusions-ignore-case",
                             help="Ignore casing for exclusions.",
                             action="store_true")
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
    restore_parser.add_argument("-ex", "--exclude",
                                help="Pattern rules to exclude, same format as git ignore rules. (Optional)",
                                metavar="%PATTERN_RULE%",
                                nargs="*")
    restore_parser.add_argument("-ef", "--ignore-file",
                                help="Ignore file containing pattern rules, same format as git ignore rules. ("
                                     "Optional)",
                                metavar="%IGNORE-FILE%",
                                nargs="?")
    restore_parser.add_argument("-eic", "--exclusions-ignore-case",
                                help="Ignore casing for exclusions.",
                                action="store_true")
    restore_parser.add_argument("-sa", "--skip-archive",
                                help="Skip setting the \"archive\" attribute.",
                                action="store_true")
    restore_parser.add_argument("-sh", "--skip-hidden",
                                help="Skip setting the \"hidden\" attribute.",
                                action="store_true")
    restore_parser.add_argument("-sr", "--skip-readonly",
                                help="Skip setting the \"read-only\" attribute.",
                                action="store_true")
    restore_parser.add_argument("-ss", "--skip-system",
                                help="Skip setting the \"system\" attribute.",
                                action="store_true")
    args = parser.parse_args()

    # Set args variables

    mode: str = args.mode

    if mode is None:
        print("You have to use either save or restore.\nRead the help.")
        sys.exit(3)

    working_path: str = args.working_path
    no_print: bool = args.no_print
    exclusions: Optional[List[str]] = args.exclude
    exclusions_file: Optional[List[str]] = args.ignore_file
    exclusions_ignore_case: bool = args.exclusions_ignore_case

    if exclusions_file is not None:
        for file in exclusions_file:
            if not os.path.isfile(file):
                print("Specified ignore path is not a file or doesn't exist, exiting...")
                sys.exit(1)

    if mode == "save":
        output_file: str = args.output
        relative: bool = args.relative

        save_attrs(working_path=working_path,
                   output_file=output_file,
                   relative=relative,
                   exclusions=exclusions,
                   exclusions_file=exclusions_file,
                   exclusions_ignore_case=exclusions_ignore_case,
                   no_print=no_print)

    if mode == "restore":
        input_file: str = args.input
        copy_to_access: bool = args.copy_to_access
        ignore_filesystem: bool = args.ignore_filesystem
        ignore_permissions: bool = args.ignore_permissions
        skip_archive: bool = args.skip_archive
        skip_hidden: bool = args.skip_hidden
        skip_readonly: bool = args.skip_readonly
        skip_system: bool = args.skip_system

        restore_attrs(input_file=input_file,
                      working_path=working_path,
                      no_print=no_print,
                      copy_to_access=copy_to_access,
                      ignore_filesystem=ignore_filesystem,
                      ignore_permissions=ignore_permissions,
                      exclusions=exclusions,
                      exclusions_file=exclusions_file,
                      exclusions_ignore_case=exclusions_ignore_case,
                      skip_archive=skip_archive,
                      skip_hidden=skip_hidden,
                      skip_readonly=skip_readonly,
                      skip_system=skip_system)


if __name__ == "__main__":
    main()
