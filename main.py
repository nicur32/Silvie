import os
import re
import uuid
import threading
import requests
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

from database import LeadDatabase
from prompts import build_system_prompt
from bpmn_gen import generate_bpmn_xml, fallback_bpmn, generate_plantuml, fallback_plantuml

load_dotenv()

# ─────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────
app = FastAPI(title="Silvie — Rhenic AI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ─────────────────────────────────────────────
# Globals
# ─────────────────────────────────────────────
db = LeadDatabase()
sessions: dict[str, dict] = {}

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
CALENDLY_URL   = os.getenv("CALENDLY_URL", "https://calendly.com/rhenic/diagnostico")

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
)

# ─────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str

class ChatResponse(BaseModel):
    session_id: str
    response: str
    stage: str
    lead_data: dict = {}
    bpmn_xml: Optional[str] = None
    plantuml_code: Optional[str] = None
    show_calendly: bool = False
    calendly_url: str = ""

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def new_session() -> dict:
    return {
        "stage": "IDENTIFICATION",
        "lead_data": {},
        "process_info": {},
        "narrative": "",
        "bpmn_xml": None,
        "plantuml_code": None,
        "history": [],
    }


def extract_markers(text: str) -> tuple[str, list[str]]:
    """Strip internal markers from LLM output; return clean text + list of found markers."""
    markers = []

    # [LEAD_COMPLETE:name|company|email|role]
    m = re.search(r"\[LEAD_COMPLETE:([^\]]+)\]", text)
    if m:
        markers.append(f"LEAD_COMPLETE:{m.group(1)}")
        text = text.replace(m.group(0), "").strip()

    for tag in ["INTERVIEW_COMPLETE", "NARRATIVE_APPROVED", "GENERATE_BPMN", "CTA_SHOWN"]:
        if f"[{tag}]" in text:
            markers.append(tag)
            text = text.replace(f"[{tag}]", "").strip()

    return text, markers


def call_llm(messages: list[dict]) -> str:
    completion = client.chat.completions.create(
        model="z-ai/glm-5.2",
        messages=messages,
        temperature=0.7,
        max_tokens=1500,
    )
    return completion.choices[0].message.content


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────
@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # Session management
    sid = req.session_id or str(uuid.uuid4())
    if sid not in sessions:
        sessions[sid] = new_session()
    s = sessions[sid]

    # Append user message
    s["history"].append({"role": "user", "content": req.message})

    # Build messages for LLM (system + last 30 turns)
    system_prompt = build_system_prompt(
        s["stage"], s["lead_data"], s["process_info"], s["narrative"]
    )
    messages = [{"role": "system", "content": system_prompt}] + s["history"][-30:]

    # Call LLM
    try:
        raw_response = call_llm(messages)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")

    # Extract markers
    clean_response, markers = extract_markers(raw_response)

    # ── Process markers ──────────────────────
    show_calendly = False
    bpmn_xml      = s.get("bpmn_xml")
    plantuml_code = s.get("plantuml_code")

    for marker in markers:

        # ── IDENTIFICATION complete ──────────
        if marker.startswith("LEAD_COMPLETE:"):
            parts = marker.split(":", 1)[1].split("|")
            if len(parts) >= 4:
                lead = {
                    "nombre":  parts[0].strip(),
                    "empresa": parts[1].strip(),
                    "email":   parts[2].strip(),
                    "cargo":   parts[3].strip(),
                }
                s["lead_data"] = lead

                existing = db.get_lead(lead["email"])
                if existing:
                    # Lead already did a process lift — redirect to CTA
                    clean_response = (
                        f"¡Hola {lead['nombre']}! 👋 "
                        f"Veo que ya hicimos un levantamiento de procesos juntos para {lead['empresa']}. "
                        f"Como parte de nuestro servicio gratuito, podemos documentar un proceso por empresa. 😊\n\n"
                        f"¿Te gustaría agendar una reunión para ver cómo podemos avanzar con instructivos detallados, "
                        f"la matriz de desarrollo y el Instructor Inteligente para tu equipo?"
                    )
                    s["stage"] = "CTA"
                    show_calendly = True
                else:
                    db.create_lead(lead)
                    s["stage"] = "PROCESS_INTERVIEW"

        # ── Interview complete ───────────────
        elif marker == "INTERVIEW_COMPLETE":
            s["stage"] = "NARRATIVE_REVIEW"

        # ── Narrative approved ───────────────
        elif marker == "NARRATIVE_APPROVED":
            s["narrative"] = clean_response
            s["stage"] = "BPMN_READY"

        # ── Generate BPMN + PlantUML ────────────────
        elif marker == "GENERATE_BPMN":
            # PlantUML — for visual rendering in PDF via Kroki
            try:
                puml = generate_plantuml(client, s["history"], s["lead_data"])
            except Exception:
                puml = fallback_plantuml(s["lead_data"])

            s["plantuml_code"] = puml
            plantuml_code = puml

            # BPMN XML — structural only, for Bizagi download
            try:
                xml = generate_bpmn_xml(client, s["history"], s["lead_data"])
            except Exception:
                xml = fallback_bpmn(s["lead_data"])

            s["bpmn_xml"] = xml
            bpmn_xml = xml

            if s["lead_data"].get("email"):
                db.update_lead_process(s["lead_data"]["email"], xml, s["narrative"])

                # Send payload to Make Webhook in background
                webhook_url = "https://hook.us2.make.com/qysp2hvo42jbv7yk2y8mzkbhyfgd9gsn"
                payload = {
                    "nombre": s["lead_data"].get("nombre", ""),
                    "empresa": s["lead_data"].get("empresa", ""),
                    "email": s["lead_data"].get("email", ""),
                    "cargo": s["lead_data"].get("cargo", ""),
                    "narrative": s["narrative"],
                    "plantuml_code": puml
                }
                threading.Thread(target=lambda: requests.post(webhook_url, json=payload)).start()

            s["stage"] = "CTA"

        # ── CTA shown ────────────────────────
        elif marker == "CTA_SHOWN":
            show_calendly = True

    # Append assistant response to history
    s["history"].append({"role": "assistant", "content": clean_response})

    return ChatResponse(
        session_id=sid,
        response=clean_response,
        stage=s["stage"],
        lead_data=s["lead_data"],
        bpmn_xml=bpmn_xml,
        plantuml_code=plantuml_code,
        show_calendly=show_calendly,
        calendly_url=CALENDLY_URL,
    )


@app.get("/leads")
async def list_leads():
    """Internal endpoint to see all captured leads."""
    return {"leads": db.get_all_leads()}


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "Silvie v1.0", "model": "z-ai/glm-5.2"}
