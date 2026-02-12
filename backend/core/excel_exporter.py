import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import pandas as pd
from io import BytesIO
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class ExcelExporter:
    """Handles Excel export functionality for OCR results."""
    
    def __init__(self):
        """Initialize Excel exporter."""
        self.supported_formats = ['xlsx', 'xls']
        logger.info("Excel exporter initialized")
    
    def export_individual_file(self, 
                              processing_result: 'ProcessingResult', 
                              filename: str,
                              include_raw_text: bool = True,
                              include_metadata: bool = True) -> bytes:
        """
        Export individual file processing results to Excel.
        
        Args:
            processing_result: ProcessingResult object
            filename: Original filename
            include_raw_text: Whether to include raw OCR text
            include_metadata: Whether to include processing metadata
            
        Returns:
            Excel file as bytes
        """
        logger.info(f"Exporting individual file results for {filename}")
        
        try:
            # Create Excel writer
            output = BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Sheet 1: Key-Value Pairs
                self._create_key_value_sheet(writer, processing_result, filename)
                
                # Sheet 2: Raw Text (if requested)
                if include_raw_text:
                    self._create_raw_text_sheet(writer, processing_result, filename)
                
                # Sheet 3: Metadata (if requested)
                if include_metadata:
                    self._create_metadata_sheet(writer, processing_result, filename)
                
                # Sheet 4: Template Mapping (if template was used)
                if processing_result.template_used:
                    self._create_template_mapping_sheet(writer, processing_result, filename)
            
            output.seek(0)
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to export individual file {filename}: {e}")
            raise
    
    def export_consolidated_files(self, 
                                processing_results: List['ProcessingResult'],
                                filenames: List[str],
                                template_used: Optional[str] = None) -> bytes:
        """
        Export consolidated results from multiple files to Excel.
        
        Args:
            processing_results: List of ProcessingResult objects
            filenames: List of original filenames
            template_used: Template name if template was used
            
        Returns:
            Excel file as bytes
        """
        logger.info(f"Exporting consolidated results for {len(processing_results)} files")
        
        try:
            output = BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Sheet 1: Consolidated Key-Value Pairs
                self._create_consolidated_key_value_sheet(writer, processing_results, filenames)
                
                # Sheet 2: Individual File Results
                self._create_individual_results_sheet(writer, processing_results, filenames)
                
                # Sheet 3: Summary Statistics
                self._create_summary_sheet(writer, processing_results, filenames, template_used)
                
                # Sheet 4: Template Analysis (if template was used)
                if template_used:
                    self._create_template_analysis_sheet(writer, processing_results, filenames, template_used)
            
            output.seek(0)
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to export consolidated results: {e}")
            raise
    
    def _create_key_value_sheet(self, writer, processing_result: 'ProcessingResult', filename: str):
        """Create key-value pairs sheet."""
        # Prepare data for DataFrame
        data = []
        for key, value in processing_result.key_value_pairs.items():
            data.append({
                'Field': key,
                'Value': str(value),
                'Confidence': processing_result.confidence_score,
                'Extraction_Time': processing_result.processing_time
            })
        
        if data:
            df = pd.DataFrame(data)
            df.to_excel(writer, sheet_name='Key-Value Pairs', index=False)
        else:
            # Create empty sheet with headers
            empty_df = pd.DataFrame(columns=['Field', 'Value', 'Confidence', 'Extraction_Time'])
            empty_df.to_excel(writer, sheet_name='Key-Value Pairs', index=False)
    
    def _create_raw_text_sheet(self, writer, processing_result: 'ProcessingResult', filename: str):
        """Create raw text sheet."""
        data = {
            'Filename': [filename],
            'Raw_Text': [processing_result.raw_text],
            'Text_Length': [len(processing_result.raw_text)],
            'Processing_Time': [processing_result.processing_time],
            'Confidence_Score': [processing_result.confidence_score]
        }
        
        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name='Raw Text', index=False)
    
    def _create_metadata_sheet(self, writer, processing_result: 'ProcessingResult', filename: str):
        """Create metadata sheet."""
        metadata = {
            'Field': [
                'Filename',
                'Processing Time (seconds)',
                'Confidence Score',
                'Template Used',
                'Key-Value Pairs Count',
                'Summary Length',
                'Export Timestamp'
            ],
            'Value': [
                filename,
                f"{processing_result.processing_time:.2f}",
                f"{processing_result.confidence_score:.2f}",
                processing_result.template_used or 'None',
                str(len(processing_result.key_value_pairs)),
                str(len(processing_result.summary)),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
        }
        
        df = pd.DataFrame(metadata)
        df.to_excel(writer, sheet_name='Metadata', index=False)
    
    def _create_template_mapping_sheet(self, writer, processing_result: 'ProcessingResult', filename: str):
        """Create template mapping sheet."""
        if not processing_result.template_mapping:
            return
        
        data = []
        for field, status in processing_result.template_mapping.items():
            data.append({
                'Template_Field': field,
                'Status': status,
                'Extracted_Value': processing_result.key_value_pairs.get(field, 'Not Found')
            })
        
        if data:
            df = pd.DataFrame(data)
            df.to_excel(writer, sheet_name='Template Mapping', index=False)
    
    def _create_consolidated_key_value_sheet(self, writer, processing_results: List['ProcessingResult'], filenames: List[str]):
        """Create consolidated key-value pairs sheet."""
        # Collect all unique keys
        all_keys = set()
        for result in processing_results:
            all_keys.update(result.key_value_pairs.keys())
        
        # Create consolidated data
        data = []
        for key in sorted(all_keys):
            row = {'Field': key}
            for i, (result, filename) in enumerate(zip(processing_results, filenames)):
                row[f'File_{i+1}_{filename}'] = result.key_value_pairs.get(key, 'N/A')
            data.append(row)
        
        if data:
            df = pd.DataFrame(data)
            df.to_excel(writer, sheet_name='Consolidated Data', index=False)
        else:
            empty_df = pd.DataFrame(columns=['Field'])
            empty_df.to_excel(writer, sheet_name='Consolidated Data', index=False)
    
    def _create_individual_results_sheet(self, writer, processing_results: List['ProcessingResult'], filenames: List[str]):
        """Create individual results summary sheet."""
        data = []
        for i, (result, filename) in enumerate(zip(processing_results, filenames)):
            data.append({
                'File_Number': i + 1,
                'Filename': filename,
                'Key_Value_Pairs_Count': len(result.key_value_pairs),
                'Processing_Time': f"{result.processing_time:.2f}s",
                'Confidence_Score': f"{result.confidence_score:.2f}",
                'Template_Used': result.template_used or 'None',
                'Text_Length': len(result.raw_text),
                'Summary_Length': len(result.summary)
            })
        
        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name='Individual Results', index=False)
    
    def _create_summary_sheet(self, writer, processing_results: List['ProcessingResult'], filenames: List[str], template_used: Optional[str]):
        """Create summary statistics sheet."""
        total_files = len(processing_results)
        total_processing_time = sum(result.processing_time for result in processing_results)
        avg_confidence = sum(result.confidence_score for result in processing_results) / total_files if total_files > 0 else 0
        total_key_value_pairs = sum(len(result.key_value_pairs) for result in processing_results)
        
        # Collect all unique keys across all files
        all_keys = set()
        for result in processing_results:
            all_keys.update(result.key_value_pairs.keys())
        
        summary_data = {
            'Metric': [
                'Total Files Processed',
                'Total Processing Time (seconds)',
                'Average Processing Time per File (seconds)',
                'Average Confidence Score',
                'Total Key-Value Pairs Extracted',
                'Average Key-Value Pairs per File',
                'Unique Fields Found',
                'Template Used',
                'Export Timestamp'
            ],
            'Value': [
                str(total_files),
                f"{total_processing_time:.2f}",
                f"{total_processing_time/total_files:.2f}" if total_files > 0 else "0.00",
                f"{avg_confidence:.2f}",
                str(total_key_value_pairs),
                f"{total_key_value_pairs/total_files:.1f}" if total_files > 0 else "0.0",
                str(len(all_keys)),
                template_used or 'None',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
        }
        
        df = pd.DataFrame(summary_data)
        df.to_excel(writer, sheet_name='Summary', index=False)
    
    def _create_template_analysis_sheet(self, writer, processing_results: List['ProcessingResult'], filenames: List[str], template_used: str):
        """Create template analysis sheet."""
        # Analyze template field coverage
        template_fields = set()
        for result in processing_results:
            if result.template_mapping:
                template_fields.update(result.template_mapping.keys())
        
        data = []
        for field in sorted(template_fields):
            found_count = 0
            not_found_count = 0
            
            for result in processing_results:
                if result.template_mapping and field in result.template_mapping:
                    if result.template_mapping[field] == 'found_in_document':
                        found_count += 1
                    else:
                        not_found_count += 1
                else:
                    not_found_count += 1
            
            coverage_percentage = (found_count / len(processing_results)) * 100 if processing_results else 0
            
            data.append({
                'Template_Field': field,
                'Found_Count': found_count,
                'Not_Found_Count': not_found_count,
                'Coverage_Percentage': f"{coverage_percentage:.1f}%"
            })
        
        if data:
            df = pd.DataFrame(data)
            df.to_excel(writer, sheet_name='Template Analysis', index=False)
        else:
            empty_df = pd.DataFrame(columns=['Template_Field', 'Found_Count', 'Not_Found_Count', 'Coverage_Percentage'])
            empty_df.to_excel(writer, sheet_name='Template Analysis', index=False)
    
    def get_export_filename(self, base_filename: str, template_used: Optional[str] = None, consolidated: bool = False) -> str:
        """Generate appropriate export filename."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if consolidated:
            prefix = f"consolidated_ocr_results_{timestamp}"
        else:
            # Clean the base filename
            clean_name = Path(base_filename).stem
            prefix = f"{clean_name}_ocr_results_{timestamp}"
        
        if template_used:
            template_clean = template_used.lower().replace(' ', '_')
            prefix = f"{prefix}_{template_clean}"
        
        return f"{prefix}.xlsx"
    
    def create_individual_excel(self, 
                               processed_data: Dict[str, Any],
                               include_raw_text: bool = True,
                               include_metadata: bool = True) -> bytes:
        """
        Create individual Excel file from processed data.
        
        Args:
            processed_data: Already processed OCR data
            include_raw_text: Whether to include raw OCR text
            include_metadata: Whether to include processing metadata
            
        Returns:
            Excel file as raw bytes
        """
        logger.info("Creating individual Excel from processed data")
        
        try:
            # Accept payloads where the actual data is nested under 'processed_data'
            if isinstance(processed_data, dict) and 'processed_data' in processed_data:
                processed_data = processed_data['processed_data']
            output = BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Sheet 1: Key-Value Pairs
                self._create_key_value_sheet_from_data(writer, processed_data)
                
                # Sheet 2: Raw Text (if requested)
                if include_raw_text and processed_data.get('raw_ocr_text'):
                    self._create_raw_text_sheet_from_data(writer, processed_data)
                
                # Sheet 3: Metadata (if requested)
                if include_metadata:
                    self._create_metadata_sheet_from_data(writer, processed_data)
                
                # Sheet 4: Template Mapping (if available)
                if processed_data.get('template_mapping'):
                    self._create_template_mapping_sheet_from_data(writer, processed_data)
            
            output.seek(0)
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Error creating individual Excel: {e}")
            raise
    
    def create_individual_excel_files(self, 
                                     batch_data: Dict[str, Any],
                                     include_raw_text: bool = True,
                                     include_metadata: bool = True) -> bytes:
        """
        Create individual Excel files for each document in batch data.
        
        Args:
            batch_data: Batch processed OCR data
            include_raw_text: Whether to include raw OCR text
            include_metadata: Whether to include processing metadata
            
        Returns:
            ZIP file containing individual Excel files as raw bytes
        """
        import zipfile
        
        logger.info("Creating individual Excel files from batch data")
        
        try:
            zip_buffer = BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                individual_results = batch_data.get('individual_results', [])
                
                for i, result in enumerate(individual_results):
                    # Create Excel file for this result
                    excel_buffer = self.create_individual_excel(
                        processed_data=result,
                        include_raw_text=include_raw_text,
                        include_metadata=include_metadata
                    )
                    
                    # Get filename for this result
                    # Prefer nested file_info.filename if available
                    filename = (
                        result.get('file_info', {}).get('filename')
                        or result.get('filename')
                        or f'document_{i+1}'
                    )
                    if not filename.endswith('.xlsx'):
                        filename = f"{filename}_extracted.xlsx"
                    
                    # Add to ZIP
                    zip_file.writestr(filename, excel_buffer)
            
            zip_buffer.seek(0)
            return zip_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error creating individual Excel files: {e}")
            raise
    
    def _create_key_value_sheet_from_data(self, writer, processed_data: Dict[str, Any]):
        """Create key-value pairs sheet from processed data."""
        # Accept alternate shapes if present
        key_value_pairs = processed_data.get('key_value_pairs')
        if not key_value_pairs and isinstance(processed_data.get('extraction_result'), dict):
            key_value_pairs = processed_data['extraction_result'].get('key_value_pairs', {})
        if key_value_pairs is None:
            key_value_pairs = {}
        
        if not key_value_pairs:
            # Create empty sheet
            df = pd.DataFrame({'Key': [], 'Value': []})
            df.to_excel(writer, sheet_name='Key-Value Pairs', index=False)
            return
        
        # Convert values to displayable strings
        rows = []
        for key, value in key_value_pairs.items():
            if isinstance(value, (dict, list)):
                safe_value = json.dumps(value, ensure_ascii=False)
            else:
                safe_value = "" if value is None else str(value)
            rows.append({'Key': key, 'Value': safe_value})
        df = pd.DataFrame(rows)
        
        df.to_excel(writer, sheet_name='Key-Value Pairs', index=False)
    
    def _create_raw_text_sheet_from_data(self, writer, processed_data: Dict[str, Any]):
        """Create raw text sheet from processed data."""
        raw_text = processed_data.get('raw_ocr_text', '')
        
        if not raw_text:
            df = pd.DataFrame({'Raw OCR Text': ['No text available']})
        else:
            df = pd.DataFrame({'Raw OCR Text': [raw_text]})
        
        df.to_excel(writer, sheet_name='Raw Text', index=False)
    
    def _create_metadata_sheet_from_data(self, writer, processed_data: Dict[str, Any]):
        """Create metadata sheet from processed data."""
        metadata = []
        
        # File info
        file_info = processed_data.get('file_info', {})
        metadata.append(['Filename', file_info.get('filename', 'Unknown')])
        # Compute MB if bytes present
        size_bytes = file_info.get('size_bytes')
        size_mb = (float(size_bytes) / (1024 * 1024)) if isinstance(size_bytes, (int, float)) else file_info.get('size_mb', 0)
        metadata.append(['File Size (MB)', round(size_mb, 3) if isinstance(size_mb, float) else size_mb])
        metadata.append(['Content Type', file_info.get('content_type', 'Unknown')])
        
        # Processing info
        processing_info = processed_data.get('processing_info', {})
        metadata.append(['Provider', processing_info.get('provider', 'Unknown')])
        metadata.append(['Processing Time (s)', processing_info.get('processing_time', 0)])
        metadata.append(['Pages Processed', processing_info.get('pages_processed', 0)])
        metadata.append(['Preprocessing Applied', processing_info.get('preprocessing_applied', False)])
        metadata.append(['Quality Enhancement', processing_info.get('quality_enhancement', False)])
        
        # Extraction info
        metadata.append(['Summary', processed_data.get('summary', 'No summary available')])
        metadata.append(['Confidence Score', processed_data.get('confidence_score', 0)])
        metadata.append(['Extraction Date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        
        # Create DataFrame
        df = pd.DataFrame(metadata, columns=['Field', 'Value'])
        df.to_excel(writer, sheet_name='Metadata', index=False)
    
    def _create_template_mapping_sheet_from_data(self, writer, processed_data: Dict[str, Any]):
        """Create template mapping sheet from processed data."""
        template_mapping = processed_data.get('template_mapping', {})
        
        if not template_mapping:
            df = pd.DataFrame({'Template Field': [], 'Status': []})
        else:
            df = pd.DataFrame([
                {'Template Field': field, 'Status': status}
                for field, status in template_mapping.items()
            ])
        
        df.to_excel(writer, sheet_name='Template Mapping', index=False)
