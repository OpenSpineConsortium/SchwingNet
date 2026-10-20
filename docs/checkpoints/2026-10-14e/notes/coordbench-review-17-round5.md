# coordbench#17, round five: the fixes to round four's findings and their reviews (2026-10-15)

The fifth commit of coordbench#17 answers round four's review
(coordbench-review-17-round4.md): the verified blocker, the three
verified should-fix findings, the unverified one and the two nits. It
was reviewed in three rounds before it was pushed: round one on the
fixes (three lenses: regression and cost, coverage, claims and tests),
round two on round one's answers (two lenses), round three on round
two's answers (one lens). Every finding below was reproduced by its
reviewer in its own copy; "old" is 21f5382. The marker in every
fixture is coordbench's stand-in PLANTED, planted in ordinary files
only. The reviewers' scripts were in the session's scratch directory
and are gone; the fixtures that mattered are tests now.

## What the commit does

- A zip -s first part that ends with a stored zip is a first part
  (refused in a work tree): bytes that start as one are a whole zip only
  when the file's own end record ends the file, says disk 0 and names a
  directory whose first entry places a local header at 4 (is_one_part).
- A tar cut short inside a later header is no header (checksum_holds
  wants 512 bytes), and the scrub's pass says and skips whatever a
  file's bytes make it raise, as the read-back refuses such a file.
- A zip64 split part's directory is read: zip_reader gives zipfile the
  bytes with the zip64 locator's two disk fields read as one disk,
  through an overlay in Reading (no copy), only for the locator zipfile
  itself reads (the 20 bytes before the end record); split_part reads
  the part's disk from the zip64 record where the classic record leaves
  it there; ends_as_zip hands zipfile the whole file when the tail holds
  a zip64 locator, since the locator's offsets hold only against the
  whole, and the tail as before otherwise.
- A tar is a sure sign only by a first header whose checksum holds. One
  found by ustar's magic alone or by a later header past a first that
  does not read is the weak kind BROKEN_TAR: looked for only where no
  sure sign is found, tried last, left out where a zip found by its end
  record has its first local header in the first block (a zipapp), left
  whole by the scrub's pass once it opens to a layer (CONTAINERS,
  holds_members), and never refusing a file it does not open.
- What follows a first block that reads as no header is opened from the
  next block, unless the next block carries ustar's magic with no
  checksum that holds, which the walk steps over itself.
- An AIX big archive is refused as a format the scrub cannot open.

## Round one (on the fixes)

Regression and cost: a sweep of 34,673 files under /usr/share and
/usr/lib and a corpus of 235 fixtures in both planted and clean forms
showed only the intended changes. Two should-fix findings: (1) the
first zip64 fix copied the whole file and patched the last PK\x06\x07
in the tail wherever it stood, so a stored member holding that
signature (libzip.so, zipimport's .pyc) lost its CRC and a clean
one-disk zip was refused; (2) the start + 512 opening recursed on
512-byte-periodic text with "ustar" at column 257, refusing it and any
repository holding it at the depth limit, where old passed it. One
nit: a split's last part whose members all lie in the other parts
passes clean, classic and zip64 alike (documented: a last part that
holds only the directory is searched as it is; not changed).

Coverage: every one of the six fixes held against variants from
Info-ZIP, GNU tar, zipapp, llvm-ar and git, in a work tree and in
history. One nit: a zip64 split part whose classic record's disk
field is 0xFFFF (65,535 or more parts) passed clean; split_part now
reads the zip64 record's disk.

Claims and tests: 38 mutants, 31 caught at first. Two should-fix
findings: (1) ends_as_zip gave zipfile only the tail, and zipfile
refuses a zip64 locator whose record offset lies beyond the buffer, so
a zip64 split part or a prefixed zip64 archive over 64 KiB was never a
zip (zip -s 1m -fz is an ordinary choice); (2) a clean zipapp of round
four's octal shape, and a clean plain zip of that shape, were refused
where 0d3279b passed them, since the weak tar was tried after the zip
and its steps over, slices of the zip, read as layers that do not
open. Nits: is_one_part's zip64 branch, the first entry's offset and
the budget charges were pinned by no test; wording.

## Round two (on round one's answers)

Regression and coverage: the Reading overlay read right at every
chunk size and offset (and the sweep was unchanged). Two should-fix
findings in the answers: (1) the rule that skipped the weak tar once
any kind before it opened also fired on a zlib-looking first member
name ("x^notes.txt": zlib_content yields an empty layer) and on a zip
stored as a member of the tar, so a GNU tar with one damaged header
byte passed with the marker in its gzip member, and the whole pass
exited 0; (2) BROKEN_TAR was not a container, so the scrub's pass
rewrote a broken tar as text, which moved every later header off its
block, and the read-back then missed the gzip member that still held
the marker: exit 0 with the marker published. Two nits: a tail kept
back when its first block's checksum held by chance, losing the stream
behind it; a text whose first line has ustar at column 257 now charges
its whole tail to the budget (43 such 24 MB logs refuse a directory).
A cost nit: ends_as_zip through Reading cost about 3x per call.

Claims and tests: the same two should-fix findings, found
independently, and a third: the tail test (is_tar or is_broken_tar on
the tail) dropped the member behind a header tarfile refuses for its
size. 37 mutants, 23 caught, the rest equivalent or now pinned.

The answers: BROKEN_TAR is left out of packed_kinds only where a
prefixed zip has its first local header in the first block (a zipapp),
and the credential_layers skip rule is gone; BROKEN_TAR is in
CONTAINERS and holds_members leaves it whole once tar_members opens to
a layer; the tail is kept back only when its first block carries
ustar's magic with no checksum that holds; ends_as_zip hands zipfile
the tail copy unless a zip64 locator stands before the end record.

## Round three (on round two's answers)

Twenty mutants, 13 killed, 3 equivalent. Three findings: (1) a damaged
GNU tar whose first member's name, or link target, starts with the
bytes PK\x03\x04 and which holds a zip among its members was taken for
that zip (a sure zip by its first bytes, or a prefixed zip with the
signature in the first block), so the gzip member behind it passed with
the marker and the whole pass exited 0 where old caught it; a chosen
name, so should-fix by realism; (2) two consecutive headers whose sizes
do not read before a stream with no header: the tail skip kept the
second block back and the walk stepped over it blind, so the stream
was never opened where old opened it; (3) a damaged tar cut short
inside a member behind an empty first member passed as a weak sign
that never opened, where old refused it (no leak, since the cut bytes
are searched, but the fail-closed rule slipped). Nits: a clean zipapp
whose interpreter line is longer than a block was still refused (as
old did); two mutants unpinned (the first block's bound, the
"prefixed zip" conjunct).

The answers: the broken tar is left out only where the zip covers the
bytes it was found in, placed as zipfile places it (zip_extent,
zip_covers_tar): the zip starts in the first block, or the later header
the tar was found by lies within the zip; a file that starts as a zip
whose end record places the zip later gets the broken tar read after
the zip. What follows the first block is opened once from the first
block the walk neither reads as a header nor steps over as GNU tar does
(past_unread_blocks), which also finds a stream after text of
magic-only blocks and makes the walk's own coverage the rule. A member
that stopped short with bytes counts as opened, so the file is refused.
The long-interpreter zipapp passes clean and is found planted.

## Round four (on round three's answers)

Started at about 02:55 UTC on 2026-10-15 and still running when the
owner's credits ran low and the work was pushed (coordbench#17 head
e3dc418). Its report was not received; the next thread runs this
round again on e3dc418 before #17 is marked ready.

## What stays as a documented limit

- A stream after text whose first block reads as a broken tar header
  is outside the read-back, as a stream after any text is.
- A split's last part whose members all lie in the other parts passes
  as a part that holds only the directory does.
- A clean zipapp whose interpreter line is longer than a block, or a
  broken tar with a zip among its members and a zip64 locator by
  chance, falls back to the fail-closed reading.
