import asyncio
import time
import json

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode

import redis.asyncio as aioredis

BOT_TOKEN = "8146060375:AAHxTGpUTCPUebui4GHpOeSrQoG5pMt2HeU"
REDIS_HOST = "redis"  # Docker service name

# Name of the sorted set in Redis where we store tasks
REDIS_TASKS_KEY = "scheduled_tasks"

# Delay for /reminde (in seconds): 1 hour = 3600 seconds
REMINDER_DELAY = 3600

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


async def get_redis_connection():
    """
    Creates a connection to Redis.
    By default, host is 'redis' (the service name in docker-compose).
    """
    return aioredis.from_url(f"redis://{REDIS_HOST}", encoding="utf-8", decode_responses=True)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    """
    /start command: sends a greeting.
    """
    await message.answer("Hello! I'm your bot. Use /reminde to schedule a reminder.")


@dp.message(Command("reminde"))
async def cmd_reminde(message: Message):
    """
    /reminde command: schedules a reminder in 1 hour.
    """
    # Prepare the data we will store in Redis
    user_id = message.from_user.id
    task_data = {
        "user_id": user_id,
        "text": "hello, im your bot"
    }

    # Calculate the timestamp when we want to send the reminder
    send_time = time.time() + REMINDER_DELAY

    # Save the task in a Redis sorted set
    redis_conn = await get_redis_connection()
    await redis_conn.zadd(REDIS_TASKS_KEY, {json.dumps(task_data): send_time})

    await message.answer("Your reminder is set for 1 hour from now.")


@dp.message(Command("list"))
async def cmd_list(message: Message):
    """
    /list command: shows scheduled tasks for the user.
    """
    user_id = message.from_user.id
    current_time = time.time()

    redis_conn = await get_redis_connection()

    # Get all tasks (with their scheduled times)
    all_tasks = await redis_conn.zrange(REDIS_TASKS_KEY, 0, -1, withscores=True)

    # Filter tasks for this user and those that haven't triggered yet
    user_tasks = []
    for task_json, timestamp in all_tasks:
        task = json.loads(task_json)
        if task.get("user_id") == user_id and timestamp > current_time:
            # Convert timestamp to a rough "minutes from now" or local time
            time_diff = int((timestamp - current_time) // 60)
            user_tasks.append((task["text"], time_diff))

    if not user_tasks:
        await message.answer("No scheduled tasks.")
        return

    msg_lines = ["Your scheduled tasks:"]
    for text, minutes_left in user_tasks:
        msg_lines.append(f"- {text} (in ~{minutes_left} min)")

    await message.answer("\n".join(msg_lines))


async def check_scheduled_tasks():
    """
    Background task: checks Redis for due tasks.
    If a task is due, remove it from Redis and send the reminder.
    """
    redis_conn = await get_redis_connection()

    while True:
        now = time.time()
        # Get tasks that are due: score <= now
        due_tasks = await redis_conn.zrangebyscore(REDIS_TASKS_KEY, 0, now, withscores=True)

        if due_tasks:
            for task_json, _ in due_tasks:
                # Remove the task from the sorted set
                await redis_conn.zrem(REDIS_TASKS_KEY, task_json)
                # Parse the task and send the message
                task = json.loads(task_json)
                user_id = task["user_id"]
                text = task["text"]

                try:
                    await bot.send_message(chat_id=user_id, text=text)
                except Exception as e:
                    print(f"Failed to send message to {user_id}: {e}")

        # Sleep a bit before checking again
        await asyncio.sleep(10)


async def main():
    # Start the background task
    asyncio.create_task(check_scheduled_tasks())
    # Run dispatcher
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())