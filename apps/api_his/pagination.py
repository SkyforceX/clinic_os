# apps/api_his/pagination.py
from rest_framework.pagination import PageNumberPagination
from rest_framework.utils.urls import replace_query_param, remove_query_param

class RelativePageNumberPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000

    def get_next_link(self):
        if not self.page.has_next(): return None
        url = self.request.get_full_path()
        return replace_query_param(url, self.page_query_param, self.page.next_page_number())

    def get_previous_link(self):
        if not self.page.has_previous(): return None
        url = self.request.get_full_path()
        if self.page.previous_page_number() == 1:
            return remove_query_param(url, self.page_query_param)
        return replace_query_param(url, self.page_query_param, self.page.previous_page_number())
