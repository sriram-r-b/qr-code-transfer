from datetime import datetime

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/send')
def send():
    return render_template('send.html')

@app.route('/receive')
def receive():
    return render_template('receive.html')

@app.post('/client-log')
def client_log():
    payload = request.get_json(silent=True) or {}
    page = str(payload.get('page', 'unknown'))[:40]
    level = str(payload.get('level', 'info'))[:12]
    message = str(payload.get('message', ''))[:1000]
    details = payload.get('details')
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    suffix = f" | {details}" if details is not None else ""
    print(f"[client {timestamp}] [{page}] [{level}] {message}{suffix}", flush=True)
    return jsonify(ok=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
