"""
Custom pagination classes for ES-NL2DSL API
"""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from collections import OrderedDict

class QueryTaskPagination(PageNumberPagination):
    """
    Pagination for query tasks with enhanced metadata
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('page_size', self.get_page_size(self.request)),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))

class QueryExecutionPagination(PageNumberPagination):
    """
    Pagination for query execution results
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50

class StandardPagination(PageNumberPagination):
    """
    Standard pagination for general use
    """
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100