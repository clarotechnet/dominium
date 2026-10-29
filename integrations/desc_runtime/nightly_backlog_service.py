"""Daily backlog scheduling owned by the Dominium HTTP server, not by a browser."""
import json
import logging
import os
from pathlib import Path
import threading
import nightly_backlog_106 as batch


class NightlyBacklogService:
    def __init__(self, root, *, runner=batch.run, clock=batch.now, logger=None, rollover_path=None):
        self.root = Path(root)
        self.config_path = self.root / 'config' / 'nightly_backlog_settings.json'
        self.state_dir = self.root / 'config' / 'nightly_backlog_106'
        self.runner = runner
        self.rollover_path = Path(rollover_path) if rollover_path is not None else Path(r'\\wsl.localhost\Ubuntu\home\technet\BotDMV\data\desc_review\capture-rotation.json')
        self.clock = clock
        self.logger = logger or logging.getLogger('imperium')
        self.stop_event = threading.Event()
        self.thread = None
        self.base_url = batch.BASE
        self.running = False
        self.last_error = ''
        self.lock = threading.Lock()

    def enabled(self):
        try:
            return json.loads(self.config_path.read_text(encoding='utf-8')).get('enabled') is True
        except (OSError, ValueError):
            return False

    def set_enabled(self, value):
        if not isinstance(value, bool):
            raise ValueError('enabled deve ser booleano')
        with self.lock:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.config_path.with_suffix('.tmp')
            tmp.write_text(json.dumps({'enabled': value, 'hour': 23, 'timezone': 'America/Sao_Paulo'}, indent=2), encoding='utf-8')
            os.replace(tmp, self.config_path)
        return self.status()

    def status(self):
        day = self.clock().date().isoformat()
        try:
            last = json.loads((self.state_dir / f'schedule_{day}.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            last = None
        return dict(ok=True, enabled=self.enabled(), running=self.running,
                    server_scheduler_active=bool(self.thread and self.thread.is_alive()),
                    hour='23:00', timezone='America/Sao_Paulo', code='106', observation='',
                    transport='datasnap', profiles=list(batch.PROFILES), today=last,
                    last_error=self.last_error)

    def _signal_capture_rollover(self, current, day):
        # Only a genuinely started 23h batch rotates the visible DESC queue.
        # This records a boundary; it never erases photographs or active work.
        record = {
            'source': 'nightly_backlog_start',
            'date': day,
            'started_at': current.isoformat(),
            'retention_days': 7,
        }
        target = self.rollover_path
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + '.tmp')
        with temp.open('w', encoding='utf-8') as handle:
            json.dump(record, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)

    def tick(self):
        current = self.clock()
        if self.stop_event.is_set() or not self.enabled() or current.hour != 23:
            return
        day = current.date().isoformat()
        path = self.state_dir / f'schedule_{day}.json'
        self.state_dir.mkdir(parents=True, exist_ok=True)
        record = dict(date=day, state='running', started_at=current.isoformat())
        # Once per day, across restarts and even accidental second server instances.
        try:
            with path.open('x', encoding='utf-8') as file:
                json.dump(record, file)
                file.flush()
                os.fsync(file.fileno())
        except FileExistsError:
            return
        self.running = True
        self.logger.info('[BACKLOG-106] Inicio do lote diario %s', day)
        try:
            try:
                self._signal_capture_rollover(current, day)
            except (OSError, ValueError):
                # Failure to refresh the photo UI must not block an authorized batch.
                self.logger.exception('[BACKLOG-106] Nao foi possivel arquivar a fila DESC')
            report = self.runner(execute=True, clock=self.clock, pause=self.stop_event.wait,
                                 state_dir=self.state_dir,
                                 should_stop=lambda: self.stop_event.is_set() or not self.enabled())
            record.update(state='finished_with_errors' if any(p['errors'] for p in report['profiles'].values()) else 'finished', report=report)
        except Exception as exc:
            self.last_error = str(exc)
            record.update(state='review_required', error=str(exc))
            self.logger.exception('[BACKLOG-106] Falha no lote diario')
        finally:
            record['finished_at'] = self.clock().isoformat()
            try:
                tmp = path.with_suffix('.tmp')
                tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
                os.replace(tmp, path)
            finally:
                self.running = False
            self.logger.info('[BACKLOG-106] Lote %s: %s', day, record['state'])

    def _loop(self):
        # Give serve_forever time to begin before the local batch API is used.
        while not self.stop_event.wait(15):
            try:
                self.tick()
            except Exception as exc:
                self.last_error = str(exc)
                self.logger.exception('[BACKLOG-106] Falha no agendador; nenhuma repeticao forcada')

    def start(self, port=8765):
        if self.thread and self.thread.is_alive():
            return
        batch.BASE = f'http://127.0.0.1:{int(port)}'
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, name='dominium-backlog-106', daemon=True)
        self.thread.start()
        self.logger.info('[BACKLOG-106] Agendador nativo iniciado; 23h Brasilia; enabled=%s', self.enabled())

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
