"""Whitelisted transient evidence; no raw text or causal interpretation."""
import re
from datetime import datetime

TYPES = ('audio_route_change', 'speakerphone_set', 'audio_session_start',
         'audio_session_stop', 'mute_set', 'hold_request', 'resume_request',
         'hold_change_accepted', 'network_change_notification', 'network_available',
         'network_lost', 'network_configuration_change', 'device_created', 'scheduling_reset', 'audio_reset_request',
         'sip_reinvite', 'call_connected', 'call_ended')


def signals(text):
    """Return only typed values from confirmed formats, never arbitrary device names."""
    if not any(marker in text for marker in (
            'Received route change notification:', 'AudioState[', 'Set isSpeakerphoneActive',
            'Setting audio input', 'On hold request sent', 'Blocking resume call',
            'VDK reported that on-hold', 'Network connection changed', 'Network is ',
            'Network available', 'Network lost', 'Creating device', 'We reset the VOD timing',
            'AudioRoute: resetAudio.', 'Network changed from SSID:', 'INVITE sip')):
        return
    h = text.split('\n', 1)[0]
    if 'We reset the VOD timing to avoid continuous false warnings.' in h:
        yield 'scheduling_reset', None, None, 'vod_timing_reset_notification'
    if 'AudioRoute: resetAudio. CurrentAudioRoute:' in h:
        yield 'audio_reset_request', None, None, 'reset_operation_not_device_recreation'
    match = re.search(r'Received route change notification: AVAudioSessionRouteChangeReason\(rawValue: (\d+)\)', h)
    if match:
        yield 'audio_route_change', None, None, 'reason_code:' + match[1]
    match = re.search(r'AudioState\[communicationDeviceChanged -> .*?type=\'([A-Z_]+)\'', h)
    if match:
        allowed = {'BUILTIN_EARPIECE', 'BUILTIN_SPEAKER', 'BLUETOOTH_SCO', 'BLUETOOTH_A2DP', 'WIRED_HEADSET', 'WIRED_HEADPHONES', 'USB_HEADSET'}
        yield 'audio_route_change', None, match[1] if match[1] in allowed else 'other', 'communication_device_notification'
    for marker, kind in [('AudioState[startAudioSession]', 'audio_session_start'), ('AudioState[stopAudioSession]', 'audio_session_stop')]:
        if marker in h:
            yield kind, None, None, 'session_operation'
    match = re.search(r'Set isSpeakerphoneActive \[(TRUE|FALSE)\]', h)
    if match:
        yield 'speakerphone_set', None, match[1].lower(), 'set_operation'
    match = re.search(r'Setting audio input \d+ mute status to\s+(true|false)\b', h)
    if match:
        yield 'mute_set', None, match[1], 'set_operation'
    if 'On hold request sent, waiting for response...' in h:
        yield 'hold_request', None, None, 'request_not_completion'
    if re.search(r'Blocking resume call on line\s+\d+\b', h):
        yield 'resume_request', None, None, 'request_not_completion'
    if re.search(r'VDK reported that on-hold change request on line \d+ has been ACCEPTED', h):
        yield 'hold_change_accepted', None, None, 'direction_unknown'
    if re.search(r': Network connection changed\s*$', h):
        yield 'network_change_notification', None, None, 'interface_unknown'
    match = re.search(r': Network changed from SSID: (.*?) - IP: (.*?) to SSID: (.*?) - IP: (.*?)\s*$', h)
    if match and (match[1],match[2]) != (match[3],match[4]):
        yield 'network_configuration_change', None, None, 'ssid_or_ip_changed_not_interface_proof'
    if re.search(r'/(?:NetworkMonitor|ConnectionChangeMonitor)[^:]* : Network (?:is )?available(?:\s*:\s*\d+)?\s*$', h):
        yield 'network_available', None, None, 'availability_notification'
    if re.search(r'/(?:NetworkMonitor|ConnectionChangeMonitor)[^:]* : Network (?:is )?lost(?:\s*:\s*\d+)?\s*$', h):
        yield 'network_lost', None, None, 'availability_notification'
    match = re.search(r'Creating device\s+(Default Audio (?:Input|Output)|NA[RW]T\d+ of Line \d+)\s*$', h)
    if match:
        yield 'device_created', None, match[1], 'creation_not_reset'
    # In-dialog INVITE requires an actual request line and a To tag in headers.
    request = re.search(r'^\s*(?:SIP/2\.0 \d{3}[^\n]*|[A-Z]+ sips?:[^\n]+ SIP/2\.0)\s*$', text, re.M)
    if request and request[0].lstrip().startswith('INVITE '):
        headers = text[request.end():].split('\n\n', 1)[0]
        if re.search(r'^\s*(?:To|t):[^\n]*;tag=[^;\s]+', headers, re.M | re.I):
            yield 'sip_reinvite', None, None, 'in_dialog_request'


def observed_timestamp(text, fallback):
    m = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}):(\d{3})\s', text)
    if m:
        try:
            return datetime.fromisoformat(m[1] + '.' + m[2]).isoformat(' ', timespec='microseconds'), 'log_android_milliseconds'
        except ValueError:
            pass
    return fallback, 'event_timestamp'
