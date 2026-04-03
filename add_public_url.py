content = open('api/offerwall/urls.py', encoding='utf-8').read()

old = 'urlpatterns = ['
new = '''from .views import PublicOfferListView
urlpatterns = [
    path('public/', PublicOfferListView.as_view(), name='public-offers'),'''

content = content.replace(old, new, 1)
open('api/offerwall/urls.py', 'w', encoding='utf-8').write(content)
print('SUCCESS')
