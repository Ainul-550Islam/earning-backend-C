# api/payment_gateways/sdk_generator.py
# SDK code generator for advertisers and publishers
import logging
from django.conf import settings
logger=logging.getLogger(__name__)
BASE_URL=getattr(settings,'SITE_URL','https://yourdomain.com') if settings.configured else ''

class SDKGenerator:
    def generate_js_sdk(self,publisher):
        return f"""// Payment Gateway SDK — Publisher {publisher.id}
(function(w,d){{
  w.PG=w.PG||{{}};
  w.PG.config={{'publisherId':{publisher.id},'baseUrl':'{BASE_URL}'}};
  w.PG.track=function(event,data){{
    var xhr=new XMLHttpRequest();
    xhr.open('POST','{BASE_URL}/api/payment/tracking/events/');
    xhr.setRequestHeader('Content-Type','application/json');
    xhr.send(JSON.stringify({{publisher_id:{publisher.id},event:event,data:data||{{}}}}))}};
  w.PG.click=function(offerId,sub1){{window.location='{BASE_URL}/api/payment/tracking/click/?aff_id={publisher.id}&offer_id='+offerId+(sub1?'&sub1='+sub1:'');}};
}})(window,document);"""
    def generate_python_sdk_config(self,api_key):
        return f"""# Payment Gateway Python Client
import requests
API_KEY='{api_key}'
BASE_URL='{BASE_URL}/api/payment'
def get_offers(country='',device=''):
    r=requests.get(f'{{BASE_URL}}/offers/',headers={{'Authorization':f'Bearer {{API_KEY}}'}},params={{'country':country,'device':device}})
    return r.json()
def record_conversion(click_id,payout=0,status='approved'):
    r=requests.get(f'{{BASE_URL}}/tracking/postback/',params={{'click_id':click_id,'payout':payout,'status':status}},headers={{'Authorization':f'Bearer {{API_KEY}}'}})
    return r.json()
"""
    def generate_android_config(self,publisher_id,app_id=''):
        return {'sdk_version':'2.0','publisher_id':publisher_id,'app_id':app_id,'base_url':BASE_URL,'click_endpoint':f'{BASE_URL}/api/payment/tracking/click/','postback_endpoint':f'{BASE_URL}/api/payment/tracking/postback/','offerwall_endpoint':f'{BASE_URL}/api/payment/locker/offerwalls/'}
sdk_generator=SDKGenerator()
