import sys
sys.path.insert(0, sys.argv[1])
from sdlc_protocol import guard
q = "'"
two_bodies = ("git commit -F - <<" + q + "EOF" + q + "\nDon" + q + "t stop\nEOF\n"
              "git push --force origin main\n"
              "cat <<" + q + "EOF" + q + "\nIt" + q + "s done\nEOF")
print("two bodies around a push ->", "REFUSED" if guard.refused_push(two_bodies, sys.argv[2]) else "passed")
