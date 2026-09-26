"""KPE telemetry v1 contract and dependency-free validation. No derived MOS."""
import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path

MAX_LINE = 65536
MAX_FILE = 40 * 1024 * 1024


def obj(properties, required=()):
    return dict(type='object', properties=properties, required=list(required), additionalProperties=False)


def string(*values):
    return dict(type='string', enum=list(values)) if values else dict(type='string', minLength=1, maxLength=256)


def number(minimum=0, maximum=None, integer=False):
    result = dict(type='integer' if integer else 'number', minimum=minimum)
    if maximum is not None:
        result['maximum'] = maximum
    return result


def nullable(schema):
    return dict(anyOf=[schema, dict(type='null')])


UINT = number(integer=True)
TIME = dict(type='string', format='date-time', pattern=r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z$')
TOKEN = dict(type='string', minLength=1, maxLength=128, pattern=r'^[A-Za-z0-9_.:@/+-]+$')
STREAM = obj(dict(call_id=TOKEN, sip_call_id=nullable(string()), stream_id=TOKEN,
                  ssrc=number(0, 4294967295, True), direction=string('local_receive', 'local_send')),
             ('call_id', 'sip_call_id', 'stream_id', 'ssrc', 'direction'))

PAYLOADS = {
    'session': obj(dict(platform=string('android', 'ios', 'windows', 'macos', 'linux', 'other'),
                        os_version=string(), app_version=string(), media_version=string(),
                        device_model=nullable(string()), clock_uncertainty_ms=nullable(number()),
                        capabilities=dict(type='array', maxItems=64, items=obj(dict(
                            name=string(), status=string('available', 'unsupported', 'permission_denied', 'disabled')),
                            ('name', 'status')))),
                   ('platform', 'os_version', 'app_version', 'media_version', 'clock_uncertainty_ms', 'capabilities')),
    'position': obj(dict(trajectory_id=TOKEN, fix_id=TOKEN, fix_utc=nullable(TIME), fix_mono_ms=number(),
                         latitude=number(-90, 90), longitude=number(-180, 180), accuracy_m=nullable(number()),
                         provider=string(), cached=dict(type='boolean'), speed_mps=nullable(number()),
                         speed_accuracy_mps=nullable(number()), bearing_deg=nullable(number(0, 359.999999)),
                         bearing_accuracy_deg=nullable(number(0, 180)), altitude_m=nullable(dict(type='number'))),
                    ('trajectory_id', 'fix_id', 'fix_utc', 'fix_mono_ms', 'latitude', 'longitude',
                     'accuracy_m', 'provider', 'cached', 'speed_mps', 'speed_accuracy_mps',
                     'bearing_deg', 'bearing_accuracy_deg')),
    'network': obj(dict(network_id=TOKEN, scope=string('media_path', 'system_default'),
                        stream_id=nullable(TOKEN), access=string('cellular', 'wifi', 'ethernet', 'other', 'unknown'),
                        upstream=string('mobile_direct', 'tethering', 'onboard_wifi', 'fixed', 'unknown'),
                        upstream_basis=string('observed', 'declared', 'unknown'),
                        subscription_id=nullable(TOKEN), sim_operator=nullable(string()),
                        serving_operator=nullable(string()), radio_technology=nullable(string()),
                        wifi_network_id=nullable(TOKEN), wifi_ap_id=nullable(TOKEN),
                        vpn=nullable(dict(type='boolean')), metered=nullable(dict(type='boolean')),
                        signals=dict(type='array', maxItems=16, items=obj(dict(name=string(),
                            value=dict(type='number'), unit=string('dBm', 'dB', 'asu', 'raw')),
                            ('name', 'value', 'unit')))),
                   ('network_id', 'scope', 'stream_id', 'access', 'upstream', 'upstream_basis',
                    'subscription_id', 'sim_operator', 'serving_operator', 'radio_technology',
                    'wifi_network_id', 'wifi_ap_id', 'vpn', 'signals')),
    'media_interval': obj(dict(stream=STREAM, network_id=nullable(TOKEN), config_id=TOKEN,
                               counter_epoch=TOKEN, start_mono_ms=number(), end_mono_ms=number(),
                               expected_packets=UINT, received_unique_packets=UINT,
                               duplicate_packets=nullable(UINT), reordered_packets=nullable(UINT),
                               missing_at_deadline_packets=nullable(UINT), late_packets=nullable(UINT),
                               discarded_late_packets=nullable(UINT), discarded_overflow_packets=nullable(UINT),
                               missing_sequence_events=nullable(UINT), skipped_media_ms=nullable(number()),
                               skipped_silence_ms=nullable(number()), concealed_media_ms=nullable(number()),
                               inserted_media_ms=nullable(number()), fec_recovered_packets=nullable(UINT),
                               buffer_current_ms=nullable(number()), buffer_target_ms=nullable(number()),
                               loss_runs_packets=nullable(dict(type='array', maxItems=4096, items=number(1, integer=True))),
                               semantics_id=TOKEN, complete=dict(type='boolean')),
                          ('stream', 'network_id', 'config_id', 'counter_epoch', 'start_mono_ms', 'end_mono_ms',
                           'expected_packets', 'received_unique_packets', 'semantics_id', 'complete')),
    'media_config': obj(dict(stream=STREAM, config_id=TOKEN, codec=string(), rtp_clock_hz=number(1, integer=True),
                             packet_duration_ms=number(.001), channels=number(1, 64, True),
                             plc=string(), fec=string(), redundancy=string(), dtx=dict(type='boolean'),
                             jitter_buffer_mode=string(), jitter_target_ms=nullable(number())),
                        ('stream', 'config_id', 'codec', 'rtp_clock_hz', 'packet_duration_ms', 'channels',
                         'plc', 'fec', 'redundancy', 'dtx', 'jitter_buffer_mode', 'jitter_target_ms')),
    'rtcp': obj(dict(stream=STREAM, transport_direction=string('sent', 'received'),
                     packet_hex=dict(type='string', minLength=8, maxLength=32768, pattern=r'^(?:[0-9a-fA-F]{2})+$')),
                ('stream', 'transport_direction', 'packet_hex')),
    'collection': obj(dict(subsystem=string('position', 'network', 'media', 'clock', 'logger'),
                           status=string('started', 'stopped', 'unavailable', 'permission_denied',
                                         'suspended', 'resumed', 'clock_change', 'dropped_events'),
                           reason=string(), dropped_events=nullable(UINT)), ('subsystem', 'status', 'reason')),
    'action': obj(dict(stream=STREAM, action_id=TOKEN, phase=string('requested', 'applied', 'failed', 'reverted'),
                       reason=string(), prediction_id=nullable(TOKEN), old_config_id=TOKEN, new_config_id=TOKEN),
                  ('stream', 'action_id', 'phase', 'reason', 'prediction_id', 'old_config_id', 'new_config_id')),
    'packet': obj(dict(stream=STREAM, sequence=number(0, 65535, True), rtp_timestamp=number(0, 4294967295, True),
                       size_bytes=UINT, status=string('sent', 'received', 'discarded', 'played', 'missing'),
                       reason=nullable(string()), deadline_mono_ms=nullable(number())),
                  ('stream', 'sequence', 'rtp_timestamp', 'size_bytes', 'status', 'reason', 'deadline_mono_ms')),
}

# Additive revision: old v1 records keep their original contract.
PLAN_REF = obj(dict(plan_id=TOKEN, revision=UINT), ('plan_id', 'revision'))
PAYLOADS_11 = {
    'api_request': obj(dict(request_id=TOKEN, phase=string('started', 'succeeded', 'timeout', 'failed'),
                           start_mono_ms=number(), end_mono_ms=nullable(number()),
                           response_plan=nullable(PLAN_REF), reason=nullable(string())),
                      ('request_id', 'phase', 'start_mono_ms', 'end_mono_ms', 'response_plan', 'reason')),
    'plan_received': obj(dict(request_id=TOKEN, plan=PLAN_REF, issued_utc=TIME, expires_utc=TIME,
                             valid_until_mono_ms=number(), route_id=TOKEN, confidence=number(0, 1),
                             horizon_m=number(), horizon_ms=number(),
                             content_sha256=dict(type='string', pattern=r'^[0-9a-f]{64}$'),
                             document=dict(type='object'),
                             fallback_profile_id=TOKEN),
                        ('request_id', 'plan', 'issued_utc', 'expires_utc', 'valid_until_mono_ms',
                         'route_id', 'confidence', 'horizon_m', 'horizon_ms', 'content_sha256', 'document', 'fallback_profile_id')),
    'plan_state': obj(dict(plan=PLAN_REF, state=string('activated', 'replaced', 'expired', 'route_deviation',
                         'position_uncertain', 'fallback', 'resumed', 'stale_rejected'),
                         segment_id=nullable(TOKEN), profile_id=nullable(TOKEN), reason=string(),
                         position_basis=string('measured', 'estimated', 'unavailable'),
                         position_event_id=nullable(TOKEN), position_uncertainty_m=nullable(number())),
                     ('plan', 'state', 'segment_id', 'profile_id', 'reason', 'position_basis',
                      'position_event_id', 'position_uncertainty_m')),
}


def payloads(version):
    if version == 'kpe.telemetry/1':
        return PAYLOADS
    revised = dict(PAYLOADS, **PAYLOADS_11)
    revised['action'] = obj(dict(PAYLOADS['action']['properties'], plan=nullable(PLAN_REF),
        trigger=string('api', 'plan_progress', 'local_feedback', 'fallback', 'manual')),
        PAYLOADS['action']['required'] + ['plan', 'trigger'])
    revised['media_interval'] = obj(dict(PAYLOADS['media_interval']['properties'],
        sequence_first=UINT, sequence_last=UINT, received_in_window_packets=UINT),
        PAYLOADS['media_interval']['required'])
    return revised


def schema(version='kpe.telemetry/1.1'):
    """A portable JSON Schema; the local validator implements its used vocabulary."""
    common = dict(schema=string(version), event_id=TOKEN, source_id=TOKEN,
                  session_id=TOKEN, boot_id=TOKEN, seq=UINT, role=string('app', 'gw'),
                  observed_utc=TIME, mono_ms=number(), validity=string('valid', 'invalid'),
                  invalid_reason=nullable(string()), extensions=dict(type='object'))
    variants = []
    for kind, payload in payloads(version).items():
        props = dict(common, type=string(kind), payload=payload)
        variants.append(obj(props, tuple(k for k in props if k != 'extensions')))
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            'title': 'KPE raw telemetry v1', 'oneOf': variants}


def check(value, spec, path='$'):
    errors = []
    if 'anyOf' in spec:
        return [] if any(not check(value, s, path) for s in spec['anyOf']) else [f'{path}: tipo/valore non valido']
    typ = spec.get('type')
    valid_type = {'object': isinstance(value, dict), 'array': isinstance(value, list),
                  'string': isinstance(value, str), 'boolean': type(value) is bool,
                  'integer': type(value) is int,
                  'number': type(value) in (int, float), 'null': value is None}.get(typ, True)
    if not valid_type:
        return [f'{path}: atteso {typ}']
    if 'enum' in spec and value not in spec['enum']:
        errors.append(f'{path}: valore non previsto')
    if typ == 'object':
        for key in spec.get('required', []):
            if key not in value:
                errors.append(f'{path}.{key}: obbligatorio')
        for key, item in value.items():
            if key in spec.get('properties', {}):
                errors.extend(check(item, spec['properties'][key], f'{path}.{key}'))
            elif spec.get('additionalProperties') is False:
                errors.append(f'{path}: campo non previsto')
    if typ == 'array':
        if len(value) > spec.get('maxItems', 10000):
            errors.append(f'{path}: troppi elementi')
        else:
            for i, item in enumerate(value):
                errors.extend(check(item, spec['items'], f'{path}[{i}]'))
    if typ in ('number', 'integer'):
        if abs(value) > 1e100 or not math.isfinite(value):
            errors.append(f'{path}: numero non finito o troppo grande')
        elif value < spec.get('minimum', -math.inf) or value > spec.get('maximum', math.inf):
            errors.append(f'{path}: fuori intervallo')
    if typ == 'string':
        if not spec.get('minLength', 0) <= len(value) <= spec.get('maxLength', MAX_LINE):
            errors.append(f'{path}: lunghezza non valida')
        if 'pattern' in spec and not re.fullmatch(spec['pattern'], value):
            errors.append(f'{path}: formato non valido')
        if spec.get('format') == 'date-time':
            try:
                datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                errors.append(f'{path}: data non valida')
    return errors


def validate(event):
    if not isinstance(event, dict):
        return ['$: atteso oggetto']
    version = event.get('schema')
    if version not in ('kpe.telemetry/1', 'kpe.telemetry/1.1'):
        return ['$.schema: versione non supportata; conservare il record originale']
    kind = event.get('type')
    if not isinstance(kind, str) or kind not in payloads(version):
        return ['$.type: evento non supportato']
    variant = schema(version)['oneOf'][list(payloads(version)).index(kind)]
    errors = check(event, variant)
    if errors:
        return errors
    p = event['payload']
    if event['validity'] == 'invalid' and not event['invalid_reason']:
        errors.append('$.invalid_reason: motivo obbligatorio per misura invalida')
    if event['validity'] == 'valid' and event['invalid_reason'] is not None:
        errors.append('$.invalid_reason: deve essere null per misura valida')
    if kind == 'position' and p['fix_mono_ms'] > event['mono_ms']:
        errors.append('$.payload.fix_mono_ms: successivo alla ricezione')
    if kind == 'media_interval' and not p['start_mono_ms'] < p['end_mono_ms'] <= event['mono_ms']:
        errors.append('$.payload: intervallo non positivo o successivo alla ricezione')
    if kind == 'network':
        if p['scope'] == 'media_path' and p['stream_id'] is None:
            errors.append('$.payload.stream_id: necessario per media_path')
        if p['upstream'] != 'unknown' and p['upstream_basis'] == 'unknown':
            errors.append('$.payload.upstream_basis: evidenza richiesta')
    if kind == 'media_interval' and p['semantics_id'] == 'rtp-sequence-window/1':
        required = ('sequence_first', 'sequence_last', 'received_in_window_packets')
        if any(k not in p for k in required):
            errors.append('$.payload: finestra di sequenza incompleta')
        elif not (p['sequence_last'] >= p['sequence_first'] and
                  p['expected_packets'] == p['sequence_last'] - p['sequence_first'] + 1 and
                  p['received_in_window_packets'] <= p['expected_packets']):
            errors.append('$.payload: conteggi della stessa finestra incoerenti')
    if kind == 'api_request':
        if p['start_mono_ms'] > event['mono_ms'] or (p['phase'] == 'started' and p['end_mono_ms'] is not None):
            errors.append('$.payload: inizio richiesta incoerente')
        if p['phase'] != 'started' and (p['end_mono_ms'] is None or not p['start_mono_ms'] <= p['end_mono_ms'] <= event['mono_ms']):
            errors.append('$.payload: fine richiesta incoerente')
    if kind == 'plan_received':
        if datetime.fromisoformat(p['expires_utc']) <= datetime.fromisoformat(p['issued_utc']):
            errors.append('$.payload: scadenza precedente all’emissione')
        # Expired responses may legitimately arrive late: archive for stale_rejected.
    if kind == 'plan_state' and p['position_basis'] == 'measured' and p['position_event_id'] is None:
        errors.append('$.payload.position_event_id: obbligatorio per posizione misurata')
    return errors


def decode(line):
    def finite_tree(value, depth=0):
        if depth > 32:
            raise ValueError('annidamento eccessivo')
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('numero non finito')
        if isinstance(value, dict):
            for item in value.values():
                finite_tree(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                finite_tree(item, depth + 1)
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('chiave JSON duplicata')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('numero JSON non finito')
    if len(line.encode('utf-8')) > MAX_LINE:
        return None, ['record oltre 64 KiB']
    try:
        event = json.loads(line, object_pairs_hook=pairs, parse_constant=constant)
        finite_tree(event)
        return event, validate(event)
    except (ValueError, RecursionError):
        return None, ['JSON non valido, troncato, troppo annidato o con chiavi duplicate']


def records(text):
    """Preserve each physical nonblank line, including malformed/unknown versions."""
    normalized = re.sub(r'\r+\n', '\n', text).replace('\r', '\n')
    for line_no, line in enumerate(normalized.split('\n'), 1):
        if not line.strip():
            continue
        event, errors = decode(line)
        ts = None
        if not errors:
            # UTC remains explicit in the canonical text; never mix with naive legacy clocks.
            ts = event['observed_utc']
        yield line_no, ts, line, event, errors


def main():
    parser = argparse.ArgumentParser(description='Validate raw KPE telemetry JSONL without opening a database')
    parser.add_argument('files', nargs='*', type=Path)
    parser.add_argument('--schema', action='store_true', help='Print portable JSON Schema')
    parser.add_argument('--version', choices=('kpe.telemetry/1', 'kpe.telemetry/1.1'), default='kpe.telemetry/1.1')
    args = parser.parse_args()
    if args.schema:
        print(json.dumps(schema(args.version), indent=2, ensure_ascii=False))
        return 0
    if not args.files:
        parser.error('specificare almeno un file o --schema')
    failed = False
    for path in args.files:
        if path.stat().st_size > MAX_FILE:
            print(json.dumps(dict(file=str(path), error='file oltre 40 MiB')))
            failed = True
            continue
        try:
            text = path.read_text(encoding='utf-8-sig')
        except UnicodeError:
            print(json.dumps(dict(file=str(path), error='UTF-8 non valido')))
            failed = True
            continue
        count = 0
        for line, _, _, _, errors in records(text):
            count += 1
            if errors:
                failed = True
                print(json.dumps(dict(file=str(path), line=line, errors=errors[:20]), ensure_ascii=False))
        if not count:
            failed = True
        print(json.dumps(dict(file=str(path), records=count)))
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
