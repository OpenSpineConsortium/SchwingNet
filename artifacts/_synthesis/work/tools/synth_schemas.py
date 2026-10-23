"""The JSON schemas the workflow's Claude sessions answer in, one per stage: read (an artifact's
record and its finder's candidates), skeptic, recheck and judge. Each is passed to the session
whole as --json-schema inside claude_args, which the action parses as a shell would, so no
schema may hold a single quote, a backslash or a dollar sign; synth_actions.py claude_args
refuses one that does. The records' fields are the ones the first reading of 2026-10-22 wrote
(synth_reads.RECORD_KEYS), with the words it used for kinds of claim, relation and
confidentiality. The limits on how many candidates a finder gives are in its brief and in the
join, not here, so a finder that gives one too many loses that one and not its answer."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import synth_reads as sr  # noqa: E402

TEXT = {"type": "string"}
MAYBE = {"type": ["string", "null"]}
WORDS = {"type": "array", "items": TEXT}
GRADES = ("measured", "reported", "inferred", "unverified")
RELATIONS = ("same-topic", "builds-on", "contradicts", "supersedes", "superseded-by")
CONFIDENTIALITY = ("schwingnet-method", "schwingnet-other", "symphony-beethoven", "personal-outreach", "mixed")
VERDICTS = tuple(dict.fromkeys(sr.CLUSTER_SCALE + sr.NUMBER_SCALE))


def obj(fields):
    """An object whose every field is required. A field the session adds is let through and
    never read, so an answer is not refused for one."""
    return {"type": "object", "properties": fields, "required": list(fields)}


def listed(fields):
    return {"type": "array", "items": obj(fields)}


def one_of(words):
    return {"type": "string", "enum": list(words)}


RECORD = obj({
    "kind": TEXT, "genre": TEXT, "date": TEXT, "date_evidence": TEXT, "question": TEXT, "summary": TEXT,
    "key_claims": listed({"claim": TEXT, "evidence_in_artifact": TEXT, "grade_hint": one_of(GRADES)}),
    "numbers": listed({"value": TEXT, "unit": TEXT, "n": MAYBE, "interval": MAYBE, "context": TEXT, "quote": TEXT}),
    "datasets": WORDS, "tools": WORDS, "models": WORDS,
    "decisions": listed({"date": MAYBE, "decision": TEXT, "owner": MAYBE, "reason": MAYBE}),
    "open_questions": WORDS, "unsourced_assertions": WORDS, "stale_markers": WORDS,
    "external_sources": listed({"title": TEXT, "url_or_citation": TEXT}),
    "cross_references": WORDS, "confidentiality": one_of(CONFIDENTIALITY),
    "related_titles": listed({"title": TEXT, "relation": one_of(RELATIONS), "why": TEXT}),
    "people_by_role": WORDS, "coverage_notes": TEXT, "notes": TEXT,
})
assert set(RECORD["properties"]) == set(sr.RECORD_KEYS), "the record schema and RECORD_KEYS differ"

CLUSTER_CANDIDATE = {"kind": one_of(sr.CLUSTER_KINDS), "topic": TEXT, "artifact_a": TEXT, "statement_a": TEXT, "quote_a": TEXT,
                     "artifact_b": TEXT, "statement_b": TEXT, "quote_b": TEXT, "why_it_matters": TEXT}


def number_candidate(kinds):
    return {"quantity": TEXT, "artifact_a": TEXT, "value_a": TEXT, "quote_a": TEXT, "artifact_b": TEXT, "value_b": TEXT,
            "quote_b": TEXT, "kind": one_of(kinds), "why": TEXT}


READ = obj({
    "record": RECORD, "changed": MAYBE, "cluster": MAYBE, "cluster_why": TEXT,
    "cluster_candidates": listed(CLUSTER_CANDIDATE),
    "number_candidates": listed(number_candidate(sr.TO_SKEPTICS)),
    "number_other": listed(number_candidate([k for k in sr.NUMBER_KINDS if k not in sr.TO_SKEPTICS])),
})

READING = {"quote_a": TEXT, "quote_b": TEXT, "explanation": TEXT, "resolution_hint": TEXT}
SKEPTIC = obj({"items": listed({"key": TEXT, "verdict": one_of(VERDICTS), **READING})})
RECHECK = obj({"items": listed({"key": TEXT, "holds": {"type": "boolean"}, "verdict": one_of(VERDICTS),
                                "hint_ok": {"type": "boolean"}, **READING})})
JUDGE = obj({"rulings": listed({"key": TEXT, "verdict": one_of(VERDICTS),
                                "sided_with": one_of(("skeptic", "re-checker", "neither")), **READING})})

SCHEMAS = {"read": READ, "skeptic": SKEPTIC, "recheck": RECHECK, "judge": JUDGE}
