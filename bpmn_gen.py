import re
from openai import OpenAI


# ─────────────────────────────────────────────
# PlantUML generation (for visual diagram via Kroki)
# ─────────────────────────────────────────────

PLANTUML_SYSTEM_PROMPT = """Eres un experto certificado en BPMN 2.0 y en PlantUML.
Tu tarea es generar un DIAGRAMA DE ACTIVIDAD en PlantUML que represente fielmente un proceso de negocio.

REGLAS ESTRICTAS:
- Genera ÚNICAMENTE el código PlantUML. Sin explicaciones, sin texto antes o después.
- El código debe comenzar con @startuml y terminar con @enduml
- Usa la sintaxis de Activity Diagram (beta) de PlantUML
- Usa :texto; para tareas/actividades
- Usa if/then/else/elseif/endif para decisiones (gateways exclusivos)
- Usa fork/fork again/end fork para tareas paralelas (gateways paralelos) — solo si corresponde
- Usa start y stop/end para eventos de inicio y fin
- Usa |Swimlane| para separar por roles/áreas si hay múltiples participantes
- NO uses -> para conexiones, la sintaxis de actividad las maneja automáticamente
- Las etiquetas de decisión van entre paréntesis: if (¿Condición?) then (Sí)

SKINPARAM OBLIGATORIO (copiar al inicio, después de @startuml):
skinparam backgroundColor #FFFFFF
skinparam ActivityBackgroundColor #E3F2FD
skinparam ActivityBorderColor #1565C0
skinparam ActivityBorderThickness 2
skinparam ActivityFontSize 13
skinparam ArrowColor #37474F
skinparam ArrowThickness 2
skinparam DiamondBackgroundColor #FFF3E0
skinparam DiamondBorderColor #E65100
skinparam SwimlaneBackgroundColor #F5F5F5
skinparam SwimlaneBorderColor #BDBDBD
skinparam SwimlaneTitleFontSize 14
skinparam SwimlaneTitleFontStyle bold

EJEMPLO DE SALIDA CORRECTA:
@startuml
skinparam backgroundColor #FFFFFF
skinparam ActivityBackgroundColor #E3F2FD
skinparam ActivityBorderColor #1565C0
skinparam ActivityBorderThickness 2
skinparam ActivityFontSize 13
skinparam ArrowColor #37474F
skinparam ArrowThickness 2
skinparam DiamondBackgroundColor #FFF3E0
skinparam DiamondBorderColor #E65100

title Proceso de Atención al Cliente

start
:Recibir solicitud del cliente;
:Revisar tipo de solicitud;

if (¿Es reclamo?) then (Sí)
  :Escalar a supervisor;
  :Registrar reclamo en sistema;
else (No)
  :Resolver consulta directamente;
endif

:Enviar respuesta al cliente;
:Registrar cierre del caso;
stop
@enduml
"""


def generate_plantuml(client: OpenAI, conversation_history: list, lead_data: dict) -> str:
    """Generate PlantUML activity diagram code from conversation history using GLM-5.2."""

    conversation_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in conversation_history
        if msg["role"] in ("user", "assistant")
    )

    prompt = f"""Basándote en esta conversación de levantamiento de proceso, genera el diagrama de actividad PlantUML completo.

EMPRESA: {lead_data.get('empresa', 'N/A')}
PROCESO DOCUMENTADO POR: {lead_data.get('nombre', 'N/A')} ({lead_data.get('cargo', '')})

CONVERSACIÓN DE LEVANTAMIENTO:
{conversation_text}

Genera el código PlantUML completo del diagrama de actividad.
Incluye un título descriptivo con el nombre del proceso.
Si hay múltiples roles/áreas, usa swimlanes con |NombreRol|.
RESPONDE ÚNICAMENTE CON EL CÓDIGO PLANTUML. Sin texto adicional."""

    completion = client.chat.completions.create(
        model="z-ai/glm-5.2",
        messages=[
            {"role": "system", "content": PLANTUML_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=4096,
    )

    raw = completion.choices[0].message.content

    # Strip markdown code fences if present
    code_match = re.search(r"```(?:plantuml|uml)?\s*([\s\S]*?)\s*```", raw)
    if code_match:
        raw = code_match.group(1)

    # Find PlantUML boundaries
    if "@startuml" in raw and "@enduml" in raw:
        start = raw.index("@startuml")
        end = raw.rindex("@enduml") + len("@enduml")
        return raw[start:end]

    return raw


def fallback_plantuml(lead_data: dict) -> str:
    """Simple fallback PlantUML in case the LLM call fails."""
    empresa = lead_data.get("empresa", "Empresa")
    return f"""@startuml
skinparam backgroundColor #FFFFFF
skinparam ActivityBackgroundColor #E3F2FD
skinparam ActivityBorderColor #1565C0
skinparam ActivityBorderThickness 2
skinparam ActivityFontSize 13
skinparam ArrowColor #37474F
skinparam ArrowThickness 2
skinparam DiamondBackgroundColor #FFF3E0
skinparam DiamondBorderColor #E65100

title Proceso documentado — {empresa}

start
:Proceso documentado por Silvie;
note right
  El diagrama detallado se generará
  en la siguiente iteración.
end note
stop
@enduml"""


# ─────────────────────────────────────────────
# BPMN XML generation (for .bpmn file attachment)
# ─────────────────────────────────────────────

BPMN_SYSTEM_PROMPT = """Eres un experto certificado en BPMN 2.0 (Business Process Model and Notation).
Tu única tarea es generar XML BPMN 2.0 válido y completo a partir de una descripción de proceso.

REGLAS ESTRICTAS:
- Genera ÚNICAMENTE el XML. Sin explicaciones, sin texto antes o después.
- El XML debe comenzar con <?xml y terminar con </definitions>
- Usa IDs únicos y descriptivos (snake_case, ej: task_revisar_documento)
- Usa swimlanes/lanes si hay múltiples roles
- Para decisiones usa exclusiveGateway
- NO es necesario incluir el bloque BPMNDiagram (será renderizado por herramientas externas)

NAMESPACE OBLIGATORIO:
<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             targetNamespace="http://rhenic.cl/bpmn">
"""


def generate_bpmn_xml(client: OpenAI, conversation_history: list, lead_data: dict) -> str:
    """Generate BPMN 2.0 XML from conversation history using GLM-5.2.
    This XML is used for the .bpmn file attachment (editable in Bizagi).
    Visual rendering is handled separately via PlantUML + Kroki."""

    conversation_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in conversation_history
        if msg["role"] in ("user", "assistant")
    )

    prompt = f"""Basándote en esta conversación de levantamiento de proceso, genera el BPMN 2.0 XML.

EMPRESA: {lead_data.get('empresa', 'N/A')}
PROCESO DOCUMENTADO POR: {lead_data.get('nombre', 'N/A')} ({lead_data.get('cargo', '')})

CONVERSACIÓN DE LEVANTAMIENTO:
{conversation_text}

Genera el XML BPMN 2.0 con la estructura lógica del proceso (tareas, gateways, flujos).
No necesitas incluir el bloque BPMNDiagram con coordenadas.
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
    empresa = lead_data.get("empresa", "Empresa")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             targetNamespace="http://rhenic.cl/bpmn">
  <process id="proceso_1" name="Proceso {empresa}" isExecutable="false">
    <startEvent id="start" name="Inicio del proceso"/>
    <task id="task_1" name="Proceso documentado por Silvie"/>
    <endEvent id="end" name="Proceso completado"/>
    <sequenceFlow id="flow_1" sourceRef="start" targetRef="task_1"/>
    <sequenceFlow id="flow_2" sourceRef="task_1" targetRef="end"/>
  </process>
</definitions>"""
