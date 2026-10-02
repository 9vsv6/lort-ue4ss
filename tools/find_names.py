"""Find LORT's FNamePool block array in the running game and save its address to names_addr.txt.

UE 5.7 name entries carry hash bits in their 2-byte header ("None" has header 0x011E), so we search for
the first entries by their text, then find the exe pointer that points at that block.
Usage: python find_names.py   (with LortGame-Win64-Shipping.exe running)
"""
import ctypes, ctypes.wintypes as wt, re, struct
from memread import Proc, Names, pid_of, k32


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wt.DWORD), ("PartitionId", wt.WORD), ("RegionSize", ctypes.c_size_t),
                ("State", wt.DWORD), ("Protect", wt.DWORD), ("Type", wt.DWORD)]


k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
MEM_COMMIT, MEM_IMAGE = 0x1000, 0x1000000
READABLE = (0x02, 0x04, 0x08, 0x20, 0x40)


def regions(p):
    a, m = 0, MBI()
    while k32.VirtualQueryEx(p.h, ctypes.c_void_p(a), ctypes.byref(m), ctypes.sizeof(m)):
        base = m.BaseAddress or 0
        if m.State == MEM_COMMIT and m.Protect in READABLE:
            yield base, m.RegionSize, m.Type
        a = base + m.RegionSize
        if a >= 0x7FFFFFFFFFFF:
            break


def main():
    p = Proc(pid_of())
    rx = re.compile(rb"None.{0,8}ByteProperty.{0,8}IntProperty", re.S)
    block0 = None
    for base, size, typ in regions(p):
        if typ == MEM_IMAGE or size > 512 * 1024 * 1024:
            continue
        d = p.read(base, size)
        m = rx.search(d) if d else None
        if m:
            block0 = base + m.start() - 2  # back up over the 2-byte entry header
            break
    if block0 is None:
        raise SystemExit("name pool not found")
    print("block0", hex(block0))
    needle = struct.pack("<Q", block0)
    for base, size, typ in regions(p):
        if typ != MEM_IMAGE:
            continue
        d = p.read(base, size)
        if not d:
            continue
        for m in re.finditer(re.escape(needle), d):
            cand = base + m.start()
            if Names(p, cand).get(0) == "None":
                print("blocks", hex(cand))
                open("names_addr.txt", "w").write(hex(cand))
                return
    raise SystemExit("blocks array not found")


if __name__ == "__main__":
    main()
