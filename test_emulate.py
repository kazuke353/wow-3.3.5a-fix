"""Emulates the patched client's spell-modifier code with unicorn (pip install unicorn pefile).

Usage: python3 test_emulate.py Wow_patched.exe
Player is a druid (family 7). Expected on the patched exe:
  warrior spell bit5 op0  (1, 0, 110)   warrior talent applies to warrior spell
  druid  spell bit5 op0   (0, 0, 0)     ...and does not leak onto druid spells
  druid/mage spell bit70  (1, 3, 100)   old-format packet (no family) applies to all
  fam40 / fam0            no modifiers
The stock exe gives the opposite for the first two lines (the original bug).
"""
import sys, struct, pefile
from unicorn import *
from unicorn.x86_const import *
pe=pefile.PE(sys.argv[1]); mu=Uc(UC_ARCH_X86,UC_MODE_32)
mu.mem_map(0x400000, pe.OPTIONAL_HEADER.SizeOfImage)
mu.mem_write(0x400000, pe.header)
for s in pe.sections:
    mu.mem_write(0x400000+s.VirtualAddress, s.get_data()[:s.Misc_VirtualSize])
mu.mem_map(0x10000000,0x100000)  # stack + scratch
STOP=0x10000000; mu.mem_write(STOP,b'\xf4')
def call(fn,args,ecx=0):
    sp=0x100f0000
    for a in reversed(args): sp-=4; mu.mem_write(sp,struct.pack('<I',a))
    sp-=4; mu.mem_write(sp,struct.pack('<I',STOP))
    mu.reg_write(UC_X86_REG_ESP,sp); mu.reg_write(UC_X86_REG_ECX,ecx)
    mu.emu_start(fn,STOP,count=200000)
    return mu.reg_read(UC_X86_REG_EAX)
DS=0x10010000; BUF=0x10011000
def packet(opcode,payload):
    mu.mem_write(BUF,payload)
    # CDataStore: vtbl, buffer, base, alloc, size, read
    mu.mem_write(DS,struct.pack('<6I',0,BUF,0,len(payload),len(payload),0))
    call(0x7fdc60,[0,opcode,0,DS])
    return struct.unpack('<I',bytes(mu.mem_read(DS+0x14,4)))[0]
PCT,FLAT=0x267,0x266
mu.mem_write(0xd397b4,struct.pack('<I',7))  # player is a druid (family 7)
print('read pos', packet(PCT, struct.pack('<BBiB',5,0,10,4)))   # warrior talent: bit5 op0 +10%, family 4
print('read pos', packet(FLAT,struct.pack('<BBi',70,1,3)))       # old-format packet, no family
print('read pos', packet(FLAT,struct.pack('<BBiB',5,0,99,40)))   # out-of-range family: ignored
SP=0x10020000; OUT=0x10030000
def mods(fam,maskbits,op):
    rec=bytearray(0x300); struct.pack_into('<I',rec,0x240,fam)
    m=[0,0,0]
    for b in maskbits: m[b//32]|=1<<(b%32)
    struct.pack_into('<3I',rec,0x244,*m); mu.mem_write(SP,bytes(rec))
    mu.mem_write(OUT,b'\xaa'*8)
    r=call(0x7fd970,[SP,op,OUT,OUT+4])&0xff
    f,p=struct.unpack('<ii',bytes(mu.mem_read(OUT,8)))
    return r,f,p
print('warrior spell bit5 op0 ', mods(4,[5],0))
print('druid  spell bit5 op0  ', mods(7,[5],0))
print('druid  spell bit70 op1 ', mods(7,[70],1))
print('mage   spell bit70 op1 ', mods(3,[70],1))
print('fam40  spell bit5 op0  ', mods(40,[5],0))
print('fam0   spell bit70 op1 ', mods(0,[70],1))
