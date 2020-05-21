import datetime

from django.conf import settings
from django.shortcuts import render
from django_redis import get_redis_connection

#from tracker.models import Report

REDIS_CONN = None

def _redis_connection():
    global REDIS_CONN
    if REDIS_CONN is None:
        REDIS_CONN = get_redis_connection('redis')
    return REDIS_CONN

def month_prefix(monthchoice):
    prefix = getattr(settings, 'CACHE_PREFIX', '')
    return f'{prefix}ma{monthchoice}'
        
def last_month(redis):
    now = datetime.datetime.now()
    code = datetime.datetime(now.year - 1, 12, 1).strftime('%Y%m')
    if now.month != 1:
        code = datetime.datetime(now.year, now.month - 1, 1).strftime('%Y%m')
    lastmonth_has_report = redis.get('{}_submissions'.format(month_prefix(code)))
    if lastmonth_has_report:
        return code

def form(request):
    mgroups = settings.MICROAGGRESSION_GROUPS
    redis = _redis_connection()
    if request.method == 'POST':
        now = datetime.datetime.now()
        # 1. iterate on mgroups to process if they are present
        #    and hincr into month report
        cur = month_prefix(now.strftime('%Y%m'))
        redis.incr(f'{cur}_submissions')
        group_report_key = f'{cur}_track'
        for mgroup in mgroups:
            name = mgroup['name']
            vals = request.POST.getlist(name)
            for val in vals:
                redis.hincrby(f'{group_report_key}_{name}_values', val, 1)
                # TODO: expire (maybe a couple months after deploy)
            if mgroup.get('other_textfield'):
                other_val = request.POST.get(f'{name}_other')
                if other_val:
                    redis.hincrby(f'{group_report_key}_{name}_other', other_val, 1)
        # 2. see if words submitted and lpush into month
        words = request.POST.get('words')
        if words:
            redis.lpush(f'{cur}_words', words)
        return render(request, 'tracker/thanks.html', {'questions': mgroups })
    return render(request, 'tracker/form.html', {'questions': mgroups })


def monthreport(request, yearmonth):
    mgroups = settings.MICROAGGRESSION_GROUPS
    minfilter = {g['name']:g['minimum'] for g in mgroups
                 if g.get('minimum')}
    redis = _redis_connection()

    yearmonth_dt = datetime.datetime.strptime(yearmonth, '%Y%m')
    now = datetime.datetime.now()
    context = {
        'last_month': last_month(redis),
    }
    if yearmonth_dt.year >= now.year and yearmonth_dt.month >= now.month:
        context.update({'notready': True })
    else:
        cur = month_prefix(yearmonth)
        words = [w.decode() for w in (redis.lrange(f'{cur}_words', 0, -1) or [])]
        keys = redis.keys(f'{cur}_track*')
        results = {}
        for key in keys:
            valother, name, *rest = reversed(key.decode().split('_'))
            obj = results.setdefault(name, {})
            obj[valother] = {a.decode():b.decode() for a,b in redis.hgetall(key).items()}
            minimum = minfilter.get(name)
            if minimum:
                obj['minimum'] = minimum
        # FUTURE?  should we defer to current mgroups or leave older report values alone?
        # Pro: questions would be ordered reliably (could also alphabetize)
        context.update({
            'results': sorted(results.items()),
            'count': int((redis.get(f'{cur}_submissions') or b'').decode() or 0),
            'words': words,
        })
    return render(request, 'tracker/report.html', context)

