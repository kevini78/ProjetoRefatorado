import threading
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, Optional


class JobService:
    """Very small in-memory job runner abstraction.
    Not a full queue – fits current thread-based usage and can be swapped later.
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self, meta: Optional[Dict[str, Any]] = None) -> str:
        job_id = str(uuid.uuid4())
        with self._lock:
            self._jobs[job_id] = {
                'status': 'starting',
                'message': 'Iniciando processamento...',
                'progress': 0,
                'logs': [],
                'should_stop': False,
                'start_time': datetime.now().isoformat(),
                'end_time': None,
                'results': {},
                'meta': meta or {},
            }
        return job_id

    def enqueue(self, target: Callable, *args, meta: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        job_id = self.create(meta=meta)

        def _runner():
            try:
                self.update(job_id, status='running', message='Executando...')
                target(job_id, *args, **kwargs)
                # The target is responsible for updating status; fallback to completed
                self.update(job_id, status='completed')
            except Exception as e:
                self.update(job_id, status='error', message=str(e))
            finally:
                with self._lock:
                    self._jobs[job_id]['end_time'] = datetime.now().isoformat()

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        return job_id

    def update(self, job_id: str, **fields) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(fields)

    def log(self, job_id: str, message: str, level: str = 'info') -> None:
        entry = {'timestamp': datetime.now().isoformat(), 'message': message, 'type': level}
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].setdefault('logs', []).append(entry)

    def set_result(self, job_id: str, result: Dict[str, Any]) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]['results'] = result

    def status(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return dict(self._jobs.get(job_id) or {})

    def stop(self, job_id: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]['should_stop'] = True


def get_job_service(app) -> JobService:
    svc = app.extensions.get('job_service')
    if not svc:
        svc = JobService()
        app.extensions['job_service'] = svc
    return svc
