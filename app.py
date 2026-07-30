import base64
import hashlib
import io
import json
import secrets
import threading
import time

import qrcode
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
CHUNK_SIZE = 500
PROTOCOL_VERSION = 1

sessions_lock = threading.Lock()
sessions = {}
SESSION_TIMEOUT = 1800


class TransferSession:
    def __init__(self, chunks, data_hash, total_size, filename, is_file):
        self.sid = 'sess_' + secrets.token_hex(16)
        self.chunks = chunks
        self.data_hash = data_hash
        self.total_size = total_size
        self.filename = filename
        self.is_file = is_file
        self.total_chunks = len(chunks)
        self.acked = set()
        self.retry_requested = {}
        self.created_at = time.time()
        self.last_activity = time.time()

    def is_expired(self):
        return time.time() - self.created_at > SESSION_TIMEOUT

    def ack_chunk(self, idx):
        if 0 <= idx < self.total_chunks:
            self.acked.add(idx)
            self.last_activity = time.time()
            self.retry_requested.pop(idx, None)

    def request_retry(self, indices):
        now = time.time()
        for idx in indices:
            if 0 <= idx < self.total_chunks and idx not in self.acked:
                self.retry_requested[idx] = now
        self.last_activity = time.time()


def cleanup_sessions():
    now = time.time()
    with sessions_lock:
        expired = [sid for sid, sess in list(sessions.items()) if sess.is_expired()]
        for sid in expired:
            del sessions[sid]


def chunk_data(data_bytes, chunk_size=CHUNK_SIZE):
    total_chunks = (len(data_bytes) + chunk_size - 1) // chunk_size
    data_hash = hashlib.md5(data_bytes).hexdigest()
    file_hash = hashlib.sha256(data_bytes).hexdigest()
    chunks = []
    for i in range(total_chunks):
        chunk = data_bytes[i * chunk_size : (i + 1) * chunk_size]
        chunk_b64 = base64.b64encode(chunk).decode('ascii')
        msg = {
            'v': PROTOCOL_VERSION,
            'i': i,
            't': total_chunks,
            'h': data_hash,
            'd': chunk_b64,
        }
        chunks.append(msg)
    return chunks, data_hash, file_hash, len(data_bytes)


def generate_qr_image(data_str, box_size=6, border=2):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data_str)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/send')
def send_page():
    return render_template('send.html')


@app.route('/receive')
def receive_page():
    return render_template('receive.html')


@app.route('/api/session/create', methods=['POST'])
def api_create_session():
    cleanup_sessions()
    data = request.get_json(force=True)
    raw = data.get('data', '')
    chunk_size = data.get('chunk_size', CHUNK_SIZE)
    is_file = data.get('is_file', False)
    filename = data.get('filename', '')

    if is_file:
        data_bytes = base64.b64decode(raw)
    else:
        data_bytes = raw.encode('utf-8')

    if not data_bytes:
        return jsonify({'error': 'No data'}), 400

    chunks, data_hash, file_hash, total_size = chunk_data(data_bytes, chunk_size)

    with sessions_lock:
        session = TransferSession(chunks, data_hash, total_size, filename, is_file)
        sessions[session.sid] = session

    return jsonify({
        'sid': session.sid,
        'total_chunks': session.total_chunks,
        'chunks': chunks,
        'data_hash': data_hash,
        'total_size': total_size,
        'filename': filename,
        'is_file': is_file,
    })


@app.route('/api/session/<sid>/status')
def api_session_status(sid):
    cleanup_sessions()
    with sessions_lock:
        session = sessions.get(sid)
        if not session:
            return jsonify({'error': 'Session not found', 'expired': True}), 404
        return jsonify({
            'total_chunks': session.total_chunks,
            'acked': sorted(session.acked),
            'retry_requested': sorted(session.retry_requested.keys()),
            'complete': len(session.acked) == session.total_chunks,
            'filename': session.filename,
            'is_file': session.is_file,
            'data_hash': session.data_hash,
        })


@app.route('/api/session/<sid>/ack', methods=['POST'])
def api_session_ack(sid):
    data = request.get_json(force=True)
    chunk_index = data.get('chunk_index')
    if chunk_index is None:
        return jsonify({'error': 'chunk_index required'}), 400

    with sessions_lock:
        session = sessions.get(sid)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        session.ack_chunk(chunk_index)
        complete = len(session.acked) == session.total_chunks
        return jsonify({
            'ok': True,
            'chunk_index': chunk_index,
            'acked': sorted(session.acked),
            'complete': complete,
        })


@app.route('/api/session/<sid>/retry', methods=['POST'])
def api_session_retry(sid):
    data = request.get_json(force=True)
    indices = data.get('indices', [])
    if not indices:
        return jsonify({'error': 'indices required'}), 400

    with sessions_lock:
        session = sessions.get(sid)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        session.request_retry(indices)
        return jsonify({
            'ok': True,
            'retry_requested': sorted(session.retry_requested.keys()),
        })


@app.route('/api/qr', methods=['POST'])
def api_qr():
    data = request.get_json(force=True)
    chunk = data.get('chunk', {})
    sid = data.get('sid', '')
    qr_data = dict(chunk)
    if sid:
        qr_data['s'] = sid
    qr_str = json.dumps(qr_data, separators=(',', ':'))
    box_size = data.get('box_size', 6)
    border = data.get('border', 2)
    qr_b64 = generate_qr_image(qr_str, box_size, border)
    return jsonify({'qr': qr_b64, 'data': qr_str})


@app.route('/api/verify', methods=['POST'])
def api_verify():
    data = request.get_json(force=True)
    received_b64 = data.get('data', '')
    expected_hash = data.get('hash', '')
    received_bytes = base64.b64decode(received_b64)
    actual_hash = hashlib.md5(received_bytes).hexdigest()
    return jsonify({
        'match': actual_hash == expected_hash,
        'expected': expected_hash,
        'actual': actual_hash,
        'size': len(received_bytes),
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
