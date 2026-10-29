import logging, os, re
from contextlib import asynccontextmanager
from datetime import date
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .config import DB_PATH
from .db import employee
from .ingest import ingest
from .orchestrator import chat, HOLIDAYS
from . import orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
DOCS=[]
READY=False

def extract_holidays(docs):
    # Parse dates and holiday names from eligible calendar documents automatically.
    result={"IN":set(),"US":set(),"DE":set()}
    import re
    from datetime import date
    for d in docs:
        if d.get("doc_type")!="calendar": continue
        for region in d.get("regions",[]):
            if region not in result: continue
            text=d["text"]
            # ISO dates
            for value in re.findall(r"20\d{2}-\d{2}-\d{2}",text):
                try:
                    if date.fromisoformat(value).year==2026: result[region].add(value)
                except ValueError: pass
            # formats like 26 January 2026 / January 26, 2026 / 26 Jan
            for m in re.finditer(r"(?i)\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+2026\b",text):
                try: result[region].add(date.fromisoformat(f"2026-{__import__('datetime').datetime.strptime(m.group(2),'%B').month:02d}-{int(m.group(1)):02d}").isoformat())
                except ValueError: pass
            for m in re.finditer(r"(?i)\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+2026\b",text):
                try: result[region].add(date.fromisoformat(f"2026-{__import__('datetime').datetime.strptime(m.group(1),'%B').month:02d}-{int(m.group(2)):02d}").isoformat())
                except ValueError: pass
    return result

@asynccontextmanager
async def lifespan(app):
    global DOCS, READY
    DOCS=ingest()
    holidays=extract_holidays(DOCS)
    HOLIDAYS.update(holidays)
    READY=True
    logging.getLogger("veltrix").info("ingestion_complete documents=%d chunks=%d",len({d["doc_id"] for d in DOCS}),len(DOCS))
    yield
    READY=False

app=FastAPI(title="Veltrix PeopleOps Assistant",version="1.0.0",lifespan=lifespan)

class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)

@app.get("/health")
def health():
    if not READY: raise HTTPException(status_code=503,detail="Ingestion is not complete")
    return {"status":"ok"}

@app.post("/chat")
def chat_endpoint(body:ChatRequest, x_employee_id:str=Header(default=None,alias="X-Employee-Id")):
    if not x_employee_id: raise HTTPException(status_code=401,detail="X-Employee-Id is required")
    emp=employee(x_employee_id)
    if not emp: raise HTTPException(status_code=401,detail="Unknown employee")
    result=chat(body.session_id,body.message,emp,DOCS)
    return result
