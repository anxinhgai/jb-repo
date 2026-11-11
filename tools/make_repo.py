#!/usr/bin/env python3
"""
make_repo.py - turn a folder of .deb files into a flat APT repo
(Sileo / Zebra / Installer ready). Pure Python 3, no dpkg needed.

    python3 tools/make_repo.py            # build in repo root
    python3 tools/make_repo.py --check    # build + verify

Input : debs/**/*.deb
Config: repo.json
Output: Packages, Packages.gz, Packages.xz, Packages.zst, Release, index.html
"""
import argparse
import gzip
import hashlib
import io
import json
import lzma
import os
import struct
import sys
import tarfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULTS = {
    "origin": "My Repo",
    "label": "My Repo",
    "suite": "stable",
    "version": "1.0",
    "codename": "ios",
    "components": "main",
    "description": "Free jailbreak packages",
    "support": "",
    "depiction": "",
    "icon": "CydiaIcon.png",
    "debs_dir": "debs",
}


# --------------------------------------------------------------------------- #
# read control out of a .deb (ar + control.tar.{gz,xz,zst,bz2,none})
# --------------------------------------------------------------------------- #
def ar_members(data):
    assert data[:8] == b"!<arch>\n", "not an ar archive"
    off = 8
    while off + 60 <= len(data):
        hdr = data[off:off + 60]
        name = hdr[0:16].decode().strip().rstrip("/")
        size = int(hdr[48:58].decode().strip())
        start = off + 60
        yield name, data[start:start + size]
        off = start + size + (size & 1)


def decompress(name, blob):
    if name.endswith(".zst"):
        try:
            import zstandard
        except ImportError:
            raise SystemExit("need `pip install zstandard` (or `zstd` CLI) for .zst debs")
        return zstandard.ZstdDecompressor().decompress(blob, max_output_size=64 << 20)
    if name.endswith(".gz"):
        return gzip.decompress(blob)
    if name.endswith(".xz") or name.endswith(".lzma"):
        return lzma.decompress(blob)
    if name.endswith(".bz2"):
        import bz2
        return bz2.decompress(blob)
    return blob


def parse_control(text):
    fields, order = {}, []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line[0] in " \t" and order:
            fields[order[-1]] += "\n" + line
        else:
            k, v = line.split(":", 1)
            fields[k] = v.strip()
            order.append(k)
    return fields, order


def deb_control(path):
    with open(path, "rb") as f:
        data = f.read()
    for name, blob in ar_members(data):
        if name.startswith("control.tar"):
            tar = tarfile.open(fileobj=io.BytesIO(decompress(name, blob)))
            for m in tar.getmembers():
                if os.path.basename(m.name) == "control" and m.isfile():
                    return parse_control(tar.extractfile(m).read().decode("utf-8", "replace"))
    raise SystemExit(f"{path}: no control file found")


# --------------------------------------------------------------------------- #
# Packages
# --------------------------------------------------------------------------- #
def build_packages(cfg):
    """Returns (Packages text, [entry dicts with fields/_file/_size/_arch])."""
    debs_dir = os.path.join(ROOT, cfg["debs_dir"])
    stanzas = []
    for dirpath, dirnames, filenames in os.walk(debs_dir):
        dirnames.sort()
        for fn in sorted(filenames):
            if not fn.endswith(".deb"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            blob = open(full, "rb").read()
            fields, order = deb_control(full)
            lines = []
            for key in ("Package", "Version", "Architecture"):
                if key in fields:
                    lines.append(f"{key}: {fields[key]}")
            for key in order:
                if key in ("Package", "Version", "Architecture", "Filename", "Size",
                           "MD5sum", "SHA1", "SHA256", "SHA512"):
                    continue
                lines.append(f"{key}: {fields[key]}")
            lines += [
                f"Filename: {rel}",
                f"Size: {len(blob)}",
                f"MD5sum: {hashlib.md5(blob).hexdigest()}",
                f"SHA1: {hashlib.sha1(blob).hexdigest()}",
                f"SHA256: {hashlib.sha256(blob).hexdigest()}",
                f"SHA512: {hashlib.sha512(blob).hexdigest()}",
            ]
            fields["_file"] = rel
            fields["_size"] = len(blob)
            stanzas.append((fields.get("Package", fn).lower() + rel, "\n".join(lines), fields))
    stanzas.sort(key=lambda x: (x[0], x[1]))
    return "\n\n".join(x[1] for x in stanzas) + ("\n" if stanzas else ""), \
        [x[2] for x in stanzas]


# --------------------------------------------------------------------------- #
# Release
# --------------------------------------------------------------------------- #
def write_release(cfg, packages_text, files):
    archs = sorted({a for a in cfg.get("_archs", [])} or {"iphoneos-arm64"})
    out = [
        f"Origin: {cfg['origin']}",
        f"Label: {cfg['label']}",
        f"Suite: {cfg['suite']}",
        f"Version: {cfg['version']}",
        f"Codename: {cfg['codename']}",
        f"Architectures: {' '.join(archs)}",
        f"Components: {cfg['components']}",
        f"Description: {cfg['description']}",
    ]
    for key in ("support", "depiction"):
        if cfg.get(key):
            out.append(f"{key.capitalize()}: {cfg[key]}")
    if cfg.get("icon"):
        out.append(f"Icon: {cfg['icon']}")
    out.append("Date: " + time.strftime("%a, %d %b %Y %H:%M:%S UTC", time.gmtime()))
    for algo, fn in (("MD5Sum", hashlib.md5), ("SHA1", hashlib.sha1),
                     ("SHA256", hashlib.sha256), ("SHA512", hashlib.sha512)):
        out.append(f"{algo}:")
        for name, blob in files:
            out.append(f" {fn(blob).hexdigest()} {len(blob):16d} {name}")
    text = "\n".join(out) + "\n"
    open(os.path.join(ROOT, "Release"), "w").write(text)
    return text


# --------------------------------------------------------------------------- #
# index.html
# --------------------------------------------------------------------------- #
PAGE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{label}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#0b0e14; color:#e6e9ef;
         font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
  .wrap {{ max-width:820px; margin:0 auto; padding:40px 22px 60px; }}
  header {{ display:flex; gap:16px; align-items:center; margin-bottom:8px; }}
  header img {{ width:64px; height:64px; border-radius:16px; }}
  h1 {{ font-size:24px; margin:0; letter-spacing:-.02em; }}
  .sub {{ color:#8b93a3; font-size:13px; margin:2px 0 0; }}
  .url {{ display:flex; gap:8px; align-items:center; background:#131824; border:1px solid #232a3a;
          border-radius:12px; padding:12px 14px; margin:22px 0 14px; flex-wrap:wrap; }}
  .url code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:13px;
               color:#9ad1ff; word-break:break-all; }}
  .btns {{ display:flex; gap:10px; flex-wrap:wrap; }}
  a.btn {{ display:inline-block; text-decoration:none; font-weight:600; font-size:13.5px;
           padding:10px 16px; border-radius:10px; border:1px solid #2b3346; color:#e6e9ef; }}
  a.btn.primary {{ background:#2f6bff; border-color:#2f6bff; }}
  h2 {{ font-size:14px; text-transform:uppercase; letter-spacing:.12em; color:#8b93a3;
        margin:34px 0 12px; font-weight:600; }}
  .pkg {{ background:#10151f; border:1px solid #1d2432; border-radius:12px;
          padding:14px 16px; margin-bottom:10px; }}
  .pkg .top {{ display:flex; justify-content:space-between; gap:12px; align-items:baseline; }}
  .pkg .name {{ font-weight:600; }}
  .pkg .ver {{ font-family:ui-monospace,monospace; font-size:12px; color:#7ee0a8; }}
  .pkg .meta {{ color:#8b93a3; font-size:12.5px; margin-top:4px;
                font-family:ui-monospace,monospace; }}
  .pkg .desc {{ color:#c3cad6; font-size:13.5px; margin-top:6px; }}
  .pkg a {{ color:#9ad1ff; font-size:12.5px; text-decoration:none; }}
  footer {{ margin-top:36px; color:#5f6878; font-size:12px; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <img src="{icon}" alt="">
    <div>
      <h1>{label}</h1>
      <p class="sub">{description}</p>
    </div>
  </header>

  <div class="url"><span style="color:#8b93a3;font-size:13px">Source URL</span>
    <code id="src">https://USERNAME.github.io/REPO/</code></div>
  <div class="btns">
    <a class="btn primary" id="sileo" href="#">＋ Add to Sileo</a>
    <a class="btn" id="zebra" href="#">＋ Add to Zebra</a>
    <a class="btn" id="copy" href="#">Copy URL</a>
  </div>

  <h2>{count} package(s)</h2>
  {packages}

  <footer>APT repository · flat layout · generated {date}</footer>
</div>
<script>
  var src = location.origin + location.pathname.replace(/index\\.html$/, "");
  if (src.startsWith("file:")) src = document.getElementById("src").textContent;
  document.getElementById("src").textContent = src;
  document.getElementById("sileo").href = "sileo://source/" + src;
  document.getElementById("zebra").href = "zbra://sources/add/" + src;
  document.getElementById("copy").onclick = function (e) {{
    e.preventDefault();
    navigator.clipboard && navigator.clipboard.writeText(src);
    e.target.textContent = "Copied";
  }};
</script>
</body>
</html>
"""


def build_index(cfg, entries):
    rows = []
    for c in entries:
        size = c.get("_size", 0)
        rows.append(
            f'  <div class="pkg"><div class="top"><span class="name">{c["Package"]}</span>'
            f'<span class="ver">{c.get("Version", "")}</span></div>'
            f'<div class="meta">{c.get("Architecture", "")} · {size/1024:.0f} KB'
            f' · {c.get("Section", "—")}</div>'
            f'<div class="desc">{c.get("Description", "").splitlines()[0]}</div>'
            f'<div style="margin-top:8px"><a href="{c["_file"]}">download .deb</a></div></div>')
    html = PAGE.format(
        label=cfg["label"], description=cfg["description"], icon=cfg["icon"] or "",
        count=len(rows), packages="\n".join(rows),
        date=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()))
    open(os.path.join(ROOT, "index.html"), "w").write(html)


# --------------------------------------------------------------------------- #
def compress_packages(text):
    raw = text.encode()
    files = [("Packages", raw)]
    files.append(("Packages.gz", gzip.compress(raw, 9, mtime=0)))
    files.append(("Packages.xz", lzma.compress(raw, preset=9)))
    try:
        import zstandard
        files.append(("Packages.zst", zstandard.ZstdCompressor(level=19).compress(raw)))
    except ImportError:
        pass
    for name, blob in files:
        open(os.path.join(ROOT, name), "wb").write(blob)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify the generated repo")
    args = ap.parse_args()

    cfg = dict(DEFAULTS)
    cfg_path = os.path.join(ROOT, "repo.json")
    if os.path.exists(cfg_path):
        cfg.update({k: v for k, v in json.load(open(cfg_path)).items() if v})

    packages_text, entries = build_packages(cfg)
    if not entries:
        raise SystemExit(f"no .deb found in {cfg['debs_dir']}/")
    archs = sorted({e.get("Architecture", "?") for e in entries})
    cfg["_archs"] = archs

    open(os.path.join(ROOT, "Packages"), "w").write(packages_text)
    files = compress_packages(packages_text)
    release = write_release(cfg, packages_text, files)
    build_index(cfg, entries)

    print(f"repo: {cfg['label']}  ({len(entries)} package(s), arch: {' '.join(archs)})")
    for c in entries:
        print(f"  - {c['Package']} {c.get('Version','')} [{c.get('Architecture','')}] "
              f"{c['_size']/1024:.0f} KB  -> {c['_file']}")
    print("wrote: Packages (+ .gz/.xz/.zst), Release, index.html")

    if args.check:
        ok = True
        for name, blob in files:
            same = open(os.path.join(ROOT, name), "rb").read() == blob
            ok &= same
        # every Filename in Packages must exist
        import re
        for m in re.finditer(r"^Filename: (.+)$", packages_text, re.M):
            p = os.path.join(ROOT, m.group(1))
            exists = os.path.exists(p)
            if not exists:
                print("MISSING:", m.group(1))
            ok &= exists
        # checksums in Release must match
        for line in release.splitlines():
            parts = line.split()
            if len(parts) == 3 and len(parts[0]) in (32, 40, 64, 128):
                blob = open(os.path.join(ROOT, parts[2]), "rb").read()
                algo = {32: hashlib.md5, 40: hashlib.sha1,
                        64: hashlib.sha256, 128: hashlib.sha512}[len(parts[0])]
                if algo(blob).hexdigest() != parts[0]:
                    print("CHECKSUM MISMATCH:", parts[2])
                    ok = False
        print("check:", "OK" if ok else "FAILED")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
