# kyc/pagination.py  ── WORLD #1
from rest_framework.pagination import PageNumberPagination


class KYCDefaultPagination(PageNumberPagination):
    page_size            = 20
    max_page_size        = 100
    page_size_query_param = 'page_size'


class KYCAdminPagination(PageNumberPagination):
    page_size            = 50
    max_page_size        = 200
    page_size_query_param = 'page_size'


class KYCLargePagination(PageNumberPagination):
    page_size            = 100
    max_page_size        = 500
    page_size_query_param = 'page_size'
