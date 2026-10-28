# api/cms/services_new/ContentBlockService.py
"""StreamField / Content Block Service. CMS owns this."""
import logging
from typing import Dict, Any, List, Optional
logger = logging.getLogger(__name__)

BLOCK_DEFAULTS = {
    'rich_text': {'content': '', 'format': 'html'},
    'image':     {'url': '', 'alt': '', 'caption': '', 'width': 'full'},
    'video':     {'url': '', 'provider': 'youtube', 'caption': ''},
    'cta':       {'text': '', 'button_text': 'Click here', 'button_url': '', 'style': 'primary'},
    'quote':     {'text': '', 'author': '', 'source': ''},
    'html':      {'content': ''},
    'code':      {'content': '', 'language': 'python', 'show_line_numbers': True},
    'divider':   {'style': 'line'},
    'gallery':   {'images': [], 'columns': 3},
    'table':     {'headers': [], 'rows': []},
    'accordion': {'items': []},
    'embed':     {'url': '', 'type': 'iframe', 'height': 400},
    'offerwall': {'config_id': None, 'title': 'Earn Coins'},
    'locker':    {'locker_id': None, 'preview_text': ''},
}


class ContentBlockService:

    @staticmethod
    def get_blocks(parent_type: str, parent_id: int) -> List[Dict]:
        from api.cms.models_new.blocks import ContentBlock
        blocks = ContentBlock.get_blocks_for(parent_type, parent_id)
        return [ContentBlockService._serialize(b) for b in blocks]

    @staticmethod
    def _serialize(block) -> Dict:
        return {
            'id': block.id, 'uuid': str(block.uuid),
            'block_type': block.block_type, 'order': block.order,
            'data': block.data, 'css_class': block.css_class,
            'is_visible': block.is_visible,
            'preview': block.render_preview(),
        }

    @staticmethod
    def add_block(parent_type: str, parent_id: int, block_type: str,
                  data: dict = None, order: int = None, user=None) -> Dict:
        from api.cms.models_new.blocks import ContentBlock
        if order is None:
            last = ContentBlock.objects.filter(
                parent_type=parent_type, parent_id=parent_id
            ).order_by('-order').values_list('order', flat=True).first()
            order = (last or -1) + 1
        block_data = dict(BLOCK_DEFAULTS.get(block_type, {}))
        if data:
            block_data.update(data)
        text_content = ''
        if block_type == 'rich_text':
            text_content = data.get('content', '') if data else ''
        block = ContentBlock.objects.create(
            parent_type=parent_type, parent_id=parent_id,
            block_type=block_type, order=order,
            data=block_data, text_content=text_content,
            created_by=user,
        )
        return ContentBlockService._serialize(block)

    @staticmethod
    def update_block(block_id: int, data: dict = None,
                     order: int = None, is_visible: bool = None) -> Optional[Dict]:
        from api.cms.models_new.blocks import ContentBlock
        try:
            block = ContentBlock.objects.get(id=block_id)
            update_fields = ['updated_at']
            if data is not None:
                block.data = data
                update_fields.append('data')
                if block.block_type == 'rich_text':
                    block.text_content = data.get('content', '')
                    update_fields.append('text_content')
            if order is not None:
                block.order = order
                update_fields.append('order')
            if is_visible is not None:
                block.is_visible = is_visible
                update_fields.append('is_visible')
            block.save(update_fields=update_fields)
            return ContentBlockService._serialize(block)
        except ContentBlock.DoesNotExist:
            return None

    @staticmethod
    def delete_block(block_id: int) -> bool:
        from api.cms.models_new.blocks import ContentBlock
        try:
            ContentBlock.objects.get(id=block_id).delete()
            return True
        except ContentBlock.DoesNotExist:
            return False

    @staticmethod
    def reorder_blocks(parent_type: str, parent_id: int, block_ids: List[int]) -> bool:
        from api.cms.models_new.blocks import ContentBlock
        try:
            for order, block_id in enumerate(block_ids):
                ContentBlock.objects.filter(
                    id=block_id, parent_type=parent_type, parent_id=parent_id
                ).update(order=order)
            return True
        except Exception as e:
            logger.error(f"Reorder blocks failed: {e}")
            return False

    @staticmethod
    def render_blocks(parent_type: str, parent_id: int) -> str:
        """Render all blocks to HTML string."""
        blocks = ContentBlockService.get_blocks(parent_type, parent_id)
        html_parts = []
        for block in blocks:
            html_parts.append(ContentBlockService._render_block(block))
        return '\n'.join(html_parts)

    @staticmethod
    def _render_block(block: dict) -> str:
        bt = block['block_type']
        data = block['data']
        css = f" {block['css_class']}" if block['css_class'] else ''
        if bt == 'rich_text':
            return f'<div class="cms-block cms-rich-text{css}">{data.get("content","")}</div>'
        elif bt == 'image':
            return f'<figure class="cms-block cms-image{css}"><img src="{data.get("url","")}" alt="{data.get("alt","")}" /><figcaption>{data.get("caption","")}</figcaption></figure>'
        elif bt == 'quote':
            return f'<blockquote class="cms-block cms-quote{css}"><p>{data.get("text","")}</p><cite>— {data.get("author","")}</cite></blockquote>'
        elif bt == 'divider':
            return f'<hr class="cms-block cms-divider{css}" />'
        elif bt == 'cta':
            return f'<div class="cms-block cms-cta{css}"><p>{data.get("text","")}</p><a href="{data.get("button_url","#")}" class="btn btn-{data.get("style","primary")}">{data.get("button_text","Click here")}</a></div>'
        elif bt == 'code':
            return f'<pre class="cms-block cms-code{css}"><code class="language-{data.get("language","text")}">{data.get("content","")}</code></pre>'
        return f'<div class="cms-block cms-{bt}{css}"><!-- {bt} block --></div>'
