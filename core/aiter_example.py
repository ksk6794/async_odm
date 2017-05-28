import asyncio


class A:
    a = ('a', 'b', 'c')
    i = 0

    async def __aiter__(self):
        return self

    async def __anext__(self):
        if self.i < len(self.a):
            res = self.a[self.i]
            self.i += 1
            return res
        else:
            raise StopAsyncIteration('')


async def main():
    async for item in A():
        print(item)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
