"""Read a remote zip's central directory through HTTP range requests."""
import json, struct, subprocess, sys

def get_range(url, start, end, out):
    subprocess.run(["curl", "-sSL", "--retry", "5", "--max-time", "600", "-r", f"{start}-{end}", "-o", out, url], check=True)
    return open(out, "rb").read()

def central_directory(url, length, out):
    tail = get_range(url, length - 65536, length - 1, out + ".tail")
    i = tail.rfind(b"PK\x06\x06")
    size_cd, off_cd = struct.unpack("<QQ", tail[i + 40:i + 56])
    cd = get_range(url, off_cd, off_cd + size_cd - 1, out + ".cd")
    entries, p = [], 0
    while p < len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        (method, csize, usize, nlen, xlen, clen, lho) = (struct.unpack("<H", cd[p+10:p+12])[0], *struct.unpack("<II", cd[p+20:p+28]), *struct.unpack("<HHH", cd[p+28:p+34]), struct.unpack("<I", cd[p+42:p+46])[0])
        name = cd[p+46:p+46+nlen].decode()
        extra = cd[p+46+nlen:p+46+nlen+xlen]
        vals = []
        q = 0
        while q < len(extra):
            hid, hlen = struct.unpack("<HH", extra[q:q+4])
            if hid == 1:
                body = extra[q+4:q+4+hlen]
                vals = list(struct.unpack("<" + "Q" * (hlen // 8), body))
            q += 4 + hlen
        it = iter(vals)
        if usize == 0xFFFFFFFF: usize = next(it)
        if csize == 0xFFFFFFFF: csize = next(it)
        if lho == 0xFFFFFFFF: lho = next(it)
        entries.append({"name": name, "method": method, "csize": csize, "usize": usize, "offset": lho})
        p += 46 + nlen + xlen + clen
    return entries

if __name__ == "__main__":
    url, length, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    e = central_directory(url, length, out)
    json.dump(e, open(out, "w"))
    print(len(e))
