// Replacement for Player::AddSpellMod in src/server/game/Entities/Player/Player.cpp (AzerothCore).
// Requires the per-family patched Wow.exe (patch_classless.py).
//
// Changes from stock:
//  1. Totals are summed only over modifiers of the same SpellFamilyName, so a warrior talent
//     and a druid talent on the same mask bit no longer add up together.
//  2. A trailing uint8 SpellFamilyName is appended so the client stores the value in that
//     family's table.

static uint8 GetSpellModFamily(SpellModifier const* mod)
{
    SpellInfo const* info = sSpellMgr->GetSpellInfo(mod->spellId);
    return info ? uint8(info->SpellFamilyName) : 0;
}

void Player::AddSpellMod(SpellModifier* mod, bool apply)
{
    LOG_DEBUG("spells.aura", "Player::AddSpellMod {}", mod->spellId);
    uint16 Opcode = (mod->type == SPELLMOD_FLAT) ? SMSG_SET_FLAT_SPELL_MODIFIER : SMSG_SET_PCT_SPELL_MODIFIER;
    uint8 family = GetSpellModFamily(mod);

    int i = 0;
    flag96 _mask = 0;
    for (int eff = 0; eff < 96; ++eff)
    {
        if (eff != 0 && eff % 32 == 0)
            _mask[i++] = 0;

        _mask[i] = uint32(1) << (eff - (32 * i));
        if (mod->mask & _mask)
        {
            int32 val = 0;
            for (SpellModContainer::iterator itr = m_spellMods[mod->op].begin(); itr != m_spellMods[mod->op].end(); ++itr)
            {
                if ((*itr)->type == mod->type && (*itr)->mask & _mask && GetSpellModFamily(*itr) == family)
                    val += (*itr)->value;
            }
            val += apply ? mod->value : -(mod->value);
            WorldPacket data(Opcode, (1 + 1 + 4 + 1));
            data << uint8(eff);
            data << uint8(mod->op);
            data << int32(val);
            data << uint8(family);
            SendDirectMessage(&data);
        }
    }

    if (apply)
    {
        m_spellMods[mod->op].insert(mod);
    }
    else
    {
        m_spellMods[mod->op].erase(mod);
        // mods bound to aura will be removed in AuraEffect::~AuraEffect
        if (!mod->ownerAura)
            delete mod;
    }
}
