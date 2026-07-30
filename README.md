# QR Data Transfer

Transfer data between devices using only QR codes — no network, no cables, no setup.

Both devices need a camera and a screen. The sender shows data QR codes while the receiver scans them. The receiver shows ACK QR codes that the sender scans to advance. Each chunk is acknowledged before the next one is sent.

## How It Works

1. **Sender** chunks data into 500-byte segments and displays each as a QR code
2. **Receiver** scans the QR codes with its camera, stores each chunk, and shows an ACK QR for the last contiguous chunk
3. **Sender's camera** watches the receiver's ACK QR. When the ACK advances, the sender moves to the next chunk
4. If a chunk is missed, the receiver's ACK stalls at the last good chunk. The sender sees the gap and resends

No HTTP, no Wi-Fi, no networking at all after the initial page load.

## Quick Start

### macOS / Linux (conda)

```bash
conda create -n qr-transfer python=3.11 -y
conda activate qr-transfer
pip install -r requirements.txt
python app.py
```

### Windows (venv)

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open [http://localhost:5001](http://localhost:5001) on both devices (same machine to test).

> **Note**: Both devices must open the same URL. On a single machine, use `localhost:5001`. On different machines on the same LAN, use the server's local IP address (e.g., `http://192.168.x.x:5001`). After the page loads, no network is needed — all logic runs in the browser.

## Usage

**Send Data** — enter text or pick a file, click Generate. Show the QR code to the receiver.

**Receive Data** — click Start Camera, point at the sender's screen. The ACK QR in the corner tells the sender what to send next.

## Protocol

Each QR contains a compact JSON message:

```
Data:  {"v":1,"t":"d","i":5,"n":10,"h":"<sha256>","d":"<base64>"}
ACK:   {"v":1,"t":"a","h":"<sha256>","i":5}
```

The SHA-256 of the full data acts as the session identifier. The receiver's ACK always reports the **highest contiguous chunk** (0 through N all present). The sender uses this value to know exactly where to resume.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Flask server (serves pages, no logic) |
| `templates/send.html` | Sender: data QR + camera PIP for ACKs |
| `templates/receive.html` | Receiver: camera + corner ACK QR |
| `static/qrcode.min.js` | QR code generation |
| `static/jsqr.js` | QR code scanning |
