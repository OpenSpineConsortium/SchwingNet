"""tools/sealbox.py makes the sealed box GitHub's secrets API takes, in
the standard library alone. The two boxes below were made once with
PyNaCl 1.6.2, libsodium's own binding, for the secret key 0, 1, ... 31:
the first by this module with a fixed ephemeral key, the second by
libsodium, so the tests hold the module to libsodium in both directions
without PyNaCl installed."""

import base64
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import sealbox  # noqa: E402

SECRET = bytes(range(32))
EPHEMERAL = bytes(range(32, 64))
OURS = base64.b64decode("NYBy1jZYgNGu6jKa35EhODhR7SGijjt16WXQ0s0WYlQhqyjzgn18kJKd7dRU6zci9ia97ri1Qhf1PqwDtiFZZk3q9Vkj")
LIBSODIUMS = base64.b64decode("TIVLmmrUYWlh4S1kRJmw/ordKyq4N6dmJFWdoC5uNVwkIHbmYSBI6vxAtRoJGliLazrVQ6DcdXsrvsEsFoc/cFY=")


class SealBoxTest(unittest.TestCase):
    def test_a_box_made_here_matches_libsodiums_byte_for_byte(self):
        made = sealbox.seal(b"symphony test message", sealbox.public_key(SECRET), EPHEMERAL)
        self.assertEqual(made, OURS)

    def test_a_box_libsodium_made_opens(self):
        self.assertEqual(sealbox.open_sealed(LIBSODIUMS, SECRET), b"made by libsodium")

    def test_a_box_with_a_fresh_key_opens_again(self):
        for message in (b"", b"x", b"a longer message " * 9):
            self.assertEqual(sealbox.open_sealed(sealbox.seal(message, sealbox.public_key(SECRET)), SECRET), message)

    def test_a_changed_box_does_not_open(self):
        changed = bytearray(OURS)
        changed[-1] ^= 1
        with self.assertRaises(sealbox.SealError):
            sealbox.open_sealed(bytes(changed), SECRET)

    def test_a_key_must_be_32_bytes_of_base64(self):
        for text in ("not base64!", base64.b64encode(bytes(31)).decode()):
            with self.assertRaises(sealbox.SealError):
                sealbox.key_from_base64(text)
        self.assertEqual(sealbox.key_from_base64(base64.b64encode(SECRET).decode()), SECRET)


if __name__ == "__main__":
    unittest.main()
