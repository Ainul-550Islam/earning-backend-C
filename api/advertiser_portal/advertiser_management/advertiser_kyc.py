"""
Advertiser KYC (Know Your Customer) Management

This module handles comprehensive KYC processes, compliance checks,
and regulatory requirements for advertisers.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID
import json
import re

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.advertiser_model import Advertiser, AdvertiserVerification
from ..database_models.audit_model import ComplianceReport
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserKYCService:
    """Service for managing advertiser KYC processes."""
    
    @staticmethod
    def initiate_kyc_process(advertiser_id: UUID, kyc_level: str = 'basic',
                            initiated_by: Optional[User] = None) -> Dict[str, Any]:
        """Initiate KYC process for advertiser."""
        try:
            advertiser = AdvertiserKYCService.get_advertiser(advertiser_id)
            
            # Check if KYC already exists
            existing_kyc = ComplianceCheck.objects.filter(
                advertiser=advertiser,
                check_type='kyc',
                status__in=['pending', 'in_review']
            ).first()
            
            if existing_kyc:
                raise AdvertiserValidationError(f"KYC process already in progress: {existing_kyc.id}")
            
            with transaction.atomic():
                # Create KYC check record
                kyc_check = ComplianceCheck.objects.create(
                    advertiser=advertiser,
                    check_type='kyc',
                    check_level=kyc_level,
                    status=ComplianceStatusEnum.PENDING.value,
                    check_data={
                        'kyc_level': kyc_level,
                        'required_documents': AdvertiserKYCService._get_required_documents(kyc_level),
                        'checklist': AdvertiserKYCService._get_kyc_checklist(kyc_level),
                        'risk_score': 0,
                        'compliance_score': 0
                    },
                    performed_by=initiated_by,
                    started_at=timezone.now(),
                    expires_at=timezone.now() + timezone.timedelta(days=90)
                )
                
                # Generate KYC reference number
                kyc_reference = AdvertiserKYCService._generate_kyc_reference(advertiser, kyc_level)
                kyc_check.reference_number = kyc_reference
                kyc_check.save(update_fields=['reference_number'])
                
                # Send KYC initiation notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=initiated_by,
                    title='KYC Process Initiated',
                    message=f'Your {kyc_level} KYC process has been initiated. Reference: {kyc_reference}',
                    notification_type='compliance',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                # Log initiation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='initiate_kyc',
                    object_type='ComplianceCheck',
                    object_id=str(kyc_check.id),
                    user=initiated_by,
                    advertiser=advertiser,
                    description=f"Initiated {kyc_level} KYC process"
                )
                
                return {
                    'kyc_id': str(kyc_check.id),
                    'reference_number': kyc_reference,
                    'kyc_level': kyc_level,
                    'status': kyc_check.status,
                    'required_documents': kyc_check.check_data.get('required_documents', []),
                    'checklist': kyc_check.check_data.get('checklist', [])
                }
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error initiating KYC process {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to initiate KYC process: {str(e)}")
    
    @staticmethod
    def submit_kyc_documents(kyc_id: UUID, documents: List[Dict[str, Any]],
                             submitted_by: Optional[User] = None) -> bool:
        """Submit KYC documents."""
        try:
            kyc_check = AdvertiserKYCService.get_kyc_check(kyc_id)
            
            if kyc_check.status not in ['pending', 'additional_info_required']:
                raise AdvertiserValidationError(f"Cannot submit documents for KYC in status: {kyc_check.status}")
            
            with transaction.atomic():
                # Process and validate documents
                processed_documents = []
                validation_results = []
                
                for doc_data in documents:
                    # Validate document
                    validation_result = AdvertiserKYCService._validate_kyc_document(doc_data, kyc_check.check_level)
                    validation_results.append(validation_result)
                    
                    if validation_result['valid']:
                        # Process document
                        processed_doc = AdvertiserKYCService._process_kyc_document(doc_data)
                        processed_documents.append(processed_doc)
                    else:
                        raise AdvertiserValidationError(f"Invalid document: {validation_result['error']}")
                
                # Update KYC check
                check_data = kyc_check.check_data
                check_data['submitted_documents'] = processed_documents
                check_data['document_validation'] = validation_results
                kyc_check.check_data = check_data
                kyc_check.status = ComplianceStatusEnum.SUBMITTED.value
                kyc_check.submitted_at = timezone.now()
                kyc_check.save(update_fields=['check_data', 'status', 'submitted_at'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=kyc_check.advertiser,
                    user=submitted_by,
                    title='KYC Documents Submitted',
                    message=f'Your KYC documents have been submitted for review.',
                    notification_type='compliance',
                    priority='medium',
                    channels=['in_app']
                )
                
                # Log submission
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='submit_kyc_documents',
                    object_type='ComplianceCheck',
                    object_id=str(kyc_check.id),
                    user=submitted_by,
                    advertiser=kyc_check.advertiser,
                    description="Submitted KYC documents"
                )
                
                return True
                
        except ComplianceCheck.DoesNotExist:
            raise AdvertiserNotFoundError(f"KYC check {kyc_id} not found")
        except Exception as e:
            logger.error(f"Error submitting KYC documents {kyc_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to submit KYC documents: {str(e)}")
    
    @staticmethod
    def perform_kyc_checks(kyc_id: UUID, performed_by: Optional[User] = None) -> Dict[str, Any]:
        """Perform automated KYC checks."""
        try:
            kyc_check = AdvertiserKYCService.get_kyc_check(kyc_id)
            
            if kyc_check.status != 'submitted':
                raise AdvertiserValidationError(f"KYC must be submitted before performing checks")
            
            with transaction.atomic():
                # Update status to in review
                kyc_check.status = ComplianceStatusEnum.IN_REVIEW.value
                kyc_check.review_started_at = timezone.now()
                kyc_check.save(update_fields=['status', 'review_started_at'])
                
                # Perform various KYC checks
                check_results = AdvertiserKYCService._perform_all_kyc_checks(kyc_check)
                
                # Calculate risk and compliance scores
                risk_score = AdvertiserKYCService._calculate_risk_score(check_results)
                compliance_score = AdvertiserKYCService._calculate_compliance_score(check_results)
                
                # Update check data
                check_data = kyc_check.check_data
                check_data['check_results'] = check_results
                check_data['risk_score'] = risk_score
                check_data['compliance_score'] = compliance_score
                check_data['checks_performed_at'] = timezone.now().isoformat()
                kyc_check.check_data = check_data
                
                # Determine status based on scores
                if risk_score >= 70 or compliance_score < 50:
                    kyc_check.status = ComplianceStatusEnum.REJECTED.value
                    kyc_check.rejected_at = timezone.now()
                elif risk_score >= 40 or compliance_score < 70:
                    kyc_check.status = ComplianceStatusEnum.ADDITIONAL_INFO_REQUIRED.value
                else:
                    kyc_check.status = ComplianceStatusEnum.APPROVED.value
                    kyc_check.approved_at = timezone.now()
                
                kyc_check.performed_by = performed_by
                kyc_check.completed_at = timezone.now()
                kyc_check.save(update_fields=['check_data', 'status', 'performed_by', 'completed_at', 'rejected_at', 'approved_at'])
                
                # Update advertiser compliance status
                if kyc_check.status == 'approved':
                    kyc_check.advertiser.compliance_level = kyc_check.check_level
                    kyc_check.advertiser.compliance_verified_at = timezone.now()
                    kyc_check.advertiser.save(update_fields=['compliance_level', 'compliance_verified_at'])
                
                # Send notification
                status_messages = {
                    'approved': 'Your KYC has been approved successfully.',
                    'rejected': 'Your KYC has been rejected. Please contact support.',
                    'additional_info_required': 'Additional information is required for your KYC.'
                }
                
                Notification.objects.create(
                    advertiser=kyc_check.advertiser,
                    user=kyc_check.advertiser.user,
                    title='KYC Check Completed',
                    message=status_messages.get(kyc_check.status, 'KYC check completed.'),
                    notification_type='compliance',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                return {
                    'kyc_id': str(kyc_id),
                    'status': kyc_check.status,
                    'risk_score': risk_score,
                    'compliance_score': compliance_score,
                    'check_results': check_results
                }
                
        except ComplianceCheck.DoesNotExist:
            raise AdvertiserNotFoundError(f"KYC check {kyc_id} not found")
        except Exception as e:
            logger.error(f"Error performing KYC checks {kyc_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to perform KYC checks: {str(e)}")
    
    @staticmethod
    def get_kyc_status(advertiser_id: UUID) -> Dict[str, Any]:
        """Get KYC status for advertiser."""
        try:
            advertiser = AdvertiserKYCService.get_advertiser(advertiser_id)
            
            # Get latest KYC check
            latest_kyc = ComplianceCheck.objects.filter(
                advertiser=advertiser,
                check_type='kyc'
            ).order_by('-created_at').first()
            
            if not latest_kyc:
                return {
                    'status': 'not_initiated',
                    'compliance_level': 'none',
                    'message': 'No KYC process initiated'
                }
            
            return {
                'kyc_id': str(latest_kyc.id),
                'reference_number': latest_kyc.reference_number,
                'kyc_level': latest_kyc.check_level,
                'status': latest_kyc.status,
                'risk_score': latest_kyc.check_data.get('risk_score', 0),
                'compliance_score': latest_kyc.check_data.get('compliance_score', 0),
                'submitted_at': latest_kyc.submitted_at.isoformat() if latest_kyc.submitted_at else None,
                'completed_at': latest_kyc.completed_at.isoformat() if latest_kyc.completed_at else None,
                'expires_at': latest_kyc.expires_at.isoformat() if latest_kyc.expires_at else None,
                'compliance_level': advertiser.compliance_level,
                'compliance_verified_at': advertiser.compliance_verified_at.isoformat() if advertiser.compliance_verified_at else None
            }
            
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error getting KYC status {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get KYC status: {str(e)}")
    
    @staticmethod
    def get_kyc_checklist(kyc_level: str) -> Dict[str, Any]:
        """Get KYC checklist for specified level."""
        try:
            checklists = {
                'basic': {
                    'identity_verification': {
                        'required': True,
                        'description': 'Verify government-issued ID',
                        'documents': ['passport', 'driver_license', 'national_id']
                    },
                    'address_verification': {
                        'required': True,
                        'description': 'Verify residential address',
                        'documents': ['utility_bill', 'bank_statement', 'rental_agreement']
                    },
                    'business_verification': {
                        'required': False,
                        'description': 'Verify business registration',
                        'documents': ['business_license', 'certificate_of_incorporation']
                    }
                },
                'standard': {
                    'identity_verification': {
                        'required': True,
                        'description': 'Verify government-issued ID',
                        'documents': ['passport', 'driver_license', 'national_id']
                    },
                    'address_verification': {
                        'required': True,
                        'description': 'Verify residential address',
                        'documents': ['utility_bill', 'bank_statement', 'rental_agreement']
                    },
                    'business_verification': {
                        'required': True,
                        'description': 'Verify business registration',
                        'documents': ['business_license', 'certificate_of_incorporation', 'tax_certificate']
                    },
                    'financial_verification': {
                        'required': True,
                        'description': 'Verify financial standing',
                        'documents': ['bank_statement', 'tax_returns', 'financial_statement']
                    },
                    'source_of_funds': {
                        'required': True,
                        'description': 'Verify source of funds',
                        'documents': ['salary_statement', 'investment_statement', 'loan_documentation']
                    }
                },
                'enhanced': {
                    'identity_verification': {
                        'required': True,
                        'description': 'Verify government-issued ID',
                        'documents': ['passport', 'driver_license', 'national_id']
                    },
                    'address_verification': {
                        'required': True,
                        'description': 'Verify residential address',
                        'documents': ['utility_bill', 'bank_statement', 'rental_agreement']
                    },
                    'business_verification': {
                        'required': True,
                        'description': 'Verify business registration',
                        'documents': ['business_license', 'certificate_of_incorporation', 'tax_certificate']
                    },
                    'financial_verification': {
                        'required': True,
                        'description': 'Verify financial standing',
                        'documents': ['bank_statement', 'tax_returns', 'financial_statement']
                    },
                    'source_of_funds': {
                        'required': True,
                        'description': 'Verify source of funds',
                        'documents': ['salary_statement', 'investment_statement', 'loan_documentation']
                    },
                    'beneficial_ownership': {
                        'required': True,
                        'description': 'Verify beneficial ownership',
                        'documents': ['shareholder_register', 'ownership_structure', 'director_declaration']
                    },
                    'political_exposure': {
                        'required': True,
                        'description': 'Check political exposure',
                        'documents': ['pep_declaration', 'political_affiliation_disclosure']
                    },
                    'sanctions_screening': {
                        'required': True,
                        'description': 'Screen against sanctions lists',
                        'documents': ['sanctions_declaration', 'compliance_certificate']
                    }
                }
            }
            
            return checklists.get(kyc_level, {})
            
        except Exception as e:
            logger.error(f"Error getting KYC checklist {kyc_level}: {str(e)}")
            return {}
    
    @staticmethod
    def _get_required_documents(kyc_level: str) -> List[str]:
        """Get required documents for KYC level."""
        checklist = AdvertiserKYCService.get_kyc_checklist(kyc_level)
        required_docs = []
        
        for check_name, check_info in checklist.items():
            if check_info.get('required', False):
                required_docs.extend(check_info.get('documents', []))
        
        return list(set(required_docs))  # Remove duplicates
    
    @staticmethod
    def _get_kyc_checklist(kyc_level: str) -> List[str]:
        """Get KYC checklist items."""
        checklist = AdvertiserKYCService.get_kyc_checklist(kyc_level)
        return list(checklist.keys())
    
    @staticmethod
    def _generate_kyc_reference(advertiser: Advertiser, kyc_level: str) -> str:
        """Generate KYC reference number."""
        timestamp = timezone.now().strftime('%Y%m%d')
        return f"KYC-{kyc_level.upper()}-{advertiser.id.hex[:8]}-{timestamp}"
    
    @staticmethod
    def _validate_kyc_document(document: Dict[str, Any], kyc_level: str) -> Dict[str, Any]:
        """Validate KYC document."""
        try:
            file = document.get('file')
            document_type = document.get('document_type')
            
            if not file:
                return {'valid': False, 'error': 'No file provided'}
            
            if not document_type:
                return {'valid': False, 'error': 'Document type not specified'}
            
            # Check file size
            max_size = 10 * 1024 * 1024  # 10MB
            if file.size > max_size:
                return {'valid': False, 'error': 'File too large (max 10MB)'}
            
            # Check file type
            allowed_types = ['pdf', 'jpg', 'jpeg', 'png']
            file_ext = file.name.split('.')[-1].lower() if '.' in file.name else ''
            if file_ext not in allowed_types:
                return {'valid': False, 'error': f'Invalid file type. Allowed: {", ".join(allowed_types)}'}
            
            # Validate document type against required documents
            required_docs = AdvertiserKYCService._get_required_documents(kyc_level)
            if document_type not in required_docs:
                return {'valid': False, 'error': f'Document type not required for {kyc_level} KYC'}
            
            return {'valid': True, 'error': None}
            
        except Exception as e:
            logger.error(f"Error validating KYC document: {str(e)}")
            return {'valid': False, 'error': 'Validation error occurred'}
    
    @staticmethod
    def _process_kyc_document(document: Dict[str, Any]) -> Dict[str, Any]:
        """Process KYC document."""
        try:
            file = document.get('file')
            document_type = document.get('document_type')
            description = document.get('description', '')
            
            # Save file (implementation would go here)
            # For now, return mock data
            return {
                'document_id': str(uuid.uuid4()),
                'document_type': document_type,
                'file_name': file.name,
                'file_size': file.size,
                'file_path': f'/kyc_documents/{file.name}',
                'description': description,
                'uploaded_at': timezone.now().isoformat(),
                'status': 'uploaded'
            }
            
        except Exception as e:
            logger.error(f"Error processing KYC document: {str(e)}")
            raise AdvertiserServiceError(f"Failed to process KYC document: {str(e)}")
    
    @staticmethod
    def _perform_all_kyc_checks(kyc_check: "ComplianceCheck") -> Dict[str, Any]:
        """Perform all KYC checks."""
        try:
            advertiser = kyc_check.advertiser
            check_results = {}
            
            # Identity verification check
            check_results['identity_verification'] = AdvertiserKYCService._check_identity_verification(advertiser)
            
            # Address verification check
            check_results['address_verification'] = AdvertiserKYCService._check_address_verification(advertiser)
            
            # Business verification check
            check_results['business_verification'] = AdvertiserKYCService._check_business_verification(advertiser)
            
            # Financial verification check
            check_results['financial_verification'] = AdvertiserKYCService._check_financial_verification(advertiser)
            
            # Source of funds check
            check_results['source_of_funds'] = AdvertiserKYCService._check_source_of_funds(advertiser)
            
            # Beneficial ownership check (for enhanced KYC)
            if kyc_check.check_level == 'enhanced':
                check_results['beneficial_ownership'] = AdvertiserKYCService._check_beneficial_ownership(advertiser)
                check_results['political_exposure'] = AdvertiserKYCService._check_political_exposure(advertiser)
                check_results['sanctions_screening'] = AdvertiserKYCService._check_sanctions_screening(advertiser)
            
            return check_results
            
        except Exception as e:
            logger.error(f"Error performing KYC checks: {str(e)}")
            return {}
    
    @staticmethod
    def _check_identity_verification(advertiser: Advertiser) -> Dict[str, Any]:
        """Check identity verification."""
        try:
            # Mock implementation - would integrate with identity verification service
            return {
                'status': 'passed',
                'score': 85,
                'details': {
                    'name_match': True,
                    'document_authentic': True,
                    'expiry_check': True,
                    'duplicate_check': False
                },
                'message': 'Identity verified successfully'
            }
        except Exception as e:
            logger.error(f"Error checking identity verification: {str(e)}")
            return {'status': 'failed', 'score': 0, 'details': {}, 'message': 'Identity verification failed'}
    
    @staticmethod
    def _check_address_verification(advertiser: Advertiser) -> Dict[str, Any]:
        """Check address verification."""
        try:
            # Mock implementation - would integrate with address verification service
            return {
                'status': 'passed',
                'score': 90,
                'details': {
                    'address_match': True,
                    'geocode_valid': True,
                    'postal_code_valid': True,
                    'residence_confirmed': True
                },
                'message': 'Address verified successfully'
            }
        except Exception as e:
            logger.error(f"Error checking address verification: {str(e)}")
            return {'status': 'failed', 'score': 0, 'details': {}, 'message': 'Address verification failed'}
    
    @staticmethod
    def _check_business_verification(advertiser: Advertiser) -> Dict[str, Any]:
        """Check business verification."""
        try:
            # Mock implementation - would integrate with business verification service
            return {
                'status': 'passed',
                'score': 88,
                'details': {
                    'company_registered': True,
                    'license_valid': True,
                    'tax_compliant': True,
                    'business_active': True
                },
                'message': 'Business verified successfully'
            }
        except Exception as e:
            logger.error(f"Error checking business verification: {str(e)}")
            return {'status': 'failed', 'score': 0, 'details': {}, 'message': 'Business verification failed'}
    
    @staticmethod
    def _check_financial_verification(advertiser: Advertiser) -> Dict[str, Any]:
        """Check financial verification."""
        try:
            # Mock implementation - would integrate with financial verification service
            return {
                'status': 'passed',
                'score': 75,
                'details': {
                    'credit_check': True,
                    'income_verification': True,
                    'bank_account_valid': True,
                    'financial_stable': True
                },
                'message': 'Financial verification passed'
            }
        except Exception as e:
            logger.error(f"Error checking financial verification: {str(e)}")
            return {'status': 'failed', 'score': 0, 'details': {}, 'message': 'Financial verification failed'}
    
    @staticmethod
    def _check_source_of_funds(advertiser: Advertiser) -> Dict[str, Any]:
        """Check source of funds."""
        try:
            # Mock implementation - would integrate with source of funds verification
            return {
                'status': 'passed',
                'score': 80,
                'details': {
                    'funds_legitimate': True,
                    'source_documented': True,
                    'amount_reasonable': True,
                    'risk_level': 'low'
                },
                'message': 'Source of funds verified'
            }
        except Exception as e:
            logger.error(f"Error checking source of funds: {str(e)}")
            return {'status': 'failed', 'score': 0, 'details': {}, 'message': 'Source of funds verification failed'}
    
    @staticmethod
    def _check_beneficial_ownership(advertiser: Advertiser) -> Dict[str, Any]:
        """Check beneficial ownership."""
        try:
            # Mock implementation - would integrate with beneficial ownership verification
            return {
                'status': 'passed',
                'score': 92,
                'details': {
                    'ownership_disclosed': True,
                    'beneficial_owners_identified': True,
                    'ownership_structure_valid': True,
                    'no_suspicious_ownership': True
                },
                'message': 'Beneficial ownership verified'
            }
        except Exception as e:
            logger.error(f"Error checking beneficial ownership: {str(e)}")
            return {'status': 'failed', 'score': 0, 'details': {}, 'message': 'Beneficial ownership verification failed'}
    
    @staticmethod
    def _check_political_exposure(advertiser: Advertiser) -> Dict[str, Any]:
        """Check political exposure."""
        try:
            # Mock implementation - would integrate with PEP screening service
            return {
                'status': 'passed',
                'score': 95,
                'details': {
                    'not_pep': True,
                    'no_political_connections': True,
                    'no_sanctions': True,
                    'low_risk_profile': True
                },
                'message': 'No political exposure detected'
            }
        except Exception as e:
            logger.error(f"Error checking political exposure: {str(e)}")
            return {'status': 'failed', 'score': 0, 'details': {}, 'message': 'Political exposure check failed'}
    
    @staticmethod
    def _check_sanctions_screening(advertiser: Advertiser) -> Dict[str, Any]:
        """Check sanctions screening."""
        try:
            # Mock implementation - would integrate with sanctions screening service
            return {
                'status': 'passed',
                'score': 98,
                'details': {
                    'not_sanctioned': True,
                    'not_on_watchlist': True,
                    'no_adverse_media': True,
                    'clean_record': True
                },
                'message': 'Sanctions screening passed'
            }
        except Exception as e:
            logger.error(f"Error checking sanctions screening: {str(e)}")
            return {'status': 'failed', 'score': 0, 'details': {}, 'message': 'Sanctions screening failed'}
    
    @staticmethod
    def _calculate_risk_score(check_results: Dict[str, Any]) -> float:
        """Calculate overall risk score."""
        try:
            if not check_results:
                return 100  # High risk if no checks performed
            
            total_score = 0
            total_checks = 0
            
            for check_name, result in check_results.items():
                if isinstance(result, dict) and 'score' in result:
                    total_score += result['score']
                    total_checks += 1
            
            if total_checks == 0:
                return 100
            
            average_score = total_score / total_checks
            risk_score = 100 - average_score  # Convert to risk score (lower is better)
            
            return round(risk_score, 2)
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {str(e)}")
            return 100  # High risk on error
    
    @staticmethod
    def _calculate_compliance_score(check_results: Dict[str, Any]) -> float:
        """Calculate overall compliance score."""
        try:
            if not check_results:
                return 0  # No compliance score if no checks performed
            
            total_score = 0
            total_checks = 0
            
            for check_name, result in check_results.items():
                if isinstance(result, dict) and 'score' in result:
                    total_score += result['score']
                    total_checks += 1
            
            if total_checks == 0:
                return 0
            
            average_score = total_score / total_checks
            
            return round(average_score, 2)
            
        except Exception as e:
            logger.error(f"Error calculating compliance score: {str(e)}")
            return 0  # No compliance score on error
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def get_kyc_check(kyc_id: UUID) -> "ComplianceCheck":
        """Get KYC check by ID."""
        try:
            return ComplianceCheck.objects.get(id=kyc_id, check_type='kyc')
        except ComplianceCheck.DoesNotExist:
            raise AdvertiserNotFoundError(f"KYC check {kyc_id} not found")
    
    @staticmethod
    def get_kyc_statistics() -> Dict[str, Any]:
        """Get KYC statistics."""
        try:
            total_kyc = ComplianceCheck.objects.filter(check_type='kyc').count()
            pending_kyc = ComplianceCheck.objects.filter(check_type='kyc', status='pending').count()
            submitted_kyc = ComplianceCheck.objects.filter(check_type='kyc', status='submitted').count()
            approved_kyc = ComplianceCheck.objects.filter(check_type='kyc', status='approved').count()
            rejected_kyc = ComplianceCheck.objects.filter(check_type='kyc', status='rejected').count()
            
            # Calculate approval rate
            completed_kyc = approved_kyc + rejected_kyc
            approval_rate = (approved_kyc / completed_kyc * 100) if completed_kyc > 0 else 0
            
            # Get KYC by level
            kyc_by_level = ComplianceCheck.objects.filter(check_type='kyc').values('check_level').annotate(
                count=Count('id')
            )
            
            return {
                'total_kyc': total_kyc,
                'pending_kyc': pending_kyc,
                'submitted_kyc': submitted_kyc,
                'approved_kyc': approved_kyc,
                'rejected_kyc': rejected_kyc,
                'approval_rate': approval_rate,
                'kyc_by_level': list(kyc_by_level)
            }
            
        except Exception as e:
            logger.error(f"Error getting KYC statistics: {str(e)}")
            return {
                'total_kyc': 0,
                'pending_kyc': 0,
                'submitted_kyc': 0,
                'approved_kyc': 0,
                'rejected_kyc': 0,
                'approval_rate': 0,
                'kyc_by_level': []
            }
