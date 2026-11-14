import threading
import time
import unittest

from imperium_operation_gate import FairOperationGate


class FairOperationGateTests(unittest.TestCase):
    def test_sequential_access_and_nonblocking_rejection(self):
        gate = FairOperationGate()
        self.assertTrue(gate.acquire())
        self.assertTrue(gate.locked())
        self.assertFalse(gate.acquire(blocking=False))
        gate.release()
        self.assertFalse(gate.locked())
        self.assertTrue(gate.acquire(blocking=False))
        gate.release()

    def test_waiting_request_has_priority_over_new_poll(self):
        gate = FairOperationGate()
        gate.acquire()
        started = threading.Event()
        completed = threading.Event()
        observations = []

        def foreground():
            started.set()
            success = gate.acquire(timeout=2)
            observations.append(success)
            if success:
                gate.release()
            completed.set()

        thread = threading.Thread(target=foreground)
        thread.start()
        self.assertTrue(started.wait(timeout=1))
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            with gate._condition:
                if len(gate._waiters):
                    break
            time.sleep(0.005)
        with gate._condition:
            self.assertEqual(len(gate._waiters), 1)
        gate.release()
        self.assertFalse(gate.acquire(blocking=False))
        self.assertTrue(completed.wait(timeout=2))
        thread.join(timeout=1)
        self.assertEqual(observations, [True])
        self.assertTrue(gate.acquire(blocking=False))
        gate.release()

    def test_timed_out_ticket_is_removed(self):
        gate = FairOperationGate()
        gate.acquire()
        self.assertFalse(gate.acquire(timeout=0.01))
        gate.release()
        self.assertTrue(gate.acquire(blocking=False))
        gate.release()

    def test_second_release_raises(self):
        gate = FairOperationGate()
        gate.acquire()
        gate.release()
        with self.assertRaises(RuntimeError):
            gate.release()

    def test_fifo_waiters(self):
        gate = FairOperationGate()
        gate.acquire()
        acquired_order = []
        threads = []
        for index in range(3):
            def worker(value=index):
                if gate.acquire(timeout=2):
                    acquired_order.append(value)
                    gate.release()
            thread = threading.Thread(target=worker)
            thread.start()
            threads.append(thread)
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                with gate._condition:
                    if len(gate._waiters) == index + 1:
                        break
                time.sleep(0.005)
            with gate._condition:
                self.assertEqual(len(gate._waiters), index + 1)
        gate.release()
        for thread in threads:
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(acquired_order, [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
