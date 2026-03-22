import os
import sqlite3
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
import pyromod # Wajib di-import agar fitur .ask() aktif

# --- KONFIGURASI ENV ---
load_dotenv()
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID")) # ID Telegram kamu sebagai Super Admin

app = Client("media_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- DATABASE SETUP ---
DB_NAME = "media.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabel Pengaturan Bot
    c.execute('''CREATE TABLE IF NOT EXISTS settings 
                 (key TEXT PRIMARY KEY, value TEXT)''')
    # Tabel Admin
    c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
    # Tabel Channel Post & Fsub
    c.execute('''CREATE TABLE IF NOT EXISTS post_channels (chat_id INTEGER PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS fsub_channels (chat_id TEXT, btn_text TEXT, layout_row INTEGER)''')
    # Tabel Media Post
    c.execute('''CREATE TABLE IF NOT EXISTS posts (post_id TEXT PRIMARY KEY, cover_id TEXT, title TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS post_media (post_id TEXT, part_num INTEGER, media_id TEXT, type TEXT)''')
    # Tabel User & Referral
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, ref_by INTEGER, ref_count INTEGER DEFAULT 0, is_vip INTEGER DEFAULT 0)''')
    
    # Default settings
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('autocover', 'off')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('fsub_teks', 'Anda belum join, silahkan join di bawah ini:')")
    conn.commit()
    conn.close()

init_db()

# --- HELPER DATABASE ---
def get_setting(key):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else None

def set_setting(key, value):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def is_admin(user_id):
    if user_id == OWNER_ID: return True
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return bool(res)

# --- HELPER FSUB ---
async def check_fsub(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT chat_id, btn_text, layout_row FROM fsub_channels ORDER BY layout_row")
    fsubs = c.fetchall()
    conn.close()
    
    unjoined = []
    for chat_id, btn_text, row in fsubs:
        try:
            # Pengecekan member
            member = await app.get_chat_member(chat_id, user_id)
            if member.status in ["left", "kicked", "banned"]:
                unjoined.append((chat_id, btn_text, row))
        except:
            unjoined.append((chat_id, btn_text, row)) # Jika bot gagal cek, anggap belum join
            
    return unjoined

def build_fsub_keyboard(unjoined_list, retry_callback_data="None"):
    keyboard = []
    current_row = []
    last_row_idx = None
    
    for chat_id, btn_text, row_idx in unjoined_list:
        link = f"https://t.me/{chat_id.replace('@', '')}" if isinstance(chat_id, str) and chat_id.startswith("@") else chat_id
        btn = InlineKeyboardButton(btn_text, url=link)
        
        if last_row_idx is None or last_row_idx == row_idx:
            current_row.append(btn)
        else:
            keyboard.append(current_row)
            current_row = [btn]
        last_row_idx = row_idx
        
    if current_row:
        keyboard.append(current_row)
        
    if retry_callback_data != "None":
        keyboard.append([InlineKeyboardButton("Coba Lagi", callback_data=retry_callback_data)])
        
    return InlineKeyboardMarkup(keyboard)

# ==========================================
# KHUSUS ADMIN COMMANDS
# ==========================================

@app.on_message(filters.command("ray") & filters.private)
async def cmd_ray(client, message):
    if not is_admin(message.from_user.id): return
    help_text = """
**Daftar Command Admin:**
/setpostch - Set ch posting
/setfsub - Set ch/grup forcesub
/setcove - Set cover utama
/setqris - Set QRIS VIP
/setpreview - Set preview VIP
/setvipgrup - Set grup VIP (untuk auto link)
/setloggrup - Set grup log
/setreffch - Set ch khusus refferal
/bc - Broadcast
/senddb - Ambil file database
/autocover [on/off] - Toggle auto cover
/listfsub - Lihat list forcesub
/update - Balas ke file media.db untuk sinkronisasi
/fsubteks - Set teks forcesub
/setadmin - Tambah admin (Hanya Owner)
/delladmin - Hapus admin (Hanya Owner)
/listadmin - List admin
    """
    await message.reply(help_text)

@app.on_message(filters.command("setfsub") & filters.private)
async def cmd_setfsub(client, message):
    if not is_admin(message.from_user.id): return
    teks = await message.chat.ask(
        "Kirim format Fsub.\nContoh sejajar:\n`Tombol 1 @usn1 - Tombol 2 @usn2`\n\nContoh kebawah:\n`Tombol 1 @usn1\nTombol 2 @usn2`"
    )
    if not teks.text: return
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM fsub_channels") # Reset lama
    
    lines = teks.text.split('\n')
    row_idx = 0
    for line in lines:
        if not line.strip(): continue
        buttons = line.split('-')
        for btn in buttons:
            try:
                text_part, id_part = btn.strip().rsplit(' ', 1)
                c.execute("INSERT INTO fsub_channels VALUES (?, ?, ?)", (id_part, text_part, row_idx))
            except:
                await message.reply("Format salah pada bagian: " + btn)
                return
        row_idx += 1
    conn.commit()
    conn.close()
    await message.reply("Fsub berhasil diset!")

@app.on_message(filters.command("autocover") & filters.private)
async def cmd_autocover(client, message):
    if not is_admin(message.from_user.id): return
    if len(message.command) < 2:
        return await message.reply("Gunakan /autocover on atau /autocover off")
    status = message.command[1].lower()
    if status in ["on", "off"]:
        set_setting("autocover", status)
        await message.reply(f"Auto cover diset menjadi: {status}")

@app.on_message(filters.command("senddb") & filters.private)
async def cmd_senddb(client, message):
    if message.from_user.id != OWNER_ID: return # Keamanan ekstra
    msg = await message.reply("Tunggu sebentar...")
    await message.reply_document(DB_NAME)
    await msg.delete()

@app.on_message(filters.command("update") & filters.private & filters.reply)
async def cmd_update(client, message):
    if message.from_user.id != OWNER_ID: return
    if not message.reply_to_message.document or not message.reply_to_message.document.file_name.endswith('.db'):
        return await message.reply("Balas ke file media.db yang valid!")
    
    msg = await message.reply("Tunggu sebentar, sedang sinkronisasi DB...")
    new_db_path = await message.reply_to_message.download("update_temp.db")
    
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("ATTACH DATABASE 'update_temp.db' AS tempdb")
        # Update/Append data tanpa replace total
        tables = ["users", "posts", "post_media"] 
        for table in tables:
            c.execute(f"INSERT OR IGNORE INTO {table} SELECT * FROM tempdb.{table}")
        conn.commit()
        conn.close()
        os.remove(new_db_path)
        await msg.edit("Database berhasil diupdate/disinkronisasi (menambahkan yang belum ada)!")
    except Exception as e:
        await msg.edit(f"Gagal update: {e}")

# ==========================================
# LOGIKA POSTING MEDIA (ADMIN)
# ==========================================
# Menyimpan sesi upload per admin
upload_sessions = {}

@app.on_message((filters.photo | filters.video | filters.document) & filters.private)
async def admin_upload_media(client, message):
    if not is_admin(message.from_user.id): return
    
    admin_id = message.from_user.id
    media_msg = message
    
    msg_wait = await message.reply("Tunggu sebentar...")
    
    judul_req = await message.chat.ask("Silahkan masukkan judul atau ketik /batal")
    await msg_wait.delete()
    
    if judul_req.text == "/batal":
        return await message.reply("Post dibatalkan.")
    
    # Simpan ke sesi sementara
    import uuid
    post_id = str(uuid.uuid4())[:8]
    upload_sessions[admin_id] = {
        "post_id": post_id,
        "title": judul_req.text,
        "parts": [media_msg.id]
    }
    
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("Post Sekarang", callback_data="post_now")],
        [InlineKeyboardButton("Tambah Part Lain", callback_data="add_part")]
    ])
    await message.reply(f"Judul diset: {judul_req.text}\nPilih tindakan selanjutnya:", reply_markup=btn)

@app.on_callback_query(filters.regex("add_part"))
async def cb_add_part(client, callback_query):
    admin_id = callback_query.from_user.id
    if admin_id not in upload_sessions: return await callback_query.answer("Sesi kadaluarsa", show_alert=True)
    
    await callback_query.message.delete()
    next_media = await client.ask(callback_query.message.chat.id, "Silahkan kirim media selanjutnya:")
    
    upload_sessions[admin_id]["parts"].append(next_media.id)
    
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("Post Sekarang", callback_data="post_now")],
        [InlineKeyboardButton("Tambah Part Lain", callback_data="add_part")]
    ])
    await callback_query.message.reply(f"Part ditambahkan. Total part: {len(upload_sessions[admin_id]['parts'])}\nPilih tindakan:", reply_markup=btn)

@app.on_callback_query(filters.regex("post_now"))
async def cb_post_now(client, callback_query):
    admin_id = callback_query.from_user.id
    if admin_id not in upload_sessions: return await callback_query.answer("Sesi kadaluarsa", show_alert=True)
    
    autocover = get_setting("autocover")
    cover_id = get_setting("cover_id") # Ambil dari DB jika ada
    
    await callback_query.message.delete()
    
    if autocover == "off":
        cover_req = await client.ask(callback_query.message.chat.id, "Autocover OFF. Silahkan kirim cover gambar/video untuk postingan ini:")
        cover_id = cover_req.photo.file_id if cover_req.photo else cover_req.video.file_id
    
    upload_sessions[admin_id]["cover"] = cover_id
    
    # Tampilkan pilihan Channel
    # (Di sini kamu bisa query channel yang diset dari /setpostch)
    # Untuk contoh ini, kita simulasikan langsung tombol post semua
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("Post di Semua Channel", callback_data="execute_post_all")]
    ])
    await callback_query.message.reply("Pilih tujuan posting:", reply_markup=btn)

@app.on_callback_query(filters.regex("execute_post_all"))
async def execute_post(client, callback_query):
    admin_id = callback_query.from_user.id
    session = upload_sessions.pop(admin_id, None)
    if not session: return await callback_query.answer("Sesi tidak valid", show_alert=True)
    
    msg_wait = await callback_query.message.reply("Tunggu sebentar, sedang memproses ke database...")
    
    post_id = session["post_id"]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO posts VALUES (?, ?, ?)", (post_id, session.get("cover"), session["title"]))
    
    for idx, msg_id in enumerate(session["parts"]):
        # Disini logic ambil file_id asli dari message (butuh get_messages untuk file_id yg persisten)
        msg = await client.get_messages(callback_query.message.chat.id, msg_id)
        media_id = msg.photo.file_id if msg.photo else (msg.video.file_id if msg.video else msg.document.file_id)
        c.execute("INSERT INTO post_media VALUES (?, ?, ?, ?)", (post_id, idx+1, media_id, msg.media.value))
    
    conn.commit()
    conn.close()
    
    # Kirim ke channel (Logika: ambil data dari post_channels)
    # Contoh format tombol di channel
    bot_username = (await client.get_me()).username
    btn_nonton = [InlineKeyboardButton("Nonton Part 1", url=f"https://t.me/{bot_username}?start=watch_{post_id}_1")]
    if len(session["parts"]) > 1:
        btn_nonton.append(InlineKeyboardButton("Part 2", url=f"https://t.me/{bot_username}?start=watch_{post_id}_2"))
    
    # Broadcast ke CH yang sudah di set...
    await msg_wait.edit("Berhasil di post!")


# ==========================================
# LOGIKA MEMBER / USER
# ==========================================

@app.on_message(filters.command("start") & filters.private)
async def cmd_start(client, message):
    user_id = message.from_user.id
    text_args = message.text.split(None, 1)[1] if len(message.text.split()) > 1 else None

    # Handle Nonton & Fsub Logika
    if text_args and text_args.startswith("watch_"):
        data_parts = text_args.replace("watch_", "").split("_")
        post_id = data_parts[0]
        part_num = int(data_parts[1]) if len(data_parts) > 1 else 1
        
        # Cek Fsub
        unjoined = await check_fsub(user_id)
        if unjoined:
            fsub_teks = get_setting("fsub_teks")
            btn = build_fsub_keyboard(unjoined, retry_callback_data=f"retry_watch_{post_id}_{part_num}")
            return await message.reply(fsub_teks, reply_markup=btn)
            
        # Jika lolos fsub, kirim media terproteksi
        msg_wait = await message.reply("Tunggu sebentar...")
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT media_id, type FROM post_media WHERE post_id=? AND part_num=?", (post_id, part_num))
        media = c.fetchone()
        conn.close()
        
        await msg_wait.delete()
        if media:
            if media[1] == "video":
                await client.send_video(message.chat.id, media[0], protect_content=True)
            elif media[1] == "photo":
                await client.send_photo(message.chat.id, media[0], protect_content=True)
            else:
                await client.send_document(message.chat.id, media[0], protect_content=True)
        else:
            await message.reply("Media tidak ditemukan.")
        return

    # Menu Utama Normal
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("Ask Admin", callback_data="menu_ask"), InlineKeyboardButton("Donasi", callback_data="menu_donasi")],
        [InlineKeyboardButton("Order VIP", callback_data="menu_order_vip"), InlineKeyboardButton("Preview VIP", callback_data="menu_preview")],
        [InlineKeyboardButton("Referral", callback_data="menu_reff")]
    ])
    await message.reply("Selamat datang di Menu Member:", reply_markup=btn)

@app.on_callback_query(filters.regex("^retry_watch_"))
async def cb_retry_watch(client, callback_query):
    # Logika Coba Lagi buat fsub
    _, _, post_id, part_num = callback_query.data.split("_")
    unjoined = await check_fsub(callback_query.from_user.id)
    if unjoined:
        btn = build_fsub_keyboard(unjoined, retry_callback_data=callback_query.data)
        await callback_query.answer("Anda masih belum join semua channel!", show_alert=True)
        await callback_query.message.edit_reply_markup(reply_markup=btn)
    else:
        await callback_query.message.delete()
        # Trigger pengiriman media spt fungsi start
        msg = callback_query.message
        msg.text = f"/start watch_{post_id}_{part_num}"
        msg.from_user = callback_query.from_user
        await cmd_start(client, msg)

@app.on_callback_query(filters.regex("menu_order_vip"))
async def cb_order_vip(client, callback_query):
    # Nampilin QRIS dari setqris
    qris_id = get_setting("qris_media_id")
    qris_text = get_setting("qris_caption") or "Silahkan scan QRIS ini dan kirim bukti SS."
    
    await callback_query.message.delete()
    if qris_id:
        await client.send_photo(callback_query.message.chat.id, qris_id, caption=qris_text)
    
    # Tunggu balasan bukti TF
    bukti = await client.ask(callback_query.message.chat.id, "Kirimkan foto Screenshot bukti transfer di sini:", filters=filters.photo)
    
    msg_wait = await bukti.reply("Tunggu sebentar...")
    # Forward ke admin grup / log grup
    log_grup = int(get_setting("log_grup_id") or OWNER_ID)
    forwarded = await bukti.copy(log_grup, caption=f"Ada Order VIP dari User ID: `{callback_query.from_user.id}`\n\nMenunggu Approve/Reject.")
    
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("Approve", callback_data=f"vip_approve_{callback_query.from_user.id}"),
         InlineKeyboardButton("Reject", callback_data=f"vip_reject_{callback_query.from_user.id}")]
    ])
    await client.edit_message_reply_markup(log_grup, forwarded.id, reply_markup=btn)
    
    await msg_wait.edit("Bukti berhasil dikirim mohon tunggu admin sedang cek.")

@app.on_callback_query(filters.regex("^vip_approve_"))
async def cb_vip_approve(client, callback_query):
    if not is_admin(callback_query.from_user.id): return
    target_user = int(callback_query.data.split("_")[2])
    
    vip_grup = get_setting("vip_grup_id")
    if not vip_grup: return await callback_query.answer("Grup VIP belum di set!", show_alert=True)
    
    # Generate Link Max Join 1 Orang
    invite_link = await client.create_chat_invite_link(int(vip_grup), member_limit=1)
    
    await client.send_message(target_user, f"Pembayaran divalidasi! Berikut link VIP Anda (Hanya bisa diklik 1x):\n{invite_link.invite_link}")
    await callback_query.message.edit_caption(f"Status: APPROVED by {callback_query.from_user.first_name}")

if __name__ == "__main__":
    app.run()
