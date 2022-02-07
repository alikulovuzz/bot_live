import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.bot.api import TelegramAPIServer
from aiogram.dispatcher.webhook import configure_app

from configreader import load_config, Config
from commandsworker import set_bot_commands
from unsupported_reply import register_admin_reply_handler
from admin_no_reply import register_admin_no_reply_handlers
from usermode import register_usermode_handlers
from adminmode import register_adminmode_handlers
from bans import register_bans_handlers
from common import register_common_handlers
from updatesworker import get_handled_updates_list


async def main():
    # Настройка логирования в stdout
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    # Объявление и инициализация объектов бота и диспетчера,
    # а также извлечение переменных окружения с приведением к нужным типам
    config: Config = load_config()
    if not config.bot.token:
        raise ValueError("Не указан токен. Бот не может быть запущен.")

    if not config.bot.admin_chat_id:
        raise ValueError("Не указан идентификатор чата для пересылки сообщений. Бот не может быть запущен.")
    if not isinstance(config.bot.admin_chat_id, int):
        raise ValueError(f'Идентификатор "{config.bot.admin_chat_id}" не является числом. Бот не может быть запущен.')

    bot = Bot(token=config.bot.token)

    if config.app.use_local_server is True:
        bot.server = TelegramAPIServer.from_base(config.app.local_server_host)

    bot["admin_chat_id"] = config.bot.admin_chat_id  # Добавление айдишника к объекту bot
    # Добавление флага "удалять или нет подтверждения отправки"
    bot["remove_sent_confirmation"] = config.bot.remove_sent_confirmation
    dp = Dispatcher(bot)

    # Регистрация хэндлеров
    register_admin_reply_handler(dp, config.bot.admin_chat_id)
    register_bans_handlers(dp, config.bot.admin_chat_id)
    register_adminmode_handlers(dp, config.bot.admin_chat_id)
    register_admin_no_reply_handlers(dp, config.bot.admin_chat_id)
    register_common_handlers(dp)
    register_usermode_handlers(dp)

    # Регистрация /-команд в интерфейсе
    await set_bot_commands(bot, config.bot.admin_chat_id)

    me = await bot.get_me()
    logging.info(f"Starting @{me.username}")

    # Запуск поллинга или вебхуков
    if False:
        app = web.Application()
        configure_app(dp, app, config.app.webhook_path)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()

        # При использовании локального Bot API сервера, формируем URL немного по-другому,
        # т.к. в этом случае можно использовать любые порты
        if config.app.use_local_server is False:
            webhook_url = f"https://{config.app.webhook_domain}{config.app.webhook_path}"
        else:
            webhook_url = f"http://{config.app.webhook_domain}:{config.app.port}{config.app.webhook_path}"
        await bot.set_webhook(webhook_url)

        site = web.TCPSite(runner, config.app.host, config.app.port)
        print("Starting webhook")
        try:
            await site.start()
            while True:
                await asyncio.sleep(3600)  # Нужно для поддержания сервера
        finally:
            await dp.storage.close()
            await dp.storage.wait_closed()
            await bot.session.close()
            await runner.cleanup()
    else:
        try:
            print("Starting polling")
            await dp.reset_webhook()
            # await dp.skip_updates()  # пропуск накопившихся апдейтов (необязательно)
            await dp.start_polling(allowed_updates=get_handled_updates_list(dp))
        finally:
            await dp.storage.close()
            await dp.storage.wait_closed()
            await bot.session.close()


asyncio.run(main())
