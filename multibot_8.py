#!/usr/bin/env python3
import meshtastic
import meshtastic.serial_interface
from pubsub import pub
import time
import logging
import logging.handlers
import os
import threading
import random
import json

# ── Config ────────────────────────────────────────────────────────────────────
DEBUG          = False
HEARTBEAT_MINS = 15
DAILY_SUMMARY  = True
LOG_DIR        = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
DATA_DIR       = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
BOARD_MAX      = 10      # max bulletin board posts to keep
MEMO_MAX       = 20      # max memos to store
TRIVIA_TIMEOUT = 120     # seconds before active trivia question expires

# ── Community announcements (edit these as needed) ────────────────────────────
ANNOUNCEMENTS = [
    'Welcome to the local Meshtastic mesh! Say "help" to MultiBot for commands.',
    'MultiBot is a community mesh bot. All are welcome to use it.',
    'Mesh tip: Use "snr" to check your signal quality to this node.',
]

# ── Fortune messages ──────────────────────────────────────────────────────────
FORTUNES = [
    'The mesh is strong with you today.',
    'A clear signal is a happy signal.',
    'Every packet finds its way home eventually.',
    'Good things come to those who wait for ACK.',
    'Your node is a beacon in the noise.',
    'The best antenna is the one you have with you.',
    'Keep calm and mesh on.',
    'May your hops be few and your SNR be high.',
    'Adventure awaits beyond the next repeater.',
    'You are never truly lost while the mesh is up.',
    '73 de MultiBot - best regards to all.',
    'A rising tide lifts all nodes.',
]

# ── Trivia questions ──────────────────────────────────────────────────────────
TRIVIA = [
    ('What does LoRa stand for?',
     'long range', 'Long Range'),
    ('What frequency band does Meshtastic use in the US?',
     '915', '915MHz'),
    ('What does SNR stand for?',
     'signal to noise ratio', 'Signal to Noise Ratio'),
    ('What does ACK stand for?',
     'acknowledgement', 'Acknowledgement'),
    ('What does GPS stand for?',
     'global positioning system', 'Global Positioning System'),
    ('What protocol does Meshtastic use for routing?',
     'flood', 'Flood routing'),
    ('What does RSSI stand for?',
     'received signal strength indicator', 'Received Signal Strength Indicator'),
    ('What does ISM band stand for?',
     'industrial scientific medical', 'Industrial Scientific Medical'),
    ('How many hops does Meshtastic allow by default?',
     '3', '3 hops'),
    ('What type of modulation does LoRa use?',
     'spread spectrum', 'Chirp Spread Spectrum'),
]

# ── Directory setup ───────────────────────────────────────────────────────────
os.makedirs(LOG_DIR,  exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

LOG_MAIN      = os.path.join(LOG_DIR, 'multibot.log')
LOG_TEXT      = os.path.join(LOG_DIR, 'text.log')
LOG_POSITION  = os.path.join(LOG_DIR, 'position.log')
LOG_TELEMETRY = os.path.join(LOG_DIR, 'telemetry.log')
LOG_NODEINFO  = os.path.join(LOG_DIR, 'nodeinfo.log')
LOG_SUMMARY   = os.path.join(LOG_DIR, 'summary.log')

DATA_BOARD    = os.path.join(DATA_DIR, 'board.txt')
DATA_MEMOS    = os.path.join(DATA_DIR, 'memos.txt')
DATA_CHECKINS = os.path.join(DATA_DIR, 'checkins.txt')
DATA_NODES    = os.path.join(DATA_DIR, 'nodes.txt')
DATA_EMERGENCY= os.path.join(DATA_DIR, 'emergency.txt')

# ── Logging setup ─────────────────────────────────────────────────────────────
FMT       = '%(asctime)s  %(levelname)-8s  %(message)s'
DATEFMT   = '%Y-%m-%d %H:%M:%S'
formatter = logging.Formatter(FMT, datefmt=DATEFMT)

def _make_handler(filepath, rotate_mb=5, backup_count=7):
    h = logging.handlers.RotatingFileHandler(
        filepath, maxBytes=rotate_mb * 1024 * 1024,
        backupCount=backup_count, encoding='utf-8')
    h.setFormatter(formatter)
    return h

def _make_console_handler():
    h = logging.StreamHandler()
    h.setFormatter(formatter)
    if hasattr(h.stream, 'reconfigure'):
        try: h.stream.reconfigure(encoding='utf-8')
        except Exception: pass
    return h

log = logging.getLogger('multibot')
log.setLevel(logging.DEBUG if DEBUG else logging.INFO)
log.addHandler(_make_handler(LOG_MAIN))
log.addHandler(_make_console_handler())

def _specialist(name, filepath):
    lg = logging.getLogger(f'multibot.{name}')
    lg.setLevel(logging.INFO)
    lg.addHandler(_make_handler(filepath, rotate_mb=10, backup_count=14))
    lg.propagate = False
    return lg

log_text      = _specialist('text',      LOG_TEXT)
log_position  = _specialist('position',  LOG_POSITION)
log_telemetry = _specialist('telemetry', LOG_TELEMETRY)
log_nodeinfo  = _specialist('nodeinfo',  LOG_NODEINFO)
log_summary   = _specialist('summary',   LOG_SUMMARY)

# ── Packet type labels ────────────────────────────────────────────────────────
PACKET_LABELS = {
    'TEXT_MESSAGE_APP':  'TEXT',     'POSITION_APP':    'POSITION',
    'TELEMETRY_APP':     'TELEMETRY','NODEINFO_APP':     'NODEINFO',
    'ROUTING_APP':       'ROUTING',  'ADMIN_APP':        'ADMIN',
    'WAYPOINT_APP':      'WAYPOINT', 'TRACEROUTE_APP':   'TRACEROUTE',
    'NEIGHBORINFO_APP':  'NEIGHBORINFO', 'MAP_REPORT_APP': 'MAP_REPORT',
}

# ── Canned responses ──────────────────────────────────────────────────────────
RESPONSES = {
    'ping':      'pong',
    'hello':     'Hello! MultiBot here.',
    'hi':        'Hi there!',
    'hey':       'Hey! What can I do for you?',
    'yo':        'Yo! Bot online.',
    'help':      'MultiBot v2.5 - Say "help info", "help mesh", "help social", '
                 '"help board", or "help fun" for command categories.',
    'help info': 'INFO: time, date, uptime, status, version, about, info, '
                 'traffic, count, nearby, lastseen <n>, announce',
    'help mesh': 'MESH: hops, snr, nearby, count, lastseen <n>, '
                 'traffic, checkin <name>, active',
    'help social': 'SOCIAL: ping, hello, hi, hey, yo, gm, gn, 73, cq, '
                   'sos, lol, thanks, ack, test, weather, location, fortune',
    'help board': 'BOARD: post <msg>, board (read), memo <node> <msg>, '
                  'inbox (get your memos)',
    'help fun':   'FUN: fortune, trivia, trivia <answer>',
    'status':    'Bot is running normally.',
    'version':   'MultiBot v2.5',
    'about':     'MultiBot v2.5 - An automated Meshtastic mesh bot. '
                 'I respond to commands and report mesh info. '
                 'Say "help" to get started. I do not store personal data.',
    'ack':       'ACK received.',
    'test':      'Test successful - you reached MultiBot!',
    'weather':   'No weather data available. Try a weather service node nearby.',
    'location':  'I do not share my location. Stay safe out there.',
    'info':      'MultiBot v2.5 | Say "help" for commands.',
    'gm':        'Good morning! Hope the bands are clear today.',
    'gn':        'Good night! 73.',
    '73':        '73! Best regards from MultiBot.',
    'cq':        'CQ CQ - MultiBot responding. Go ahead.',
    'sos':       'SOS received! I am just a bot - please contact emergency services.',
    'lol':       'Ha! Glad to brighten your day.',
    'thanks':    'You are welcome!',
    'thank you': 'You are welcome!',
}

# ── Bot class ─────────────────────────────────────────────────────────────────
class MultiBot:
    def __init__(self):
        self.start_time      = time.time()
        self._daily_reset    = self._next_midnight()
        self.stats           = self._empty_stats()
        self.welcomed_nodes  = set()

        # Trivia state: {sender_id: (question, answer, expiry_time)}
        self._trivia_active  = {}
        self._trivia_lock    = threading.Lock()

        self.interface = meshtastic.serial_interface.SerialInterface()
        pub.subscribe(self.on_receive,    "meshtastic.receive")
        pub.subscribe(self.on_connection, "meshtastic.connection.established")

        self._print_startup_summary()

        threading.Thread(target=self._heartbeat_loop,      daemon=True).start()
        threading.Thread(target=self._daily_summary_loop,  daemon=True).start()

    # ── Stats ─────────────────────────────────────────────────────────────────
    def _empty_stats(self):
        return {
            'packets_seen': 0, 'texts_received': 0, 'commands_matched': 0,
            'replies_sent': 0, 'unknown_cmds':   0, 'position_pkts':    0,
            'telemetry_pkts': 0, 'nodeinfo_pkts': 0, 'other_pkts':       0,
        }

    def _next_midnight(self):
        now = time.localtime()
        return time.mktime((now.tm_year, now.tm_mon, now.tm_mday,
                            0, 0, 0, 0, 0, -1)) + 86400

    # ── Startup summary ───────────────────────────────────────────────────────
    def _print_startup_summary(self):
        sep = '=' * 60
        log.info(sep)
        log.info('  MultiBot v2.5 starting up')
        log.info(sep)
        try:
            user     = self.interface.getMyUser()
            metadata = self.interface.getMetadata() if hasattr(self.interface, 'getMetadata') else None
            nodes    = self.interface.nodes or {}
            log.info(f"  Node ID    : {user.get('id', 'unknown')}")
            log.info(f"  Long name  : {user.get('longName', 'unknown')}")
            log.info(f"  Short name : {user.get('shortName', 'unknown')}")
            if metadata:
                log.info(f"  Firmware   : {getattr(metadata, 'firmwareVersion', 'unknown')}")
                log.info(f"  Region     : {getattr(metadata, 'region', 'unknown')}")
            try:
                channels = self.interface.localNode.channels
                primary  = next((c for c in channels if c.role == c.role.PRIMARY), None)
                ch_name  = primary.settings.name if primary and primary.settings.name else 'LongFast (default)'
                log.info(f"  Channel    : {ch_name}")
            except Exception:
                log.info('  Channel    : (unavailable)')
            log.info(f"  Known nodes: {len(nodes)}")
            log.info(f"  Log dir    : {LOG_DIR}")
            log.info(f"  Data dir   : {DATA_DIR}")
            log.info(f"  Debug mode : {'ON' if DEBUG else 'OFF'}")
            log.info(f"  Heartbeat  : every {HEARTBEAT_MINS}m")
        except Exception as e:
            log.warning(f"  Could not read full device info: {e}")
        log.info(sep)
        log.info('Waiting for messages...')

    # ── Connection ────────────────────────────────────────────────────────────
    def on_connection(self, interface, topic=pub.AUTO_TOPIC):
        log.info('Connected to Meshtastic device')

    # ── Receive handler ───────────────────────────────────────────────────────
    def on_receive(self, packet, interface):
        try:
            self.stats['packets_seen'] += 1
            if 'decoded' not in packet:
                return

            decoded = packet['decoded']
            portnum = decoded.get('portnum', 'UNKNOWN')
            sender  = packet.get('fromId', 'unknown')
            label   = PACKET_LABELS.get(portnum, portnum)

            # Ignore our own packets
            if sender == self.interface.getMyUser().get('id'):
                return

            if DEBUG:
                log.debug(f"RAW [{label}] from {sender}:\n{packet}")

            # ── Position ──────────────────────────────────────────────────
            if portnum == 'POSITION_APP':
                self.stats['position_pkts'] += 1
                pos  = decoded.get('position', {})
                lat  = pos.get('latitudeI', 0) / 1e7
                lon  = pos.get('longitudeI', 0) / 1e7
                alt  = pos.get('altitude', '?')
                snr  = packet.get('rxSnr', '?')
                msg  = f"from {sender} | lat:{lat:.5f} lon:{lon:.5f} alt:{alt}m | SNR:{snr}"
                log.info(f"[POSITION] {msg}")
                log_position.info(msg)
                return

            # ── Telemetry ─────────────────────────────────────────────────
            elif portnum == 'TELEMETRY_APP':
                self.stats['telemetry_pkts'] += 1
                tel      = decoded.get('telemetry', {})
                dev      = tel.get('deviceMetrics', {})
                bat      = dev.get('batteryLevel', '?')
                volt     = dev.get('voltage', '?')
                ch_util  = dev.get('channelUtilization', '?')
                air_util = dev.get('airUtilTx', '?')
                snr      = packet.get('rxSnr', '?')
                if isinstance(ch_util,  float): ch_util  = f"{ch_util:.1f}"
                if isinstance(air_util, float): air_util = f"{air_util:.1f}"
                msg = (f"from {sender} | bat:{bat}% volt:{volt}V | "
                       f"ch_util:{ch_util}% air_util:{air_util}% | SNR:{snr}")
                log.info(f"[TELEMETRY] {msg}")
                log_telemetry.info(msg)
                self._record_node_activity(sender, packet)
                return

            # ── Node info ─────────────────────────────────────────────────
            elif portnum == 'NODEINFO_APP':
                self.stats['nodeinfo_pkts'] += 1
                user_info = decoded.get('user', {})
                name  = user_info.get('longName') or user_info.get('shortName') or sender
                short = user_info.get('shortName', '?')
                hw    = user_info.get('hwModel', '?')
                snr   = packet.get('rxSnr', '?')
                msg   = f"from {sender} | name:'{name}' short:'{short}' hw:{hw} | SNR:{snr}"
                log.info(f"[NODEINFO] {msg}")
                log_nodeinfo.info(msg)
                self._record_node_activity(sender, packet, name=name)
                return

            elif portnum != 'TEXT_MESSAGE_APP':
                self.stats['other_pkts'] += 1
                log.info(f"[{label}] from {sender}")
                return

            # ── Text messages ─────────────────────────────────────────────
            self.stats['texts_received'] += 1
            raw_text = decoded.get('text', '')
            try:
                text = raw_text.encode('utf-8', errors='replace').decode('utf-8')
            except Exception:
                text = repr(raw_text)
            text = text.strip()

            hops     = self._hops_taken(packet)
            snr      = packet.get('rxSnr', '?')
            rssi     = packet.get('rxRssi', '?')
            hop_str  = f"{hops}hop{'s' if hops != 1 else ''}" if hops is not None else "?hops"

            log.info(f"[TEXT] from {sender} | {hop_str} | SNR:{snr} RSSI:{rssi} | msg:'{text}'")
            log_text.info(f"from {sender} | {hop_str} | SNR:{snr} RSSI:{rssi} | msg:'{text}'")

            # Record node activity
            node_name = self._get_node_name(sender)
            self._record_node_activity(sender, packet, name=node_name)

            # Welcome first-time nodes this session
            if sender not in self.welcomed_nodes:
                self.welcomed_nodes.add(sender)
                welcome = ('Welcome to MultiBot! I am an automated mesh bot. '
                           'Say "help" for commands or "about" for more info.')
                log.info(f"  [WELCOME] -> {sender}")
                self.interface.sendText(welcome, destinationId=sender)
                time.sleep(1)

                # Deliver any waiting memos
                memos = self._get_memos(sender)
                if memos:
                    time.sleep(1)
                    for memo in memos:
                        self.interface.sendText(memo, destinationId=sender)
                        time.sleep(1)
                    self._clear_memos(sender)

            cmd   = text.lower()
            reply = self._handle_command(cmd, sender, packet, text)

            if reply is None:
                self.stats['unknown_cmds'] += 1
                return

            self.stats['commands_matched'] += 1
            self.stats['replies_sent']     += 1
            log.info(f"  -> {sender}: '{reply}'")
            log_text.info(f"  REPLY -> {sender}: '{reply}'")
            self.interface.sendText(reply, destinationId=sender)

        except Exception as e:
            log.error(f"Error handling packet: {e}", exc_info=DEBUG)

    # ── Command router ────────────────────────────────────────────────────────
    def _handle_command(self, cmd, sender, packet, raw_text):
        # Dynamic commands
        if cmd == 'time':         return time.strftime('Time: %H:%M:%S UTC')
        if cmd == 'date':         return time.strftime('Date: %Y-%m-%d')
        if cmd == 'uptime':       return self._uptime_str()
        if cmd == 'hops':         return self._hops_reply(packet)
        if cmd == 'nearby':       return self._nearby_reply()
        if cmd == 'snr':          return self._snr_reply(packet)
        if cmd == 'count':        return self._count_reply()
        if cmd == 'traffic':      return self._traffic_reply()
        if cmd == 'fortune':      return self._fortune_reply()
        if cmd == 'announce':     return self._announce_reply()
        if cmd == 'board':        return self._board_read_reply()
        if cmd == 'inbox':        return self._inbox_reply(sender)
        if cmd == 'active':       return self._active_nodes_reply()
        if cmd == 'trivia':       return self._trivia_question(sender)

        if cmd.startswith('lastseen '):
            return self._lastseen_reply(cmd[9:].strip())
        if cmd.startswith('checkin '):
            return self._checkin_reply(sender, cmd[8:].strip())
        if cmd.startswith('post '):
            return self._board_post_reply(sender, raw_text[5:].strip())
        if cmd.startswith('memo '):
            return self._memo_send_reply(sender, cmd[5:].strip(), raw_text[5:].strip())
        if cmd.startswith('emergency '):
            return self._emergency_reply(sender, raw_text[10:].strip())
        if cmd.startswith('trivia '):
            return self._trivia_answer(sender, cmd[7:].strip())
        if cmd.startswith('help '):
            return RESPONSES.get(cmd, 'Unknown help category. Try: help info, help mesh, help social, help board, help fun')
        if cmd in RESPONSES:
            return RESPONSES[cmd]
        return None

    # ── Hops ──────────────────────────────────────────────────────────────────
    def _hops_taken(self, packet):
        hop_start = packet.get('hopStart')
        hop_limit = packet.get('hopLimit')
        if hop_start is not None and hop_limit is not None:
            return hop_start - hop_limit
        return None

    def _hops_reply(self, packet):
        hops = self._hops_taken(packet)
        if hops is None:
            hop_limit = packet.get('hopLimit')
            if hop_limit is not None:
                return f"Your message arrived with {hop_limit} hop(s) remaining."
            return "Hop count unavailable for your firmware version."
        if hops == 0:
            return "You reached me directly - 0 hops (direct link)."
        return f"Your message took {hops} hop{'s' if hops != 1 else ''} to reach me."

    # ── Nearby ────────────────────────────────────────────────────────────────
    def _nearby_reply(self):
        try:
            nodes = self.interface.nodes
            if not nodes:
                return "No nodes in my database yet."
            my_id   = self.interface.getMyUser().get('id', '')
            entries = []
            for node_id, info in nodes.items():
                if node_id == my_id:
                    continue
                user       = info.get('user', {})
                name       = user.get('longName') or user.get('shortName') or node_id
                snr        = info.get('snr')
                snr_str    = f" SNR:{snr:.1f}dB" if snr is not None else ""
                last_heard = info.get('lastHeard')
                age_str    = f" {int((time.time() - last_heard) / 60)}m ago" if last_heard else ""
                entries.append(f"{name}{snr_str}{age_str}")
            if not entries:
                return "No other nodes known."
            header = f"Nearby ({len(entries)} node{'s' if len(entries) != 1 else ''}): "
            full   = header + ', '.join(entries)
            return full[:197] + '...' if len(full) > 200 else full
        except Exception as e:
            log.error(f"nearby error: {e}")
            return "Could not retrieve node list."

    # ── SNR ───────────────────────────────────────────────────────────────────
    def _snr_reply(self, packet):
        snr  = packet.get('rxSnr')
        rssi = packet.get('rxRssi')
        if snr is None and rssi is None:
            return "Signal info not available for your packet."
        parts = []
        if snr  is not None: parts.append(f"SNR:{snr:.1f}dB")
        if rssi is not None: parts.append(f"RSSI:{rssi}dBm")
        quality = ""
        if snr is not None:
            if snr >= 5:    quality = " (excellent)"
            elif snr >= 0:  quality = " (good)"
            elif snr >= -5: quality = " (fair)"
            else:           quality = " (weak)"
        return f"Your signal at my node: {' '.join(parts)}{quality}"

    # ── Count ─────────────────────────────────────────────────────────────────
    def _count_reply(self):
        try:
            nodes  = self.interface.nodes or {}
            my_id  = self.interface.getMyUser().get('id', '')
            others = [n for n in nodes if n != my_id]
            if not others:
                return "No other nodes known yet."
            now    = time.time()
            active = sum(1 for n in others
                         if nodes[n].get('lastHeard') and (now - nodes[n]['lastHeard']) < 3600)
            return (f"Mesh count: {len(others)} node{'s' if len(others) != 1 else ''} known, "
                    f"{active} active in last 60m.")
        except Exception as e:
            log.error(f"count error: {e}")
            return "Could not retrieve node count."

    # ── Traffic ───────────────────────────────────────────────────────────────
    def _traffic_reply(self):
        s = self.stats
        total = s['packets_seen']
        if total == 0:
            return "No packets seen yet this session."
        return (f"Traffic this session: {total} total | "
                f"Text:{s['texts_received']} Pos:{s['position_pkts']} "
                f"Tel:{s['telemetry_pkts']} Node:{s['nodeinfo_pkts']} "
                f"Other:{s['other_pkts']}")

    # ── Lastseen ──────────────────────────────────────────────────────────────
    def _lastseen_reply(self, search_name):
        try:
            nodes   = self.interface.nodes or {}
            my_id   = self.interface.getMyUser().get('id', '')
            search  = search_name.lower()
            matches = []
            for node_id, info in nodes.items():
                if node_id == my_id:
                    continue
                user       = info.get('user', {})
                long_name  = (user.get('longName')  or '').lower()
                short_name = (user.get('shortName') or '').lower()
                if search in long_name or search in short_name:
                    display    = user.get('longName') or user.get('shortName') or node_id
                    last_heard = info.get('lastHeard')
                    if last_heard:
                        age_min = int((time.time() - last_heard) / 60)
                        age_str = (f"{age_min}m ago" if age_min < 60
                                   else f"{age_min // 60}h {age_min % 60}m ago")
                    else:
                        age_str = "never"
                    matches.append(f"{display}: last seen {age_str}")
            if not matches:
                return f"No node matching '{search_name}' found."
            return ' | '.join(matches)[:200]
        except Exception as e:
            log.error(f"lastseen error: {e}")
            return "Could not search node list."

    # ── Fortune ───────────────────────────────────────────────────────────────
    def _fortune_reply(self):
        return random.choice(FORTUNES)

    # ── Announce ──────────────────────────────────────────────────────────────
    def _announce_reply(self):
        if not ANNOUNCEMENTS:
            return "No announcements at this time."
        return ANNOUNCEMENTS[int(time.time() / 3600) % len(ANNOUNCEMENTS)]

    # ── Bulletin board ────────────────────────────────────────────────────────
    def _board_post_reply(self, sender, message):
        if not message:
            return "Usage: post <your message>"
        name      = self._get_node_name(sender)
        timestamp = time.strftime('%m/%d %H:%M')
        entry     = f"[{timestamp}] {name}: {message[:80]}\n"
        try:
            lines = []
            if os.path.exists(DATA_BOARD):
                with open(DATA_BOARD, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            lines.append(entry)
            lines = lines[-BOARD_MAX:]
            with open(DATA_BOARD, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            log.info(f"  [BOARD POST] {sender}: {message[:80]}")
            return f"Posted to board! Say 'board' to read all {len(lines)} post{'s' if len(lines) != 1 else ''}."
        except Exception as e:
            log.error(f"board post error: {e}")
            return "Could not post to board."

    def _board_read_reply(self):
        try:
            if not os.path.exists(DATA_BOARD):
                return "Board is empty. Say 'post <msg>' to add a message."
            with open(DATA_BOARD, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
            if not lines:
                return "Board is empty. Say 'post <msg>' to add a message."
            # Return most recent post with count
            latest = lines[-1]
            total  = len(lines)
            reply  = f"Board ({total} post{'s' if total != 1 else ''}), latest: {latest}"
            return reply[:200]
        except Exception as e:
            log.error(f"board read error: {e}")
            return "Could not read board."

    # ── Memos ─────────────────────────────────────────────────────────────────
    def _memo_send_reply(self, sender, args, raw_args):
        parts = args.split(' ', 1)
        if len(parts) < 2:
            return "Usage: memo <node_name> <message>"
        target_search = parts[0].lower()
        message       = raw_args.split(' ', 1)[1] if ' ' in raw_args else ''
        if not message:
            return "Usage: memo <node_name> <message>"

        # Find target node ID by name
        target_id = self._find_node_id(target_search)
        if not target_id:
            return f"No node matching '{target_search}' found."

        from_name = self._get_node_name(sender)
        timestamp = time.strftime('%m/%d %H:%M')
        entry     = f"{target_id}|{from_name}|{timestamp}|{message[:100]}\n"

        try:
            lines = []
            if os.path.exists(DATA_MEMOS):
                with open(DATA_MEMOS, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            lines.append(entry)
            lines = lines[-MEMO_MAX:]
            with open(DATA_MEMOS, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            log.info(f"  [MEMO] {sender} -> {target_id}: {message[:80]}")
            return f"Memo saved! It will be delivered when {target_search} next messages me."
        except Exception as e:
            log.error(f"memo send error: {e}")
            return "Could not save memo."

    def _get_memos(self, node_id):
        try:
            if not os.path.exists(DATA_MEMOS):
                return []
            with open(DATA_MEMOS, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            memos = []
            for line in lines:
                parts = line.strip().split('|', 3)
                if len(parts) == 4 and parts[0] == node_id:
                    memos.append(f"Memo from {parts[1]} ({parts[2]}): {parts[3]}")
            return memos
        except Exception as e:
            log.error(f"get memos error: {e}")
            return []

    def _clear_memos(self, node_id):
        try:
            if not os.path.exists(DATA_MEMOS):
                return
            with open(DATA_MEMOS, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            remaining = [l for l in lines if not l.startswith(f"{node_id}|")]
            with open(DATA_MEMOS, 'w', encoding='utf-8') as f:
                f.writelines(remaining)
        except Exception as e:
            log.error(f"clear memos error: {e}")

    def _inbox_reply(self, sender):
        memos = self._get_memos(sender)
        if not memos:
            return "Your inbox is empty."
        self._clear_memos(sender)
        return f"You have {len(memos)} memo{'s' if len(memos) != 1 else ''}. Delivering now..."

    # ── Check-in ──────────────────────────────────────────────────────────────
    def _checkin_reply(self, sender, name):
        if not name:
            return "Usage: checkin <your name or callsign>"
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        entry     = f"{timestamp} | {sender} | {name}\n"
        try:
            with open(DATA_CHECKINS, 'a', encoding='utf-8') as f:
                f.write(entry)
            log.info(f"  [CHECKIN] {sender} as '{name}'")
            return f"Checked in as '{name}'! Your check-in has been logged. 73!"
        except Exception as e:
            log.error(f"checkin error: {e}")
            return "Could not record check-in."

    # ── Emergency ─────────────────────────────────────────────────────────────
    def _emergency_reply(self, sender, message):
        if not message:
            return "Usage: emergency <your situation>"
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        entry     = f"{timestamp} | {sender} | {message}\n"
        try:
            with open(DATA_EMERGENCY, 'a', encoding='utf-8') as f:
                f.write(entry)
            log.warning(f"  [EMERGENCY] {sender}: {message}")
            return ("EMERGENCY LOGGED. I am an automated bot - "
                    "please also contact emergency services (911). "
                    "Your message and node ID have been recorded.")
        except Exception as e:
            log.error(f"emergency log error: {e}")
            return "Could not log emergency. Please contact 911 directly."

    # ── Node tracking ─────────────────────────────────────────────────────────
    def _record_node_activity(self, node_id, packet, name=None):
        try:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            snr       = packet.get('rxSnr', '?')
            if name is None:
                name = self._get_node_name(node_id)

            lines = []
            if os.path.exists(DATA_NODES):
                with open(DATA_NODES, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

            # Check if node is new
            known_ids = set()
            for line in lines:
                parts = line.split('|')
                if parts:
                    known_ids.add(parts[0].strip())

            is_new = node_id not in known_ids

            # Append activity record
            entry = f"{node_id} | {name} | {timestamp} | SNR:{snr} | {'NEW' if is_new else 'SEEN'}\n"
            lines.append(entry)
            # Keep last 500 records
            lines = lines[-500:]
            with open(DATA_NODES, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            if is_new:
                log.info(f"  [NEW NODE] {node_id} '{name}' first seen!")

        except Exception as e:
            log.error(f"node tracking error: {e}")

    def _active_nodes_reply(self):
        try:
            if not os.path.exists(DATA_NODES):
                return "No node activity recorded yet."
            with open(DATA_NODES, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Count unique nodes seen today
            today   = time.strftime('%Y-%m-%d')
            seen    = set()
            new_cnt = 0
            for line in lines:
                if today in line:
                    parts = line.split('|')
                    if parts:
                        node_id = parts[0].strip()
                        seen.add(node_id)
                        if 'NEW' in line:
                            new_cnt += 1

            if not seen:
                return "No node activity recorded today yet."
            return (f"Today: {len(seen)} unique node{'s' if len(seen) != 1 else ''} active, "
                    f"{new_cnt} new first-time node{'s' if new_cnt != 1 else ''}.")
        except Exception as e:
            log.error(f"active nodes error: {e}")
            return "Could not read node activity."

    # ── Trivia ────────────────────────────────────────────────────────────────
    def _trivia_question(self, sender):
        q, _, display_answer = random.choice(TRIVIA)
        expiry = time.time() + TRIVIA_TIMEOUT
        with self._trivia_lock:
            self._trivia_active[sender] = (q, display_answer.lower(), expiry)
        return f"TRIVIA: {q} (say 'trivia <answer>')"

    def _trivia_answer(self, sender, answer):
        with self._trivia_lock:
            if sender not in self._trivia_active:
                return "No active trivia question. Say 'trivia' to start one!"
            q, correct, expiry = self._trivia_active[sender]
            if time.time() > expiry:
                del self._trivia_active[sender]
                return f"Too slow! The question expired. The answer was: {correct}. Say 'trivia' for a new one."
            if answer.lower() in correct.lower() or correct.lower() in answer.lower():
                del self._trivia_active[sender]
                return f"Correct! Well done. Say 'trivia' for another question."
            return f"Not quite! Try again or say 'trivia' to skip."

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _get_node_name(self, node_id):
        try:
            nodes = self.interface.nodes or {}
            info  = nodes.get(node_id, {})
            user  = info.get('user', {})
            return user.get('longName') or user.get('shortName') or node_id
        except Exception:
            return node_id

    def _find_node_id(self, search):
        try:
            nodes  = self.interface.nodes or {}
            my_id  = self.interface.getMyUser().get('id', '')
            for node_id, info in nodes.items():
                if node_id == my_id:
                    continue
                user  = info.get('user', {})
                long  = (user.get('longName')  or '').lower()
                short = (user.get('shortName') or '').lower()
                if search in long or search in short:
                    return node_id
            return None
        except Exception:
            return None

    def _uptime_str(self):
        elapsed = int(time.time() - self.start_time)
        h, rem  = divmod(elapsed, 3600)
        m, s    = divmod(rem, 60)
        if h:  return f"Uptime: {h}h {m}m {s}s"
        if m:  return f"Uptime: {m}m {s}s"
        return f"Uptime: {s}s"

    def _stats_summary(self, label='Heartbeat'):
        s = self.stats
        return (
            f"-- {label} -- {self._uptime_str()} | "
            f"Packets:{s['packets_seen']} Texts:{s['texts_received']} "
            f"Cmds:{s['commands_matched']} Replies:{s['replies_sent']} "
            f"Unknown:{s['unknown_cmds']} | "
            f"Pos:{s['position_pkts']} Tel:{s['telemetry_pkts']} "
            f"Node:{s['nodeinfo_pkts']} Other:{s['other_pkts']}"
        )

    # ── Background threads ────────────────────────────────────────────────────
    def _heartbeat_loop(self):
        while True:
            time.sleep(HEARTBEAT_MINS * 60)
            log.info(self._stats_summary())

    def _daily_summary_loop(self):
        while True:
            now  = time.time()
            wait = max(0, self._daily_reset - now)
            time.sleep(wait)
            if DAILY_SUMMARY:
                date_str = time.strftime('%Y-%m-%d', time.localtime(self._daily_reset - 1))
                summary  = self._stats_summary(label=f"Daily Summary {date_str}")
                log.info(summary)
                log_summary.info(summary)
            self.stats        = self._empty_stats()
            self._daily_reset = self._next_midnight()

    # ── Main loop ─────────────────────────────────────────────────────────────
    def run(self):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log.info('Shutting down...')
            log.info(self._stats_summary())
            log_summary.info(self._stats_summary(label='Shutdown'))
        finally:
            self.interface.close()


if __name__ == "__main__":
    bot = MultiBot()
    bot.run()
