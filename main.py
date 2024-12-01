import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.escape
import redis.asyncio as redis
import json
from uuid import uuid4
from dotenv import load_dotenv
import os

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
CHANNEL_NAME = os.getenv("CHANNEL_NAME", "chat")
WEBSOCKET_PORT = int(os.getenv("WEBSOCKET_PORT", 8888))

redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

clients = {}
processed_message_ids = set()

class ChatWebSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self, room=None):
        self.room = room or str(uuid4())
        self.id = str(uuid4())
        if self.room not in clients:
            clients[self.room] = set()
        clients[self.room].add(self)
        self.write_message(json.dumps({"type": "info", "message": f"Connected to the chat room: {self.room}!"}))
        self.update_clients()
        tornado.ioloop.IOLoop.current().add_callback(self.subscribe_to_redis)

    async def subscribe_to_redis(self):
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"{CHANNEL_NAME}:{self.room}")
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                print(f"Redis message for room {f'{CHANNEL_NAME}:{self.room}'}: {data}")
                await self.broadcast_message(data)

    async def broadcast_message(self, data):
        message_id = data.get("id")
        if message_id in processed_message_ids:
            print(f"Duplicate message ignored: {message_id}")
            return
        processed_message_ids.add(message_id)
        if self.room in clients:
            for client in clients[self.room]:
                await client.write_message(json.dumps({"type": "message", "id": data["id"], "message": data["message"]}))

    def on_message(self, message):
        data = tornado.escape.json_decode(message)
        if data.get("type") == "message":
            print("on_message", data, self.room)
            tornado.ioloop.IOLoop.current().add_callback(
                lambda: redis_client.publish(f"{CHANNEL_NAME}:{self.room}", json.dumps({
                    "id": self.id,
                    "message": data.get("message"),
                }))
            )

    def on_close(self):
        if self.room in clients:
            clients[self.room].remove(self)
            if not clients[self.room]:
                del clients[self.room]
        self.update_clients()

    def check_origin(self, origin):
        return True

    @staticmethod
    def update_clients():
        online_users = {room: [client.id for client in clients.get(room, [])] for room in clients}
        for room, room_clients in clients.items():
            for client in room_clients:
                client.write_message(json.dumps({"type": "users", "room": room, "users": online_users[room]}))

async def redis_listener():
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"{CHANNEL_NAME}:*")
    async for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            room = message["channel"].decode().split(":")[1]
            print(f"Redis message for room {room}: {data}")
            await broadcast_message(room, data)

async def broadcast_message(room, data):
    message_id = data.get("id")
    if message_id in processed_message_ids:
        print(f"Duplicate message ignored: {message_id}")
        return
    processed_message_ids.add(message_id)
    if room in clients:
        for client in clients[room]:
            await client.write_message(json.dumps({"type": "message", "id": data["id"], "message": data["message"]}))

def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/ws/([a-zA-Z0-9_-]+)", ChatWebSocketHandler),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": "./static"}),
    ])

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("static/index.html")

if __name__ == "__main__":
    app = make_app()
    tornado.ioloop.IOLoop.current().add_callback(redis_listener)
    app.listen(WEBSOCKET_PORT)
    print(f"WebSocket server started on port {WEBSOCKET_PORT}")
    tornado.ioloop.IOLoop.current().start()
