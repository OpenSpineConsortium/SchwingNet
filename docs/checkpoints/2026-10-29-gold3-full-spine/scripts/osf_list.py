"""List every file under a set of OSF nodes, recursively, with size and download link."""
import json, sys, time, urllib.request

def get(url):
    for attempt in range(8):
        try:
            time.sleep(0.4)
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "gold3-ct-reader"}), timeout=120) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(2 * (attempt + 1))
            last = e
    raise last

def walk(url, node, out):
    while url:
        d = get(url + ("&" if "?" in url else "?") + "page[size]=100") if "page[size]" not in url else get(url)
        for it in d["data"]:
            a = it["attributes"]
            if a["kind"] == "folder":
                walk(it["relationships"]["files"]["links"]["related"]["href"], node, out)
            else:
                out.append({"node": node, "path": a["materialized_path"], "size": a["size"], "url": it["links"]["download"]})
        url = d["links"].get("next")

if __name__ == "__main__":
    out = []
    for node in sys.argv[2:]:
        walk(f"https://api.osf.io/v2/nodes/{node}/files/osfstorage/", node, out)
        print(node, len(out), file=sys.stderr)
    json.dump(out, open(sys.argv[1], "w"), indent=0)
