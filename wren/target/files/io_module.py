"""Ported from io.h, io.c, and io.wren.

The original implements `File`, `Directory`, `Stat`, `Stdin`, and `Stdout`
as Wren foreign classes backed by libuv's async filesystem API
(uv_fs_open, uv_fs_read, uv_fs_scandir, uv_tty_*, ...). Every blocking
filesystem call there completes via a callback that resumes a suspended
Wren fiber through the Scheduler.

This port keeps the same classes and method names. Filesystem calls are
run on a thread-pool executor via `asyncio` (mirroring the "doesn't block
the event loop" property of the original libuv calls); `Stdin` raw-mode
handling uses `termios`/`tty` in place of `uv_tty_set_mode`.
"""

import asyncio
import os
import stat as stat_module
import sys

try:
    import termios
    import tty
    _HAS_TERMIOS = True
except ImportError:
    # termios/tty are POSIX-only (mirrors the original's `#if __APPLE__` /
    # POSIX-specific code paths -- Windows raw mode isn't handled here,
    # same as it wasn't fully handled in the portable parts of io.c).
    _HAS_TERMIOS = False


# Originally: FileFlags in io.wren, mapped to OS flags via mapFileFlags() in
# io.c. Values must stay in sync between the two, same note as the original.
class FileFlags:
    READ = 0x01
    WRITE = 0x02
    READ_WRITE = 0x04
    SYNC = 0x08
    CREATE = 0x10
    TRUNCATE = 0x20
    EXCLUSIVE = 0x40


def _map_file_flags(flags):
    # Originally: mapFileFlags() in io.c.
    result = 0
    if flags & FileFlags.READ:
        result |= os.O_RDONLY
    if flags & FileFlags.WRITE:
        result |= os.O_WRONLY
    if flags & FileFlags.READ_WRITE:
        result |= os.O_RDWR
    if flags & FileFlags.SYNC:
        result |= getattr(os, "O_SYNC", 0)
    if flags & FileFlags.CREATE:
        result |= os.O_CREAT
    if flags & FileFlags.TRUNCATE:
        result |= os.O_TRUNC
    if flags & FileFlags.EXCLUSIVE:
        result |= os.O_EXCL
    return result


async def _run(func, *args):
    """Runs a blocking call off the event loop thread.

    Stands in for the original's libuv thread-pool dispatch used by every
    uv_fs_* call in io.c.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


class Stat:
    """Ported from the `Stat` foreign class in io.wren, backed by
    statBlockCount() / statSize() / statIsDirectory() / etc. in io.c.
    """

    def __init__(self, stat_result):
        self._stat = stat_result

    @property
    def block_count(self):
        # Originally: statBlockCount() -> st_blocks.
        return getattr(self._stat, "st_blocks", 0)

    @property
    def block_size(self):
        # Originally: statBlockSize() -> st_blksize.
        return getattr(self._stat, "st_blksize", 0)

    @property
    def device(self):
        # Originally: statDevice() -> st_dev.
        return self._stat.st_dev

    @property
    def group(self):
        # Originally: statGroup() -> st_gid.
        return self._stat.st_gid

    @property
    def inode(self):
        # Originally: statInode() -> st_ino.
        return self._stat.st_ino

    @property
    def link_count(self):
        # Originally: statLinkCount() -> st_nlink.
        return self._stat.st_nlink

    @property
    def mode(self):
        # Originally: statMode() -> st_mode.
        return self._stat.st_mode

    @property
    def size(self):
        # Originally: statSize() -> st_size.
        return self._stat.st_size

    @property
    def special_device(self):
        # Originally: statSpecialDevice() -> st_rdev.
        return getattr(self._stat, "st_rdev", 0)

    @property
    def user(self):
        # Originally: statUser() -> st_uid.
        return self._stat.st_uid

    @property
    def is_directory(self):
        # Originally: statIsDirectory() -> S_ISDIR(st_mode).
        return stat_module.S_ISDIR(self._stat.st_mode)

    @property
    def is_file(self):
        # Originally: statIsFile() -> S_ISREG(st_mode).
        return stat_module.S_ISREG(self._stat.st_mode)

    @staticmethod
    async def path(path):
        # Originally: statPath() -> uv_fs_stat().
        result = await _run(os.stat, path)
        return Stat(result)


class Directory:
    """Ported from directoryList() / directoryCreate() / directoryDelete()
    in io.c (the `Directory` foreign class declared in io.wren).
    """

    @staticmethod
    async def list(path):
        # Originally: directoryList() -> uv_fs_scandir().
        return await _run(os.listdir, path)

    @staticmethod
    async def create(path):
        # Originally: directoryCreate() -> uv_fs_mkdir().
        await _run(os.mkdir, path)

    @staticmethod
    async def delete(path):
        # Originally: directoryDelete() -> uv_fs_rmdir().
        await _run(os.rmdir, path)


class File:
    """Ported from the `File` foreign class in io.wren, backed by
    fileAllocate() / fileOpen() / fileClose() / fileReadBytes() / etc. in
    io.c.

    The original stores the raw file descriptor as foreign data and closes
    it from `fileFinalize()`, a finalizer invoked when the Wren object is
    garbage collected. Python doesn't guarantee finalizer timing either, so
    prefer calling `close()` explicitly (this class also finalizes on `del`
    as a best-effort fallback, matching the intent of fileFinalize()).
    """

    def __init__(self, fd):
        # Originally: fileAllocate().
        self._fd = fd

    @staticmethod
    async def open(path, flags):
        # Originally: fileOpen() -> uv_fs_open().
        real_flags = _map_file_flags(flags)
        # TODO: Allow controlling access (same TODO as in the original).
        fd = await _run(lambda: os.open(path, real_flags, 0o600))
        return File(fd)

    @staticmethod
    async def delete(path):
        # Originally: fileDelete() -> uv_fs_unlink().
        await _run(os.unlink, path)

    @staticmethod
    async def real_path(path):
        # Originally: fileRealPath() -> uv_fs_realpath().
        return await _run(os.path.realpath, path)

    @staticmethod
    async def size_path(path):
        # Originally: fileSizePath() -> uv_fs_stat().st_size.
        result = await _run(os.stat, path)
        return result.st_size

    @property
    def descriptor(self):
        # Originally: fileDescriptor().
        return self._fd

    async def close(self):
        # Originally: fileClose() -> uv_fs_close().
        if self._fd == -1:
            return True

        fd, self._fd = self._fd, -1
        await _run(os.close, fd)
        return False

    async def stat(self):
        # Originally: fileStat() -> uv_fs_fstat().
        result = await _run(os.fstat, self._fd)
        return Stat(result)

    async def size(self):
        # Originally: fileSize() -> uv_fs_fstat().st_size.
        s = await self.stat()
        return s.size

    async def read_bytes(self, length, offset):
        # Originally: fileReadBytes() -> uv_fs_read().
        def _read():
            os.lseek(self._fd, offset, os.SEEK_SET)
            return os.read(self._fd, length)

        return await _run(_read)

    async def write_bytes(self, data, offset):
        # Originally: fileWriteBytes() -> uv_fs_write().
        def _write():
            os.lseek(self._fd, offset, os.SEEK_SET)
            os.write(self._fd, data)

        await _run(_write)

    def __del__(self):
        # Best-effort mirror of fileFinalize() in io.c.
        fd = getattr(self, "_fd", -1)
        if fd != -1:
            try:
                os.close(fd)
            except OSError:
                pass


class Stdin:
    """Ported from the `Stdin` foreign class in io.wren, backed by
    stdinIsRaw() / stdinIsRawSet() / stdinIsTerminal() / stdinReadStart() /
    stdinReadStop() in io.c.

    The original reads stdin asynchronously via libuv and dispatches each
    chunk to a Wren `onData_()` callback. The REPL (the only consumer in
    this codebase) actually wants synchronous byte-at-a-time reads, so this
    port exposes `read_byte()` directly instead of a callback.
    """

    _is_raw = False
    _saved_settings = None

    @staticmethod
    def is_raw():
        # Originally: stdinIsRaw().
        return Stdin._is_raw

    @staticmethod
    def set_raw(value):
        # Originally: stdinIsRawSet() -> uv_tty_set_mode().
        Stdin._is_raw = value

        if not (_HAS_TERMIOS and sys.stdin.isatty()):
            # Can't set raw mode when not talking to a TTY.
            # TODO: Make this a runtime error? (same TODO as the original)
            return

        fd = sys.stdin.fileno()
        if value:
            Stdin._saved_settings = termios.tcgetattr(fd)
            tty.setraw(fd)
        elif Stdin._saved_settings is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, Stdin._saved_settings)
            Stdin._saved_settings = None

    @staticmethod
    def is_terminal():
        # Originally: stdinIsTerminal() -> uv_guess_handle() == UV_TTY.
        return sys.stdin.isatty()

    @staticmethod
    def read_byte():
        # Originally driven by stdinReadStart()/stdinReadCallback(), which
        # delivered bytes asynchronously via onData_(). Simplified to a
        # direct blocking read since every caller in this codebase (the
        # REPL) consumes stdin one byte at a time synchronously anyway.
        byte = sys.stdin.buffer.read(1)
        return byte[0] if byte else None

    @staticmethod
    def shutdown():
        # Originally: shutdownStdin() in io.c -- resets tty mode, closes
        # the stream, releases handles.
        if Stdin._is_raw:
            Stdin.set_raw(False)


class Stdout:
    """Ported from the `Stdout` foreign class in io.wren, backed by
    stdoutFlush() in io.c.
    """

    @staticmethod
    def flush():
        # Originally: stdoutFlush().
        sys.stdout.flush()


def io_shutdown():
    """Frees up any pending resources in use by the IO module.

    Originally: ioShutdown() in io.h/io.c -- in particular, this closes
    down the stdin stream.
    """
    Stdin.shutdown()
