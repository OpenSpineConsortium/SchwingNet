import json
P='/tmp/claude-0/-home-user/fc677e8c-eac5-5c7b-b3c7-c77e3a8aea70/scratchpad/refs/'
def ins(uid, find, marker, before=None):
    # insert marker after find (or before the text 'before' within find)
    if before is None:
        return {"unit_id": uid, "find": find, "replace": find + " " + marker}
    i = find.index(before)
    return {"unit_id": uid, "find": find, "replace": find[:i].rstrip() + " " + marker + find[i:]}
edits = [
 ins("mrzzsdjxrm2.10136", "public repositories as of 2026-10-15", "[[s1]]"),
 {"unit_id":"mrzzsdjxrm2.10806","find":"The claim-lock check (research/taxonomy/verify/02) did this","replace":"The claim-lock check [[s2]] did this"},
 ins("mrzzsdjxrm2.10806", "the idle clock is the pusher's", "[[s3]]"),
 ins("mrzzsdjxrm2.11530", "The adversarial search", "[[s4]]"),
 ins("mrzzsdjxrm2.11530", "(a compare-and-swap on a ledger branch)", "[[s5]]"),
 ins("mrzzsdjxrm2.11530", "(first push wins on a shared claims branch)", "[[s6]]"),
 ins("mrzzsdjxrm2.11530", "(a create-only branch push)", "[[s7]]"),
 ins("mrzzsdjxrm2.12465", "states its gap three ways", "[[s8]]"),
 ins("mrzzsdjxrm2.12678", "is still a draft", "[[s9]]"),
 ins("mrzzsdjxrm2.12957", "the github/docs repository's", "[[s10]]"),
 ins("mrzzsdjxrm2.12957", "read from cooperbench/website", "[[s8]]"),
 ins("mrzzsdjxrm2.16404", "(agenticsnz/unsorry)", "[[s11]]", before=")"),
 ins("mrzzsdjxrm2.16404", "the closest rival the search found", "[[s4]]"),
 {"unit_id":"mrzzsdjxrm2.16404","find":"on 2026-10-15 (research/taxonomy/verify/03).","replace":"on 2026-10-15.","removes_only":True},
 ins("mrzzsdjxrm2.16803", "queue-dispatcher.yml", "[[s12]]"),
 ins("mrzzsdjxrm2.16955", "ADR-004", "[[s6]]"),
 ins("mrzzsdjxrm2.17143", "ADR-004 lines 14 and 25", "[[s6]]"),
 ins("mrzzsdjxrm2.17143", "ADR-072", "[[s11]]"),
 ins("mrzzsdjxrm2.17143", "reaper.yml", "[[s13]]"),
 ins("mrzzsdjxrm2.17143", "config.py line 11", "[[s14]]"),
 ins("mrzzsdjxrm2.17348", "swarm/agent.sh", "[[s15]]"),
 ins("mrzzsdjxrm2.17348", ".github/workflows", "[[s11]]"),
 ins("mrzzsdjxrm2.17474", "reaper.yml", "[[s13]]"),
 ins("mrzzsdjxrm2.17570", "ADR-004", "[[s6]]"),
 ins("mrzzsdjxrm2.17706", "swarm/agent.sh line 2685", "[[s15]]"),
 ins("mrzzsdjxrm2.17816", "ADR-004", "[[s6]]"),
 ins("mrzzsdjxrm2.17845", "not a ref per item", "[[s4]]"),
 ins("mrzzsdjxrm2.17924", "the work is not kept", "[[s4]]"),
 ins("mrzzsdjxrm2.18030", "Yes", "[[s4]]"),
 ins("mrzzsdjxrm2.18080", "no subscription token there", "[[s4]]"),
 ins("mrzzsdjxrm2.18197", "No", "[[s4]]"),
]
U='https://github.com/'
def rf(key, authors, path, repo, date, sha, read, supports, public_url=""):
    return {"key":key,"kind":"repository-file","authors":authors,"title":path,"container":repo,"date":date,"version":sha,
            "url":f"{U}{repo}/blob/{sha}/{path}","public_url":public_url,"read":read,"path":"","supports":supports}
sources = [
 rf("s1",["GitHub"],"data/reusables/actions/supported-github-runners.md","github/docs","2026-10-15","12691d2","opened",
    "standard GitHub-hosted runners free and unlimited on public repositories"),
 {"key":"s2","kind":"project-record","authors":[],"title":"Verify 02: the claim lock, idleness and re-claims after a merge","container":"",
  "date":"2026-10-15","version":"","url":"","public_url":"","read":"record","path":"/mnt/project-files/research/taxonomy/verify/02-claim-lock.md",
  "supports":"claim-lock experiments: server enforces only creation, guard reads the session's directory, pusher's clock"},
 rf("s3",["OpenSpineConsortium"],"validation/DESIGN.md","OpenSpineConsortium/symphony-protocol","","a3a5b4d","opened",
    "finding F8: idleness measured by the pusher's committer date"),
 {"key":"s4","kind":"project-record","authors":[],"title":"03 Uniqueness: is Symphony the only system that combines (a) to (e)?","container":"",
  "date":"2026-10-15","version":"","url":"","public_url":"","read":"record","path":"/mnt/project-files/research/taxonomy/verify/03-uniqueness.md",
  "supports":"adversarial search for atomic claims; unsorry as closest rival and its scores on (a) to (e)"},
 rf("s5",["GitHub"],"docs/src/content/docs/reference/work-queue.md","github/gh-aw","2026-10-15","dc91dbed","opened",
    "gh-aw work queue claims published by compare-and-swap on a ledger branch"),
 rf("s6",["agenticsnz"],"docs/adrs/ADR-004-Claims-Branch-First-Push-Wins.md","agenticsnz/unsorry","","029d328b","opened",
    "unsorry's first-push-wins claim files on a shared claims branch"),
 rf("s7",["marcelusfernandes"],"scripts/claim.mts","marcelusfernandes/agentic-setup","","4907361","opened",
    "agentic-setup's create-only branch push as a lock"),
 rf("s8",[],"public/static/pdfs/main.pdf","cooperbench/website","2026-03-25","97dbb0a","opened",
    "CooperBench paper: the coordination gap stated three ways", public_url="https://arxiv.org/abs/2601.13295"),
 rf("s9",["GitHub"],"docs/adr/64955-git-backed-work-queue-coordination.md","github/gh-aw","2026-10-15","dc91dbed","opened",
    "gh-aw's work-queue ADR has status Draft"),
 {"key":"s10","kind":"repository","authors":["GitHub"],"title":"github/docs","container":"github/docs","date":"2026-10-15","version":"12691d2",
  "url":"https://github.com/github/docs","public_url":"","read":"opened","path":"","supports":"GitHub's documentation read from its content files"},
 {"key":"s11","kind":"repository","authors":["agenticsnz"],"title":"unsorry","container":"agenticsnz/unsorry","date":"","version":"029d328b",
  "url":"https://github.com/agenticsnz/unsorry","public_url":"","read":"opened","path":"","supports":"unsorry, a Lean proof swarm; ADR-072 and its workflows"},
 rf("s12",["agenticsnz"],".github/workflows/queue-dispatcher.yml","agenticsnz/unsorry","","029d328b","opened","unsorry's dispatcher in Actions"),
 rf("s13",["agenticsnz"],".github/workflows/reaper.yml","agenticsnz/unsorry","","029d328b","opened","unsorry's reaper, every 15 minutes in Actions"),
 rf("s14",["agenticsnz"],"tools/gate_b/config.py","agenticsnz/unsorry","","029d328b","opened","unsorry's claim TTL of two hours"),
 rf("s15",["agenticsnz"],"swarm/agent.sh","agenticsnz/unsorry","","029d328b","opened","unsorry's agents on volunteers' machines, each paying for inference"),
]
res={"edits":edits,"sources":sources,"uncited":[],"checker_problems":0,
     "changes":["Replaced the mentions of research/taxonomy/verify/02 and verify/03 with markers (the verify records themselves where the claim is their own experiment or synthesis, plus primary files)",
                "Cited unsorry's worksheet source cells to the files at 029d328b, gh-aw's queue and ADR at dc91dbed, agentic-setup at 4907361, the CooperBench PDF at cooperbench/website 97dbb0a and github/docs at 12691d2"]}
json.dump(res,open(P+'out/man-B-cite.json','w'),indent=1)
