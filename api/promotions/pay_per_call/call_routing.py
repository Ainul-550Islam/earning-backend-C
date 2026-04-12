# =============================================================================
# promotions/pay_per_call/call_routing.py
# Call Routing — Route calls to correct advertiser number
# =============================================================================


class CallRouter:
    """Route inbound tracked calls to advertiser's destination."""

    def get_routing_instructions(self, tracking_id: str) -> dict:
        """Get Twilio-compatible routing instructions."""
        from django.core.cache import cache
        number_data = cache.get(f'ppc_number:{tracking_id}', {})
        if not number_data:
            return {'error': 'Tracking number not found'}
        return {
            'destination': number_data.get('destination_number'),
            'record': True,
            'timeout': 30,
            'twiml': f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial timeout="30" record="record-from-answer" action="/api/promotions/calls/complete/">
        <Number>{number_data.get("destination_number")}</Number>
    </Dial>
</Response>''',
        }
