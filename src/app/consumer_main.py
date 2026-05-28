import asyncio

from faststream import FastStream

from app.infrastructure.messaging.consumer import broker

app = FastStream(broker)


def main() -> None:
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
