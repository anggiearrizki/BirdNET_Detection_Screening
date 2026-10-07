"""Comment-only BirdNET writer. No verification or lock fields are sent."""
import os
from pathlib import Path
from urllib.parse import urlparse
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / '.env', override=True)
BIRDNET_BASE_URL = os.getenv('BIRDNET_BASE_URL', '').rstrip('/')

class BirdNETReviewWriteError(RuntimeError):
    def __init__(self, message, http_status=None):
        super().__init__(message)
        self.http_status = http_status

def build_comment_payload(note_text):
    if not isinstance(note_text, str) or not note_text.strip():
        raise ValueError('note_text must be a nonempty string.')
    return {'comment': note_text.strip()}

def build_review_url(detection_id):
    if not BIRDNET_BASE_URL or int(detection_id) <= 0:
        raise BirdNETReviewWriteError('A base URL and positive detection ID are required.')
    return f'{BIRDNET_BASE_URL}/api/v2/detections/{int(detection_id)}/review'

def build_authenticated_session(station=None):
    load_dotenv(PROJECT_ROOT / '.env', override=True)
    prefix = f'BIRDNET_{station}_' if station else 'BIRDNET_'
    cookie = os.getenv(prefix + 'SESSION_COOKIE', '')
    csrf = os.getenv(prefix + 'CSRF_TOKEN', '')
    if not cookie or not csrf:
        raise BirdNETReviewWriteError(f'Configure {prefix}SESSION_COOKIE and {prefix}CSRF_TOKEN.')
    host = urlparse(BIRDNET_BASE_URL).hostname
    if not host:
        raise BirdNETReviewWriteError('Invalid BirdNET base URL.')
    session = requests.Session()
    session.cookies.set('_gothic_session', cookie, domain=host, path='/')
    session.cookies.set('csrf', csrf, domain=host, path='/')
    session.headers.update({'X-CSRF-Token': csrf, 'Content-Type': 'application/json'})
    return session

def test_authenticated_session(session=None):
    owned = session is None
    session = session or build_authenticated_session()
    try:
        response = session.get(f'{BIRDNET_BASE_URL}/api/v2/detections/ignored', timeout=15,
                               allow_redirects=False)
        if not response.ok or response.is_redirect:
            raise BirdNETReviewWriteError('Protected GET failed.', response.status_code)
        return response  # GET success does not prove permission to POST.
    finally:
        if owned:
            session.close()

def preview_comment_write(detection_id, note_text):
    result = {'url': build_review_url(detection_id),
              'payload': build_comment_payload(note_text), 'dry_run': True}
    print(result)
    return result

def write_comment(detection_id, note_text, session=None):
    owned = session is None
    session = session or build_authenticated_session()
    try:
        response = session.post(build_review_url(detection_id),
                                json=build_comment_payload(note_text), timeout=30,
                                allow_redirects=False)
        if not 200 <= response.status_code < 300:
            # Do not print response bodies, which may contain sensitive content.
            raise BirdNETReviewWriteError(
                f'BirdNET comment POST rejected: HTTP {response.status_code}.',
                response.status_code)
        return response
    finally:
        if owned:
            session.close()
