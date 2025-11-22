"""Simple Redis queue helpers with an in-memory fallback when `redis` is not installed.
This keeps the dev environment runnable without external dependencies.
"""
import os
import json
import time

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')

try:
    import redis
    _HAS_REDIS = True
except Exception:
    redis = None
    _HAS_REDIS = False


class _InMemoryRedis:
    def __init__(self):
        self.store = {}
        self.queues = {}

    @classmethod
    def from_url(cls, url, decode_responses=True):
        return cls()

    def set(self, key, value):
        self.store[key] = value

    def get(self, key):
        return self.store.get(key)

    def lpush(self, key, value):
        q = self.queues.setdefault(key, [])
        q.insert(0, value)

    def brpop(self, key, timeout=0):
        # simple non-blocking pop for demo purposes
        q = self.queues.get(key, [])
        if not q:
            return None
        val = q.pop()
        return (key, val)


def redis_client():
    if _HAS_REDIS:
        return redis.from_url(REDIS_URL, decode_responses=True)
    else:
        return _InMemoryRedis()


def enqueue_job(job: dict):
    r = redis_client()
    job_id = job.get('job_id')
    key = f'job:{job_id}'
    r.set(key, json.dumps(job))
    r.lpush('queue:jobs', json.dumps(job))


def get_job(job_id: str):
    r = redis_client()
    key = f'job:{job_id}'
    data = r.get(key)
    if not data:
        return None
    try:
        return json.loads(data)
    except Exception:
        return None


def set_job_result(job_id: str, result: dict):
    r = redis_client()
    key = f'job:{job_id}'
    job = get_job(job_id) or {}
    job['result'] = result
    job['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    r.set(key, json.dumps(job))


def set_job_status(job_id: str, status: str):
    r = redis_client()
    key = f'job:{job_id}'
    job = get_job(job_id) or {}
    job['status'] = status
    job['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    r.set(key, json.dumps(job))
