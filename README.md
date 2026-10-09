# wow-3.3.5a-fix

Client patch for classless 3.3.5a (build 12340) servers. Talent and aura spell
modifiers apply to spells of any class, and each class keeps its own modifiers.
Example: a Druid with a Warrior talent sees the warrior spell's tooltip, cast
bar, cost and cooldown update, while druid spells that use the same mask bit are
left alone.

```
python3 patch_classless.py Wow.exe            # patches in place, keeps Wow.exe.bak
python3 patch_classless.py Wow.exe Wow2.exe   # writes a new file
python3 test_emulate.py Wow2.exe              # optional: emulated check (pip install unicorn pefile)
```

Stock exe SHA-256: `bf644876709c591acc17c0da8cdf1814edcc9f1e6bc109a8c0d5c38c79dc953c`
Patched exe SHA-256: `1b56f6a4edcd7e7d1b351c60c00f8fddb757bd4a60e9a27c2120bebc0a17ec41`

## Server side

Full task brief for the core: [CORE_CHANGES.md](CORE_CHANGES.md).

The client accepts an optional trailing byte on both modifier packets:

```
SMSG_SET_FLAT_SPELL_MODIFIER / SMSG_SET_PCT_SPELL_MODIFIER:
    uint8 bit, uint8 op, int32 value [, uint8 spellFamily]
```

- **With the byte:** the value is stored only for that spell family (`SpellClassSet` /
  `SpellFamilyName`). The server must total values per family as well. Replace
  `Player::AddSpellMod` with [server/AddSpellMod_AzerothCore.cpp](server/AddSpellMod_AzerothCore.cpp)
  or [server/AddSpellMod_TrinityCore.cpp](server/AddSpellMod_TrinityCore.cpp).
- **Without it (unmodified core):** the value is stored for every family. Class checks are
  gone, but a modifier on bit N affects every class's spells that use bit N.

## How the stock client works

The `SMSG_SET_FLAT/PCT_SPELL_MODIFIER` handler (`0x7FDC60`) writes `value` into one global
table per type, at `bit*31 + op`: pct at `0xD397D8` and flat at `0xD3C658`, each `0x2E80`
bytes. `GetSpellModifiers` (`0x7FD970`) reads these tables. The tooltip code and the
cast/cost/cooldown code call it through `0x7FDB50`. It first requires
`spell->SpellClassSet (+0x240) == g_playerSpellClassSet (0xD397B4)`, a global set from
`ChrClasses.dbc` (`SpellClassSet`, +0x20) by `0x8007A0`.

## What is patched

The patcher adds a new `.cls` section: VA `0xDFD000`, 0xC0D00 bytes, RWX.

- **Code at `0xDFD000`.** The source is [cave_source.py](cave_source.py).
- **Tables at `0xDFE000`.** There are 33 blocks of `[pct 0x2E80][flat 0x2E80]`: block *f*
  is spell family *f* (0–31), and block 32 always stays zero. The layout matches the stock
  tables, so the original lookup code still works. It only adds the block offset.

| VA | Original | New | Effect |
|----|----------|-----|--------|
| `0x7FD98C` | `jne` (class check) | `nop ×6` | Spells of any class get modifiers |
| `0x7FD9CA` | `mov eax,2; add esi,esi` | `call 0xDFD000` | Lookup reads the block for `spell->SpellClassSet` (32 or above → zero block) |
| `0x7FDC60` | handler prologue | `jmp 0xDFD025` | New handler: reads the optional family byte, checks bit/op/family ranges, stores per family (all families if the byte is absent) |
| `0x8102AF` / `0x8102B5` | `memset(0xD3C658, 0, 0x2E80)` | `memset(0xDFE000, 0, 0xBFD00)` | World init clears the new tables. The old flat table is no longer read. |
| `0x800D99` | `jne` (class check) | `nop ×2` | Same class check removed from the aura spell-mask usability test (`0x800D60`) |

Spells with `SpellClassSet = 0` still get no modifiers, the same as on the stock client.

If your core uses Warden memory scans, make sure they don't check these addresses.
