from app.tools import working_days
from app.retrieval import eligible, resolve_precedence

def test_working_days_weekends_and_holiday():
    assert working_days("2026-01-02","2026-01-06",{"2026-01-05"}) == 2

def test_region_and_access_filters():
    emp={"role":"employee","region":"IN"}
    base={"access_level":"all","regions":["GLOBAL"],"effective_date":"2025-01-01"}
    assert eligible(base,emp,"2026-10-29")
    assert not eligible({**base,"regions":["US"]},emp,"2026-10-29")
    assert not eligible({**base,"access_level":"hr"},emp,"2026-10-29")

def test_precedence_authority_before_recency():
    emp={"role":"employee","region":"IN"}
    old={"doc_type":"policy","regions":["GLOBAL"],"effective_date":"2025-01-01"}
    newer_faq={"doc_type":"faq","regions":["GLOBAL"],"effective_date":"2026-05-01"}
    assert resolve_precedence([old,newer_faq],emp)==[old]

def test_regional_scope_wins():
    emp={"role":"employee","region":"IN"}
    global_doc={"doc_type":"policy","regions":["GLOBAL"],"effective_date":"2026-01-01"}
    regional={"doc_type":"policy","regions":["IN"],"effective_date":"2025-01-01"}
    assert resolve_precedence([global_doc,regional],emp)==[regional]
