# coordbench#17, round four's review, as far as it ran (2026-10-14 23:35 UTC)

The adversarial review of coordbench#17's head 21f5382 (the fourth round of
read-back fixes), stopped when the owner's weekly usage ran out. Three lenses
ran: regression and cost, coverage, and claims; the claims lens and one
verifier did not finish, so the claims lens left nothing and one finding is
unverified. Every finding below was reproduced by its reviewer; "verified"
means a second agent reproduced it independently in its own copy. The
marker in every fixture is coordbench's stand-in PLANTED, a made-up string.
Paths under SCRATCHDIR were the reviewers' own scratch copies and are gone.

What it means: do not merge #17 at 21f5382. The regression lens found a
verified blocker (a zip -s first part that ends with a stored zip passes
with the marker inside, which 0d3279b refused) and three verified
should-fix findings; fix each with a test, rerun the full check, review the
fixes, then merge.

# Lens regression

## Checked and found fine

All runs compared 0d3279b and 21f5382 on the same files, under Python 3.12 with -I. ReadingBack passes 26 tests, and `bash scripts/check.sh` passes: 1109 tests OK, 18 skipped.

Same verdict on both commits except where noted, with and without PLANTED inside, for these ordinary files:
- **GNU tar 1.35:** gnu, oldgnu, pax, posix, ustar and v7, each plain, -z, -J, -j and --lzma. Also sparse files (gnu, oldgnu, pax 0.0/0.1/1.0), 150-character names and symlinks, hard links, FIFOs, -g incremental, -V label, --xattrs --acls, huge numeric uid/gid, -b 1, and -M multi-volume parts. The tars that hold only a gzipped marker are all found.
- **Info-ZIP zip 3.0:** default, -0, -9, -Z bzip2, -fz, stdin, a comment, and -s in one part (now read instead of refused, as intended) and in several parts. In a multi-part split, the members on the last disk are found and the first part is refused.
- **zip in history:** a last part that holds only the directory (the central directory straddles parts) gives no members, which is consistent.
- **Python zipfile:** stored, deflated, bzip2 and lzma, with and without force_zip64.
- **gzip:** multi-member, -n, --rsyncable, zero padding, trailing junk, cut short, empty, not gzip. The scrub pass refuses and rewrites as before. Each member costs 1 KiB as in the read-back: 200000 empty members cost 204.8 MB on both sides in 0.5 s.
- **xz and lzma:** xz -0/-6/-9/-e, and lzma with presets and with lc/lp/pb/dict across liblzma's whole range. Python's FORMAT_ALONE with custom filters is now found; 0d3279b missed it. The lc+lp<=4 and byte<225 bound matches liblzma.
- **bzip2 and ar:** bzip2 -1/-9. GNU ar (rc, rcs), llvm-ar gnu, bsd and darwin with long names, odd sizes and gzip or xz members (BSD and darwin are now found), and thin archives.
- **Packages:** .deb with -Zxz, -Zgzip, -Znone and -Zzstd (zstd still refused, as before). Also setuptools sdists, npm pack tarballs and jars.
- **git:** loose objects at the default level and at core.compression 0, gc and gc --aggressive packs, full and incremental bundles, and a repository whose history holds every fixture above. The clean history cost 72.3 MB at 0d3279b and 73.0 MB at 21f5382.
- **GNU tars with one byte of the first header wrong:** gnu, ustar, oldgnu and pax, with only the first member holding the marker. 0d3279b passed them; 21f5382 finds them.
- **A sweep of 140,076 files under /usr/lib, /usr/share, /usr/bin, /usr/local and /opt,** Go's archive testdata among them. The only change in kinds or verdict was Go's neg-size.tar, refused by the depth limit before and clean now, which is right: it is one block and is searched as plain bytes. No file got slower or costlier.

**Code read with no fault found:**
- split_part agrees with zipfile's rfind on commented archives.
- ar_members' padding of length % 2 is right for BSD members whose size includes the name.
- tar_members' ReadError branch steps over what follows and then re-raises.
- stepped_over and what_follows always advance, and their walk and copies cost time in proportion to bytes already charged.
- is_broken_tar's alignment is consistent because start is a multiple of 512.
- The UNOPENED_NAMES early return only adds weak signs after an unopened sure sign, and in a work tree that sign still refuses first.
- read_for_scrub's member loop matches gzip on zero padding and trailing bytes.

**Fixture paths:** the repros are under /tmp/claude-0/-home-claude-symphony-template/171b4d76-da53-585e-a4d4-4a4eb26e06e6/scratchpad/wf5-review-regression/rp (f1 for the split zip; tools/structerr2.py and tools/dodge1.py for the other two).

## [regression] blocker | A zip -s first part that ends with a stored zip is now read as that inner zip, so a split archive holding the token passes (0d3279b refused it)

Status: verified: reproduced=True real=True severity=blocker

**repro**: Build the fixture under SCRATCHDIR with Info-ZIP only:
  mkdir -p inner src run
  head -c 20000 /dev/urandom > inner/data.bin; (cd inner && zip -q ../src/b-inner.zip data.bin)
  for i in $(seq 30); do echo "export TOKEN=coordbench-planted-stand-in-7f3a9c2e51d0"; done > src/a-notes.txt
  head -c 100000 /dev/urandom > src/c-random.bin
  (cd src && zip -s 64k ../run/split.zip a-notes.txt b-inner.zip c-random.bin)
zip reports a-notes.txt deflated, b-inner.zip stored (by default zip stores .zip files) and c-random.bin deflated. This writes split.z01, split.z02 and split.zip. Then, with each copy on sys.path: run.packed_kinds(bytes of split.z01) and run.unscrubbed('run', [PLANTED]). Also run command_scrub on a copy of run/ with run.credential_values patched to return [PLANTED]. The same result came from -s 1m with a 1 MB file before b-inner.zip. Checks: `zip -s 0 split.zip --out whole.zip; unzip -p whole.zip a-notes.txt | grep -c PLANTED` prints 30, and grep -c finds PLANTED in none of the three parts.

**observed**: 0d3279b: split.z01 kinds ["a split zip's first part (zip -s)"], and unscrubbed gives [".../split.z01: could not be read (a split zip's first part (zip -s), a format the scrub cannot open)"], so command_scrub exits 2.
21f5382: split.z01 kinds ['zip'], unscrubbed gives [], and command_scrub prints "no file holds the agents' credential" and exits 0.
The cause: packed_kinds takes SPANNED_ZIP plus ends_as_zip(data) as a whole one-part zip. ends_as_zip uses zipfile.is_zipfile on the last ZIP_TAIL bytes, and Python 3.12's _EndRecData accepts any end record in that window, even with other bytes after it. So the stored inner zip's end record makes the first part a "zip". zipfile then reads only the inner zip's members. split_part reads that inner record as disk 0, so nothing is refused. The outer a-notes.txt is never inflated. The last part split.zip holds only the directory and passes as a weak sign. split.z02 is a middle part and is searched as it is.

**expected**: As in 0d3279b and as the README says: a split zip's first part (a file that starts with PK\x07\x08 and has no end record of its own) is refused in a work tree. Only a zip -s archive that really fits in one part is read as an ordinary zip.

**fix**: In packed_kinds, take SPANNED_ZIP as a whole zip only when the archive's own end record ends the file. One way: find the record by rfind in the tail and require at + 22 + comment_length == len(data), with disk numbers 0. Another way: require the directory it names to place the first local header at offset 4. Otherwise leave the file as the unopened first part. Add a test that splits a directory holding a stored .zip with zip -s 64k.

**verifier's reasoning**: I reproduced the finding exactly, in my own copies under /tmp/claude-0/-home-claude-symphony-template/171b4d76-da53-585e-a4d4-4a4eb26e06e6/scratchpad/wf5-verify-regression-0: `old` has 0d3279b's files checked out and `new` is 21f5382. I built the fixture with Info-ZIP only, following the repro. zip reported "a-notes.txt (deflated 96%)", "b-inner.zip (stored 0%)" and "c-random.bin (deflated 0%)". `grep -c` found the marker in none of the parts. After `zip -s 0 split.zip --out whole.zip`, `unzip -p whole.zip a-notes.txt | grep -c` printed 30.

What I observed with fix1 (two parts at 64k):
- 0d3279b: split.z01 kinds ["a split zip's first part (zip -s)"]. unscrubbed returns the refusal "split.z01: could not be read (a split zip's first part (zip -s), a format the scrub cannot open)". command_scrub, with credential_values patched to return [PLANTED], on a copy of run/ exits 2.
- 21f5382: split.z01 kinds ['zip'] and unscrubbed returns []. command_scrub prints "...run-new: no file holds the agents' credential" and exits 0. A run directory that holds the marker would be published.

The cause is as the reviewer says. split.z01 is 65536 bytes and starts with SPANNED_ZIP, and ends_as_zip is True. The only PK\x05\x06 in the file is at offset 20358: the stored inner zip's end record, which ends at 20380, not at the end of the file. split_part returns None because that record says disk 0. zipfile lists only the inner zip's member, data.bin (header_offset 214). So the deflated a-notes.txt in the outer first part is never opened. split.zip is only a weak sign ('prefixed zip') and refuses nothing. In the diff, `data.startswith(SPANNED_ZIP) and ends_as_zip(data)` is new in 21f5382, so this is a regression.

Variants:
- fixA, four parts (z01, z02, z03, zip) at 64k: same result. 0d3279b refuses z01; 21f5382 returns [].
- fixB, `-s 1m` with a 1 MB file before b-inner.zip: same result.
- fixC, the control, a split with no stored inner zip: still refused in 21f5382. The stored inner zip is what triggers the bypass.
- fixD, a real one-part `zip -s 1m` archive holding the notes and a stored zip: read as 'zip' in 21f5382, and the marker is found ("holds the agents' credential, read through zip").

The README contradicts 21f5382's behaviour. It lists "a split zip's (zip -s) first part" among the files that make the scrub exit 2. Only "a zip -s archive that fits in one part" is to be read as an ordinary zip.

Why blocker: the input is a file made by Info-ZIP in an ordinary mode, `zip -s` over a directory that holds a .zip, which zip stores by default. 0d3279b refused it, and 21f5382 lets it pass with exit 0 and publishes the marker. At the minimum split size (64k) the whole first part lies inside ZIP_TAIL, so any stored zip in the first part triggers it. At larger split sizes the inner zip has to end in the last ~64 KiB of the first part.

The ReadingBack tests on 21f5382 pass (26 tests, OK), and none of them splits a directory that holds a stored zip. I did not run the full scripts/check.sh.

**verifier's fix**: In packed_kinds, read a file that starts with SPANNED_ZIP as a whole zip only when its own end record ends the file and says disk 0. Then a stored inner zip's record can no longer stand in for the outer one.

I tried this in a third copy (`fixed`). The `SPANNED_ZIP` condition calls a new helper in place of `ends_as_zip(data)`:

    def is_one_part(data):
        if not ends_as_zip(data):
            return False
        tail = bytes(data[-ZIP_TAIL:])
        at = tail.rfind(b"PK\x05\x06")
        record = tail[at:at + 22]
        if len(record) < 22 or record[4:8] != bytes(4):
            return False
        return at + 22 + int.from_bytes(record[20:22], "little") == len(tail)

Results with the patch:
- fix1, fixA and fixB: split.z01 is again refused as "a split zip's first part (zip -s)". Its kinds become ["a split zip's first part (zip -s)", 'prefixed zip'].
- fixC: still refused.
- fixD, the real one-part zip -s archive: still read as 'zip', and the marker is found.
- ReadingBack: 26 tests, OK.

Add a ReadingBack test with Info-ZIP: `zip -s 64k` over a directory holding a deflated text file with PLANTED and a stored .zip. Assert that the .z01 part is refused, or that the run's scrub exits 2.

## [regression] should-fix | is_broken_tar passes a header shorter than 512 bytes to checksum_holds; the struct.error escapes the scrub as a traceback and stops the rest of the pass

Status: verified: reproduced=True real=True severity=should-fix

**repro**: Python 3.12, each copy on sys.path, with run.credential_values = lambda environ=None: [PLANTED]:
  buf = io.BytesIO()
  with tarfile.open(fileobj=buf, mode='w', format=tarfile.GNU_FORMAT) as t:
      for name, body in (('a.txt', b'hello\n'*10), ('b.txt', b'world\n'*10)):
          info = tarfile.TarInfo(name); info.size = len(body); t.addfile(info, io.BytesIO(body))
  data = bytearray(buf.getvalue()); data[257] ^= 1   # the first header's magic, one byte wrong
  (d / 'transcript.bin').write_bytes(data[:1024 + 400])   # cut short inside the second header
  (d / 'zz-log.txt').write_text(f'TOKEN={PLANTED}\n')
  run.command_scrub(types.SimpleNamespace(run_dir=str(d)))
(The file is named without .tar so that scrub_file reaches packed_kinds. A .gz holding such a tar does the same.)

**observed**: 0d3279b: zz-log.txt is rewritten, then "no file holds the agents' credential", exit 0.
21f5382: a traceback ending in run.py:1288 is_broken_tar -> run.py:1301 checksum_holds, "struct.error: unpack requires a buffer of 512 bytes". command_scrub catches only OSError and scrub_paths catches (OSError, EOFError, ValueError, zlib.error), so the exception escapes both. zz-log.txt still holds PLANTED. On its own, unscrubbed reports the tar as "could not be read (unpack requires a buffer of 512 bytes)". In run.py the same exception would come out of scrub_pair inside finish_pair's finally: the files after it stay unscrubbed and the pair is recorded as an error. The job publishes nothing on a nonzero exit, so this fails safe, but it is a crash where 0d3279b ran to the end.

**expected**: is_broken_tar treats a block that is cut short as no header, as header_size and is_tar already do. The scrub pass never ends in a traceback.

**fix**: In is_broken_tar, require len(data) - (at - 257) >= 512 before calling checksum_holds, or have checksum_holds return False when len(header) != 512. Also consider having scrub_paths catch Exception per file, as unscrubbed does, so that one unreadable file never stops the scrub of the others.

**verifier's reasoning**: I reproduced this in my own copies, old (0d3279b) and new (21f5382), under SCRATCHDIR, using Python 3.12 with -I. The script is SCRATCHDIR/scripts/repro.py. It builds a GNU-format tar with two members, flips data[257], keeps only data[:1024+400], and writes that as transcript.bin (and, in a second run, gzipped as transcript.bin.gz). It also writes zz-log.txt containing TOKEN=PLANTED, then calls run.command_scrub with credential_values patched to return [PLANTED].

What I saw:
- 0d3279b, plain and .gz: "credential was in 1 files and is scrubbed out of them", then "no file holds the agents' credential", exit 0. zz-log.txt no longer holds PLANTED.
- 21f5382, plain and .gz: the exception escapes command_scrub as a traceback. The chain is packed_kinds (run.py:1230) -> is_broken_tar (run.py:1288) -> checksum_holds (run.py:1301), ending in "struct.error: unpack requires a buffer of 512 bytes". zz-log.txt still holds PLANTED.
- 21f5382, same cut but with the first header left intact: exit 0 and zz-log.txt scrubbed. is_tar short-circuits there, so only the new is_broken_tar path is at fault.

Calling the functions directly on 21f5382 (scripts/direct.py):
- unscrubbed() returns "transcript.bin: could not be read (unpack requires a buffer of 512 bytes)".
- scrub_credentials() raises struct.error, because scrub_paths catches only (OSError, EOFError, ValueError, zlib.error).
- In run.py, finish_pair calls scrub_pair in a finally, so the same exception would propagate out of it. I read that code; I did not run a pair.

Cause: is_broken_tar slices data[at-257:at+255]. When the file ends inside that block, the slice has between 262 and 511 bytes. TAR_CHECKSUM still matches header[148:156], and struct.unpack("512b", ...) then raises. Scanning every cut length of the 10240-byte tar, lengths 1286 through 1535 raise (250 lengths); 0d3279b raises on none of them.

Impact, from reading bench/cooperbench/actions/scrub.sh and run-pair/action.yml: the traceback exits nonzero, scrub.sh deletes RUN_DIR and publish=false. So it fails safe and nothing leaks. The cost is a crash and a lost pair, where 0d3279b ran to the end and published clean files.

Plausibility: is_broken_tar is only reached when the first header does not read, so the input needs a tar whose first header is broken, cut short inside a later header. That is not something an ordinary tool writes. The rules allow should-fix for a regression from 0d3279b on any input, and this is one: is_broken_tar is new in 21f5382, and the old code finished the pass on these exact bytes. I would not rate it higher than should-fix, because it fails safe.

Checked and found fine: with an intact first header, the same truncation gives no error. ReadingBack passes on 21f5382 (26 tests OK).

**verifier's fix**: Guard the header's length before checksum. I made this change in SCRATCHDIR/fix/coordbench/run.py, in checksum_holds:

```
field = TAR_CHECKSUM.fullmatch(header[148:156])
if len(header) != 512 or not field:
    return False
```

(The alternative is to require len(data) - (at - 257) >= 512 in is_broken_tar's loop before calling it.) With that change:
- the repro exits 0 and zz-log.txt is scrubbed;
- unscrubbed() returns [];
- scrub_credentials rewrites zz-log.txt;
- none of the 10240 cut lengths raises;
- ReadingBack still passes (26 tests OK).

Add a ReadingBack test with this fixture: a tar whose first header is broken and which is cut inside its second header. The test should expect the scrub to run to the end.

Optionally, scrub_paths could also catch Exception per file, as unscrubbed does, so that one unreadable file never stops the others from being scrubbed. That is defence in depth, not needed for this fix.

## [regression] nit | A first block with ustar's magic but non-octal checksum and size fields now hides what follows it; 0d3279b refused the file

Status: nit, not verified

**repro**: Build a ustar tar with tarfile, one member notes.gz = gzip.compress(f'export TOKEN={PLANTED}\n'.encode()*40). Set data[148] = ord('x') and data[124] = ord('x'), so the checksum field and the size field each have one non-octal byte. Write the result as notes.tar and call run.unscrubbed(dir, [PLANTED]).

**observed**: 0d3279b: ["notes.tar: could not be read (layers nested deeper than the scrub reads, the last tar)"].
21f5382: [].
is_tar is true by the magic. tarfile reads no member. stepped_over(0, len) meets block 0, whose size does not read. That block is not shaped, so what_follows tries only begin=0, and the new (0, len(data)) guard drops it. The gzip stream at offset 512 is never opened. Go's testdata neg-size.tar shows the same change from refused to clean, but it is one block and holds nothing.

**expected**: When the guard stops the whole input being given back, the bytes after the first block are still opened (from start + 512), or the tar is refused.

**fix**: In what_follows, when begin == 0 and end == len(data) is skipped, still try start + 512 whether or not the block is shaped. Or have tar_members raise when it read nothing and stepped_over gave nothing for a non-zero input.

## [regression] nit | The last part of a zip64 split archive (zip -fz -s) is not read in a repository's history

Status: nit, not verified

**repro**: In a directory with split-pay.bin (300000 random bytes), aa-secret.txt and zz-secret.txt (both holding PLANTED lines), run `zip -q -r -fz -s 100k sp.zip .`. Commit sp.z01, sp.z02 and sp.zip to a git repository, remove them in a second commit and run git gc, then run run.unscrubbed on the repository. For comparison, do the same without -fz.

**observed**: Without -fz, 21f5382 reports "holds the agents' credential, read through git packfile, zip" (zz-secret.txt lies on the last disk). With -fz, both commits report []. zipfile refuses the part ("zipfiles that span multiple disks are not supported"), so ends_as_zip is false, packed_kinds gives [], and the members on its own disk are never searched. In a work tree, sp.z01 still refuses the directory.

**expected**: The README says a split zip's last part has the members it holds whole searched, which this round added for history. A zip64 split's last part either does that too or is listed with the first and middle parts as a limit in history.

**fix**: Document it beside "a split zip's first and middle parts in history". Or read the local headers that split_part's disk places in the part without zipfile's directory check.

# Lens coverage

## Checked and found fine

I ran every fixture against a scratch copy of 21f5382 at /tmp/claude-0/-home-claude-symphony-template/171b4d76-da53-585e-a4d4-4a4eb26e06e6/scratchpad/wf5-review-coverage/repo, and against an extract of 0d3279b for the regression checks, with Python 3.12.3. Fixtures are under .../wf5-review-coverage/fx, builders under .../scripts. The ReadingBack tests passed (26 tests) and `bash scripts/check.sh` passed (1109 tests, 18 skipped, "checks ok"). /home/claude/coordbench is untouched.

Reported correctly (unscrubbed() named the file holding the marker):
- Split zips without zip64:
  - The last part of `zip -s 64k` (the member whole in the last part), alone, renamed, in a work tree with all parts (.z01 refused, .zip reported), inside a .tgz, and in a bundle.
  - The last part committed and removed (loose and packed), and all three parts committed (packed).
  - One-part `zip -s 1m` and `zip -fz -s 1m`, and a one-part streamed `zip -s 1m -`, each in the work tree and loose and packed; one-part zip -s also bundled, in a .tgz and in a BSD ar.
- Tar:
  - GNU tar --format gnu, oldgnu, pax, posix, ustar and v7 with 120-plus-character names.
  - Sparse members (gnu, oldgnu, pax 0.0, 0.1, 1.0), --listed-incremental (dumpdir), --label, and the multi-volume first and second volumes (the first refused as cut short).
  - Non-UTF-8 names in posix and gnu, a pax comment, git archive tar, tgz and zip, python -m tarfile (.tar, .tar.xz, .tar.bz2), and tarfile pax, gnu and ustar .tar.gz.
  - A first header with one byte broken (name, mode, size, mtime, typeflag, magic, version, prefix) in gnu, pax, posix and ustar, alone, as .tgz, .txz and .tlz (pb=0), packed and bundled.
  - A header broken right after a pax header or a GNU long-name header, with the marker only in the member after it, in the work tree and loose.
- ar:
  - GNU ar (long names, D mode, symbol table with an object file) and llvm-ar gnu, bsd and darwin with long and short names, with and without symbol tables.
  - Each in loose and packed history; a cut BSD ar in the work tree and in history.
  - .deb from dpkg-deb -Zgzip, -Zxz and -Znone (-Zzstd refused).
- lzma:
  - All 75 lc/lp/pb combinations xz accepts (lc+lp<=4, pb 0..4), dictionaries 4KiB to 64MiB (including 1000000 and 6KiB), -9e, the lzma command, and mode=fast.
  - Non-default lzma inside a tar, tgz, zip, GNU ar, BSD ar and .tar.lzma, each alone, loose and packed; a python zipfile ZIP_LZMA member.
- Deflate64: a deflate-compatible Deflate64 member is read in the work tree and in history.
- Multi-member gzip: the marker in member 2 or 51, zeros between members, BGZF-style FEXTRA blocks, and concatenated .tar.gz files, each under .gz and .bin names, loose and packed. scrub_credentials rewrote all of these, and the read-back then found nothing.
- Multi-stream bzip2 and xz, xz with padding, and multi-block xz.
- A nest of gzip > BSD ar > one-part zip -s > pax tar > lzma (pb=0, lc=0) > a two-member gzip, in the work tree, loose, packed, and in a bundle (eight layers).
- A v3 git bundle.

[] results not counted as findings:
- A v7 tar with a broken first header (documented).
- A multi-volume tar's third volume, which starts partway through a gzip member (accepted).
- Incremental bundles HEAD~1..HEAD, which do not hold the blob.
- Two adjacent tar headers with broken magic, where the second member is lost. GNU tar does not show it either, and the bytes were patched by hand.

## [coverage] should-fix | The last part of a zip64 split archive is never opened, in a work tree or in history, although the README says a split zip's last part is read for the members it holds whole

Status: verified: reproduced=True real=True severity=should-fix

**repro**: Full script: /tmp/claude-0/-home-claude-symphony-template/171b4d76-da53-585e-a4d4-4a4eb26e06e6/scratchpad/wf5-review-coverage/scripts/repro1.sh, run as `repro1.sh <copy of coordbench> <empty workdir> <py312>`. Its core:
```
P=coordbench-planted-stand-in-7f3a9c2e51d0
for i in 1 2 3; do head -c 30000 /dev/urandom > filler$i.bin; done
{ for i in $(seq 300); do echo "line $i of the log"; done; echo "export TOKEN=$P"; for i in $(seq 300); do echo "after $i"; done; } > log.txt
cat log.txt | zip -q -s 64k st.zip filler1.bin filler2.bin filler3.bin -   # stdin makes zip write zip64 records
# result: st.z01 and st.zip; zipinfo -v st.zip puts the '-' member on disk 2, the last part
zip -q -s 0 st.zip --out joined.zip; unzip -p joined.zip - | grep -c $P    # 1
mkdir run; cp st.zip run/
git init -q hist/repo; cp st.z01 st.zip hist/repo/; git -C hist/repo add -A; git -C hist/repo commit -qm parts; git -C hist/repo rm -q st.z01 st.zip; git -C hist/repo commit -qm gone
python3 -I -c 'import sys; sys.path.insert(0,"coordbench"); import run; print(run.unscrubbed(sys.argv[1], [sys.argv[2]]))' run $P
```
`zip -fz -s 64k` over ordinary files gives the same kind of archive.

**observed**: unscrubbed() returns [] for run/ (st.zip alone), for hist/ (both parts committed and then removed, loose objects), for the last part after git gc, in a git bundle, inside a .tgz and inside a BSD ar. packed_kinds(st.zip) returns [] and split_part returns 2. zipfile.is_zipfile is False, and ZipFile raises BadZipFile("zipfiles that span multiple disks are not supported") from its zip64 end-locator check. So ends_as_zip is False and no layer is opened. With both parts in one work tree, st.z01 is refused, so a run directory is safe only when the first part is there too. 0d3279b also returns [] for all of these, so this is a gap in the path this round fixed, not a regression. The same archive without zip64 records (`zip -s 64k` over files, fixtures fx/b1-*) is reported through zip in a work tree, loose, packed and bundled.

**expected**: The member that lies whole in the last part is found, as it is for the non-zip64 last part: "holds the agents' credential, read through zip" in a work tree, and through zlib or git packfile, then zip, in history. At the least, the part should be refused and not passed.

**fix**: In ends_as_zip and zip_members, read a zip64 split part's directory even though zipfile refuses it. One way: when the tail holds a zip64 end locator (PK\x06\x07) whose total-disks field is over 1, hand zipfile a view of the bytes with the locator's disk and total fields, and the zip64 end record's two disk fields, set to 0 and 1. Then keep only the entries whose volume equals the end record's disk, as split_part already does. Add `cat log | zip -s 64k st.zip f1 f2 f3 -` as a ReadingBack fixture, alone and in history.

**verifier's reasoning**: I reproduced this on my own copy (SCRATCHDIR/coordbench at 21f5382) with my own scripts in SCRATCHDIR/scripts and fixtures in SCRATCHDIR/w1.

The fixture is three 30000-byte random filler files plus log.txt, which holds PLANTED on one line among 600 others. I built it as `cat log.txt | zip -q -s 64k st.zip filler1.bin filler2.bin filler3.bin -`. That gives st.z01 (65536 bytes) and st.zip (26558 bytes). zipinfo -v shows the '-' member starting on disk 2, which is the last part. Joining the parts with `zip -s 0` and running `unzip -p joined.zip - | grep -c` gives 1, so the member does hold the marker.

What 21f5382 does with it:
- packed_kinds(st.zip) returns [] and ends_as_zip is False. split_part returns 1: the record's disk number counts from 0, where zipinfo counts from 1; the finding says 2, which does not matter. zipfile.ZipFile raises BadZipFile("zipfiles that span multiple disks are not supported").
- unscrubbed(run with st.zip alone) returns [].
- `zip -fz -s 64k` over the same files as ordinary files (fz.zip) behaves the same: [].
- History, with both parts committed and then removed by `git rm`, returns [] as loose objects and [] after `git gc --prune=now` as a pack.
- With both parts in one work tree, st.z01 is refused as "a split zip's first part", so a run directory is caught when the first part is present too.

Control: the same archive without zip64 records (`zip -s 64k ctl.zip f1 f2 f3 log.txt`) is reported. In a work tree it reads "holds the agents' credential, read through zip"; in history it reads "read through zlib, zip". A one-part zip64 split archive (`cat log | zip -s 64k one.zip -`) is also reported through zip.

At 0d3279b I extracted the coordbench folder with git archive. It also returns [] for run, runfz and hist, so this is not a regression. It is a gap in the very path this round set out to fix.

Judgement: zip -s reading stdin, and -fz, are ordinary modes of an ordinary tool. The README says a split zip's last part is read for the members it holds whole. A zip64 last part is neither read nor refused. In history, removing both parts lets the whole archive through, because the first part in history is an accepted limit and is never refused. A work tree is affected only when the last part is there without the first. That is the same class of file this round fixed as "passed unread in a repository's history", so I agree with should-fix rather than blocker.

I checked that the proposed fix works. In a separate copy (SCRATCHDIR/fixed), I set the zip64 locator's disk to 0 and its total to 1, and zeroed the zip64 end record's two disk fields, before zipfile reads the bytes, in ends_as_zip and in zip_members. With that change, st.zip and fz.zip are reported "read through zip" in a work tree. History is reported "read through zlib, zip" as loose objects and "read through git packfile, zip" after gc. The control is still reported, and ReadingBack passes 26 of 26, the same as the unpatched copy.

**verifier's fix**: Let zipfile read a zip64 split part's directory. Add a helper, one_disk(data). When the tail's zip64 end locator (PK\x06\x07) gives a total of more than one disk, it returns a copy of the bytes with:
- the locator's disk field (offset 4, 4 bytes) set to 0;
- its total-disks field (offset 16, 4 bytes) set to 1;
- the zip64 end record's disk fields (PK\x06\x06, the 56 bytes before the locator, offsets 16 to 24) zeroed.

Use one_disk in ends_as_zip (on the tail) and in zip_members (Reading(one_disk(data))). Keep split_part reading the disk from the classic end record, so only the members on the part's own disk are yielded and the part is then refused as now.

Add fixtures to ReadingBack: `cat log | zip -s 64k st.zip f1 f2 f3 -` with the last part alone in a work tree and both parts committed then removed in history, and `zip -fz -s 64k`. Both should be reported through zip. I prototyped this, and the existing ReadingBack tests still pass.

## [coverage] should-fix | Regression: is_broken_tar turns a prefixed zip (a zipapp) into a 'tar', which stops the zip end-record search, so its members are not read

Status: verified: reproduced=True real=True severity=should-fix

**repro**: Full script: /tmp/claude-0/-home-claude-symphony-template/171b4d76-da53-585e-a4d4-4a4eb26e06e6/scratchpad/wf5-review-coverage/scripts/repro23.py (build "finding2"), run as `py312 -I repro23.py <21f5382 copy> <0d3279b copy from git archive 0d3279b | tar -x> <workdir>`. Its core:
```
import gzip, io, subprocess, sys, tarfile, zipfile
P = "coordbench-planted-stand-in-7f3a9c2e51d0"
log = "".join(f"line {i} of the log\n" for i in range(300)) + f"export TOKEN={P}\n" + "".join(f"after {i}\n" for i in range(300))
open("app/a_secret.log.gz","wb").write(gzip.compress(log.encode(), mtime=0))
with tarfile.open("app/data.tar","w",format=tarfile.GNU_FORMAT) as t:   # an ordinary small tar
    i = tarfile.TarInfo("readme.txt"); b = b"just a readme\n"; i.size = len(b); t.addfile(i, io.BytesIO(b))
for pad in range(2048):
    head = "import sys\n# the installer sets the data files to these modes, in octal:\n#"
    open("app/__main__.py","w").write(head + " "*(84-len(head)) + " 644    for each file, as the tarball says\n" + "#"*pad + "\nprint('hi')\n")
    subprocess.run([sys.executable,"-m","zipapp","app","-o","run/app.pyz","-p","/usr/bin/env python3"], check=True)
    d = open("run/app.pyz","rb").read(); h = zipfile.ZipFile("run/app.pyz").getinfo("data.tar").header_offset
    if (h + 30 + int.from_bytes(d[h+26:h+28],"little") + int.from_bytes(d[h+28:h+30],"little")) % 512 == 0: break
# app.pyz bytes 148..156 are b' 644    ' and data.tar's bytes start at 4096; then commit app.pyz in a repo and git rm it
```

**observed**: `unzip -p run/app.pyz a_secret.log.gz | zcat` shows the marker. With 21f5382, the work tree is refused for the wrong reason: "could not be read (a zip member that does not read (Bad magic number for file header))". The same file committed and removed in a repository gives []. With 0d3279b, both are reported: "holds the agents' credential, read through zip, gzip" and "... read through zlib, zip, gzip". The cause: packed_kinds now returns ["tar"], because is_broken_tar sees a header-shaped checksum field at 148 and a valid ustar header at a later 512-byte boundary. That skips the prefixed-zip search. tar_members then only gives slices that start at block boundaries. The one holding the zip directory opens with the wrong offsets, so a_secret.log.gz, which lies before the tar, is never read.

**expected**: As on 0d3279b: the member is read through the zip's end record and the file is reported as holding the credential, in a work tree and in history. Both conditions are needed (a stored tar on a 512 boundary, and bytes 148..155 reading as an octal number), so this is rare. Ordinary tools wrote every byte, and it is a regression.

**fix**: Do not let a tar found only by is_broken_tar count as a sign that covers all of the bytes. In packed_kinds, look for the weak signs (zlib, lzma, prefixed zip) whenever the only opening sure sign is a tar from is_broken_tar, and append them after "tar". A weak sign never refuses, so the extra search costs one ends_as_zip. Add this zipapp as a fixture.

**verifier's reasoning**: I reproduced this on my own, with my own script, without running the reviewer's: /tmp/claude-0/-home-claude-symphony-template/171b4d76-da53-585e-a4d4-4a4eb26e06e6/scratchpad/wf5-verify-coverage-1/scripts/verify.py, run as `py312 -I verify.py <21f5382 copy> <0d3279b copy> <workdir>`.

How the fixture is built: an app directory holds three files.
- a_secret.log.gz: gzip.compress of a log that contains `TOKEN=` followed by PLANTED.
- data.tar: a GNU-format tar with one readme, written by tarfile.
- __main__.py: its text puts " 644    " at bytes 84..91, which become bytes 148..155 of the .pyz. A run of '#' lines is grown until data.tar's bytes fall on a 512-byte boundary (pad 319, offset 1536).

zipapp.create_archive(app, out, interpreter="/usr/bin/env python3") then writes the file. Ordinary tools wrote every byte, and the file is valid:
- `unzip -p app.pyz a_secret.log.gz | zcat` shows the marker.
- `python3 app.pyz` prints "hi".

The same file was also committed to a git repository and then removed with git rm.

What I observed:
- **21f5382:**
  - packed_kinds(app.pyz) is ['tar']: is_tar is False and is_broken_tar is True.
  - Work tree: unscrubbed gives ['./run/app.pyz: could not be read (a zip member that does not read (Bad magic number for file header))'].
  - History, as a loose object: [].
  - History after `git gc` packed it: still [].
- **0d3279b:**
  - packed_kinds is ['prefixed zip'].
  - Work tree: "holds the agents' credential, read through zip, gzip".
  - Loose object: "... read through zlib, zip, gzip".
  - Pack: "... read through git packfile, zip, gzip".

So the reviewer's claim and cause are confirmed. is_broken_tar sees a checksum-shaped field at 148 and the stored tar's valid ustar header at a later 512-byte boundary, so packed_kinds returns ['tar']. Because "tar" is not in UNOPENED_NAMES, the early return skips ends_as_zip. tar_members then gives only slices that start on block boundaries, and in those the zip's offsets no longer hold.

How bad it is:
- In a work tree the check still fails closed (exit 2), only for the wrong reason.
- In a repository's history (loose or packed) it reports nothing, so a file 0d3279b caught would be published with the marker inside.

It is rare: it needs 8 exact bytes at offset 148 that read as an octal field, plus a stored tar on a 512 boundary, which is about 1 in 512 for a zipapp holding a tar. Nothing was patched by hand, though: the bytes are ordinary source text in a file zipapp wrote. The severity rule counts a regression from 0d3279b on any input as should-fix or worse, so should-fix is right.

Baseline: ReadingBack (26 tests) passes on unpatched 21f5382. No existing test covers this case.

On the proposed fix, I patched a separate copy in two ways:
- **As proposed** (weak signs searched when the only tar comes from is_broken_tar, appended after "tar"): packed_kinds becomes ['tar', 'prefixed zip']. History is reported again (pack: read through git packfile, zip, gzip), and ReadingBack passes. The work tree is still refused for the wrong "Bad magic number" reason, though, because "tar" is tried first and its stepped-over slice of the zip directory raises MembersUnread in strict mode. So it does not fully restore 0d3279b's behaviour, as the report expects.
- **Alternative** (the weak signs looked for and tried before a tar found only by is_broken_tar; a tar from is_tar keeps its place and still ends the search when it is the only sure sign): packed_kinds becomes ['prefixed zip', 'tar']. Both the work tree ("read through zip, gzip") and the pack history are reported as on 0d3279b. ReadingBack passes, and the whole `bash scripts/check.sh` passes (1109 tests, "checks ok").

**verifier's fix**: In packed_kinds, do not let a tar found only by is_broken_tar count as a sure sign that covers every byte. Compute whole_tar = is_tar(data) and broken_tar = not whole_tar and is_broken_tar(data). Make the early return depend only on the other sure signs and on a tar from is_tar. When no sure sign that opens is present, look for the weak signs (zlib, lzma, prefixed zip) and append "tar" for broken_tar after them, so the prefixed zip is tried first. Appending the weak signs after "tar", as the report proposes, restores the history case but leaves the work tree refused for the wrong reason. I verified that the ordering above restores 0d3279b's result in both places and passes check.sh. Add this zipapp, with " 644    " at bytes 148..155 and a stored GNU tar on a 512-byte boundary, as a ReadingBack fixture in the work tree and committed then removed in a repository, packed and loose.

## [coverage] should-fix | Regression: a file with 'ustar' at byte 257 that is not a tar is no longer refused, and its zip end record is never searched, so it passes with the marker inside

Status: not verified (review stopped)

**repro**: Full script: /tmp/claude-0/-home-claude-symphony-template/171b4d76-da53-585e-a4d4-4a4eb26e06e6/scratchpad/wf5-review-coverage/scripts/repro23.py (build "finding3"). Its core:
```
import gzip, subprocess, sys
P = "coordbench-planted-stand-in-7f3a9c2e51d0"
log = "".join(f"line {i} of the log\n" for i in range(300)) + f"export TOKEN={P}\n"
open("app/a_secret.log.gz","wb").write(gzip.compress(log.encode(), mtime=0))
lead = ('"""Pack the run\'s logs into a tarball.\n\nThe archive is written in the POSIX format; tarfile.PAX_FORMAT\n'
        'is what GNU tar calls posix, and the older formats are\n# ')
open("app/__main__.py","w").write(lead + " "*(257-64-len(lead)) + 'ustar and gnu, which we do not use.\n"""\nimport tarfile\nprint(tarfile.PAX_FORMAT)\n')
subprocess.run([sys.executable,"-m","zipapp","app","-o","run/app.pyz","-p","/usr/bin/env python3"], check=True)
# bytes 257..262 of run/app.pyz are b'ustar'; then commit app.pyz in a repo and git rm it
import run; print(run.unscrubbed("run", [P]))
```

**observed**: `unzip -p run/app.pyz a_secret.log.gz | zcat` shows the marker. With 21f5382, unscrubbed() returns [] for the work tree and for the repository it was committed to and removed from. With 0d3279b, both are refused: "could not be read (layers nested deeper than the scrub reads, the last tar)". The cause: is_tar matches on the magic, so packed_kinds returns ["tar"] and skips the prefixed-zip search. tarfile finds no member. stepped_over meets a block 0 that reads as no header and whose checksum field is not a number. what_follows no longer gives back (0, len(data)), the change this round made so the walk cannot recurse to the depth limit. So nothing is opened, and the file passes where it used to be refused.

**expected**: The zip found by its end record is opened and the file reported as holding the credential. At the least it should still be refused, as on 0d3279b. As in finding 2, the byte position must match exactly, so this is rare, but ordinary tools wrote every byte and the verdict changed from refused to published.

**fix**: Use the same fix as finding 2, covering the magic-only case too: when tar_members reads no member from bytes that is_tar or is_broken_tar called a tar, the tar sign should not stop the weak signs. Either append zlib, lzma and prefixed zip after "tar" in packed_kinds whenever block 0 is not a header tarfile reads, or have tar_members raise (refuse) when it gave nothing at all. Add this zipapp as a fixture.

## [coverage] nit | An AIX big archive (llvm-ar --format=bigarchive) is not recognized, so its members are never read

Status: nit, not verified

**repro**: ```
P=coordbench-planted-stand-in-7f3a9c2e51d0
{ for i in $(seq 300); do echo "line $i"; done; echo "export TOKEN=$P"; } | gzip > s.gz
printf odd > odd.txt; printf x > o1
mkdir run; llvm-ar rc --format=bigarchive run/llvm-big.a odd.txt s.gz o1   # starts with <bigaf>\n
llvm-ar p run/llvm-big.a s.gz | zcat | grep -c $P   # 1
python3 -I -c 'import sys; sys.path.insert(0,"coordbench"); import run; print(run.unscrubbed("run", [sys.argv[1]]))' $P
```

**observed**: [] (fixture fx/a1-llvm-big.a). The same members in GNU, BSD and Darwin ar archives from ar and llvm-ar are reported through ar, gzip.

**expected**: Refused as a format the scrub cannot open, or read. It is a mode llvm-ar offers, but an agent's run on a Linux runner is unlikely to write one.

**fix**: Add (b"<bigaf>\n", "AIX big archive") to UNOPENED_FORMATS so the file is refused, or parse its fixed-length member headers.

