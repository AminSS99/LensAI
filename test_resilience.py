import asyncio
from functions.resilience import safe_call, safe_call_async

def test_safe_call_success():
    def my_func(a, b):
        return a + b

    assert safe_call(my_func, 1, 2) == 3

def test_safe_call_exception(capsys):
    def my_func(a, b):
        raise ValueError("Oops")

    assert safe_call(my_func, 1, 2) is None
    assert safe_call(my_func, 1, 2, default=10) == 10
    captured = capsys.readouterr()
    assert captured.out.count("WARNING: my_func failed: Oops. Returning default value.\n") == 2

def test_safe_call_kwargs(capsys):
    def my_func(a, b=0):
        if b == 0:
            raise ValueError("Oops")
        return a + b

    assert safe_call(my_func, 1, b=2) == 3
    assert safe_call(my_func, 1, b=0, default=42) == 42
    captured = capsys.readouterr()
    assert captured.out == "WARNING: my_func failed: Oops. Returning default value.\n"

def test_safe_call_async_success():
    async def my_func(a, b):
        await asyncio.sleep(0.01)
        return a + b

    assert asyncio.run(safe_call_async(my_func, 1, 2)) == 3

def test_safe_call_async_exception(capsys):
    async def my_func(a, b):
        await asyncio.sleep(0.01)
        raise ValueError("Oops")

    assert asyncio.run(safe_call_async(my_func, 1, 2)) is None
    assert asyncio.run(safe_call_async(my_func, 1, 2, default=10)) == 10
    captured = capsys.readouterr()
    assert captured.out.count("WARNING: my_func failed: Oops. Returning default value.\n") == 2
