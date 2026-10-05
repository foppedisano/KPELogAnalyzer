"""Validated analytical adapters; reuse UI calculations without opening raw logs."""
import json

from .geo_temporal import SIZES
from .perceptual import METHOD


def schema(properties, required):
    return dict(type='object', properties=properties, required=required, additionalProperties=False)


ID = dict(type='integer', minimum=1)
CALL_IDS = dict(type='array', minItems=1, maxItems=20, items=ID)
ROUTE_SCHEMA = schema(dict(call_id=ID, perspective_id=ID,
                           cell=dict(type='integer', enum=list(SIZES))), ['call_id'])
PQ_SCHEMA = schema(dict(call_ids=CALL_IDS), ['call_ids'])
CONNECTIVITY_SCHEMA = schema(dict(call_ids=CALL_IDS, import_id=ID,
    start=dict(type='string'), end=dict(type='string')), [])
CONNECTIVITY_SCHEMA['oneOf'] = [dict(required=['call_ids']), dict(required=['import_id','start','end'])]
RULES = [
    'PQ uses awt-occupancy-4, not MOS or certified perceptual quality. PQ 100 assumes complete AWT logging, even without heartbeat evidence.',
    'PQ incident placement differs from generic incident windows; reuse perceptual-quality, never derive PQ by subtracting arbitrary incident percentages.',
    'Direct geographic cells take priority. Estimates in estimate remain separate from direct means; estimated cells fill only traversed gaps.',
    'Routes interpolate coordinates within one call/source up to 120 seconds; quality is recalculated from AWT. No road/rail inference or extrapolation.',
    'Connectivity states expire after 30 seconds. Service rejection proves reachability, not general network failure; unknown is not down.',
    'User attempts are not SIP calls. Analytical attempt rows are raw observations, not the deduplicated UI register; do not sum them as unique calls.',
]
SCHEMAS = {'call-route': ROUTE_SCHEMA, 'perceptual-quality': PQ_SCHEMA, 'connectivity': CONNECTIVITY_SCHEMA}


def contract():
    return dict(version='analytics-current-1', pq_method=METHOD, rules=RULES,
                request_schemas=SCHEMAS, limits=dict(call_ids=20, response_bytes=4*1024*1024,
                pq_samples=100000, route_positions=10000, route_samples=100000,
                connectivity_hours=24, connectivity_observations=50000))


def validate(name, obj):
    spec=SCHEMAS[name]
    if not isinstance(obj,dict) or set(obj)-set(spec['properties']) or set(spec['required'])-set(obj):
        raise ValueError('Parametri analitici non validi')
    for key,value in obj.items():
        if key in ('call_id','perspective_id','import_id') and (type(value) is not int or value<1):
            raise ValueError('ID positivo richiesto')
        if key=='call_ids' and (not isinstance(value,list) or not 1<=len(value)<=20 or any(type(i) is not int or i<1 for i in value)):
            raise ValueError('Selezionare da 1 a 20 chiamate SIP')
        if key=='cell' and (type(value) is not int or value not in SIZES):
            raise ValueError('Dimensione cella non valida')
        if key in ('start','end') and (not isinstance(value,str) or not value or len(value)>100):
            raise ValueError('Periodo non valido')
    if name=='connectivity' and set(obj) not in ({'call_ids'},{'import_id','start','end'}):
        raise ValueError('Specificare call_ids oppure import_id, start e end')


def run(db, name, obj):
    validate(name,obj)
    # All dependent reads share a snapshot, without writes or enrichment.
    if db.in_transaction:
        raise ValueError('Analisi richiede una connessione senza transazioni aperte')
    try:
        db.execute('BEGIN')
        if name=='call-route':
            from .call_route import route
            result=route(db,obj['call_id'],obj.get('perspective_id'),obj.get('cell',50))
        elif name=='perceptual-quality':
            from .perceptual import calculate
            result=dict(method=METHOD, samples=calculate(db,obj['call_ids']), rules=RULES[:2])
        else:
            from .connectivity import timeline, for_calls
            result=(for_calls(db,obj['call_ids']) if 'call_ids' in obj else
                    timeline(db,obj['import_id'],obj['start'],obj['end']))
        if len(json.dumps(result,ensure_ascii=False,allow_nan=False).encode('utf-8'))>4*1024*1024:
            raise ValueError('Risposta analitica oltre 4 MiB: restringere la selezione')
        return result
    finally:
        db.rollback()
