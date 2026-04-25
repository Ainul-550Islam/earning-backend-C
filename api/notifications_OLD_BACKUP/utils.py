from datetime import date, datetime  # সরাসরি date এবং datetime ইমপোর্ট করুন
from typing import Dict, List, Any, Optional, Union, Tuple
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.http import HttpResponse
import json
import re
import uuid
import logging

# লগিং সেটআপ (আপনার ডিবানিংয়ের জন্য কাজে লাগবে)
logger = logging.getLogger(__name__)



def send_email_template(
    subject: str,
    template_name: str,
    context: Dict,
    to_emails: List[str],
    from_email: Optional[str] = None,
    cc_emails: Optional[List[str]] = None,
    bcc_emails: Optional[List[str]] = None,
    attachments: Optional[List[Tuple[str, bytes, str]]] = None
) -> bool:
    """
    Send email using HTML template.
    
    Args:
        subject: Email subject
        template_name: Template name without extension
        context: Template context
        to_emails: List of recipient emails
        from_email: Sender email
        cc_emails: List of CC emails
        bcc_emails: List of BCC emails
        attachments: List of (filename, content, mimetype)
    
    Returns:
        bool: True if successful
    """
    try:
        # Render HTML content
        html_content = render_to_string(f'{template_name}.html', context)
        text_content = strip_tags(html_content)
        
        from_email = from_email or settings.DEFAULT_FROM_EMAIL
        
        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=to_emails,
            cc=cc_emails or [],
            bcc=bcc_emails or []
        )
        email.attach_alternative(html_content, "text/html")
        
        # Add attachments
        if attachments:
            for filename, content, mimetype in attachments:
                email.attach(filename, content, mimetype)
        
        # Send email
        email.send()
        logger.info(f"Email sent to {to_emails}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        sentry_sdk.capture_exception(e)
        return False

def send_slack_notification(
    webhook_url: str,
    message: str,
    channel: Optional[str] = None,
    username: Optional[str] = None,
    icon_emoji: Optional[str] = None,
    attachments: Optional[List[Dict]] = None
) -> bool:
    """
    Send notification to Slack.
    
    Args:
        webhook_url: Slack webhook URL
        message: Message text
        channel: Channel name
        username: Bot username
        icon_emoji: Bot icon emoji
        attachments: List of attachments
    
    Returns:
        bool: True if successful
    """
    try:
        payload = {
            "text": message,
            "channel": channel,
            "username": username or settings.APP_NAME,
            "icon_emoji": icon_emoji or ":robot_face:"
        }
        
        if attachments:
            payload["attachments"] = attachments
        
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return True
        
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
        return False

def format_currency(
    amount: Union[Decimal, float, int],
    currency: str = "USD",
    locale: str = "en_US"
) -> str:
    """
    Format currency amount.
    
    Args:
        amount: Amount to format
        currency: Currency code
        locale: Locale string
    
    Returns:
        str: Formatted currency string
    """
    try:
        # Convert to Decimal for precision
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        
        # Format based on currency
        if currency == "USD":
            return f"${amount:,.2f}"
        elif currency == "EUR":
            return f"€{amount:,.2f}"
        elif currency == "GBP":
            return f"£{amount:,.2f}"
        elif currency == "JPY":
            return f"¥{amount:,.0f}"
        elif currency == "INR":
            return f"₹{amount:,.2f}"
        else:
            return f"{currency} {amount:,.2f}"
            
    except Exception as e:
        logger.error(f"Failed to format currency: {e}")
        return str(amount)

def calculate_tax(
    amount: Union[Decimal, float, int],
    tax_rate: Union[Decimal, float],
    inclusive: bool = False
) -> Tuple[Decimal, Decimal]:
    """
    Calculate tax amount.
    
    Args:
        amount: Base amount
        tax_rate: Tax rate (percentage)
        inclusive: Whether tax is included in amount
    
    Returns:
        Tuple[Decimal, Decimal]: (tax_amount, total_amount)
    """
    try:
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        if not isinstance(tax_rate, Decimal):
            tax_rate = Decimal(str(tax_rate))
        
        tax_rate = tax_rate / Decimal('100')
        
        if inclusive:
            # Tax included in amount
            tax_amount = amount - (amount / (Decimal('1') + tax_rate))
            base_amount = amount - tax_amount
        else:
            # Tax added to amount
            tax_amount = amount * tax_rate
            base_amount = amount
        
        total_amount = base_amount + tax_amount
        
        # Round to 2 decimal places
        tax_amount = tax_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_amount = total_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return tax_amount, total_amount
        
    except Exception as e:
        logger.error(f"Failed to calculate tax: {e}")
        return Decimal('0'), amount

def generate_pdf(
    template_name: str,
    context: Dict,
    filename: Optional[str] = None,
    output_type: str = "bytes"  # "bytes", "file", or "response"
) -> Union[bytes, str, HttpResponse]:
    """
    Generate PDF from template.
    
    Args:
        template_name: Template name
        context: Template context
        filename: Output filename
        output_type: Type of output
    
    Returns:
        PDF content based on output_type
    """
    try:
        # Create buffer
        buffer = BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Add custom styles
        styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30
        ))
        
        # Prepare story (content)
        story = []
        
        # Add content from template
        html_content = render_to_string(template_name, context)
        
        # Convert HTML to PDF elements (simplified)
        # In production, use a proper HTML to PDF library like xhtml2pdf or weasyprint
        paragraphs = html_content.split('\n')
        for para in paragraphs:
            if para.strip():
                story.append(Paragraph(para.strip(), styles["Normal"]))
                story.append(Spacer(1, 12))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        # Return based on output type
        if output_type == "bytes":
            return pdf_bytes
        elif output_type == "file":
            if not filename:
                filename = f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            with open(filename, 'wb') as f:
                f.write(pdf_bytes)
            return filename
        else:
            from django.http import HttpResponse
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename or "document.pdf"}"'
            return response
            
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")
        sentry_sdk.capture_exception(e)
        raise

def validate_data(
    data: Dict,
    rules: Dict[str, Dict],
    raise_exception: bool = True
) -> Tuple[bool, Dict[str, List[str]]]:
    """
    Validate data against rules.
    
    Args:
        data: Data to validate
        rules: Validation rules
        raise_exception: Whether to raise exception
    
    Returns:
        Tuple[bool, Dict]: (is_valid, errors)
    """
    errors = {}
    is_valid = True
    
    for field, field_rules in rules.items():
        field_errors = []
        value = data.get(field)
        
        # Check required
        if field_rules.get('required', False) and (value is None or value == ''):
            field_errors.append(f"{field} is required")
        
        # Check type
        if value is not None and value != '':
            expected_type = field_rules.get('type')
            if expected_type:
                if expected_type == 'string' and not isinstance(value, str):
                    field_errors.append(f"{field} must be a string")
                elif expected_type == 'integer' and not isinstance(value, int):
                    field_errors.append(f"{field} must be an integer")
                elif expected_type == 'float' and not isinstance(value, (int, float)):
                    field_errors.append(f"{field} must be a float")
                elif expected_type == 'boolean' and not isinstance(value, bool):
                    field_errors.append(f"{field} must be a boolean")
                elif expected_type == 'email' and not validate_email_format(value):
                    field_errors.append(f"{field} must be a valid email")
                elif expected_type == 'phone' and not validate_phone_number(value):
                    field_errors.append(f"{field} must be a valid phone number")
            
            # Check min/max length
            if isinstance(value, str):
                min_length = field_rules.get('min_length')
                max_length = field_rules.get('max_length')
                if min_length and len(value) < min_length:
                    field_errors.append(f"{field} must be at least {min_length} characters")
                if max_length and len(value) > max_length:
                    field_errors.append(f"{field} must be at most {max_length} characters")
            
            # Check min/max value
            if isinstance(value, (int, float)):
                min_value = field_rules.get('min_value')
                max_value = field_rules.get('max_value')
                if min_value is not None and value < min_value:
                    field_errors.append(f"{field} must be at least {min_value}")
                if max_value is not None and value > max_value:
                    field_errors.append(f"{field} must be at most {max_value}")
            
            # Check regex pattern
            pattern = field_rules.get('pattern')
            if pattern and isinstance(value, str):
                if not re.match(pattern, value):
                    field_errors.append(f"{field} format is invalid")
            
            # Check custom validator
            validator = field_rules.get('validator')
            if validator and callable(validator):
                try:
                    if not validator(value):
                        field_errors.append(f"{field} is invalid")
                except Exception as e:
                    field_errors.append(f"{field} validation failed: {str(e)}")
        
        if field_errors:
            errors[field] = field_errors
            is_valid = False
    
    if not is_valid and raise_exception:
        from django.core.exceptions import ValidationError
        raise ValidationError(errors)
    
    return is_valid, errors

def generate_report_data(
    model_class,
    filters: Dict = None,
    group_by: List[str] = None,
    aggregates: Dict = None,
    date_field: str = 'created_at',
    date_range: Tuple[datetime, datetime] = None
) -> Dict:
    """
    Generate report data from model.
    
    Args:
        model_class: Django model class
        filters: Query filters
        group_by: Fields to group by
        aggregates: Aggregation functions
        date_field: Date field name
        date_range: Date range tuple
    
    Returns:
        Dict: Report data
    """
    try:
        queryset = model_class.objects.all()
        
        # Apply filters
        if filters:
            queryset = queryset.filter(**filters)
        
        # Apply date range
        if date_range:
            start_date, end_date = date_range
            date_filter = {f"{date_field}__gte": start_date, f"{date_field}__lte": end_date}
            queryset = queryset.filter(**date_filter)
        
        # Apply grouping and aggregation
        if group_by and aggregates:
            annotation_dict = {}
            for agg_name, agg_func in aggregates.items():
                if agg_func == 'count':
                    annotation_dict[agg_name] = Count('id')
                elif agg_func == 'sum':
                    # Assuming there's an amount field
                    annotation_dict[agg_name] = Sum('amount')
                elif agg_func == 'avg':
                    annotation_dict[agg_name] = Avg('amount')
                elif agg_func == 'max':
                    annotation_dict[agg_name] = Max('amount')
                elif agg_func == 'min':
                    annotation_dict[agg_name] = Min('amount')
            
            queryset = queryset.values(*group_by).annotate(**annotation_dict)
        
        # Convert to list
        data = list(queryset)
        
        # Calculate summary
        summary = {}
        if aggregates:
            for agg_name in aggregates.keys():
                if data and agg_name in data[0]:
                    values = [item[agg_name] for item in data if item.get(agg_name)]
                    if values:
                        summary[f'total_{agg_name}'] = sum(values)
                        summary[f'avg_{agg_name}'] = sum(values) / len(values) if len(values) > 0 else 0
        
        return {
            'data': data,
            'summary': summary,
            'count': len(data),
            'generated_at': timezone.now()
        }
        
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        return {'data': [], 'summary': {}, 'count': 0, 'error': str(e)}

def export_to_csv(
    data: List[Dict],
    filename: str,
    fieldnames: List[str] = None
) -> str:
    """
    Export data to CSV file.
    
    Args:
        data: List of dictionaries
        filename: Output filename
        fieldnames: List of field names
    
    Returns:
        str: Path to generated file
    """
    try:
        if not fieldnames and data:
            fieldnames = list(data[0].keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        logger.info(f"CSV exported to {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Failed to export CSV: {e}")
        raise

def export_to_excel(
    data: List[Dict],
    filename: str,
    sheet_name: str = 'Sheet1',
    include_index: bool = False
) -> str:
    """
    Export data to Excel file.
    
    Args:
        data: List of dictionaries
        filename: Output filename
        sheet_name: Worksheet name
        include_index: Include index column
    
    Returns:
        str: Path to generated file
    """
    try:
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Create Excel writer
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(
                writer,
                sheet_name=sheet_name,
                index=include_index,
                header=True
            )
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]
            
            # Apply styles
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(
                start_color="366092",
                end_color="366092",
                fill_type="solid"
            )
            
            # Style header
            for cell in worksheet[1]:
                cell.font = header_font
                cell.fill = header_fill
        
        logger.info(f"Excel exported to {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Failed to export to Excel: {e}")
        raise

def backup_database(
    output_path: str,
    compress: bool = True
) -> str:
    """
    Backup database.
    
    Args:
        output_path: Output path
        compress: Whether to compress backup
    
    Returns:
        str: Path to backup file
    """
    try:
        from django.core.management import call_command
        import subprocess
        
        # Create backup directory if not exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Dump database
        dump_file = f"{output_path}.sql"
        
        db_settings = settings.DATABASES['default']
        engine = db_settings['ENGINE']
        
        if 'postgresql' in engine:
            # PostgreSQL backup
            cmd = [
                'pg_dump',
                '-h', db_settings.get('HOST', 'localhost'),
                '-p', str(db_settings.get('PORT', '5432')),
                '-U', db_settings['USER'],
                '-d', db_settings['NAME'],
                '-f', dump_file
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = db_settings['PASSWORD']
            
            subprocess.run(cmd, env=env, check=True)
            
        elif 'mysql' in engine:
            # MySQL backup
            cmd = [
                'mysqldump',
                '-h', db_settings.get('HOST', 'localhost'),
                '-P', str(db_settings.get('PORT', '3306')),
                '-u', db_settings['USER'],
                '-p' + db_settings['PASSWORD'],
                db_settings['NAME'],
                '--result-file=' + dump_file
            ]
            
            subprocess.run(cmd, check=True)
        
        else:
            # Use Django dumpdata for SQLite or other
            with open(dump_file, 'w') as f:
                call_command('dumpdata', stdout=f)
        
        # Compress if requested
        if compress:
            import gzip
            compressed_file = f"{output_path}.gz"
            with open(dump_file, 'rb') as f_in:
                with gzip.open(compressed_file, 'wb') as f_out:
                    f_out.write(f_in.read())
            os.remove(dump_file)
            final_file = compressed_file
        else:
            final_file = dump_file
        
        logger.info(f"Database backed up to {final_file}")
        return final_file
        
    except Exception as e:
        logger.error(f"Failed to backup database: {e}")
        sentry_sdk.capture_exception(e)
        raise

def cleanup_old_files(
    directory: str,
    pattern: str = "*",
    days_old: int = 30,
    recursive: bool = False
) -> int:
    """
    Clean up old files in directory.
    
    Args:
        directory: Directory path
        pattern: File pattern
        days_old: Delete files older than days
        recursive: Whether to search recursively
    
    Returns:
        int: Number of files deleted
    """
    import glob
    import fnmatch
    
    deleted_count = 0
    cutoff_date = timezone.now() - timedelta(days=days_old)
    
    try:
        if recursive:
            # Walk through directory tree
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if fnmatch.fnmatch(file, pattern):
                        file_path = os.path.join(root, file)
                        file_time = datetime.fromtimestamp(
                            os.path.getmtime(file_path)
                        ).replace(tzinfo=pytz.UTC)
                        
                        if file_time < cutoff_date:
                            os.remove(file_path)
                            deleted_count += 1
        else:
            # Single directory
            for file in glob.glob(os.path.join(directory, pattern)):
                if os.path.isfile(file):
                    file_time = datetime.fromtimestamp(
                        os.path.getmtime(file)
                    ).replace(tzinfo=pytz.UTC)
                    
                    if file_time < cutoff_date:
                        os.remove(file)
                        deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} old files from {directory}")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Failed to cleanup old files: {e}")
        return 0

def compress_files(
    files: List[str],
    output_path: str,
    compression_format: str = 'zip'
) -> str:
    """
    Compress multiple files.
    
    Args:
        files: List of file paths
        output_path: Output archive path
        compression_format: Compression format
    
    Returns:
        str: Path to compressed file
    """
    try:
        import zipfile
        import tarfile
        
        if compression_format == 'zip':
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in files:
                    if os.path.exists(file):
                        arcname = os.path.basename(file)
                        zipf.write(file, arcname)
        
        elif compression_format in ['tar', 'tgz', 'tar.gz']:
            mode = 'w:gz' if compression_format in ['tgz', 'tar.gz'] else 'w'
            with tarfile.open(output_path, mode) as tar:
                for file in files:
                    if os.path.exists(file):
                        tar.add(file, arcname=os.path.basename(file))
        
        else:
            raise ValueError(f"Unsupported compression format: {compression_format}")
        
        logger.info(f"Compressed {len(files)} files to {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to compress files: {e}")
        raise

def encrypt_data(
    data: Union[str, bytes],
    key: Optional[str] = None
) -> str:
    """
    Encrypt data.
    
    Args:
        data: Data to encrypt
        key: Encryption key
    
    Returns:
        str: Encrypted data (base64)
    """
    try:
        from cryptography.fernet import Fernet
        
        key = key or settings.SECRET_KEY[:32].encode()
        
        # Ensure key is 32 bytes
        if len(key) < 32:
            key = key.ljust(32, b'0')
        elif len(key) > 32:
            key = key[:32]
        
        # Create Fernet key
        fernet_key = hashlib.sha256(key).digest()[:32]
        cipher = Fernet(base64.urlsafe_b64encode(fernet_key))
        
        # Convert data to bytes if string
        if isinstance(data, str):
            data = data.encode()
        
        # Encrypt
        encrypted = cipher.encrypt(data)
        
        return base64.b64encode(encrypted).decode()
        
    except Exception as e:
        logger.error(f"Failed to encrypt data: {e}")
        raise

def decrypt_data(
    encrypted_data: str,
    key: Optional[str] = None
) -> str:
    """
    Decrypt data.
    
    Args:
        encrypted_data: Encrypted data (base64)
        key: Decryption key
    
    Returns:
        str: Decrypted data
    """
    try:
        from cryptography.fernet import Fernet
        
        key = key or settings.SECRET_KEY[:32].encode()
        
        # Ensure key is 32 bytes
        if len(key) < 32:
            key = key.ljust(32, b'0')
        elif len(key) > 32:
            key = key[:32]
        
        # Create Fernet key
        fernet_key = hashlib.sha256(key).digest()[:32]
        cipher = Fernet(base64.urlsafe_b64encode(fernet_key))
        
        # Decode base64
        encrypted_bytes = base64.b64decode(encrypted_data)
        
        # Decrypt
        decrypted = cipher.decrypt(encrypted_bytes)
        
        return decrypted.decode()
        
    except Exception as e:
        logger.error(f"Failed to decrypt data: {e}")
        raise

def sync_with_external_service(
    endpoint: str,
    method: str = 'GET',
    data: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    timeout: int = 30
) -> Optional[Dict]:
    """
    Sync with external API service.
    
    Args:
        endpoint: API endpoint
        method: HTTP method
        data: Request data
        headers: Request headers
        timeout: Request timeout
    
    Returns:
        Optional[Dict]: Response data
    """
    try:
        headers = headers or {}
        headers.update({
            'User-Agent': f'{settings.APP_NAME}/1.0',
            'Accept': 'application/json'
        })
        
        response = requests.request(
            method=method,
            url=endpoint,
            json=data,
            headers=headers,
            timeout=timeout
        )
        
        response.raise_for_status()
        
        if response.headers.get('content-type', '').startswith('application/json'):
            return response.json()
        else:
            return {'text': response.text}
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to sync with {endpoint}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during sync: {e}")
        sentry_sdk.capture_exception(e)
        return None

def check_api_health(
    endpoints: List[Dict[str, str]],
    expected_status: int = 200
) -> Dict[str, Dict]:
    """
    Check health of multiple API endpoints.
    
    Args:
        endpoints: List of endpoint configs
        expected_status: Expected HTTP status
    
    Returns:
        Dict: Health status for each endpoint
    """
    results = {}
    
    for endpoint_config in endpoints:
        url = endpoint_config['url']
        method = endpoint_config.get('method', 'GET')
        name = endpoint_config.get('name', url)
        
        try:
            start_time = time.time()
            response = requests.request(
                method=method,
                url=url,
                timeout=10
            )
            response_time = time.time() - start_time
            
            is_healthy = response.status_code == expected_status
            results[name] = {
                'healthy': is_healthy,
                'status_code': response.status_code,
                'response_time': response_time,
                'timestamp': timezone.now()
            }
            
        except Exception as e:
            results[name] = {
                'healthy': False,
                'error': str(e),
                'timestamp': timezone.now()
            }
    
    return results

def rate_limit_check(
    key: str,
    limit: int,
    period: int = 60  # seconds
) -> Tuple[bool, Dict]:
    """
    Check rate limit.
    
    Args:
        key: Rate limit key
        limit: Maximum requests
        period: Time period in seconds
    
    Returns:
        Tuple[bool, Dict]: (allowed, details)
    """
    redis_client = get_redis_client()
    
    if not redis_client:
        # No Redis, always allow
        return True, {'remaining': limit, 'reset_time': None}
    
    current = redis_client.get(key)
    
    if current is None:
        # First request in period
        redis_client.setex(key, period, 1)
        return True, {'remaining': limit - 1, 'reset_time': period}
    
    current_count = int(current)
    
    if current_count >= limit:
        # Rate limit exceeded
        ttl = redis_client.ttl(key)
        return False, {
            'remaining': 0,
            'reset_time': ttl,
            'limit': limit,
            'period': period
        }
    
    # Increment counter
    redis_client.incr(key)
    remaining = limit - (current_count + 1)
    
    return True, {
        'remaining': remaining,
        'reset_time': redis_client.ttl(key),
        'limit': limit,
        'period': period
    }

def get_exchange_rate(
    from_currency: str,
    to_currency: str,
    date: Optional[date] = None
) -> Optional[Decimal]:
    """
    Get exchange rate between currencies.
    
    Args:
        from_currency: Source currency
        to_currency: Target currency
        date: Date for historical rate
    
    Returns:
        Optional[Decimal]: Exchange rate
    """
    try:
        # Try to get from cache first
        cache_key = f"exchange_rate_{from_currency}_{to_currency}_{date or 'latest'}"
        cached_rate = cache.get(cache_key)
        
        if cached_rate:
            return Decimal(cached_rate)
        
        # Fetch from external API (example using free API)
        if date:
            url = f"https://api.exchangerate.host/{date}"
        else:
            url = "https://api.exchangerate.host/latest"
        
        params = {
            'base': from_currency,
            'symbols': to_currency
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if 'rates' in data and to_currency in data['rates']:
            rate = Decimal(str(data['rates'][to_currency]))
            
            # Cache for 1 hour
            cache.set(cache_key, str(rate), 3600)
            
            return rate
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to get exchange rate: {e}")
        return None

def convert_currency(
    amount: Union[Decimal, float, int],
    from_currency: str,
    to_currency: str,
    date: Optional[date] = None
) -> Optional[Decimal]:
    """
    Convert amount between currencies.
    
    Args:
        amount: Amount to convert
        from_currency: Source currency
        to_currency: Target currency
        date: Date for historical rate
    
    Returns:
        Optional[Decimal]: Converted amount
    """
    try:
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        
        rate = get_exchange_rate(from_currency, to_currency, date)
        
        if rate:
            converted = amount * rate
            return converted.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to convert currency: {e}")
        return None

def generate_random_string(
    length: int = 32,
    include_digits: bool = True,
    include_symbols: bool = False
) -> str:
    """
    Generate random string.
    
    Args:
        length: String length
        include_digits: Include digits
        include_symbols: Include symbols
    
    Returns:
        str: Random string
    """
    characters = string.ascii_letters
    
    if include_digits:
        characters += string.digits
    
    if include_symbols:
        characters += string.punctuation
    
    return ''.join(secrets.choice(characters) for _ in range(length))

def hash_password(password: str) -> str:
    """
    Hash password using bcrypt.
    
    Args:
        password: Plain text password
    
    Returns:
        str: Hashed password
    """
    try:
        import bcrypt
        
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode(), salt)
        
        return hashed.decode()
        
    except ImportError:
        # Fallback to Django's password hasher
        from django.contrib.auth.hashers import make_password
        return make_password(password)
    except Exception as e:
        logger.error(f"Failed to hash password: {e}")
        raise

def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify password against hash.
    
    Args:
        password: Plain text password
        hashed_password: Hashed password
    
    Returns:
        bool: True if password matches
    """
    try:
        import bcrypt
        
        return bcrypt.checkpw(
            password.encode(),
            hashed_password.encode()
        )
        
    except ImportError:
        # Fallback to Django's password checker
        from django.contrib.auth.hashers import check_password
        return check_password(password, hashed_password)
    except Exception as e:
        logger.error(f"Failed to verify password: {e}")
        return False

def generate_jwt_token(
    payload: Dict,
    expires_in: int = 3600,  # 1 hour
    secret: Optional[str] = None
) -> str:
    """
    Generate JWT token.
    
    Args:
        payload: Token payload
        expires_in: Expiration time in seconds
        secret: Secret key
    
    Returns:
        str: JWT token
    """
    try:
        secret = secret or settings.SECRET_KEY
        
        # Add expiration
        payload = payload.copy()
        payload['exp'] = timezone.now() + timedelta(seconds=expires_in)
        payload['iat'] = timezone.now()
        
        token = jwt.encode(payload, secret, algorithm='HS256')
        
        return token
        
    except Exception as e:
        logger.error(f"Failed to generate JWT token: {e}")
        raise

def verify_jwt_token(
    token: str,
    secret: Optional[str] = None
) -> Optional[Dict]:
    """
    Verify JWT token.
    
    Args:
        token: JWT token
        secret: Secret key
    
    Returns:
        Optional[Dict]: Decoded payload if valid
    """
    try:
        secret = secret or settings.SECRET_KEY
        
        payload = jwt.decode(
            token,
            secret,
            algorithms=['HS256'],
            options={'verify_exp': True}
        )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to verify JWT token: {e}")
        return None

def create_short_url(
    long_url: str,
    custom_alias: Optional[str] = None,
    expires_in: Optional[int] = None
) -> Optional[str]:
    """
    Create short URL.
    
    Args:
        long_url: Original URL
        custom_alias: Custom alias
        expires_in: Expiration in seconds
    
    Returns:
        Optional[str]: Short URL
    """
    try:
        # Generate unique alias
        if not custom_alias:
            alias = generate_random_string(6, include_digits=True, include_symbols=False)
        else:
            alias = custom_alias
        
        # Store in database or cache
        cache_key = f"shorturl_{alias}"
        cache_data = {
            'url': long_url,
            'created_at': timezone.now().isoformat(),
            'expires_at': (timezone.now() + timedelta(seconds=expires_in)).isoformat() if expires_in else None
        }
        
        if expires_in:
            cache.set(cache_key, cache_data, expires_in)
        else:
            cache.set(cache_key, cache_data)
        
        # Return short URL
        base_url = settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://localhost:8000'
        return f"{base_url}/s/{alias}"
        
    except Exception as e:
        logger.error(f"Failed to create short URL: {e}")
        return None

def validate_url(url: str) -> bool:
    """
    Validate URL format.
    
    Args:
        url: URL to validate
    
    Returns:
        bool: True if valid URL
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def extract_domain(url: str) -> Optional[str]:
    """
    Extract domain from URL.
    
    Args:
        url: URL
    
    Returns:
        Optional[str]: Domain name
    """
    try:
        result = urlparse(url)
        return result.netloc
    except:
        return None

def parse_csv_file(
    file_path: str,
    has_header: bool = True,
    delimiter: str = ','
) -> List[Dict[str, Any]]:
    """
    Parse CSV file.
    
    Args:
        file_path: Path to CSV file
        has_header: Whether file has header row
        delimiter: Column delimiter
    
    Returns:
        List[Dict]: Parsed data
    """
    try:
        data = []
        
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            if has_header:
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                data = list(reader)
            else:
                reader = csv.reader(csvfile, delimiter=delimiter)
                # Create field names as column_1, column_2, etc.
                for row in reader:
                    data.append({
                        f'column_{i+1}': value
                        for i, value in enumerate(row)
                    })
        
        return data
        
    except Exception as e:
        logger.error(f"Failed to parse CSV file: {e}")
        raise

def parse_json_file(file_path: str) -> Any:
    """
    Parse JSON file.
    
    Args:
        file_path: Path to JSON file
    
    Returns:
        Parsed JSON data
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as jsonfile:
            return json.load(jsonfile)
    except Exception as e:
        logger.error(f"Failed to parse JSON file: {e}")
        raise

def validate_email_format(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email address
    
    Returns:
        bool: True if valid email
    """
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False
    except:
        # Simple regex fallback
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

def validate_phone_number(
    phone_number: str,
    country_code: str = 'US'
) -> bool:
    """
    Validate phone number.
    
    Args:
        phone_number: Phone number
        country_code: Country code
    
    Returns:
        bool: True if valid phone number
    """
    try:
        parsed = phonenumbers.parse(phone_number, country_code)
        return phonenumbers.is_valid_number(parsed)
    except:
        return False

def geocode_address(
    address: str,
    api_key: Optional[str] = None
) -> Optional[Dict[str, float]]:
    """
    Geocode address to coordinates.
    
    Args:
        address: Address string
        api_key: Google Maps API key
    
    Returns:
        Optional[Dict]: Latitude and longitude
    """
    try:
        if not api_key and hasattr(settings, 'GOOGLE_MAPS_API_KEY'):
            api_key = settings.GOOGLE_MAPS_API_KEY
        
        if api_key:
            # Use Google Maps
            gmaps = googlemaps.Client(key=api_key)
            result = gmaps.geocode(address)
            
            if result:
                location = result[0]['geometry']['location']
                return {
                    'latitude': location['lat'],
                    'longitude': location['lng'],
                    'formatted_address': result[0]['formatted_address']
                }
        
        # Fallback to Nominatim
        geolocator = get_geolocator()
        location = geolocator.geocode(address)
        
        if location:
            return {
                'latitude': location.latitude,
                'longitude': location.longitude,
                'address': location.address
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to geocode address: {e}")
        return None

def calculate_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    unit: str = 'km'
) -> float:
    """
    Calculate distance between two coordinates.
    
    Args:
        lat1, lon1: First coordinate
        lat2, lon2: Second coordinate
        unit: 'km' or 'miles'
    
    Returns:
        float: Distance
    """
    try:
        # Haversine formula
        R = 6371  # Earth radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        
        if unit == 'miles':
            distance *= 0.621371
        
        return round(distance, 2)
        
    except Exception as e:
        logger.error(f"Failed to calculate distance: {e}")
        return 0.0

def get_weather_data(
    location: str,
    api_key: Optional[str] = None
) -> Optional[Dict]:
    """
    Get weather data for location.
    
    Args:
        location: City name or coordinates
        api_key: Weather API key
    
    Returns:
        Optional[Dict]: Weather data
    """
    try:
        if not api_key and hasattr(settings, 'WEATHER_API_KEY'):
            api_key = settings.WEATHER_API_KEY
        
        if not api_key:
            logger.warning("No weather API key configured")
            return None
        
        # Example using OpenWeatherMap
        base_url = "https://api.openweathermap.org/data/2.5/weather"
        
        params = {
            'q': location,
            'appid': api_key,
            'units': 'metric'  # Use 'imperial' for Fahrenheit
        }
        
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        
        return response.json()
        
    except Exception as e:
        logger.error(f"Failed to get weather data: {e}")
        return None

def get_location_info(ip_address: str) -> Optional[Dict]:
    """
    Get location info from IP address.
    
    Args:
        ip_address: IP address
    
    Returns:
        Optional[Dict]: Location information
    """
    try:
        # Using ipinfo.io (free tier)
        response = requests.get(f"https://ipinfo.io/{ip_address}/json", timeout=10)
        response.raise_for_status()
        
        return response.json()
        
    except Exception as e:
        logger.error(f"Failed to get location info: {e}")
        return None

def send_sms(
    to_number: str,
    message: str,
    from_number: Optional[str] = None
) -> bool:
    """
    Send SMS using Twilio.
    
    Args:
        to_number: Recipient phone number
        message: Message text
        from_number: Sender phone number
    
    Returns:
        bool: True if successful
    """
    try:
        twilio_client = get_twilio_client()
        
        if not twilio_client:
            logger.error("Twilio client not configured")
            return False
        
        from_number = from_number or settings.TWILIO_PHONE_NUMBER
        
        message = twilio_client.messages.create(
            body=message,
            from_=from_number,
            to=to_number
        )
        
        logger.info(f"SMS sent to {to_number}: {message.sid}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")
        sentry_sdk.capture_exception(e)
        return False

def make_phone_call(
    to_number: str,
    message: str,
    from_number: Optional[str] = None
) -> bool:
    """
    Make phone call using Twilio.
    
    Args:
        to_number: Recipient phone number
        message: Message to speak
        from_number: Sender phone number
    
    Returns:
        bool: True if successful
    """
    try:
        twilio_client = get_twilio_client()
        
        if not twilio_client:
            logger.error("Twilio client not configured")
            return False
        
        from_number = from_number or settings.TWILIO_PHONE_NUMBER
        
        # Create TwiML for call
        twiml = f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="alice">{message}</Say>
        </Response>
        """
        
        call = twilio_client.calls.create(
            twiml=twiml,
            to=to_number,
            from_=from_number
        )
        
        logger.info(f"Phone call initiated to {to_number}: {call.sid}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to make phone call: {e}")
        sentry_sdk.capture_exception(e)
        return False

# AWS Utilities
def upload_to_s3(
    file_path: str,
    bucket_name: str,
    object_name: Optional[str] = None,
    extra_args: Optional[Dict] = None
) -> bool:
    """
    Upload file to S3.
    
    Args:
        file_path: Local file path
        bucket_name: S3 bucket name
        object_name: S3 object name
        extra_args: Extra arguments for upload
    
    Returns:
        bool: True if successful
    """
    try:
        s3_client = get_s3_client()
        
        if object_name is None:
            object_name = os.path.basename(file_path)
        
        extra_args = extra_args or {}
        
        s3_client.upload_file(
            file_path,
            bucket_name,
            object_name,
            ExtraArgs=extra_args
        )
        
        logger.info(f"File uploaded to s3://{bucket_name}/{object_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to upload to S3: {e}")
        sentry_sdk.capture_exception(e)
        return False

def download_from_s3(
    bucket_name: str,
    object_name: str,
    file_path: str
) -> bool:
    """
    Download file from S3.
    
    Args:
        bucket_name: S3 bucket name
        object_name: S3 object name
        file_path: Local file path
    
    Returns:
        bool: True if successful
    """
    try:
        s3_client = get_s3_client()
        
        s3_client.download_file(
            bucket_name,
            object_name,
            file_path
        )
        
        logger.info(f"File downloaded from s3://{bucket_name}/{object_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to download from S3: {e}")
        sentry_sdk.capture_exception(e)
        return False

def generate_presigned_url(
    bucket_name: str,
    object_name: str,
    expiration: int = 3600
) -> Optional[str]:
    """
    Generate presigned URL for S3 object.
    
    Args:
        bucket_name: S3 bucket name
        object_name: S3 object name
        expiration: URL expiration in seconds
    
    Returns:
        Optional[str]: Presigned URL
    """
    try:
        s3_client = get_s3_client()
        
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': object_name
            },
            ExpiresIn=expiration
        )
        
        return url
        
    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        return None

def delete_from_s3(
    bucket_name: str,
    object_name: str
) -> bool:
    """
    Delete file from S3.
    
    Args:
        bucket_name: S3 bucket name
        object_name: S3 object name
    
    Returns:
        bool: True if successful
    """
    try:
        s3_client = get_s3_client()
        
        s3_client.delete_object(
            Bucket=bucket_name,
            Key=object_name
        )
        
        logger.info(f"File deleted from s3://{bucket_name}/{object_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete from S3: {e}")
        return False

def list_s3_files(
    bucket_name: str,
    prefix: str = '',
    max_keys: int = 1000
) -> List[Dict]:
    """
    List files in S3 bucket.
    
    Args:
        bucket_name: S3 bucket name
        prefix: File prefix filter
        max_keys: Maximum number of keys
    
    Returns:
        List[Dict]: List of file objects
    """
    try:
        s3_client = get_s3_client()
        
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix,
            MaxKeys=max_keys
        )
        
        files = []
        
        if 'Contents' in response:
            for obj in response['Contents']:
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'etag': obj['ETag']
                })
        
        return files
        
    except Exception as e:
        logger.error(f"Failed to list S3 files: {e}")
        return []

# Decorators
def retry(
    max_retries: int = 3,
    delay: int = 1,
    backoff: int = 2,
    exceptions: Tuple = (Exception,)
):
    """
    Retry decorator.
    
    Args:
        max_retries: Maximum retry attempts
        delay: Initial delay in seconds
        backoff: Backoff multiplier
        exceptions: Exceptions to catch
    
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed for {func.__name__}: {e}"
                        )
                        raise last_exception
            
            raise last_exception
        
        return wrapper
    return decorator

def timing(func):
    """
    Timing decorator to measure function execution time.
    
    Args:
        func: Function to decorate
    
    Returns:
        Decorated function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        logger.info(
            f"Function {func.__name__} took {end_time - start_time:.2f} seconds"
        )
        
        return result
    
    return wrapper

def cache_result(
    timeout: int = 300,
    key_prefix: str = ''
):
    """
    Cache function result.
    
    Args:
        timeout: Cache timeout in seconds
        key_prefix: Cache key prefix
    
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}{func.__name__}:{str(args)}:{str(kwargs)}"
            cache_key = hashlib.md5(cache_key.encode()).hexdigest()
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(cache_key, result, timeout)
            logger.debug(f"Cache set for {func.__name__}")
            
            return result
        
        return wrapper
    return decorator

def require_auth(func):
    """
    Require authentication decorator.
    
    Args:
        func: Function to decorate
    
    Returns:
        Decorated function
    """
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.http import JsonResponse
            return JsonResponse(
                {'error': 'Authentication required'},
                status=401
            )
        return func(request, *args, **kwargs)
    
    return wrapper

def admin_required(func):
    """
    Require admin permission decorator.
    
    Args:
        func: Function to decorate
    
    Returns:
        Decorated function
    """
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            from django.http import JsonResponse
            return JsonResponse(
                {'error': 'Admin permission required'},
                status=403
            )
        return func(request, *args, **kwargs)
    
    return wrapper

# Context managers
class Timer:
    """Context manager for timing code blocks."""
    
    def __enter__(self):
        self.start = time.time()
        return self
    
    def __exit__(self, *args):
        self.end = time.time()
        self.interval = self.end - self.start
        logger.info(f"Execution time: {self.interval:.2f} seconds")

class DatabaseTransaction:
    """Context manager for database transactions."""
    
    def __enter__(self):
        transaction.set_autocommit(False)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            transaction.commit()
        else:
            transaction.rollback()
        transaction.set_autocommit(True)

# Custom exceptions
class ValidationError(Exception):
    """Custom validation error."""
    pass

class ExternalServiceError(Exception):
    """External service error."""
    pass

class RateLimitExceeded(Exception):
    """Rate limit exceeded error."""
    pass

class ConfigurationError(Exception):
    """Configuration error."""
    pass

# Data conversion utilities
def dict_to_model(data: Dict, model_class):
    """
    Convert dictionary to model instance.
    
    Args:
        data: Dictionary data
        model_class: Model class
    
    Returns:
        Model instance
    """
    instance = model_class()
    
    for key, value in data.items():
        if hasattr(instance, key):
            setattr(instance, key, value)
    
    return instance

def model_to_dict(instance, fields=None, exclude=None):
    """
    Convert model instance to dictionary.
    
    Args:
        instance: Model instance
        fields: Fields to include
        exclude: Fields to exclude
    
    Returns:
        Dictionary representation
    """
    if fields is None:
        fields = [field.name for field in instance._meta.fields]
    
    if exclude is None:
        exclude = []
    
    data = {}
    
    for field in fields:
        if field not in exclude:
            value = getattr(instance, field)
            
            # Handle special types
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, Decimal):
                value = float(value)
            
            data[field] = value
    
    return data

def flatten_dict(d, parent_key='', sep='_'):
    """
    Flatten nested dictionary.
    
    Args:
        d: Dictionary to flatten
        parent_key: Parent key
        sep: Separator
    
    Returns:
        Flattened dictionary
    """
    items = []
    
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Convert lists to JSON string or handle appropriately
            items.append((new_key, json.dumps(v)))
        else:
            items.append((new_key, v))
    
    return dict(items)

def chunk_list(lst, chunk_size):
    """
    Split list into chunks.
    
    Args:
        lst: List to split
        chunk_size: Size of each chunk
    
    Yields:
        Chunks of the list
    """
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

def safe_int(value, default=0):
    """
    Safely convert value to integer.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
    
    Returns:
        Integer value
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float(value, default=0.0):
    """
    Safely convert value to float.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
    
    Returns:
        Float value
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_bool(value, default=False):
    """
    Safely convert value to boolean.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
    
    Returns:
        Boolean value
    """
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        value = value.lower().strip()
        if value in ('true', 'yes', '1', 'on'):
            return True
        elif value in ('false', 'no', '0', 'off'):
            return False
    
    try:
        return bool(value)
    except:
        return default

# String utilities
def truncate_string(text, max_length, ellipsis='...'):
    """
    Truncate string to maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        ellipsis: Ellipsis string
    
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(ellipsis)] + ellipsis

def slugify_string(text, allow_unicode=False):
    """
    Create slug from string.
    
    Args:
        text: Text to slugify
        allow_unicode: Allow unicode characters
    
    Returns:
        Slug string
    """
    return slugify(text, allow_unicode=allow_unicode)

def generate_unique_id(prefix='', length=8):
    """
    Generate unique ID.
    
    Args:
        prefix: ID prefix
        length: ID length
    
    Returns:
        Unique ID string
    """
    import uuid
    unique_part = str(uuid.uuid4())[:length]
    
    if prefix:
        return f"{prefix}_{unique_part}"
    
    return unique_part

def mask_sensitive_data(data, fields=None):
    """
    Mask sensitive data in dictionary.
    
    Args:
        data: Data dictionary
        fields: Fields to mask
    
    Returns:
        Masked data
    """
    if fields is None:
        fields = ['password', 'token', 'secret', 'key', 'ssn', 'credit_card']
    
    masked_data = data.copy()
    
    for key, value in masked_data.items():
        if isinstance(value, dict):
            masked_data[key] = mask_sensitive_data(value, fields)
        elif isinstance(value, str):
            for field in fields:
                if field in key.lower():
                    masked_data[key] = '********'
                    break
    
    return masked_data

# Date/Time utilities
def parse_date(date_string, formats=None):
    """
    Parse date string.
    
    Args:
        date_string: Date string
        formats: List of date formats
    
    Returns:
        datetime object or None
    """
    if formats is None:
        formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%d-%m-%Y',
            '%d/%m/%Y',
            '%m-%d-%Y',
            '%m/%d/%Y',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%fZ'
        ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    
    return None

def format_date(date_obj, format_str='%Y-%m-%d'):
    """
    Format date object.
    
    Args:
        date_obj: Date/datetime object
        format_str: Format string
    
    Returns:
        Formatted date string
    """
    if date_obj is None:
        return ''
    
    return date_obj.strftime(format_str)

def get_timezone_abbreviation(timezone_str):
    """
    Get timezone abbreviation.
    
    Args:
        timezone_str: Timezone string
    
    Returns:
        Timezone abbreviation
    """
    try:
        tz = pytz.timezone(timezone_str)
        now = timezone.now()
        return now.astimezone(tz).strftime('%Z')
    except:
        return timezone_str

def business_days_between(start_date, end_date):
    """
    Calculate business days between two dates.
    
    Args:
        start_date: Start date
        end_date: End date
    
    Returns:
        Number of business days
    """
    from datetime import timedelta
    
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    
    business_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        # Monday=0, Sunday=6
        if current_date.weekday() < 5:
            business_days += 1
        current_date += timedelta(days=1)
    
    return business_days

# File utilities
def get_file_size(file_path, human_readable=False):
    """
    Get file size.
    
    Args:
        file_path: File path
        human_readable: Return human-readable format
    
    Returns:
        File size
    """
    try:
        size = os.path.getsize(file_path)
        
        if human_readable:
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} PB"
        
        return size
        
    except:
        return 0

def get_file_extension(filename):
    """
    Get file extension.
    
    Args:
        filename: Filename
    
    Returns:
        File extension (without dot)
    """
    return os.path.splitext(filename)[1][1:].lower()

def is_safe_filename(filename):
    """
    Check if filename is safe.
    
    Args:
        filename: Filename
    
    Returns:
        True if filename is safe
    """
    # List of unsafe characters
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    
    for char in unsafe_chars:
        if char in filename:
            return False
    
    # Check for reserved names
    reserved_names = [
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]
    
    name_without_ext = os.path.splitext(filename)[0].upper()
    if name_without_ext in reserved_names:
        return False
    
    return True

def sanitize_filename(filename):
    """
    Sanitize filename.
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename
    """
    # Remove unsafe characters
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    
    # Remove multiple underscores
    filename = re.sub(r'_+', '_', filename)
    
    # Remove leading/trailing underscores and dots
    filename = filename.strip('_.')
    
    # Ensure filename is not empty
    if not filename:
        filename = 'unnamed_file'
    
    return filename

# Network utilities
def get_client_ip(request):
    """
    Get client IP address from request.
    
    Args:
        request: Django request object
    
    Returns:
        IP address string
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    return ip

def is_valid_ip(ip_address):
    """
    Check if IP address is valid.
    
    Args:
        ip_address: IP address string
    
    Returns:
        True if valid IP
    """
    import socket
    
    try:
        socket.inet_pton(socket.AF_INET, ip_address)
        return True
    except socket.error:
        try:
            socket.inet_pton(socket.AF_INET6, ip_address)
            return True
        except socket.error:
            return False

def get_domain_from_email(email):
    """
    Extract domain from email address.
    
    Args:
        email: Email address
    
    Returns:
        Domain string
    """
    try:
        return email.split('@')[1]
    except:
        return ''

# Performance utilities
def profile_function(func):
    """
    Profile function execution.
    
    Args:
        func: Function to profile
    
    Returns:
        Profiling results
    """
    import cProfile
    import pstats
    from io import StringIO
    
    def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        
        result = func(*args, **kwargs)
        
        pr.disable()
        s = StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats()
        
        logger.debug(f"Profile for {func.__name__}:\n{s.getvalue()}")
        
        return result
    
    return wrapper

def memory_usage():
    """
    Get current memory usage.
    
    Returns:
        Memory usage in MB
    """
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # MB

# Security utilities
def generate_csrf_token():
    """
    Generate CSRF token.
    
    Returns:
        CSRF token string
    """
    import secrets
    return secrets.token_hex(32)

def validate_csrf_token(token, session_token):
    """
    Validate CSRF token.
    
    Args:
        token: Token to validate
        session_token: Session token
    
    Returns:
        True if valid
    """
    import hmac
    
    try:
        return hmac.compare_digest(token, session_token)
    except:
        return False

def sanitize_html(html):
    """
    Sanitize HTML to prevent XSS.
    
    Args:
        html: HTML string
    
    Returns:
        Sanitized HTML
    """
    import bleach
    
    allowed_tags = bleach.sanitizer.ALLOWED_TAGS + [
        'p', 'br', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'strong', 'em', 'u', 's', 'blockquote', 'code', 'pre',
        'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td'
    ]
    
    allowed_attributes = bleach.sanitizer.ALLOWED_ATTRIBUTES.copy()
    allowed_attributes.update({
        '*': ['class', 'style'],
        'a': ['href', 'title', 'target'],
        'img': ['src', 'alt', 'title', 'width', 'height']
    })
    
    return bleach.clean(
        html,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True
    )

# QR Code and Barcode utilities
def generate_qr_code(data, filename=None, size=10):
    """
    Generate QR code.
    
    Args:
        data: Data to encode
        filename: Output filename
        size: QR code size
    
    Returns:
        QR code image bytes or filename
    """
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=size,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        if filename:
            img.save(filename)
            return filename
        else:
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            return buffer.getvalue()
            
    except Exception as e:
        logger.error(f"Failed to generate QR code: {e}")
        return None

def generate_barcode(data, barcode_type='code128', filename=None):
    """
    Generate barcode.
    
    Args:
        data: Data to encode
        barcode_type: Barcode type
        filename: Output filename
    
    Returns:
        Barcode image bytes or filename
    """
    try:
        barcode_class = barcode.get_barcode_class(barcode_type)
        barcode_image = barcode_class(data, writer=ImageWriter())
        
        if filename:
            barcode_image.save(filename)
            return filename
        else:
            buffer = BytesIO()
            barcode_image.write(buffer)
            return buffer.getvalue()
            
    except Exception as e:
        logger.error(f"Failed to generate barcode: {e}")
        return None

# Math utilities
def calculate_percentage(part, whole, decimal_places=2):
    """
    Calculate percentage.
    
    Args:
        part: Part value
        whole: Whole value
        decimal_places: Decimal places
    
    Returns:
        Percentage value
    """
    if whole == 0:
        return 0
    
    percentage = (part / whole) * 100
    return round(percentage, decimal_places)

def calculate_compound_interest(principal, rate, time, compounding_frequency=1):
    """
    Calculate compound interest.
    
    Args:
        principal: Initial amount
        rate: Annual interest rate (decimal)
        time: Time in years
        compounding_frequency: Compounding frequency per year
    
    Returns:
        Final amount
    """
    amount = principal * (1 + rate / compounding_frequency) ** (compounding_frequency * time)
    return round(amount, 2)

def calculate_moving_average(values, window_size):
    """
    Calculate moving average.
    
    Args:
        values: List of values
        window_size: Window size
    
    Returns:
        List of moving averages
    """
    if len(values) < window_size:
        return []
    
    moving_averages = []
    
    for i in range(len(values) - window_size + 1):
        window = values[i:i + window_size]
        average = sum(window) / window_size
        moving_averages.append(average)
    
    return moving_averages

# Statistics utilities
def calculate_statistics(values):
    """
    Calculate basic statistics.
    
    Args:
        values: List of values
    
    Returns:
        Dictionary of statistics
    """
    if not values:
        return {}
    
    values = [float(v) for v in values if v is not None]
    
    if not values:
        return {}
    
    stats = {
        'count': len(values),
        'mean': np.mean(values),
        'median': np.median(values),
        'std': np.std(values),
        'min': np.min(values),
        'max': np.max(values),
        'sum': np.sum(values),
        'q1': np.percentile(values, 25),
        'q3': np.percentile(values, 75),
        'iqr': np.percentile(values, 75) - np.percentile(values, 25)
    }
    
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in stats.items()}

# Color utilities
def hex_to_rgb(hex_color):
    """
    Convert hex color to RGB.
    
    Args:
        hex_color: Hex color string
    
    Returns:
        Tuple of (R, G, B)
    """
    hex_color = hex_color.lstrip('#')
    
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    """
    Convert RGB to hex color.
    
    Args:
        rgb: Tuple of (R, G, B)
    
    Returns:
        Hex color string
    """
    return '#%02x%02x%02x' % rgb

def get_contrast_color(hex_color):
    """
    Get contrasting color (black or white).
    
    Args:
        hex_color: Background color
    
    Returns:
        '#000000' or '#FFFFFF'
    """
    rgb = hex_to_rgb(hex_color)
    
    # Calculate luminance
    luminance = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255
    
    return '#000000' if luminance > 0.5 else '#FFFFFF'

# Validation utilities
def validate_credit_card(number):
    """
    Validate credit card number using Luhn algorithm.
    
    Args:
        number: Credit card number
    
    Returns:
        True if valid
    """
    try:
        digits = [int(d) for d in str(number) if d.isdigit()]
        
        if not digits:
            return False
        
        checksum = 0
        parity = len(digits) % 2
        
        for i, digit in enumerate(digits):
            if i % 2 == parity:
                digit *= 2
                if digit > 9:
                    digit -= 9
            checksum += digit
        
        return checksum % 10 == 0
        
    except:
        return False

def validate_postal_code(postal_code, country='US'):
    """
    Validate postal code.
    
    Args:
        postal_code: Postal code
        country: Country code
    
    Returns:
        True if valid
    """
    patterns = {
        'US': r'^\d{5}(-\d{4})?$',
        'CA': r'^[A-Z]\d[A-Z] \d[A-Z]\d$',
        'UK': r'^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$',
        'AU': r'^\d{4}$',
        'DE': r'^\d{5}$',
        'FR': r'^\d{5}$',
        'JP': r'^\d{3}-\d{4}$',
    }
    
    pattern = patterns.get(country.upper())
    
    if pattern:
        return bool(re.match(pattern, postal_code))
    
    return True  # Unknown country, assume valid

# URL utilities
def is_valid_url(url):
    """
    Check if URL is valid.
    
    Args:
        url: URL string
    
    Returns:
        True if valid URL
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def ensure_scheme(url, default_scheme='https'):
    """
    Ensure URL has scheme.
    
    Args:
        url: URL string
        default_scheme: Default scheme
    
    Returns:
        URL with scheme
    """
    if not url:
        return url
    
    if '://' not in url:
        return f"{default_scheme}://{url}"
    
    return url

def get_url_parameters(url):
    """
    Get URL query parameters.
    
    Args:
        url: URL string
    
    Returns:
        Dictionary of parameters
    """
    try:
        parsed = urlparse(url)
        from urllib.parse import parse_qs
        return parse_qs(parsed.query)
    except:
        return {}

# File format detection
def detect_file_type(file_path):
    """
    Detect file type.
    
    Args:
        file_path: File path
    
    Returns:
        File type string
    """
    import magic
    
    try:
        mime = magic.Magic(mime=True)
        return mime.from_file(file_path)
    except:
        # Fallback based on extension
        ext = get_file_extension(file_path).lower()
        
        mime_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'pdf': 'application/pdf',
            'txt': 'text/plain',
            'csv': 'text/csv',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }
        
        return mime_types.get(ext, 'application/octet-stream')

# Compression utilities
def compress_string(text, compression_level=6):
    """
    Compress string using gzip.
    
    Args:
        text: Text to compress
        compression_level: Compression level
    
    Returns:
        Compressed bytes
    """
    import gzip
    
    if isinstance(text, str):
        text = text.encode('utf-8')
    
    return gzip.compress(text, compresslevel=compression_level)

def decompress_string(compressed_bytes):
    """
    Decompress gzipped bytes.
    
    Args:
        compressed_bytes: Compressed bytes
    
    Returns:
        Decompressed string
    """
    import gzip
    
    try:
        decompressed = gzip.decompress(compressed_bytes)
        return decompressed.decode('utf-8')
    except:
        return None

# Checksum utilities
def calculate_checksum(file_path, algorithm='sha256'):
    """
    Calculate file checksum.
    
    Args:
        file_path: File path
        algorithm: Hash algorithm
    
    Returns:
        Checksum string
    """
    hash_func = getattr(hashlib, algorithm)()
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()

def verify_checksum(file_path, expected_checksum, algorithm='sha256'):
    """
    Verify file checksum.
    
    Args:
        file_path: File path
        expected_checksum: Expected checksum
        algorithm: Hash algorithm
    
    Returns:
        True if checksum matches
    """
    actual_checksum = calculate_checksum(file_path, algorithm)
    return actual_checksum == expected_checksum

# Image utilities
def resize_image(image_path, output_path, max_width=None, max_height=None, quality=85):
    """
    Resize image.
    
    Args:
        image_path: Input image path
        output_path: Output image path
        max_width: Maximum width
        max_height: Maximum height
        quality: JPEG quality
    
    Returns:
        True if successful
    """
    try:
        img = PILImage.open(image_path)
        
        # Calculate new dimensions
        width, height = img.size
        
        if max_width and max_height:
            # Maintain aspect ratio
            ratio = min(max_width / width, max_height / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
        elif max_width:
            ratio = max_width / width
            new_width = max_width
            new_height = int(height * ratio)
        elif max_height:
            ratio = max_height / height
            new_width = int(width * ratio)
            new_height = max_height
        else:
            new_width, new_height = width, height
        
        # Resize image
        img = img.resize((new_width, new_height), PILImage.Resampling.LANCZOS)
        
        # Save image
        if output_path.lower().endswith('.jpg') or output_path.lower().endswith('.jpeg'):
            img.save(output_path, 'JPEG', quality=quality)
        elif output_path.lower().endswith('.png'):
            img.save(output_path, 'PNG', optimize=True)
        else:
            img.save(output_path)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to resize image: {e}")
        return False

def compress_image(image_path, output_path, quality=85):
    """
    Compress image.
    
    Args:
        image_path: Input image path
        output_path: Output image path
        quality: JPEG quality (1-100)
    
    Returns:
        True if successful
    """
    try:
        img = PILImage.open(image_path)
        
        if image_path.lower().endswith('.jpg') or image_path.lower().endswith('.jpeg'):
            img.save(output_path, 'JPEG', quality=quality, optimize=True)
        elif image_path.lower().endswith('.png'):
            img.save(output_path, 'PNG', optimize=True)
        else:
            img.save(output_path)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to compress image: {e}")
        return False

# Data serialization
def serialize_to_json(data, pretty=False):
    """
    Serialize data to JSON.
    
    Args:
        data: Data to serialize
        pretty: Pretty print
    
    Returns:
        JSON string
    """
    try:
        if pretty:
            return json.dumps(data, indent=2, default=str, ensure_ascii=False)
        else:
            return json.dumps(data, default=str, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to serialize to JSON: {e}")
        return '{}'

def deserialize_from_json(json_string):
    """
    Deserialize JSON string.
    
    Args:
        json_string: JSON string
    
    Returns:
        Deserialized data
    """
    try:
        return json.loads(json_string)
    except Exception as e:
        logger.error(f"Failed to deserialize from JSON: {e}")
        return {}

# Configuration utilities
def load_config(config_file):
    """
    Load configuration from file.
    
    Args:
        config_file: Config file path
    
    Returns:
        Configuration dictionary
    """
    try:
        with open(config_file, 'r') as f:
            if config_file.endswith('.json'):
                return json.load(f)
            elif config_file.endswith('.yaml') or config_file.endswith('.yml'):
                import yaml
                return yaml.safe_load(f)
            elif config_file.endswith('.toml'):
                import toml
                return toml.load(f)
            else:
                # Assume INI format
                import configparser
                config = configparser.ConfigParser()
                config.read_file(f)
                return dict(config)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}

def save_config(config, config_file):
    """
    Save configuration to file.
    
    Args:
        config: Configuration dictionary
        config_file: Config file path
    
    Returns:
        True if successful
    """
    try:
        with open(config_file, 'w') as f:
            if config_file.endswith('.json'):
                json.dump(config, f, indent=2)
            elif config_file.endswith('.yaml') or config_file.endswith('.yml'):
                import yaml
                yaml.dump(config, f, default_flow_style=False)
            elif config_file.endswith('.toml'):
                import toml
                toml.dump(config, f)
            else:
                # Assume INI format
                import configparser
                config_parser = configparser.ConfigParser()
                config_parser.read_dict(config)
                config_parser.write(f)
        
        return True
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False

# Text processing
def extract_emails(text):
    """
    Extract email addresses from text.
    
    Args:
        text: Text to search
    
    Returns:
        List of email addresses
    """
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.findall(pattern, text)

def extract_phone_numbers(text, country='US'):
    """
    Extract phone numbers from text.
    
    Args:
        text: Text to search
        country: Country code
    
    Returns:
        List of phone numbers
    """
    try:
        numbers = []
        for match in phonenumbers.PhoneNumberMatcher(text, country):
            numbers.append(phonenumbers.format_number(
                match.number,
                phonenumbers.PhoneNumberFormat.E164
            ))
        return numbers
    except:
        # Fallback regex
        pattern = r'\+?\d[\d\s\-\(\)]{7,}\d'
        return re.findall(pattern, text)

def extract_urls(text):
    """
    Extract URLs from text.
    
    Args:
        text: Text to search
    
    Returns:
        List of URLs
    """
    pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*'
    return re.findall(pattern, text)

def count_words(text):
    """
    Count words in text.
    
    Args:
        text: Text
    
    Returns:
        Word count
    """
    words = re.findall(r'\b\w+\b', text)
    return len(words)

def count_characters(text, include_spaces=True):
    """
    Count characters in text.
    
    Args:
        text: Text
        include_spaces: Include spaces in count
    
    Returns:
        Character count
    """
    if include_spaces:
        return len(text)
    else:
        return len(text.replace(' ', '').replace('\n', '').replace('\t', ''))

# System information
def get_system_info():
    """
    Get system information.
    
    Returns:
        Dictionary of system info
    """
    import platform
    import psutil
    
    info = {
        'platform': platform.platform(),
        'system': platform.system(),
        'node': platform.node(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': platform.python_version(),
        'cpu_count': psutil.cpu_count(),
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_total': psutil.virtual_memory().total,
        'memory_available': psutil.virtual_memory().available,
        'memory_percent': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/').percent,
        'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat()
    }
    
    return info

def get_process_info():
    """
    Get current process information.
    
    Returns:
        Dictionary of process info
    """
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    
    info = {
        'pid': process.pid,
        'name': process.name(),
        'status': process.status(),
        'create_time': datetime.fromtimestamp(process.create_time()).isoformat(),
        'cpu_percent': process.cpu_percent(interval=0.1),
        'memory_percent': process.memory_percent(),
        'memory_rss': process.memory_info().rss,
        'memory_vms': process.memory_info().vms,
        'num_threads': process.num_threads(),
        'connections': len(process.connections()),
        'open_files': len(process.open_files()),
    }
    
    return info

# Performance monitoring
class PerformanceMonitor:
    """Monitor performance metrics."""
    
    def __init__(self):
        self.metrics = {}
        self.start_time = None
    
    def start(self, name):
        """Start timing for a metric."""
        self.metrics[name] = {
            'start': time.time(),
            'end': None,
            'duration': None
        }
    
    def stop(self, name):
        """Stop timing for a metric."""
        if name in self.metrics:
            self.metrics[name]['end'] = time.time()
            self.metrics[name]['duration'] = (
                self.metrics[name]['end'] - self.metrics[name]['start']
            )
    
    def get_metrics(self):
        """Get all metrics."""
        return self.metrics
    
    def get_report(self):
        """Get performance report."""
        report = {
            'total_duration': sum(
                m['duration'] for m in self.metrics.values() if m['duration']
            ),
            'metrics': self.metrics
        }
        
        return report

# Batch processing
class BatchProcessor:
    """Process items in batches."""
    
    def __init__(self, batch_size=100, max_workers=4):
        self.batch_size = batch_size
        self.max_workers = max_workers
    
    def process(self, items, process_func, *args, **kwargs):
        """
        Process items in batches.
        
        Args:
            items: List of items to process
            process_func: Function to process each batch
            *args, **kwargs: Additional arguments for process_func
        
        Returns:
            List of results
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = []
        
        # Split items into batches
        batches = list(chunk_list(items, self.batch_size))
        
        # Process batches in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(process_func, batch, *args, **kwargs): i
                for i, batch in enumerate(batches)
            }
            
            for future in as_completed(futures):
                try:
                    batch_result = future.result()
                    results.extend(batch_result)
                except Exception as e:
                    logger.error(f"Batch processing failed: {e}")
                    sentry_sdk.capture_exception(e)
        
        return results

# Cache utilities
class CacheManager:
    """Manage cache operations."""
    
    def __init__(self, prefix='', default_timeout=300):
        self.prefix = prefix
        self.default_timeout = default_timeout
    
    def make_key(self, key):
        """Make cache key with prefix."""
        return f"{self.prefix}:{key}" if self.prefix else key
    
    def get(self, key, default=None):
        """Get value from cache."""
        cache_key = self.make_key(key)
        return cache.get(cache_key, default)
    
    def set(self, key, value, timeout=None):
        """Set value in cache."""
        cache_key = self.make_key(key)
        timeout = timeout or self.default_timeout
        return cache.set(cache_key, value, timeout)
    
    def delete(self, key):
        """Delete value from cache."""
        cache_key = self.make_key(key)
        return cache.delete(cache_key)
    
    def clear(self):
        """Clear all cache entries with prefix."""
        if self.prefix:
            from django.core.cache.utils import make_template_fragment_key
            # This is a simplified approach
            # In production, you might need to use cache.clear() or iterate over keys
            pass
    
    def incr(self, key, delta=1):
        """Increment cache value."""
        cache_key = self.make_key(key)
        try:
            return cache.incr(cache_key, delta)
        except ValueError:
            cache.set(cache_key, delta)
            return delta
    
    def decr(self, key, delta=1):
        """Decrement cache value."""
        cache_key = self.make_key(key)
        try:
            return cache.decr(cache_key, delta)
        except ValueError:
            cache.set(cache_key, 0)
            return 0

# Error handling
class ErrorHandler:
    """Handle errors gracefully."""
    
    @staticmethod
    def handle_exception(func):
        """Decorator to handle exceptions."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                sentry_sdk.capture_exception(e)
                
                # Return default value based on return type annotations
                import inspect
                sig = inspect.signature(func)
                return_annotation = sig.return_annotation
                
                if return_annotation == str:
                    return ""
                elif return_annotation == int:
                    return 0
                elif return_annotation == float:
                    return 0.0
                elif return_annotation == bool:
                    return False
                elif return_annotation == list:
                    return []
                elif return_annotation == dict:
                    return {}
                else:
                    return None
        
        return wrapper

# Template rendering
def render_template_to_string(template_name, context):
    """
    Render template to string.
    
    Args:
        template_name: Template name
        context: Template context
    
    Returns:
        Rendered template string
    """
    try:
        return render_to_string(template_name, context)
    except Exception as e:
        logger.error(f"Failed to render template: {e}")
        return ""

def render_template_to_response(template_name, context, request=None):
    """
    Render template to HTTP response.
    
    Args:
        template_name: Template name
        context: Template context
        request: Django request object
    
    Returns:
        HTTP response
    """
    from django.shortcuts import render
    
    try:
        return render(request, template_name, context)
    except Exception as e:
        logger.error(f"Failed to render template response: {e}")
        from django.http import HttpResponseServerError
        return HttpResponseServerError("Template rendering failed")

# API response formatting
def api_response(
    success: bool,
    data: Any = None,
    message: str = "",
    status_code: int = 200,
    errors: List[str] = None
) -> Dict:
    """
    Format API response.
    
    Args:
        success: Success flag
        data: Response data
        message: Response message
        status_code: HTTP status code
        errors: List of errors
    
    Returns:
        Formatted response dictionary
    """
    response = {
        'success': success,
        'message': message,
        'timestamp': timezone.now().isoformat(),
    }
    
    if data is not None:
        response['data'] = data
    
    if errors:
        response['errors'] = errors
    
    return response

def api_error_response(
    message: str = "An error occurred",
    errors: List[str] = None,
    status_code: int = 400
) -> Dict:
    """
    Format API error response.
    
    Args:
        message: Error message
        errors: List of errors
        status_code: HTTP status code
    
    Returns:
        Formatted error response
    """
    return api_response(
        success=False,
        message=message,
        status_code=status_code,
        errors=errors or []
    )

def api_success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200
) -> Dict:
    """
    Format API success response.
    
    Args:
        data: Response data
        message: Success message
        status_code: HTTP status code
    
    Returns:
        Formatted success response
    """
    return api_response(
        success=True,
        data=data,
        message=message,
        status_code=status_code
    )

# Data transformation
def transform_data(data, mapping):
    """
    Transform data using mapping dictionary.
    
    Args:
        data: Input data
        mapping: Field mapping dictionary
    
    Returns:
        Transformed data
    """
    if isinstance(data, list):
        return [transform_data(item, mapping) for item in data]
    elif isinstance(data, dict):
        transformed = {}
        
        for old_key, new_key in mapping.items():
            if isinstance(new_key, dict):
                # Nested transformation
                if old_key in data:
                    transformed.update(transform_data(data[old_key], new_key))
            else:
                # Simple key rename
                if old_key in data:
                    transformed[new_key] = data[old_key]
        
        return transformed
    else:
        return data

def filter_data(data, include_fields=None, exclude_fields=None):
    """
    Filter data fields.
    
    Args:
        data: Input data
        include_fields: Fields to include
        exclude_fields: Fields to exclude
    
    Returns:
        Filtered data
    """
    if include_fields:
        if isinstance(data, list):
            return [
                {k: v for k, v in item.items() if k in include_fields}
                for item in data
            ]
        elif isinstance(data, dict):
            return {k: v for k, v in data.items() if k in include_fields}
    
    if exclude_fields:
        if isinstance(data, list):
            return [
                {k: v for k, v in item.items() if k not in exclude_fields}
                for item in data
            ]
        elif isinstance(data, dict):
            return {k: v for k, v in data.items() if k not in exclude_fields}
    
    return data

def sort_data(data, key, reverse=False):
    """
    Sort data by key.
    
    Args:
        data: List of dictionaries
        key: Sort key
        reverse: Reverse sort
    
    Returns:
        Sorted data
    """
    if not data:
        return data
    
    return sorted(data, key=lambda x: x.get(key), reverse=reverse)

def group_data(data, key):
    """
    Group data by key.
    
    Args:
        data: List of dictionaries
        key: Group key
    
    Returns:
        Grouped data dictionary
    """
    grouped = {}
    
    for item in data:
        group_key = item.get(key)
        if group_key not in grouped:
            grouped[group_key] = []
        grouped[group_key].append(item)
    
    return grouped

# Export utilities
def export_data_formats(data, format_type, **kwargs):
    """
    Export data in different formats.
    
    Args:
        data: Data to export
        format_type: Export format
        **kwargs: Format-specific options
    
    Returns:
        Exported data
    """
    if format_type == 'json':
        return json.dumps(data, indent=2, default=str)
    elif format_type == 'csv':
        import csv
        output = StringIO()
        
        if data and isinstance(data, list):
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        
        return output.getvalue()
    elif format_type == 'xml':
        from xml.etree.ElementTree import Element, tostring
        
        root = Element('data')
        
        if isinstance(data, list):
            for item in data:
                element = Element('item')
                for key, value in item.items():
                    child = Element(key)
                    child.text = str(value)
                    element.append(child)
                root.append(element)
        elif isinstance(data, dict):
            for key, value in data.items():
                element = Element(key)
                element.text = str(value)
                root.append(element)
        
        return tostring(root, encoding='unicode')
    else:
        raise ValueError(f"Unsupported format: {format_type}")

# Import utilities
def import_data_formats(data_string, format_type, **kwargs):
    """
    Import data from different formats.
    
    Args:
        data_string: Data string
        format_type: Import format
        **kwargs: Format-specific options
    
    Returns:
        Imported data
    """
    if format_type == 'json':
        return json.loads(data_string)
    elif format_type == 'csv':
        import csv
        reader = csv.DictReader(data_string.splitlines())
        return list(reader)
    elif format_type == 'xml':
        from xml.etree.ElementTree import fromstring
        
        root = fromstring(data_string)
        data = []
        
        for item in root.findall('item'):
            data_item = {}
            for child in item:
                data_item[child.tag] = child.text
            data.append(data_item)
        
        return data
    else:
        raise ValueError(f"Unsupported format: {format_type}")

# Main utility function registry
class UtilityRegistry:
    """Registry for utility functions."""
    
    def __init__(self):
        self.functions = {}
    
    def register(self, name, func):
        """Register a utility function."""
        self.functions[name] = func
    
    def get(self, name):
        """Get a utility function."""
        return self.functions.get(name)
    
    def list(self):
        """List all registered functions."""
        return list(self.functions.keys())

# Create global registry instance
registry = UtilityRegistry()

# Register core utilities
registry.register('send_email_template', send_email_template)
registry.register('send_slack_notification', send_slack_notification)
registry.register('format_currency', format_currency)
registry.register('calculate_tax', calculate_tax)
registry.register('generate_pdf', generate_pdf)
registry.register('validate_data', validate_data)
registry.register('generate_report_data', generate_report_data)
registry.register('export_to_csv', export_to_csv)
registry.register('export_to_excel', export_to_excel)
registry.register('backup_database', backup_database)
registry.register('cleanup_old_files', cleanup_old_files)
registry.register('compress_files', compress_files)
registry.register('encrypt_data', encrypt_data)
registry.register('decrypt_data', decrypt_data)
registry.register('sync_with_external_service', sync_with_external_service)
registry.register('check_api_health', check_api_health)
registry.register('rate_limit_check', rate_limit_check)
registry.register('get_exchange_rate', get_exchange_rate)
registry.register('convert_currency', convert_currency)
registry.register('generate_random_string', generate_random_string)
registry.register('hash_password', hash_password)
registry.register('verify_password', verify_password)
registry.register('generate_jwt_token', generate_jwt_token)
registry.register('verify_jwt_token', verify_jwt_token)
registry.register('create_short_url', create_short_url)
registry.register('validate_url', validate_url)
registry.register('extract_domain', extract_domain)
registry.register('parse_csv_file', parse_csv_file)
registry.register('parse_json_file', parse_json_file)
registry.register('validate_email_format', validate_email_format)
registry.register('validate_phone_number', validate_phone_number)
registry.register('geocode_address', geocode_address)
registry.register('calculate_distance', calculate_distance)
registry.register('get_weather_data', get_weather_data)
registry.register('get_location_info', get_location_info)
registry.register('send_sms', send_sms)
registry.register('make_phone_call', make_phone_call)

# Export commonly used utilities
__all__ = [
    'send_email_template',
    'send_slack_notification',
    'format_currency',
    'calculate_tax',
    'generate_pdf',
    'validate_data',
    'generate_report_data',
    'export_to_csv',
    'export_to_excel',
    'backup_database',
    'cleanup_old_files',
    'compress_files',
    'encrypt_data',
    'decrypt_data',
    'sync_with_external_service',
    'check_api_health',
    'rate_limit_check',
    'get_exchange_rate',
    'convert_currency',
    'generate_random_string',
    'hash_password',
    'verify_password',
    'generate_jwt_token',
    'verify_jwt_token',
    'create_short_url',
    'validate_url',
    'extract_domain',
    'parse_csv_file',
    'parse_json_file',
    'validate_email_format',
    'validate_phone_number',
    'geocode_address',
    'calculate_distance',
    'get_weather_data',
    'get_location_info',
    'send_sms',
    'make_phone_call',
    'retry',
    'timing',
    'cache_result',
    'require_auth',
    'admin_required',
    'Timer',
    'DatabaseTransaction',
    'ValidationError',
    'ExternalServiceError',
    'RateLimitExceeded',
    'ConfigurationError',
    'dict_to_model',
    'model_to_dict',
    'flatten_dict',
    'chunk_list',
    'safe_int',
    'safe_float',
    'safe_bool',
    'truncate_string',
    'slugify_string',
    'generate_unique_id',
    'mask_sensitive_data',
    'parse_date',
    'format_date',
    'get_timezone_abbreviation',
    'business_days_between',
    'get_file_size',
    'get_file_extension',
    'is_safe_filename',
    'sanitize_filename',
    'get_client_ip',
    'is_valid_ip',
    'get_domain_from_email',
    'profile_function',
    'memory_usage',
    'generate_csrf_token',
    'validate_csrf_token',
    'sanitize_html',
    'generate_qr_code',
    'generate_barcode',
    'calculate_percentage',
    'calculate_compound_interest',
    'calculate_moving_average',
    'calculate_statistics',
    'hex_to_rgb',
    'rgb_to_hex',
    'get_contrast_color',
    'validate_credit_card',
    'validate_postal_code',
    'is_valid_url',
    'ensure_scheme',
    'get_url_parameters',
    'detect_file_type',
    'compress_string',
    'decompress_string',
    'calculate_checksum',
    'verify_checksum',
    'resize_image',
    'compress_image',
    'serialize_to_json',
    'deserialize_from_json',
    'load_config',
    'save_config',
    'extract_emails',
    'extract_phone_numbers',
    'extract_urls',
    'count_words',
    'count_characters',
    'get_system_info',
    'get_process_info',
    'PerformanceMonitor',
    'BatchProcessor',
    'CacheManager',
    'ErrorHandler',
    'render_template_to_string',
    'render_template_to_response',
    'api_response',
    'api_error_response',
    'api_success_response',
    'transform_data',
    'filter_data',
    'sort_data',
    'group_data',
    'export_data_formats',
    'import_data_formats',
    'registry',
]



class NotificationValidator:
    """নোটিফিকেশন ডাটা ভ্যালিডেশন করার জন্য ক্লাস"""
    @staticmethod
    def validate_payload(data):
        if not data.get('title') or not data.get('message'):
            return False, "Title and message are required"
        return True, None

class EncryptionService:
    """নোটিফিকেশন মেটাডেটা বা সেনসিটিভ ডাটা এনক্রিপ্ট করার জন্য (বেসিক স্ট্রাকচার)"""
    @staticmethod
    def encrypt(text):
        # আপাতত শুধু টেক্সট রিটার্ন করছি, আপনার প্রয়োজন হলে এখানে logic যোগ করবেন
        return text

    @staticmethod
    def decrypt(text):
        return text

class TemplateRenderer:
    """টেমপ্লেট রেন্ডার করার জন্য ক্লাস"""
    @staticmethod
    def render(template_content, context):
        from django.template import Template, Context
        try:
            t = Template(template_content)
            return t.render(Context(context))
        except Exception:
            return template_content