"""The first review's getpass probe: what Python's hidden prompt does in a
given terminal window (it was asked about Git Bash's own window, mintty).
Run it by hand in the window in question and type anything; it prints only
the length of what was typed, never the text."""
import getpass, sys
v = getpass.getpass("Paste (nothing is shown): ")
print("got", len(v), "chars")
