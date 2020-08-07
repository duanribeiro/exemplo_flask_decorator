#!/usr/bin/env python
import os
import json
import libep
import time
import sys
import uuid
import inspect
from amqpstorm.base import IDLE_WAIT
from amqpstorm import Connection
from amqpstorm import AMQPChannelError
from amqpstorm import AMQPMessageError
from amqpstorm import AMQPInvalidArgument
from amqpstorm import AMQPConnectionError

log_info = libep.log_info
log_error = libep.log_error


class busmsg2:
    type = ""
    src = ""
    pload = {}
    content = ""
    header = {}

    def __init__(self, body):
        self.pload = json.loads(body.body)
        self.src = self.pload['src']
        self.type = self.pload['type']
        self.content = self.pload['content']


def msg_compose(src, type, content):
    pload = {}
    pload['src'] = src
    pload['type'] = type
    pload['content'] = content
    return pload


class MessageQueue(object):
    def __init__(self, host='127.0.0.1', user='guest', password='guest', queue_name="", durable=True):
        super(MessageQueue, self).__init__()
        self.stop_consuming = False
        self.queue_name = queue_name
        retries_limit = 3
        retries_counter = 1
        while True:
            try:
                self.connection = Connection(host, user, password)
                self.channel = self.connection.channel()
                self.channel.queue.declare(self.queue_name, durable=durable)
                break
            except Exception as e:
                if retries_counter > retries_limit:
                    raise
                error_msg = f'{retries_counter}/{retries_limit} {str(e)}'
                log_error(error_msg)
                retries_counter += 1
                time.sleep(0.5)

    def delete_queue(self, queue):
        self.channel.queue.delete(queue=queue)

    def publish(self, msg, queue_name=None):
        if not queue_name:
            self.channel.basic.publish(exchange='', routing_key=self.queue_name, body=json.dumps(msg))
        else:
            self.channel.queue.declare(queue_name, durable=True)
            self.channel.basic.publish(exchange='', routing_key=queue_name, body=json.dumps(msg))

    def start_consumer(self, callback_func, keepalive=True, timeout=None):
        def callback_prepare(msg):
            my_delivery_tag = msg.delivery_tag
            msg = busmsg2(body=msg)

            if msg.type == 'keepalive':
                if keepalive:
                    hearbeat_response = msg_compose(self.queue_name, 'keepalive', msg.content)
                    self.channel.basic.publish(exchange='', routing_key=msg.src, body=json.dumps(hearbeat_response))
                else:
                    status = callback_func(msg)
                    self.channel.basic.ack(delivery_tag=my_delivery_tag)
                    if status == -1:
                        self.stop_consuming = True
                    return
            elif callback_func(msg) == -1:
                return
            self.channel.basic.ack(delivery_tag=my_delivery_tag)

        if not callback_func:
            return -1

        self.channel.basic.qos(prefetch_count=1)
        self.channel.basic.consume(callback_prepare, self.queue_name, no_ack=False)

        start_time = time.time()
        try:
            while not self.channel.is_closed:
                if timeout:
                    elapsed_time = time.time() - start_time
                    if elapsed_time > timeout:
                        break
                if self.stop_consuming:
                    break
                self.channel.process_data_events(to_tuple=False, auto_decode=True)
                if self.channel.consumer_tags:
                    time.sleep(IDLE_WAIT)
                    continue
                break
        except KeyboardInterrupt:
            sys.exit()
        except (AMQPConnectionError, AMQPChannelError, AMQPMessageError, AMQPInvalidArgument, Exception):
            raise

    def stop_consumer(self):
        self.channel.stop_consuming()


def start_consumer(callback_func, qname, durable=False, keepalive=True, timeout=None):
    msg_queue = MessageQueue(queue_name=qname, durable=durable)
    msg_queue.start_consumer(callback_func, keepalive=keepalive, timeout=timeout)


def publish(queue_name, msg):
    msg_queue = MessageQueue(queue_name=queue_name)
    msg_queue.publish(msg)


def wait_queues_get_ready(source_queue, queues, timeout):
    msg_queue = MessageQueue(queue_name=source_queue)

    hashkey = str(uuid.uuid4()).split('-')[0]
    message = {"src": source_queue, "type": "keepalive", "content": hashkey}
    for queue in queues:
        msg_queue.publish(message, queue_name=queue)

    def keepalive_response(msg):
        if msg.src in queues:
            if msg.content == hashkey:
                queues.remove(msg.src)

        if not queues:
            return -1  # stop consumer

    msg_queue.start_consumer(keepalive_response, keepalive=False, timeout=timeout)
    msg_queue.delete_queue(source_queue)
    return queues


def wait_queue_or_exit(queues, timeout, exit_code=1):
    if not queues:
        return

    queue_hash = str(uuid.uuid4()).split('-')[0]
    source_queue = f'queue-{queue_hash}-keepalive'
    waiting_list = wait_queues_get_ready(source_queue, queues, timeout)

    if waiting_list:
        frame = inspect.stack()[1]
        filename = os.path.basename(frame.filename)
        log_error(f'{filename} keep alive timeout for: {waiting_list}')
        exit(exit_code)
