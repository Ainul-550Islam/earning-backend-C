# utils/icu.py
"""
ICU Message Format parser and formatter.
Supports: simple, select, plural, date, number interpolation.
No external dependency — pure Python implementation.

ICU format examples:
  Simple:   "Hello, {name}!"
  Plural:   "{count, plural, one {# item} other {# items}}"
  Select:   "{gender, select, male {He} female {She} other {They}}"
  Number:   "{amount, number, currency}"
  Nested:   "{count, plural, one {{name} has # message} other {{name} has # messages}}"
"""
import re
from typing import Any, Dict, Optional, List, Tuple


class ICUParseError(Exception):
    pass


class ICUMessageFormatter:
    """
    ICU MessageFormat formatter — parse template + apply values.
    Used by translation system to handle plurals, gender, select.
    """

    def format(self, template: str, values: Dict[str, Any], locale: str = 'en') -> str:
        """
        ICU template-কে values দিয়ে format করে।
        template: "You have {count, plural, one {# message} other {# messages}}"
        values:   {"count": 3}
        returns:  "You have 3 messages"
        """
        if not template:
            return template
        try:
            return self._process(template, values, locale)
        except Exception as e:
            # Graceful fallback — return template with simple substitution
            result = template
            for key, val in values.items():
                result = result.replace('{' + key + '}', str(val))
            return result

    def _process(self, template: str, values: Dict[str, Any], locale: str) -> str:
        """Recursively process ICU message"""
        result = []
        i = 0
        while i < len(template):
            if template[i] == '{':
                # Find matching closing brace
                end, inner = self._find_block(template, i)
                result.append(self._process_block(inner, values, locale))
                i = end + 1
            elif template[i] == '#':
                # # is replaced by the innermost count value
                count = values.get('__count__', values.get('count', ''))
                result.append(str(count))
                i += 1
            else:
                result.append(template[i])
                i += 1
        return ''.join(result)

    def _find_block(self, template: str, start: int) -> Tuple[int, str]:
        """Find matching closing brace, handling nesting"""
        depth = 0
        i = start
        while i < len(template):
            if template[i] == '{':
                depth += 1
            elif template[i] == '}':
                depth -= 1
                if depth == 0:
                    return i, template[start+1:i]
            i += 1
        raise ICUParseError(f"Unmatched brace at position {start}")

    def _process_block(self, block: str, values: Dict[str, Any], locale: str) -> str:
        """Process a {...} block"""
        parts = block.split(',', 2)

        if len(parts) == 1:
            # Simple variable: {name}
            var_name = parts[0].strip()
            return str(values.get(var_name, '{' + var_name + '}'))

        var_name = parts[0].strip()
        block_type = parts[1].strip().lower()
        value = values.get(var_name)

        if block_type == 'plural':
            options_str = parts[2].strip() if len(parts) > 2 else ''
            count = value if value is not None else 0
            # Set __count__ for # substitution in nested templates
            nested_values = {**values, '__count__': count, 'count': count}
            template = self._select_plural(count, options_str, locale)
            return self._process(template, nested_values, locale)

        elif block_type == 'select':
            options_str = parts[2].strip() if len(parts) > 2 else ''
            key = str(value) if value is not None else 'other'
            template = self._select_option(key, options_str)
            return self._process(template, values, locale)

        elif block_type == 'selectordinal':
            options_str = parts[2].strip() if len(parts) > 2 else ''
            count = value if value is not None else 0
            nested_values = {**values, '__count__': count}
            template = self._select_ordinal(count, options_str, locale)
            return self._process(template, nested_values, locale)

        elif block_type in ('number', 'integer', 'currency', 'percent'):
            return self._format_number(value, block_type, locale)

        elif block_type in ('date', 'time', 'datetime'):
            return self._format_datetime(value, block_type, locale)

        else:
            # Unknown type — return value as string
            return str(value) if value is not None else ''

    def _select_plural(self, count: Any, options_str: str, locale: str) -> str:
        """Plural form select করে locale-based rules অনুযায়ী"""
        try:
            count_num = float(count) if count is not None else 0
        except (TypeError, ValueError):
            count_num = 0

        options = self._parse_options(options_str)

        # Exact match first: =0, =1, =2
        exact_key = f'={int(count_num)}'
        if exact_key in options:
            return options[exact_key]

        # CLDR plural category
        category = get_plural_category(count_num, locale)

        if category in options:
            return options[category]
        if 'other' in options:
            return options['other']
        return ''

    def _select_option(self, key: str, options_str: str) -> str:
        """Select form select করে"""
        options = self._parse_options(options_str)
        return options.get(key, options.get('other', ''))

    def _select_ordinal(self, count: Any, options_str: str, locale: str) -> str:
        """Ordinal plural (1st, 2nd, 3rd)"""
        options = self._parse_options(options_str)
        # Simple English ordinal
        n = int(count) if count else 0
        if n % 100 in (11, 12, 13):
            cat = 'other'
        elif n % 10 == 1:
            cat = 'one'
        elif n % 10 == 2:
            cat = 'two'
        elif n % 10 == 3:
            cat = 'few'
        else:
            cat = 'other'
        return options.get(cat, options.get('other', ''))

    def _parse_options(self, options_str: str) -> Dict[str, str]:
        """Parse "one {template} other {template}" → dict"""
        options = {}
        i = 0
        s = options_str.strip()
        while i < len(s):
            # Skip whitespace
            while i < len(s) and s[i].isspace():
                i += 1
            if i >= len(s):
                break
            # Read key
            key_start = i
            while i < len(s) and s[i] != '{':
                i += 1
            if i >= len(s):
                break
            key = s[key_start:i].strip()
            # Read value in braces
            try:
                end, inner = self._find_block(s, i)
                options[key] = inner
                i = end + 1
            except ICUParseError:
                break
        return options

    def _format_number(self, value: Any, fmt_type: str, locale: str) -> str:
        """Number formatting"""
        try:
            num = float(value) if value is not None else 0
            if fmt_type == 'integer':
                return str(int(num))
            elif fmt_type == 'percent':
                return f"{num * 100:.0f}%"
            elif fmt_type == 'currency':
                return f"{num:,.2f}"
            else:
                return f"{num:,}"
        except Exception:
            return str(value)

    def _format_datetime(self, value: Any, fmt_type: str, locale: str) -> str:
        """Date/time formatting"""
        try:
            from datetime import datetime
            if isinstance(value, str):
                dt = datetime.fromisoformat(value)
            elif isinstance(value, datetime):
                dt = value
            else:
                return str(value)
            if fmt_type == 'date':
                return dt.strftime('%Y-%m-%d')
            elif fmt_type == 'time':
                return dt.strftime('%H:%M')
            else:
                return dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            return str(value)


def get_plural_category(n: float, locale: str) -> str:
    """
    CLDR plural category for a number in a given locale.
    Returns: 'zero' | 'one' | 'two' | 'few' | 'many' | 'other'
    """
    # Import plural rules
    from .plural import get_plural_form
    return get_plural_form(n, locale)


def is_icu_format(text: str) -> bool:
    """Text ICU format কিনা check করে"""
    return bool(re.search(r'\{[^}]+,\s*(plural|select|number|date)\b', text))


def extract_icu_variables(template: str) -> List[str]:
    """ICU template থেকে variable names extract করে"""
    variables = []
    for match in re.finditer(r'\{(\w+)(?:,|\})', template):
        var = match.group(1)
        if var not in ('one', 'two', 'few', 'many', 'other', 'zero', 'male', 'female'):
            variables.append(var)
    return list(set(variables))


def validate_icu_template(template: str) -> Dict[str, Any]:
    """ICU template validate করে"""
    errors = []
    warnings = []

    # Check balanced braces
    depth = 0
    for i, ch in enumerate(template):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth < 0:
                errors.append(f"Unexpected '}}' at position {i}")
                break
    if depth != 0:
        errors.append(f"Unmatched '{{' — {depth} unclosed brace(s)")

    # Check plural options
    plural_matches = re.finditer(r'\{(\w+),\s*plural,([^}]+(?:\{[^}]*\}[^}]*)*)\}', template)
    for m in plural_matches:
        options_str = m.group(2)
        if 'other' not in options_str:
            warnings.append(f"Plural for '{m.group(1)}' missing 'other' form")

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'variables': extract_icu_variables(template),
        'is_icu': is_icu_format(template),
    }
