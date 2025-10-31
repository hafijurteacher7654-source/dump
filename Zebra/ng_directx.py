"""
ng_anydesk.py - EVENT-DRIVEN Screen Capture (Like AnyDesk)
Hotkeys:
   r+4 => pause (notify clients)
   r+5 => resume (notify clients)

Per-client paused state stored server-side for reliability.
"""
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from PIL import ImageGrab, Image
import pyautogui
import io
import base64
import threading
import time
import numpy as np
import traceback

# Disable PyAutoGUI failsafe
pyautogui.FAILSAFE = False

app = Flask(__name__)
app.config['SECRET_KEY'] = 'MyStrongToken123456'
CORS(app)

# Force threading-mode for reliability with blocking ImageGrab calls
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
print("⚠️ Using threading async_mode (recommended for blocking desktop capture)")

AUTH_TOKEN = "MyStrongToken123456"
# streaming_threads will map sid -> {'streaming': bool, 'paused': bool}
streaming_threads = {}
streaming_lock = threading.Lock()

# SETTINGS
SCALE_FACTOR = 0.85
JPEG_QUALITY = 70
CHECK_INTERVAL = 0.02  # seconds
CHANGE_THRESHOLD = 0.4  # percent of pixels (0-100)

print("=" * 60)
print("Windows Server - EVENT-DRIVEN CAPTURE (Like AnyDesk) with Host Notifications")
print("=" * 60)
print(f"⚙️ Scale={SCALE_FACTOR}, Quality={JPEG_QUALITY}")
print(f"🔍 Change detection: {int(1/CHECK_INTERVAL)} checks/sec")
print(f"📊 Threshold: {CHANGE_THRESHOLD}% pixels must change")
print("🔔 Hotkeys: r+4 = PAUSE (notify clients), r+5 = RESUME")
print("=" * 60)

HTML_VIEWER = """
<!DOCTYPE html>
<html>
<head>
    <title>Remote Control</title>
    <style>
        body { margin: 0; background: #000; display: flex; justify-content: center; align-items: center; height: 100vh; }
        #screen { max-width: 100%; max-height: 100vh; cursor: crosshair; }
        #status { position: fixed; top: 10px; left: 10px; color: #0f0; font-family: monospace; background: rgba(0,0,0,0.7); padding: 5px; z-index: 1000; }
        /* Notification overlay */
        #pauseOverlay {
            position: fixed;
            inset: 0;
            display: none;
            align-items: center;
            justify-content: center;
            background: rgba(0, 0, 0, 0.6);
            z-index: 9999;
            pointer-events: auto;
        }
        #pauseBox {
            background: #222;
            color: #fff;
            padding: 24px 28px;
            border-radius: 8px;
            font-family: Arial, sans-serif;
            font-size: 20px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.6);
            text-align: center;
            max-width: 85%;
        }
        #pauseBox small { display:block; margin-top:10px; font-size:12px; color:#ccc; }
    </style>
</head>
<body>
    <div id="status">Connecting...</div>
    <img id="screen" src="">
    <div id="pauseOverlay">
        <div id="pauseBox">
            <div id="pauseMessage">Owner requested temporary pause. Please stop interacting with the host machine.</div>
            <small>Waiting for owner to allow access again...</small>
        </div>
    </div>

    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        const token = 'MyStrongToken123456';
        const socket = io({ transports: ['websocket'], query: { token: token } });
        const img = document.getElementById('screen');
        const status = document.getElementById('status');
        const pauseOverlay = document.getElementById('pauseOverlay');
        const pauseMessage = document.getElementById('pauseMessage');

        let frameData = null;
        let frameCount = 0;
        let lastUpdate = Date.now();
        let pausedByHost = false; // when true, do not send control events

        socket.on('connect', () => {
            status.textContent = 'Connected - Waiting for changes...';
            socket.emit('start_stream', { token: token });
        });

        function safeSetImage(base64jpg) {
            const dataUrl = 'data:image/jpeg;base64,' + base64jpg;
            const tmp = new Image();
            tmp.onload = function() {
                img.src = tmp.src;
            };
            tmp.onerror = function(e) {
                console.error('Image load error', e);
            };
            tmp.src = dataUrl;
        }

        socket.on('frame', (data) => {
            if (data && data.image) {
                safeSetImage(data.image);
            }
            frameData = data;
            frameCount++;
            const now = Date.now();
            const timeSince = ((now - lastUpdate) / 1000).toFixed(2);
            status.textContent = `Streaming | Frames: ${frameCount} | Last update: ${timeSince}s ago | Changed: ${data ? data.change_percent : 'N/A'}%`;
            lastUpdate = now;
        });

        socket.on('disconnect', () => {
            status.textContent = 'Disconnected';
        });

        // Notification handler from host
        socket.on('notify', (data) => {
            try {
                const action = data.action;
                const message = data.message || '';
                if (action === 'pause') {
                    pausedByHost = true;
                    pauseMessage.textContent = message || 'Owner requested temporary pause. Please stop interacting with the host machine.';
                    pauseOverlay.style.display = 'flex';
                    status.textContent = 'PAUSED BY HOST';
                } else if (action === 'resume') {
                    pausedByHost = false;
                    pauseOverlay.style.display = 'none';
                    status.textContent = 'Resumed - Waiting for changes...';
                }
            } catch (e) {
                console.error('notify handler error', e);
            }
        });

        // Emit control events only if not paused
        function emitControl(payload) {
            if (pausedByHost) return;
            socket.emit('control', Object.assign({token: token}, payload));
        }

        img.addEventListener('mousemove', (e) => {
            if (!frameData) return;
            if (pausedByHost) return;
            const rect = img.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width;
            const y = (e.clientY - rect.top) / rect.height;
            emitControl({
                type: 'mouse_move',
                x: Math.floor(x * frameData.original_size.width),
                y: Math.floor(y * frameData.original_size.height)
            });
        });

        img.addEventListener('click', () => {
            emitControl({ type: 'mouse_click', button: 'left' });
        });

        img.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            emitControl({ type: 'mouse_right_click' });
        });

    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_VIEWER)

@app.route('/health')
def health():
    with streaming_lock:
        clients = {sid: {'streaming': bool(v.get('streaming')), 'paused': bool(v.get('paused'))} for sid, v in streaming_threads.items()}
    return {'status': 'running', 'clients': clients}

def verify_token(data):
    return data.get('token') == AUTH_TOKEN

def calculate_difference(img1, img2):
    try:
        arr1 = np.array(img1)
        arr2 = np.array(img2)
        if arr1.shape != arr2.shape:
            return 100.0
        diff = np.abs(arr1.astype(np.int16) - arr2.astype(np.int16))
        per_channel_threshold = 10
        changed_mask = np.any(diff > per_channel_threshold, axis=2)
        changed_pixels = int(np.count_nonzero(changed_mask))
        total_pixels = changed_mask.shape[0] * changed_mask.shape[1]
        if total_pixels == 0:
            return 100.0
        return (changed_pixels / total_pixels) * 100.0
    except Exception as e:
        print("calculate_difference error:", e)
        traceback.print_exc()
        return 100.0

def stream_screen(sid):
    print(f"🎥 Starting EVENT-DRIVEN capture for {sid[:8]}")
    try:
        frame_count = 0
        checks_count = 0
        start_time = time.time()
        last_screenshot = None

        # Initial capture
        screenshot = ImageGrab.grab(all_screens=False).convert('RGB')
        width, height = screenshot.size
        new_width = max(1, int(width * SCALE_FACTOR))
        new_height = max(1, int(height * SCALE_FACTOR))
        screenshot_small = screenshot.resize((new_width, new_height), Image.BILINEAR)

        buffer = io.BytesIO()
        screenshot_small.save(buffer, format='JPEG', quality=JPEG_QUALITY)
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        socketio.emit('frame', {
            'image': img_base64,
            'original_size': {'width': width, 'height': height},
            'display_size': {'width': new_width, 'height': new_height},
            'frame_id': 0,
            'change_percent': 100.0
        }, room=sid)

        last_screenshot = screenshot_small
        frame_count = 1

        print(f"✅ Monitoring for screen changes...")

        while True:
            with streaming_lock:
                client_state = streaming_threads.get(sid)
                # Stop streaming if client removed or streaming flag false
                if not client_state or not client_state.get('streaming', False):
                    break

            checks_count += 1

            try:
                current_screenshot = ImageGrab.grab(all_screens=False).convert('RGB')
                current_small = current_screenshot.resize((new_width, new_height), Image.BILINEAR)

                change_percent = calculate_difference(last_screenshot, current_small)

                if change_percent >= CHANGE_THRESHOLD:
                    frame_count += 1
                    buffer = io.BytesIO()
                    current_small.save(buffer, format='JPEG', quality=JPEG_QUALITY)
                    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                    socketio.emit('frame', {
                        'image': img_base64,
                        'original_size': {'width': width, 'height': height},
                        'display_size': {'width': new_width, 'height': new_height},
                        'frame_id': frame_count,
                        'change_percent': round(change_percent, 2)
                    }, room=sid)

                    print(f"📤 Frame {frame_count}: {change_percent:.2f}% changed")

                    last_screenshot = current_small
                    del buffer, img_base64

                if checks_count % 500 == 0:
                    elapsed = time.time() - start_time
                    checks_per_sec = checks_count / elapsed if elapsed > 0 else 0
                    frames_per_sec = frame_count / elapsed if elapsed > 0 else 0
                    efficiency = (frame_count / checks_count * 100) if checks_count > 0 else 0
                    print(f"📊 Stats: {checks_count} checks, {frame_count} frames sent, "
                          f"{checks_per_sec:.0f} checks/s, {frames_per_sec:.1f} FPS, "
                          f"{efficiency:.1f}% efficiency")

                time.sleep(CHECK_INTERVAL)

            except Exception as e:
                print(f"❌ Capture error: {e}")
                traceback.print_exc()
                time.sleep(0.5)

    except Exception as e:
        print(f"❌ Stream error: {e}")
        traceback.print_exc()
    finally:
        with streaming_lock:
            if sid in streaming_threads:
                # remove client entry
                del streaming_threads[sid]

        elapsed = time.time() - start_time
        print(f"🛑 Stream stopped: {sid[:8]}")
        print(f"   Total checks: {checks_count}")
        print(f"   Frames sent: {frame_count}")
        print(f"   Duration: {elapsed:.1f}s")
        try:
            efficiency = (frame_count / checks_count * 100) if checks_count > 0 else 0
            print(f"   Efficiency: {efficiency:.1f}%")
        except:
            pass

@socketio.on('connect')
def handle_connect(auth):
    token = None
    if auth and isinstance(auth, dict):
        token = auth.get('token')
    if not token:
        token = request.args.get('token')
    if token != AUTH_TOKEN:
        print(f"❌ Unauthorized: {request.sid[:8]}")
        return False
    print(f"✅ Connected: {request.sid[:8]}")
    return True

@socketio.on('disconnect')
def handle_disconnect():
    with streaming_lock:
        # mark streaming False so thread loop exits cleanly
        if request.sid in streaming_threads:
            streaming_threads[request.sid]['streaming'] = False
    print(f"👋 Disconnected: {request.sid[:8]}")

@socketio.on('start_stream')
def handle_start_stream(data):
    if not verify_token(data):
        emit('error', {'message': 'Unauthorized'})
        return
    print(f"🚀 Starting event-driven stream: {request.sid[:8]}")
    with streaming_lock:
        # initialize per-client state
        streaming_threads[request.sid] = {'streaming': True, 'paused': False}
    thread = threading.Thread(target=stream_screen, args=(request.sid,), daemon=True)
    thread.start()

@socketio.on('control')
def handle_control(data):
    if not verify_token(data):
        emit('error', {'message': 'Unauthorized'})
        return
    try:
        # Respect server-side paused flag: ignore control if paused
        with streaming_lock:
            client_state = streaming_threads.get(request.sid)
            if client_state and client_state.get('paused', False):
                # ignore control events while paused
                return

        cmd_type = data.get('type')
        if cmd_type == 'mouse_move':
            x, y = data['x'], data['y']
            pyautogui.moveTo(x, y, _pause=False)
        elif cmd_type == 'mouse_click':
            button = data.get('button', 'left')
            pyautogui.click(button=button, _pause=False)
        elif cmd_type == 'mouse_double_click':
            pyautogui.doubleClick(_pause=False)
        elif cmd_type == 'mouse_right_click':
            pyautogui.rightClick(_pause=False)
        elif cmd_type == 'key_press':
            key = data['key']
            pyautogui.press(key, _pause=False)
        elif cmd_type == 'type_text':
            text = data['text']
            pyautogui.write(text, interval=0)
    except Exception as e:
        print(f"❌ Control error: {e}")
        traceback.print_exc()

# ----------------------
# Host hotkey notification thread (r+4 = pause, r+5 = resume)
# ----------------------
def hotkey_notify_thread():
    """
    Listens for global hotkeys:
      r+4 => send 'pause' notify to all connected clients
      r+5 => send 'resume' notify to all connected clients
    Requires `keyboard` package: pip install keyboard
    On Windows, running the script as Administrator may be required for system-wide hotkeys.
    """
    try:
        import keyboard
    except Exception as e:
        print("⚠️ 'keyboard' package not available. Install with: pip install keyboard")
        print("Host notifications disabled until 'keyboard' is installed.")
        return

    def send_pause():
        msg = "Ruk ja lawde."
        print("🔔 Host hotkey pressed: PAUSE - notifying clients")
        with streaming_lock:
            for sid, state in list(streaming_threads.items()):
                try:
                    # set paused flag server-side
                    state['paused'] = True
                    socketio.emit('notify', {'action': 'pause', 'message': msg}, room=sid)
                    print(f" - paused {sid[:8]}")
                except Exception as ex:
                    print(f"Error emitting pause to {sid}: {ex}")

    def send_resume():
        msg = "Owner resumed access. You may continue interacting with the host machine."
        print("🔔 Host hotkey pressed: RESUME - notifying clients")
        with streaming_lock:
            for sid, state in list(streaming_threads.items()):
                try:
                    # clear paused flag server-side
                    state['paused'] = False
                    socketio.emit('notify', {'action': 'resume', 'message': msg}, room=sid)
                    print(f" - resumed {sid[:8]}")
                except Exception as ex:
                    print(f"Error emitting resume to {sid}: {ex}")

    # Register hotkeys (system-wide)
    try:
        # Using 'r+4' and 'r+5' as requested
        keyboard.add_hotkey('r+4', send_pause)
        keyboard.add_hotkey('r+5', send_resume)
        print("🔔 Hotkeys registered: r+4 (pause) and r+5 (resume).")
        # Block this thread and let keyboard listener run
        keyboard.wait()
    except Exception as e:
        print("⚠️ Failed to register hotkeys:", e)
        traceback.print_exc()

if __name__ == '__main__':
    # Start the hotkey notifier thread (daemon so it doesn't block exit)
    hk_thread = threading.Thread(target=hotkey_notify_thread, daemon=True)
    hk_thread.start()

    print("\n🔥 EVENT-DRIVEN CAPTURE RUNNING:")
    print("   ✓ Hotkeys: r+4 = pause (notify), r+5 = resume")
    print(f"   • Scale: {SCALE_FACTOR}, Quality: {JPEG_QUALITY}, Check interval: {CHECK_INTERVAL}s, Threshold: {CHANGE_THRESHOLD}%")
    print("\n✅ Starting on port 5003...")
    print("=" * 60)

    socketio.run(app, host='0.0.0.0', port=5003, debug=False, allow_unsafe_werkzeug=True)
