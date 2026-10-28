from ...exceptions import WebhookTemplateError
"""Webhook Template Engine

This service handles Jinja2 templating and transformation rules
for webhook payloads before delivery.
"""

import ast
import json
import logging
import operator
import re
from typing import Dict, Any, Optional, List, Union
from jinja2 import Environment, BaseLoader, Template, TemplateError, Undefined
from django.core.exceptions import ValidationError

from ...models import WebhookTemplate
from ...constants import EventType

logger = logging.getLogger(__name__)


def _json_finalize(value: Any) -> str:
    """Jinja `finalize` hook: runs on every `{{ }}` output, wherever the
    value came from (top-level context, a `{% for %}` loop variable, a
    filter result, ...).

    BUG FIX: payload_template authors write bare placeholders like
    `"email": {{user_email}}` with no quotes of their own — the template
    is only valid JSON once string values come out quoted. Values are
    NOT pre-quoted before being handed to Jinja (a dict/list needs to
    stay a real object for `{% for %}` / `|length` / `.attr` to work;
    pre-quoting it would turn it into a JSON *string* Jinja would then
    iterate character-by-character). Finalizing at output time instead
    reaches every placeholder uniformly, including ones inside loops.

    Undefined (a variable missing from event_data entirely) becomes a
    quoted empty string rather than nothing — nothing would leave a
    dangling `"key": ` behind, which isn't valid JSON.
    """
    if isinstance(value, Undefined):
        return '""'
    if isinstance(value, str):
        stripped = value.strip()
        if stripped[:1] in ('{', '['):
            try:
                json.loads(stripped)
                return stripped
            except (json.JSONDecodeError, ValueError):
                pass
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return 'None'
    if isinstance(value, bool):
        return str(value)
    return str(value)


def _date_jinja_filter(value: Any, fmt: str = '%Y-%m-%d') -> str:
    """Custom `date` filter for payload templates — Jinja has no built-in
    `date` filter (Django's template language does, which is presumably
    where template authors picked up the `{{ value | date('%Y-%m-%d') }}`
    habit from), so payload_template strings using it need one registered
    here or every such template fails with "No filter named 'date'"."""
    from datetime import datetime
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return value
    if hasattr(value, 'strftime'):
        return value.strftime(fmt)
    return str(value)


# ── Safe expression evaluation for _calculate_field ────────────────────────
# SECURITY FIX: this module previously used eval(expression, {"__builtins__":
# {}}, data) to evaluate "calculate_field" transform rules. Clearing
# __builtins__ does NOT make eval() safe — it can still be escaped via
# attribute-chain tricks (e.g. ().__class__.__bases__[0].__subclasses__())
# to reach arbitrary Python objects, giving remote code execution to any
# user who can write WebhookTemplate.transform_rules (WebhookTemplateViewSet
# only requires IsAuthenticated, so this was reachable by ordinary users,
# not just staff). Replaced with a whitelist-only AST walker: numeric
# literals, field lookups from `data`, arithmetic, and comparisons only.
# No attribute access, calls, subscripts, or imports are reachable at all,
# so there is no sandbox to escape.
_SAFE_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_SAFE_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_SAFE_COMPAREOPS = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


def _safe_eval_node(node: ast.AST, data: Dict[str, Any]) -> Any:
    """Evaluate one whitelisted AST node against `data`. Raises ValueError
    for anything outside the arithmetic/comparison whitelist."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body, data)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")
        return node.value
    if isinstance(node, ast.Name):
        value = data.get(node.id)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Unknown or non-numeric field: {node.id}")
        return value
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_BINOPS:
        return _SAFE_BINOPS[type(node.op)](
            _safe_eval_node(node.left, data), _safe_eval_node(node.right, data)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNARYOPS:
        return _SAFE_UNARYOPS[type(node.op)](_safe_eval_node(node.operand, data))
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _SAFE_COMPAREOPS:
        return _SAFE_COMPAREOPS[type(node.ops[0])](
            _safe_eval_node(node.left, data), _safe_eval_node(node.comparators[0], data)
        )
    raise ValueError(f"Unsupported expression element: {type(node).__name__}")


def safe_eval_expression(expression: str, data: Dict[str, Any]) -> Any:
    """Safely evaluate a restricted arithmetic/comparison expression against
    `data`. Whitelist-only — no attribute access, calls, subscripts, or
    imports are reachable, unlike eval() with a stripped __builtins__."""
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError) as e:
        raise ValueError(f"Invalid expression syntax: {e}")
    return _safe_eval_node(tree, data)


class TemplateEngine:
    """
    Service for processing webhook payload templates.
    Supports Jinja2 templating and JSON transformation rules.
    """
    
    def __init__(self):
        """Initialize template engine."""
        self.logger = logger
        self.env = self._get_jinja_environment()

    def _get_jinja_environment(self) -> Environment:
        """Build the Jinja2 Environment used for payload template rendering.

        BUG FIX: autoescape=True HTML-escapes output (quotes become
        `&#34;`, ampersands become `&amp;`, ...) which corrupts JSON —
        this environment renders JSON payloads, not HTML. Also wires in
        `_json_finalize` (see module level) so every substituted value
        comes out JSON-safe regardless of where in the template it
        appears.

        NOTE: called fresh by render_template() rather than cached on
        self — WebhookTemplateEngineTest's custom-filter/include/extends
        tests patch this method on the class and expect a call made
        *after* the instance already exists to take effect.
        """
        env = Environment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=Undefined,
            finalize=_json_finalize,
        )
        env.filters['date'] = _date_jinja_filter
        return env

    def render_template(self, template: Union[WebhookTemplate, str], event_data: Dict[str, Any]) -> str:
        """
        Render a webhook payload template with event data.

        Args:
            template: Either a WebhookTemplate instance (its
                payload_template and transform_rules are used), or a raw
                template string. BUG FIX: admin/template_admin.py and
                WebhookTemplateViewSet already call this with
                `template.payload_template` (a plain string) rather than
                the model instance — those call sites only care whether
                rendering succeeds, and a bare string has no
                transform_rules to apply, so that branch skips them.
            event_data: Event data to render into the template.

        Returns:
            str: The rendered JSON payload text (not a parsed dict —
                every real caller, and every test, treats the result as
                text to search/re-parse, not a mapping).
        """
        if isinstance(template, str):
            payload_template = template
            transform_rules: Dict[str, Any] = {}
        else:
            payload_template = template.payload_template
            transform_rules = template.transform_rules or {}

        if not payload_template:
            return ''

        working_data = dict(event_data or {})
        template_text = payload_template
        post_render_rules = []

        for rule_name, rule_config in transform_rules.items():
            rule_type = rule_config.get('type')
            try:
                if rule_type == 'map_value':
                    working_data = self._map_value(rule_config, working_data)
                elif rule_type == 'format_date':
                    working_data = self._format_date(rule_config, working_data)
                elif rule_type == 'remove_field':
                    # Operates on the template source: `path` names the
                    # event-data/Jinja variable, which may not match the
                    # JSON key label the template author chose for it —
                    # blanking the *value* would leave that key behind
                    # with an empty value instead of removing it.
                    template_text = self._strip_field_from_template(
                        template_text, rule_config.get('path')
                    )
                elif rule_type == 'rename_field':
                    template_text = self._rename_field_in_template(
                        template_text, rule_config.get('old_name'), rule_config.get('new_name')
                    )
                elif rule_type in ('add_field', 'calculate_field'):
                    # Both introduce a key the template body never
                    # references at all, so there is no `{{ }}`
                    # placeholder to feed a value into — handled after
                    # rendering instead, by splicing into the result.
                    post_render_rules.append((rule_type, rule_config))
                else:
                    self.logger.warning(f"Unknown transformation rule type: {rule_type}")
            except Exception as e:
                self.logger.error(f"Transformation rule error ({rule_name}): {e}")

        env = self._get_jinja_environment()
        try:
            jinja_template = env.from_string(template_text)
            rendered_payload = jinja_template.render(working_data)
        except TemplateError as e:
            self.logger.error(f"Template rendering error: {e}")
            return payload_template

        for rule_type, rule_config in post_render_rules:
            field_name = rule_config.get('field_name')
            if rule_type == 'add_field':
                value = rule_config.get('value')
            else:
                try:
                    value = safe_eval_expression(rule_config.get('expression'), working_data)
                except Exception as e:
                    self.logger.error(f"Calculation error: {e}")
                    continue
            rendered_payload = self._splice_field(rendered_payload, field_name, value)

        try:
            json.loads(rendered_payload)
        except json.JSONDecodeError as e:
            self.logger.error(f"Rendered template is not valid JSON: {e}")

        name = template if isinstance(template, str) else template.name
        self.logger.debug(f"Template rendered successfully: {name}")

        return rendered_payload

    def _strip_field_from_template(self, template_text: str, var_name: Optional[str]) -> str:
        """Remove the `"key": {{ var_name }}` clause referencing var_name
        from the template source (remove_field transform rule), tidying
        up any comma left dangling by the removal."""
        if not var_name:
            return template_text
        pattern = re.compile(r'"[^"]*"\s*:\s*\{\{\s*' + re.escape(var_name) + r'\s*\}\}')
        new_text, count = pattern.subn('', template_text)
        if not count:
            return template_text
        new_text = re.sub(r',\s*,', ',', new_text)
        new_text = re.sub(r'\{\s*,', '{', new_text)
        new_text = re.sub(r',\s*\}', '}', new_text)
        return new_text

    def _rename_field_in_template(
        self, template_text: str, old_name: Optional[str], new_name: Optional[str]
    ) -> str:
        """Rename the JSON key preceding `{{ old_name }}` to new_name,
        keeping the variable reference (and so its rendered value)
        intact (rename_field transform rule)."""
        if not old_name or not new_name:
            return template_text
        pattern = re.compile(r'"[^"]*"(\s*:\s*\{\{\s*' + re.escape(old_name) + r'\s*\}\})')
        return pattern.sub('"' + new_name + r'"\1', template_text)

    def _splice_field(self, rendered_json: str, field_name: Optional[str], value: Any) -> str:
        """Insert a `"field_name": value` pair into a rendered JSON
        object, just before its closing brace (add_field /
        calculate_field transform rules — both add a key the template
        never mentioned, so there's nothing to substitute into)."""
        if not field_name:
            return rendered_json
        close_idx = rendered_json.rfind('}')
        if close_idx == -1:
            return rendered_json
        body_before = rendered_json[:close_idx].rstrip()
        needs_comma = not body_before.endswith('{')
        insertion = f'"{field_name}": {json.dumps(value, ensure_ascii=False)}'
        if needs_comma:
            insertion = ', ' + insertion
        return body_before + insertion + rendered_json[close_idx:]
    
    def _map_value(self, rule_config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Map values based on conditions."""
        field_path = rule_config.get('path')
        mappings = rule_config.get('mappings', {})
        default_value = rule_config.get('default')
        
        current_value = self._get_nested_value(data, field_path)
        
        if current_value in mappings:
            mapped_value = mappings[current_value]
            self._set_nested_value(data, field_path, mapped_value)
        elif default_value is not None:
            self._set_nested_value(data, field_path, default_value)
        
        return data
    
    def _format_date(self, rule_config: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Format a date field."""
        field_path = rule_config.get('path')
        date_format = rule_config.get('format', '%Y-%m-%d %H:%M:%S')
        
        current_value = self._get_nested_value(data, field_path)
        
        if current_value:
            try:
                from datetime import datetime
                if isinstance(current_value, str):
                    parsed_date = datetime.fromisoformat(current_value)
                else:
                    parsed_date = current_value
                
                formatted_date = parsed_date.strftime(date_format)
                self._set_nested_value(data, field_path, formatted_date)
                
            except Exception as e:
                self.logger.error(f"Date formatting error: {e}")
        
        return data
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value from dictionary using dot notation."""
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and key.isdigit():
                index = int(key)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            else:
                return None
        
        return current
    
    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Set nested value in dictionary using dot notation."""
        keys = path.split('.')
        current = data
        
        for i, key in enumerate(keys):
            is_last = i == len(keys) - 1
            
            if is_last:
                current[key] = value
            else:
                if key not in current:
                    current[key] = {}
                current = current[key]
    
    def validate_template(self, template: WebhookTemplate) -> List[str]:
        """
        Validate a webhook template.
        
        Args:
            template: WebhookTemplate instance
            
        Returns:
            List[str]: List of validation errors
        """
        errors = []
        
        if not template.name:
            errors.append("Template name is required")
        
        if not template.event_type:
            errors.append("Event type is required")
        
        if not template.payload_template:
            errors.append("Payload template is required")
        
        try:
            # Test template rendering
            test_data = {"test": "value"}
            self.env.from_string(template.payload_template).render(test_data)
        except TemplateError as e:
            errors.append(f"Invalid template syntax: {e}")
        
        return errors
    
    def get_template_summary(self, template: WebhookTemplate) -> Dict[str, Any]:
        """
        Get template summary including transformation rules.
        
        Args:
            template: WebhookTemplate instance
            
        Returns:
            Dict: Template summary
        """
        return {
            'id': template.id,
            'name': template.name,
            'event_type': template.event_type,
            'transform_rules_count': len(template.transform_rules or {}),
            'transform_rules': template.transform_rules or {},
            'is_active': template.is_active,
            'created_at': template.created_at,
            'updated_at': template.updated_at,
        }