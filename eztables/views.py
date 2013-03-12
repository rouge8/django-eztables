# -*- coding: utf-8 -*-
import json
import re

from operator import or_

from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import View
from django.views.generic.list import MultipleObjectMixin

from eztables.forms import DatatablesForm, DESC


JSON_MIMETYPE = 'application/json'

RE_FORMATTED = re.compile(r'\{(\w+)\}')


class DatatablesView(MultipleObjectMixin, View):
    '''
    Render a paginated server-side Datatables JSON view.

    See: http://www.datatables.net/usage/server-side
    '''
    fields = []
    search_fields = []
    _callables = None
    _db_fields = None
    _db_search_fields = None

    def post(self, request, *args, **kwargs):
        return self.process_dt_response(request.POST)

    def get(self, request, *args, **kwargs):
        return self.process_dt_response(request.GET)

    def process_dt_response(self, data):
        self.form = DatatablesForm(data)
        if self.form.is_valid():
            qs = self.get_queryset()
            # convert to a list so you can reassign entries
            self.object_list = list(qs.values(*self.get_db_fields()))
            if self.get_callables():
                for i, obj in enumerate(qs):
                    for key, f in self.get_callables().items():
                        self.object_list[i][key] = f(obj)
            return self.render_to_response(self.form)
        else:
            return HttpResponseBadRequest()

    def get_callables(self):
        if isinstance(self.fields, dict) and not self._callables:
            self._callables = dict([
                (key, value) for key, value in self.fields.items()
                if hasattr(value, '__call__')
            ])
        return self._callables

    def get_db_fields(self):
        if not self._db_fields:
            self._db_fields = self._get_fields(self.fields)
        return self._db_fields

    def get_search_fields(self):
        if not self._db_search_fields:
            self._db_search_fields = self._get_fields(self.search_fields or
                                                      self.fields)
        return self._db_search_fields

    def _get_fields(self, fields):
        out_fields = []
        fields = fields.values() if isinstance(fields, dict) else fields
        for field in fields:
            if not isinstance(field, basestring):
                continue
            if RE_FORMATTED.match(field):
                out_fields.extend(RE_FORMATTED.findall(field))
            else:
                out_fields.append(field)
        return out_fields

    @property
    def dt_data(self):
        return self.form.cleaned_data

    def get_field(self, index):
        if isinstance(self.fields, dict):
            return self.fields[self.dt_data['mDataProp_%s' % index]]
        else:
            return self.fields[index]

    def get_orders(self):
        '''Get ordering fields for ``QuerySet.order_by``'''
        orders = []
        iSortingCols = self.dt_data['iSortingCols']
        dt_orders = [(self.dt_data['iSortCol_%s' % i], self.dt_data['sSortDir_%s' % i]) for i in xrange(iSortingCols)]
        for field_idx, field_dir in dt_orders:
            direction = '-' if field_dir == DESC else ''
            if hasattr(self, 'sort_col_%s' % field_idx):
                method = getattr(self, 'sort_col_%s' % field_idx)
                result = method(direction)
                if isinstance(result, str):
                    orders.append(result)
                else:
                    orders.extend(result)
            else:
                field = self.get_field(field_idx)
                if RE_FORMATTED.match(field):
                    tokens = RE_FORMATTED.findall(field)
                    orders.extend(['%s%s' % (direction, token) for token in tokens])
                else:
                    orders.append('%s%s' % (direction, field))
        return orders

    def global_search(self, queryset):
        '''Filter a queryset with global search'''
        search = self.dt_data['sSearch']
        if search:
            if self.dt_data['bRegex']:
                criterions = (Q(**{'%s__iregex' % field: search}) for field in self.get_search_fields())
                search = reduce(or_, criterions)
                queryset = queryset.filter(search)
            else:
                for term in search.split():
                    criterions = (Q(**{'%s__icontains' % field: term}) for field in self.get_search_fields())
                    search = reduce(or_, criterions)
                    queryset = queryset.filter(search)
        return queryset

    def column_search(self, queryset):
        '''Filter a queryset with column search'''
        for idx in xrange(self.dt_data['iColumns']):
            search = self.dt_data['sSearch_%s' % idx]
            if search:
                if hasattr(self, 'search_col_%s' % idx):
                    custom_search = getattr(self, 'search_col_%s' % idx)
                    queryset = custom_search(search, queryset)
                else:
                    field = self.get_field(idx)
                    fields = RE_FORMATTED.findall(field) if RE_FORMATTED.match(field) else [field]
                    if self.dt_data['bRegex_%s' % idx]:
                        criterions = (Q(**{'%s__iregex' % field: search}) for field in fields)
                        search = reduce(or_, criterions)
                        queryset = queryset.filter(search)
                    else:
                        for term in search.split():
                            criterions = (Q(**{'%s__icontains' % field: term}) for field in fields)
                            search = reduce(or_, criterions)
                            queryset = queryset.filter(search)
        return queryset

    def get_queryset(self):
        '''Apply Datatables sort and search criterion to QuerySet'''
        qs = super(DatatablesView, self).get_queryset()
        # Perform global search
        qs = self.global_search(qs)
        # Perform column search
        qs = self.column_search(qs)
        # Return the ordered queryset
        return qs.order_by(*self.get_orders())

    def get_page(self, form):
        '''Get the requested page'''
        page_size = form.cleaned_data['iDisplayLength']
        start_index = form.cleaned_data['iDisplayStart']
        paginator = Paginator(self.object_list, page_size)
        num_page = (start_index / page_size) + 1
        return paginator.page(num_page)

    def get_rows(self, rows):
        '''Format all rows'''
        return [self.get_row(row) for row in rows]

    def get_row(self, row):
        '''Format a single row (if necessary)'''

        if isinstance(self.fields, dict):
            d = {}
            for key, value in self.fields.items():
                if isinstance(value, basestring):
                    d[key] = unicode(value).format(**row) if RE_FORMATTED.match(value) else row[value]
                elif hasattr(value, '__call__'):
                    d[key] = row[key]
            return d
        else:
            return [unicode(field).format(**row) if RE_FORMATTED.match(field) else row[field] for field in self.fields]

    def render_to_response(self, form, **kwargs):
        '''Render Datatables expected JSON format'''
        page = self.get_page(form)
        data = {
            'iTotalRecords': page.paginator.count,
            'iTotalDisplayRecords': page.paginator.count,
            'sEcho': form.cleaned_data['sEcho'],
            'aaData': self.get_rows(page.object_list),
        }
        return self.json_response(data)

    def json_response(self, data):
        return HttpResponse(
            json.dumps(data, cls=DjangoJSONEncoder),
            mimetype=JSON_MIMETYPE
        )
