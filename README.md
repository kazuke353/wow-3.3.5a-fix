# wow-3.3.5a-fix

Client patch for classless 3.3.5a (build 12340) servers: spell modifiers from
talents/auras of any class now apply client-side, so tooltips, cast bars, costs
and cooldowns update for spells from other classes.

```
python3 patch_classless.py Wow.exe            # patches in place, keeps Wow.exe.bak
python3 patch_classless.py Wow.exe Wow2.exe   # writes a new file
```

Stock exe SHA-256: `bf644876709c591acc17c0da8cdf1814edcc9f1e6bc109a8c0d5c38c79dc953c`
Patched exe SHA-256: `79efc2ec4d203fe31906276e71975940e01f7fcc3bbddada8577469f8520af51`

## What is patched

`SMSG_SET_FLAT_SPELL_MODIFIER` / `SMSG_SET_PCT_SPELL_MODIFIER` (handler `0x7FDC60`)
store values in two global tables (`0xD3C658` flat, `0xD397D8` pct) indexed by
mask bit and spell-mod op. They are read by `0x7FD970` (GetSpellModifiers), which
the tooltip code and the cast/cost/cooldown code call through `0x7FDB50`.
That function first requires
`spell->SpellClassSet (+0x240) == g_playerSpellClassSet (0xD397B4)`, a global
set from `ChrClasses.dbc` (`SpellClassSet`, +0x20) by `0x8007A0`.

| VA | File offset | Original | Patched | Effect |
|----|-------------|----------|---------|--------|
| `0x7FD98C` | `0x3FCD8C` | `0F 85 9B 01 00 00` (jne) | `90 ×6` | Modifiers apply to every class's spells |
| `0x800D99` | `0x400199` | `75 29` (jne) | `90 90` | Same class check in the aura spell-mask usability test (`0x800D60`, used by cast checks) |

Spells with `SpellClassSet = 0` are still skipped, the same as on the stock client.

## Caveat

The client keeps one modifier table for all classes, indexed only by mask bit.
Once the class check is removed, a modifier on bit N affects every spell with
bit N set, whatever its class. Example: a warrior talent on bit 5 will also
change the tooltip of a druid spell that uses bit 5. The server still calculates
the real values; only what the client displays can be wrong.
