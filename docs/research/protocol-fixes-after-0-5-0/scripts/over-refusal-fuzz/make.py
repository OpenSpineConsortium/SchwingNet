"""Session-style commands, seeded: python3.12 -I make.py <seed> <n> <out.json> <text roots...>."""
import json, os, random, sys
seed, n, out, roots = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4:]
rng = random.Random(seed)
texts = []
for root in roots:
    for d, _, files in os.walk(root):
        if "/.git" in d: continue
        for f in files:
            if f.endswith(".md"):
                try: t = open(os.path.join(d, f), encoding="utf-8").read()
                except Exception: continue
                texts += [p for p in t.split("\n\n") if p.strip() and len(p) < 1500]
words = ["fix", "the guard", "claim", "board", "push", "main", "it's", "don't", "$HOME", "`x`",
         "$(date)", "a \"quote\"", "50%", "a;b", "a|b", "a&&b", "#7", "--force", "git push origin main"]
def phrase():
    return " ".join(rng.choice(words) for _ in range(rng.randint(1, 6)))
def text():
    return rng.choice(texts) if rng.random() < 0.7 else phrase()
B = lambda: rng.choice(["claude/7", "claude/12", "\"$(git branch --show-current)\"", "HEAD", "-u origin claude/7"])
def push():
    return rng.choice([
        "git push -u origin claude/7", "git push origin claude/7",
        "git push -u origin \"$(git branch --show-current)\"",
        "git push --force-with-lease=claude/7:$(git rev-parse origin/claude/7) origin claude/7",
        "git -C /home/claude/symphony-protocol push -u origin claude/7",
        "git push origin HEAD:claude/7"])
forms = [
    lambda t: "git commit -m \"$(cat <<'EOF'\n" + t + "\nEOF\n)\" && " + push(),
    lambda t: "gh pr create --draft --title T --body \"$(cat <<'EOF'\n" + t + "\nEOF\n)\"",
    lambda t: "git commit -m \"$(printf '%s\\n' '" + t.replace("'", "'\\''") + "')\" && " + push(),
    lambda t: "echo $'" + t.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'",
    lambda t: "git commit -m $'" + t.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "' && " + push(),
    lambda t: "cat > notes.md <<'EOF'\n" + t + "\nEOF",
    lambda t: "git -C /home/claude/x add -A && git -C /home/claude/x commit -q -m \"" + t.replace("\\", "\\\\").replace("\"", "\\\"").replace("$", "\\$").replace("`", "\\`") + "\" && " + push(),
    lambda t: "gh api -X PATCH repos/o/r/pulls/7 -f body=\"$(cat body.md)\" && " + push(),
    lambda t: "for f in $(git diff --name-only origin/main...HEAD); do echo \"$f\"; done; " + push(),
    lambda t: "B=$(git rev-parse --abbrev-ref HEAD); git push -u origin \"$B\"",
]
cmds = []
while len(cmds) < n:
    t = text()
    if "\nEOF\n" in "\n" + t + "\n": continue
    c = rng.choice(forms)(t)
    if len(c) <= 20000: cmds.append(c)
json.dump(cmds, open(out, "w"))
