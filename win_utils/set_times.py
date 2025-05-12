# Based on win32-setctime module by Delgan
import os
import sys

try:
    from ctypes import byref, get_last_error, wintypes, FormatError, WinDLL, WinError
    from ctypes.wintypes import FILETIME, HANDLE

    kernel32: WinDLL = WinDLL("kernel32", use_last_error=True)

    CreateFileW = kernel32.CreateFileW
    SetFileTime = kernel32.SetFileTime
    CloseHandle = kernel32.CloseHandle

    CreateFileW.argtypes = (
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    CreateFileW.restype = wintypes.HANDLE

    SetFileTime.argtypes = (
        wintypes.HANDLE,
        wintypes.PFILETIME,
        wintypes.PFILETIME,
        wintypes.PFILETIME,
    )
    SetFileTime.restype = wintypes.BOOL

    CloseHandle.argtypes = (wintypes.HANDLE,)
    CloseHandle.restype = wintypes.BOOL
except (ImportError, AttributeError, OSError, ValueError):
    SUPPORTED: bool = False
else:
    SUPPORTED = os.name == "nt"

if sys.version_info >= (3, 6):
    PathLike = os.PathLike
else:
    raise RuntimeError("Python version must be 3.6+")

from typing import Union


def set_times(filepath: Union[str, PathLike],
              *,
              ctime: Union[float, int] = None,
              mtime: Union[float, int] = None,
              atime: Union[float, int] = None,
              follow_symlinks: bool = False) -> None:
    """Set the modified, accessed and creation times attribute of a file given an unix timestamp (Windows only)."""

    if not SUPPORTED:
        raise OSError("This function is only available for the Windows platform.")

    if ctime is None and mtime is None and atime is None:
        raise ValueError("No timestamp given.")

    file_path: str = "\\\\?\\" + os.path.normpath(os.path.abspath(str(filepath)))

    win_ctime: FILETIME = _convert_time(time=ctime)
    win_mtime: FILETIME = _convert_time(time=mtime)
    win_atime: FILETIME = _convert_time(time=atime)

    flags: int = 128 | 0x02000000

    if not follow_symlinks:
        flags |= 0x00200000

    handle: HANDLE = wintypes.HANDLE(CreateFileW(file_path, 256, 0, None, 3, flags, None))
    if handle.value == wintypes.HANDLE(-1).value:
        raise WinError(get_last_error())
    try:
        if not wintypes.BOOL(SetFileTime(handle, byref(win_ctime), byref(win_atime), byref(win_mtime))):
            raise WinError(get_last_error())
    finally:
        CloseHandle(handle)


def _convert_time(time: Union[float, int, None]) -> FILETIME:
    if type(time) is float:
        result_time = int(time * 10000000) + 116444736000000000
    elif type(time) is int:
        result_time = int(time / 100) + 116444736000000000
    elif time is None:
        return wintypes.FILETIME(0xFFFFFFFF, 0xFFFFFFFF)
    else:
        raise TypeError(f"Expected int or float, got {type(time).__name__}")

    if not 0 < result_time < (1 << 64):
        raise ValueError(f"The system value of the timestamp exceeds u64 size: {result_time}")

    return wintypes.FILETIME(result_time & 0xFFFFFFFF, result_time >> 32)
