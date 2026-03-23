import asyncio
import os
import aiosqlite
import json
import sqlite3
import uuid
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest

# --- KONFIGURASI ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    OWNER_ID = int(os.getenv("ADMIN_ID")) 
except (TypeError, ValueError):
    OWNER_ID = 0 

DB_NAME = "media.db"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# --- STATES ---
class AdminStates(StatesGroup):
    waiting_for_fsub = State()
    waiting_for_fsub_text = State()
    waiting_for_post_ch = State()
    waiting_for_cover = State()
    waiting_for_qris = State()
    waiting_for_preview = State()
    waiting_for_vip_grup = State()
    waiting_for_log_grup = State()
    waiting_for_reff_ch = State()
    waiting_for_bc = State()
    waiting_for_add_admin = State()
    waiting_for_del_admin = State()
    # Logika Post Admin
    waiting_for_title = State()
    waiting_for_more_media = State()
    waiting_for_manual_cover = State()
    # Member Side
    waiting_for_ask = State()
    waiting_for_donation_media = State()
    waiting_for_vip_ss = State()

class PostData:
    def __init__(self):
        self.media_list = []
        self.title = ""
        self.manual_cover = None

post_temp = {}

# ================= DATABASE HELPER ===============
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, ref_count INTEGER DEFAULT 0, referrer INTEGER)")
        await db.execute("CREATE TABLE IF NOT EXISTS admins (admin_id INTEGER PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS media_store (msg_unique_id TEXT PRIMARY KEY, media_data TEXT, title TEXT)")
        defaults = [('auto_cover', 'off'), ('fsub_text', 'Join dulu ya'), ('fsub_list', ''), ('post_channels', '')]
        for k, v in defaults:
            await db.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (k, v))
        await db.commit()

async def get_config(key, default=""):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM config WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

async def set_config(key, value):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, str(value)))
        await db.commit()

async def is_admin(user_id):
    if user_id == OWNER_ID: return True
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM admins WHERE admin_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

# ================= ADMIN CMD ===============
@dp.message(Command("ray"))
async def cmd_ray(m: Message):
    if not await is_admin(m.from_user.id): return
    teks = "<b>🏠 MENU ADMIN</b>\n/setpostch /setfsub /setcove /autocover /setadmin /setqris /setvipgrup"
    await m.reply(teks)

# --- ALUR POSTING ADMIN ---
@dp.message(F.photo | F.video, StateFilter(None))
async def start_post_flow(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    uid = m.from_user.id
    post_temp[uid] = PostData()
    fid = m.photo[-1].file_id if m.photo else m.video.file_id
    m_type = "photo" if m.photo else "video"
    post_temp[uid].media_list.append({"file_id": fid, "type": m_type})
    await m.reply("Silakan masukkan **Judul**:")
    await state.set_state(AdminStates.waiting_for_title)

@dp.message(AdminStates.waiting_for_title)
async def process_title(m: Message, state: FSMContext):
    uid = m.from_user.id
    post_temp[uid].title = m.text
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ TAMBAH PART", callback_data="add_more_part")],
        [InlineKeyboardButton(text="🚀 POST SEKARANG", callback_data="post_final")]
    ])
    await m.reply(f"Judul: {m.text}\nMedia: {len(post_temp[uid].media_list)}", reply_markup=kb)

@dp.callback_query(F.data == "add_more_part")
async def add_more_part_btn(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Kirim media selanjutnya:")
    await state.set_state(AdminStates.waiting_for_more_media)

@dp.message(AdminStates.waiting_for_more_media, F.photo | F.video)
async def process_more_media(m: Message, state: FSMContext):
    uid = m.from_user.id
    fid = m.photo[-1].file_id if m.photo else m.video.file_id
    post_temp[uid].media_list.append({"file_id": fid, "type": "photo" if m.photo else "video"})
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ TAMBAH PART", callback_data="add_more_part")],
        [InlineKeyboardButton(text="🚀 POST SEKARANG", callback_data="post_final")]
    ])
    await m.reply(f"Berhasil! Total: {len(post_temp[uid].media_list)}", reply_markup=kb)

@dp.callback_query(F.data == "post_final")
async def post_final_check(c: CallbackQuery, state: FSMContext):
    acover = await get_config("auto_cover", "off")
    if acover == "off":
        await c.message.answer("Kirim **GAMBAR COVER** manual:")
        await state.set_state(AdminStates.waiting_for_manual_cover)
    else:
        await show_channel_options(c.message, c.from_user.id)

@dp.message(AdminStates.waiting_for_manual_cover, F.photo)
async def process_manual_cover(m: Message, state: FSMContext):
    post_temp[m.from_user.id].manual_cover = m.photo[-1].file_id
    await show_channel_options(m, m.from_user.id)

async def show_channel_options(m, uid):
    ch_raw = await get_config("post_channels", "")
    if not ch_raw: return await m.reply("Set channel dulu!")
    channels = ch_raw.split()
    kb = [[InlineKeyboardButton(text=f"📤 {ch}", callback_data=f"send_to:{ch}")] for ch in channels]
    kb.append([InlineKeyboardButton(text="🌍 SEMUA", callback_data="send_to:ALL")])
    await m.answer("Pilih Tujuan:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# --- EXECUTE POST (ADMIN & DONASI) ---
@dp.callback_query(F.data.startswith("send_to"))
async def execute_post(c: CallbackQuery, state: FSMContext):
    uid = c.from_user.id
    target = c.data.split(":")[1]
    sdata = await state.get_data()
    
    # LOGIKA DONASI
    if "donasi_prefix" in sdata:
        prefix = sdata["donasi_prefix"]
        target_user = sdata["current_donasi_user"]
        msg_ref = c.message.reply_to_message
        if not msg_ref: return await c.answer("Media tidak ditemukan!", show_alert=True)
        
        fid = msg_ref.photo[-1].file_id if msg_ref.photo else (msg_ref.video.file_id if msg_ref.video else msg_ref.voice.file_id)
        m_type = "photo" if msg_ref.photo else ("video" if msg_ref.video else "voice")
        caption = f"{prefix} donasi member"

        ch_list = (await get_config("post_channels")).split() if target == "ALL" else [target]
        for ch in ch_list:
            try:
                if m_type == "photo": await bot.send_photo(ch, photo=fid, caption=caption)
                elif m_type == "video": await bot.send_video(ch, video=fid, caption=caption)
                elif m_type == "voice": await bot.send_voice(ch, voice=fid, caption=caption)
            except: pass
        
        await bot.send_message(target_user, "✅ Donasi kamu sudah tayang!")
        await c.message.edit_text("✅ Donasi Berhasil di-post!")
        await state.clear()
        return

    # LOGIKA ADMIN BIASA
    data = post_temp.get(uid)
    if not data: return await c.answer("Data hilang!", show_alert=True)
    
    post_id = str(uuid.uuid4())[:8]
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO media_store VALUES (?, ?, ?)", (post_id, json.dumps(data.media_list), data.title))
        await db.commit()

    cover = data.manual_cover or await get_config("default_cover")
    kb_nonton = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎬 NONTON", url=f"https://t.me/{(await bot.get_me()).username}?start={post_id}")]])
    
    ch_list = (await get_config("post_channels")).split() if target == "ALL" else [target]
    for ch in ch_list:
        try: await bot.send_photo(ch, photo=cover, caption=f"<b>{data.title}</b>", reply_markup=kb_nonton)
        except: pass

    await c.message.edit_text("✅ Berhasil dipost!")
    post_temp.pop(uid, None)
    await state.clear()

# --- HANDLER DONASI ---
@dp.callback_query(F.data == "member_donasi")
async def donasi_start(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 COWO", callback_data="donasi:co"), InlineKeyboardButton(text="👩 CEWE", callback_data="donasi:ce")]
    ])
    await c.message.edit_text("Pilih kategori donasi:", reply_markup=kb)

@dp.callback_query(F.data.startswith("donasi:"))
async def donasi_type(c: CallbackQuery, state: FSMContext):
    await state.update_data(donasi_prefix=c.data.split(":")[1])
    await c.message.answer("Kirim Media (Foto/Video/Voice):")
    await state.set_state(AdminStates.waiting_for_donation_media)

@dp.message(AdminStates.waiting_for_donation_media)
async def process_donasi_media(m: Message, state: FSMContext):
    if not (m.photo or m.video or m.voice): return await m.reply("Kirim media!")
    sdata = await state.get_data()
    prefix = sdata["donasi_prefix"]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ APPROVE", callback_data=f"app_donasi:{m.from_user.id}:{prefix}"),
         InlineKeyboardButton(text="❌ TOLAK", callback_data=f"rej_donasi:{m.from_user.id}")]
    ])
    try:
        await bot.send_message(OWNER_ID, f"🎁 **DONASI BARU** ({prefix}) dari {m.from_user.id}:")
        await m.forward(OWNER_ID)
        await bot.send_message(OWNER_ID, "Tindakan:", reply_markup=kb)
        await m.reply("✅ Donasi terkirim ke admin!")
    except:
        await m.reply("❌ Gagal lapor admin.")
    await state.set_state(None)

@dp.callback_query(F.data.startswith("app_donasi:"))
async def approve_donasi(c: CallbackQuery, state: FSMContext):
    parts = c.data.split(":")
    await state.update_data(current_donasi_user=int(parts[1]), donasi_prefix=parts[2])
    await show_channel_options(c.message, c.from_user.id)

@dp.callback_query(F.data.startswith("rej_donasi:"))
async def reject_donasi(c: CallbackQuery):
    target = int(c.data.split(":")[1])
    try: await bot.send_message(target, "❌ Donasi ditolak.")
    except: pass
    await c.message.edit_text("❌ Donasi Ditolak.")

# --- START & LAINNYA ---
@dp.message(CommandStart())
async def start(m: Message):
    # Logika database user & args (seperti kode kamu sebelumnya)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 DONASI", callback_data="member_donasi"), InlineKeyboardButton(text="💎 VIP", callback_data="member_vip")]
    ])
    await m.reply(f"Halo {m.from_user.first_name}!", reply_markup=kb)

async def main():
    await init_db()
    print("Bot is Running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
