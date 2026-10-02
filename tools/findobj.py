"""Find UClass objects by name by walking GUObjectArray (FUObjectItem is 0x18 bytes, object pointer at +8).
Usage: python findobj.py <GUObjectArray address from UE4SS.log> Pawn UserWidget ...
Writes found.txt ("<name> <address>").
"""
from memread import *
import sys
p=Proc(pid_of()); N=Names(p,int(open('names_addr.txt').read(),16))
guo=int(sys.argv[1],16); want=set(sys.argv[2:])
objs=p.q(guo+0x10); num=p.i32(guo+0x10+0x14)
print("NumElements",num)
found={}
for i in range(num):
    chunk=p.q(objs+(i//65536)*8)
    if not chunk: continue
    o=p.q(chunk+(i%65536)*0x18+8)
    if not o: continue
    n=N.get(p.u32(o+0x18))
    if n in want:
        c=p.q(o+0x10); cn=N.get(p.u32(c+0x18)) if c else None
        if cn in ("Class","ASClass","BlueprintGeneratedClass","WidgetBlueprintGeneratedClass"):
            found[n]=o; print(n,cn,hex(o))
            if len(found)==len(want): break
open("found.txt","w").write("\n".join(f"{k} {v:x}" for k,v in found.items()))
