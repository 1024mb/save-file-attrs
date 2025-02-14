#!/usr/bin/env python

"""
Save and restore modified, accessed and created times, owners and mode for all files in a tree.
"""

from __future__ import annotations

import argparse
import copy
import ctypes
import os
import sys
import textwrap
from os import DirEntry
from string import Template
from typing import Optional, List, Dict

import orjson
from pathspec import PathSpec, GitIgnoreSpec
from pydantic import BaseModel, ValidationError

from version import __version__

SYSTEM_PLATFORM: str = sys.platform
if SYSTEM_PLATFORM.startswith("linux"):
    SYSTEM_PLATFORM = "linux"
elif SYSTEM_PLATFORM in ("win32", "cygwin"):
    SYSTEM_PLATFORM = "windows"

# ERROR CODES
SUCCESS: int = 0
USER_INTERRUPTED: int = 1
GENERIC_ERROR: int = 2
FILE_RELATED: int = 3
ATTRIB_FILE_RELATED: int = 10

if SYSTEM_PLATFORM == "windows":
    import stat
    from win32_setctime import setctime

DEFAULT_ATTR_FILENAME = ".saved-file-attrs"

CREATION_TIME_ATTR: str


class ResultAttr(BaseModel, validate_assignment=True):
    atime: int | float = None
    mtime: int | float = None
    ctime: int | float = None
    mode: int = None
    uid: int = None
    gid: int = None
    archive: bool = None
    hidden: bool = None
    readonly: bool = None
    system: bool = None
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


class AttrData(BaseModel, validate_assignment=True):
    atime: int | float = 0
    mtime: int | float = 0
    ctime: int | float = 0
    mode: int = 0
    uid: int = 0
    gid: int = 0


class WinAttrData(BaseModel, validate_assignment=True):
    atime: int | float = 0
    mtime: int | float = 0
    ctime: int | float = 0
    archive: bool = False
    hidden: bool = False
    readonly: bool = False
    system: bool = False


class OldWinAttrData(BaseModel):
    mode: int = 0
    uid: int = 0
    gid: int = 0
    atime: int | float = 0
    mtime: int | float = 0
    ctime: int | float = 0
    archive: bool = False
    hidden: bool = False
    readonly: bool = False
    system: bool = False


def get_path_content(path_to_scan: str):
    return [item for item in os.scandir(path_to_scan)]


def get_non_excluded_items(path_to_scan: str,
                           exclusion_rules: Optional[PathSpec],
                           exclusions_ignore_case: bool,
                           relative: bool,
                           no_print_excluded: bool) -> List[DirEntry]:
    non_excluded_items = []
    items = get_path_content(path_to_scan=path_to_scan)

    for item in items:
        if exclusions_ignore_case:
            path = item.path.lower()
        else:
            path = item.path

        if item.is_dir():
            path += os.path.sep

        if not exclusion_rules.match_file(path):
            non_excluded_items.append(item)
        else:
            if not no_print_excluded:
                if relative:
                    print(f"Skipping excluded path \"{item.path}\"")
                else:
                    print(f"Skipping excluded path \"{os.path.abspath(item.path)}\"")

    return copy.copy(non_excluded_items)


def get_paths(ignore_files: Optional[List[str]],
              exclusions: Optional[List[str]],
              exclusions_ignore_case: bool,
              initial_path: str,
              relative: bool,
              no_print_excluded: bool) -> List[DirEntry]:
    matched_items: List[DirEntry] = []
    compiled_rules: Optional[PathSpec] = compile_ignore_rules(ignore_files=ignore_files,
                                                              exclusions=exclusions,
                                                              exclusions_ignore_case=exclusions_ignore_case)

    if compiled_rules is None:
        alternative_items_list = get_path_content(path_to_scan=initial_path)
    else:
        alternative_items_list = get_non_excluded_items(path_to_scan=initial_path,
                                                        exclusion_rules=compiled_rules,
                                                        exclusions_ignore_case=exclusions_ignore_case,
                                                        relative=relative,
                                                        no_print_excluded=no_print_excluded)

    matched_items += copy.copy(alternative_items_list)

    temp_items_list = []

    while True:
        for item in alternative_items_list:
            if item.is_dir() and not item.is_symlink() and not item.is_junction():
                if compiled_rules is not None:
                    temp_items_list += get_non_excluded_items(path_to_scan=item.path,
                                                              exclusion_rules=compiled_rules,
                                                              exclusions_ignore_case=exclusions_ignore_case,
                                                              relative=relative,
                                                              no_print_excluded=no_print_excluded)
                else:
                    temp_items_list += get_path_content(path_to_scan=item.path)

        if len(temp_items_list) == 0:
            break

        matched_items += copy.copy(temp_items_list)

        alternative_items_list = copy.copy(temp_items_list)
        temp_items_list = []

    return matched_items


def collect_file_attrs(relative: bool,
                       exclusions: Optional[List[str]],
                       ignore_files: Optional[List[str]],
                       no_print_excluded: bool,
                       exclusions_ignore_case: bool,
                       output_file: str) -> None:
    global CREATION_TIME_ATTR
    print("\nCollecting item list, please wait...")

    file_attrs: Dict[str, AttrData | WinAttrData] = {}

    if sys.version_info >= (3, 12):
        CREATION_TIME_ATTR = "st_birthtime_ns"
    else:
        CREATION_TIME_ATTR = "st_ctime_ns"

    paths: List[DirEntry] = get_paths(ignore_files=ignore_files,
                                      exclusions=exclusions,
                                      exclusions_ignore_case=exclusions_ignore_case,
                                      initial_path=os.curdir,
                                      relative=relative,
                                      no_print_excluded=no_print_excluded)

    print("\nCollecting attributes, please wait...")

    consecutive_errors = 0

    for item in paths:
        try:
            if consecutive_errors == 10:
                print(f"\nToo many consecutive errors ({consecutive_errors}), aborting...")
                if len(file_attrs) > 0:
                    write_attr_file(file_path=output_file,
                                    content=file_attrs)
                sys.exit(GENERIC_ERROR)

            consecutive_errors = 0
            path = item.path

            if not relative:
                path = os.path.abspath(path)

            file_attrs[path] = get_attrs(path=item)
        except KeyboardInterrupt:
            try:
                print("\nShutdown requested... dumping what could be collected...\n")
                write_attr_file(file_path=output_file,
                                content=file_attrs)
                raise
            except KeyboardInterrupt:
                print("Cancelling...")
                raise
        except Exception as e:
            print(f"\n{e}", end="\n\n")
            consecutive_errors += 1

    write_attr_file(file_path=output_file,
                    content=file_attrs)


def write_attr_file(file_path: str,
                    content: dict[str, AttrData | WinAttrData]) -> None:
    with open(file_path, "wb") as attr_file:
        attr_file.write(orjson.dumps(content, option=orjson.OPT_INDENT_2))

    print(f"\nAttributes saved to \"{os.path.abspath(file_path)}\"")


def compile_ignore_rules(ignore_files: Optional[List[str]],
                         exclusions: Optional[List[str]],
                         exclusions_ignore_case: bool) -> Optional[PathSpec]:
    pattern_rules = []

    if ignore_files is not None:
        for ignore_file in ignore_files:
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
        return GitIgnoreSpec.from_lines(pattern_rules)
    else:
        return None


def get_attrs(path: DirEntry) -> AttrData | WinAttrData:
    file_info = path.stat(follow_symlinks=False)

    if SYSTEM_PLATFORM == "windows":
        file_attrs = WinAttrData()
    else:
        file_attrs = AttrData()

    file_attrs.ctime = getattr(file_info, CREATION_TIME_ATTR)
    file_attrs.mtime = file_info.st_mtime_ns
    file_attrs.atime = file_info.st_atime_ns

    if SYSTEM_PLATFORM == "windows":
        file_attrs.archive = bool(file_info.st_file_attributes & stat.FILE_ATTRIBUTE_ARCHIVE)
        file_attrs.hidden = bool(file_info.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
        file_attrs.readonly = bool(file_info.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)
        file_attrs.system = bool(file_info.st_file_attributes & stat.FILE_ATTRIBUTE_SYSTEM)

        return WinAttrData.model_dump(file_attrs)
    else:
        file_attrs.mode = file_info.st_mode
        file_attrs.uid = file_info.st_uid
        file_attrs.gid = file_info.st_gid

        return AttrData.model_dump(file_attrs)


def get_attr_for_restore(attr: AttrData | WinAttrData | OldWinAttrData,
                         path: str,
                         ignore_filesystem: bool) -> ResultAttr:
    stored_data = ResultAttr()
    current_file_info = os.lstat(path)

    stored_data.atime = attr.atime
    stored_data.mtime = attr.mtime

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

    if SYSTEM_PLATFORM == "windows":
        stored_data.ctime = attr.ctime

        if not ignore_filesystem and stored_data.ctime > 0:
            stored_data.ctime_changed = getattr(current_file_info, c_attr) != stored_data.ctime

        if not isinstance(attr, AttrData):
            stored_data.archive = attr.archive
            stored_data.hidden = attr.hidden
            stored_data.readonly = attr.readonly
            stored_data.system = attr.system

            cur_archive = bool(current_file_info.st_file_attributes & stat.FILE_ATTRIBUTE_ARCHIVE)
            cur_hidden = bool(current_file_info.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
            cur_readonly = bool(current_file_info.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)
            cur_system = bool(current_file_info.st_file_attributes & stat.FILE_ATTRIBUTE_SYSTEM)

            stored_data.archive_changed = cur_archive != stored_data.archive
            stored_data.hidden_changed = cur_hidden != stored_data.hidden
            stored_data.readonly_changed = cur_readonly != stored_data.readonly
            stored_data.system_changed = cur_system != stored_data.system
    else:
        if isinstance(attr, AttrData) or isinstance(attr, OldWinAttrData):
            stored_data.uid = attr.uid
            stored_data.gid = attr.gid
            stored_data.mode = attr.mode

            stored_data.mode_changed = current_file_info.st_mode != stored_data.mode
            stored_data.uid_changed = current_file_info.st_uid != stored_data.uid
            stored_data.gid_changed = current_file_info.st_gid != stored_data.gid

    return stored_data


def apply_file_attrs(attrs: Dict[str, AttrData | WinAttrData | OldWinAttrData],
                     no_print_modified: bool,
                     no_print_skipped: bool,
                     no_print_excluded: bool,
                     copy_to_access: bool,
                     ignore_filesystem: bool,
                     ignore_permissions: bool,
                     exclusions: Optional[List[str]],
                     ignore_files: Optional[List[str]],
                     exclusions_ignore_case: bool,
                     skip_archive: bool,
                     skip_hidden: bool,
                     skip_readonly: bool,
                     skip_system: bool):
    processed: bool = False
    errored: List[str] = []  # to store errored files/folders
    optional_args: Dict[str, bool] = {}
    symlink_support = os.utime in os.supports_follow_symlinks

    msg_uid_gid = Template("Updating $changed_ids for \"$path\"")
    msg_permissions = Template("Updating permissions for \"$path\"")
    msg_dates = Template("Updating $dates timestamp(s) for \"$path\"")
    msg_win_attribs = Template("Updating $win_attribs attribute(s) for \"$path\"")

    if symlink_support:
        optional_args["follow_symlinks"] = False

    compiled_rules: Optional[PathSpec] = compile_ignore_rules(ignore_files=ignore_files,
                                                              exclusions=exclusions,
                                                              exclusions_ignore_case=exclusions_ignore_case)

    for item_path in sorted(attrs):
        try:
            if not os.path.lexists(item_path):
                if not no_print_skipped:
                    print(f"Skipping non-existent item \"{item_path}\"")
                continue

            attr: AttrData | WinAttrData | OldWinAttrData
            try:
                attr = AttrData.model_validate(attrs[item_path])
            except ValidationError:
                try:
                    attr = WinAttrData.model_validate(attrs[item_path])
                except ValidationError:
                    try:
                        attr = OldWinAttrData.model_validate(attrs[item_path])
                    except ValidationError:
                        print(f"Attribute file is corrupt, aborting...\nError in path {item_path}")
                        sys.exit(ATTRIB_FILE_RELATED)

            comp_item_path = os.path.relpath(item_path, os.getcwd())

            if os.path.isdir(item_path):
                comp_item_path += os.path.sep

            if exclusions_ignore_case:
                comp_item_path = comp_item_path.lower()

            if compiled_rules is not None and compiled_rules.match_file(comp_item_path):
                if not no_print_excluded:
                    print(f"Skipping excluded path \"{os.path.abspath(item_path)}\"")
                continue

            stored_data = get_attr_for_restore(attr=attr, path=item_path, ignore_filesystem=ignore_filesystem)

            if (not os.path.islink(item_path) or
                    (os.path.islink(item_path) and symlink_support)):
                if SYSTEM_PLATFORM != "windows":
                    # Does nothing in Windows
                    if set_uid_gid(item_path=item_path,
                                   stored_data=stored_data,
                                   no_print_modified=no_print_modified,
                                   msg_uid_gid=msg_uid_gid,
                                   optional_arg=optional_args):
                        processed = True

                    # st_mode on Windows is pretty useless, so we only perform this if the current OS is not Windows
                    if set_permissions(item_path=item_path,
                                       stored_data=stored_data,
                                       no_print_modified=no_print_modified,
                                       ignore_permissions=ignore_permissions,
                                       msg_permissions=msg_permissions,
                                       optional_arg=optional_args):
                        processed = True
                elif not stored_data.archive is None:
                    if process_win_attributes(item_path=item_path,
                                              stored_data=stored_data,
                                              skip_archive=skip_archive,
                                              skip_hidden=skip_hidden,
                                              skip_readonly=skip_readonly,
                                              skip_system=skip_system,
                                              no_print_modified=no_print_modified,
                                              errored=errored,
                                              msg_win_attribs=msg_win_attribs):
                        processed = True

                if set_timestamps(item_path=item_path,
                                  stored_data=stored_data,
                                  no_print_modified=no_print_modified,
                                  msg_dates=msg_dates,
                                  ignore_filesystem=ignore_filesystem,
                                  optional_arg=optional_args):
                    processed = True

                if copy_creation_to_accessed(item_path=item_path,
                                             stored_data=stored_data,
                                             copy_to_access=copy_to_access,
                                             optional_arg=optional_args):
                    processed = True
            elif not no_print_skipped:
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
        sys.exit(GENERIC_ERROR)
    elif not processed:
        print("Nothing to change.")

    sys.exit(SUCCESS)


def set_timestamps(item_path: str,
                   stored_data: ResultAttr,
                   no_print_modified: bool,
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
        if not no_print_modified:
            print(msg_dates.substitute(path=item_path, dates=" & ".join(changed_times)))

        if stored_data.mtime_changed or stored_data.atime_changed:
            if type(stored_data.mtime) is int:
                os.utime(item_path, ns=(stored_data.atime, stored_data.mtime), **optional_arg)
            else:
                os.utime(item_path, (stored_data.atime, stored_data.mtime), **optional_arg)

            something_changed = True

        if stored_data.ctime_changed and SYSTEM_PLATFORM == "windows" and not ignore_filesystem:
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
                           no_print_modified: bool,
                           msg_win_attribs: Template,
                           errored: List[str]) -> bool:
    """
    Returns True if attributes have been processed.
    """

    # Can't set attributes for symbolic links in Windows from Python
    if not os.path.islink(item_path):
        changed_win_attribs: List[str] = []
        attribs_to_set: int = 0
        attribs_to_unset: int = 0

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

        if len(changed_win_attribs) > 0:
            if not no_print_modified:
                print(msg_win_attribs.substitute(path=item_path,
                                                 win_attribs=" & ".join(changed_win_attribs)))

            if not modify_win_attribs(path=item_path,
                                      attribs_to_set=attribs_to_set,
                                      attribs_to_unset=attribs_to_unset):
                print(f"Error setting Windows attributes for \"{item_path}\"")
                errored.append(item_path)

            return True

    return False


def set_uid_gid(item_path: str,
                stored_data: ResultAttr,
                no_print_modified: bool,
                msg_uid_gid: Template,
                optional_arg: dict[str, bool]) -> bool:
    changed_ids = []
    if stored_data.uid_changed:
        changed_ids.append("UID")
    if stored_data.gid_changed:
        changed_ids.append("GID")

    if len(changed_ids) != 0:
        if not no_print_modified:
            print(msg_uid_gid.substitute(path=item_path, changed_ids=" & ".join(changed_ids)))

        os.chown(item_path, stored_data.uid, stored_data.gid, **optional_arg)
        return True
    else:
        return False


def set_permissions(item_path: str,
                    stored_data: ResultAttr,
                    no_print_modified: bool,
                    ignore_permissions: bool,
                    msg_permissions: Template,
                    optional_arg: dict[str, bool]) -> bool:
    if stored_data.mode_changed and not ignore_permissions:
        if not no_print_modified:
            print(msg_permissions.substitute(path=item_path))

        os.chmod(item_path, stored_data.mode, **optional_arg)

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
               ignore_files: Optional[List[str]],
               exclusions_ignore_case: bool,
               no_print_excluded: bool) -> None:
    """
    :param working_path: Path where the attributes will be saved from
    :param output_file: Path to the file where to save the attributes to
    :param relative: Whether to store the paths as relatives to the root drive
    :param exclusions: List of pattern rules to exclude
    :param ignore_files: List of paths of ignore-files.
    :param no_print_excluded: Whether to print excluded file/dir paths
    :param exclusions_ignore_case: Ignore casing with exclusion rules.
    """

    if SYSTEM_PLATFORM == "windows":
        if working_path.endswith("\""):
            print(f"Invalid character in working path: {working_path}", file=sys.stderr)
            sys.exit(FILE_RELATED)

        if output_file.endswith("\""):
            print(f"Invalid character in output file: {output_file}", file=sys.stderr)
            sys.exit(FILE_RELATED)

        if working_path.endswith(":"):
            working_path += os.path.sep

    if not os.path.exists(working_path):
        print(f"\nERROR: The specified working path doesn't exist, aborting...", file=sys.stderr)
        sys.exit(FILE_RELATED)

    has_drive: str = os.path.splitdrive(output_file)[0]
    if has_drive != "" and not os.path.exists(has_drive):
        print(f"\nERROR: The specified output drive doesn't exist, aborting...", file=sys.stderr)
        sys.exit(FILE_RELATED)

    if output_file.endswith(":"):
        output_file += os.path.sep

    if os.path.basename(output_file) != "" and os.path.isdir(output_file):
        print("ERROR: The output filename you specified is the same one of a directory, a directory and a file "
              "with the same name can't exist within the same path, aborting...")
        sys.exit(FILE_RELATED)

    if os.path.dirname(output_file) != "":
        if os.path.isfile(os.path.dirname(output_file)):
            print("ERROR: The output directory name you specified is the same one of a file, a directory and a file "
                  "with the same name can't exist within the same path, aborting...")
            sys.exit(FILE_RELATED)

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
    else:
        if os.path.isdir(os.path.join(os.getcwd(), output_file)):
            print("ERROR: The output filename you specified is the same one of a directory, a directory and a file "
                  "with the same name can't exist within the same path, aborting...")
            sys.exit(FILE_RELATED)

    if os.path.basename(output_file) == "":
        output_file = os.path.join(output_file, DEFAULT_ATTR_FILENAME)

    reqstate: List[bool] = [relative,
                            working_path != os.curdir,
                            working_path != os.getcwd(),
                            os.path.dirname(output_file) == ""]

    if all(reqstate):
        output_file = os.path.abspath(output_file)

    os.chdir(working_path)

    try:
        collect_file_attrs(relative=relative,
                           exclusions=exclusions,
                           ignore_files=ignore_files,
                           no_print_excluded=no_print_excluded,
                           exclusions_ignore_case=exclusions_ignore_case,
                           output_file=output_file)
    except OSError as ERR_W:
        print("ERROR: There was an error writing to the attribute file.\n\n", ERR_W, file=sys.stderr)
        sys.exit(FILE_RELATED)


def restore_attrs(input_file: str,
                  working_path: str,
                  no_print_modified: bool,
                  no_print_skipped: bool,
                  no_print_excluded: bool,
                  copy_to_access: bool,
                  ignore_filesystem: bool,
                  ignore_permissions: bool,
                  exclusions: Optional[List[str]],
                  ignore_files: Optional[List[str]],
                  exclusions_ignore_case: bool,
                  skip_archive: bool,
                  skip_hidden: bool,
                  skip_readonly: bool,
                  skip_system: bool):
    if SYSTEM_PLATFORM == "windows" and input_file.endswith('"'):
        print(f"Invalid character in attribute file path: {input_file}", file=sys.stderr)
        sys.exit(FILE_RELATED)

    if os.path.basename(input_file) == "":
        input_file = os.path.join(input_file, DEFAULT_ATTR_FILENAME)

    if not os.path.exists(input_file):
        print(f"ERROR: Attribute file \"{input_file}\" not found", file=sys.stderr)
        sys.exit(FILE_RELATED)

    if os.path.isdir(input_file):
        print("ERROR: You have specified a directory for the input file, aborting...")
        sys.exit(FILE_RELATED)

    if os.path.getsize(input_file) == 0:
        print("ERROR: The attribute file is empty!", file=sys.stderr)
        sys.exit(FILE_RELATED)

    try:
        with open(input_file, "rb") as attr_file:
            attrs: Dict[str, AttrData | WinAttrData | OldWinAttrData] = orjson.loads(attr_file.read())

        if len(attrs) == 0:
            print("ERROR: The attribute file is empty!", file=sys.stderr)
            sys.exit(FILE_RELATED)

        os.chdir(working_path)

        apply_file_attrs(attrs=attrs,
                         no_print_modified=no_print_modified,
                         no_print_skipped=no_print_skipped,
                         no_print_excluded=no_print_excluded,
                         copy_to_access=copy_to_access,
                         ignore_filesystem=ignore_filesystem,
                         ignore_permissions=ignore_permissions,
                         exclusions=exclusions,
                         ignore_files=ignore_files,
                         exclusions_ignore_case=exclusions_ignore_case,
                         skip_archive=skip_archive,
                         skip_hidden=skip_hidden,
                         skip_readonly=skip_readonly,
                         skip_system=skip_system)
    except KeyboardInterrupt:
        print("Shutdown requested...", file=sys.stderr)
        raise
    except OSError as ERR_R:
        print(f"ERROR: There was an error reading the attribute file, no attribute has been changed.\n\n{ERR_R}\n",
              file=sys.stderr)
        sys.exit(FILE_RELATED)


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(
                                             """
                                     Save and restore file attributes in a directory tree
                                     
                                     Exit code:
                                         0: Success
                                         1: User interrupted
                                         2: Generic error
                                         3: File related error
                                         10: Attribute file related error
                                     """))
    parser.add_argument("--version", "-version",
                        action="version",
                        version=f"%(prog)s v{__version__}")
    subparsers = parser.add_subparsers(dest="mode",
                                       help="Select the mode of operation")

    save_parser = subparsers.add_parser("save",
                                        formatter_class=argparse.RawDescriptionHelpFormatter,
                                        description=textwrap.dedent("""
                                        Save file and directory attributes in a directory tree
                                        
                                        Exit code:
                                            0: Success
                                            1: User interrupted
                                            2: Generic error
                                            3: File related error
                                            10: Attribute file related error
                                        """))
    save_parser.add_argument("-o", "--output",
                             help="Set the output file (Optional, default is \".saved-file-attrs\" in current dir)",
                             metavar="%OUTPUT%",
                             default=DEFAULT_ATTR_FILENAME,
                             nargs="?")
    save_parser.add_argument("-wp", "--working-path",
                             help="Set the path to store attributes from (Optional, default is current path)",
                             metavar="%PATH%",
                             default=os.curdir,
                             nargs="?")
    save_parser.add_argument("-ex", "--exclude",
                             help="Pattern rules to exclude, same format as git ignore rules. (Optional)",
                             metavar="%PATTERN_RULE%",
                             nargs="*")
    save_parser.add_argument("-if", "--ignore-file",
                             help="Ignore file containing pattern rules, same format as git ignore rules. (Optional)",
                             metavar="%IGNORE-FILE%",
                             nargs="*")
    save_parser.add_argument("-eic", "--exclusions-ignore-case",
                             help="Ignore casing for exclusions.",
                             action="store_true")
    save_parser.add_argument("-r", "--relative",
                             help="Store the paths as relative instead of full (Optional)",
                             action="store_true")
    save_parser.add_argument("--no-print-excluded",
                             help="Don't print excluded files and folders (Optional)",
                             action="store_true")

    restore_parser = subparsers.add_parser("restore",
                                           formatter_class=argparse.RawDescriptionHelpFormatter,
                                           description=textwrap.dedent("""
                                            Restore file and directory attributes in a directory tree
                                            
                                            Exit code:
                                                0: Success
                                                1: User interrupted
                                                2: Generic error
                                                3: File related error
                                                10: Attribute file related error
                                            """))
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
    restore_parser.add_argument("--no-print-modified",
                                help="Don't print modified files and folders (Optional)",
                                action="store_true")
    restore_parser.add_argument("--no-print-skipped",
                                help="Don't print skipped files and folders (Optional)",
                                action="store_true")
    restore_parser.add_argument("--no-print-excluded",
                                help="Don't print excluded files and folders (Optional)",
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
    restore_parser.add_argument("-if", "--ignore-file",
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
        sys.exit(GENERIC_ERROR)

    working_path: str = args.working_path
    no_print_excluded: bool = args.no_print_excluded
    exclusions: Optional[List[str]] = args.exclude
    ignore_files: Optional[List[str]] = args.ignore_file
    exclusions_ignore_case: bool = args.exclusions_ignore_case

    if ignore_files is not None:
        for file in ignore_files:
            if not os.path.isfile(file):
                print("Specified ignore filepath is not a file or doesn't exist, exiting...")
                sys.exit(FILE_RELATED)

    if mode == "save":
        output_file: str = args.output
        relative: bool = args.relative

        save_attrs(working_path=working_path,
                   output_file=output_file,
                   relative=relative,
                   exclusions=exclusions,
                   ignore_files=ignore_files,
                   exclusions_ignore_case=exclusions_ignore_case,
                   no_print_excluded=no_print_excluded)

    if mode == "restore":
        input_file: str = args.input
        no_print_modified: bool = args.no_print_modified
        no_print_skipped: bool = args.no_print_skipped
        copy_to_access: bool = args.copy_to_access
        ignore_filesystem: bool = args.ignore_filesystem
        ignore_permissions: bool = args.ignore_permissions
        skip_archive: bool = args.skip_archive
        skip_hidden: bool = args.skip_hidden
        skip_readonly: bool = args.skip_readonly
        skip_system: bool = args.skip_system

        restore_attrs(input_file=input_file,
                      working_path=working_path,
                      no_print_skipped=no_print_skipped,
                      no_print_excluded=no_print_excluded,
                      no_print_modified=no_print_modified,
                      copy_to_access=copy_to_access,
                      ignore_filesystem=ignore_filesystem,
                      ignore_permissions=ignore_permissions,
                      exclusions=exclusions,
                      ignore_files=ignore_files,
                      exclusions_ignore_case=exclusions_ignore_case,
                      skip_archive=skip_archive,
                      skip_hidden=skip_hidden,
                      skip_readonly=skip_readonly,
                      skip_system=skip_system)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Exiting...")
        sys.exit(USER_INTERRUPTED)
