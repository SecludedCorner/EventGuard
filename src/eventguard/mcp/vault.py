"""Current-user DPAPI storage. No plaintext or non-Windows fallback exists."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import threading
import uuid


_REF = re.compile(r"v1_[0-9a-f]{32}\Z")
_MAGIC = b"EGDP1\x00"
_MAX_CIPHERTEXT = 16384


class _Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


class _Attributes(ctypes.Structure):
    _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]


class DPAPIVault:
    """Bounded encrypted files identified only by generated opaque references.

    Directory ancestors are opened without following reparse points and held
    without delete sharing during access. A directory lock serializes writers
    across processes. DPAPI uses CRYPTPROTECT_UI_FORBIDDEN, never LOCAL_MACHINE.
    This prevents plaintext storage; it cannot protect against the same account
    already running arbitrary code. Reference UUIDs are identifiers, not keys.
    """

    def __init__(self, directory):
        if os.name != "nt":
            raise OSError("vault_platform_unsupported")
        path = Path(directory)
        if ".." in path.parts:
            raise ValueError("invalid_vault_directory")
        self.directory = path.absolute()
        # No UNC/network shares, device namespaces, alternate streams or a
        # filesystem root: a vault must be a local ordinary subdirectory.
        if (len(self.directory.drive) != 2 or self.directory.drive[1] != ":"
                or len(self.directory.parts) < 2
                or any(":" in part or "\x00" in part for part in self.directory.parts[1:])):
            raise ValueError("invalid_vault_directory")
        self._lock = threading.Lock()
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
        self._kernel.GetDriveTypeW.restype = wintypes.UINT
        if self._kernel.GetDriveTypeW(self.directory.anchor) != 3:  # DRIVE_FIXED
            raise ValueError("invalid_vault_directory")
        self._crypt = ctypes.WinDLL("crypt32", use_last_error=True)
        self._kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                           ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self._kernel.CreateFileW.restype = wintypes.HANDLE
        self._kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                           ctypes.c_void_p, wintypes.DWORD]
        self._kernel.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                         ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        self._kernel.WriteFile.argtypes = self._kernel.ReadFile.argtypes
        self._kernel.GetFileSizeEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong)]
        self._kernel.FlushFileBuffers.argtypes = [wintypes.HANDLE]
        self._kernel.LocalFree.argtypes = [ctypes.c_void_p]
        self._kernel.LocalFree.restype = ctypes.c_void_p
        signature = [ctypes.POINTER(_Blob), wintypes.LPCWSTR, ctypes.POINTER(_Blob), ctypes.c_void_p,
                     ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
        self._crypt.CryptProtectData.argtypes = signature
        self._crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p,
                                                  ctypes.POINTER(_Blob), ctypes.c_void_p,
                                                  ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]

    def _open(self, path, access, sharing, creation, flags):
        handle = self._kernel.CreateFileW(str(path), access, sharing, None, creation, flags, None)
        if handle == ctypes.c_void_p(-1).value:
            raise OSError("vault_access_failed")
        attributes = _Attributes()
        if (not self._kernel.GetFileInformationByHandleEx(handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes))
                or attributes.attributes & 0x400):
            self._kernel.CloseHandle(handle)
            raise OSError("vault_reparse_refused")
        return handle

    @contextmanager
    def _guard(self, create):
        handles = []
        try:
            try:
                path = Path(self.directory.anchor)
                components = [path]
                for part in self.directory.parts[1:]:
                    path = path / part
                    components.append(path)
                for path in components:
                    if create:
                        # Parents held without delete-sharing cannot be swapped.
                        try:
                            path.lstat()
                        except FileNotFoundError:
                            path.mkdir()
                    handles.append(self._open(path, 0x80, 3, 3, 0x02000000 | 0x00200000))
            except (ValueError, OSError):
                raise OSError("vault_access_failed") from None
            yield
        finally:
            for handle in reversed(handles):
                self._kernel.CloseHandle(handle)

    def _transform(self, payload, decrypt=False):
        buffer = ctypes.create_string_buffer(payload)
        incoming = _Blob(len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
        outgoing = _Blob()
        try:
            function = self._crypt.CryptUnprotectData if decrypt else self._crypt.CryptProtectData
            if not function(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
                raise OSError("vault_crypto_failed")
            if not 1 <= outgoing.size <= _MAX_CIPHERTEXT:
                raise OSError("vault_crypto_failed")
            return ctypes.string_at(outgoing.data, outgoing.size)
        finally:
            ctypes.memset(buffer, 0, len(payload))
            if outgoing.data:
                ctypes.memset(outgoing.data, 0, outgoing.size)
                self._kernel.LocalFree(outgoing.data)

    def put(self, secret: str) -> str:
        if not isinstance(secret, str) or not 1 <= len(secret) <= 4096:
            raise ValueError("invalid_vault_secret")
        try:
            encoded = secret.encode("utf-8")
        except UnicodeError:
            raise ValueError("invalid_vault_secret") from None
        if len(encoded) > 4096:
            raise ValueError("invalid_vault_secret")
        with self._lock, self._guard(True):
            # Persistent empty lock file is not a credential; share=0 fails closed
            # while another process is operating. It is never a plaintext store.
            lock = self._open(self.directory / ".vault.lock", 0x80000000 | 0x40000000, 0, 4, 0x00200000)
            handle = None
            try:
                count = 0
                for entry in self.directory.iterdir():
                    if entry.name != ".vault.lock":
                        count += 1
                    if count >= 128:
                        raise OSError("vault_capacity_reached")
                payload = _MAGIC + self._transform(encoded)
                reference = "v1_" + uuid.uuid4().hex
                handle = self._open(self.directory / (reference + ".bin"), 0x40000000, 0, 1, 0x00200000 | 0x80)
                written = wintypes.DWORD()
                if (not self._kernel.WriteFile(handle, payload, len(payload), ctypes.byref(written), None)
                        or written.value != len(payload) or not self._kernel.FlushFileBuffers(handle)):
                    raise OSError("vault_write_failed")
                return reference
            except OSError as exc:
                code = str(exc)
                raise OSError(code if code in {"vault_capacity_reached", "vault_crypto_failed", "vault_write_failed"}
                              else "vault_access_failed") from None
            finally:
                if handle is not None:
                    self._kernel.CloseHandle(handle)
                self._kernel.CloseHandle(lock)

    def get(self, reference: str) -> str:
        if not isinstance(reference, str) or not _REF.fullmatch(reference):
            raise ValueError("invalid_vault_reference")
        with self._lock, self._guard(False):
            handle = self._open(self.directory / (reference + ".bin"), 0x80000000, 0, 3, 0x00200000)
            try:
                size = ctypes.c_longlong()
                if (not self._kernel.GetFileSizeEx(handle, ctypes.byref(size))
                        or not len(_MAGIC) < size.value <= _MAX_CIPHERTEXT + len(_MAGIC)):
                    raise OSError
                buffer = ctypes.create_string_buffer(size.value)
                count = wintypes.DWORD()
                if (not self._kernel.ReadFile(handle, buffer, size.value, ctypes.byref(count), None)
                        or count.value != size.value or not buffer.raw.startswith(_MAGIC)):
                    raise OSError
                plain = self._transform(buffer.raw[len(_MAGIC):], decrypt=True)
                if not 1 <= len(plain) <= 4096:
                    raise OSError
                return plain.decode("utf-8")
            except (OSError, UnicodeError):
                raise OSError("vault_read_failed") from None
            finally:
                self._kernel.CloseHandle(handle)
