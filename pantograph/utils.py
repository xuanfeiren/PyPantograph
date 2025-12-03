import asyncio
from pathlib import Path
import functools as F
import concurrent.futures

def to_sync(func):
    """
    Wraps an async function to make it synchronous.
    
    If called from within a running event loop (e.g., Jupyter, async program),
    runs the async function in a separate thread with its own event loop.
    Otherwise, uses asyncio.run() to create a new event loop.
    """
    @F.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop is not None:
            # We're inside a running event loop - run in a separate thread
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, func(*args, **kwargs))
                return future.result()
        else:
            # No running loop - use asyncio.run
            return asyncio.run(func(*args, **kwargs))
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
