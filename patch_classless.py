#!/usr/bin/env python3
"""Classless spell-modifier patch for WoW 3.3.5a (build 12340) Wow.exe.

Stock client: talent/aura spell modifiers (SMSG_SET_FLAT/PCT_SPELL_MODIFIER) are kept in one
global table indexed by mask bit, and only applied to spells whose SpellClassSet equals the
player's class SpellClassSet (ChrClasses.dbc).

This patch:
  * removes the player-class check, so spells of any class get modifiers;
  * gives every spell family (SpellClassSet 0-31) its own modifier table, so a modifier
    on mask bit N of one class does not leak onto another class's spells using bit N.

Packet format accepted by the patched client (both opcodes):
    uint8 bit, uint8 op, int32 value [, uint8 spellFamily]
The trailing family byte is optional. Without it (unmodified server) the value is written to
every family's table, which equals the simple "class check removed" behaviour.

Usage: python3 patch_classless.py Wow.exe [output.exe]
"""
import hashlib
import shutil
import struct
import sys

ORIGINAL_SHA256 = "bf644876709c591acc17c0da8cdf1814edcc9f1e6bc109a8c0d5c38c79dc953c"

IMAGE_BASE = 0x400000
SEC_RVA = 0x9FD000            # new ".cls" section, right after .rsrc
SEC_VA = IMAGE_BASE + SEC_RVA  # 0xDFD000: code
TABLES = SEC_VA + 0x1000       # 0xDFE000: 33 blocks of [pct 0x2E80][flat 0x2E80]; block 32 stays zero
BLOCK = 0x5D00
TABLES_SIZE = 33 * BLOCK
SEC_VSIZE = 0x1000 + TABLES_SIZE
SEC_RAW_OFF = 0x757C00         # end of the stock file
SEC_RAW_SIZE = 0x200
HANDLER_OFF = 0x25             # offset of the packet handler inside CAVE_CODE

# Built by cave_source.py
CAVE_CODE = bytes.fromhex(
    "01f68b834002000083f8207205b82000000069c0005d00008db40628480c00b802000000c35589e583ec0856578b"
    "75148d45ff5089f1bf40b34700ffd78d45fe5089f1ffd78d45f85089f1b8c0b34700ffd00fb64dff83f960735f0f"
    "b655fe83fa1f73566bc91f01d18d0c8d00e0df00817d0c67020000740681c1802e00008b55f88b46143b46107320"
    "51528d45fd5089f1ffd75a590fb645fd83f820731b69c0005d0000891401eb10b820000000891181c1005d000048"
    "75f55f5eb80100000089ec5dc3")


def va_to_off(va):  # .text only
    return va - 0x401000 + 0x400


def rel32(src_next, dst):
    return struct.pack("<i", dst - src_next)


# (file offset, original bytes, patched bytes, description)
PATCHES = [
    # 0x7FD970 GetSpellModifiers: `cmp eax,[0xD397B4]; jne` -> spell family vs player class family
    (va_to_off(0x7FD98C), bytes.fromhex("0f859b010000"), bytes.fromhex("909090909090"),
     "GetSpellModifiers: remove player-class SpellClassSet check"),
    # 0x7FD9CA `mov eax,2; add esi,esi` -> call cave: picks the table block from spell->SpellClassSet
    (va_to_off(0x7FD9CA), bytes.fromhex("b80200000003f6"),
     b"\xe8" + rel32(0x7FD9CF, SEC_VA) + b"\x90\x90",
     "GetSpellModifiers: read modifiers from the spell family's own table"),
    # 0x7FDC60 SMSG_SET_FLAT/PCT_SPELL_MODIFIER handler -> jmp to new handler
    (va_to_off(0x7FDC60), bytes.fromhex("558bec83ec"),
     b"\xe9" + rel32(0x7FDC65, SEC_VA + HANDLER_OFF),
     "Spell modifier packet handler: store per family (optional trailing family byte)"),
    # 0x8102AF memset(0xD3C658, 0, 0x2E80) on world init -> clear the new tables instead
    (va_to_off(0x8102AF), bytes.fromhex("68802e0000"), b"\x68" + struct.pack("<I", TABLES_SIZE),
     "World init: clear per-family tables (size)"),
    (va_to_off(0x8102B5), bytes.fromhex("6858c6d300"), b"\x68" + struct.pack("<I", TABLES),
     "World init: clear per-family tables (address)"),
    # 0x800D60 aura spell-mask usability check: `cmp ecx,[0xD397B4]; jne`
    (va_to_off(0x800D99), bytes.fromhex("7529"), bytes.fromhex("9090"),
     "Aura spell-mask usability check: remove player-class SpellClassSet check"),
]


def add_section(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = pe + 24
    sec_table = opt + struct.unpack_from("<H", data, pe + 20)[0]
    hdr_off = sec_table + 40 * nsec
    if data[sec_table + 40 * (nsec - 1):sec_table + 40 * (nsec - 1) + 8].rstrip(b"\0") == b".cls":
        return "already present"
    if nsec != 6 or len(data) != SEC_RAW_OFF or any(data[hdr_off:hdr_off + 40]):
        sys.exit("[fail] unexpected PE layout; nothing written")
    hdr = struct.pack("<8sIIIIIIHHI", b".cls", SEC_VSIZE, SEC_RVA, SEC_RAW_SIZE, SEC_RAW_OFF,
                      0, 0, 0, 0, 0xE0000060)  # code | initialized data | exec | read | write
    data[hdr_off:hdr_off + 40] = hdr
    struct.pack_into("<H", data, pe + 6, nsec + 1)
    struct.pack_into("<I", data, opt + 56, (SEC_RVA + SEC_VSIZE + 0xFFF) & ~0xFFF)  # SizeOfImage
    data += CAVE_CODE.ljust(SEC_RAW_SIZE, b"\xcc")
    return "added"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src
    data = bytearray(open(src, "rb").read())

    if hashlib.sha256(data).hexdigest() != ORIGINAL_SHA256:
        print("warning: not the stock build 12340 Wow.exe; verifying patch sites anyway")

    for off, orig, new, desc in PATCHES:
        cur = bytes(data[off:off + len(orig)])
        if cur == new:
            print(f"[skip] 0x{off:X} already patched: {desc}")
        elif cur == orig:
            data[off:off + len(orig)] = new
            print(f"[ok]   0x{off:X} {orig.hex()} -> {new.hex()}: {desc}")
        else:
            sys.exit(f"[fail] 0x{off:X} unexpected bytes {cur.hex()}; nothing written")
    print(f"[ok]   .cls section {add_section(data)} (VA 0x{SEC_VA:X}, tables at 0x{TABLES:X})")

    if dst == src:
        shutil.copyfile(src, src + ".bak")
        print(f"backup written to {src}.bak")
    open(dst, "wb").write(data)
    print(f"patched exe written to {dst}")


if __name__ == "__main__":
    main()
