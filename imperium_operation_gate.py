"""Serializacao justa das operacoes do terminal Imperium/DataSnap.

Operacoes de fundo usam acquire(blocking=False); uma requisicao aguardando
impede que novas consultas oportunistas passem na sua frente.
"""
from collections import deque
import threading
import time


class FairOperationGate:
    """Substituto FIFO para o Lock de acesso compartilhado ao Imperium."""

    def __init__(self):
        self._condition = threading.Condition()
        self._active = False
        self._waiters = deque()

    def acquire(self, blocking=True, timeout=-1):
        if not blocking and timeout != -1:
            raise ValueError("timeout nao permitido com blocking=False")
        if timeout < -1:
            raise ValueError("timeout invalido")
        with self._condition:
            if not self._active and not self._waiters:
                self._active = True
                return True
            if not blocking:
                return False

            ticket = object()
            self._waiters.append(ticket)
            deadline = None if timeout == -1 else time.monotonic() + timeout
            try:
                while True:
                    if not self._active and self._waiters[0] is ticket:
                        self._waiters.popleft()
                        self._active = True
                        return True
                    remaining = None if deadline is None else deadline - time.monotonic()
                    if remaining is not None and remaining <= 0:
                        return False
                    self._condition.wait(timeout=remaining)
            finally:
                if ticket in self._waiters:
                    self._waiters.remove(ticket)
                    self._condition.notify_all()

    def release(self):
        with self._condition:
            if not self._active:
                raise RuntimeError("release unlocked lock")
            self._active = False
            self._condition.notify_all()

    def locked(self):
        with self._condition:
            return self._active

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *_):
        self.release()
