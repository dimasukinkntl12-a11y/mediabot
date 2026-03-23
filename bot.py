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
    waiting_for_log_ch = State()
    waiting_for_title = State()
    waiting_for_more_media = State()
    waiting_for_manual_cover = State()
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

async def check_fsub(user_id):
    fsub_raw = await get_config("fsub_list", "")
    if not fsub_raw:
        return True, None
    
    channels = fsub_raw.split()
    not_joined = []
    
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(ch)
        except Exception:
            not_joined.append(ch)
            
    if not not_joined:
        return True, None
    
    # Ambil teks fsub dari config
    teks = await get_config("fsub_text", "Silakan join channel di bawah untuk melanjutkan")
    
    kb = []
    for ch in not_joined:
        try:
            chat = await bot.get_chat(ch)
            kb.append([InlineKeyboardButton(text=f"Join {chat.title}", url=f"https://t.me/{chat.username or chat.id}")])
        except: continue
    
    kb.append([InlineKeyboardButton(text="🔄 Coba Lagi", callback_data="check_again")])
    return False, InlineKeyboardMarkup(inline_keyboard=kb)
# ================= ADMIN CMD ===============
@dp.message(Command("ray"))
async def cmd_ray(m: Message):
    if not await is_admin(m.from_user.id): return
    teks = "<b>🏠 MENU ADMIN</b>\n/setpostch /setfsub /setcove /autocover /setadmin /setqris /setvipgrup"
    await m.reply(teks)

@dp.message(Command("setfsub"))
async def set_fsub_cmd(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirimkan Username/ID Channel (pisahkan dengan spasi jika lebih dari satu):")
    await state.set_state(AdminStates.waiting_for_fsub)

@dp.message(AdminStates.waiting_for_fsub)
async def process_fsub_list(m: Message, state: FSMContext):
    await set_config("fsub_list", m.text)
    await m.reply(f"✅ FSub berhasil di-set ke: {m.text}")
    await state.clear()

@dp.message(Command("setfsubteks"))
async def set_fsub_teks(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirimkan teks untuk FSub (bisa pakai emoji/format telegram):")
    await state.set_state(AdminStates.waiting_for_fsub_text)

@dp.message(AdminStates.waiting_for_fsub_text)
async def process_fsub_teks(m: Message, state: FSMContext):
    # Menyimpan teks persis seperti yang dikirim (termasuk entitas/emoji)
    await set_config("fsub_text", m.html_text)
    await m.reply("✅ Teks FSub berhasil diupdate!")
    await state.clear()

@dp.message(Command("setqris"))
async def set_qris(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirimkan foto QRIS:")
    await state.set_state(AdminStates.waiting_for_qris)

@dp.message(AdminStates.waiting_for_qris, F.photo)
async def process_qris(m: Message, state: FSMContext):
    await set_config("qris_file_id", m.photo[-1].file_id)
    await m.reply("✅ QRIS Berhasil disimpan!")
    await state.clear()

@dp.message(Command("autocover"))
async def toggle_autocover(m: Message):
    if not await is_admin(m.from_user.id): return
    current = await get_config("auto_cover", "off")
    new_status = "on" if current == "off" else "off"
    await set_config("auto_cover", new_status)
    await m.reply(f"✅ Auto Cover sekarang: <b>{new_status.upper()}</b>")

@dp.message(Command("setpostch"))
async def set_post_ch(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirimkan ID/Username channel tujuan post (pisahkan spasi):")
    await state.set_state(AdminStates.waiting_for_post_ch)

@dp.message(AdminStates.waiting_for_post_ch)
async def process_post_ch(m: Message, state: FSMContext):
    await set_config("post_channels", m.text)
    await m.reply(f"✅ Channel post di-set ke: {m.text}")
    await state.clear()

@dp.message(Command("setpreview"))
async def set_preview_vip(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirim foto/video preview VIP beserta caption-nya:")
    await state.set_state(AdminStates.waiting_for_preview)

@dp.message(AdminStates.waiting_for_preview)
async def process_preview(m: Message, state: FSMContext):
    fid = (m.photo[-1].file_id if m.photo else m.video.file_id) if (m.photo or m.video) else None
    await set_config("vip_preview_file", fid or "")
    await set_config("vip_preview_text", m.html_text or m.caption or "")
    await m.reply("✅ Preview VIP berhasil di-set!")
    await state.clear()

@dp.message(Command("setvipgrup"))
async def set_vip_grup(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirimkan ID Grup VIP (contoh: -100xxx):")
    await state.set_state(AdminStates.waiting_for_vip_grup)

@dp.message(AdminStates.waiting_for_vip_grup)
async def process_vip_grup(m: Message, state: FSMContext):
    await set_config("vip_group_id", m.text)
    await m.reply(f"✅ ID Grup VIP disimpan: {m.text}")
    await state.clear()

@dp.message(Command("bc"))
async def cmd_broadcast(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirim pesan yang ingin di-broadcast (Teks/Media):")
    await state.set_state(AdminStates.waiting_for_bc)

@dp.message(AdminStates.waiting_for_bc)
async def process_bc(m: Message, state: FSMContext):
    await m.reply("🚀 Memulai broadcast...")
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
    
    success = 0
    for (uid,) in users:
        try:
            await m.copy_to(uid)
            success += 1
            await asyncio.sleep(0.05) # Jeda dikit biar gak limit
        except: continue
    
    await m.reply(f"✅ Broadcast selesai!\nBerhasil ke {success} user.")
    await state.clear()

@dp.message(Command("senddb"))
async def send_db(m: Message):
    if m.from_user.id != OWNER_ID: return
    file = FSInputFile(DB_NAME, filename="media.db")
    await m.reply_document(file, caption="Backup Database Terbaru")

@dp.message(Command("update"))
async def update_db(m: Message):
    if m.from_user.id != OWNER_ID: return
    if not m.reply_to_message or not m.reply_to_message.document:
        return await m.reply("Reply ke file .db untuk update!")
    
    # Download file baru
    new_db_path = "temp_update.db"
    await bot.download(m.reply_to_message.document, destination=new_db_path)
    
    # Logika menambahkan yang belum ada
    try:
        conn_old = sqlite3.connect(DB_NAME)
        conn_new = sqlite3.connect(new_db_path)
        
        # Contoh: Menambah media yang belum ada di media_store
        cursor_new = conn_new.execute("SELECT * FROM media_store")
        for row in cursor_new:
            conn_old.execute("INSERT OR IGNORE INTO media_store VALUES (?, ?, ?)", row)
            
        conn_old.commit()
        conn_old.close()
        conn_new.close()
        os.remove(new_db_path)
        await m.reply("✅ Database berhasil di-update (Record baru ditambahkan)!")
    except Exception as e:
        await m.reply(f"❌ Gagal update: {str(e)}")

@dp.message(Command("setlogch"))
async def set_log_ch(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirimkan ID Grup Log (contoh: -100xxx):")
    await state.set_state(AdminStates.waiting_for_log_ch)

@dp.message(AdminStates.waiting_for_log_ch)
async def process_log_ch(m: Message, state: FSMContext):
    await set_config("log_channel_id", m.text)
    await m.reply(f"✅ ID Grup Log disimpan: {m.text}")
    await state.clear()

# Fungsi Helper untuk kirim log (Taruh di bawah set_config)
async def send_log(text, media=None):
    log_id = await get_config("log_channel_id")
    if not log_id: return
    try:
        if media:
            await bot.send_photo(log_id, photo=media, caption=text)
        else:
            await bot.send_message(log_id, text)
    except: pass
    
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
                await bot.send_photo(
                ch, 
                photo=cover, 
                caption=f"<b>{data.title}</b>", 
                reply_markup=kb_nonton,
                protect_content=True # <--- INI BIAR GAK BISA COPY/FORWARD
            )
            except: pass
        
        await bot.send_message(target_user, "✅ Donasi kamu sudah tayang!")
        await c.message.edit_text("✅ Donasi Berhasil di-post!")
        await state.clear()
        return
        
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

@dp.callback_query(F.data == "check_again")
async def check_again_btn(c: CallbackQuery):
    is_joined, kb_fsub = await check_fsub(c.from_user.id)
    if is_joined:
        await c.message.edit_text("✅ Terimakasih sudah join! Silahkan klik lagi link nontonnya atau ketik /start")
    else:
        await c.answer("❌ Kamu belum join semua channel!", show_alert=True)

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
    
@dp.message(CommandStart())
async def start(m: Message):
    args = m.text.split()
    user_id = m.from_user.id
    # Tambahkan User ke DB jika belum ada & Logika Referral
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cursor:
            if not await cursor.fetchone():
                referrer = 0
                if len(args) > 1 and args[1].startswith("ref_"):
                    try:
                        referrer = int(args[1].replace("ref_", ""))
                        if referrer != user_id:
                            # Update jumlah reff pengajak
                            await db.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id = ?", (referrer,))
                            await bot.send_message(referrer, "🎊 Seseorang bergabung menggunakan link kamu!")
                    except: pass
                await db.execute("INSERT INTO users (user_id, ref_count, referrer) VALUES (?, 0, ?)", (user_id, referrer))
                await db.commit()
    # 1. Cek FSub Dulu
    is_joined, kb_fsub = await check_fsub(user_id)
    if not is_joined:
        return await m.reply(await get_config("fsub_text"), reply_markup=kb_fsub)
    # 2. Logika ambil media jika ada args (start=post_id)
    if len(args) > 1:
        post_id = args[1]
        await m.answer("tunggu sebentar...") # Notif delay agar tidak dikira mati
        
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT media_data, title FROM media_store WHERE msg_unique_id = ?", (post_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    media_list = json.loads(row[0])
                    title = row[1]
                    for item in media_list:
                        if item['type'] == 'photo':
                            await m.answer_photo(item['file_id'], caption=title, protect_content=True)
                        else:
                            await m.answer_video(item['file_id'], caption=title, protect_content=True)
                    return
                else:
                    await m.reply("❌ Media tidak ditemukan atau sudah dihapus.")
                    return
                    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 ASK ADMIN", callback_data="member_ask")],
        [InlineKeyboardButton(text="🎁 DONASI", callback_data="member_donasi")],
        [InlineKeyboardButton(text="💎 ORDER VIP", callback_data="member_vip"), InlineKeyboardButton(text="👀 PREVIEW", callback_data="member_preview")],
        [InlineKeyboardButton(text="🔗 REFERRAL", callback_data="member_reff")]
    ])
    await m.reply(f"Halo {m.from_user.first_name}! Selamat datang di Bot Media.", reply_markup=kb)

@dp.callback_query(F.data == "member_ask")
async def ask_admin_start(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Silakan kirim pesan/pertanyaan kamu untuk admin:")
    await state.set_state(AdminStates.waiting_for_ask)

@dp.message(AdminStates.waiting_for_ask)
async def process_ask_admin(m: Message, state: FSMContext):
    await m.answer("tunggu sebentar...")
    try:
        await bot.send_message(OWNER_ID, f"📩 **PESAN BARU (ASK)** dari <code>{m.from_user.id}</code>:")
        await m.forward(OWNER_ID)
        await m.reply("✅ Pesan berhasil terkirim, silakan tunggu balasan.")
    except:
        await m.reply("❌ Gagal menghubungi admin.")
    await state.clear()
# --- REPLY ADMIN (Logika Membalas Pesan Ask) ---
@dp.message(F.reply_to_message & F.from_user.id == OWNER_ID)
async def reply_to_user(m: Message):
    # Logika: Jika admin reply pesan yang di-forward tadi
    if m.reply_to_message.forward_from:
        target_id = m.reply_to_message.forward_from.id
        try:
            await bot.send_message(target_id, f"<b>📩 Balasan dari Admin:</b>\n\n{m.text or m.caption}")
            await m.reply("✅ Balasan terkirim!")
        except:
            await m.reply("❌ Gagal membalas (mungkin user blokir bot).")

@dp.callback_query(F.data == "back_start")
async def back_to_start(c: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 ASK ADMIN", callback_data="member_ask")],
        [InlineKeyboardButton(text="🎁 DONASI", callback_data="member_donasi")],
        [InlineKeyboardButton(text="💎 ORDER VIP", callback_data="member_vip"), InlineKeyboardButton(text="👀 PREVIEW", callback_data="member_preview")],
        [InlineKeyboardButton(text="🔗 REFERRAL", callback_data="member_reff")]
    ])
    await c.message.edit_text(f"Halo {c.from_user.first_name}! Silahkan pilij tombol dibawah ini", reply_markup=kb)
# --- PREVIEW VIP ---
@dp.callback_query(F.data == "member_preview")
async def preview_vip(c: CallbackQuery):
    await c.answer("tunggu sebentar...")
    file_id = await get_config("vip_preview_file")
    teks = await get_config("vip_preview_text", "Berikut adalah preview konten VIP kami.")
    if file_id:
        try:
            await bot.send_photo(c.from_user.id, photo=file_id, caption=teks)
        except:
            await bot.send_message(c.from_user.id, teks)
    else:
        await c.message.answer("Preview belum diset oleh admin.")
# --- ORDER VIP ---
@dp.callback_query(F.data == "member_vip")
async def order_vip_start(c: CallbackQuery, state: FSMContext):
    qris_id = await get_config("qris_file_id")
    if not qris_id:
        return await c.message.answer("Admin belum set QRIS.")
    
    await bot.send_photo(c.from_user.id, photo=qris_id, caption="Silakan scan QRIS di atas dan kirim Bukti Transfer (SS) ke sini:")
    await state.set_state(AdminStates.waiting_for_vip_ss)

@dp.message(AdminStates.waiting_for_vip_ss, F.photo)
async def process_vip_ss(m: Message, state: FSMContext):
    await m.answer("tunggu sebentar...")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ APPROVE", callback_data=f"app_vip:{m.from_user.id}"),
         InlineKeyboardButton(text="❌ REJECT", callback_data=f"rej_vip:{m.from_user.id}")]
    ])
    await bot.send_message(OWNER_ID, f"💰 **BUKTI BAYAR VIP** dari <code>{m.from_user.id}</code>:")
    await m.forward(OWNER_ID)
    await bot.send_message(OWNER_ID, "Konfirmasi pembayaran:", reply_markup=kb)
    await m.reply("✅ Bukti berhasil dikirim, mohon tunggu admin sedang cek.")
    await state.clear()
# --- APPROVE/REJECT VIP ---
@dp.callback_query(F.data.startswith("app_vip:"))
async def approve_vip(c: CallbackQuery):
    user_id = int(c.data.split(":")[1])
    group_id = await get_config("vip_group_id")
    
    if not group_id:
        return await c.answer("Admin belum set VIP Group ID!", show_alert=True)

    try:
        # Generate link yang hanya bisa dipakai 1 orang (member_limit=1)
        link = await bot.create_chat_invite_link(chat_id=group_id, member_limit=1)
        await bot.send_message(user_id, f"✅ Pembayaran Valid!\nSilakan join grup VIP melalui link sekali pakai ini:\n{link.invite_link}")
        await c.message.edit_text(f"✅ User {user_id} disetujui. Link terkirim.")
    except Exception as e:
        await c.answer(f"Gagal generate link: {str(e)}", show_alert=True)

@dp.callback_query(F.data.startswith("rej_vip:"))
async def reject_vip(c: CallbackQuery):
    user_id = int(c.data.split(":")[1])
    await bot.send_message(user_id, "❌ Maaf, bukti pembayaran kamu dinyatakan tidak valid.")
    await c.message.edit_text("❌ Pembayaran ditolak.")
# --- REFERRAL ---
@dp.callback_query(F.data == "member_reff")
async def member_reff(c: CallbackQuery):
    user_id = c.from_user.id
    bot_user = await bot.get_me()
    reff_link = f"https://t.me/{bot_user.username}?start=ref_{user_id}"
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT ref_count FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            count = row[0] if row else 0
            
    teks = (f"🔗 **Program Referral**\n\nInvite 20 orang ke bot ini dan dapatkan VIP GRATIS!\n"
            f"Minimal 20 orang.\n\n"
            f"📊 Progres: <b>{count}/20</b>\n"
            f"Link Reff: <code>{reff_link}</code>")
    
    kb = []
    # Jika sudah 20 atau lebih, munculkan tombol klaim
    if count >= 20:
        kb.append([InlineKeyboardButton(text="🎁 KLAIM VIP SEKARANG", callback_data="claim_vip_reff")])
    
    kb.append([InlineKeyboardButton(text="🔙 KEMBALI", callback_data="back_start")])
    
    await c.message.edit_text(teks, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "claim_vip_reff")
async def claim_vip_reff(c: CallbackQuery):
    user_id = c.from_user.id
    # Kirim laporan ke log/admin
    teks_log = f"🎊 **KLAIM VIP REFERRAL**\nUser: <code>{user_id}</code>\nBerhasil mengundang 20+ orang!"
    await send_log(teks_log)
    
    # Notif ke user
    await c.answer("✅ Permintaan klaim dikirim! Admin akan verifikasi.", show_alert=True)
    await bot.send_message(OWNER_ID, f"📩 **NOTIF KLAIM VIP REFF**\nUser ID: <code>{user_id}</code>\nCek data reff-nya dan berikan link VIP jika valid.")
    
async def main():
    await init_db()
    print("Bot is Running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
