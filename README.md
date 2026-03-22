# MultiBot

A feature-rich automated Meshtastic mesh network bot running on a Raspberry Pi with a Heltec V3 LoRa device. MultiBot is an open community node that responds to commands, reports mesh intelligence, and provides useful utilities to anyone on the mesh.

---

## Hardware

- Raspberry Pi (tested on Pi 5, compatible with Pi 3/4/Zero 2 W)
- Heltec V3 LoRa device (connected via USB)
- 8dBi 915MHz fiberglass outdoor antenna (recommended)
- U.FL to SMA pigtail adapter

---

## Features

### Mesh Intelligence
- `snr` — signal quality of your packet at this node
- `hops` — how many hops your message took to arrive
- `nearby` — list of known nodes with SNR and last heard time
- `count` — total known nodes and how many are active
- `lastseen <name>` — when a specific node was last heard
- `traffic` — packet breakdown for the current session
- `active` — unique nodes seen today including first-timers

### Community Utilities
- `post <message>` — post to the bulletin board
- `board` — read the latest bulletin board posts
- `memo <node> <message>` — leave a message for another node
- `inbox` — retrieve your waiting memos
- `checkin <name>` — register your callsign or name
- `announce` — read the current community announcement
- `emergency <situation>` — log a distress call with timestamp

### Info Commands
- `time` — current UTC time
- `date` — current date
- `uptime` — how long the bot has been running
- `status` — bot health check
- `version` — current bot version
- `about` — bot description and usage info

### Fun & Social
- `fortune` — random mesh-themed fortune
- `trivia` — multiple choice LoRa/Meshtastic trivia
- `ping` — pong
- `gm` / `gn` — good morning / good night
- `73` — ham radio sign-off
- `cq` — CQ call response
- `sos` — emergency acknowledgement (logs and advises calling 911)

### Help System
- `help` — overview and category list
- `help info` — info commands
- `help mesh` — mesh intelligence commands
- `help social` — social commands
- `help board` — bulletin board and memo commands
- `help fun` — trivia and fortune

---

## Web Dashboard

MultiBot includes a local web dashboard (`dashboard.py`) built with Flask. It provides:

- Live color-coded log viewer
- Session stats (packets, texts, commands, replies)
- Bot start/stop/restart controls
- Node activity table with NEW node detection
- Bulletin board viewer
- Check-in log
- Emergency log

Access it from any device on your local network — no internet required.

---

## Setup

### Requirements

```bash
pip install meshtastic pypubsub flask
```

Or using a virtual environment (recommended):

```bash
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install meshtastic pypubsub
```

### Configure your device name

```bash
meshtastic --set-owner "MultiBot" --set-owner-short "MBOT"
```

### Run the bot

```bash
source .venv/bin/activate
python3 multibot.py
```

### Run the dashboard (separate terminal)

```bash
source .venv/bin/activate
python3 dashboard.py
```

Then open `http://<your-pi-ip>:5000` in a browser.

---

## File Structure

```
multibot.py       — main bot
dashboard.py      — web dashboard
logs/             — rotating log files (auto-created, gitignored)
  multibot.log    — all activity
  text.log        — text messages only
  position.log    — position packets
  telemetry.log   — telemetry packets
  nodeinfo.log    — node info packets
  summary.log     — daily summaries
data/             — persistent data (auto-created, gitignored)
  board.txt       — bulletin board posts
  memos.txt       — pending memos
  checkins.txt    — check-in log
  nodes.txt       — node activity history
  emergency.txt   — emergency log
```

---

## Configuration

At the top of `multibot.py`:

```python
DEBUG          = False   # Set True for raw packet dumps
HEARTBEAT_MINS = 15      # Heartbeat log interval in minutes
DAILY_SUMMARY  = True    # Log daily summary at midnight
```

Community announcements can be edited in the `ANNOUNCEMENTS` list and fortunes in the `FORTUNES` list.

---

## Mesh Etiquette

- Bot is set to **Client mode** — not Router mode — to minimize channel utilization
- Only responds when directly messaged — no beaconing or broadcasting
- Tested stable at 1-2% channel utilization on a 200+ node mesh

---

## License

MIT License — free to use, modify, and share. Contributions welcome.

---

## Frequency

- 915MHz (US region)
