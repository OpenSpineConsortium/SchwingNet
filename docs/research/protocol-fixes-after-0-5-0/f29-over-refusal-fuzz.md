# F29's over-refusal fuzz, and the guard misses the brief named

Source: the thread "Protocol fixes toward 0.5.1", 2026-10-18, run after symphony-protocol#53 (F29) merged at f6ac177. Its pull request's description had a placeholder line where this result was to go; the line now carries it.

## The fuzz

scripts/over-refusal-fuzz/make.py writes session-style commands from a seed: commit messages and pull request bodies by here-document, printf and `$'...'` messages, `git -C` commits, leases with `$(git rev-parse ...)`, `$(git branch --show-current)` targets, loops over `$(git diff ...)`, and `cat > notes.md <<'EOF'` notes. Their text is drawn from the paragraphs of every Markdown file in symphony-template and symphony-protocol, or from a short list of phrases that hold quotes, expansions and `git push origin main`. scripts/over-refusal-fuzz/judge.py judges each command with one checkout's guard.refused_push, the current branch claude/7 and the default branch main. It spends nothing: it runs on the container's processors and calls no service.

    python3.12 -I make.py <seed> 20000 cmds.json <template checkout> <library checkout>
    python3.12 -I judge.py <library checkout at a4ff6c3> cmds.json old.json
    python3.12 -I judge.py <library checkout at main> cmds.json new.json

Seeds 1 and 2, 40,000 commands: a4ff6c3 (main before F29) refuses 75, main at f6ac177 refuses 80. F29 refuses none fewer and 5 more. Each of the 5 is a quoted `cat > notes.md <<'EOF'` body with a line that starts with an expansion before a literal push of main, as `$HOME git push origin main`, the over-refusal F29's "What it leaves" already names; the other 75 are the same bodies with the push at the line's start, which a4ff6c3 refused too. Neither refuses a commit message, a pull request body, a printf message or a `$'...'` command.

## The misses the brief named

The 2026-10-18 handoff listed three push guard misses for their own pull requests: `git push origin $'main'`, `git pu$(true)sh origin main`, and here-documents. On main at f6ac177 each is refused, by guard.refused_push and by the hook's run(): F29 decodes `$'...'` and reads a substitution inside a word as a hole, and F24, F25 and F29 read here-documents, so `bash <<'EOF'`, `sh <<EOF`, `cat <<'EOF' | bash` and `bash -s <<'EOF'` with a push in the body are refused. No pull request is owed for them.

## What still passes: text handed to another shell

These pass on main, by guard.refused_push and run() alike:

- `bash -c 'git push origin main'`, `eval 'git push origin main'`
- `bash <<<'git push origin main'`, `sh <<< "git push origin main"`
- `echo 'git push origin main' | bash`, `printf 'git push origin main' | sh`
- `eval "$(cat <<'EOF'` ... `EOF` `)"` with the push in the body
- `echo main | xargs -I{} git push origin {}`

The module's docstring names this class as known: what a command hands to another shell as text, as bash -c and eval do, is one word and passes, as do sudo and xargs, the remote's rules standing behind it. The here-document forms are refused only because the whole reading reads every body as commands, so the guard refuses a push handed to a shell by here-document and passes the same text handed by a here-string, a pipe or -c. Reading a shell's -c string, eval's words and a here-string or piped text fed to a shell as commands would close it, as F28 reads env -S's string. The owner chose to take it on (2026-10-18), and F32, symphony-protocol#54, merged that day, does so.
