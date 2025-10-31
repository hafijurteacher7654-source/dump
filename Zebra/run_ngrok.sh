#!/bin/bash
NGROK="/opt/homebrew/bin/ngrok"
PORT=8002

"$NGROK" http "$PORT"

