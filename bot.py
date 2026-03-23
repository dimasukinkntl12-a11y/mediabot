import asyncio
import os
import aiosqlite
import json
import sqlite3
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
    OWNER_ID = 0  # Default jika belum di-set

DB_NAME = "media.db"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN belum di-set di Environment Variables Railway!")

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
    # Logika Post
    waiting_for_title = State()
    waiting_for_more_media = State()
    waiting_for_update_db = State()
    waiting_for_manual_cover = State()
    # Member Side
    waiting_for_ask = State()
    waiting_for_donation_media = State()
    waiting_for_vip_ss = State()

class PostData:
    def __init__(self):
        self.media_list = [] # List of (file_id, type)
        self.title = ""
        self.manual_cover = None 
# ================= DATABASE HELPER ===============
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, ref_count INTEGER DEFAULT 0, referrer INTEGER)")
        await db.execute("CREATE TABLE IF NOT EXISTS admins (admin_id INTEGER PRIMARY KEY)")
        await db.execute("CREATE TABLE IF NOT EXISTS media_store (msg_unique_id TEXT PRIMARY KEY, media_data TEXT, title TEXT)")
        
        # Default Config
        defaults = [
            ('auto_cover', 'off'),
            ('fsub_text', 'Anda belum join, silakan join dibawah ini'),
            ('fsub_list', ''),
            ('post_channels', '')
        ]
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

async def wait_msg(m: Message):
    return await m.answer("⏳ Tunggu sebentar...")
# ================= cmd ===============
@dp.message(Command("ray"))
async def cmd_ray(m: Message):
    if not await is_admin(m.from_user.id): return
    teks = (
        "<b>🏠 MENU ADMIN RAY</b>\n\n"
        "<b>⚙️ Konfigurasi:</b>\n"
        "/setpostch - Set Channel Post\n"
        "/setfsub - Set Force Subs\n"
        "/listfsub - List FSub aktif\n"
        "/fsubteks - Set Teks FSub\n"
        "/setcove - Set Cover Default\n"
        "/autocover on/off - Toggle Cover\n"
        "/setloggrup - Set Log Grup\n\n"
        "<b>💰 VIP & Reff:</b>\n"
        "/setqris - Set QRIS VIP\n"
        "/setpreview - Set Preview VIP\n"
        "/setvipgrup - Set Grup VIP\n"
        "/setreffch - Set Channel Reff\n\n"
        "<b>👥 Admin:</b>\n"
        "/setadmin - Tambah Admin\n"
        "/delladmin - Hapus Admin\n"
        "/listadmin - List Admin\n\n"
        "<b>📦 System:</b>\n"
        "/bc - Broadcast\n"
        "/senddb - Ambil Database\n"
        "/update - Update Database"
    )
    await m.reply(teks)

@dp.message(Command("setadmin"))
async def set_admin_cmd(m: Message, state: FSMContext):
    if m.from_user.id != OWNER_ID: return
    await m.reply("Kirim ID user yang ingin dijadikan admin:")
    await state.set_state(AdminStates.waiting_for_add_admin)

@dp.message(AdminStates.waiting_for_add_admin)
async def process_add_admin(m: Message, state: FSMContext):
    try:
        aid = int(m.text)
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT OR IGNORE INTO admins VALUES (?)", (aid,))
            await db.commit()
        await m.reply(f"✅ User {aid} berhasil jadi admin.")
    except:
        await m.reply("❌ Kirim ID berupa angka.")
    await state.clear()

@dp.message(Command("listadmin"))
async def list_admin_cmd(m: Message):
    if not await is_admin(m.from_user.id): return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT admin_id FROM admins") as cur:
            rows = await cur.fetchall()
    teks = f"<b>Owner:</b> <code>{OWNER_ID}</code>\n<b>Admins:</b>\n"
    for r in rows: teks += f"- <code>{r[0]}</code>\n"
    await m.reply(teks)

@dp.message(Command("delladmin"))
async def del_admin_cmd(m: Message, state: FSMContext):
    if m.from_user.id != OWNER_ID: return
    await m.reply("Kirim ID admin yang ingin dihapus:")
    await state.set_state(AdminStates.waiting_for_del_admin)

@dp.message(AdminStates.waiting_for_del_admin)
async def process_del_admin(m: Message, state: FSMContext):
    try:
        aid = int(m.text)
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM admins WHERE admin_id = ?", (aid,))
            await db.commit()
        await m.reply(f"✅ Admin {aid} dihapus.")
    except: await m.reply("❌ ID tidak valid.")
    await state.clear()

@dp.message(Command("setpostch"))
async def cmd_setpostch(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await wait_msg(m)
    await m.answer("Kirim ID/Username Channel tujuan post (bisa banyak, pisahkan dengan spasi):")
    await state.set_state(AdminStates.waiting_for_post_ch)

@dp.message(AdminStates.waiting_for_post_ch)
async def process_postch(m: Message, state: FSMContext):
    await set_config("post_channels", m.text.strip())
    await m.reply(f"✅ Channel post diatur ke: <code>{m.text}</code>")
    await state.clear()

@dp.message(Command("fsubteks"))
async def cmd_fsubteks(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await wait_msg(m)
    await m.answer("Kirim teks FSub (Emoji/Format akan disamakan):")
    await state.set_state(AdminStates.waiting_for_fsub_text)

@dp.message(AdminStates.waiting_for_fsub_text)
async def process_fsub_txt(m: Message, state: FSMContext):
    await set_config("fsub_text", m.text)
    await m.reply("✅ Teks FSub berhasil diperbarui.")
    await state.clear()

@dp.message(Command("setfsub"))
async def cmd_setfsub(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await wait_msg(m)
    info = (
        "Kirim daftar FSub dengan format:\n\n"
        "Menyamping: <code>Nama ID - Nama ID</code>\n"
        "Kebawah: <code>Nama ID (pake enter) Nama ID</code>"
    )
    await m.answer(info)
    await state.set_state(AdminStates.waiting_for_fsub)

@dp.message(AdminStates.waiting_for_fsub)
async def process_fsub_list(m: Message, state: FSMContext):
    await set_config("fsub_list", m.text.strip())
    await m.reply("✅ Daftar FSub berhasil disimpan.")
    await state.clear()

@dp.message(Command("listfsub"))
async def cmd_listfsub(m: Message):
    if not await is_admin(m.from_user.id): return
    val = await get_config("fsub_list", "Kosong")
    await m.reply(f"📜 **Daftar FSub:**\n<code>{val}</code>")

@dp.message(Command("autocover"))
async def cmd_autocover(m: Message):
    if not await is_admin(m.from_user.id): return
    status = m.text.split()[-1].lower()
    if status in ['on', 'off']:
        await set_config("auto_cover", status)
        await m.reply(f"✅ Auto Cover: {status.upper()}")
    else:
        await m.reply("Gunakan /autocover on atau off")

@dp.message(Command("setcove"))
async def cmd_setcove(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirim Foto untuk Cover Default:")
    await state.set_state(AdminStates.waiting_for_cover)

@dp.message(Command("setqris"))
async def cmd_setqris(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirim Foto QRIS VIP:")
    await state.set_state(AdminStates.waiting_for_qris)

@dp.message(Command("setpreview"))
async def cmd_setpreview(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirim Foto/Video untuk Preview VIP:")
    await state.set_state(AdminStates.waiting_for_preview)

@dp.message(StateFilter(AdminStates.waiting_for_cover, AdminStates.waiting_for_qris, AdminStates.waiting_for_preview))
async def process_admin_media_configs(m: Message, state: FSMContext):
    current = await state.get_state()
    fid = ""
    if m.photo: fid = m.photo[-1].file_id
    elif m.video: fid = m.video.file_id
    else: return await m.reply("❌ Kirim Media!")

    if current == AdminStates.waiting_for_cover: await set_config("default_cover", fid)
    elif current == AdminStates.waiting_for_qris: await set_config("qris_img", fid)
    elif current == AdminStates.waiting_for_preview: await set_config("vip_preview", fid)
    
    await m.reply("✅ Berhasil diperbarui.")
    await state.clear()

@dp.message(Command("setvipgrup"))
async def set_vip_g(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirim ID Grup VIP:")
    await state.set_state(AdminStates.waiting_for_vip_grup)

@dp.message(AdminStates.waiting_for_vip_grup)
async def process_vip_g(m: Message, state: FSMContext):
    await set_config("vip_group", m.text)
    await m.reply("✅ Grup VIP diset.")
    await state.clear()

@dp.message(Command("setloggrup"))
async def set_log_g(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirim ID Grup/Channel Log:")
    await state.set_state(AdminStates.waiting_for_log_grup)

@dp.message(AdminStates.waiting_for_log_grup)
async def process_log_g(m: Message, state: FSMContext):
    await set_config("log_group", m.text)
    await m.reply("✅ Log Grup diset.")
    await state.clear()

@dp.message(Command("setreffch"))
async def set_reff_c(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirim Username Channel Reff (@ch):")
    await state.set_state(AdminStates.waiting_for_reff_ch)

@dp.message(AdminStates.waiting_for_reff_ch)
async def process_reff_c(m: Message, state: FSMContext):
    await set_config("ref_ch", m.text)
    await m.reply("✅ Channel Reff diset.")
    await state.clear()
# --- Helper untuk menyimpan PostData di Memory per user ---
post_temp = {}

@dp.message(F.media_group_id) # Mencegah error jika kirim album sekaligus
async def handle_media_group(m: Message):
    await m.reply("❌ Mohon kirim media satu per satu (jangan album) agar sistem part berfungsi dengan baik.")

@dp.message(F.photo | F.video)
async def start_post_flow(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    
    # Inisialisasi data post untuk user ini
    uid = m.from_user.id
    post_temp[uid] = PostData()
    
    fid = m.photo[-1].file_id if m.photo else m.video.file_id
    m_type = "photo" if m.photo else "video"
    post_temp[uid].media_list.append({"file_id": fid, "type": m_type})
    
    await m.reply("⏳ Tunggu sebentar...\nSilakan masukkan **Judul** atau ketik /batal")
    await state.set_state(AdminStates.waiting_for_title)

@dp.message(AdminStates.waiting_for_title)
async def process_title(m: Message, state: FSMContext):
    if m.text == "/batal":
        post_temp.pop(m.from_user.id, None)
        await state.clear()
        return await m.reply("✅ Posting dibatalkan.")
    
    uid = m.from_user.id
    post_temp[uid].title = m.text
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ TAMBAH PART LAIN", callback_data="add_more_part")],
        [InlineKeyboardButton(text="🚀 POST SEKARANG", callback_data="post_final")]
    ])
    
    await m.reply(f"Judul: <b>{m.text}</b>\nMedia tersimpan: {len(post_temp[uid].media_list)}", reply_markup=kb)

@dp.callback_query(F.data == "add_more_part")
async def add_more_part_btn(c: CallbackQuery, state: FSMContext):
    await c.message.answer("⏳ Tunggu sebentar...\nSilakan kirim media selanjutnya:")
    await state.set_state(AdminStates.waiting_for_more_media)
    await c.answer()

@dp.message(AdminStates.waiting_for_more_media, F.photo | F.video)
async def process_more_media(m: Message, state: FSMContext):
    uid = m.from_user.id
    fid = m.photo[-1].file_id if m.photo else m.video.file_id
    m_type = "photo" if m.photo else "video"
    
    post_temp[uid].media_list.append({"file_id": fid, "type": m_type})
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ TAMBAH PART LAIN", callback_data="add_more_part")],
        [InlineKeyboardButton(text="🚀 POST SEKARANG", callback_data="post_final")]
    ])
    await m.reply(f"✅ Berhasil ditambah!\nTotal Media: {len(post_temp[uid].media_list)}", reply_markup=kb)

@dp.callback_query(F.data == "post_final")
async def post_final_check(c: CallbackQuery, state: FSMContext):
    uid = c.from_user.id
    acover = await get_config("auto_cover", "off")
    
    if acover == "off":
        await c.message.answer("⏳ Tunggu sebentar...\nAuto Cover <b>OFF</b>. Silakan kirim <b>GAMBAR COVER</b> manual:")
        await state.set_state(AdminStates.waiting_for_manual_cover)
    else:
        # Langsung pilih channel
        await show_channel_options(c.message, uid)
    await c.answer()

@dp.message(AdminStates.waiting_for_manual_cover, F.photo)
async def process_manual_cover(m: Message, state: FSMContext):
    uid = m.from_user.id
    # Simpan cover manual sementara di object PostData
    post_temp[uid].manual_cover = m.photo[-1].file_id
    await show_channel_options(m, uid)
    await state.clear()

async def show_channel_options(m, uid):
    ch_raw = await get_config("post_channels", "")
    if not ch_raw:
        return await m.reply("❌ Belum ada channel post yang diset! Gunakan /setpostch")
    
    channels = ch_raw.split()
    kb_list = []
    for ch in channels:
        kb_list.append([InlineKeyboardButton(text=f"📤 Ke {ch}", callback_data=f"send_to:{ch}")])
    
    kb_list.append([InlineKeyboardButton(text="🌍 POST KE SEMUA CHANNEL", callback_data="send_to_all")])
    
    await m.answer("⏳ Tunggu sebentar...\nPilih channel tujuan posting:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list))

@dp.callback_query(F.data.startswith("send_to"))
async def execute_post(c: CallbackQuery, state: FSMContext):
    uid = c.from_user.id
    target = c.data.split(":")[1] if ":" in c.data else "ALL"
   
    state_data = await state.get_data()
    donasi_prefix = state_data.get("donasi_prefix")
    
    # 1. LOGIKA JIKA INI ADALAH DONASI MEMBER
    if donasi_prefix:
        target_user = state_data.get("current_donasi_user")
        caption = f"{donasi_prefix} donasi member"
        
        msg_ref = c.message.reply_to_message
        
        fid = ""
        m_type = ""
        if msg_ref.photo: 
            fid, m_type = msg_ref.photo[-1].file_id, "photo"
        elif msg_ref.video: 
            fid, m_type = msg_ref.video.file_id, "video"
        elif msg_ref.voice: 
            fid, m_type = msg_ref.voice.file_id, "voice"

        ch_list = (await get_config("post_channels")).split() if target == "ALL" else [target]
        for ch in ch_list:
            try:
                if m_type == "photo": await bot.send_photo(ch, photo=fid, caption=caption)
                elif m_type == "video": await bot.send_video(ch, video=fid, caption=caption)
                elif m_type == "voice": await bot.send_voice(ch, voice=fid, caption=caption)
            except: pass
        
        await bot.send_message(target_user, "🌟 Donasi kamu sudah diposting ke channel! Terima kasih.")
        await c.message.edit_text(f"✅ Donasi berhasil diposting ke {target}.")
        await state.clear()
        return
        
    data = post_temp.get(uid)
    if not data:
        return await c.answer("❌ Data tidak ditemukan.", show_alert=True)

    default_c = await get_config("default_cover")
    cover_to_use = getattr(data, 'manual_cover', default_c)
    
    if not cover_to_use:
        return await c.answer("❌ Cover tidak ditemukan! Set dulu di /setcove atau kirim manual.", show_alert=True)

    # Generate Unique ID untuk Database Store (agar link button aman)
    import uuid
    post_id = str(uuid.uuid4())[:8]
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO media_store VALUES (?, ?)", (post_id, json.dumps(data.media_list)))
        await db.commit()

    # Buat Tombol Nonton
    kb_post = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 NONTON SEKARANG", url=f"https://t.me/{(await bot.get_me()).username}?start={post_id}")]
    ])
    
    caption = f"<b>{data.title}</b>"
    ch_list = (await get_config("post_channels")).split() if target == "ALL" else [target]

    success = 0
    for ch in ch_list:
        try:
            await bot.send_photo(ch, photo=cover_to_use, caption=caption, reply_markup=kb_post)
            success += 1
        except Exception as e:
            print(f"Gagal kirim ke {ch}: {e}")

    await c.message.edit_text(f"✅ Berhasil dipost ke {success} channel!")
    post_temp.pop(uid, None)
    await c.answer()

@dp.message(Command("update"))
async def cmd_update(m: Message, state: FSMContext):
    if m.from_user.id != OWNER_ID: return
    await m.reply("Silakan kirim file <code>media.db</code> untuk update data.")
    await state.set_state(AdminStates.waiting_for_update_db)

@dp.message(AdminStates.waiting_for_update_db, F.document)
async def process_update_db(m: Message, state: FSMContext):
    if not m.document.file_name.endswith(".db"):
        return await m.reply("❌ Harus file .db!")
    
    file_path = "temp_update.db"
    await bot.download(m.document, destination=file_path)
    
    try:
        source_conn = sqlite3.connect(file_path)
        dest_conn = sqlite3.connect(DB_NAME)
        cursor = source_conn.cursor()
        
        # Ambil data media_store
        cursor.execute("SELECT * FROM media_store")
        rows = cursor.fetchall()
        
        added = 0
        dest_cursor = dest_conn.cursor()
        for row in rows:
            # INSERT OR IGNORE agar tidak error jika ID sudah ada
            dest_cursor.execute("INSERT OR IGNORE INTO media_store VALUES (?, ?)", row)
            if dest_cursor.rowcount > 0:
                added += 1
        
        dest_conn.commit()
        source_conn.close()
        dest_conn.close()
        os.remove(file_path)
        await m.reply(f"✅ Berhasil sinkronisasi! {added} data baru ditambahkan.")
    except Exception as e:
        await m.reply(f"❌ Gagal: {e}")
    await state.clear()
# ================= LOGIKA FSUB PARSER =================
async def get_fsub_kb(user_id, post_id=None):
    fsub_raw = await get_config("fsub_list", "")
    if not fsub_raw: return None
    
    rows = []
    lines = fsub_raw.split('\n')
    for line in lines:
        if not line.strip(): continue
        side_by_side = line.split('-')
        current_row = []
        for item in side_by_side:
            parts = item.strip().split()
            if len(parts) < 2: continue
            name, target_id = " ".join(parts[:-1]), parts[-1]
            
            try:
                member = await bot.get_chat_member(target_id, user_id)
                if member.status in ["left", "kicked"]:
                    current_row.append(InlineKeyboardButton(text=name, url=f"https://t.me/{target_id.replace('@','')}"))
            except:
                current_row.append(InlineKeyboardButton(text=name, url=f"https://t.me/{target_id.replace('@','')}"))
        
        if current_row: rows.append(current_row)
    
    if rows:
        if post_id:
            rows.append([InlineKeyboardButton(text="🔄 COBA LAGI", callback_data=f"check:{post_id}")])
        return InlineKeyboardMarkup(inline_keyboard=rows)
    return None
# ================= HANDLER MEMBER =================
@dp.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    uid = m.from_user.id
    args = m.text.split()
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (uid,)) as cur:
            is_new_user = await cur.fetchone() is None

        if is_new_user:
            referrer_id = None
            if len(args) > 1 and args[1].startswith("ref_"):
                try:
                    referrer_id = int(args[1].replace("ref_", ""))
                    if referrer_id != uid: # Tidak bisa mengundang diri sendiri
                        await db.execute(
                            "UPDATE users SET ref_count = ref_count + 1 WHERE user_id = ?", 
                            (referrer_id,)
                        )
                        # Notif ke pengundang (Opsional)
                        try:
                            await bot.send_message(referrer_id, "🔔 Seseorang bergabung menggunakan link kamu! +1 Poin.")
                        except: pass
                except: pass
            
            # Masukkan user baru ke DB
            await db.execute("INSERT INTO users (user_id, referrer) VALUES (?, ?)", (uid, referrer_id))
            await db.commit()

    if len(args) > 1 and not args[1].startswith("ref_"):
        post_id = args[1]
        kb_fsub = await get_fsub_kb(uid)
        if kb_fsub:
            txt = await get_config("fsub_text")
            kb_fsub.inline_keyboard.append([InlineKeyboardButton(text="🔄 COBA LAGI", url=f"https://t.me/{(await bot.get_me()).username}?start={post_id}")])
            return await m.reply(txt, reply_markup=kb_fsub)
        
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT media_data FROM media_store WHERE msg_unique_id = ?", (post_id,)) as cur:
                row = await cur.fetchone()
        
        if row:
            await wait_msg(m)
            media_list = json.loads(row[0])
            for i, med in enumerate(media_list):
                caption = f"Part {i+1}" if len(media_list) > 1 else ""
                if med['type'] == "photo":
                    await bot.send_photo(uid, photo=med['file_id'], caption=caption, protect_content=True)
                else:
                    await bot.send_video(uid, video=med['file_id'], caption=caption, protect_content=True)
            return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ ASK ADMIN", callback_data="member_ask"), InlineKeyboardButton(text="🎁 DONASI", callback_data="member_donasi")],
        [InlineKeyboardButton(text="💎 ORDER VIP", callback_data="member_vip"), InlineKeyboardButton(text="👀 PREVIEW VIP", callback_data="member_preview")],
        [InlineKeyboardButton(text="🔗 REFERRAL", callback_data="member_reff")]
    ])
    await m.reply(f"Halo {m.from_user.first_name}! Selamat datang di Bot Media.", reply_markup=kb)
# --- Fitur Referral ---
@dp.callback_query(F.data == "member_reff")
async def reff_menu(c: CallbackQuery):
    uid = c.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT ref_count FROM users WHERE user_id = ?", (uid,)) as cur:
            row = await cur.fetchone()
            count = row[0] if row else 0
    
    bot_user = (await bot.get_me()).username
    link = f"https://t.me/{bot_user}?start=ref_{uid}"
    
    txt = (
        "<b>🔗 PROGRAM REFERRAL</b>\n\n"
        f"Undang teman untuk bergabung dan dapatkan VIP Gratis!\n"
        f"Minimal: 20 Orang\n"
        f"Progress Kamu: <b>{count}/20</b>\n\n"
        f"Link Referral Kamu:\n<code>{link}</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ SAYA SETUJU & AMBIL LINK", callback_data="gen_reff")],
        [InlineKeyboardButton(text="⬅️ KEMBALI", callback_data="back_home")]
    ])
    await c.message.edit_text(txt, reply_markup=kb)

@dp.callback_query(F.data == "member_ask")
async def ask_start(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Silakan kirim pesan yang ingin disampaikan ke admin:")
    await state.set_state(AdminStates.waiting_for_ask)
    await c.answer()

@dp.message(AdminStates.waiting_for_ask)
async def process_ask(m: Message, state: FSMContext):
    await bot.send_message(OWNER_ID, f"📩 **PESAN ASK BARU** dari <code>{m.from_user.id}</code>:")
    await m.forward(OWNER_ID)
    await m.reply("✅ Pesan berhasil terkirim, silakan tunggu balasan.")
    await state.clear()

@dp.callback_query(F.data == "member_donasi")
async def donasi_start(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 COWO", callback_data="donasi:CO"), InlineKeyboardButton(text="👩 CEWE", callback_data="donasi:CE")]
    ])
    await c.message.edit_text("Pilih kategori donasi kamu:", reply_markup=kb)

@dp.callback_query(F.data.startswith("donasi:"))
async def donasi_type(c: CallbackQuery, state: FSMContext):
    dtype = c.data.split(":")[1]
    await state.update_data(donasi_type=dtype)
    await c.message.answer("Silakan kirim Media atau Voice Note untuk didonasikan:")
    await state.set_state(AdminStates.waiting_for_donation_media)
    await c.answer()

@dp.message(AdminStates.waiting_for_donation_media, F.photo | F.video | F.voice)
async def process_donasi_media(m: Message, state: FSMContext):
    data = await state.get_data()
    dtype = data.get("donasi_type", "CO")
    prefix = "co" if dtype == "CO" else "ce"
    
    kb_admin = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ APPROVE", callback_data=f"app_donasi:{m.from_user.id}:{prefix}"), 
         InlineKeyboardButton(text="❌ REJECT", callback_data=f"rej_donasi:{m.from_user.id}")]
    ])
    
    await bot.send_message(OWNER_ID, f"🎁 **DONASI BARU** dari <code>{m.from_user.id}</code> ({prefix}):")
    await m.forward(OWNER_ID)
    await bot.send_message(OWNER_ID, "Tindakan:", reply_markup=kb_admin)
    
    await m.reply("✅ Donasi berhasil terkirim, terimakasih sudah berdonasi!")
    await state.clear()

@dp.callback_query(F.data == "member_vip")
async def vip_order(c: CallbackQuery, state: FSMContext):
    qris = await get_config("qris_img")
    if not qris: return await c.answer("❌ Admin belum set QRIS.", show_alert=True)
    
    await bot.send_photo(c.from_user.id, photo=qris, caption="Silakan scan QRIS di atas dan kirim bukti pembayaran (Screenshot) ke sini:")
    await state.set_state(AdminStates.waiting_for_vip_ss)
    await c.answer()

@dp.message(AdminStates.waiting_for_vip_ss, F.photo)
async def process_vip_ss(m: Message, state: FSMContext):
    kb_admin = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ APPROVE", callback_data=f"app_vip:{m.from_user.id}"), 
         InlineKeyboardButton(text="❌ REJECT", callback_data=f"rej_vip:{m.from_user.id}")]
    ])
    await bot.send_message(OWNER_ID, f"💰 **ORDER VIP** dari <code>{m.from_user.id}</code>:")
    await m.forward(OWNER_ID)
    await bot.send_message(OWNER_ID, "Konfirmasi Pembayaran:", reply_markup=kb_admin)
    await m.reply("✅ Bukti berhasil dikirim, mohon tunggu admin sedang cek.")
    await state.clear()

@dp.callback_query(F.data.startswith(("app_vip", "rej_vip")))
async def handle_approval(c: CallbackQuery):
    action = c.data.split(":")[0]
    target_id = int(c.data.split(":")[1])
    
    if action == "app_vip":
        # Generate Link VIP
        vip_chat = await get_config("vip_group")
        try:
            link = await bot.create_chat_invite_link(vip_chat, member_limit=1)
            await bot.send_message(target_id, f"✅ Pembayaran Valid! Ini link grup VIP kamu:\n{link.invite_link}")
            await c.message.edit_text("✅ Berhasil dikirim ke user.")
        except:
            await c.answer("❌ Gagal generate link. Pastikan ID Grup benar & Bot Admin.", show_alert=True)
            
    elif action == "rej_vip":
        await bot.send_message(target_id, "❌ Bukti pembayaran kamu tidak valid.")
        await c.message.edit_text("❌ Ditolak.")
        
    await c.answer()
    
@dp.callback_query(F.data.startswith(("app_donasi:", "rej_donasi:")))
async def handle_donasi_approval(c: CallbackQuery, state: FSMContext):
    data_parts = c.data.split(":")
    action = data_parts[0]
    target_id = int(data_parts[1])
    
    if action == "app_donasi":
        prefix = data_parts[2] # 'ce' atau 'co'
        # Simpan prefix ke state sementara untuk proses posting
        await state.update_data(current_donasi_user=target_id, donasi_prefix=prefix)
        
        # Ambil media dari pesan yang di-forward (pesan yang di-reply oleh tombol ini)
        # Kita perlu kirim ulang logika pilih channel seperti posting biasa
        await c.message.answer(f"✅ Donasi ({prefix}) disetujui. Pilih channel untuk posting:")
        await show_channel_options(c.message, c.from_user.id)
        
    elif action == "rej_donasi":
        try:
            await bot.send_message(target_id, "❌ Maaf, donasi kamu ditolak oleh admin karena tidak sesuai kriteria.")
            await c.message.edit_text(f"❌ Donasi dari {target_id} telah ditolak.")
        except:
            await c.message.edit_text(f"❌ Ditolak, tapi gagal memberitahu user (bot diblokir).")
    
    await c.answer()

@dp.callback_query(F.data == "back_home")
async def back_home(c: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ ASK ADMIN", callback_data="member_ask"), InlineKeyboardButton(text="🎁 DONASI", callback_data="member_donasi")],
        [InlineKeyboardButton(text="💎 ORDER VIP", callback_data="member_vip"), InlineKeyboardButton(text="👀 PREVIEW VIP", callback_data="member_preview")],
        [InlineKeyboardButton(text="🔗 REFERRAL", callback_data="member_reff")]
    ])
    await c.message.edit_text(f"Halo {c.from_user.first_name}! Ada yang bisa dibantu?", reply_markup=kb)

@dp.callback_query(F.data == "gen_reff")
async def check_claim(c: CallbackQuery):
    uid = c.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT ref_count FROM users WHERE user_id = ?", (uid,)) as cur:
            row = await cur.fetchone()
            count = row[0] if row else 0
    
    if count >= 20:
        await bot.send_message(OWNER_ID, f"🔔 **KLAIM REFERRAL**\nUser: <code>{uid}</code> berhasil mencapai {count} poin!")
        await c.answer("✅ Permintaan klaim dikirim ke admin!", show_alert=True)
    else:
        await c.answer(f"Poin kamu baru {count}, butuh {20-count} lagi untuk klaim.", show_alert=True)
# --- System Commands ---
@dp.message(Command("senddb"))
async def cmd_senddb(m: Message):
    if m.from_user.id != OWNER_ID: return
    # Memaksa nama file menjadi media.db
    file = FSInputFile(DB_NAME, filename="media.db")
    await m.reply_document(file, caption="Backup Database Terbaru")

@dp.message(Command("bc"))
async def cmd_bc(m: Message, state: FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.reply("Kirim pesan broadcast:")
    await state.set_state(AdminStates.waiting_for_bc)

@dp.message(AdminStates.waiting_for_bc)
async def process_bc(m: Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            users = await cur.fetchall()
    
    success = 0
    for u in users:
        try:
            await m.copy_to(u[0])
            success += 1
            await asyncio.sleep(0.05)
        except: pass
    await m.reply(f"✅ Broadcast selesai ke {success} user.")
    await state.clear()

@dp.callback_query(F.data.startswith("check:"))
async def check_fsub_btn(c: CallbackQuery):
    pid = c.data.split(":")[1]
    kb = await get_fsub_kb(c.from_user.id, pid)
    if kb:
        return await c.answer("❌ Kamu belum join semua channel!", show_alert=True)
    
    # Jika sudah join semua, hapus pesan fsub dan kirim medianya
    await c.message.delete()
    # Panggil fungsi kirim media (send_media_logic)
    await send_media_to_user(c.from_user.id, pid)
    
async def main():
    await init_db()
    print("Bot is Running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except:
        pass
