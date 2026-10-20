# coordbench#17, round six: round four's review run again on e3dc418 (2026-10-15)

The 2026-10-15 handoff asked for round four's review to run again on
e3dc418, since the fourth round of round five's reviews ended on a
usage limit: break zip_covers_tar and zip_extent, past_unread_blocks,
and the stopped-short rule in layers_through, with mutants of those
lines, and fix what it finds, each with a test. It ran as seven finder
lenses on the diff from 21f5382 (old) through 0d3279b (base) to
e3dc418 (new): zip-covers, tar-walk, stopped-short, mutants of the
zip lines, claims against tests, regression and cost, and the
scrub's pass; then one verifier per finding that was not a nit, each
reproducing it in its own copy from the description before reading
the finder's scripts. The marker in every fixture is coordbench's
stand-in PLANTED, planted in ordinary files only. The fixtures that
mattered are tests now, in one new test and pins beside the old ones.

## What the sixth commit does

- zip_extent reads an end record as a zip's only when the directory
  stands where it says (its first entry's signature at the record's
  place less its size), the zip starts at or after the file's start,
  and the record's comment ends the file. A record's signature inside
  a member's bytes (a library that reads zips, a note on them), or a
  zip stored in a tar, whose record the tar's padding follows, marks
  no zip of the whole; zipfile reads such a record as a zip's, and the
  tar it stands in was covered by it, so a damaged tar's later members
  passed unread. Now the tar is read.
- packed_kinds looks for a later header only when the first does not
  read (a sure tar never needed it).
- The walk's first gap, where a block reads as no header, opens what
  follows from past the headers it reads or steps over, and the block
  it lands on opens the next block too when it is shaped like a
  header, as a gap's block always did: a stream behind a block whose
  checksum field is a number, after headers tarfile refuses, was
  searched as text.
- past_member: a header whose checksum does not hold, which GNU tar
  skips a block at a time, gives its member by its size, and the walk
  goes on from the first header inside that member whose checksum
  holds, which GNU tar reads, where it went past the member and lost a
  header tarfile refuses and GNU tar reads (an mtime, uid or devmajor
  that is no number, with a checksum that holds).
- tar_members steps over what follows on whatever tarfile raised, a
  pax record it cannot read (a sparse map that is no numbers) among
  them, not only on its ReadError, so a weak tar that raised with
  nothing opened is no longer passed unread; a limit met inside it is
  re-raised as the limit.
- A container's member that stopped short counts as opened with bytes
  or with none, since its header read: a damaged tar cut at the end of
  a member's header passed where old refused it. gives_anything counts
  it the same at the depth's end.
- The docstrings of holds_members, zip_covers_tar and packed_kinds say
  these; the README's list of what the walk reads says past_member's
  rule and the record's.

## The findings

Severity is the verifier's. "Leaks" means the marker passed the
read-back on new; every leak below is found on the sixth commit, and
every fixture is refused or found as GNU tar or old reads it.

1. zip_extent takes any PK\x05\x06 (should-fix, verified). A member of
   a damaged tar holding the signature followed by its own bytes gave an
   extent that started before the file or inside the member, which
   covered the tar; the tar's later member passed. Three shapes in the
   test: an ELF-like member, a note quoting the record, and a note whose
   counts place the directory before the file. Fixed in zip_extent.
2. A stored zip first in a damaged tar with an aligned inner tar
   (should-fix, verified). The zip's record, followed by the tar's
   padding and end, gave an extent in which the tar's later header lay
   (the inner tar's, on a block boundary), so the zip covered the tar
   and the gzip member after the zip passed. Now the record is no zip's
   and the tar is read; what the tar's reader stepped over to the
   header inside the zip is a slice that starts as a zip and opens as
   none, so the file is refused, as old refused it, and in a
   repository's history the member after the zip is found.
3. The shaped rule dropped at the landing block in the whole-file range
   (should-fix, verified). Fixed in what_follows.
4. A magic-only header's size skips a header GNU tar reads (nit by the
   verifier: old and base leak the same, no tool writes the shape, the
   fix is cheap). Fixed in past_member, in stepped_over and
   past_unread_blocks alike. The cost is one checksum sum per header
   read by its magic: 2.85 s to 4.43 s on a 50 MB tar of such headers
   in the verifier's timing.
5. tar_members catches only ReadError (should-fix, verified): GNU tar's
   own posix sparse tar with three damaged bytes, or a hand-built pax
   record, raised ValueError, which left a weak tar's rest unread.
   Fixed in tar_members, with LimitReached re-raised first, as the
   verifier asked, so a budget met inside a tar stays the limit.
6. A member cut to zero bytes passes (should-fix, verified): a damaged
   tar cut at a member's header's end, by head -c or dd, was published
   where old refused it. Fixed in layers_through (scoped to a
   container's StoppedShort, since the unscoped rule refuses the lzma
   look-alike that must fall through to zip) and in gives_anything.

Nits taken: the zip64 extent, the end record being the last in the
tail, the zero blocks before a damaged tar and an lzma stream cut
short at the depth's end are pinned; holds_members's docstring says
what a log whose first line puts ustar's magic at 257 does. Nits left:
header_size summing a holding header's checksum once more in
past_member (the cost above).

The last two verifiers, of the mutants lens and the claims lens, met
findings 2 and 5 again from their own fixtures (Info-ZIP's zip -0, a
zipapp and zipfile for the stored zip; GNU tar's own posix sparse
output with reproducible-build flags for the pax record) and graded
both should-fix; the mutants verifier also asked that the README name
where a zip's later header leaves the weak tar out, which the second
commit of the round, ae708f5, does.

## What was measured

- The 1898-file regression corpus (every round's fixtures and the
  planted and clean twins): no verdict differs between e3dc418 and the
  fix; one file slower by 3x and over 50 ms (git-tarball-loose, 17 ms
  to 60 ms).
- 35352 files under /usr/share, /usr/lib and /usr/bin: no verdict
  differs; one slower (a jmod, 18 ms to 57 ms).
- Each new assertion fails on e3dc418's run.py in a copy with the new
  tests: the stray records, the stored zip, the landing block, the
  covering header, the sparse records and the cut member, and the deep
  cut member through gives_anything.

## What stays as a documented limit

The limits in bench/cooperbench/README.md stand. A zip stored in a
damaged tar with a tar of its own on a block boundary is refused, not
read, since the slice the tar's reader stepped over starts as a zip:
fail closed, as before this pull request. So is a clean prefixed zip
with a tar appended after it, whose record no longer ends the file
(a zip member that does not read), as old and base refused it; no tool
writes either shape. A v7 outer tar, which has no magic to find its
later header by, stays the documented limit.
