// Replacement for Player::AddSpellMod in src/server/game/Entities/Player/Player.cpp (TrinityCore 3.3.5).
// Requires the per-family patched Wow.exe (patch_classless.py).
//
// Changes from stock:
//  1. Totals are summed only over modifiers of the same SpellFamilyName, so a warrior talent
//     and a druid talent on the same mask bit no longer add up together.
//  2. A trailing uint8 SpellFamilyName is appended so the client stores the value in that
//     family's table. (Raw WorldPacket, because SetSpellModifier has no field for it.)

static uint8 GetSpellModFamily(SpellModifier const* mod)
{
    SpellInfo const* info = sSpellMgr->GetSpellInfo(mod->spellId);
    return info ? uint8(info->SpellFamilyName) : 0;
}

void Player::AddSpellMod(SpellModifier* mod, bool apply)
{
    TC_LOG_DEBUG("spells", "Player::AddSpellMod: Player '{}' ({}), SpellID: {}", GetName(), GetGUID().ToString(), mod->spellId);

    OpcodeServer opcode = (mod->type == SPELLMOD_FLAT) ? SMSG_SET_FLAT_SPELL_MODIFIER : SMSG_SET_PCT_SPELL_MODIFIER;
    uint8 family = GetSpellModFamily(mod);

    for (uint8 i = 0; i < 3; ++i)
    {
        for (uint32 eff = 0; eff < 32; ++eff)
        {
            uint32 modMask = uint32(1) << eff;
            if ((mod->mask[i] & modMask))
            {
                int32 val = 0;
                for (SpellModifier* spellMod : m_spellMods[mod->op])
                    if (spellMod->type == mod->type && (spellMod->mask[i] & modMask) && GetSpellModFamily(spellMod) == family)
                        val += spellMod->value;

                val += apply ? mod->value : -(mod->value);

                WorldPacket data(opcode, 1 + 1 + 4 + 1);
                data << uint8(eff + 32 * i);
                data << uint8(AsUnderlyingType(mod->op));
                data << int32(val);
                data << uint8(family);
                SendDirectMessage(&data);
            }
        }
    }

    if (apply)
        m_spellMods[mod->op].insert(mod);
    else
        m_spellMods[mod->op].erase(mod);
}
