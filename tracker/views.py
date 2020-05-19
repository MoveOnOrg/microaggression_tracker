import datetime

from django.conf import settings
from django.shortcuts import render
from django_redis import get_redis_connection

from tracker.models import Report

REDIS_CONN = None

def _redis_connection():
    global REDIS_CONN
    if REDIS_CONN is None:
        try:
            REDIS_CONN = get_redis_connection('redis')
        except Exception as err:
            REDIS_CONN = False
    return REDIS_CONN

def month_prefix(monthchoice):
    prefix = getattr(settings, 'CACHE_PREFIX', '')
    return f'{prefix}ma{monthchoice}'
        


def track(request):
    mgroups = settings.MICROAGGRESSION_GROUPS
    redis = _redis_connection()
    # redis.hget(x, y)
    #redis.expire
    # redis.ltrim
    # redis.lpush
    if request.method == 'POST':
        now = datetime.datetime.now()
        # 1. iterate on mgroups to process if they are present
        #    and hincr into month report
        cur = month_prefix(now.strftime('%Y%m'))
        group_report_key = f'{cur}_track'
        for mgroup in mgroups:
            name = mgroup['name']
            val = request.POST.get(name)
            if val:
                redis.hincrby(f'{group_report_key}_{name}', val, 1)
        # 2. see if words submitted and lpush into month
        words = request.POST.get('words')
        if words:
            redis.lpush(f'{cur}__words', words)
        # 3. check if last month record exists in cache
        #    if so, check if last month record exists in db
        #       if not, then save record to db
        last = (now.replace(month=now.month -1)
                if now.month != 1 else
                now.replace(year=now.year - 1, month=12))
        lastmonth = last.strftime('%Y%m')
        Report.
        