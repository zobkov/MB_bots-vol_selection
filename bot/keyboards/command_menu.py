from aiogram import Bot
from aiogram.types import BotCommand

LEXICON_COMMANDS_RU: dict[str, str] = {
    '/start': 'Запуск бота / Главный экран',
    '/menu': 'Личный кабинет',
    '/apply': 'Заполнить анкету волонтера'
}

async def set_main_menu(bot: Bot):
    main_menu_commands = [
        BotCommand(
            command=command,
            description=description
        ) for command, description in LEXICON_COMMANDS_RU.items()
    ]
    await bot.set_my_commands(main_menu_commands)
