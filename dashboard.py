#!/usr/bin/env python3
"""
MultiBot Dashboard - Local web interface for monitoring and controlling the bot.
Run with: python3 dashboard.py
Access at: http://<pi-ip>:5000
"""

from flask import Flask, jsonify, render_template_string, request
import os
import subprocess
import time

app = Flask(__name__)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
LOG_DIR   = os.path.join(BASE_DIR, 'logs')
DATA_DIR  = os.path.join(BASE_DIR, 'data')

LOG_MAIN      = os.path.join(LOG_DIR, 'multibot.log')
LOG_TEXT      = os.path.join(LOG_DIR, 'text.log')
DATA_NODES    = os.path.join(DATA_DIR, 'nodes.txt')
DATA_BOARD    = os.path.join(DATA_DIR, 'board.txt')
DATA_CHECKINS = os.path.join(DATA_DIR, 'checkins.txt')
DATA_EMERGENCY= os.path.join(DATA_DIR, 'emergency.txt')

BOT_SCRIPT = os.path.join(BASE_DIR, 'multibot.py')
VENV_PYTHON = os.path.join(BASE_DIR, '.venv', 'bin', 'python3')

# ── HTML Template ─────────────────────────────────────────────────────────────
TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MultiBot Dashboard</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700&display=swap');

  :root {
    --bg:       #0a0e17;
    --panel:    #0f1623;
    --border:   #1a2a3a;
    --accent:   #00d4ff;
    --accent2:  #00ff9f;
    --warn:     #ff6b35;
    --danger:   #ff3355;
    --text:     #c8d8e8;
    --muted:    #4a6080;
    --glow:     0 0 12px rgba(0,212,255,0.4);
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Share Tech Mono', monospace;
    font-size: 13px;
    line-height: 1.5;
    min-height: 100vh;
  }

  /* Animated grid background */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
  }

  .wrapper { position: relative; z-index: 1; padding: 20px; max-width: 1400px; margin: 0 auto; }

  /* Header */
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-bottom: 2px solid var(--accent);
    margin-bottom: 20px;
    box-shadow: var(--glow);
  }

  .logo {
    font-family: 'Orbitron', monospace;
    font-size: 20px;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: 3px;
    text-shadow: var(--glow);
  }

  .logo span { color: var(--accent2); }

  .status-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--muted);
  }

  .dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--muted);
    animation: pulse 2s infinite;
  }

  .dot.online  { background: var(--accent2); box-shadow: 0 0 8px var(--accent2); }
  .dot.offline { background: var(--danger);  box-shadow: 0 0 8px var(--danger); }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.4; }
  }

  /* Grid layout */
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 16px;
    margin-bottom: 16px;
  }

  .grid-wide { grid-column: 1 / -1; }

  /* Panels */
  .panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 2px;
    overflow: hidden;
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    background: rgba(0,212,255,0.04);
  }

  .panel-title {
    font-family: 'Orbitron', monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    color: var(--accent);
    text-transform: uppercase;
  }

  .panel-body { padding: 16px; }

  /* Stats grid */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }

  .stat-box {
    background: rgba(0,212,255,0.04);
    border: 1px solid var(--border);
    padding: 12px;
    text-align: center;
  }

  .stat-value {
    font-family: 'Orbitron', monospace;
    font-size: 24px;
    font-weight: 700;
    color: var(--accent);
    text-shadow: var(--glow);
  }

  .stat-label {
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 1px;
    margin-top: 4px;
    text-transform: uppercase;
  }

  /* Log viewer */
  .log-box {
    background: #060a10;
    border: 1px solid var(--border);
    height: 300px;
    overflow-y: auto;
    padding: 12px;
    font-size: 11px;
    line-height: 1.6;
    scroll-behavior: smooth;
  }

  .log-line { color: var(--text); word-break: break-all; }
  .log-line.info    { color: var(--text); }
  .log-line.warning { color: var(--warn); }
  .log-line.error   { color: var(--danger); }
  .log-line.text    { color: var(--accent2); }
  .log-line.position { color: #a78bfa; }
  .log-line.telemetry { color: #60a5fa; }
  .log-line.nodeinfo  { color: #fbbf24; }
  .log-line.heartbeat { color: var(--muted); font-style: italic; }

  /* Tables */
  table { width: 100%; border-collapse: collapse; font-size: 11px; }
  th {
    text-align: left;
    padding: 6px 8px;
    color: var(--accent);
    border-bottom: 1px solid var(--border);
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
  }
  td { padding: 5px 8px; border-bottom: 1px solid rgba(26,42,58,0.5); }
  tr:hover td { background: rgba(0,212,255,0.04); }
  .new-badge {
    background: var(--accent2);
    color: #000;
    font-size: 9px;
    padding: 1px 5px;
    border-radius: 2px;
    font-weight: bold;
    letter-spacing: 1px;
  }
  .emerg-row td { color: var(--danger); }

  /* Controls */
  .controls { display: flex; gap: 10px; flex-wrap: wrap; }

  .btn {
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    padding: 8px 18px;
    border: 1px solid;
    background: transparent;
    cursor: pointer;
    letter-spacing: 1px;
    text-transform: uppercase;
    transition: all 0.2s;
  }

  .btn-start  { border-color: var(--accent2); color: var(--accent2); }
  .btn-stop   { border-color: var(--danger);  color: var(--danger);  }
  .btn-restart{ border-color: var(--warn);    color: var(--warn);    }
  .btn-refresh{ border-color: var(--accent);  color: var(--accent);  }

  .btn:hover { filter: brightness(1.3); box-shadow: var(--glow); }
  .btn:active { transform: scale(0.97); }

  .bot-status-msg {
    margin-top: 10px;
    font-size: 11px;
    color: var(--muted);
    min-height: 18px;
  }

  /* Board posts */
  .board-post {
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
    font-size: 12px;
  }
  .board-post:last-child { border-bottom: none; }
  .board-meta { color: var(--accent); font-size: 10px; margin-bottom: 2px; }
  .board-msg  { color: var(--text); }

  /* Tab system for log */
  .tab-bar { display: flex; gap: 0; border-bottom: 1px solid var(--border); }
  .tab {
    padding: 7px 14px;
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--muted);
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
  }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }
  .tab:hover  { color: var(--text); }

  /* Auto-refresh indicator */
  .refresh-info {
    font-size: 10px;
    color: var(--muted);
    letter-spacing: 1px;
  }

  .empty { color: var(--muted); font-size: 11px; text-align: center; padding: 20px; }

  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: var(--border); }
</style>
</head>
<body>
<div class="wrapper">

  <header>
    <div class="logo">MULTI<span>BOT</span> // DASHBOARD</div>
    <div class="status-pill">
      <div class="dot" id="bot-dot"></div>
      <span id="bot-status-text">checking...</span>
      <span style="color:var(--border)">|</span>
      <span class="refresh-info">AUTO-REFRESH 10s</span>
    </div>
  </header>

  <!-- Stats row -->
  <div class="grid" style="grid-template-columns: 2fr 1fr;">

    <div class="panel">
      <div class="panel-header">
        <span class="panel-title">Session Stats</span>
        <span class="refresh-info" id="last-updated"></span>
      </div>
      <div class="panel-body">
        <div class="stats-grid" id="stats-grid">
          <div class="stat-box"><div class="stat-value" id="s-packets">-</div><div class="stat-label">Packets</div></div>
          <div class="stat-box"><div class="stat-value" id="s-texts">-</div><div class="stat-label">Texts</div></div>
          <div class="stat-box"><div class="stat-value" id="s-cmds">-</div><div class="stat-label">Commands</div></div>
          <div class="stat-box"><div class="stat-value" id="s-replies">-</div><div class="stat-label">Replies</div></div>
          <div class="stat-box"><div class="stat-value" id="s-pos">-</div><div class="stat-label">Position</div></div>
          <div class="stat-box"><div class="stat-value" id="s-tel">-</div><div class="stat-label">Telemetry</div></div>
        </div>
      </div>
    </div>

    <!-- Bot controls -->
    <div class="panel">
      <div class="panel-header"><span class="panel-title">Bot Control</span></div>
      <div class="panel-body">
        <div class="controls">
          <button class="btn btn-start"   onclick="botAction('start')">Start</button>
          <button class="btn btn-stop"    onclick="botAction('stop')">Stop</button>
          <button class="btn btn-restart" onclick="botAction('restart')">Restart</button>
        </div>
        <div class="bot-status-msg" id="control-msg"></div>
      </div>
    </div>

  </div>

  <!-- Log viewer -->
  <div class="panel" style="margin-bottom:16px;">
    <div class="panel-header">
      <span class="panel-title">Live Log</span>
      <div class="tab-bar" style="border:none; margin:0;">
        <div class="tab active" onclick="switchLog('main', this)">Main</div>
        <div class="tab" onclick="switchLog('text', this)">Text</div>
      </div>
    </div>
    <div class="log-box" id="log-box"></div>
  </div>

  <!-- Bottom grid -->
  <div class="grid">

    <!-- Node activity -->
    <div class="panel">
      <div class="panel-header"><span class="panel-title">Node Activity</span></div>
      <div class="panel-body" style="padding:0;">
        <div style="max-height:280px; overflow-y:auto;">
          <table>
            <thead><tr><th>Node</th><th>Name</th><th>Last Seen</th><th>SNR</th><th></th></tr></thead>
            <tbody id="nodes-table"><tr><td colspan="5" class="empty">Loading...</td></tr></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Bulletin board -->
    <div class="panel">
      <div class="panel-header"><span class="panel-title">Bulletin Board</span></div>
      <div class="panel-body" id="board-body" style="max-height:280px; overflow-y:auto;">
        <div class="empty">Loading...</div>
      </div>
    </div>

  </div>

  <div class="grid">

    <!-- Check-ins -->
    <div class="panel">
      <div class="panel-header"><span class="panel-title">Check-ins</span></div>
      <div class="panel-body" style="padding:0;">
        <div style="max-height:220px; overflow-y:auto;">
          <table>
            <thead><tr><th>Time</th><th>Node</th><th>Name</th></tr></thead>
            <tbody id="checkins-table"><tr><td colspan="3" class="empty">Loading...</td></tr></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Emergency log -->
    <div class="panel">
      <div class="panel-header"><span class="panel-title" style="color:var(--danger);">Emergency Log</span></div>
      <div class="panel-body" style="padding:0;">
        <div style="max-height:220px; overflow-y:auto;">
          <table>
            <thead><tr><th>Time</th><th>Node</th><th>Message</th></tr></thead>
            <tbody id="emerg-table"><tr><td colspan="3" class="empty">No emergencies logged.</td></tr></tbody>
          </table>
        </div>
      </div>
    </div>

  </div>

</div>

<script>
let currentLog = 'main';

// ── Log viewer ────────────────────────────────────────────────────────────────
function classifyLine(line) {
  if (line.includes('[TEXT]') || line.includes('REPLY ->') || line.includes('WELCOME')) return 'text';
  if (line.includes('[POSITION]'))  return 'position';
  if (line.includes('[TELEMETRY]')) return 'telemetry';
  if (line.includes('[NODEINFO]'))  return 'nodeinfo';
  if (line.includes('Heartbeat') || line.includes('Daily Summary')) return 'heartbeat';
  if (line.includes('WARNING'))     return 'warning';
  if (line.includes('ERROR'))       return 'error';
  return 'info';
}

function loadLog() {
  fetch(`/api/log?type=${currentLog}&lines=100`)
    .then(r => r.json())
    .then(data => {
      const box = document.getElementById('log-box');
      const wasAtBottom = box.scrollHeight - box.clientHeight <= box.scrollTop + 5;
      box.innerHTML = data.lines.map(l =>
        `<div class="log-line ${classifyLine(l)}">${escHtml(l)}</div>`
      ).join('');
      if (wasAtBottom) box.scrollTop = box.scrollHeight;
    });
}

function switchLog(type, el) {
  currentLog = type;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  loadLog();
}

// ── Stats ─────────────────────────────────────────────────────────────────────
function loadStats() {
  fetch('/api/stats')
    .then(r => r.json())
    .then(d => {
      document.getElementById('s-packets').textContent = d.packets_seen   ?? '-';
      document.getElementById('s-texts').textContent   = d.texts_received ?? '-';
      document.getElementById('s-cmds').textContent    = d.commands_matched ?? '-';
      document.getElementById('s-replies').textContent = d.replies_sent   ?? '-';
      document.getElementById('s-pos').textContent     = d.position_pkts  ?? '-';
      document.getElementById('s-tel').textContent     = d.telemetry_pkts ?? '-';
      document.getElementById('last-updated').textContent =
        'updated ' + new Date().toLocaleTimeString();
    });
}

// ── Bot status ────────────────────────────────────────────────────────────────
function loadBotStatus() {
  fetch('/api/status')
    .then(r => r.json())
    .then(d => {
      const dot  = document.getElementById('bot-dot');
      const txt  = document.getElementById('bot-status-text');
      if (d.running) {
        dot.className = 'dot online';
        txt.textContent = 'ONLINE';
      } else {
        dot.className = 'dot offline';
        txt.textContent = 'OFFLINE';
      }
    });
}

function botAction(action) {
  const msg = document.getElementById('control-msg');
  msg.textContent = action.toUpperCase() + 'ING...';
  fetch(`/api/control/${action}`, { method: 'POST' })
    .then(r => r.json())
    .then(d => {
      msg.textContent = d.message;
      setTimeout(loadBotStatus, 2000);
    })
    .catch(() => { msg.textContent = 'Error communicating with server.'; });
}

// ── Node activity ─────────────────────────────────────────────────────────────
function loadNodes() {
  fetch('/api/nodes')
    .then(r => r.json())
    .then(data => {
      const tbody = document.getElementById('nodes-table');
      if (!data.nodes.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty">No node activity yet.</td></tr>';
        return;
      }
      tbody.innerHTML = data.nodes.map(n => `
        <tr>
          <td style="color:var(--muted);font-size:10px;">${escHtml(n.id)}</td>
          <td>${escHtml(n.name)}</td>
          <td style="color:var(--muted);">${escHtml(n.last_seen)}</td>
          <td style="color:var(--accent2);">${escHtml(n.snr)}</td>
          <td>${n.is_new ? '<span class="new-badge">NEW</span>' : ''}</td>
        </tr>`).join('');
    });
}

// ── Bulletin board ────────────────────────────────────────────────────────────
function loadBoard() {
  fetch('/api/board')
    .then(r => r.json())
    .then(data => {
      const body = document.getElementById('board-body');
      if (!data.posts.length) {
        body.innerHTML = '<div class="empty">No posts yet.</div>';
        return;
      }
      body.innerHTML = data.posts.slice().reverse().map(p => `
        <div class="board-post">
          <div class="board-meta">${escHtml(p.meta)}</div>
          <div class="board-msg">${escHtml(p.message)}</div>
        </div>`).join('');
    });
}

// ── Check-ins ─────────────────────────────────────────────────────────────────
function loadCheckins() {
  fetch('/api/checkins')
    .then(r => r.json())
    .then(data => {
      const tbody = document.getElementById('checkins-table');
      if (!data.checkins.length) {
        tbody.innerHTML = '<tr><td colspan="3" class="empty">No check-ins yet.</td></tr>';
        return;
      }
      tbody.innerHTML = data.checkins.slice().reverse().map(c => `
        <tr>
          <td style="color:var(--muted);font-size:10px;">${escHtml(c.time)}</td>
          <td style="color:var(--accent);font-size:10px;">${escHtml(c.node)}</td>
          <td>${escHtml(c.name)}</td>
        </tr>`).join('');
    });
}

// ── Emergency log ─────────────────────────────────────────────────────────────
function loadEmergency() {
  fetch('/api/emergency')
    .then(r => r.json())
    .then(data => {
      const tbody = document.getElementById('emerg-table');
      if (!data.events.length) {
        tbody.innerHTML = '<tr><td colspan="3" class="empty">No emergencies logged.</td></tr>';
        return;
      }
      tbody.innerHTML = data.events.slice().reverse().map(e => `
        <tr class="emerg-row">
          <td style="font-size:10px;white-space:nowrap;">${escHtml(e.time)}</td>
          <td style="font-size:10px;">${escHtml(e.node)}</td>
          <td>${escHtml(e.message)}</td>
        </tr>`).join('');
    });
}

function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Refresh all ───────────────────────────────────────────────────────────────
function refreshAll() {
  loadLog();
  loadStats();
  loadBotStatus();
  loadNodes();
  loadBoard();
  loadCheckins();
  loadEmergency();
}

refreshAll();
setInterval(refreshAll, 10000);
</script>
</body>
</html>
"""

# ── Helper functions ──────────────────────────────────────────────────────────
def read_tail(filepath, lines=100):
    """Read last N lines from a file."""
    try:
        if not os.path.exists(filepath):
            return []
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
        return [l.rstrip() for l in all_lines[-lines:]]
    except Exception:
        return []

def is_bot_running():
    """Check if multibot.py is running."""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'multibot.py'],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False

def parse_stats_from_log():
    """Parse the latest heartbeat line from the log to get stats."""
    lines = read_tail(LOG_MAIN, 500)
    stats = {}
    for line in reversed(lines):
        if 'Heartbeat' in line or 'Daily Summary' in line or 'Shutdown' in line:
            # Parse stats from heartbeat line
            import re
            pairs = re.findall(r'(\w+):(\d+)', line)
            for k, v in pairs:
                stats[k] = int(v)
            break
    return stats

# ── API routes ────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template_string(TEMPLATE)

@app.route('/api/log')
def api_log():
    log_type = request.args.get('type', 'main')
    lines    = int(request.args.get('lines', 100))
    filepath = LOG_TEXT if log_type == 'text' else LOG_MAIN
    return jsonify({'lines': read_tail(filepath, lines)})

@app.route('/api/stats')
def api_stats():
    return jsonify(parse_stats_from_log())

@app.route('/api/status')
def api_status():
    return jsonify({'running': is_bot_running()})

@app.route('/api/control/<action>', methods=['POST'])
def api_control(action):
    python = VENV_PYTHON if os.path.exists(VENV_PYTHON) else 'python3'
    try:
        if action == 'start':
            if is_bot_running():
                return jsonify({'message': 'Bot is already running.'})
            subprocess.Popen(
                [python, BOT_SCRIPT],
                cwd=BASE_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return jsonify({'message': 'Bot started.'})

        elif action == 'stop':
            result = subprocess.run(['pkill', '-f', 'multibot.py'], capture_output=True)
            if result.returncode == 0:
                return jsonify({'message': 'Bot stopped.'})
            return jsonify({'message': 'Bot was not running.'})

        elif action == 'restart':
            subprocess.run(['pkill', '-f', 'multibot.py'], capture_output=True)
            time.sleep(2)
            subprocess.Popen(
                [python, BOT_SCRIPT],
                cwd=BASE_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return jsonify({'message': 'Bot restarted.'})

        return jsonify({'message': f'Unknown action: {action}'})
    except Exception as e:
        return jsonify({'message': f'Error: {e}'})

@app.route('/api/nodes')
def api_nodes():
    try:
        if not os.path.exists(DATA_NODES):
            return jsonify({'nodes': []})
        with open(DATA_NODES, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        # Deduplicate — keep latest entry per node
        seen = {}
        for line in lines:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 5:
                node_id = parts[0]
                seen[node_id] = parts

        nodes = []
        for node_id, parts in seen.items():
            nodes.append({
                'id':       node_id,
                'name':     parts[1] if len(parts) > 1 else node_id,
                'last_seen': parts[2] if len(parts) > 2 else '?',
                'snr':      parts[3] if len(parts) > 3 else '?',
                'is_new':   'NEW' in (parts[4] if len(parts) > 4 else ''),
            })

        # Sort by last seen descending
        nodes.sort(key=lambda x: x['last_seen'], reverse=True)
        return jsonify({'nodes': nodes[:50]})
    except Exception as e:
        return jsonify({'nodes': [], 'error': str(e)})

@app.route('/api/board')
def api_board():
    try:
        if not os.path.exists(DATA_BOARD):
            return jsonify({'posts': []})
        with open(DATA_BOARD, 'r', encoding='utf-8', errors='replace') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        posts = []
        for line in lines:
            # Format: [MM/DD HH:MM] name: message
            import re
            m = re.match(r'\[(.+?)\] (.+?): (.+)', line)
            if m:
                posts.append({'meta': f"{m.group(1)} — {m.group(2)}", 'message': m.group(3)})
            else:
                posts.append({'meta': '', 'message': line})
        return jsonify({'posts': posts})
    except Exception as e:
        return jsonify({'posts': [], 'error': str(e)})

@app.route('/api/checkins')
def api_checkins():
    try:
        if not os.path.exists(DATA_CHECKINS):
            return jsonify({'checkins': []})
        with open(DATA_CHECKINS, 'r', encoding='utf-8', errors='replace') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        checkins = []
        for line in lines:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3:
                checkins.append({
                    'time': parts[0],
                    'node': parts[1],
                    'name': parts[2],
                })
        return jsonify({'checkins': checkins})
    except Exception as e:
        return jsonify({'checkins': [], 'error': str(e)})

@app.route('/api/emergency')
def api_emergency():
    try:
        if not os.path.exists(DATA_EMERGENCY):
            return jsonify({'events': []})
        with open(DATA_EMERGENCY, 'r', encoding='utf-8', errors='replace') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        events = []
        for line in lines:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 3:
                events.append({
                    'time':    parts[0],
                    'node':    parts[1],
                    'message': parts[2],
                })
        return jsonify({'events': events})
    except Exception as e:
        return jsonify({'events': [], 'error': str(e)})

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("MultiBot Dashboard starting...")
    print(f"Open http://$(hostname -I | awk '{{print $1}}'):5000 in your browser")
    app.run(host='0.0.0.0', port=5000, debug=False)
