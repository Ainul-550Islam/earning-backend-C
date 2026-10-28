"""
template_service.py – PostbackTemplate management service.

Provides high-level operations for managing postback templates.
Handles template rendering, validation, and usage tracking.
"""
import logging
from typing import Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from api.postback.models import NetworkPostbackConfig, PostbackTemplate

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for managing postback templates."""

    @staticmethod
    def create_template(
        network: NetworkPostbackConfig,
        name: str,
        template_body: str,
        description: str = "",
        variables: Optional[Dict] = None,
        validation_regex: str = "",
        required_variables: Optional[List[str]] = None,
    ) -> PostbackTemplate:
        """
        Create a new postback template with validation.
        """
        if variables is None:
            variables = {}
        if required_variables is None:
            required_variables = []
        
        template = PostbackTemplate.objects.create(
            network=network,
            name=name,
            description=description,
            template_body=template_body,
            variables=variables,
            validation_regex=validation_regex,
            required_variables=required_variables,
        )
        
        # Generate integrity hash
        template.integrity_hash = template.generate_integrity_hash()
        template.save()
        
        logger.info(
            "Created template '%s' for network %s",
            name, network.network_key
        )
        
        return template

    @staticmethod
    def render_template(
        template_id: str,
        context: Dict,
        increment_usage: bool = True
    ) -> str:
        """
        Render a template with the provided context.
        Raises ValueError if template not found or validation fails.
        """
        try:
            template = PostbackTemplate.objects.get(id=template_id, is_active=True)
        except PostbackTemplate.DoesNotExist:
            raise ValueError(f"Active template with ID {template_id} not found")
        
        rendered_content = template.render_template(context)
        
        if increment_usage:
            template.increment_usage()
        
        logger.debug(
            "Rendered template '%s' (usage: %d)",
            template.name, template.usage_count
        )
        
        return rendered_content

    @staticmethod
    def get_template_for_network(
        network: NetworkPostbackConfig,
        template_name: str
    ) -> Optional[PostbackTemplate]:
        """Get an active template by name for a specific network."""
        try:
            return PostbackTemplate.objects.get(
                network=network,
                name=template_name,
                is_active=True
            )
        except PostbackTemplate.DoesNotExist:
            return None

    @staticmethod
    def list_network_templates(
        network: NetworkPostbackConfig,
        active_only: bool = True
    ) -> List[PostbackTemplate]:
        """List all templates for a network."""
        queryset = PostbackTemplate.objects.filter(network=network)
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        return list(queryset.order_by('name'))

    @staticmethod
    def update_template(
        template_id: str,
        **updates
    ) -> PostbackTemplate:
        """
        Update an existing template.
        Automatically regenerates integrity hash.
        """
        try:
            template = PostbackTemplate.objects.get(id=template_id)
        except PostbackTemplate.DoesNotExist:
            raise ValueError(f"Template with ID {template_id} not found")
        
        # Update fields
        for field, value in updates.items():
            if hasattr(template, field):
                setattr(template, field, value)
        
        # Regenerate integrity hash
        template.integrity_hash = template.generate_integrity_hash()
        template.save()
        
        logger.info(
            "Updated template '%s' for network %s",
            template.name, template.network.network_key
        )
        
        return template

    @staticmethod
    def deactivate_template(template_id: str) -> bool:
        """Deactivate a template (soft delete)."""
        try:
            template = PostbackTemplate.objects.get(id=template_id)
            template.is_active = False
            template.integrity_hash = template.generate_integrity_hash()
            template.save()
            
            logger.info(
                "Deactivated template '%s' for network %s",
                template.name, template.network.network_key
            )
            
            return True
        except PostbackTemplate.DoesNotExist:
            return False

    @staticmethod
    def validate_template_syntax(template_body: str, variables: Dict) -> Dict:
        """
        Validate template syntax and check for missing variables.
        Returns validation results.
        """
        import re
        
        # Find all variables in template
        pattern = r'\{\{(\w+)\}\}'
        found_variables = re.findall(pattern, template_body)
        
        # Check for undefined variables
        undefined_vars = set(found_variables) - set(variables.keys())
        
        # Check for unused variables
        unused_vars = set(variables.keys()) - set(found_variables)
        
        return {
            'valid': len(undefined_vars) == 0,
            'found_variables': found_variables,
            'undefined_variables': list(undefined_vars),
            'unused_variables': list(unused_vars),
            'variable_count': len(found_variables),
        }

    @staticmethod
    def get_template_usage_stats(network: NetworkPostbackConfig) -> List[Dict]:
        """Get usage statistics for all templates of a network."""
        templates = PostbackTemplate.objects.filter(network=network)
        
        return [
            {
                'id': str(template.id),
                'name': template.name,
                'is_active': template.is_active,
                'usage_count': template.usage_count,
                'last_used_at': template.last_used_at.isoformat() if template.last_used_at else None,
                'created_at': template.created_at.isoformat(),
            }
            for template in templates.order_by('-usage_count')
        ]

    @staticmethod
    @transaction.atomic
    def clone_template(
        source_template_id: str,
        new_name: str,
        target_network: Optional[NetworkPostbackConfig] = None
    ) -> PostbackTemplate:
        """
        Clone an existing template.
        Can clone to the same network with a new name, or to a different network.
        """
        try:
            source_template = PostbackTemplate.objects.get(id=source_template_id)
        except PostbackTemplate.DoesNotExist:
            raise ValueError(f"Source template with ID {source_template_id} not found")
        
        # Determine target network
        if target_network is None:
            target_network = source_template.network
        
        # Create clone
        clone = PostbackTemplate.objects.create(
            network=target_network,
            name=new_name,
            description=f"Cloned from: {source_template.name}",
            template_body=source_template.template_body,
            variables=source_template.variables.copy(),
            validation_regex=source_template.validation_regex,
            required_variables=source_template.required_variables.copy(),
            is_active=True,  # Start as active
        )
        
        # Generate integrity hash
        clone.integrity_hash = clone.generate_integrity_hash()
        clone.save()
        
        logger.info(
            "Cloned template '%s' to '%s' for network %s",
            source_template.name, new_name, target_network.network_key
        )
        
        return clone

    @staticmethod
    def verify_template_integrity(template_id: str) -> bool:
        """Verify the integrity hash of a template."""
        try:
            template = PostbackTemplate.objects.get(id=template_id)
            return template.verify_integrity()
        except PostbackTemplate.DoesNotExist:
            return False

    @staticmethod
    def batch_verify_integrity(network: NetworkPostbackConfig) -> Dict:
        """Verify integrity of all templates for a network."""
        templates = PostbackTemplate.objects.filter(network=network)
        
        results = {
            'total': templates.count(),
            'valid': 0,
            'invalid': 0,
            'invalid_templates': []
        }
        
        for template in templates:
            if template.verify_integrity():
                results['valid'] += 1
            else:
                results['invalid'] += 1
                results['invalid_templates'].append({
                    'id': str(template.id),
                    'name': template.name,
                })
        
        return results
