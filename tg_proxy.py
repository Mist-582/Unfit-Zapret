from __future__ import annotations

import asyncio
import base64
import ctypes
import ctypes.util
import hashlib
import http.client
import os
import random
import re
import socket as _socket
import ssl
import struct
import sys
import threading
import time
import urllib.request
from typing import Optional

try:
    from cryptography.hazmat.primitives.ciphers import (
        Cipher as _CryptoCipher,
        algorithms as _CryptoAlg,
        modes as _CryptoModes,
    )
    _HAS_CRYPTOGRAPHY = True
except ImportError:
    _HAS_CRYPTOGRAPHY = False

try:
    import certifi
except ImportError:
    certifi = None


HANDSHAKE_LEN = 64
SKIP_LEN = 8
PREKEY_LEN = 32
IV_LEN = 16
PROTO_TAG_POS = 56
DC_IDX_POS = 60

PROTO_TAG_ABRIDGED = b"\xef\xef\xef\xef"
PROTO_TAG_INTERMEDIATE = b"\xee\xee\xee\xee"
PROTO_TAG_SECURE = b"\xdd\xdd\xdd\xdd"

PROTO_ABRIDGED_INT = 0xEFEFEFEF
PROTO_INTERMEDIATE_INT = 0xEEEEEEEE
PROTO_PADDED_INTERMEDIATE_INT = 0xDDDDDDDD

RESERVED_STARTS = {
    b"HEAD",
    b"POST",
    b"GET ",
    b"OPTI",
    b"\xee\xee\xee\xee",
    b"\xdd\xdd\xdd\xdd",
    b"\x16\x03\x01\x02",
}

WS_DIRECT_IPS: dict[int, str] = {
    2: "149.154.167.220",
    4: "149.154.167.220",
}

DC_DEFAULT_IPS: dict[int, str] = {
    1: "149.154.175.50",
    2: "149.154.167.51",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "149.154.171.5",
    203: "91.105.192.100",
}

DC_TEST_IPS: dict[int, str] = {
    1: "149.154.175.10",
    2: "149.154.167.40",
    3: "149.154.175.117",
}

CFPROXY_DOMAINS_URL = (
    "https://raw.githubusercontent.com/Flowseal/tg-ws-proxy/main"
    "/.github/cfproxy-domains.txt"
)

_CFPROXY_ENC = [
    "virkgj.com",
    "vmmzovy.com",
    "mkuosckvso.com",
    "zaewayzmplad.com",
    "twdmbzcm.com",
    "awzwsldi.com",
    "clngqrflngqin.com",
    "tjacxbqtj.com",
    "bxaxtxmrw.com",
    "dmohrsgmohcrwb.com",
    "vwbmtmoi.com",
    "khgrre.com",
    "ulihssf.com",
    "tmhqsdqmfpmk.com",
    "xwuwoqbm.com",
    "orgcnunpj.com",
    "zhkuldz.com",
    "zypoljnslxa.com",
    "efabnxaowuzs.com",
    "zaftuzsftqdq.com",
]
_CF_SUFFIX = ".co.uk"


def _decode_cf_domain(s: str) -> str:
    if not s.endswith(".com"):
        return s
    p = s[:-4]
    n = sum(1 for c in p if c.isalpha())
    out = []
    for c in p:
        if c.isalpha():
            base = 97 if c > "`" else 65
            out.append(chr((ord(c) - base - n) % 26 + base))
        else:
            out.append(c)
    return "".join(out) + _CF_SUFFIX


CFPROXY_DEFAULT_DOMAINS: list[str] = [_decode_cf_domain(d) for d in _CFPROXY_ENC]

_AES_SBOX = (
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
)
_AES_RCON = (0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)


def _xtime(a: int) -> int:
    return ((a << 1) ^ 0x1B) & 0xFF if (a & 0x80) else (a << 1)


def _aes_expand_key_256(key: bytes) -> list[list[int]]:
    w: list[int] = [int.from_bytes(key[4 * i:4 * i + 4], "big") for i in range(8)]
    for i in range(8, 60):
        temp = w[i - 1]
        if i % 8 == 0:
            rot = ((temp << 8) | (temp >> 24)) & 0xFFFFFFFF
            sub = (
                (_AES_SBOX[(rot >> 24) & 0xFF] << 24)
                | (_AES_SBOX[(rot >> 16) & 0xFF] << 16)
                | (_AES_SBOX[(rot >> 8) & 0xFF] << 8)
                | _AES_SBOX[rot & 0xFF]
            )
            temp = sub ^ (_AES_RCON[i // 8] << 24)
        elif i % 8 == 4:
            temp = (
                (_AES_SBOX[(temp >> 24) & 0xFF] << 24)
                | (_AES_SBOX[(temp >> 16) & 0xFF] << 16)
                | (_AES_SBOX[(temp >> 8) & 0xFF] << 8)
                | _AES_SBOX[temp & 0xFF]
            )
        w.append(w[i - 8] ^ temp)
    rounds: list[list[int]] = []
    for r in range(15):
        rk: list[int] = []
        for c in range(4):
            word = w[r * 4 + c]
            rk.extend(((word >> 24) & 0xFF, (word >> 16) & 0xFF, (word >> 8) & 0xFF, word & 0xFF))
        rounds.append(rk)
    return rounds


def _aes_encrypt_block_256(block: bytearray, round_keys: list[list[int]]) -> bytes:
    s = [block[i] ^ round_keys[0][i] for i in range(16)]
    sbox = _AES_SBOX
    for rnd in range(1, 14):
        s = [sbox[x] for x in s]
        s[1], s[5], s[9], s[13] = s[5], s[9], s[13], s[1]
        s[2], s[6], s[10], s[14] = s[10], s[14], s[2], s[6]
        s[3], s[7], s[11], s[15] = s[15], s[3], s[7], s[11]
        rk = round_keys[rnd]
        for c in range(0, 16, 4):
            a0, a1, a2, a3 = s[c], s[c + 1], s[c + 2], s[c + 3]
            t = a0 ^ a1 ^ a2 ^ a3
            s[c] = a0 ^ t ^ _xtime(a0 ^ a1) ^ rk[c]
            s[c + 1] = a1 ^ t ^ _xtime(a1 ^ a2) ^ rk[c + 1]
            s[c + 2] = a2 ^ t ^ _xtime(a2 ^ a3) ^ rk[c + 2]
            s[c + 3] = a3 ^ t ^ _xtime(a3 ^ a0) ^ rk[c + 3]
    s = [sbox[x] for x in s]
    s[1], s[5], s[9], s[13] = s[5], s[9], s[13], s[1]
    s[2], s[6], s[10], s[14] = s[10], s[14], s[2], s[6]
    s[3], s[7], s[11], s[15] = s[15], s[3], s[7], s[11]
    rk = round_keys[14]
    return bytes(s[i] ^ rk[i] for i in range(16))


class _PureAesCtr:
    def __init__(self, key: bytes, iv: bytes):
        if len(key) != 32 or len(iv) != 16:
            raise ValueError("AES-256-CTR requires 32-byte key and 16-byte iv")
        self._rk = _aes_expand_key_256(key)
        self._ctr = bytearray(iv)
        self._buf = b""
        self._pos = 16

    def _next_keystream_block(self) -> bytes:
        ks = _aes_encrypt_block_256(self._ctr, self._rk)
        for i in range(15, -1, -1):
            v = self._ctr[i] + 1
            if v <= 255:
                self._ctr[i] = v
                break
            self._ctr[i] = 0
        return ks

    def update(self, data: bytes) -> bytes:
        if not data:
            return b""
        out = bytearray(len(data))
        pos = self._pos
        buf = self._buf
        for idx, b in enumerate(data):
            if pos >= 16:
                buf = self._next_keystream_block()
                pos = 0
            out[idx] = b ^ buf[pos]
            pos += 1
        self._pos = pos
        self._buf = buf
        return bytes(out)


def _init_libcrypto():
    candidates = []
    found = ctypes.util.find_library("crypto")
    if found:
        candidates.append(found)
    candidates.extend([
        "libcrypto.so.3",
        "libcrypto.so.1.1",
        "libcrypto.so.1.0.0",
        "libcrypto.so",
    ])
    for name in candidates:
        try:
            lib = ctypes.CDLL(name)
            lib.EVP_CIPHER_CTX_new.restype = ctypes.c_void_p
            lib.EVP_CIPHER_CTX_free.argtypes = [ctypes.c_void_p]
            lib.EVP_aes_256_ctr.restype = ctypes.c_void_p
            lib.EVP_EncryptInit_ex.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.c_char_p,
            ]
            lib.EVP_EncryptInit_ex.restype = ctypes.c_int
            lib.EVP_EncryptUpdate.argtypes = [
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_int),
                ctypes.c_char_p,
                ctypes.c_int,
            ]
            lib.EVP_EncryptUpdate.restype = ctypes.c_int
            return lib
        except OSError:
            continue
    return None


_LIBCRYPTO = None if _HAS_CRYPTOGRAPHY else _init_libcrypto()


class _LibCryptoCtr:
    def __init__(self, key: bytes, iv: bytes):
        ctx = _LIBCRYPTO.EVP_CIPHER_CTX_new()
        if not ctx:
            raise RuntimeError("EVP_CIPHER_CTX_new failed")
        self._ctx = ctx
        if _LIBCRYPTO.EVP_EncryptInit_ex(ctx, _LIBCRYPTO.EVP_aes_256_ctr(), None, key, iv) != 1:
            _LIBCRYPTO.EVP_CIPHER_CTX_free(ctx)
            self._ctx = None
            raise RuntimeError("EVP_EncryptInit_ex failed")

    def update(self, data: bytes) -> bytes:
        if not data:
            return b""
        outlen = ctypes.c_int(0)
        buf = ctypes.create_string_buffer(len(data) + 16)
        if _LIBCRYPTO.EVP_EncryptUpdate(self._ctx, buf, ctypes.byref(outlen), data, len(data)) != 1:
            raise RuntimeError("EVP_EncryptUpdate failed")
        return buf.raw[:outlen.value]

    def __del__(self):
        ctx = getattr(self, "_ctx", None)
        if ctx and _LIBCRYPTO is not None:
            _LIBCRYPTO.EVP_CIPHER_CTX_free(ctx)
            self._ctx = None


def create_aes_ctr(key: bytes, iv: bytes):
    if _HAS_CRYPTOGRAPHY:
        return _CryptoCipher(_CryptoAlg.AES(key), _CryptoModes.CTR(iv)).encryptor()
    if _LIBCRYPTO is not None:
        return _LibCryptoCtr(key, iv)
    return _PureAesCtr(key, iv)


_XOR_TABLES = tuple(bytes(v ^ k for v in range(256)) for k in range(256))
_st_BB = struct.Struct(">BB")
_st_BBH = struct.Struct(">BBH")
_st_BBQ = struct.Struct(">BBQ")
_st_BB4s = struct.Struct(">BB4s")
_st_BBH4s = struct.Struct(">BBH4s")
_st_BBQ4s = struct.Struct(">BBQ4s")
_st_H = struct.Struct(">H")
_st_Q = struct.Struct(">Q")
_st_I_le = struct.Struct("<I")


def _xor_mask(data: bytes, mask: bytes) -> bytes:
    if not data:
        return data
    n = len(data)
    if n >= 512:
        masked = bytearray(data)
        for offset in range(4):
            masked[offset::4] = masked[offset::4].translate(_XOR_TABLES[mask[offset]])
        return bytes(masked)
    mask_rep = (mask * (n // 4 + 1))[:n]
    return (int.from_bytes(data, "big") ^ int.from_bytes(mask_rep, "big")).to_bytes(n, "big")


def _create_ssl_context(check_hostname: bool = True) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if certifi is not None:
        try:
            ctx.load_verify_locations(cafile=certifi.where())
        except Exception:
            pass
    try:
        ctx.set_ecdh_curve("X25519")
    except Exception:
        pass
    ctx.check_hostname = check_hostname
    return ctx


_SSL_CTX = _create_ssl_context(check_hostname=True)
_SSL_CTX_FRONTING = _create_ssl_context(check_hostname=False)


def _set_sock_opts(transport, buf_size: int = 262144) -> None:
    if transport is None:
        return
    sock = transport.get_extra_info("socket")
    if sock is None:
        return
    try:
        sock.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
    except OSError:
        pass
    try:
        sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_RCVBUF, buf_size)
        sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_SNDBUF, buf_size)
    except OSError:
        pass


class WsHandshakeError(ConnectionError):
    def __init__(self, status_code: int, message: str, location: str = ""):
        self.status_code = status_code
        self.location = location
        super().__init__(message)


class RawWebSocket:
    OP_CONT = 0x0
    OP_BINARY = 0x2
    OP_CLOSE = 0x8
    OP_PING = 0x9
    OP_PONG = 0xA
    MAX_MESSAGE_LEN = 16 * 1024 * 1024

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self._closed = False
        self._frag = bytearray()

    def is_alive(self) -> bool:
        if self._closed or self.writer is None:
            return False
        try:
            if self.writer.is_closing() or self.reader.at_eof() or self.reader.exception() is not None:
                return False
        except Exception:
            return False
        return True

    @staticmethod
    async def connect(
        host: str,
        domain: str,
        timeout: float = 5.0,
        path: str = "/apiws",
        *,
        sni: Optional[str] = None,
        secure: bool = True,
    ) -> RawWebSocket:
        port = 443 if secure else 80
        ssl_ctx = _SSL_CTX_FRONTING if (secure and sni) else (_SSL_CTX if secure else None)
        tls_kw = {"ssl": ssl_ctx, "server_hostname": (sni or domain)} if secure else {}
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        writer = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port, limit=262144, **tls_kw),
                timeout=timeout,
            )
            _set_sock_opts(writer.transport)
            ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
            req = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {domain}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {ws_key}\r\n"
                "Sec-WebSocket-Version: 13\r\n"
                "Sec-WebSocket-Protocol: binary\r\n"
                "\r\n"
            ).encode("ascii")
            writer.write(req)
            await asyncio.wait_for(writer.drain(), max(0.5, deadline - loop.time()))

            lines: list[str] = []
            while True:
                line = await asyncio.wait_for(reader.readline(), max(0.5, deadline - loop.time()))
                if line in (b"\r\n", b"\n", b""):
                    break
                lines.append(line.decode("utf-8", errors="replace").strip())

            if not lines:
                raise WsHandshakeError(0, "Empty WebSocket HTTP response")
            parts = lines[0].split(" ", 2)
            code = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
            if code != 101:
                hdrs: dict[str, str] = {}
                for hl in lines[1:]:
                    if ":" in hl:
                        k, v = hl.split(":", 1)
                        hdrs[k.strip().lower()] = v.strip()
                raise WsHandshakeError(code, f"WebSocket handshake HTTP {code}", location=hdrs.get("location", ""))
            return RawWebSocket(reader, writer)
        except BaseException:
            if writer is not None:
                try:
                    writer.transport.abort()
                except Exception:
                    pass
            raise

    @staticmethod
    def build_frame(opcode: int, data: bytes, mask: bool = True, mask_key: Optional[bytes] = None) -> bytes:
        length = len(data)
        fb = 0x80 | opcode
        if not mask:
            if length < 126:
                return _st_BB.pack(fb, length) + data
            if length < 65536:
                return _st_BBH.pack(fb, 126, length) + data
            return _st_BBQ.pack(fb, 127, length) + data
        mkey = mask_key if mask_key is not None else os.urandom(4)
        masked = _xor_mask(data, mkey)
        if length < 126:
            return _st_BB4s.pack(fb, 0x80 | length, mkey) + masked
        if length < 65536:
            return _st_BBH4s.pack(fb, 0x80 | 126, length, mkey) + masked
        return _st_BBQ4s.pack(fb, 0x80 | 127, length, mkey) + masked

    async def send(self, data: bytes) -> None:
        if self._closed:
            raise ConnectionError("WebSocket closed")
        self.writer.write(self.build_frame(self.OP_BINARY, data, mask=True))
        await self.writer.drain()

    async def send_batch(self, parts: list[bytes]) -> None:
        if self._closed:
            raise ConnectionError("WebSocket closed")
        for part in parts:
            self.writer.write(self.build_frame(self.OP_BINARY, part, mask=True))
        await self.writer.drain()

    async def _read_frame(self) -> tuple[int, bytes, bool]:
        hdr = await self.reader.readexactly(2)
        fin = bool(hdr[0] & 0x80)
        opcode = hdr[0] & 0x0F
        length = hdr[1] & 0x7F
        if length == 126:
            length = _st_H.unpack(await self.reader.readexactly(2))[0]
        elif length == 127:
            length = _st_Q.unpack(await self.reader.readexactly(8))[0]
        if length > self.MAX_MESSAGE_LEN:
            raise ConnectionError("WS frame too large")
        if hdr[1] & 0x80:
            mkey = await self.reader.readexactly(4)
            payload = _xor_mask(await self.reader.readexactly(length), mkey)
            return opcode, payload, fin
        payload = await self.reader.readexactly(length)
        return opcode, payload, fin

    async def recv(self) -> Optional[bytes]:
        while not self._closed:
            opcode, payload, fin = await self._read_frame()
            if opcode == self.OP_CLOSE:
                self._closed = True
                try:
                    self.writer.write(self.build_frame(self.OP_CLOSE, payload[:2], mask=True))
                    await self.writer.drain()
                except Exception:
                    pass
                return None
            if opcode == self.OP_PING:
                try:
                    self.writer.write(self.build_frame(self.OP_PONG, payload, mask=True))
                    await self.writer.drain()
                except Exception:
                    pass
                continue
            if opcode == self.OP_PONG:
                continue
            if opcode in (self.OP_CONT, 0x1, self.OP_BINARY):
                if fin and not self._frag:
                    return payload
                self._frag.extend(payload)
                if len(self._frag) > self.MAX_MESSAGE_LEN:
                    raise ConnectionError("WS message too large")
                if not fin:
                    continue
                msg = bytes(self._frag)
                self._frag.clear()
                return msg
        return None

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                self.writer.write(self.build_frame(self.OP_CLOSE, b"", mask=True))
                await asyncio.wait_for(self.writer.drain(), timeout=1.5)
            except Exception:
                pass
        try:
            self.writer.close()
            await asyncio.wait_for(self.writer.wait_closed(), timeout=1.5)
        except Exception:
            try:
                self.writer.transport.abort()
            except Exception:
                pass


class MsgSplitter:
    def __init__(self, proto_int: int):
        self._proto = proto_int
        self._cipher_buf = bytearray()
        self._plain_buf = bytearray()
        self._disabled = False

    def split(self, chunk: bytes, plain: bytes) -> list[bytes]:
        if not chunk:
            return []
        if self._disabled:
            return [chunk]
        self._cipher_buf.extend(chunk)
        self._plain_buf.extend(plain)
        parts: list[bytes] = []
        offset = 0
        buf_len = len(self._cipher_buf)
        while offset < buf_len:
            pkt_len = self._next_packet_len(offset, buf_len - offset)
            if pkt_len is None:
                break
            if pkt_len <= 0:
                parts.append(bytes(self._cipher_buf[offset:]))
                offset = buf_len
                self._disabled = True
                break
            parts.append(bytes(self._cipher_buf[offset:offset + pkt_len]))
            offset += pkt_len
        if offset:
            del self._cipher_buf[:offset]
            del self._plain_buf[:offset]
        return parts

    def flush(self) -> list[bytes]:
        if not self._cipher_buf:
            return []
        tail = bytes(self._cipher_buf)
        self._cipher_buf.clear()
        self._plain_buf.clear()
        return [tail]

    def _next_packet_len(self, offset: int, avail: int) -> Optional[int]:
        if avail <= 0:
            return None
        if self._proto == PROTO_ABRIDGED_INT:
            first = self._plain_buf[offset]
            if first in (0x7F, 0xFF):
                if avail < 4:
                    return None
                plen = int.from_bytes(self._plain_buf[offset + 1:offset + 4], "little") * 4
                hlen = 4
            else:
                plen = (first & 0x7F) * 4
                hlen = 1
            return 0 if plen <= 0 else (None if avail < hlen + plen else hlen + plen)
        if self._proto in (PROTO_INTERMEDIATE_INT, PROTO_PADDED_INTERMEDIATE_INT):
            if avail < 4:
                return None
            plen = _st_I_le.unpack_from(self._plain_buf, offset)[0] & 0x7FFFFFFF
            return 0 if plen <= 0 else (None if avail < 4 + plen else 4 + plen)
        return 0


class _CryptoCtx:
    __slots__ = ("clt_dec", "clt_enc", "tg_enc", "tg_dec")

    def __init__(self, clt_dec, clt_enc, tg_enc, tg_dec):
        self.clt_dec = clt_dec
        self.clt_enc = clt_enc
        self.tg_enc = tg_enc
        self.tg_dec = tg_dec


def try_handshake(handshake: bytes, secret: bytes) -> Optional[tuple[int, bool, bytes, bytes]]:
    if len(handshake) != HANDSHAKE_LEN:
        return None
    dec_prekey_and_iv = handshake[SKIP_LEN:SKIP_LEN + PREKEY_LEN + IV_LEN]
    dec_key = hashlib.sha256(dec_prekey_and_iv[:PREKEY_LEN] + secret).digest()
    dec_iv = dec_prekey_and_iv[PREKEY_LEN:]
    decrypted = create_aes_ctr(dec_key, dec_iv).update(handshake)
    proto_tag = decrypted[PROTO_TAG_POS:PROTO_TAG_POS + 4]
    if proto_tag not in (PROTO_TAG_ABRIDGED, PROTO_TAG_INTERMEDIATE, PROTO_TAG_SECURE):
        return None
    dc_idx = int.from_bytes(decrypted[DC_IDX_POS:DC_IDX_POS + 2], "little", signed=True)
    dc_id = abs(dc_idx)
    if dc_id == 0:
        return None
    return dc_id, (dc_idx < 0), proto_tag, dec_prekey_and_iv


def generate_relay_init(proto_tag: bytes, dc_idx: int) -> bytes:
    while True:
        rnd = bytearray(os.urandom(HANDSHAKE_LEN))
        if rnd[0] == 0xEF:
            continue
        if bytes(rnd[:4]) in RESERVED_STARTS:
            continue
        if rnd[4:8] == b"\x00\x00\x00\x00":
            continue
        break
    rnd_bytes = bytes(rnd)
    enc_key = rnd_bytes[SKIP_LEN:SKIP_LEN + PREKEY_LEN]
    enc_iv = rnd_bytes[SKIP_LEN + PREKEY_LEN:SKIP_LEN + PREKEY_LEN + IV_LEN]
    ks = create_aes_ctr(enc_key, enc_iv).update(b"\x00" * HANDSHAKE_LEN)
    tail_plain = proto_tag + struct.pack("<h", dc_idx) + os.urandom(2)
    out = bytearray(rnd_bytes)
    for i in range(8):
        out[PROTO_TAG_POS + i] = tail_plain[i] ^ ks[PROTO_TAG_POS + i]
    return bytes(out)


def build_crypto_ctx(client_dec_prekey_iv: bytes, secret: bytes, relay_init: bytes) -> _CryptoCtx:
    clt_dec_key = hashlib.sha256(client_dec_prekey_iv[:PREKEY_LEN] + secret).digest()
    clt_dec_iv = client_dec_prekey_iv[PREKEY_LEN:]
    clt_enc_rev = client_dec_prekey_iv[::-1]
    clt_enc_key = hashlib.sha256(clt_enc_rev[:PREKEY_LEN] + secret).digest()
    clt_enc_iv = clt_enc_rev[PREKEY_LEN:]

    clt_dec = create_aes_ctr(clt_dec_key, clt_dec_iv)
    clt_dec.update(b"\x00" * HANDSHAKE_LEN)
    clt_enc = create_aes_ctr(clt_enc_key, clt_enc_iv)

    tg_enc_key = relay_init[SKIP_LEN:SKIP_LEN + PREKEY_LEN]
    tg_enc_iv = relay_init[SKIP_LEN + PREKEY_LEN:SKIP_LEN + PREKEY_LEN + IV_LEN]
    tg_dec_rev = relay_init[SKIP_LEN:SKIP_LEN + PREKEY_LEN + IV_LEN][::-1]
    tg_dec_key = tg_dec_rev[:PREKEY_LEN]
    tg_dec_iv = tg_dec_rev[PREKEY_LEN:]

    tg_enc = create_aes_ctr(tg_enc_key, tg_enc_iv)
    tg_enc.update(b"\x00" * HANDSHAKE_LEN)
    tg_dec = create_aes_ctr(tg_dec_key, tg_dec_iv)
    return _CryptoCtx(clt_dec, clt_enc, tg_enc, tg_dec)


def ensure_secret(cfg: dict) -> str:
    raw = str(cfg.get("tg_proxy_secret", "") or "").strip().lower()
    if raw.startswith("dd") and len(raw) == 34:
        raw = raw[2:]
    if len(raw) == 32 and all(c in "0123456789abcdef" for c in raw):
        return raw
    return os.urandom(16).hex()


class _PinnedGitHubHTTPSHandler(urllib.request.HTTPSHandler):
    _GITHUB_IPS = {
        "raw.githubusercontent.com": "185.199.109.133",
        "release-assets.githubusercontent.com": "185.199.109.133",
    }

    def https_open(self, req):
        host = req.host.split(":")[0]
        pinned = self._GITHUB_IPS.get(host)
        if not pinned:
            return super().https_open(req)

        class _Conn(http.client.HTTPSConnection):
            def connect(self):
                self.sock = _socket.create_connection((pinned, self.port or 443), self.timeout, self.source_address)
                if self._tunnel_host:
                    self._tunnel()
                self.sock = self._context.wrap_socket(self.sock, server_hostname=self._tunnel_host or self.host)

        try:
            return self.do_open(_Conn, req, context=self._context)
        except Exception:
            return super().https_open(req)


class TgProxyService:
    POOL_MAX_PER_KEY = 3
    POOL_TTL_SEC = 75.0
    DIRECT_COOLDOWN_SEC = 90.0
    CF_COOLDOWN_SEC = 30.0
    TCP_COOLDOWN_SEC = 60.0

    def __init__(self):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._ready_event = threading.Event()
        self._running = False
        self._host = "127.0.0.1"
        self._port = 1443
        self._secret_hex = ""
        self._last_error = ""
        self._cf_domains: list[str] = list(CFPROXY_DEFAULT_DOMAINS)
        self._cf_cooldown: dict[tuple[str, bool], float] = {}
        self._cf_preferred: dict[int, str] = {}
        self._cf_tls_ok = 0
        self._cf_notls_ok = 0
        self._direct_cooldown: dict[tuple[int, bool], float] = {}
        self._tcp_cooldown: dict[int, float] = {}
        self._ws_pool: dict[tuple[int, bool, bool], list[tuple[RawWebSocket, float, str]]] = {}
        self._refill_tasks: dict[tuple[int, bool, bool], asyncio.Task] = {}
        self._stats: dict[str, int] = {
            "active": 0,
            "total": 0,
            "ws": 0,
            "cf": 0,
            "tcp": 0,
            "bytes_up": 0,
            "bytes_down": 0,
        }

    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    def get_tg_link(self) -> str:
        if not self._secret_hex:
            return ""
        return f"tg://proxy?server=127.0.0.1&port={self._port}&secret=dd{self._secret_hex}"

    def get_stats(self) -> dict:
        with self._lock:
            res = dict(self._stats)
            res["running"] = self.is_running()
            res["port"] = self._port
            res["host"] = self._host
            res["last_error"] = self._last_error
            return res

    def start(self, host: str = "127.0.0.1", port: int = 1443, secret_hex: str = "") -> tuple[bool, str]:
        self.stop()
        if not secret_hex or len(secret_hex) != 32:
            secret_hex = os.urandom(16).hex()
        self._host = host
        self._port = int(port)
        self._secret_hex = secret_hex.lower()
        self._last_error = ""
        self._ready_event.clear()

        self._thread = threading.Thread(target=self._run_thread, daemon=True, name="tg-ws-bridge")
        self._thread.start()
        self._ready_event.wait(timeout=3.0)
        if self._last_error:
            return False, self._last_error
        if not self.is_running():
            return False, "Не удалось запустить Telegram WS-Мост"
        return True, f"Telegram WS-Мост запущен на {self._host}:{self._port}"

    def stop(self) -> None:
        loop = self._loop
        stop_ev = self._stop_event
        thread = self._thread
        self._running = False
        if loop is not None and stop_ev is not None and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(stop_ev.set)
            except Exception:
                pass
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.5)
        self._thread = None
        self._loop = None
        self._stop_event = None
        with self._lock:
            self._stats["active"] = 0

    def _run_thread(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._serve())
        except Exception as e:
            self._last_error = str(e)
        finally:
            self._running = False
            self._ready_event.set()
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            loop.close()

    def _refresh_cf_domains_sync(self) -> None:
        try:
            req = urllib.request.Request(
                CFPROXY_DOMAINS_URL,
                headers={"User-Agent": "Unfit-Zapret-TG-Bridge"},
            )
            opener = urllib.request.build_opener(_PinnedGitHubHTTPSHandler(context=_SSL_CTX))
            with opener.open(req, timeout=6) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            decoded = [
                _decode_cf_domain(line.strip())
                for line in raw.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            valid = [d for d in decoded if "." in d and re.match(r"^[a-zA-Z0-9.-]+$", d)]
            if len(valid) >= 3:
                with self._lock:
                    self._cf_domains = valid
        except Exception:
            pass

    async def _serve(self) -> None:
        self._stop_event = asyncio.Event()
        secret_bytes = bytes.fromhex(self._secret_hex)
        try:
            server = await asyncio.start_server(
                lambda r, w: self._handle_client(r, w, secret_bytes),
                self._host,
                self._port,
                limit=262144,
                reuse_address=(sys.platform != "win32"),
            )
        except Exception as e:
            self._last_error = f"Порт {self._port} занят или недоступен: {e}"
            self._ready_event.set()
            return

        self._running = True
        self._ready_event.set()
        threading.Thread(target=self._refresh_cf_domains_sync, daemon=True).start()
        self._schedule_pool_refill((2, False, False))
        self._schedule_pool_refill((4, False, False))

        try:
            async with server:
                await self._stop_event.wait()
        finally:
            for t in list(self._refill_tasks.values()):
                t.cancel()
            self._refill_tasks.clear()
            for bucket in self._ws_pool.values():
                for ws, _, _ in bucket:
                    try:
                        await ws.close()
                    except Exception:
                        pass
            self._ws_pool.clear()

    def _pop_pool_ws(self, key: tuple[int, bool, bool]) -> tuple[Optional[RawWebSocket], str]:
        bucket = self._ws_pool.get(key)
        now = time.monotonic()
        chosen: Optional[RawWebSocket] = None
        chosen_kind = ""
        if bucket:
            while bucket:
                ws, created, kind = bucket.pop(0)
                if (now - created) < self.POOL_TTL_SEC and ws.is_alive():
                    chosen = ws
                    chosen_kind = kind
                    break
                asyncio.create_task(ws.close())
        self._schedule_pool_refill(key)
        return chosen, chosen_kind

    def _schedule_pool_refill(self, key: tuple[int, bool, bool]) -> None:
        if not self._running or self._loop is None:
            return
        task = self._refill_tasks.get(key)
        if task is not None and not task.done():
            return
        if len(self._ws_pool.get(key, [])) >= self.POOL_MAX_PER_KEY:
            return
        try:
            self._refill_tasks[key] = asyncio.create_task(self._refill_pool_key(key))
        except Exception:
            pass

    async def _refill_pool_key(self, key: tuple[int, bool, bool]) -> None:
        try:
            dc, is_media, is_test = key
            bucket = self._ws_pool.setdefault(key, [])
            needed = self.POOL_MAX_PER_KEY - len(bucket)
            if needed <= 0 or not self._running:
                return
            ws, kind = await self._connect_ws_for_key(dc, is_media, is_test)
            if ws is None:
                return
            if not self._running:
                await ws.close()
                return
            bucket.append((ws, time.monotonic(), kind))
            rest = self.POOL_MAX_PER_KEY - len(bucket)
            if rest > 0 and self._running:
                extra = await asyncio.gather(
                    *(self._connect_ws_for_key(dc, is_media, is_test) for _ in range(rest)),
                    return_exceptions=True,
                )
                for item in extra:
                    if isinstance(item, tuple) and item[0] is not None:
                        w_extra, k_extra = item
                        if self._running and len(bucket) < self.POOL_MAX_PER_KEY:
                            bucket.append((w_extra, time.monotonic(), k_extra))
                        else:
                            await w_extra.close()
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        finally:
            self._refill_tasks.pop(key, None)

    async def _connect_ws_for_key(self, dc: int, is_media: bool, is_test: bool) -> tuple[Optional[RawWebSocket], str]:
        ws = await self._open_ws_direct(dc, is_media, is_test)
        if ws is not None:
            return ws, "ws"
        if not is_test:
            cf_ws = await self._open_ws_cf(dc)
            if cf_ws is not None:
                return cf_ws, "cf"
        return None, ""

    async def _open_ws_direct(self, dc: int, is_media: bool, is_test: bool) -> Optional[RawWebSocket]:
        if is_test:
            ip = DC_TEST_IPS.get(dc)
            path = "/apiws_test"
        else:
            ip = WS_DIRECT_IPS.get(dc)
            path = "/apiws"
        if not ip:
            return None
        cd_key = (dc, is_media)
        if self._direct_cooldown.get(cd_key, 0.0) > time.monotonic():
            return None
        base_dc = 2 if dc == 203 else dc
        domains = [f"kws{base_dc}-1.web.telegram.org", f"kws{base_dc}.web.telegram.org"] if is_media else [f"kws{base_dc}.web.telegram.org"]
        for dom in domains:
            try:
                ws = await RawWebSocket.connect(ip, dom, timeout=2.5, path=path, sni=dom, secure=True)
                self._direct_cooldown.pop(cd_key, None)
                return ws
            except Exception:
                continue
        self._direct_cooldown[cd_key] = time.monotonic() + self.DIRECT_COOLDOWN_SEC
        return None

    async def _open_ws_cf(self, dc: int) -> Optional[RawWebSocket]:
        base_dc = 2 if dc == 203 else dc
        # На Cloudflare существуют только базовые поддомены kws{dc} без -1
        sub = f"kws{base_dc}"
        with self._lock:
            pool = list(self._cf_domains)
            pref = self._cf_preferred.get(base_dc)
        ordered = [d for d in pool if d != pref]
        random.shuffle(ordered)
        if pref:
            ordered.insert(0, pref)

        secure_order = (True, False) if self._cf_tls_ok >= self._cf_notls_ok else (False, True)
        timeouts = (2.5, 3.0, 4.0, 5.0)
        now = time.monotonic()
        attempts = 0
        for base in ordered[:8]:
            host = f"{sub}.{base}"
            for secure in secure_order:
                until = self._cf_cooldown.get((host, secure))
                if until and now < until:
                    continue
                if attempts >= 10:
                    return None
                tmo = timeouts[min(attempts, len(timeouts) - 1)]
                attempts += 1
                try:
                    ws = await RawWebSocket.connect(host, host, timeout=tmo, path="/apiws", secure=secure)
                    with self._lock:
                        self._cf_preferred[base_dc] = base
                        if secure:
                            self._cf_tls_ok += 1
                        else:
                            self._cf_notls_ok += 1
                    self._cf_cooldown.pop((host, secure), None)
                    return ws
                except Exception:
                    self._cf_cooldown[(host, secure)] = time.monotonic() + self.CF_COOLDOWN_SEC
                    continue
        return None

    async def _bridge_ws(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        ws: RawWebSocket,
        ctx: _CryptoCtx,
        splitter: MsgSplitter,
    ) -> None:
        async def tcp_to_ws():
            try:
                while True:
                    chunk = await reader.read(65536)
                    if not chunk:
                        tail = splitter.flush()
                        if tail:
                            await ws.send(tail[0])
                        break
                    with self._lock:
                        self._stats["bytes_up"] += len(chunk)
                    plain = ctx.clt_dec.update(chunk)
                    reenc = ctx.tg_enc.update(plain)
                    parts = splitter.split(reenc, plain)
                    if parts:
                        await ws.send_batch(parts)
            except (asyncio.CancelledError, ConnectionError, OSError):
                pass

        async def ws_to_tcp():
            try:
                while True:
                    data = await ws.recv()
                    if data is None:
                        break
                    with self._lock:
                        self._stats["bytes_down"] += len(data)
                    plain = ctx.tg_dec.update(data)
                    out = ctx.clt_enc.update(plain)
                    writer.write(out)
                    await writer.drain()
            except (asyncio.CancelledError, ConnectionError, OSError, asyncio.IncompleteReadError):
                pass

        tasks = [asyncio.create_task(tcp_to_ws()), asyncio.create_task(ws_to_tcp())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await ws.close()

    async def _bridge_tcp(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        r_reader: asyncio.StreamReader,
        r_writer: asyncio.StreamWriter,
        ctx: _CryptoCtx,
    ) -> None:
        async def pipe(src, dst, up: bool):
            try:
                while True:
                    data = await src.read(65536)
                    if not data:
                        break
                    with self._lock:
                        if up:
                            self._stats["bytes_up"] += len(data)
                        else:
                            self._stats["bytes_down"] += len(data)
                    if up:
                        out = ctx.tg_enc.update(ctx.clt_dec.update(data))
                    else:
                        out = ctx.clt_enc.update(ctx.tg_dec.update(data))
                    dst.write(out)
                    await dst.drain()
            except (asyncio.CancelledError, ConnectionError, OSError):
                pass

        tasks = [asyncio.create_task(pipe(reader, r_writer, True)), asyncio.create_task(pipe(r_reader, writer, False))]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            try:
                r_writer.close()
                await asyncio.wait_for(r_writer.wait_closed(), timeout=1.0)
            except Exception:
                pass

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, secret: bytes) -> None:
        with self._lock:
            self._stats["total"] += 1
            self._stats["active"] += 1
        _set_sock_opts(writer.transport)
        try:
            try:
                handshake = await asyncio.wait_for(reader.readexactly(HANDSHAKE_LEN), timeout=8.0)
            except (asyncio.IncompleteReadError, asyncio.TimeoutError, OSError):
                return

            parsed = try_handshake(handshake, secret)
            if parsed is None:
                return
            dc, is_media, proto_tag, clt_prekey_iv = parsed
            is_test = dc >= 10000
            if is_test:
                dc -= 10000

            if proto_tag == PROTO_TAG_ABRIDGED:
                proto_int = PROTO_ABRIDGED_INT
            elif proto_tag == PROTO_TAG_INTERMEDIATE:
                proto_int = PROTO_INTERMEDIATE_INT
            else:
                proto_int = PROTO_PADDED_INTERMEDIATE_INT

            dc_idx = -dc if is_media else dc
            relay_init = generate_relay_init(proto_tag, dc_idx)
            ctx = build_crypto_ctx(clt_prekey_iv, secret, relay_init)
            splitter = MsgSplitter(proto_int)
            pool_key = (dc, is_media, is_test)

            ws, kind = self._pop_pool_ws(pool_key)
            if ws is not None:
                try:
                    await asyncio.wait_for(ws.send(relay_init), timeout=4.0)
                    with self._lock:
                        self._stats[kind] += 1
                    await self._bridge_ws(reader, writer, ws, ctx, splitter)
                    return
                except Exception:
                    await ws.close()

            ws, kind = await self._connect_ws_for_key(dc, is_media, is_test)
            if ws is not None:
                try:
                    await asyncio.wait_for(ws.send(relay_init), timeout=4.0)
                    with self._lock:
                        self._stats[kind] += 1
                    self._schedule_pool_refill(pool_key)
                    await self._bridge_ws(reader, writer, ws, ctx, splitter)
                    return
                except Exception:
                    await ws.close()

            ip_table = DC_TEST_IPS if is_test else DC_DEFAULT_IPS
            dst_ip = ip_table.get(dc)
            if dst_ip and self._tcp_cooldown.get(dc, 0.0) <= time.monotonic():
                try:
                    r_reader, r_writer = await asyncio.wait_for(
                        asyncio.open_connection(dst_ip, 443, limit=262144),
                        timeout=4.5,
                    )
                    _set_sock_opts(r_writer.transport)
                    r_writer.write(relay_init)
                    await r_writer.drain()
                    self._tcp_cooldown.pop(dc, None)
                    with self._lock:
                        self._stats["tcp"] += 1
                    await self._bridge_tcp(reader, writer, r_reader, r_writer, ctx)
                except Exception:
                    self._tcp_cooldown[dc] = time.monotonic() + self.TCP_COOLDOWN_SEC
        finally:
            with self._lock:
                self._stats["active"] = max(0, self._stats["active"] - 1)
            try:
                writer.close()
                await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
            except Exception:
                pass


def probe_proxy(
    host: str = "127.0.0.1",
    port: int = 1443,
    secret_hex: str = "",
    dc: int = 2,
    timeout: float = 6.0,
) -> tuple[bool, int, str]:
    sec_hex = (secret_hex or "").strip().lower()
    if sec_hex.startswith("dd") and len(sec_hex) == 34:
        sec_hex = sec_hex[2:]
    if len(sec_hex) != 32:
        try:
            import zapret_core as core
            sec_hex = ensure_secret(core.load_config())
        except Exception:
            sec_hex = ""
    if len(sec_hex) != 32:
        return False, 0, "Не задан секрет Telegram WS-Моста"

    secret = bytes.fromhex(sec_hex)
    nonce = os.urandom(16)
    msg_id = int(time.time() * (2**32)) & ~3
    inner = struct.pack("<I", 0xBE7E8EF1) + nonce
    mtproto_msg = struct.pack("<qqI", 0, msg_id, len(inner)) + inner

    while True:
        rnd = bytearray(os.urandom(HANDSHAKE_LEN))
        if rnd[0] == 0xEF or bytes(rnd[:4]) in RESERVED_STARTS or rnd[4:8] == b"\x00\x00\x00\x00":
            continue
        break

    pre_iv = bytes(rnd[SKIP_LEN:SKIP_LEN + PREKEY_LEN + IV_LEN])
    enc_key = hashlib.sha256(pre_iv[:PREKEY_LEN] + secret).digest()
    enc_iv = pre_iv[PREKEY_LEN:]
    rev = pre_iv[::-1]
    dec_key = hashlib.sha256(rev[:PREKEY_LEN] + secret).digest()
    dec_iv = rev[PREKEY_LEN:]

    enc = create_aes_ctr(enc_key, enc_iv)
    ks = enc.update(b"\x00" * HANDSHAKE_LEN)
    tail = PROTO_TAG_SECURE + struct.pack("<h", dc) + os.urandom(2)
    for i in range(8):
        rnd[PROTO_TAG_POS + i] = tail[i] ^ ks[PROTO_TAG_POS + i]

    dec = create_aes_ctr(dec_key, dec_iv)
    pad = os.urandom(7)
    pkt = _st_I_le.pack(len(mtproto_msg) + len(pad)) + mtproto_msg + pad

    t0 = time.monotonic()
    try:
        with _socket.create_connection((host, int(port)), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(bytes(rnd) + enc.update(pkt))
            resp = sock.recv(4096)
    except OSError as e:
        return False, 0, f"Не удалось подключиться к {host}:{port}: {e}"

    if not resp:
        return False, 0, "Мост разорвал соединение (возможен сбой WS/CF или несовпадение секрета)"

    plain = dec.update(resp)
    if b"\x63\x24\x16\x05" not in plain:
        return False, 0, "Получен некорректный ответ MTProto (проверьте секрет)"
    ms = int(round((time.monotonic() - t0) * 1000))
    return True, ms, f"Мост работает (DC{dc}: {ms} мс)"


def run_standalone_from_config() -> int:
    import signal
    import zapret_core as core

    cfg = core.load_config()
    port = int(cfg.get("tg_proxy_port", 1443) or 1443)
    secret_hex = ensure_secret(cfg)
    if cfg.get("tg_proxy_secret") != secret_hex:
        cfg["tg_proxy_secret"] = secret_hex
        try:
            core.save_config(cfg)
        except Exception:
            pass

    svc = TgProxyService()
    ok, _ = svc.start("127.0.0.1", port, secret_hex)
    if not ok:
        return 1

    own_pid = str(os.getpid())
    try:
        core.WORK_DIR.mkdir(parents=True, exist_ok=True)
        core.TG_PROXY_PID_FILE.write_text(own_pid, encoding="utf-8")
    except OSError:
        pass

    stop_flag = threading.Event()
    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            try:
                signal.signal(sig, lambda *_: stop_flag.set())
            except Exception:
                pass

    try:
        while not stop_flag.wait(timeout=1.0):
            if not svc.is_running():
                return 1
    finally:
        svc.stop()
        try:
            if core.TG_PROXY_PID_FILE.exists() and core.TG_PROXY_PID_FILE.read_text(encoding="utf-8").strip() == own_pid:
                core.TG_PROXY_PID_FILE.unlink()
        except OSError:
            pass
    return 0
