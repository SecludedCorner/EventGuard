"""Finite synthetic Tk session inside an already-assigned private Windows Job."""
import os
import sys
import threading
import time

from .desktop_fixture import DesktopFixtureController
from .gui import EventGuardWindow
from .processes import adopt_current_job
from .runtime import atomic_json


def _owner_eof(cancel):
    try:
        os.read(sys.stdin.fileno(), 1)  # Raw read avoids buffered stdin shutdown locks.
    except (OSError, ValueError):
        pass
    cancel.set()


def run_fixture(root, seconds, job_name, *, cancel=None):
    """Do not create any scope/window until membership in the owner Job is proven."""
    if type(seconds) is not int or not 1 <= seconds <= 900:
        raise ValueError('desktop_fixture_duration_invalid')
    keeper = adopt_current_job(job_name)
    membership = keeper.receipt()
    controller = DesktopFixtureController(root, 'desktop-ux-session')
    result_path = controller.root.parent.parent/'worker-exit.json'
    window = app = None
    reason = 'user_close'
    try:
        import tkinter as tk
        window = tk.Tk()
        app = EventGuardWindow(window, controller)
        from tkinter import ttk
        from .desktop_ux_tasks import instructions
        notebook = app.events.master.master
        tasks = ttk.Frame(notebook, padding=8)
        tasks.columnconfigure(0, weight=1)
        tasks.rowconfigure(0, weight=1)
        text = tk.Text(tasks, wrap='word')
        text.insert('1.0', instructions())
        text.configure(state='disabled')
        text.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(tasks, orient='vertical', command=text.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        text.configure(yscrollcommand=scroll.set)
        notebook.add(tasks, text='六項合成任務')
        deadline = time.monotonic()+seconds
        if cancel is None:
            cancel = threading.Event()
            threading.Thread(target=_owner_eof, args=(cancel,), daemon=True, name='fixture-owner-eof').start()
        def poll():
            nonlocal reason
            if cancel.is_set() or time.monotonic() >= deadline:
                reason = 'owner_eof' if cancel.is_set() else 'deadline'
                app.pause_and_exit()
            app._after(100, poll)
        app._after(100, poll)
        atomic_json(controller.root.parent.parent/'worker-ready.json', {
            'synthetic': True, 'fixture_root': 'reports/desktop-ux-session',
            'model_calls': 0, 'membership_verified': membership['kind'] == 'eventguard-private-job-keeper-v1'})
        window.mainloop()
        state = 'closed' if app.verified_close else 'shutdown_unconfirmed'
    except Exception as error:
        state = 'unavailable'
        reason = type(error).__name__  # Never save raw exception/path contents.
    finally:
        if app is not None:
            app.dispose()
            app.worker.shutdown(wait=True)
        controller.close()
        if window is not None:
            try:
                window.destroy()
            except Exception:
                pass
    result = {'kind': 'desktop-synthetic-session-v1', 'synthetic': True, 'state': state, 'reason': reason,
        'gui_worker_exited': app is None or not app.worker.thread.is_alive(), 'model_calls': 0,
        'machine_scan_executed': False, 'ack_performed': False, 'participant_results': None}
    atomic_json(result_path, result)
    return result
