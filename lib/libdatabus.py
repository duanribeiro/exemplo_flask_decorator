# -*- coding: utf-8 -*-

import json
import redis
import time

redis_inst = redis.Redis(charset="utf-8", decode_responses=True)


class DataBus:
    def flush(self):
        redis_inst.flushdb()

    def get(self, key):
        if redis_inst.type(key) == 'set':
            return redis_inst.smembers(key)

        value = redis_inst.get(key)
        if value is None:
            return None

        return json.loads(value)

    def set(self, key, value):
        redis_inst.set(key, json.dumps(value))

    def expire(self, key, time):
        """Set an expire flag on key name for `time` seconds.
        `time` can be represented by an integer or a Python timedelta object.

        https://redis-py.readthedocs.io/en/stable/#
        """
        redis_inst.expire(key, time)

    def exists(self, key):
        return redis_inst.exists(key)

    def publish(self, queue, value):
        redis_inst.publish(queue, value)

    def delete(self, key):
        if redis_inst.type(key) == 'set':
            keys = redis_inst.keys(key + '/*')
            redis_inst.delete(*keys)

        redis_inst.delete(key)

        index = key.rfind('/')
        if index > 0:
            parent_key = key[:index]
            childname = key[index + 1 :]
            redis_inst.srem(parent_key, childname)

    def increase_by_float(self, key, amount):
        redis_inst.incrbyfloat(key, amount)

    def decrease_by_float(self, key, amount):
        redis_inst.incrbyfloat(key, -abs(amount))

    def decrease_if_greater_than(self, key, amount, reset=False):
        max_attempts = 3
        amount = abs(amount)
        error_count = 0
        with redis_inst.pipeline() as pipe:
            while error_count < max_attempts:
                try:
                    pipe.watch(key)
                    if self.exists(key) and float(redis_inst.get(key)) < amount:
                        if reset:
                            pipe.set(key, 0.0)
                            break
                        else:
                            return False
                    else:
                        pipe.multi()
                        pipe.incrbyfloat(key, -amount)
                        pipe.execute()
                        break
                except redis.WatchError:
                    error_count += 1
                    time.sleep(2 / 1000)

            if error_count == max_attempts:
                raise RuntimeError('The operation cannot be done.')

        return True

    def get_dict(self, key):
        local_dict = {}
        value = databus.get(key)

        if type(value) == set:
            for i in value:
                local_dict[i] = self.get_dict(key + '/' + i)
        else:
            return value

        return local_dict

    def update_from_file(self, datafile, initial_key=''):
        with open(datafile) as json_file:
            data = json.load(json_file)
            self.__iterate__(data, parent_key=initial_key)

    def update_from_dict(self, dictionary, initial_key=''):
        self.__iterate__(dictionary, initial_key)

    def __iterate__(self, dictionary, parent_key=''):
        for key, value in dictionary.items():
            redis_inst.sadd(parent_key, key)
            current_key = parent_key + '/' + key

            if isinstance(value, dict):
                self.__iterate__(value, current_key)
                continue

            redis_inst.set(current_key, json.dumps(value))

    def overwrite_from_file(self, datafile, initial_key):
        with open(datafile) as json_file:
            data = json.load(json_file)
            self.delete(initial_key)
            self.__iterate__(data, parent_key=initial_key)


databus = DataBus()
