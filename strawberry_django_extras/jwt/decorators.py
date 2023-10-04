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


def sync_or_async(func):
    if is_async():
        if inspect.iscoroutinefunction(func):
            return func
        return sync_to_async(func)

    if inspect.iscoroutinefunction(func):
        return async_to_sync(func)
    return func
