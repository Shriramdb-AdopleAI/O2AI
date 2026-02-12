import os
import uuid
import pandas as pd
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from io import BytesIO
import logging
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class TemplateField:
    """Represents a field in the template"""
    key: str
    display_name: str
    data_type: str = "text"
    required: bool = False
    description: str = ""
    
@dataclass
class MappingResult:
    """Result of mapping document values to template"""
    document_id: str
    filename: str
    mapped_values: Dict[str, Any]
    confidence_scores: Dict[str, float]
    unmapped_fields: List[str]
    processing_timestamp: str

class TemplateMapper:
    """Service for handling Excel templates and document value mapping"""
    
    def __init__(self, templates_dir: str = "data/templates"):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.templates_cache = {}
        # Disable fuzzy mapping by default to avoid hallucinated mappings
        self.allow_fuzzy_mapping = False
    
    def upload_template(self, file_data: bytes, filename: str, tenant_id: str) -> Dict[str, Any]:
        """
        Upload and parse an Excel template file
        
        Args:
            file_data: Excel file bytes
            filename: Original filename
            tenant_id: Tenant identifier
            
        Returns:
            Template metadata and parsed fields
        """
        try:
            # Generate template ID
            template_id = str(uuid.uuid4())
            
            # Parse Excel file: read all sheets
            sheets = pd.read_excel(BytesIO(file_data), sheet_name=None)
            
            # Extract template fields from all sheets
            # Strategy per sheet:
            # 1) Prefer a column named Key/Field to enumerate field names from rows
            # 2) Else use header row as fields
            # Deduplicate by field key across sheets
            aggregated_fields: Dict[str, TemplateField] = {}
            for sheet_name, df in sheets.items():
                if df is None or df.empty:
                    continue
                df = df.copy()
                df.columns = [str(c).strip() for c in df.columns]

                # Promote first row to header if it looks like ['Key','Value']
                first_row_lower = [str(v).strip().lower() for v in (df.iloc[0].tolist() if len(df) > 0 else [])]
                if {'key', 'value'}.issubset(set(first_row_lower)) and len(first_row_lower) >= 2:
                    df = df[1:].reset_index(drop=True)
                    df.columns = [str(v).strip() for v in first_row_lower]
                lower_cols = {str(c).strip().lower(): c for c in df.columns}
                key_col_name = None
                for candidate in ["key", "field", "fields", "name"]:
                    if candidate in lower_cols:
                        key_col_name = lower_cols[candidate]
                        break
                if key_col_name is not None:
                    value_col = None
                    for candidate in ["value", "values", "sample", "example"]:
                        if candidate in lower_cols:
                            value_col = lower_cols[candidate]
                            break
                    keys_series = (
                        df[key_col_name]
                        .astype(str, errors='ignore')
                        .map(lambda s: str(s).strip())
                        .replace({"": pd.NA, "nan": pd.NA})
                        .dropna()
                    )
                    for idx, key in keys_series.items():
                        if key in aggregated_fields:
                            continue
                        sample_value = df.loc[idx, value_col] if (value_col is not None and idx in df.index) else ""
                        aggregated_fields[key] = TemplateField(
                            key=key,
                            display_name=key,
                            data_type=self._detect_data_type(sample_value),
                            required=False,
                            description=f"Auto-generated from sheet '{sheet_name}'"
                        )
                else:
                    # Heuristic: first column as keys if it contains multiple strings
                    first_col = df.columns[0]
                    first_col_values = (
                        df[first_col]
                        .astype(str, errors='ignore')
                        .map(lambda s: str(s).strip())
                        .replace({"": pd.NA, "nan": pd.NA})
                        .dropna()
                    )
                    if len(first_col_values) >= 2:
                        value_col = df.columns[1] if len(df.columns) > 1 else None
                        for idx, key in first_col_values.items():
                            if key in aggregated_fields:
                                continue
                            sample_value = df.loc[idx, value_col] if (value_col is not None and idx in df.index) else ""
                            aggregated_fields[key] = TemplateField(
                                key=key,
                                display_name=key,
                                data_type=self._detect_data_type(sample_value),
                                required=False,
                                description=f"Auto-generated from sheet '{sheet_name}' first column"
                            )
                    else:
                        # Fallback: headers as fields
                        for col in df.columns:
                            key = str(col).strip()
                            if key in aggregated_fields or key.startswith("Unnamed"):
                                continue
                            sample_value = df[col].iloc[0] if len(df) > 0 else ""
                            aggregated_fields[key] = TemplateField(
                                key=key,
                                display_name=key,
                                data_type=self._detect_data_type(sample_value),
                                required=False,
                                description=f"Auto-generated from sheet '{sheet_name}' header"
                            )

            template_fields = list(aggregated_fields.values())
            
            # Save template file
            template_path = self.templates_dir / f"{tenant_id}_{template_id}.xlsx"
            with open(template_path, 'wb') as f:
                f.write(file_data)
            
            # Save template metadata
            metadata = {
                "template_id": template_id,
                "filename": filename,
                "tenant_id": tenant_id,
                "fields": [asdict(field) for field in template_fields],
                "created_at": datetime.now().isoformat(),
                "file_path": str(template_path),
                "total_columns": len(template_fields)
            }
            
            metadata_path = self.templates_dir / f"{tenant_id}_{template_id}_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Cache template
            self.templates_cache[template_id] = metadata
            
            logger.info(f"Template uploaded successfully: {template_id} for tenant {tenant_id}")
            
            return {
                "success": True,
                "template_id": template_id,
                "metadata": metadata,
                "message": f"Template uploaded successfully with {len(template_fields)} fields"
            }
            
        except Exception as e:
            logger.error(f"Failed to upload template: {e}")
            return {
                "success": False,
                "message": "Failed to process template file"
            }
    
    def get_template(self, template_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get template metadata and fields"""
        try:
            if template_id in self.templates_cache:
                return self.templates_cache[template_id]
            
            # Load from file
            metadata_path = self.templates_dir / f"{tenant_id}_{template_id}_metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    self.templates_cache[template_id] = metadata
                    return metadata
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get template {template_id}: {e}")
            return None
    
    def list_templates(self, tenant_id: str) -> List[Dict[str, Any]]:
        """List all templates for a tenant"""
        try:
            templates = []
            
            # Scan template directory
            for metadata_file in self.templates_dir.glob(f"{tenant_id}_*_metadata.json"):
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        # Only include essential info in list
                        templates.append({
                            "template_id": metadata["template_id"],
                            "filename": metadata["filename"],
                            "created_at": metadata["created_at"],
                            "total_columns": metadata["total_columns"],
                            "fields_preview": [f["key"] for f in metadata["fields"][:5]]  # First 5 fields
                        })
                except Exception as e:
                    logger.warning(f"Failed to load template metadata {metadata_file}: {e}")
            
            return sorted(templates, key=lambda x: x["created_at"], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list templates for tenant {tenant_id}: {e}")
            return []
    
    def map_document_to_template(self, 
                               template_id: str, 
                               tenant_id: str,
                               extracted_data: Dict[str, Any],
                               document_id: str,
                               filename: str) -> MappingResult:
        """
        Map extracted document values to template fields
        
        Args:
            template_id: Template to map against
            tenant_id: Tenant identifier
            extracted_data: Key-value pairs from document processing
            document_id: Unique document identifier
            filename: Original document filename
            
        Returns:
            MappingResult with mapped values and confidence scores
        """
        try:
            # Get template
            template = self.get_template(template_id, tenant_id)
            if not template:
                raise ValueError(f"Template {template_id} not found")
            
            template_fields = {field["key"]: field for field in template["fields"]}
            
            # Perform intelligent mapping
            mapped_values = {}
            confidence_scores = {}
            unmapped_fields = []
            
            # Direct mapping (exact key matches only unless fuzzy mapping is explicitly enabled)
            for template_key, template_field in template_fields.items():
                if template_key in extracted_data:
                    mapped_values[template_key] = extracted_data[template_key]
                    confidence_scores[template_key] = 1.0
                else:
                    if self.allow_fuzzy_mapping:
                        # Fuzzy mapping (similar keys) with a strict threshold to minimize errors
                        best_match, confidence = self._find_best_match(template_key, extracted_data)
                        if best_match and confidence >= 0.95:
                            mapped_values[template_key] = extracted_data[best_match]
                            confidence_scores[template_key] = confidence
                        else:
                            mapped_values[template_key] = ""
                            confidence_scores[template_key] = 0.0
                            unmapped_fields.append(template_key)
                    else:
                        # Do not attempt fuzzy mapping; mark as unmapped and keep value empty
                        mapped_values[template_key] = ""
                        confidence_scores[template_key] = 0.0
                        unmapped_fields.append(template_key)
            
            return MappingResult(
                document_id=document_id,
                filename=filename,
                mapped_values=mapped_values,
                confidence_scores=confidence_scores,
                unmapped_fields=unmapped_fields,
                processing_timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Failed to map document to template: {e}")
            raise
    
    def update_mapped_values(self, 
                           template_id: str,
                           tenant_id: str,
                           document_id: str,
                           updated_values: Dict[str, Any]) -> Dict[str, Any]:
        """Update mapped values for a document"""
        try:
            # This would typically save to a database
            # For now, we'll return success
            logger.info(f"Updated mapped values for document {document_id} in template {template_id}")
            
            return {
                "success": True,
                "message": "Mapped values updated successfully",
                "updated_fields": list(updated_values.keys())
            }
            
        except Exception as e:
            # Log full exception details on the server for debugging
            logger.exception(f"Failed to update mapped values for document {document_id} in template {template_id}")
            # Return a generic error message to avoid exposing internal details
            return {
                "success": False,
                "error": "Failed to update mapped values"
            }
    
    def generate_consolidated_excel(self, 
                                  template_id: str,
                                  tenant_id: str,
                                  mapping_results: List[MappingResult]) -> BytesIO:
        """
        Generate consolidated Excel file with all mapped documents
        
        Args:
            template_id: Template to use for structure
            tenant_id: Tenant identifier
            mapping_results: List of mapping results
            
        Returns:
            BytesIO object containing Excel file
        """
        try:
            # Get template structure
            template = self.get_template(template_id, tenant_id)
            if not template:
                raise ValueError(f"Template {template_id} not found")
            
            # Create DataFrame with template structure
            template_fields = [field["key"] for field in template["fields"]]
            
            # Add document metadata columns
            all_columns = ["Document ID", "Filename", "Processing Date"] + template_fields
            
            # Build data rows
            data_rows = []
            for result in mapping_results:
                row = {
                    "Document ID": result.document_id,
                    "Filename": result.filename,
                    "Processing Date": result.processing_timestamp
                }
                
                # Add mapped values
                for field in template_fields:
                    row[field] = result.mapped_values.get(field, "")
                
                data_rows.append(row)
            
            # Create DataFrame
            df = pd.DataFrame(data_rows, columns=all_columns)
            
            # Generate Excel file
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Main data sheet
                df.to_excel(writer, sheet_name='Mapped Data', index=False)
                
                # Template structure sheet
                template_df = pd.DataFrame(template["fields"])
                template_df.to_excel(writer, sheet_name='Template Structure', index=False)
                
                # Mapping summary sheet
                summary_data = []
                for result in mapping_results:
                    summary_data.append({
                        "Document ID": result.document_id,
                        "Filename": result.filename,
                        "Total Fields": len(template_fields),
                        "Mapped Fields": len([k for k, v in result.mapped_values.items() if v]),
                        "Unmapped Fields": len(result.unmapped_fields),
                        "Average Confidence": sum(result.confidence_scores.values()) / len(result.confidence_scores) if result.confidence_scores else 0
                    })
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Mapping Summary', index=False)
            
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Failed to generate consolidated Excel: {e}")
            raise
    
    def _detect_data_type(self, sample_value: Any) -> str:
        """Detect data type from sample value"""
        if pd.isna(sample_value):
            return "text"
        
        if isinstance(sample_value, (int, float)):
            return "number"
        elif isinstance(sample_value, str):
            if sample_value.lower() in ['true', 'false', 'yes', 'no', '1', '0']:
                return "boolean"
            elif '@' in sample_value and '.' in sample_value:
                return "email"
            elif len(sample_value) == 10 and sample_value.count('-') == 2:
                return "date"
            else:
                return "text"
        else:
            return "text"
    
    def _find_best_match(self, template_key: str, extracted_data: Dict[str, Any]) -> Tuple[Optional[str], float]:
        """Find best matching key in extracted data using fuzzy matching"""
        template_key_lower = template_key.lower().strip()
        
        best_match = None
        best_score = 0.0
        
        for extracted_key, value in extracted_data.items():
            extracted_key_lower = extracted_key.lower().strip()
            
            # Exact match
            if template_key_lower == extracted_key_lower:
                return extracted_key, 1.0
            
            # Partial match (contains)
            if template_key_lower in extracted_key_lower or extracted_key_lower in template_key_lower:
                score = min(len(template_key_lower), len(extracted_key_lower)) / max(len(template_key_lower), len(extracted_key_lower))
                if score > best_score:
                    best_match = extracted_key
                    best_score = score
            
            # Word-based matching
            template_words = set(template_key_lower.split())
            extracted_words = set(extracted_key_lower.split())
            
            if template_words & extracted_words:  # Intersection
                score = len(template_words & extracted_words) / len(template_words | extracted_words)
                if score > best_score:
                    best_match = extracted_key
                    best_score = score
        
        return best_match, best_score
    
    def delete_template(self, template_id: str, tenant_id: str) -> Dict[str, Any]:
        """Delete a template and its metadata"""
        try:
            # Remove files
            template_path = self.templates_dir / f"{tenant_id}_{template_id}.xlsx"
            metadata_path = self.templates_dir / f"{tenant_id}_{template_id}_metadata.json"
            
            if template_path.exists():
                template_path.unlink()
            if metadata_path.exists():
                metadata_path.unlink()
            
            # Remove from cache
            if template_id in self.templates_cache:
                del self.templates_cache[template_id]
            
            logger.info(f"Template {template_id} deleted successfully")
            
            return {
                "success": True,
                "message": "Template deleted successfully"
            }
            
        except Exception as e:
            # Log the detailed exception server-side, but do not expose it to the caller
            logger.error(f"Failed to delete template {template_id}: {e}")
            return {
                "success": False,
                "error": "Failed to delete template"
            }
