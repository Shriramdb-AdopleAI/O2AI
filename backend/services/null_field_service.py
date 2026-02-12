"""
Service for tracking null required fields in processed documents.
"""
import logging
from typing import Dict, Any, List
from models.database import SessionLocal, NullFieldTracking
from datetime import datetime

logger = logging.getLogger(__name__)

class NullFieldTrackingService:
    """Service for storing and querying null field tracking data."""
    
    # Define required fields mapping
    REQUIRED_FIELDS = {
        "Name (First, Middle, Last)": "name_is_null",
        "Date of Birth": "dob_is_null",
        "Member ID": "member_id_is_null",
        "Address": "address_is_null",
        "Gender": "gender_is_null",
        "Insurance ID": "insurance_id_is_null"
    }
    
    def store_null_fields(
        self,
        processing_id: str,
        tenant_id: str,
        filename: str,
        extracted_fields: Dict[str, Any]
    ) -> bool:
        """
        Store null field tracking data for a processed document.
        
        Args:
            processing_id: Unique processing ID
            tenant_id: Tenant identifier
            filename: Original filename
            extracted_fields: All extracted key-value pairs
            
        Returns:
            bool: True if successful, False otherwise
        """
        session = SessionLocal()
        try:
            logger.info("=" * 80)
            logger.info(f"STORING NULL FIELD TRACKING DATA")
            logger.info("=" * 80)
            logger.info(f"Processing ID: {processing_id}")
            logger.info(f"Filename: {filename}")
            
            # Check which required fields are null
            null_fields = {}
            null_field_names = []
            null_count = 0
            
            logger.info(f"\n--- CHECKING REQUIRED FIELDS ---")
            for field_name, db_column in self.REQUIRED_FIELDS.items():
                value = extracted_fields.get(field_name)
                # Check if value is None, empty string, or the string "None"
                is_null = (
                    value is None or 
                    value == "" or 
                    (isinstance(value, str) and value.strip().lower() in ["none", "null"])
                )
                
                null_fields[db_column] = is_null
                
                if is_null:
                    null_field_names.append(field_name)
                    null_count += 1
                    logger.warning(f"  ✗ [{field_name}]: None")
                else:
                    logger.info(f"  ✓ [{field_name}]: {value}")

            
            logger.info(f"\n--- NULL FIELDS SUMMARY ---")
            logger.info(f"  Total required fields: {len(self.REQUIRED_FIELDS)}")
            logger.info(f"  Null fields: {null_count}")
            if null_field_names:
                logger.warning(f"  Null field names: {', '.join(null_field_names)}")
            else:
                logger.info(f"  All required fields have values ✓")
            
            # Create database record
            tracking_record = NullFieldTracking(
                processing_id=processing_id,
                tenant_id=tenant_id,
                filename=filename,
                name_is_null=null_fields.get("name_is_null", False),
                dob_is_null=null_fields.get("dob_is_null", False),
                member_id_is_null=null_fields.get("member_id_is_null", False),
                address_is_null=null_fields.get("address_is_null", False),
                gender_is_null=null_fields.get("gender_is_null", False),
                insurance_id_is_null=null_fields.get("insurance_id_is_null", False),
                null_field_count=null_count,
                null_field_names=null_field_names,
                all_extracted_fields=extracted_fields
            )
            
            session.add(tracking_record)
            session.commit()
            
            logger.info(f"\n--- DATABASE STORAGE RESULT ---")
            logger.info(f"  ✓ Successfully stored null field tracking data")
            logger.info(f"  Table: null_field_tracking")
            logger.info(f"  Database ID: {tracking_record.id}")
            logger.info(f"  Processing ID: {processing_id}")
            logger.info(f"  Null field count: {null_count}")
            logger.info("=" * 80)
            
            return True
            
        except Exception as e:
            session.rollback()
            logger.error("=" * 80)
            logger.error(f"✗ FAILED TO STORE NULL FIELD TRACKING DATA")
            logger.error(f"  Error: {str(e)}")
            logger.error(f"  Processing ID: {processing_id}")
            logger.error(f"  Filename: {filename}")
            logger.error("=" * 80)
            import traceback
            logger.error(traceback.format_exc())
            return False
        finally:
            session.close()
    
    def get_documents_with_null_fields(self, tenant_id: str = None) -> List[NullFieldTracking]:
        """
        Get all documents that have null required fields.
        
        Args:
            tenant_id: Optional tenant ID to filter by
            
        Returns:
            List of NullFieldTracking records
        """
        session = SessionLocal()
        try:
            query = session.query(NullFieldTracking).filter(
                NullFieldTracking.null_field_count > 0
            )
            
            if tenant_id:
                query = query.filter(NullFieldTracking.tenant_id == tenant_id)
            
            results = query.order_by(NullFieldTracking.created_at.desc()).all()
            
            logger.info(f"✓ Found {len(results)} documents with null fields")
            return results
            
        except Exception as e:
            logger.error(f"✗ Error querying null field tracking: {e}")
            return []
        finally:
            session.close()
    
    def get_null_field_statistics(self, tenant_id: str = None) -> Dict[str, Any]:
        """
        Get statistics about null fields across all documents.
        
        Args:
            tenant_id: Optional tenant ID to filter by
            
        Returns:
            Dictionary with statistics
        """
        session = SessionLocal()
        try:
            query = session.query(NullFieldTracking)
            if tenant_id:
                query = query.filter(NullFieldTracking.tenant_id == tenant_id)
            
            all_records = query.all()
            total_documents = len(all_records)
            
            if total_documents == 0:
                return {"total_documents": 0}
            
            # Count null occurrences per field
            null_counts = {
                "Name": sum(1 for r in all_records if r.name_is_null),
                "Date of Birth": sum(1 for r in all_records if r.dob_is_null),
                "Member ID": sum(1 for r in all_records if r.member_id_is_null),
                "Address": sum(1 for r in all_records if r.address_is_null),
                "Gender": sum(1 for r in all_records if r.gender_is_null),
                "Insurance ID": sum(1 for r in all_records if r.insurance_id_is_null)
            }
            
            documents_with_nulls = sum(1 for r in all_records if r.null_field_count > 0)
            
            stats = {
                "total_documents": total_documents,
                "documents_with_null_fields": documents_with_nulls,
                "documents_with_all_fields": total_documents - documents_with_nulls,
                "null_field_counts": null_counts,
                "most_common_null_field": max(null_counts.items(), key=lambda x: x[1])[0] if any(null_counts.values()) else None
            }
            
            logger.info(f"✓ Null field statistics calculated for {total_documents} documents")
            return stats
            
        except Exception as e:
            logger.error(f"✗ Error calculating statistics: {e}")
            return {}
        finally:
            session.close()

# Create singleton instance
null_field_service = NullFieldTrackingService()
