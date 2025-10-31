cat > index.html <<'EOF'
<!DOCTYPE html>
<html>
<head>
  <title>Remote Desktop</title>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; overflow: hidden; }
    #status { position: fixed; top: 10px; left: 10px; background: rgba(0,0,0,0.8); padding: 10px 20px; border-radius: 5px; z-index: 1000; font-size: 14px; }
    #status.connected { color: #4CAF50; }
    #status.disconnected { color: #f44336; }
    #container { width: 100vw; height: 100vh; display: flex; justify-content: center; align-items: center; background: #1a1a1a; }
    #screen { max-width: 100%; max-height: 100%; border: 2px solid #333; cursor: crosshair; }
    #loading { position: absolute; font-size: 20px; color: #888; }
  </style>
</head>
<body>
  <div id="status" class="disconnected">Connecting...</div>
  <div id="container">
    <div id="loading">Loading screen...</div>
    <canvas id="screen" style="display:none;"></canvas>
  </div>
  <script>
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    const pcId = 'work-laptop';
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = protocol + '//' + window.location.host + '?token=' + token + '&type=browser&pc_id=' + pcId;

    let ws;
    let canvas = document.getElementById('screen');
    let ctx = canvas.getContext('2d');
    let statusEl = document.getElementById('status');
    let loadingEl = document.getElementById('loading');

    function connect() {
      statusEl.textContent = 'Connecting...';
      statusEl.className = 'disconnected';
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        statusEl.textContent = 'Connected';
        statusEl.className = 'connected';
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'screen') {
            loadingEl.style.display = 'none';
            canvas.style.display = 'block';
            const img = new Image();
            img.onload = () => {
              canvas.width = img.width;
              canvas.height = img.height;
              ctx.drawImage(img, 0, 0);
            };
            img.src = 'data:image/jpeg;base64,' + data.data;
          }
        } catch (e) {
          console.error('Error handling message:', e);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.onclose = () => {
        statusEl.textContent = 'Disconnected';
        statusEl.className = 'disconnected';
        setTimeout(connect, 3000);
      };
    }

    canvas.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      const y = (e.clientY - rect.top) / rect.height;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'mouse_move', x: x, y: y }));
      }
    });

    canvas.addEventListener('click', (e) => {
      const rect = canvas.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      const y = (e.clientY - rect.top) / rect.height;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'mouse_click', x: x, y: y, button: e.button }));
      }
    });

    document.addEventListener('keydown', (e) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'keydown', key: e.key }));
        e.preventDefault();
      }
    });

    connect();
  </script>
</body>
</html>
EOF