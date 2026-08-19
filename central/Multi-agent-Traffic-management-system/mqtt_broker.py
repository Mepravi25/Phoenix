"""Embedded MQTT Broker using amqtt for local development without external Mosquitto."""
import asyncio
import logging
from amqtt.broker import Broker

config = {
    'listeners': {
        'default': {
            'type': 'tcp',
            'bind': '127.0.0.1:1883',
        },
    },
    'sys_interval': 10,
    'auth': {
        'allow-anonymous': True,
    }
}

async def main():
    broker = Broker(config)
    await broker.start()
    print("[MQTT Broker] Running on 127.0.0.1:1883...")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        await broker.shutdown()

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
