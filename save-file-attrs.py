#!/usr/bin/env python

"""
Save and restore modified, accessed and created times, owners and mode for all files in a tree.
"""

import argparse
import copy
import os
import sys
import textwrap
from os import DirEntry
from string import Template

import orjson
from pathspec import PathSpec, GitIgnoreSpec
from pydantic import BaseModel, ValidationError

from version import __version__

# ERROR CODES
SUCCESS: int = 0
USER_INTERRUPTED: int = 1
GENERIC_ERROR: int = 2
FILE_RELATED: int = 3
ATTRIB_FILE_RELATED: int = 10

# STRING TEMPLATES
SKIP_SYMLINK_TEMPLATE: Template = Template("Skipping symbolic link \"$path\"")

if sys.version_info < (3, 12):
    print("Python version must be >= 3.12")
    sys.exit(GENERIC_ERROR)

SYSTEM_PLATFORM: str = sys.platform
if SYSTEM_PLATFORM.startswith("linux"):
    SYSTEM_PLATFORM = "linux"
elif SYSTEM_PLATFORM in ("win32", "cygwin"):
    SYSTEM_PLATFORM = "windows"

if SYSTEM_PLATFORM == "windows":
    from win_utils.set_times import set_times
    import stat
    import ctypes

DEFAULT_ATTR_FILENAME = ".saved-file-attrs"


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
    atime: int | float
    mtime: int | float
    ctime: int | float
    mode: int
    uid: int
    gid: int


class WinAttrData(BaseModel, validate_assignment=True):
    atime: int | float
    mtime: int | float
    ctime: int | float
    archive: bool
    hidden: bool
    readonly: bool
    system: bool


class OldWinAttrData(BaseModel, validate_assignment=True):
    atime: int | float
    mtime: int | float
    ctime: int | float
    mode: int
    uid: int
    gid: int
    archive: bool
    hidden: bool
    readonly: bool
    system: bool


class SaveConfig(BaseModel, validate_assignment=True):
    """
    Attributes:
        output_file: Path to the file where to save the attributes to
        working_path: Path where attributes will be collected from
        exclusions: List of exclusion rules
        ignore_files: List of files containing exclusion rules
        exclusions_ignore_case: Ignore case for exclusions
        relative: Store paths relative to the working path or full paths
        skip_links: Skip symbolic links and junctions
        no_print_excluded: Don't print excluded files/folders paths
        no_print_skipped: Don't print skipped files/folders paths
    """

    output_file: str
    working_path: str
    exclusions: list[str] | None
    ignore_files: list[str] | None
    exclusions_ignore_case: bool
    relative: bool
    skip_links: bool
    no_print_excluded: bool
    no_print_skipped: bool


class RestoreConfig(BaseModel, validate_assignment=True):
    """
    Attributes:
        input_file: Input file
        working_path: Directory where attributes will be applied to
        exclusions: List of exclusion rules
        ignore_files: List of files containing exclusion rules
        exclusions_ignore_case: Ignore case for exclusions
        no_print_modified: Don't print modified files
        no_print_skipped: Don't print skipped files
        no_print_excluded: Don't print excluded files
        copy_to_access: Copy the creation dates to accessed
        skip_permissions: Skip setting permissions
        skip_owner: Skip setting ownership
        skip_archive: Skip setting the archive attribute
        skip_hidden: Skip setting the hidden attribute
        skip_readonly: Skip setting the readonly attribute
        skip_system: Skip setting the system attribute
        skip_modified: Skip setting the modified timestamp
        skip_creation: Skip setting the creation timestamp
        skip_accessed: Skip setting the accessed timestamp
        skip_links: Skip symbolic links and junctions
    """

    input_file: str
    working_path: str
    exclusions: list[str] | None
    ignore_files: list[str] | None
    exclusions_ignore_case: bool
    no_print_modified: bool
    no_print_skipped: bool
    no_print_excluded: bool
    copy_to_access: bool
    skip_permissions: bool
    skip_owner: bool
    skip_archive: bool
    skip_hidden: bool
    skip_readonly: bool
    skip_system: bool
    skip_modified: bool
    skip_creation: bool
    skip_accessed: bool
    skip_links: bool


def get_path_content(path_to_scan: str,
                     relative: bool,
                     skip_links: bool,
                     no_print_skipped: bool) -> list[DirEntry]:
    if skip_links:
        path_content = []

        for item in os.scandir(path_to_scan):
            if item.is_symlink() or item.is_junction():
                if not no_print_skipped:
                    if relative:
                        print(SKIP_SYMLINK_TEMPLATE.substitute(path=item.path))
                    else:
                        print(SKIP_SYMLINK_TEMPLATE.substitute(path=os.path.abspath(item.path)))
                continue

            path_content.append(item)

        return path_content
    else:
        return [item for item in os.scandir(path_to_scan)]


def get_non_excluded_items(path_to_scan: str,
                           exclusion_rules: PathSpec | None,
                           exclusions_ignore_case: bool,
                           relative: bool,
                           skip_links: bool,
                           no_print_excluded: bool,
                           no_print_skipped: bool) -> list[DirEntry]:
    non_excluded_items = []
    items = get_path_content(path_to_scan=path_to_scan,
                             skip_links=False,
                             no_print_skipped=no_print_skipped,
                             relative=relative)

    for item in items:
        if skip_links and (item.is_symlink() or item.is_junction()):
            if not no_print_skipped:
                if relative:
                    print(SKIP_SYMLINK_TEMPLATE.substitute(path=item.path))
                else:
                    print(SKIP_SYMLINK_TEMPLATE.substitute(path=os.path.abspath(item.path)))
            continue

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


def get_paths(config: SaveConfig,
              initial_path: str) -> list[DirEntry]:
    matched_items: list[DirEntry] = []
    compiled_rules: PathSpec | None = compile_ignore_rules(ignore_files=config.ignore_files,
                                                           exclusions=config.exclusions,
                                                           exclusions_ignore_case=config.exclusions_ignore_case)

    if compiled_rules is None:
        alternative_items_list = get_path_content(path_to_scan=initial_path,
                                                  relative=config.relative,
                                                  skip_links=config.skip_links,
                                                  no_print_skipped=config.no_print_skipped)
    else:
        alternative_items_list = get_non_excluded_items(path_to_scan=initial_path,
                                                        exclusion_rules=compiled_rules,
                                                        exclusions_ignore_case=config.exclusions_ignore_case,
                                                        relative=config.relative,
                                                        skip_links=config.skip_links,
                                                        no_print_excluded=config.no_print_excluded,
                                                        no_print_skipped=config.no_print_skipped)

    matched_items += copy.copy(alternative_items_list)

    temp_items_list = []

    while True:
        for item in alternative_items_list:
            if item.is_dir() and not item.is_symlink() and not item.is_junction():
                if compiled_rules is not None:
                    temp_items_list += get_non_excluded_items(path_to_scan=item.path,
                                                              exclusion_rules=compiled_rules,
                                                              exclusions_ignore_case=config.exclusions_ignore_case,
                                                              relative=config.relative,
                                                              skip_links=config.skip_links,
                                                              no_print_excluded=config.no_print_excluded,
                                                              no_print_skipped=config.no_print_skipped)
                else:
                    temp_items_list += get_path_content(path_to_scan=item.path,
                                                        relative=config.relative,
                                                        skip_links=config.skip_links,
                                                        no_print_skipped=config.no_print_skipped)

        if len(temp_items_list) == 0:
            break

        matched_items += copy.copy(temp_items_list)

        alternative_items_list = copy.copy(temp_items_list)
        temp_items_list = []

    return matched_items


def collect_file_attrs(config: SaveConfig) -> None:
    print("\nCollecting item list, please wait...")

    file_attrs: dict[str, AttrData | WinAttrData] = {}

    paths: list[DirEntry] = get_paths(config=config,
                                      initial_path=os.curdir)

    print("\nCollecting attributes, please wait...")

    consecutive_errors = 0

    for item in paths:
        try:
            if consecutive_errors == 10:
                try:
                    print(f"\nToo many consecutive errors ({consecutive_errors}), aborting...")
                    if len(file_attrs) > 0:
                        write_attr_file(file_path=config.output_file,
                                        content=file_attrs)
                    sys.exit(GENERIC_ERROR)
                except KeyboardInterrupt:
                    print("Cancelling...")
                    sys.exit(GENERIC_ERROR)

            consecutive_errors = 0
            path = item.path

            if not config.relative:
                path = os.path.abspath(path)

            file_attrs[path] = get_attrs(path=item)
        except KeyboardInterrupt:
            try:
                print("\nShutdown requested... dumping what could be collected...\n")
                write_attr_file(file_path=config.output_file,
                                content=file_attrs)
                raise
            except KeyboardInterrupt:
                print("Cancelling...")
                raise
        except Exception as e:
            print(f"\n{e}", end="\n\n")
            consecutive_errors += 1

    write_attr_file(file_path=config.output_file,
                    content=file_attrs)


def write_attr_file(file_path: str,
                    content: dict[str, AttrData | WinAttrData]) -> None:
    with open(file_path, "wb") as attr_file:
        attr_file.write(orjson.dumps(content, option=orjson.OPT_INDENT_2))

    print(f"\nAttributes saved to \"{os.path.abspath(file_path)}\"")


def compile_ignore_rules(ignore_files: list[str] | None,
                         exclusions: list[str] | None,
                         exclusions_ignore_case: bool) -> PathSpec | None:
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
        file_attrs = WinAttrData(atime=0, mtime=0, ctime=0, archive=False, hidden=False, readonly=False, system=False)
    else:
        file_attrs = AttrData(atime=0, mtime=0, ctime=0, mode=0, uid=0, gid=0)

    file_attrs.ctime = file_info.st_birthtime_ns
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
                         skip_creation: bool) -> ResultAttr:
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

    stored_data.atime_changed = timestamp_changed(timestamp_1=getattr(current_file_info, a_attr),
                                                  timestamp_2=stored_data.atime)
    stored_data.mtime_changed = timestamp_changed(timestamp_1=getattr(current_file_info, m_attr),
                                                  timestamp_2=stored_data.mtime)

    if SYSTEM_PLATFORM == "windows":
        stored_data.ctime = attr.ctime

        if not skip_creation and stored_data.ctime > 0:
            stored_data.ctime_changed = timestamp_changed(timestamp_1=getattr(current_file_info, c_attr),
                                                          timestamp_2=stored_data.ctime)

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


def timestamp_changed(timestamp_1: float | int,
                      timestamp_2: float | int) -> bool:
    if isinstance(timestamp_1, float):
        timestamp_1 *= 1_000_000_000

    if isinstance(timestamp_2, float):
        timestamp_2 *= 1_000_000_000

    if SYSTEM_PLATFORM == "windows":
        return abs(timestamp_1 - timestamp_2) > 300
    else:
        return timestamp_1 != timestamp_2


def apply_file_attrs(attrs: dict[str, AttrData | WinAttrData | OldWinAttrData],
                     config: RestoreConfig) -> None:
    processed: bool = False
    errored: list[str] = []  # to store errored files/folders
    optional_args: dict[str, bool] = {}
    symlink_support = os.utime in os.supports_follow_symlinks or SYSTEM_PLATFORM == "windows"

    msg_uid_gid = Template("Updating $changed_ids for \"$path\"")
    msg_permissions = Template("Updating permissions for \"$path\"")
    msg_dates = Template("Updating $dates timestamp(s) for \"$path\"")
    msg_win_attribs = Template("Updating $win_attribs attribute(s) for \"$path\"")

    if symlink_support:
        optional_args["follow_symlinks"] = False

    compiled_rules: PathSpec | None = compile_ignore_rules(ignore_files=config.ignore_files,
                                                           exclusions=config.exclusions,
                                                           exclusions_ignore_case=config.exclusions_ignore_case)

    for item_path in sorted(attrs):
        try:
            if not os.path.lexists(item_path):
                if not config.no_print_skipped:
                    print(f"Skipping non-existent item \"{item_path}\"")
                continue

            attr: AttrData | WinAttrData | OldWinAttrData
            try:
                attr = AttrData.model_validate(attrs[item_path], strict=True)
            except ValidationError:
                try:
                    attr = WinAttrData.model_validate(attrs[item_path], strict=True)
                except ValidationError:
                    try:
                        attr = OldWinAttrData.model_validate(attrs[item_path], strict=True)
                    except ValidationError:
                        print(f"Attribute file is corrupt, aborting...\nError in path {item_path}")
                        sys.exit(ATTRIB_FILE_RELATED)

            comp_item_path = os.path.relpath(item_path, os.getcwd())

            if os.path.isdir(item_path):
                comp_item_path += os.path.sep

            if config.exclusions_ignore_case:
                comp_item_path = comp_item_path.lower()

            if compiled_rules is not None and compiled_rules.match_file(comp_item_path):
                if not config.no_print_excluded:
                    print(f"Skipping excluded path \"{item_path}\"")
                continue

            stored_data = get_attr_for_restore(attr=attr, path=item_path, skip_creation=config.skip_creation)

            if ((not os.path.islink(item_path) and not os.path.isjunction(item_path)) or
                    ((os.path.islink(item_path) or os.path.isjunction(item_path)) and
                     symlink_support and not config.skip_links)):
                if SYSTEM_PLATFORM != "windows":
                    # Does nothing in Windows
                    if set_uid_gid(item_path=item_path,
                                   stored_data=stored_data,
                                   no_print_modified=config.no_print_modified,
                                   skip_owner=config.skip_owner,
                                   msg_uid_gid=msg_uid_gid,
                                   optional_arg=optional_args):
                        processed = True

                    # st_mode on Windows is pretty useless, so we only perform this if the current OS is not Windows
                    if set_permissions(item_path=item_path,
                                       stored_data=stored_data,
                                       no_print_modified=config.no_print_modified,
                                       skip_permissions=config.skip_permissions,
                                       msg_permissions=msg_permissions,
                                       optional_arg=optional_args):
                        processed = True
                elif not stored_data.archive is None:
                    if process_win_attributes(item_path=item_path,
                                              stored_data=stored_data,
                                              skip_archive=config.skip_archive,
                                              skip_hidden=config.skip_hidden,
                                              skip_readonly=config.skip_readonly,
                                              skip_system=config.skip_system,
                                              no_print_modified=config.no_print_modified,
                                              errored=errored,
                                              msg_win_attribs=msg_win_attribs):
                        processed = True

                if set_timestamps(item_path=item_path,
                                  stored_data=stored_data,
                                  no_print_modified=config.no_print_modified,
                                  msg_dates=msg_dates,
                                  skip_modified=config.skip_modified,
                                  skip_creation=config.skip_creation,
                                  skip_accessed=config.skip_accessed,
                                  optional_arg=optional_args):
                    processed = True

                if copy_creation_to_accessed(item_path=item_path,
                                             stored_data=stored_data,
                                             copy_to_access=config.copy_to_access,
                                             optional_arg=optional_args):
                    processed = True
            elif not config.no_print_skipped:
                # Python doesn't support not following symlinks in this OS so we skip them
                print(SKIP_SYMLINK_TEMPLATE.substitute(path=item_path))
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
                   skip_modified: bool,
                   skip_creation: bool,
                   skip_accessed: bool,
                   optional_arg: dict[str, bool]) -> bool:
    changed_times = []
    something_changed = False

    if skip_creation and skip_accessed and skip_modified:
        return something_changed

    if stored_data.mtime_changed and not skip_modified:
        changed_times.append("modification")
        something_changed = True
    if stored_data.atime_changed and not skip_accessed:
        changed_times.append("accessed")
        something_changed = True
    if stored_data.ctime_changed and not skip_creation:
        changed_times.append("creation")
        something_changed = True

    if len(changed_times) != 0:
        if not no_print_modified:
            print(msg_dates.substitute(path=item_path, dates=" & ".join(changed_times)))

        if SYSTEM_PLATFORM == "windows":
            new_ctime: float | int | None = None
            if not skip_creation and stored_data.ctime_changed:
                new_ctime = stored_data.ctime

            new_mtime: float | int | None = None
            if not skip_modified and stored_data.mtime_changed:
                new_mtime = stored_data.mtime

            new_atime: float | int | None = None
            if not skip_accessed and stored_data.atime_changed:
                new_atime = stored_data.atime

            try:
                set_times(filepath=item_path,
                          ctime=new_ctime,
                          mtime=new_mtime,
                          atime=new_atime,
                          **optional_arg)
            except WindowsError as e:
                print(f"An error occurred while restoring the timestamps.\n{e}")
        else:
            if not (skip_modified and skip_accessed):
                if stored_data.mtime_changed or stored_data.atime_changed:
                    if type(stored_data.mtime) is int:
                        if skip_modified:
                            stored_data.mtime = os.lstat(item_path).st_mtime_ns

                        if skip_accessed:
                            stored_data.atime = os.lstat(item_path).st_atime_ns

                        os.utime(item_path, ns=(stored_data.atime, stored_data.mtime), **optional_arg)
                    else:
                        if skip_modified:
                            stored_data.mtime = os.lstat(item_path).st_mtime

                        if skip_accessed:
                            stored_data.atime = os.lstat(item_path).st_atime

                        os.utime(item_path, (stored_data.atime, stored_data.mtime), **optional_arg)

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
                           errored: list[str]) -> bool:
    changed_win_attribs: list[str] = []
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
                skip_owner: bool,
                msg_uid_gid: Template,
                optional_arg: dict[str, bool]) -> bool:
    if skip_owner:
        return False

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
                    skip_permissions: bool,
                    msg_permissions: Template,
                    optional_arg: dict[str, bool]) -> bool:
    if skip_permissions:
        return False

    if stored_data.mode_changed:
        if not no_print_modified:
            print(msg_permissions.substitute(path=item_path))

        os.chmod(item_path, stored_data.mode, **optional_arg)

        return True

    return False


def modify_win_attribs(path: str,
                       attribs_to_set: int,
                       attribs_to_unset: int) -> bool:
    try:
        current_attribs = get_win_attributes(path=path)
    except ctypes.WinError as e:
        print(e, end="\n\n")
        return False

    win_attribs = current_attribs | attribs_to_set
    win_attribs &= ~attribs_to_unset

    try:
        set_win_attributes(path=path, win_attributes=win_attribs)
        return True
    except ctypes.WinError as e:
        print(e, end="\n\n")
        return False


def get_win_attributes(path: str) -> int:
    attribs: int = ctypes.windll.kernel32.GetFileAttributesW(path)

    if attribs == -1:
        raise ctypes.WinError(ctypes.get_last_error())
    else:
        return attribs


def set_win_attributes(path: str,
                       win_attributes: int) -> None:
    if ctypes.windll.kernel32.SetFileAttributesW(path, win_attributes) == 0:
        raise ctypes.WinError(ctypes.get_last_error())


def save_attrs(config: SaveConfig) -> None:

    if SYSTEM_PLATFORM == "windows":
        if config.working_path.endswith("\""):
            print(f"Invalid character in working path: {config.working_path}", file=sys.stderr)
            sys.exit(FILE_RELATED)

        if config.output_file.endswith("\""):
            print(f"Invalid character in output file: {config.output_file}", file=sys.stderr)
            sys.exit(FILE_RELATED)

        if config.working_path.endswith(":"):
            config.working_path += os.path.sep

    if not os.path.exists(config.working_path):
        print(f"\nERROR: The specified working path doesn't exist, aborting...", file=sys.stderr)
        sys.exit(FILE_RELATED)

    has_drive: str = os.path.splitdrive(config.output_file)[0]
    if has_drive != "" and not os.path.exists(has_drive):
        print(f"\nERROR: The specified output drive doesn't exist, aborting...", file=sys.stderr)
        sys.exit(FILE_RELATED)

    if config.output_file.endswith(":"):
        config.output_file += os.path.sep

    if os.path.basename(config.output_file) != "" and os.path.isdir(config.output_file):
        print("ERROR: The output filename you specified is the same one of a directory, a directory and a file "
              "with the same name can't exist within the same path, aborting...")
        sys.exit(FILE_RELATED)

    if os.path.dirname(config.output_file) != "":
        if os.path.isfile(os.path.dirname(config.output_file)):
            print("ERROR: The output directory name you specified is the same one of a file, a directory and a file "
                  "with the same name can't exist within the same path, aborting...")
            sys.exit(FILE_RELATED)

        os.makedirs(os.path.dirname(config.output_file), exist_ok=True)
    else:
        if os.path.isdir(os.path.join(os.getcwd(), config.output_file)):
            print("ERROR: The output filename you specified is the same one of a directory, a directory and a file "
                  "with the same name can't exist within the same path, aborting...")
            sys.exit(FILE_RELATED)

    if os.path.basename(config.output_file) == "":
        config.output_file = os.path.join(config.output_file, DEFAULT_ATTR_FILENAME)

    reqstate: list[bool] = [config.relative,
                            config.working_path != os.curdir,
                            config.working_path != os.getcwd(),
                            os.path.dirname(config.output_file) == ""]

    if all(reqstate):
        config.output_file = os.path.abspath(config.output_file)

    os.chdir(config.working_path)

    try:
        collect_file_attrs(config=config)
    except OSError as ERR_W:
        print("ERROR: There was an error writing to the attribute file.\n\n", ERR_W, file=sys.stderr)
        sys.exit(FILE_RELATED)


def restore_attrs(config: RestoreConfig):
    if SYSTEM_PLATFORM == "windows" and config.input_file.endswith('"'):
        print(f"Invalid character in attribute file path: {config.input_file}", file=sys.stderr)
        sys.exit(FILE_RELATED)

    if os.path.basename(config.input_file) == "":
        config.input_file = os.path.join(config.input_file, DEFAULT_ATTR_FILENAME)

    if not os.path.exists(config.input_file):
        print(f"ERROR: Attribute file \"{config.input_file}\" not found", file=sys.stderr)
        sys.exit(FILE_RELATED)

    if os.path.isdir(config.input_file):
        print("ERROR: You have specified a directory for the input file, aborting...")
        sys.exit(FILE_RELATED)

    if os.path.getsize(config.input_file) == 0:
        print("ERROR: The attribute file is empty!", file=sys.stderr)
        sys.exit(FILE_RELATED)

    try:
        with open(config.input_file, "rb") as attr_file:
            attrs: dict[str, AttrData | WinAttrData | OldWinAttrData] = orjson.loads(attr_file.read())

        if len(attrs) == 0:
            print("ERROR: The attribute file is empty!", file=sys.stderr)
            sys.exit(FILE_RELATED)

        os.chdir(config.working_path)

        apply_file_attrs(attrs=attrs,
                         config=config)
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
                             help="Set the output file. (Default is \".saved-file-attrs\" in the current directory)",
                             metavar="%OUTPUT%",
                             default=DEFAULT_ATTR_FILENAME,
                             nargs="?")
    save_parser.add_argument("-wp", "--working-path",
                             help="Set the path to store attributes from. (Default is the current path)",
                             metavar="%PATH%",
                             default=os.curdir,
                             nargs="?")
    save_parser.add_argument("-ex", "--exclude",
                             help="Pattern rules to exclude, same format as git ignore rules.",
                             metavar="%PATTERN_RULE%",
                             nargs="*")
    save_parser.add_argument("-if", "--ignore-file",
                             help="File(s) containing pattern rules, same format as git ignore rules.",
                             metavar="%IGNORE-FILE%",
                             nargs="*")
    save_parser.add_argument("-eic", "--exclusions-ignore-case",
                             help="Ignore casing for exclusions.",
                             action="store_true")
    save_parser.add_argument("-r", "--relative",
                             help="Store the paths as relative instead of full paths.",
                             action="store_true")
    save_parser.add_argument("-sl", "--skip-links",
                             help="Skip symbolic links and junctions.",
                             action="store_true")
    save_parser.add_argument("--no-print-excluded",
                             help="Don't print excluded files and folders.",
                             action="store_true")
    save_parser.add_argument("--no-print-skipped",
                             help="Don't print skipped files and folders.",
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
                                help="Set the input file containing the attributes to restore. (Default is "
                                     "\".saved-file-attrs\" in the current directory)",
                                metavar="%INPUT%",
                                default=DEFAULT_ATTR_FILENAME,
                                nargs="?")
    restore_parser.add_argument("-wp", "--working-path",
                                help="Set the working path. The attributes will be applied to the contents of this "
                                     "path if they are relative, ignored otherwise. (Default is the current directory)",
                                metavar="%PATH%",
                                default=os.curdir,
                                nargs="?")
    restore_parser.add_argument("--no-print-modified",
                                help="Don't print modified files and folders.",
                                action="store_true")
    restore_parser.add_argument("--no-print-skipped",
                                help="Don't print skipped files and folders.",
                                action="store_true")
    restore_parser.add_argument("--no-print-excluded",
                                help="Don't print excluded files and folders.",
                                action="store_true")
    restore_parser.add_argument("-cta", "--copy-to-access",
                                help="Copy the creation dates to the accessed date.",
                                action="store_true")
    restore_parser.add_argument("-sp", "--skip-permissions",
                                help="Skip setting permissions.",
                                action="store_true")
    restore_parser.add_argument("-so", "--skip-owner",
                                help="Skip setting ownership.",
                                action="store_true")
    restore_parser.add_argument("-ex", "--exclude",
                                help="Pattern rules to exclude, same format as git ignore rules.",
                                metavar="%PATTERN_RULE%",
                                nargs="*")
    restore_parser.add_argument("-if", "--ignore-file",
                                help="File(s) containing pattern rules, same format as git ignore rules.",
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
    restore_parser.add_argument("-sc", "--skip-creation",
                                help="Skip setting the \"creation\" timestamp.",
                                action="store_true")
    restore_parser.add_argument("-sm", "--skip-modified",
                                help="Skip setting the \"modified\" timestamp.",
                                action="store_true")
    restore_parser.add_argument("-sac", "--skip-accessed",
                                help="Skip setting the \"accessed\" timestamp.",
                                action="store_true")
    restore_parser.add_argument("-sl", "--skip-links",
                                help="Skip symbolic links and junctions.",
                                action="store_true")

    args = parser.parse_args()

    mode: str = args.mode

    if mode is None:
        print("You have to use either save or restore.\nRead the help.")
        sys.exit(GENERIC_ERROR)

    if args.ignore_file is not None:
        for file in args.ignore_file:
            if not os.path.isfile(file):
                print("Specified ignore filepath is not a file or doesn't exist, exiting...")
                sys.exit(FILE_RELATED)

    if mode == "save":
        config = SaveConfig(output_file=args.output,
                            working_path=args.working_path,
                            exclusions=args.exclude,
                            ignore_files=args.ignore_file,
                            exclusions_ignore_case=args.exclusions_ignore_case,
                            relative=args.relative,
                            skip_links=args.skip_links,
                            no_print_excluded=args.no_print_excluded,
                            no_print_skipped=args.no_print_skipped)

        save_attrs(config=config)

    if mode == "restore":
        config = RestoreConfig(input_file=args.input,
                               working_path=args.working_path,
                               exclusions=args.exclude,
                               ignore_files=args.ignore_file,
                               exclusions_ignore_case=args.exclusions_ignore_case,
                               no_print_modified=args.no_print_modified,
                               no_print_skipped=args.no_print_skipped,
                               no_print_excluded=args.no_print_excluded,
                               copy_to_access=args.copy_to_access,
                               skip_permissions=args.skip_permissions,
                               skip_owner=args.skip_owner,
                               skip_archive=args.skip_archive,
                               skip_hidden=args.skip_hidden,
                               skip_readonly=args.skip_readonly,
                               skip_system=args.skip_system,
                               skip_modified=args.skip_modified,
                               skip_accessed=args.skip_accessed,
                               skip_creation=args.skip_creation,
                               skip_links=args.skip_links)

        restore_attrs(config=config)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Exiting...")
        sys.exit(USER_INTERRUPTED)
