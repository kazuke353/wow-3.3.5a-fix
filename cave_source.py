"""Assembly source for the per-family spell modifier code cave used by patch_classless.py.

Run `python3 cave_source.py` (needs `pip install keystone-engine`) to print the bytes
that patch_classless.py embeds as CAVE_CODE.
"""
import keystone
CODE=0xdfd000; TABLES=0xdfe000; BLOCK=0x5d00; HALF=0x2e80; NFAM=32
OLD_PCT=0xd397d8
GET_U8=0x47b340; GET_U32=0x47b3c0
DELTA=TABLES-OLD_PCT
asm=f"""
getmods:
  add esi, esi
  mov eax, dword ptr [ebx+0x240]
  cmp eax, {NFAM}
  jb gm_ok
  mov eax, {NFAM}
gm_ok:
  imul eax, eax, {BLOCK}
  lea esi, [esi+eax+{DELTA}]
  mov eax, 2
  ret

handler:
  push ebp
  mov ebp, esp
  sub esp, 8
  push esi
  push edi
  mov esi, dword ptr [ebp+0x14]
  lea eax, [ebp-1]
  push eax
  mov ecx, esi
  mov edi, {GET_U8}
  call edi
  lea eax, [ebp-2]
  push eax
  mov ecx, esi
  call edi
  lea eax, [ebp-8]
  push eax
  mov ecx, esi
  mov eax, {GET_U32}
  call eax
  movzx ecx, byte ptr [ebp-1]
  cmp ecx, 96
  jae h_done
  movzx edx, byte ptr [ebp-2]
  cmp edx, 31
  jae h_done
  imul ecx, ecx, 31
  add ecx, edx
  lea ecx, [ecx*4+{TABLES}]
  cmp dword ptr [ebp+0xc], 0x267
  je h_pct
  add ecx, {HALF}
h_pct:
  mov edx, dword ptr [ebp-8]
  mov eax, dword ptr [esi+0x14]
  cmp eax, dword ptr [esi+0x10]
  jae h_all
  push ecx
  push edx
  lea eax, [ebp-3]
  push eax
  mov ecx, esi
  call edi
  pop edx
  pop ecx
  movzx eax, byte ptr [ebp-3]
  cmp eax, {NFAM}
  jae h_done
  imul eax, eax, {BLOCK}
  mov dword ptr [ecx+eax], edx
  jmp h_done
h_all:
  mov eax, {NFAM}
h_loop:
  mov dword ptr [ecx], edx
  add ecx, {BLOCK}
  dec eax
  jnz h_loop
h_done:
  pop edi
  pop esi
  mov eax, 1
  mov esp, ebp
  pop ebp
  ret
"""
ks=keystone.Ks(keystone.KS_ARCH_X86,keystone.KS_MODE_32)
enc,_=ks.asm(asm,CODE)
code=bytes(enc)
# find handler offset by assembling getmods alone
g,_=ks.asm(asm.split("handler:")[0],CODE)
print("len",len(code),"handler_off",hex(len(g)))
print(code.hex())
