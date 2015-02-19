import datetime
import json
import decimal

from django.http import HttpResponse
from django.db import models
from django.core import serializers
from django.db.models import query
from django.forms.models import model_to_dict
from django.conf import settings
from django.contrib.auth.decorators import login_required

def configurable_login_required(function):
    def wrapper(*args, **kw):
        if globals()['settings'].WEB_LOCKDOWN:
            curried_page = login_required(function)
            return curried_page(*args, **kw)
        else:
            return function(*args, **kw)
    return wrapper

class jsonres(object):
    def __init__(self, f):
        self._f = f

    def __call__(self, *args, **kwargs):
        res = self._f(*args, **kwargs)
        if isinstance(res, query.QuerySet):
            j = serializers.serialize('json', res)
        else:
            j = json.dumps(res, indent=2, cls=JSONEncoder)
        return HttpResponse(j, content_type='application/json')


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        if isinstance(o, datetime.date):
            return '%i-%02i-%02i' % (o.year, o.month, o.day)
        if isinstance(o, datetime.time):
            return '%i:%s' % (o.hour, o.minute)
        if isinstance(o, models.Model):
            return model_to_dict(o)
        return super(JSONEncoder, self).default(o)
