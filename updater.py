import subprocess
import tempfile
import requests
import shutil
import time
import sys
import os

from aiogram.types import FSInputFile

from assets.antispam import admin_only
from assets import keyboards as kb
from utils.settings import get_setting, update_setting
from filters.custom import TextIn, StartsWith
from aiogram import types, Dispatcher
import config as cfg
from bot import bot, dp
import asyncio

if_notification = False
GITHUB_REPO_URL = "https://github.com/GohHacked/Bfg-copy-New.git"
GITHUB_BRANCH = "main"  # Изменено с V3 на main (стандартная ветка)

async def check_updates() -> None:
    """Проверка и отправка уведомлений об успешном обновлении/перезагрузке"""
    update = get_setting(key="update_flag", default={})
    restart = get_setting(key="restart_flag", default={})

    if update and all(key in update for key in ["time", "chat_id", "message_id"]):
        ctime = time.time() - update["time"]
        txt = (f"<b>✅ Обновление успешно установлено!</b>\n"
               f"<i>Время установки: {ctime:.1f} секунд</i>\n\n"
               f"<tg-spoiler>Официальный канал разработки бота - @copybfg</tg-spoiler>")
        try:
            await bot.edit_message_text(chat_id=update["chat_id"], 
                                        message_id=update["message_id"], 
                                        text=txt)
        except Exception as e:
            print(f"Ошибка при отправке уведомления об обновлении: {e}")

    if restart and all(key in restart for key in ["time", "chat_id", "message_id"]):
        ctime = time.time() - restart["time"]
        txt = (f"<b>🔄 Бот перезагружен!</b>\n\n"
               f"<i>Время перезагрузки: {ctime:.1f} секунд</i>")
        try:
            await bot.edit_message_text(chat_id=restart["chat_id"], 
                                        message_id=restart["message_id"], 
                                        text=txt)
        except Exception as e:
            print(f"Ошибка при отправке уведомления о перезагрузке: {e}")

    # Очищаем флаги после отправки уведомлений
    update_setting(key="update_flag", value={})
    update_setting(key="restart_flag", value={})


async def search_update(force: bool = False, check: bool = False) -> bool:
    """Поиск доступных обновлений"""
    global if_notification
    
    # Пропускаем проверку, если уже было уведомление и это не принудительная проверка
    if not check and if_notification and not force:
        return False
    
    try:
        # Получаем информацию о версии из удаленного репозитория
        version_url = f"{GITHUB_REPO_URL.replace('.git', '')}/raw/{GITHUB_BRANCH}/bot.py"
        response = requests.get(version_url, timeout=10)
        response.raise_for_status()
        
        # Извлекаем версию из первой строки
        remote_first_line = response.text.splitlines()[0].strip()
        if ": " in remote_first_line:
            last_version = remote_first_line.split(": ")[1]
        else:
            last_version = remote_first_line
            
        # Получаем локальную версию
        if not os.path.exists("bot.py"):
            print("Файл bot.py не найден")
            return False
            
        with open("bot.py", "r", encoding="utf-8") as file:
            local_first_line = file.readline().strip()
            if ": " in local_first_line:
                version = local_first_line.split(": ")[1]
            else:
                version = local_first_line
        
        # Нормализация версий для сравнения
        def normalize_version(ver):
            return float(ver.replace(",", ".").replace(" ", "").split(".")[0])
        
        last_version_int = normalize_version(last_version)
        version_int = normalize_version(version)
        
        # Если версия не новее
        if last_version_int <= version_int:
            if_notification = False
            return False
        
        # Если только проверка - возвращаем результат
        if check:
            return True
        
        # Получаем список изменений
        changelog_url = f"{GITHUB_REPO_URL.replace('.git', '')}/raw/{GITHUB_BRANCH}/update_list.txt"
        changelog_response = requests.get(changelog_url, timeout=10)
        changelog_text = changelog_response.text if changelog_response.status_code == 200 else "Информация об изменениях недоступна"
        
        # Формируем сообщение
        txt = (f"<b>🔄 Доступно обновление!</b>\n"
               f"<b>Текущая версия:</b> {version}\n"
               f"<b>Новая версия:</b> {last_version}\n\n"
               f"<b>Что нового?</b>\n<i>{changelog_text}</i>")
        
        # Отправляем уведомление всем администраторам
        for admin in cfg.admin:
            try:
                await bot.send_message(admin, txt, reply_markup=kb.update_bot())
            except Exception as e:
                print(f"Не удалось отправить уведомление админу {admin}: {e}")
        
        if_notification = True
        return True
                
    except requests.RequestException as e:
        print(f"Ошибка сети при проверке обновлений: {e}")
        return False
    except Exception as e:
        print(f"Ошибка при проверке обновлений: {e}")
        return False


@admin_only(private=True)
async def update_bot(message: types.Message):
    """Обработчик команды обновления"""
    force = False
    check = await search_update(check=True)
    
    # Формируем текст ответа в зависимости от ситуации
    if not check and "-f" not in message.text:
        await message.answer(
            "<b>✅ У вас установлена последняя версия бота!</b>\n"
            "Вы также можете попробовать "
            "<a href='https://github.com/GohHacked/Bfg-copy-New'>обновиться вручную</a>"
        )
        return
    
    if not check:
        txt = ("⚠️ У вас уже установлена последняя версия бота.\n"
               "<i>Нажмите на кнопку ниже, если вы хотите</i> "
               "<a href='https://github.com/GohHacked/Bfg-copy-New'>обновить файлы бота</a>")
        force = True
    else:
        try:
            changelog_url = f"{GITHUB_REPO_URL.replace('.git', '')}/raw/{GITHUB_BRANCH}/update_list.txt"
            response = requests.get(changelog_url, timeout=10)
            changelog_text = response.text if response.status_code == 200 else "Информация об изменениях недоступна"
            txt = (f"<b>🔄 Доступно обновление!</b>\n"
                   f"Что нового?\n\n<i>{changelog_text}</i>")
        except:
            txt = "<b>🔄 Доступно обновление!</b>\n\n<i>Информация об изменениях временно недоступна</i>"

    await message.answer(txt, reply_markup=kb.update_bot(force=force))


async def bot_update(call: types.CallbackQuery) -> None:
    """Обработчик callback для установки обновлений"""
    global if_notification
    
    if call.from_user.id not in cfg.admin:
        await bot.answer_callback_query(call.id, text="❌ Доступ запрещен", show_alert=True)
        return
    
    check = await search_update(check=True)
    force = int(call.data.split("_")[1])
    if_notification = False
    
    if not check and force == 0:
        await bot.answer_callback_query(call.id, 
                                       show_alert=True, 
                                       text="✅ У вас уже установлена последняя версия.")
        return
    
    try:
        # Создаем резервную копию базы данных
        if os.path.exists("users.db"):
            file = FSInputFile("users.db")
            await bot.send_document(call.message.chat.id, file, 
                                  caption="💾 Создана резервная копия базы данных")
        else:
            await call.message.answer("⚠️ Файл базы данных не найден, резервная копия не создана")
        
        await call.message.edit_text("<i>⏳ Установка обновления...</i>")
        
        # Клонируем репозиторий во временную директорию
        with tempfile.TemporaryDirectory() as temp_dir:
            clone_cmd = ["git", "clone", "--branch", GITHUB_BRANCH, 
                        "--depth", "1", GITHUB_REPO_URL, temp_dir]
            
            result = subprocess.run(clone_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"Ошибка клонирования: {result.stderr}")
            
            # Копируем файлы
            for item in os.listdir(temp_dir):
                if item in ["config_ex.py", "modules", ".git", ".github"]:
                    continue
                
                src_path = os.path.join(temp_dir, item)
                dest_path = os.path.join(os.getcwd(), item)
                
                try:
                    if os.path.isdir(src_path):
                        if os.path.exists(dest_path):
                            shutil.rmtree(dest_path, ignore_errors=True)
                        shutil.copytree(src_path, dest_path)
                    else:
                        shutil.copy2(src_path, dest_path)
                except Exception as e:
                    print(f"Ошибка при копировании {item}: {e}")
        
        # Сохраняем информацию для уведомления
        update_setting(key="update_flag", 
                      value={"time": time.time(), 
                             "chat_id": call.message.chat.id, 
                             "message_id": call.message.message_id})
        
        # Перезапуск бота
        os.execv(sys.executable, [sys.executable] + sys.argv)
        
    except subprocess.CalledProcessError as e:
        await call.message.edit_text(f"❌ Ошибка при установке обновления:\n<code>{e}</code>")
    except Exception as e:
        await call.message.edit_text(f"❌ Произошла ошибка:\n<code>{e}</code>")


@admin_only()
async def restart_bot(message: types.Message):
    """Перезагрузка бота"""
    msg = await message.answer("<i>🔄 Перезагрузка бота...</i>")
    
    # Сохраняем информацию для уведомления
    update_setting(key="restart_flag", 
                  value={"time": time.time(), 
                         "chat_id": msg.chat.id, 
                         "message_id": msg.message_id})
    
    await asyncio.sleep(1)
    
    try:
        await bot.close()
        await dp.storage.close()
    except Exception as e:
        await message.answer(f"⚠️ Не удалось корректно закрыть соединения: <code>{e}</code>")
    
    # Перезапуск
    os.execl(sys.executable, sys.executable, *sys.argv)


def reg(dp: Dispatcher):
    """Регистрация обработчиков"""
    dp.message.register(restart_bot, TextIn("🔄 Перезагрузка", "/restartb"))
    dp.message.register(update_bot, TextIn("/updateb", "/updateb -f"))
    dp.callback_query.register(bot_update, StartsWith("update-bot"))