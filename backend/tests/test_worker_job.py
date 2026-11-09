import os
import subprocess
import sys
import textwrap
import time
import unittest


@unittest.skipUnless(os.name == "nt", "Windows job objects only")
class WorkerDiesWithBackendTests(unittest.TestCase):
    def test_worker_is_killed_when_backend_is_force_killed(self):
        # A stand-in backend puts a long-running "worker" in the job, prints its PID, then waits.
        backend = textwrap.dedent("""
            import subprocess, sys, time
            from server.services.runtime_service import _kill_with_parent_job
            job, kernel32 = _kill_with_parent_job()
            worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
            kernel32.AssignProcessToJobObject(job, int(worker._handle))
            print(worker.pid, flush=True)
            time.sleep(60)
        """)
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        parent = subprocess.Popen([sys.executable, "-c", backend], cwd=root, stdout=subprocess.PIPE, text=True)
        worker_pid = int(parent.stdout.readline())
        parent.kill()  # TerminateProcess: no atexit, like Task Manager or a crash
        parent.wait()
        deadline = time.monotonic() + 10
        alive = True
        while alive and time.monotonic() < deadline:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {worker_pid}", "/NH"],
                                 capture_output=True, text=True).stdout
            alive = str(worker_pid) in out
            time.sleep(0.2)
        if alive:
            subprocess.run(["taskkill", "/PID", str(worker_pid), "/F"], capture_output=True)
        self.assertFalse(alive, "worker outlived its backend")


if __name__ == "__main__":
    unittest.main()
