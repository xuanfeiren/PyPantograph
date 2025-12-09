import asyncio
from pathlib import Path
import functools as F
import concurrent.futures
import threading

# Thread-local storage: each thread gets its own executor and event loop
# This enables parallel execution across multiple threads
_thread_local = threading.local()

def _get_executor():
    """
    Get or create a thread-local executor.
    
    Changed from global single-worker executor to thread-local executors
    to enable parallel execution. Each thread now has its own executor,
    allowing multiple Server instances to run concurrently.
    """
    if not hasattr(_thread_local, 'executor') or _thread_local.executor._shutdown:
        _thread_local.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    return _thread_local.executor

def _get_worker_loop():
    """
    Get or create a thread-local event loop.
    
    Changed from global event loop to thread-local loops to support
    parallel execution across multiple threads.
    """
    if not hasattr(_thread_local, 'loop') or _thread_local.loop.is_closed():
        _thread_local.loop = asyncio.new_event_loop()
    return _thread_local.loop

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
