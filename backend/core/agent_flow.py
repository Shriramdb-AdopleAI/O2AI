from __future__ import annotations

from typing import Any, Dict, Optional, TypedDict, List
import asyncio

from langgraph.graph import StateGraph, END

from utility.utils import ocr_from_path
from core.enhanced_text_processor import EnhancedTextProcessor
from services.template_mapper import TemplateMapper


class AgentState(TypedDict, total=False):
    file_bytes: bytes
    filename: str
    apply_preprocessing: bool
    enhance_quality: bool
    include_raw_text: bool
    include_metadata: bool
    template_id: Optional[str]
    tenant_id: Optional[str]

    ocr: Dict[str, Any]
    extraction: Dict[str, Any]
    mapping: Dict[str, Any]
    errors: List[str]


async def node_ocr(state: AgentState) -> AgentState:
    try:
        result = await ocr_from_path(
            file_data=state["file_bytes"],
            original_filename=state.get("filename") or "unknown",
            ocr_engine="azure_computer_vision",
            ground_truth="",
            apply_preprocessing=bool(state.get("apply_preprocessing", True)),
            enhance_quality=bool(state.get("enhance_quality", True))
        )
        return {"ocr": result}
    except Exception as e:
        return {"errors": [f"ocr_error: {e}"]}


async def node_extract(state: AgentState) -> AgentState:
    try:
        ocr_text = (state.get("ocr") or {}).get("combined_text", "")
        filename = state.get("filename") or "unknown"
        text_processor = EnhancedTextProcessor()
        processing_result = await text_processor.process_without_template(
            ocr_text=ocr_text,
            filename=filename
        )
        return {
            "extraction": {
                "key_value_pairs": processing_result.key_value_pairs,
                "summary": processing_result.summary,
                "confidence_score": processing_result.confidence_score
            }
        }
    except Exception as e:
        return {"errors": [f"extraction_error: {e}"]}


async def node_map_template(state: AgentState) -> AgentState:
    template_id = state.get("template_id")
    if not template_id:
        return {}
    try:
        template_mapper = TemplateMapper()
        tenant_id = state.get("tenant_id") or "default"
        document_id = state.get("filename") or "doc"
        extraction = state.get("extraction") or {}
        mapping_result = template_mapper.map_document_to_template(
            template_id=template_id,
            tenant_id=tenant_id,
            extracted_data=extraction.get("key_value_pairs", {}),
            document_id=document_id,
            filename=state.get("filename") or "unknown"
        )
        return {
            "mapping": {
                "document_id": mapping_result.document_id,
                "filename": mapping_result.filename,
                "mapped_values": mapping_result.mapped_values,
                "confidence_scores": mapping_result.confidence_scores,
                "unmapped_fields": mapping_result.unmapped_fields,
                "processing_timestamp": mapping_result.processing_timestamp
            }
        }
    except Exception as e:
        return {"errors": [f"mapping_error: {e}"]}


def build_graph() -> Any:
    graph = StateGraph(AgentState)
    graph.add_node("ocr", node_ocr)
    graph.add_node("extract", node_extract)
    graph.add_node("map", node_map_template)

    graph.set_entry_point("ocr")
    graph.add_edge("ocr", "extract")
    graph.add_edge("extract", "map")
    graph.add_edge("map", END)
    return graph.compile()


async def run_agent(
    file_bytes: bytes,
    filename: str,
    tenant_id: Optional[str] = None,
    template_id: Optional[str] = None,
    apply_preprocessing: bool = True,
    enhance_quality: bool = True,
    include_raw_text: bool = False,
    include_metadata: bool = True
) -> Dict[str, Any]:
    agraph = build_graph()
    initial: AgentState = {
        "file_bytes": file_bytes,
        "filename": filename,
        "tenant_id": tenant_id,
        "template_id": template_id,
        "apply_preprocessing": apply_preprocessing,
        "enhance_quality": enhance_quality,
        "include_raw_text": include_raw_text,
        "include_metadata": include_metadata,
        "errors": []
    }
    result: AgentState = await agraph.ainvoke(initial)
    return {
        "ocr": result.get("ocr"),
        "extraction": result.get("extraction"),
        "mapping": result.get("mapping"),
        "errors": result.get("errors", [])
    }


