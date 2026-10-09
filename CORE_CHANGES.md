# Core changes for the per-family spell modifier client patch

This is a task brief for whoever (person or AI agent) edits the server core. It describes the
server-side change needed by the patched 3.3.5a client in this repo (`patch_classless.py`).
Reference implementations: [server/AddSpellMod_AzerothCore.cpp](server/AddSpellMod_AzerothCore.cpp) and
[server/AddSpellMod_TrinityCore.cpp](server/AddSpellMod_TrinityCore.cpp). Both are based on current
upstream code, have not been compiled, and the target core is customised, so adapt them rather than paste them.

## Background

- The server tells the client about talent/aura/glyph spell modifiers with
  `SMSG_SET_FLAT_SPELL_MODIFIER` (0x266) and `SMSG_SET_PCT_SPELL_MODIFIER` (0x267).
  Stock payload: `uint8 bit, uint8 op, int32 value`. Here `bit` is a SpellFamilyFlags bit
  (0–95), `op` is the `SpellModOp`, and `value` is the **total** for that (bit, op, type).
- The client uses these only for display: tooltips, cast bar, cost and cooldown text. The server
  still calculates the real values.
- Mask bits mean different things in each class (spell family). Example: bit 5 can be one ability
  for warriors and a different one for druids. On a classless server the stock protocol cannot say
  which family a value belongs to.
- The patched client keeps one table per spell family and accepts an **optional trailing byte**:

```
SMSG_SET_FLAT_SPELL_MODIFIER / SMSG_SET_PCT_SPELL_MODIFIER
    uint8  bit          // 0..95
    uint8  op           // SpellModOp, 0..30
    int32  value        // total for (family, bit, op, type)
    uint8  spellFamily  // NEW: SpellFamilyName of the modifier's spell, 0..31
```

  The client stores `value` only in `spellFamily`'s table, and applies it to spells whose
  `SpellFamilyName` equals `spellFamily` and whose `SpellFamilyFlags` contain `bit`.
  If the byte is missing, the client writes the value into every family's table, and the class
  separation is lost.

## Required change

The only function that needs changing is `Player::AddSpellMod(SpellModifier* mod, bool apply)` in
`src/server/game/Entities/Player/Player.cpp`. That's the only sender in stock AzerothCore/TrinityCore.

1. **Find the modifier's family.** Use
   `sSpellMgr->GetSpellInfo(mod->spellId)->SpellFamilyName`, and fall back to 0 when the spell info
   is null. A small static helper `GetSpellModFamily(SpellModifier const*)` does the job.
2. **Add up totals per family.** In the loop that totals `val` over `m_spellMods[mod->op]`, add the
   condition that the other modifier's family equals this modifier's family. The existing type and
   mask conditions stay. Without this, a warrior talent and a druid talent on the same bit get summed
   together, and the client would show that combined total for both classes.
3. **Append the byte.** After `int32(val)`, write `uint8(family)`, and set the packet size hint to
   7 bytes.
   - TrinityCore 3.3.5 builds this packet with `WorldPackets::Spells::SetSpellModifier`, which has no
     field for the family. Either build a raw `WorldPacket` (as the reference file does) or add a
     `uint8 SpellFamily` field to that packet struct and write it in its `Write()`.
4. Leave the `insert`/`erase` bookkeeping at the end of the function exactly as it is.

## Must stay consistent with the core's own spell-mod logic

The user said their core is "already fixed" for classless spell mods. Find out how before changing
anything:

- Look at `SpellInfo::IsAffectedBySpellMod` / `Player::IsAffectedBySpellmod`, `SpellInfo::IsAffected`
  and `Player::ApplySpellMod` / `GetTotalSpellMod`. Also search for any custom code (scripts, Eluna,
  hooks) that changes how a modifier is matched to a spell.
- The family you send must be the same rule the server uses to decide which spells a modifier
  affects. The stock rule is `modSpell->SpellFamilyName == spell->SpellFamilyName` plus the mask
  check, and it matches the client patch.
- If the custom fix instead lets a modifier affect spells of **other** families, or maps families
  in some other way, the client display will differ from the server for those cases. Report this
  to the user rather than guessing.

## Also check

- Search the whole core, including scripts and modules, for other senders of these two opcodes:
  `grep -rn "SMSG_SET_FLAT_SPELL_MODIFIER\|SMSG_SET_PCT_SPELL_MODIFIER\|SetSpellModifier"`.
  Each one needs the same family byte and per-family total.
- `SpellFamilyName` values above 31 are dropped by the client. Stock 3.3.5 families are 0–17.
- Spells with family 0 (generic) never get modifiers on the client, the same as the stock client.
  That's expected and needs no server change.
- No login or resync change is needed: modifiers are sent when their auras apply, and the client
  clears its tables when you enter the world.
- Unpatched 3.3.5a clients receive one extra byte that they don't read. Their handler reads 6 bytes
  and ignores the rest. This has not been tested on a stock client, so if unpatched clients must
  still connect, check that before relying on it.

## Acceptance test

Test with a Druid that has learned a warrior ability and a warrior talent that modifies it. For
example: Heroic Strike plus Improved Heroic Strike (rage cost), or any warrior talent with a
SpellFamilyFlags mask.

1. Log in with the patched `Wow.exe`. The warrior ability's tooltip and cost show the talent's effect.
2. Druid abilities that share the same mask bit in family 7 do **not** change.
3. Unlearning the talent (talent reset) reverts the warrior tooltip. The server sends `val` without
   the removed modifier, for family 4.
4. Optional packet check: a sniff or debug log shows 7-byte payloads, with the last byte equal to the
   modifier spell's `SpellFamilyName` (4 for Warrior, 7 for Druid, and so on).
5. The core builds without warnings in the changed function.
