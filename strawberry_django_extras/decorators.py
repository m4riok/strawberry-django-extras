import asyncio
import inspect

from asgiref.sync import async_to_sync, sync_to_async


def is_async() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    else:
        return True


def sync_or_async(func=None, *, thread_sensitive=True):
    def decorator(f):
        if is_async():
            if inspect.iscoroutinefunction(f):
                return f
            return sync_to_async(f, thread_sensitive=thread_sensitive)

        if inspect.iscoroutinefunction(f):
            return async_to_sync(f)
        return f

    if func is None:
        return decorator

    return decorator(func)
