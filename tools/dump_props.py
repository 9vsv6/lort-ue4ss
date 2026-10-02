"""Walk a class's FProperty chain (ChildProperties at UStruct+0x50, Next at FField+0x18) and print each property's
type, name, Offset_Internal (+0x48 in LORT) and the words at +0x70..+0x90 to identify subclass members.
Usage: python dump_props.py <address of any object of the class, e.g. a CDO from UE4SS.log>
"""
from memread import *
import sys
p=Proc(pid_of()); N=Names(p,int(open('names_addr.txt').read(),16))
def oname(o): return N.get(p.u32(o+0x18)) if o else None
cdo=int(sys.argv[1],16); c=p.q(cdo+0x10)
seen={}
while c:
    f=p.q(c+0x50)
    while f:
        t=N.get(p.u32(p.q(f+8)))
        if t not in seen: seen[t]=f
        f=p.q(f+0x18)
    c=p.q(c+0x40)
for t,f in seen.items():
    w=[p.q(f+o) for o in range(0x70,0xA8,8)]
    desc=[]
    for o,v in zip(range(0x70,0xA8,8),w):
        s=f"{v:x}"
        if v and 0x10000<v<0x7fffffffffff:
            on=oname(v) if p.read(v+0x18,4) else None
            fc=None
            try: fc=N.get(p.u32(p.q(v+8))) 
            except Exception: pass
            s+=f"({on}|ff:{fc})"
        desc.append(f"+{o:x}={s}")
    print(f"{t:22} {N.get(p.u32(f+0x20))!s:28} off={p.i32(f+0x48):#x} sz={p.i32(f+0x34)}  "+"  ".join(desc[:5]))
