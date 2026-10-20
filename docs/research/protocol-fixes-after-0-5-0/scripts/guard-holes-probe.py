import sys
sys.path.insert(0, sys.argv[1])
from sdlc_protocol import guard
here = sys.argv[2]
q = "'"
cases = {
    "plain": "git push --force origin main",
    "after heredoc with apostrophe": "cat <<" + q + "EOF" + q + " > /dev/null\nIt" + q + "s done\nEOF\ngit push --force origin main",
    "after heredoc, no apostrophe": "cat <<" + q + "EOF" + q + " > /dev/null\nIt is done\nEOF\ngit push --force origin main",
    "proc subst": "cat <(git push --force origin main)",
    "dq cmd subst": 'out="$(git push --force origin main 2>&1)"',
    "env abbrev": "env --uns HOME git push --force origin main",
}
for name, cmd in cases.items():
    r = guard.refused_push(cmd, here)
    print("%-32s -> %s" % (name, "REFUSED" if r else "passed"))
