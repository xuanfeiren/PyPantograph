import asyncio
from pathlib import Path
import functools as F
import concurrent.futures
import threading

# Thread-local storage for persistent event loops
_loop_local = threading.local()

# Shared thread pool executor (lazily initialized)
_executor = None
_executor_lock = threading.Lock()

def _get_executor():
    """Get or create the shared executor."""
    global _executor
    with _executor_lock:
        if _executor is None or _executor._shutdown:
            _executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        return _executor

def _get_or_create_loop():
    """Get or create a persistent event loop for the current thread."""
    if not hasattr(_loop_local, 'loop') or _loop_local.loop is None or _loop_local.loop.is_closed():
        _loop_local.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop_local.loop)
    return _loop_local.loop

def to_sync(func):
    """
    Wraps an async function to make it synchronous.
    
    Uses a persistent event loop per thread to ensure async resources
    (like subprocesses) work correctly across multiple calls.
    
    If called from within a running event loop, runs in a separate thread
    with its own persistent loop.
    """
    @F.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            asyncio.get_running_loop()
            in_async_context = True
        except RuntimeError:
            in_async_context = False
        
        if in_async_context:
            # We're inside a running event loop - run in a separate thread
            executor = _get_executor()
            future = executor.submit(
                lambda: _get_or_create_loop().run_until_complete(func(*args, **kwargs))
            )
            return future.result()
        else:
            # No running loop - use persistent loop for this thread
            loop = _get_or_create_loop()
            return loop.run_until_complete(func(*args, **kwargs))
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
