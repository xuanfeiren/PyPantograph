import asyncio
from pathlib import Path
import functools as F
import concurrent.futures
import threading

# Shared thread pool executor with a single worker to ensure all operations
# use the same thread and event loop (important for loop-bound resources like subprocesses)
_executor = None
_executor_lock = threading.Lock()
_worker_loop = None
_worker_loop_lock = threading.Lock()

def _get_executor():
    """Get or create the shared single-worker executor."""
    global _executor
    with _executor_lock:
        if _executor is None or _executor._shutdown:
            _executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        return _executor

def _get_worker_loop():
    """Get or create the persistent event loop for the worker thread."""
    global _worker_loop
    with _worker_loop_lock:
        if _worker_loop is None or _worker_loop.is_closed():
            _worker_loop = asyncio.new_event_loop()
        return _worker_loop

def _run_in_worker(coro):
    """Run a coroutine in the worker thread's event loop."""
    loop = _get_worker_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

def to_sync(func):
    """
    Wraps an async function to make it synchronous.
    
    Always runs in a dedicated worker thread with a persistent event loop
    to ensure async resources (like subprocesses) work correctly across
    multiple calls, regardless of whether the caller is in an async context.
    """
    @F.wraps(func)
    def wrapper(*args, **kwargs):
        executor = _get_executor()
        future = executor.submit(_run_in_worker, func(*args, **kwargs))
        return future.result()
    return wrapper

async def check_output(*args, **kwargs):
    p = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **kwargs,
    )
    stdout_data, stderr_data = await p.communicate()
    if p.returncode == 0:
        return stdout_data

def _get_proc_cwd():
    return Path(__file__).parent

def _get_proc_path():
    return _get_proc_cwd() / "pantograph-repl"

async def get_lean_path_async(project_path):
    """
    Extracts the `LEAN_PATH` variable from a project path.
    """
    p = await check_output(
        'lake', 'env', 'printenv', 'LEAN_PATH',
        cwd=project_path,
    )
    return p

get_lean_path = to_sync(get_lean_path_async)
