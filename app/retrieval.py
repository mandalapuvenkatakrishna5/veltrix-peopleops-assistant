import re
from datetime import date
from collections import defaultdict
from .config import APP_TODAY

AUTHORITY = {"policy": 6, "addendum": 6, "memo": 5, "handbook": 4, "calendar": 4, "faq": 2, "wiki": 1}

def can_read_doc(doc, employee):
    access=doc.get("access_level","all")
    return (access=="all" or (access=="managers" and employee["role"] in ("manager","hr"))
            or (access=="hr" and employee["role"]=="hr"))

def eligible(doc, employee, ref_date):
    return (can_read_doc(doc, employee)
            and ("GLOBAL" in doc["regions"] or employee["region"] in doc["regions"])
            and doc["effective_date"] <= ref_date)

def rank_doc(doc, employee):
    regional = 1 if employee["region"] in doc["regions"] and "GLOBAL" not in doc["regions"] else 0
    return (AUTHORITY.get(doc["doc_type"],0), regional, doc["effective_date"])

def tokenize(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))

def retrieve(query, docs, employee, ref_date=None, limit=8):
    ref_date=ref_date or APP_TODAY
    eligible_docs=[d for d in docs if eligible(d, employee, ref_date)]
    q=tokenize(query)
    scored=[]
    for d in eligible_docs:
        words=tokenize(d["text"])
        if not words: continue
        overlap=len(q & words)
        score=overlap/(len(q)**0.5 * len(words)**0.35)
        # exact key phrase relevance boost
        if any(k in d["text"].lower() for k in query.lower().split() if len(k)>4): score += .03
        if score>0: scored.append((score,d))
    scored.sort(key=lambda x:x[0], reverse=True)
    # Deduplicate near-identical chunks from the same document, retain metadata for precedence handling.
    out=[]
    for score,d in scored:
        if not any(x["doc_id"]==d["doc_id"] and x["locator"]==d["locator"] for x in out):
            out.append(d)
        if len(out)>=limit: break
    return out

def resolve_precedence(docs, employee):
    # Exposed helper for deterministic policy tests: authority, scope, then recency.
    if not docs: return []
    best=max(rank_doc(d, employee) for d in docs)
    return [d for d in docs if rank_doc(d, employee)==best]
