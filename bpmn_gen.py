import re
from openai import OpenAI


# ─────────────────────────────────────────────
# PLANTUML GENERATOR (visual — para Kroki/PDF)
# ─────────────────────────────────────────────

PLANTUML_SYSTEM_PROMPT = """Eres un experto en modelado de procesos de negocio.
Tu única tarea es generar código PlantUML de Activity Diagram a partir de una descripción de proceso.

REGLAS ESTRICTAS:
- Genera ÚNICAMENTE el código PlantUML. Sin explicaciones, sin texto antes o después.
- El código DEBE comenzar con @startuml y terminar con @enduml
- Usa Activity Diagram syntax (start, stop, :actividad;, if/else, fork, etc.)
- Aplica los siguientes skinparams exactamente:

skinparam backgroundColor #FFFFFF
skinparam ActivityBackgroundColor #E3F2FD
skinparam ActivityBorderColor #1565C0
skinparam ActivityBorderThickness 2
skinparam ActivityFontSize 13
skinparam ActivityFontName Arial
skinparam ArrowColor #37474F
skinparam ArrowThickness 2
skinparam DiamondBackgroundColor #FFF3E0
skinparam DiamondBorderColor #E65100

- Usa "title Nombre del Proceso" al inicio
- Representa decisiones con if/else
- Usa fork/fork again para procesos paralelos si aplica
- Máximo 20 actividades para mantener legibilidad
"""


def generate_plantuml(client: OpenAI, conversation_history: list, lead_data: dict) -> str:
    """Generate PlantUML Activity Diagram for visual rendering via Kroki."""

    conversation_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in conversation_history
        if msg["role"] in ("user", "assistant")
    )

    prompt = f"""Basándote en esta conversación de levantamiento de proceso, genera el diagrama PlantUML Activity Diagram.

EMPRESA: {lead_data.get('empresa', 'N/A')}
PROCESO DOCUMENTADO POR: {lead_data.get('nombre', 'N/A')} ({lead_data.get('cargo', '')})

CONVERSACIÓN DE LEVANTAMIENTO:
{conversation_text}

Genera el código PlantUML completo.
RESPONDE ÚNICAMENTE CON EL CÓDIGO PLANTUML. Sin texto adicional."""

    completion = client.chat.completions.create(
        model="z-ai/glm-5.2",
        messages=[
            {"role": "system", "content": PLANTUML_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=2048,
    )

    raw = completion.choices[0].message.content

    # Strip markdown fences if present
    code_match = re.search(r"```(?:plantuml)?\s*([\s\S]*?)\s*```", raw)
    if code_match:
        raw = code_match.group(1)

    # Ensure boundaries
    if "@startuml" in raw and "@enduml" in raw:
        start = raw.index("@startuml")
        end = raw.rindex("@enduml") + len("@enduml")
        return raw[start:end]

    return raw


def fallback_plantuml(lead_data: dict) -> str:
    """Fallback PlantUML diagram when LLM generation fails."""
    empresa = lead_data.get("empresa", "Empresa")
    nombre = lead_data.get("nombre", "")
    return f"""@startuml
skinparam backgroundColor #FFFFFF
skinparam ActivityBackgroundColor #E3F2FD
skinparam ActivityBorderColor #1565C0
skinparam ActivityBorderThickness 2
skinparam ActivityFontSize 13
skinparam ActivityFontName Arial
skinparam ArrowColor #37474F
skinparam ArrowThickness 2
skinparam DiamondBackgroundColor #FFF3E0
skinparam DiamondBorderColor #E65100

title Proceso documentado — {empresa}

start
:Inicio del proceso;
:Proceso levantado por {nombre};
:Documentado con Silvie — Rhenic;
stop
@enduml"""


# ─────────────────────────────────────────────
# BPMN XML GENERATOR (estructural — para Bizagi)
# ─────────────────────────────────────────────

BPMN_SYSTEM_PROMPT = """Eres un experto certificado en BPMN 2.0 (Business Process Model and Notation).
Tu única tarea es generar XML BPMN 2.0 estructural a partir de una descripción de proceso.
Este XML es para uso en herramientas como Bizagi, NO para renderizado visual.

REGLAS ESTRICTAS:
- Genera ÚNICAMENTE el XML. Sin explicaciones, sin texto antes o después.
- El XML debe comenzar con <?xml y terminar con </definitions>
- Usa IDs únicos y descriptivos (snake_case, ej: task_revisar_documento)
- Usa swimlanes/lanes si hay múltiples roles
- Para decisiones usa exclusiveGateway
- NO es necesario incluir BPMNDiagram con coordenadas — solo la estructura lógica del proceso

NAMESPACE OBLIGATORIO:
<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             targetNamespace="http://rhenic.cl/bpmn">
"""


def generate_bpmn_xml(client: OpenAI, conversation_history: list, lead_data: dict) -> str:
    """Generate BPMN 2.0 XML (structural only, for Bizagi download)."""

    conversation_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in conversation_history
        if msg["role"] in ("user", "assistant")
    )

    prompt = f"""Basándote en esta conversación de levantamiento de proceso, genera el BPMN 2.0 XML estructural.

EMPRESA: {lead_data.get('empresa', 'N/A')}
PROCESO DOCUMENTADO POR: {lead_data.get('nombre', 'N/A')} ({lead_data.get('cargo', '')})

CONVERSACIÓN DE LEVANTAMIENTO:
{conversation_text}

Genera el XML BPMN 2.0 con la estructura lógica del proceso (sin coordenadas visuales).
RESPONDE ÚNICAMENTE CON EL XML. Sin texto adicional."""

    completion = client.chat.completions.create(
        model="z-ai/glm-5.2",
        messages=[
            {"role": "system", "content": BPMN_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=4096,
    )

    raw = completion.choices[0].message.content

    # Strip markdown code fences if present
    xml_match = re.search(r"```(?:xml)?\s*([\s\S]*?)\s*```", raw)
    if xml_match:
        raw = xml_match.group(1)

    # Find XML boundaries
    if "<?xml" in raw and "</definitions>" in raw:
        start = raw.index("<?xml")
        end = raw.rindex("</definitions>") + len("</definitions>")
        return raw[start:end]

    return raw


def fallback_bpmn(lead_data: dict) -> str:
    """Fallback BPMN XML when LLM generation fails."""
    empresa = lead_data.get("empresa", "Empresa")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             targetNamespace="http://rhenic.cl/bpmn">
  <process id="proceso_1" name="Proceso {empresa}" isExecutable="false">
    <startEvent id="start" name="Inicio del proceso"/>
    <task id="task_1" name="Proceso documentado por Silvie — Rhenic"/>
    <endEvent id="end" name="Proceso completado"/>
    <sequenceFlow id="flow_1" sourceRef="start" targetRef="task_1"/>
    <sequenceFlow id="flow_2" sourceRef="task_1" targetRef="end"/>
  </process>
</definitions>"""
