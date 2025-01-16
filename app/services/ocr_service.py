"""
Enhanced OCR service module for high-accuracy text extraction from contract documents.
Implements Google Cloud Vision API integration with comprehensive error handling,
performance monitoring, and validation workflows.

Version: 1.0
"""

# External imports with version specifications
from google.cloud import vision  # google-cloud-vision v3.4.0
from tenacity import retry, stop_after_attempt  # tenacity v8.2.2
import asyncio  # built-in
import logging  # built-in
import time  # built-in
from typing import Dict, List, Optional, Any
import json
import base64
from datetime import datetime
import re  # Add re import at the top level
from pdf2image import convert_from_path  # pdf2image library for PDF conversion
import io
from PIL import Image

# Internal imports
from app.core.config import get_settings
from app.core.exceptions import (
    InternalServerException,
    OCRProcessingException,
    ValidationException
)
from app.schemas.ocr import (
    OCRRequest,
    OCRResponse,
    OCRValidationRequest,
    OCRValidationResponse,
    BatchOCRRequest,
    MIN_CONFIDENCE_SCORE,
    MAX_PROCESSING_TIME
)
from app.services.s3_service import S3Service

# Add additional tenacity imports
from tenacity import (
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

# Configure logging
logger = logging.getLogger(__name__)

# Constants for OCR processing
MAX_RETRIES = 3
CONFIDENCE_THRESHOLD = 0.95
BATCH_CONCURRENCY_LIMIT = 5

class OCRService:
    """
    Enhanced service class for OCR processing using Google Cloud Vision API
    with comprehensive error handling, retry mechanisms, and performance monitoring.
    """

    def __init__(self):
        """Initialize OCR service with required dependencies and configurations."""
        try:
            settings = get_settings()
            
            # Initialize Google Cloud Vision client
            self._vision_client = vision.ImageAnnotatorClient.from_service_account_info(
                json.loads(settings.GOOGLE_VISION_CREDENTIALS.get_secret_value())
            )
            
            # Initialize S3 service for document handling
            self._s3_service = S3Service()
            
            # Initialize processing cache
            self._processing_cache: Dict[str, Dict] = {}
            
            logger.info("OCR Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize OCR service: {str(e)}")
            raise InternalServerException("OCR service initialization failed")

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((OCRProcessingException, Exception)),
        before_sleep=before_sleep_log(logger, logging.INFO),
        after=after_log(logger, logging.INFO),
        reraise=True
    )
    async def process_document(self, request: OCRRequest) -> OCRResponse:
        """
        Process document using OCR with retry mechanism and performance monitoring.
        
        Args:
            request: OCR processing request
            
        Returns:
            OCRResponse: OCR processing results with confidence scores
            
        Raises:
            OCRProcessingException: If processing fails
        """
        start_time = time.time()
        temp_file_path = None
        
        try:
            # Download document from S3
            download_result = self._s3_service.download_file(
                s3_key=request.file_path,
                destination_path=f"/tmp/{request.contract_id}.pdf"
            )
            temp_file_path = download_result['destination']

            # Convert PDF to images
            images = convert_from_path(temp_file_path)
            if not images:
                raise OCRProcessingException("Failed to extract images from PDF")

            # Process all pages
            all_pages_data = []
            total_confidence = 0.0
            
            # Process first page immediately
            first_page = images[0]
            img_byte_arr = io.BytesIO()
            first_page.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            
            # Create vision image
            image = vision.Image(content=img_byte_arr)
            
            # Process with Google Vision API
            response = await asyncio.to_thread(
                self._vision_client.document_text_detection,
                image=image
            )
            
            if response.text_annotations:
                # Extract and structure text with confidence scoring
                extracted_data = self._process_text_annotations(response.text_annotations)
                page_confidence = self._calculate_confidence_score(response.text_annotations)
                
                # Add page number to extracted data
                extracted_data['page_number'] = 1
                all_pages_data.append(extracted_data)
                total_confidence += page_confidence

            # Check processing time after first page
            current_time = time.time() - start_time
            
            # Process remaining pages if time permits
            if current_time < MAX_PROCESSING_TIME and len(images) > 1:
                # Process remaining pages
                for page_num, page_image in enumerate(images[1:], start=2):
                    img_byte_arr = io.BytesIO()
                    page_image.save(img_byte_arr, format='PNG')
                    img_byte_arr = img_byte_arr.getvalue()
                    
                    image = vision.Image(content=img_byte_arr)
                    response = await asyncio.to_thread(
                        self._vision_client.document_text_detection,
                        image=image
                    )
                    
                    if response.text_annotations:
                        extracted_data = self._process_text_annotations(response.text_annotations)
                        page_confidence = self._calculate_confidence_score(response.text_annotations)
                        extracted_data['page_number'] = page_num
                        all_pages_data.append(extracted_data)
                        total_confidence += page_confidence
            
            if not all_pages_data:
                raise OCRProcessingException("No text detected in any page of the document")
            
            # Calculate average confidence score
            avg_confidence_score = total_confidence / len(all_pages_data)
            
            # Combine all pages data
            combined_data = self._combine_pages_data(all_pages_data)
            
            # Convert combined data to JSON string
            json_data = json.dumps(combined_data)
            
            # Prepare response
            ocr_response = OCRResponse(
                contract_id=request.contract_id,
                status="COMPLETED" if avg_confidence_score >= CONFIDENCE_THRESHOLD else "VALIDATION_REQUIRED",
                extracted_data=json_data,  # Use the JSON string
                confidence_score=avg_confidence_score,
                processing_time=min(time.time() - start_time, MAX_PROCESSING_TIME),
                performance_metrics={
                    "api_latency": time.time() - start_time,
                    "document_size": sum(len(page['full_text'].encode()) for page in all_pages_data),
                    "total_pages": len(images),
                    "processed_pages": len(all_pages_data),
                    "remaining_pages": len(images) - len(all_pages_data)
                }
            )
            
            # Cache results for validation
            self._cache_results(request.contract_id, ocr_response)
            
            # If there are remaining pages, process them in background
            if len(all_pages_data) < len(images):
                asyncio.create_task(self._process_remaining_pages(
                    request.contract_id,
                    images[len(all_pages_data):],
                    request.file_path
                ))
            
            return ocr_response
            
        except Exception as e:
            logger.error(f"OCR processing failed: {str(e)}")
            raise OCRProcessingException(f"Document processing failed: {str(e)}")
            
        finally:
            # Cleanup temporary files
            if temp_file_path:
                import os
                try:
                    os.remove(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temporary file: {str(e)}")

    async def _process_remaining_pages(
        self,
        contract_id: str,
        remaining_images: List[Image.Image],
        file_path: str
    ) -> None:
        """Process remaining pages in the background and update cache."""
        try:
            all_pages_data = []
            total_confidence = 0.0
            
            for page_num, page_image in enumerate(remaining_images, start=2):
                # Convert PIL Image to bytes
                img_byte_arr = io.BytesIO()
                page_image.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()
                
                # Create vision image
                image = vision.Image(content=img_byte_arr)
                
                # Process with Google Vision API
                response = await asyncio.to_thread(
                    self._vision_client.document_text_detection,
                    image=image
                )
                
                if response.text_annotations:
                    # Extract and structure text with confidence scoring
                    extracted_data = self._process_text_annotations(response.text_annotations)
                    page_confidence = self._calculate_confidence_score(response.text_annotations)
                    
                    # Add page number to extracted data
                    extracted_data['page_number'] = page_num
                    all_pages_data.append(extracted_data)
                    total_confidence += page_confidence
            
            if all_pages_data:
                # Update cache with additional pages
                cached_data = self._processing_cache.get(str(contract_id))
                if cached_data:
                    current_data = json.loads(cached_data["extracted_data"])
                    current_data["pages"].extend(all_pages_data)
                    
                    # Update confidence score
                    total_pages = len(current_data["pages"])
                    new_confidence = (cached_data["confidence_score"] + total_confidence) / total_pages
                    
                    # Create new OCR response with updated data
                    updated_response = OCRResponse(
                        contract_id=contract_id,
                        status="COMPLETED" if new_confidence >= CONFIDENCE_THRESHOLD else "VALIDATION_REQUIRED",
                        extracted_data=json.dumps(current_data),  # Ensure data is JSON serialized
                        confidence_score=new_confidence,
                        processing_time=MAX_PROCESSING_TIME,
                        performance_metrics={
                            "total_pages": total_pages,
                            "processed_pages": total_pages
                        }
                    )
                    
                    # Cache the updated response
                    self._cache_results(contract_id, updated_response)
        
        except Exception as e:
            logger.error(f"Background processing failed for contract {contract_id}: {str(e)}")

    async def process_batch(self, request: BatchOCRRequest) -> List[OCRResponse]:
        """
        Process multiple documents in batch with parallel execution.
        
        Args:
            request: Batch processing request
            
        Returns:
            List[OCRResponse]: Batch processing results
        """
        try:
            # Create processing tasks
            tasks = []
            for doc_request in request.documents:
                task = asyncio.create_task(self.process_document(doc_request))
                tasks.append(task)
            
            # Process in parallel with concurrency limit
            results = []
            for batch in self._batch_tasks(tasks, BATCH_CONCURRENCY_LIMIT):
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                results.extend(batch_results)
            
            # Handle partial failures
            processed_results = []
            for result in results:
                if isinstance(result, Exception):
                    processed_results.append(
                        OCRResponse(
                            contract_id=result.contract_id,
                            status="FAILED",
                            error_details={"message": str(result)}
                        )
                    )
                else:
                    processed_results.append(result)
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Batch processing failed: {str(e)}")
            raise OCRProcessingException(f"Batch processing failed: {str(e)}")

    async def validate_extracted_data(
        self,
        request: OCRValidationRequest
    ) -> OCRValidationResponse:
        """
        Validate and process corrected OCR data with business rules.
        
        Args:
            request: Validation request
            
        Returns:
            OCRValidationResponse: Validation results
        """
        try:
            # Retrieve cached results
            cached_data = self._processing_cache.get(str(request.contract_id))
            if not cached_data:
                raise ValidationException("No cached data found for validation")
            
            # Apply validation rules
            validation_result = self._validate_data(
                request.corrected_data,
                cached_data['extracted_data']
            )
            
            # Calculate validation confidence
            validation_confidence = self._calculate_validation_confidence(
                validation_result,
                cached_data['confidence_score']
            )
            
            return OCRValidationResponse(
                contract_id=request.contract_id,
                status="VALIDATED" if validation_confidence >= CONFIDENCE_THRESHOLD else "VALIDATION_REQUIRED",
                validated_data=validation_result,
                validation_metadata={
                    "original_confidence": cached_data['confidence_score'],
                    "validation_confidence": validation_confidence,
                    "validation_timestamp": datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            raise ValidationException(f"Data validation failed: {str(e)}")

    def _process_text_annotations(self, annotations: List) -> Dict[str, Any]:
        """Process and structure extracted text annotations."""
        full_text = annotations[0].description if annotations else ""
        
        structured_data = {
            "full_text": full_text,
            "blocks": []
        }
        
        # Process raw text blocks
        for annotation in annotations[1:]:
            block = {
                "text": annotation.description,
                "confidence": annotation.confidence,
                "bounds": self._get_bounds(annotation.bounding_poly),
                "locale": annotation.locale if hasattr(annotation, 'locale') else None
            }
            structured_data["blocks"].append(block)
        
        # Extract structured fields from full text
        parsed_data = self._parse_contract_fields(full_text)
        structured_data.update(parsed_data)
        
        return structured_data

    def _parse_contract_fields(self, text: str) -> Dict[str, Any]:
        """
        Parse required contract fields from extracted text.
        Supports various contract formats while maintaining high precision.
        """
        if not text:
            return {
                "contract_number": None,
                "parties": [],
                "payment_terms": [],
                "total_value": None,
                "effective_date": None,
                "expiration_date": None,
                "items": []
            }
        
        parsed_data = {
            "contract_number": None,
            "parties": [],
            "payment_terms": [],
            "total_value": None,
            "effective_date": None,
            "expiration_date": None,
            "items": []
        }

        # Extract contract number with more flexible patterns
        contract_patterns = [
            r"Contract\s*(?:No\.|Number|#|ID)?\s*[:.]?\s*((?:SAAS|CON|AGR|SER|CNT)-?\d{3,6}(?:-[A-Z0-9]+)?)",
            r"Contract\s*(?:No\.|Number|#|ID)?\s*[:.]?\s*([A-Z0-9]+-[A-Z0-9]+-\d{3,6})",
            r"Contract\s*(?:No\.|Number|#|ID)?\s*[:.]?\s*([A-Z0-9]{5,20})",
            r"Agreement\s*(?:No\.|Number|#|ID)?\s*[:.]?\s*([A-Z0-9-]{5,20})"
        ]
        for pattern in contract_patterns:
            if contract_match := re.search(pattern, text, re.IGNORECASE):
                parsed_data["contract_number"] = contract_match.group(1).strip()
                break

        # Extract party information with improved patterns
        party_sections = re.split(r'\n\s*\n', text)  # Split by double newlines to find sections
        
        # Simplified but comprehensive party extraction pattern
        party_pattern = r"(Provider|Client):\s*([^,]+),\s*a\s+([^,]+),\s*with\s+its\s+principal\s+place\s+of\s+business\s+at\s+([^\.]+)"
        
        for section in party_sections:
            if matches := re.finditer(party_pattern, section, re.IGNORECASE):
                for match in matches:
                    role, name, legal_entity, address = match.groups()
                    if name:
                        party_info = {
                            "name": name.strip(),
                            "role": role.lower(),
                            "legal_entity": legal_entity.strip(),
                            "address": address.strip()
                        }
                        parsed_data["parties"].append(party_info)

        # If no parties found with the main pattern, try alternative patterns
        if not parsed_data["parties"]:
            # Alternative pattern for agreements that start with "between" or "by and between"
            alt_party_pattern = r"between:\s*([^,]+),\s*a\s+([^,]+),\s*with\s+its\s+principal\s+place\s+of\s+business\s+at\s+([^\.]+)"
            
            if matches := re.finditer(alt_party_pattern, text, re.IGNORECASE):
                for i, match in enumerate(matches):
                    name, legal_entity, address = match.groups()
                    if name:
                        party_info = {
                            "name": name.strip(),
                            "role": "provider" if i == 0 else "client",
                            "legal_entity": legal_entity.strip(),
                            "address": address.strip()
                        }
                        parsed_data["parties"].append(party_info)

        # Extract dates with more format support
        date_patterns = {
            "effective_date": [
                r"(?:Effective|Start|Commencement)\s*Date\s*[:.]?\s*([A-Za-z]+\s+\d{1,2},?\s*\d{4})",
                r"(?:Effective|Start|Commencement)\s*[:.]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
                r"(?:Effective|Start|Commencement)\s*as\s*of\s*([A-Za-z]+\s+\d{1,2},?\s*\d{4})"
            ],
            "expiration_date": [
                r"(?:Expiration|End|Termination)\s*Date\s*[:.]?\s*([A-Za-z]+\s+\d{1,2},?\s*\d{4})",
                r"(?:Expiration|End|Termination)\s*[:.]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
                r"(?:Valid|Expires)\s*(?:until|through)\s*([A-Za-z]+\s+\d{1,2},?\s*\d{4})"
            ]
        }
        
        for field, patterns in date_patterns.items():
            for pattern in patterns:
                if date_match := re.search(pattern, text, re.IGNORECASE):
                    matched_date = date_match.group(1).strip()
                    parsed_data[field] = self._normalize_date(matched_date)
                    break

        # Extract payment terms with improved pattern
        payment_patterns = [
            r"Payment\s+Terms?.*?[:.]([^\n]+(?:\n(?!\n)[^\n]+)*)",
            r"Terms\s+of\s+Payment.*?[:.]([^\n]+(?:\n(?!\n)[^\n]+)*)",
            r"Payment\s+Schedule.*?[:.]([^\n]+(?:\n(?!\n)[^\n]+)*)"
        ]
        
        for pattern in payment_patterns:
            if payment_match := re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                payment_text = payment_match.group(1).strip()
                payment_lines = [line.strip() for line in payment_text.split('\n') if line.strip()]
                if payment_lines:
                    parsed_data["payment_terms"] = payment_lines
                    break

        # Extract total value with improved currency handling
        value_patterns = [
            r"Total\s+Contract\s+Value\s*:?\s*\$?\s*([\d,]+(?:\.\d{2})?)",
            r"Total\s+Contract\s+Value\s*:?\s*([\d,]+(?:\.\d{2})?)",
            r"Total\s+Value\s*:?\s*\$?\s*([\d,]+(?:\.\d{2})?)"
        ]
        
        for pattern in value_patterns:
            if value_match := re.search(pattern, text, re.IGNORECASE):
                try:
                    value_str = value_match.group(1).replace(',', '')
                    parsed_data["total_value"] = float(value_str)
                    break
                except (ValueError, TypeError):
                    continue

        # Extract service items with improved pattern
        items_section_patterns = [
            r"(?:Description\s+of\s+Services?)(?:\s*:?\s*\n?)([^#]+?)(?=\n\s*\d+\.|Client\s+Responsibilities|Provider\s+Responsibilities|$)",
            r"(?:Services?\s+Description)(?:\s*:?\s*\n?)([^#]+?)(?=\n\s*\d+\.|Client\s+Responsibilities|Provider\s+Responsibilities|$)",
            r"(?:Scope\s+of\s+Services?)(?:\s*:?\s*\n?)([^#]+?)(?=\n\s*\d+\.|Client\s+Responsibilities|Provider\s+Responsibilities|$)",
            r"(?:Services?\s+Provided)(?:\s*:?\s*\n?)([^#]+?)(?=\n\s*\d+\.|Client\s+Responsibilities|Provider\s+Responsibilities|$)"
        ]
        
        # Try to find items section first
        items_text = None
        for pattern in items_section_patterns:
            if section_match := re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                items_text = section_match.group(1).strip()
                break
        
        if items_text:
            # Try to extract platform/product name first
            platform_patterns = [
                r"(?:access\s+to\s+(?:the\s+)?)([\w\s]+?)(?:\s*\(.*?\))?(?:\s+via|\s+through|\s*$)",
                r"(?:provide.*?access\s+to\s+(?:the\s+)?)([\w\s]+?)(?:\s*\(.*?\))?(?:\s+via|\s+through|\s*$)",
                r"(?:provide\s+)(?:the\s+)?([\w\s]+?)(?:\s*\(.*?\))?(?:\s+service|\s+platform|\s+system)",
            ]
            
            platform_name = None
            platform_description = None
            
            # Try to find the platform name
            for pattern in platform_patterns:
                if platform_match := re.search(pattern, items_text, re.IGNORECASE):
                    platform_name = platform_match.group(1).strip()
                    # Get the full sentence containing the platform name as description
                    sentences = re.split(r'(?<=[.!?])\s+', items_text)
                    for sentence in sentences:
                        if platform_name in sentence:
                            platform_description = sentence.strip()
                            break
                    break
            
            if platform_name and platform_description:
                parsed_data["items"].append({
                    "name": platform_name,
                    "description": platform_description,
                    "quantity": None,
                    "unit_price": None
                })
            else:
                # Fallback: use the entire items text as description
                parsed_data["items"].append({
                    "name": "Service",
                    "description": items_text.strip(),
                    "quantity": None,
                    "unit_price": None
                })

        # If still no items found, try looking for inline service descriptions
        if not parsed_data["items"]:
            service_patterns = [
                r"(?:Provider\s+(?:shall|will|agrees\s+to)\s+provide)\s+([^\.]+?)(?=\.|$)",
                r"(?:Services?\s+includes?)\s+([^\.]+?)(?=\.|$)",
                r"(?:Provider\s+(?:shall|will|agrees\s+to)\s+deliver)\s+([^\.]+?)(?=\.|$)"
            ]
            
            for pattern in service_patterns:
                if service_match := re.search(pattern, text, re.IGNORECASE):
                    description = service_match.group(1).strip()
                    if description:
                        # Try to extract platform/product name from description
                        name_match = re.search(r"(?:the\s+)?([\w\s]+?)(?:\s*\(.*?\))?(?:\s+via|\s+through|\s+platform|\s+service|\s*$)", description)
                        name = name_match.group(1).strip() if name_match else "Service"
                        
                        parsed_data["items"].append({
                            "name": name,
                            "description": description,
                            "quantity": None,
                            "unit_price": None
                        })
                        break

        return parsed_data

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize various date formats to a standard format."""
        if not date_str:
            return None
            
        # Remove any extra whitespace and commas
        date_str = re.sub(r'\s+', ' ', date_str.strip().replace(',', ''))
        
        try:
            # Try parsing different formats
            for fmt in [
                '%B %d %Y',      # January 1 2025
                '%d/%m/%Y',      # 01/01/2025
                '%Y/%m/%d',      # 2025/01/01
                '%Y-%m-%d',      # 2025-01-01
                '%d-%m-%Y'       # 01-01-2025
            ]:
                try:
                    return datetime.strptime(date_str, fmt).strftime('%B %d, %Y')
                except ValueError:
                    continue
        except Exception:
            return date_str
        
        return date_str

    def _clean_payment_terms(self, terms: str) -> Optional[str]:
        """Clean and normalize payment terms text."""
        if not terms:
            return None
            
        # Remove extra whitespace and normalize line breaks
        terms = re.sub(r'\s+', ' ', terms.strip())
        # Remove bullet points and other common artifacts
        terms = re.sub(r'[•·]', '', terms)
        return terms

    def _extract_address(self, text: str) -> Optional[str]:
        """Extract address from party information if available."""
        if not text:
            return None
            
        address_pattern = r"(?:located|based|place of business|address)[^,]*?at\s+([^\.]+)"
        if address_match := re.search(address_pattern, text, re.IGNORECASE):
            matched_text = address_match.group(1)
            return matched_text.strip() if matched_text else None
        return None

    def _calculate_confidence_score(self, annotations: List) -> float:
        """Calculate overall confidence score for extracted text."""
        if not annotations:
            return 0.0
            
        confidences = [ann.confidence for ann in annotations if hasattr(ann, 'confidence')]
        return sum(confidences) / len(confidences) if confidences else 0.0

    def _get_bounds(self, bounding_poly) -> Dict[str, int]:
        """Extract bounding box coordinates."""
        return {
            "left": min(vertex.x for vertex in bounding_poly.vertices),
            "top": min(vertex.y for vertex in bounding_poly.vertices),
            "right": max(vertex.x for vertex in bounding_poly.vertices),
            "bottom": max(vertex.y for vertex in bounding_poly.vertices)
        }

    def _cache_results(self, contract_id: str, response: OCRResponse) -> None:
        """Cache processing results for validation."""
        self._processing_cache[str(contract_id)] = {
            "extracted_data": response.extracted_data,
            "confidence_score": response.confidence_score,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _batch_tasks(self, tasks: List, batch_size: int):
        """Split tasks into batches for controlled concurrency."""
        for i in range(0, len(tasks), batch_size):
            yield tasks[i:i + batch_size]

    def _validate_data(
        self,
        corrected_data: Dict,
        original_data: Dict
    ) -> Dict[str, Any]:
        """Apply validation rules to corrected data."""
        validation_result = corrected_data.copy()
        
        # Track changes from original
        validation_result["_validation"] = {
            "changes": self._track_changes(original_data, corrected_data),
            "original_blocks": len(original_data.get("blocks", [])),
            "corrected_blocks": len(corrected_data.get("blocks", []))
        }
        
        return validation_result

    def _track_changes(self, original: Dict, corrected: Dict) -> Dict[str, Any]:
        """Track changes between original and corrected data."""
        changes = {
            "modified_blocks": [],
            "added_blocks": [],
            "removed_blocks": []
        }
        
        original_blocks = {b["text"]: b for b in original.get("blocks", [])}
        corrected_blocks = {b["text"]: b for b in corrected.get("blocks", [])}
        
        for text, block in corrected_blocks.items():
            if text in original_blocks:
                if block != original_blocks[text]:
                    changes["modified_blocks"].append(text)
            else:
                changes["added_blocks"].append(text)
                
        for text in original_blocks:
            if text not in corrected_blocks:
                changes["removed_blocks"].append(text)
                
        return changes

    def _calculate_validation_confidence(
        self,
        validation_result: Dict,
        original_confidence: float
    ) -> float:
        """Calculate confidence score after validation."""
        changes = validation_result.get("_validation", {}).get("changes", {})
        change_penalty = (
            len(changes.get("modified_blocks", [])) +
            len(changes.get("added_blocks", [])) +
            len(changes.get("removed_blocks", []))
        ) * 0.05
        
        return max(0.0, min(1.0, original_confidence - change_penalty))

    def _combine_pages_data(self, pages_data: List[Dict]) -> Dict[str, Any]:
        """
        Combine extracted data from multiple pages into a single coherent structure.
        
        Args:
            pages_data: List of extracted data from each page
            
        Returns:
            Combined data structure with information from all pages
        """
        if not pages_data:
            return {}
            
        # Initialize combined structure
        combined = {
            "pages": pages_data,  # Keep individual page data
            "full_text": "\n\n".join(page['full_text'] for page in pages_data),
            "blocks": [],
            "contract_number": None,
            "parties": [],
            "payment_terms": None,
            "total_value": None,
            "effective_date": None,
            "expiration_date": None,
            "items": []  # Initialize items list
        }
        
        # Combine blocks from all pages
        for page in pages_data:
            for block in page.get('blocks', []):
                # Add page number to block data
                block['page_number'] = page.get('page_number')
                combined['blocks'].append(block)
        
        # Use the first non-null value for single-value fields
        for field in ['contract_number', 'total_value', 'effective_date', 'expiration_date']:
            for page in pages_data:
                if page.get(field):
                    combined[field] = page[field]
                    break
        
        # Combine parties from all pages, avoiding duplicates
        seen_parties = set()
        for page in pages_data:
            for party in page.get('parties', []):
                party_key = f"{party['name']}:{party['role']}"
                if party_key not in seen_parties:
                    seen_parties.add(party_key)
                    combined['parties'].append(party)
        
        # Combine payment terms
        all_payment_terms = []
        for page in pages_data:
            if page.get('payment_terms'):
                all_payment_terms.extend(page['payment_terms'])
        if all_payment_terms:
            combined['payment_terms'] = all_payment_terms

        # Process items using the full text for better context
        combined_items = self._parse_contract_fields(combined['full_text']).get('items', [])
        if combined_items:
            combined['items'] = combined_items
        else:
            # Fallback: try to find items in individual pages
            for page in pages_data:
                if page.get('items'):
                    combined['items'].extend(page['items'])
        
        return combined