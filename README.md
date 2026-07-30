# QR Data Transfer

Transfer data between devices using QR codes with bidirectional ACK-based reliability.

## How It Works

Data is split into chunks, each encoded as a QR code. The sender displays QR codes while the receiver scans them with a camera. Unlike naive QR transfer tools that blindly cycle through codes, this app uses an **ACK-based protocol**:

1. **Sender** displays a chunk as a QR code and **waits** for the receiver to acknowledge it
2. **Receiver** scans the QR code, decodes the chunk, and sends an **ACK** via HTTP
3. **Sender** only advances to the next chunk when the ACK is received
4. If chunks are missed, the **receiver detects gaps** and requests **retransmission**

## Quick Start

```bash
# Create conda environment
conda create -n qr-transfer python=3.11 -y
conda activate qr-transfer

# Install
pip install -r requirements.txt

# Run
python app.py
```

Open `http://localhost:5001` — both devices need access to this URL (same network).

## Usage

1. On one device: click **Send Data**, enter text or pick a file, then **Generate QR Codes**
2. On the other device: click **Receive Data**, then **Start Camera**
3. Point the receiver's camera at the sender's screen
4. The sender waits for ACKs and auto-advances; the receiver requests retries for missed chunks

## Protocol

Each QR encodes a JSON message:

```json
{"v":1,"s":"sess_<id>","i":0,"t":10,"h":"<md5>","d":"<base64 chunk>"}
```

- `v`: protocol version
- `s`: session ID (links sender and receiver)
- `i` / `t`: chunk index / total chunks
- `h`: MD5 hash of the full data
- `d`: base64-encoded chunk data

The receiver sends ACKs via `POST /api/session/<sid>/ack` and requests retries via `POST /api/session/<sid>/retry` when gaps are detected.
