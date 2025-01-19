import asyncio
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore

BOT_TOKEN = "8146060375:AAHxTGpUTCPUebui4GHpOeSrQoG5pMt2HeU"
REDIS_HOST = "redis"  # по умолчанию 'redis', чтобы в docker-compose не менять
REDIS_PORT = 6379  # Если нужно менять порт

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализируем планировщик с RedisJobStore
# APScheduler будет сериализовать задачи в Redis.
scheduler = AsyncIOScheduler(
    jobstores={
        "default": RedisJobStore(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=0
            # при необходимости можно указать пароль, сериализатор и т.п.
        )
    }
)


async def send_reminder(user_id: int):
    """
    Функция, которую вызовет APScheduler в нужное время, чтобы отправить сообщение пользователю.
    """
    try:
        await bot.send_message(chat_id=user_id, text="hello, im your bot")
    except Exception as e:
        print(f"Failed to send reminder to user {user_id}: {e}")


@dp.message(Command("start"))
async def cmd_start(message: Message):
    """
    /start — приветствие.
    """
    await message.answer("Hello! I'm your bot. Use /reminde to schedule a reminder in 1 hour.")


@dp.message(Command("reminde"))
async def cmd_reminde(message: Message):
    """
    /reminde — планирует задачу на отправку через 1 час.
    """
    user_id = message.from_user.id
    # Время, когда нужно отправить сообщение
    run_time = datetime.now() + timedelta(hours=1)

    # Планируем задачу через APScheduler в Redis
    job = scheduler.add_job(
        send_reminder,
        "date",                 # одноразовый запуск
        run_date=run_time,      # конкретное время запуска
        args=(user_id,)         # передаем user_id в send_reminder
    )

    # job.id — это уникальный идентификатор задачи,
    # APScheduler самостоятельно генерирует, можно использовать для отмены/обновления.
    answer_text = (
        f"Your reminder is set for approximately {run_time}.\n\n"
        f"Job ID: {job.id}"
    )
    await message.answer(answer_text)


@dp.message(Command("list"))
async def cmd_list(message: Message):
    """
    /list — выводит список задач, запланированных для пользователя.
    """
    user_id = message.from_user.id
    jobs = scheduler.get_jobs()  # подтянет задачи из Redis

    # Отфильтруем только те, где в аргументах первый параметр == user_id
    user_jobs = [job for job in jobs if job.args and job.args[0] == user_id]

    if not user_jobs:
        await message.answer("No scheduled tasks.")
        return

    msg_lines = ["Your scheduled tasks:"]
    for job in user_jobs:
        if job.next_run_time:
            # next_run_time - это дата/время (datetime), когда задача будет выполнена
            run_dt = job.next_run_time
            msg_lines.append(f"- Job ID: {job.id}, run at: {run_dt}")
        else:
            msg_lines.append(f"- Job ID: {job.id}, no run_time (???).")

    await message.answer("\n".join(msg_lines))


async def main():
    # Запускаем планировщик (после инициализации jobstores)
    scheduler.start()

    # Запускаем long-polling бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())