from asyncio import iscoroutinefunction
from typing import AnyStr, NoReturn, Callable


class Signal:
    _listeners = {}

    @staticmethod
    def init_listeners(module: AnyStr):
        __import__(module)

    @classmethod
    def add_listener(cls, action: AnyStr, func: Callable) -> NoReturn:
        if cls._listeners.get(action):
            cls._listeners[action].append(func)
        else:
            cls._listeners[action] = [func]

    @classmethod
    async def _a_send(cls, action: AnyStr, **kwargs):
        if cls._listeners.get(action):
            for listener in cls._listeners[action]:
                if callable(listener):
                    await listener(**kwargs) if iscoroutinefunction(listener) else listener()

    @classmethod
    def _send(cls, action: AnyStr, **kwargs):
        if cls._listeners.get(action):
            for listener in cls._listeners[action]:
                if callable(listener):
                    listener(**kwargs)

    @classmethod
    def send(cls, mode, action: AnyStr, **kwargs) -> NoReturn:
        if mode in ('ASYNC', 'SYNC'):
            f = cls._a_send if mode is 'ASYNC' else cls._send
            return f(action, **kwargs)


def listen(action: AnyStr) -> Callable:
    def _decorator(func: Callable):
        Signal.add_listener(action, func)
    return _decorator
