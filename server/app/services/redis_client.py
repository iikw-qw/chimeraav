"""
Redis-клиент: пул, Streams (задачи), Pub/Sub, кеш, warmup_coefficient.
Зависит от: config.py
"""

import json
from typing import Any, Optional, List, Dict
import redis.asyncio as aioredis
from app.config import settings


class RedisClient:
    def __init__(self):
        self.pool: Optional[aioredis.ConnectionPool] = None
        self.redis: Optional[aioredis.Redis] = None
        self.pubsub: Optional[aioredis.client.PubSub] = None

    async def connect(self):
        self.pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=50,
            decode_responses=True,
        )
        self.redis = aioredis.Redis(connection_pool=self.pool)
        await self.redis.ping()

    async def disconnect(self):
        if self.redis:
            await self.redis.close()
        if self.pool:
            await self.pool.disconnect()

    async def ping(self) -> bool:
        try:
            return await self.redis.ping()
        except Exception:
            return False

    # ═══ Streams (очередь задач) ═══

    async def add_task(self, stream: str, data: Dict[str, Any]) -> str:
        return await self.redis.xadd(stream, {"data": json.dumps(data)})

    async def create_consumer_group(self, stream: str, group: str):
        try:
            await self.redis.xgroup_create(stream, group, id="0", mkstream=True)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def read_tasks(
        self, stream: str, group: str, consumer: str, count: int = 10, block: int = 5000
    ) -> List[Dict]:
        results = await self.redis.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=count,
            block=block,
        )
        tasks = []
        if results:
            for stream_name, messages in results:
                for msg_id, fields in messages:
                    tasks.append({
                        "id": msg_id,
                        "data": json.loads(fields.get("data", "{}")),
                    })
        return tasks

    async def ack_task(self, stream: str, group: str, msg_id: str):
        await self.redis.xack(stream, group, msg_id)

    # ═══ Pub/Sub ═══

    async def publish(self, channel: str, message: Any):
        data = json.dumps(message) if not isinstance(message, str) else message
        await self.redis.publish(channel, data)

    async def subscribe(self, *channels: str) -> aioredis.client.PubSub:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(*channels)
        return pubsub

    # ═══ Cache ═══

    async def set_cache(self, key: str, value: Any, ttl: int = 300):
        data = json.dumps(value) if not isinstance(value, str) else value
        await self.redis.set(key, data, ex=ttl)

    async def get_cache(self, key: str) -> Optional[Any]:
        data = await self.redis.get(key)
        if data is None:
            return None
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return data

    async def delete_cache(self, key: str):
        await self.redis.delete(key)

    # ═══ Warmup Coefficient ═══

    async def set_warmup_coefficient(self, value: float):
        await self.redis.set("chimera:warmup_coefficient", str(value))

    async def get_warmup_coefficient(self) -> float:
        val = await self.redis.get("chimera:warmup_coefficient")
        return float(val) if val else 0.0

    # ═══ Stream SPS/PPS storage ═══

    async def set_stream_sps_pps(self, device_id: str, sps_pps: bytes):
        await self.redis.set(f"stream:sps_pps:{device_id}", sps_pps)

    async def get_stream_sps_pps(self, device_id: str) -> Optional[bytes]:
        r = aioredis.Redis(connection_pool=self.pool, decode_responses=False)
        return await r.get(f"stream:sps_pps:{device_id}")

    # ═══ Generic hash operations ═══

    async def hset(self, name: str, key: str, value: Any):
        data = json.dumps(value) if not isinstance(value, str) else value
        await self.redis.hset(name, key, data)

    async def hget(self, name: str, key: str) -> Optional[Any]:
        data = await self.redis.hget(name, key)
        if data is None:
            return None
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return data

    async def hgetall(self, name: str) -> Dict:
        data = await self.redis.hgetall(name)
        result = {}
        for k, v in data.items():
            try:
                result[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                result[k] = v
        return result

    async def hdel(self, name: str, *keys: str):
        await self.redis.hdel(name, *keys)


redis_client = RedisClient()
