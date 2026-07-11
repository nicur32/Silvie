import re
from openai import OpenAI


BPMN_SYSTEM_PROMPT = """Eres un experto certificado en BPMN 2.0 (Business Process Model and Notation).
Tu única tarea es generar XML BPMN 2.0 válido y completo a partir de una descripción de proceso.

REGLAS ESTRICTAS:
- Genera ÚNICAMENTE el XML. Sin explicaciones, sin texto antes o después.
- El XML debe comenzar con <?xml y terminar con </definitions>
- Usa IDs únicos y descriptivos (snake_case, ej: task_revisar_documento)
- Incluye SIEMPRE las posiciones de los elementos (BPMNDiagram con BPMNShape y BPMNEdge)
- Usa swimlanes/lanes si hay múltiples roles
- Para decisiones usa exclusiveGateway
- Posiciona los elementos de izquierda a derecha con espacio de 200px entre elementos

NAMESPACE OBLIGATORIO:
<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
             xmlns:omgdc="http://www.omg.org/spec/DD/20100524/DC"
             xmlns:omgdi="http://www.omg.org/spec/DD/20100524/DI"
             targetNamespace="http://rhenic.cl/bpmn">
"""


def generate_bpmn_xml(client: OpenAI, conversation_history: list, lead_data: dict) -> str:
    """Generate BPMN 2.0 XML from conversation history using GLM-5.2."""

    conversation_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in conversation_history
        if msg["role"] in ("user", "assistant")
    )

    prompt = f"""Basándote en esta conversación de levantamiento de proceso, genera el BPMN 2.0 XML completo.

EMPRESA: {lead_data.get('empresa', 'N/A')}
PROCESO DOCUMENTADO POR: {lead_data.get('nombre', 'N/A')} ({lead_data.get('cargo', '')})

CONVERSACIÓN DE LEVANTAMIENTO:
{conversation_text}

Genera el XML BPMN 2.0 completo, válido y con posicionamiento de elementos.
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
             xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
             xmlns:omgdc="http://www.omg.org/spec/DD/20100524/DC"
             xmlns:omgdi="http://www.omg.org/spec/DD/20100524/DI"
             targetNamespace="http://rhenic.cl/bpmn">
  <process id="proceso_1" name="Proceso {empresa}" isExecutable="false">
    <startEvent id="start" name="Inicio del proceso"/>
    <task id="task_1" name="Proceso documentado por Silvie"/>
    <endEvent id="end" name="Proceso completado"/>
    <sequenceFlow id="flow_1" sourceRef="start" targetRef="task_1"/>
    <sequenceFlow id="flow_2" sourceRef="task_1" targetRef="end"/>
  </process>
  <bpmndi:BPMNDiagram id="diagram_1">
    <bpmndi:BPMNPlane id="plane_1" bpmnElement="proceso_1">
      <bpmndi:BPMNShape id="shape_start" bpmnElement="start">
        <omgdc:Bounds x="100" y="120" width="36" height="36"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="shape_task_1" bpmnElement="task_1">
        <omgdc:Bounds x="220" y="100" width="140" height="80"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNShape id="shape_end" bpmnElement="end">
        <omgdc:Bounds x="440" y="120" width="36" height="36"/>
      </bpmndi:BPMNShape>
      <bpmndi:BPMNEdge id="edge_1" bpmnElement="flow_1">
        <omgdi:waypoint x="136" y="138"/><omgdi:waypoint x="220" y="138"/>
      </bpmndi:BPMNEdge>
      <bpmndi:BPMNEdge id="edge_2" bpmnElement="flow_2">
        <omgdi:waypoint x="360" y="138"/><omgdi:waypoint x="440" y="138"/>
      </bpmndi:BPMNEdge>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</definitions>"""
