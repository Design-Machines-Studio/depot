#!/usr/bin/env bash
# One-shot Jev Decisions adapter. JSON stdin; --receipt NEW_FILE; --timeout 1..60.
# Uses this bundle's credential loader and structural boundary. No client retries or model substitution.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$ROOT/openrouter-credential.sh"
if ! load_openrouter_api_key; then
  echo 'OpenRouter credential unavailable or invalid.' >&2
  exit 1
fi
exec /usr/bin/python3 -I - "$ROOT" "$@" 3<&0 <<'PY'
"""One-shot, bounded Decisions transport; no application decisions or retries."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

MODEL = 'typesafe/jev-1.13'
ENDPOINT = 'https://openrouter.ai/api/alpha/decisions'
MAX_INPUT = 32000


def require(condition):
    if not condition:
        raise ValueError('Invalid Decisions schema')


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def probability(value):
    return number(value) and 0 <= value <= 1


def validate_request(body):
    require(type(body) is dict and set(body) == {'model', 'state', 'questions'})
    require(body['model'] == MODEL)
    require(type(body['state']) in (str, dict, list))
    questions = body['questions']
    require(type(questions) is dict and 1 <= len(questions) <= 32)
    for name, question in questions.items():
        require(type(name) is str and bool(re.fullmatch(r'[A-Za-z0-9_]{1,80}', name)))
        require(type(question) is dict and set(question) == {'type', 'instructions', 'criteria'})
        require(type(question['instructions']) is str and bool(question['instructions'].strip()))
        kind, criteria = question['type'], question['criteria']
        require(kind in ('choice', 'score', 'noul'))
        if kind == 'score':
            require(type(criteria) is list and 2 <= len(criteria) <= 10)
            values = criteria
        else:
            require(type(criteria) is dict and 1 <= len(criteria) <= 255)
            require(all(type(k) is str and 0 < len(k) <= 100 for k in criteria))
            if kind == 'noul':
                require(set(criteria) == {'true', 'false'})
            values = criteria.values()
        require(all(type(v) is str and bool(v.strip()) for v in values))


def validate_response(body, request):
    require(type(body) is dict and not body.get('error'))
    answers = body.get('answers')
    require(type(answers) is dict and set(answers) == set(request['questions']))
    clean = {}
    for name, question in request['questions'].items():
        answer = answers[name]
        require(type(answer) is dict and answer.get('type') == question['type'])
        kind = question['type']
        if kind == 'noul':
            require(probability(answer.get('noul')))
            clean[name] = {'type': kind, 'noul': answer['noul']}
            continue
        options = set(question['criteria']) if kind == 'choice' else {str(i) for i in range(len(question['criteria']))}
        probs = answer.get('probabilities')
        require(type(probs) is dict and set(probs) == options)
        require(all(probability(p) for p in probs.values()))
        require(abs(sum(probs.values()) - 1) <= 0.02 and probability(answer.get('confidence')))
        if kind == 'choice':
            require(type(answer.get('choice')) is str and answer['choice'] in options)
            clean[name] = {k: answer[k] for k in ('type', 'choice', 'confidence', 'probabilities')}
        else:
            # Scores are expected values; not necessarily integer level indices.
            require(number(answer.get('score')) and 0 <= answer['score'] <= len(options)-1)
            require(answer.get('legend') == {str(i): v for i, v in enumerate(question['criteria'])})
            clean[name] = {k: answer[k] for k in ('type', 'score', 'confidence', 'probabilities', 'legend')}
    model = body.get('model')
    require(model is None or model == MODEL or (
        type(model) is str and bool(re.fullmatch(re.escape(MODEL) + r'-[0-9]{8}', model))))
    usage = body.get('usage')
    require(type(usage) is dict)
    require(all(type(usage.get(k)) is int and usage[k] >= 0 for k in ('input_tokens', 'output_tokens')))
    result = {'answers': clean, 'usage': {k: usage[k] for k in ('input_tokens', 'output_tokens')}, 'model': model}
    for field in ('id', 'provider'):
        value = body.get(field)
        require(value is None or (type(value) is str and bool(re.fullmatch(r'[A-Za-z0-9 ._:/-]{1,200}', value))))
        result[field] = value
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def alarm(*args):
    raise TimeoutError


def interrupt(*args):
    raise InterruptedError


def main():
    root = Path(sys.argv.pop(1)).resolve()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--timeout', type=int, default=20)
    args = parser.parse_args()
    key = os.environ.pop('OPENROUTER_API_KEY', '')
    os.environ.pop('OPENROUTER_API_KEY_FILE', None)
    if not key or not 1 <= args.timeout <= 60:
        parser.exit(2, 'Invalid credential or timeout.\n')
    # The alpha Decisions contract has no chat provider-routing/privacy fields.
    # Refuse requirements we cannot preserve rather than silently dropping them.
    if os.environ.get('OPENROUTER_ZDR') == '1' or any(os.environ.get(k) for k in (
            'OPENROUTER_PROVIDER_ORDER', 'OPENROUTER_PROVIDER_SORT',
            'OPENROUTER_FALLBACK_PROVIDER_ORDER', 'OPENROUTER_ALLOW_FALLBACKS',
            'OPENROUTER_REASONING_EFFORT')) or os.environ.get('OPENROUTER_WEB_SEARCH') == '1':
        parser.exit(2, 'Requested chat privacy/routing options are unsupported by Decisions.\n')
    endpoint = os.environ.get('OPENROUTER_DECISIONS_ENDPOINT', ENDPOINT)
    if endpoint != ENDPOINT and not (key == 'test' and re.fullmatch(r'http://127\.0\.0\.1:[1-9][0-9]{0,4}/api/alpha/decisions', endpoint)):
        parser.exit(2, 'Endpoint override is restricted to loopback fixture requests.\n')
    # Refuse existing paths/symlinks and reserve the receipt before any network call.
    try:
        fd = os.open(args.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        parser.exit(2, 'Receipt must be a new writable file.\n')
    receipt = {'schemaVersion': 1, 'endpoint': 'alpha/decisions', 'requestedModel': MODEL,
               'outcome': 'error', 'generationId': None, 'responseModel': None,
               'servingProvider': None, 'servingProviderProvenance': 'not_reported_by_decisions',
               'responseModelProvenance': 'not_reported_by_decisions', 'usage': None,
               'requestEnvelopeSha256': None, 'failureKind': None, 'httpStatus': None}
    started = time.monotonic()
    result, code = None, 1
    signal.signal(signal.SIGALRM, alarm)
    signal.signal(signal.SIGHUP, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    signal.alarm(args.timeout)
    try:
        with os.fdopen(3, 'rb') as incoming:
            raw = incoming.read(MAX_INPUT + 1)
        require(0 < len(raw) <= MAX_INPUT and b'\0' not in raw)
        body = json.loads(raw)
        validate_request(body)
        # Snapshot once; boundary and transport see exactly the same UTF-8 bytes.
        with tempfile.TemporaryDirectory(prefix='openrouter-decisions-') as temporary:
            snapshot = Path(temporary) / 'request.json'
            snapshot.write_bytes(raw)
            check = subprocess.run(['bash', str(root/'delegation-boundary.sh'), '--mode', 'artifact-delegation',
                '--policy', str(root/'delegation-security-policy.json'), '--content-file', str(snapshot)],
                capture_output=True, timeout=min(5, args.timeout))
            require(check.returncode == 0)
        receipt['requestEnvelopeSha256'] = hashlib.sha256(raw).hexdigest()
        request = urllib.request.Request(endpoint, data=raw, method='POST',
            headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'})
        # Never forward credentials through redirects or ambient proxy configuration.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
        with opener.open(request, timeout=args.timeout) as response:
            receipt['httpStatus'] = response.status
            raw_response = response.read(2_000_001)
        require(len(raw_response) <= 2_000_000)
        result = validate_response(json.loads(raw_response), body)
        receipt.update(outcome='success', generationId=result['id'], responseModel=result['model'],
                       servingProvider=result['provider'], usage=result['usage'])
        if result['model'] is not None:
            receipt['responseModelProvenance'] = 'response'
        if result['provider'] is not None:
            receipt['servingProviderProvenance'] = 'response'
        code = 0
    except urllib.error.HTTPError as error:
        receipt.update(failureKind='http_error', httpStatus=error.code)
    except (TimeoutError, socket.timeout, subprocess.TimeoutExpired):
        receipt.update(failureKind='timeout'); code = 28
    except (InterruptedError, KeyboardInterrupt):
        receipt.update(failureKind='interrupted'); code = 130
    except (ValueError, TypeError, KeyError, UnicodeError):
        receipt.update(failureKind='invalid_schema'); code = 2
    except (OSError, urllib.error.URLError):
        receipt.update(failureKind='transport_or_local_io')
    finally:
        signal.alarm(0)
        receipt['elapsedMs'] = round((time.monotonic()-started)*1000, 2)
        with os.fdopen(fd, 'w') as file:
            json.dump(receipt, file); file.flush(); os.fsync(file.fileno())
    if code == 0:
        print(json.dumps(result))
    else:
        print('OpenRouter Decisions failed: '+str(receipt['failureKind'])+'. No retry made.', file=sys.stderr)
    return code


if __name__ == '__main__':
    sys.exit(main())
PY
