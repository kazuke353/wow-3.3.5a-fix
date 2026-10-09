#!/usr/bin/env python3
"""Classless spell-modifier patch for WoW 3.3.5a (build 12340) Wow.exe.

The client only applies talent/aura spell modifiers (SMSG_SET_FLAT/PCT_SPELL_MODIFIER)
to spells whose SpellClassSet (SpellFamilyName) equals the player's class SpellClassSet
from ChrClasses.dbc. This removes that comparison so tooltips, cast times, costs and
cooldowns shown by the client update for spells from any class.

Usage: python3 patch_classless.py Wow.exe [output.exe]
"""
import hashlib
import shutil
import sys

ORIGINAL_SHA256 = "bf644876709c591acc17c0da8cdf1814edcc9f1e6bc109a8c0d5c38c79dc953c"

# (file offset, original bytes, patched bytes, description)
PATCHES = [
    # 0x7FD970 GetSpellModifiers(spellRec, op, &flat, &pct):
    #   007FD986  cmp eax, [0xD397B4]   ; spell->SpellClassSet vs player class SpellClassSet
    #   007FD98C  jne 0x7FDB2D          ; -> no modifiers
    (0x3FCD8C, bytes.fromhex("0f859b010000"), bytes.fromhex("909090909090"),
     "GetSpellModifiers: ignore class SpellClassSet check (tooltips, cast time, cost, cooldown...)"),
    # 0x800D60 aura class-mask check used by cast/usability checks (e.g. ignore shapeshift/aura state):
    #   00800D93  cmp ecx, [0xD397B4]
    #   00800D99  jne 0x800DC4
    (0x400199, bytes.fromhex("7529"), bytes.fromhex("9090"),
     "Aura spell-mask usability check: ignore class SpellClassSet check"),
]


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

    if dst == src:
        shutil.copyfile(src, src + ".bak")
        print(f"backup written to {src}.bak")
    open(dst, "wb").write(data)
    print(f"patched exe written to {dst}")


if __name__ == "__main__":
    main()
