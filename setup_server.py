"""
Bot dựng server Discord GTA 6 — chạy MỘT LẦN, xong tự tắt.

Cách dùng:
  1. pip install discord.py
  2. Đặt token bot vào biến môi trường DISCORD_TOKEN (KHÔNG dán token vào code)
  3. python setup_server.py

Chạy lại nhiều lần cũng không sao: cái gì có rồi thì bỏ qua, chỉ cập nhật quyền.
"""

import os
import discord

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # không bắt buộc nếu bot chỉ ở 1 server
REASON = "Setup server GTA 6"

# ───────────────────────── ROLE ─────────────────────────
# (tên, màu, quyền, hiện riêng trong danh sách thành viên)
ROLES = [
    ("🛡️ Mod", 0x3498DB, dict(manage_messages=True, kick_members=True,
                              moderate_members=True, manage_threads=True,
                              mute_members=True, move_members=True), True),
    ("🎮 PS5", 0x2E6BE6, {}, False),
    ("🎮 Xbox", 0x107C10, {}, False),
    ("💻 Đang chờ PC", 0x95A5A6, {}, False),
    ("🔓 Xem spoil", 0xF1C40F, {}, False),
    ("🔔 Thông báo video", 0xE74C3C, {}, False),
]

# ──────────────────────── KÊNH ──────────────────────────
# mode: "readonly" = chỉ Mod đăng | "spoil" = chỉ role Xem spoil thấy | "public"
STRUCTURE = [
    ("📌 THÔNG TIN", [
        ("text", "📜・luật-server", "readonly", "Đọc luật trước khi chat nhé!"),
        ("text", "📢・thông-báo", "readonly", "Thông báo của server"),
        ("text", "🎬・video-mới", "readonly", "Video mới từ kênh YouTube"),
    ]),
    ("📰 TIN TỨC GTA 6", [
        ("text", "📰・tin-chính-thức", "readonly", "Tin chính thức từ Rockstar / Take-Two"),
        ("text", "🕵️・leak-tin-đồn", "public", "Tin đồn & leak — CHƯA xác thực, nhớ ghi nguồn"),
    ]),
    ("🌴 CỘNG ĐỒNG", [
        ("text", "💬・chat-chung", "public", "Chém gió đủ thứ (không spoil!)"),
        ("text", "📸・khoe-ảnh-clip", "public", "Khoe ảnh, clip GTA 6 của bạn"),
        ("text", "❓・hỏi-đáp", "public", "Kẹt nhiệm vụ? Hỏi ở đây"),
        ("text", "🤝・tìm-bạn-chơi", "public", "Tìm đồng đội, ghi rõ PS5/Xbox"),
    ]),
    ("⚠️ KHU SPOIL", [
        ("text", "🔥・spoil-cốt-truyện", "spoil", "Spoil thoải mái — đã vào đây là chấp nhận"),
    ]),
    ("🎥 KÊNH YOUTUBE", [
        ("text", "💡・góp-ý-tưởng", "public", "Muốn xem video gì? Đề xuất & thả 👍 để vote"),
    ]),
    ("🔊 VOICE", [
        ("voice", "🎙️ Chém gió", "public", None),
        ("voice", "🎮 Chơi cùng", "public", None),
    ]),
]

# ─────────────────────── NỘI DUNG ───────────────────────
RULES = [
    ("1. Tôn trọng mọi người",
     "Không chửi bới, phân biệt, công kích cá nhân."),
    ("2. Không spoil ngoài khu spoil",
     "Bàn cốt truyện thì vào 🔥・spoil-cốt-truyện (cần role 🔓 Xem spoil). "
     "Ở kênh khác phải che bằng ||spoiler||."),
    ("3. Không spam, không quảng cáo",
     "Không quảng cáo server/kênh khác khi chưa được Mod cho phép."),
    ("4. Cẩn thận lừa đảo ⚠️",
     "GTA 6 hiện CHƯA có bản PC. Mọi link \"tải GTA 6 PC\", \"key miễn phí\", "
     "\"hack tiền\" đều là lừa đảo. Không đăng, không bấm."),
    ("5. Không đăng file leak hay crack",
     "Muốn bàn tin leak thì vào 🕵️・leak-tin-đồn và ghi nguồn."),
    ("6. Đúng kênh, đúng chủ đề",
     "Đọc mô tả kênh trước khi đăng."),
    ("7. Nghe lời Mod",
     "Vi phạm: nhắc nhở → timeout → kick/ban."),
]

ANNOUNCE = (
    "Chào mừng anh em đến với cộng đồng GTA 6! 🌴\n\n"
    "Ở đây có tin tức mới nhất, hỏi đáp, khoe ảnh clip, tìm bạn chơi "
    "và là nơi góp ý cho kênh YouTube của server.\n\n"
    "👉 Đọc 📜・luật-server trước\n"
    "👉 Muốn bàn cốt truyện thoải mái? Lấy role 🔓 Xem spoil\n"
    "👉 Muốn xem video gì, ghé 💡・góp-ý-tưởng"
)

IDEA_GUIDE = (
    "**Cách góp ý tưởng video:**\n"
    "• Mỗi tin nhắn là một ý tưởng\n"
    "• Thả 👍 cho ý tưởng bạn muốn xem nhất\n"
    "• Ý tưởng nhiều 👍 nhất sẽ được ưu tiên làm!"
)

SPOIL_WARN = "⚠️ Khu này spoil thoải mái. Chưa chơi xong thì quay xe nhé!"

LEAK_WARN = (
    "🕵️ Tin ở đây là tin đồn, CHƯA được xác nhận. Luôn ghi nguồn. "
    "Không đăng file/video leak trực tiếp."
)

# ───────────────────────── CODE ─────────────────────────
intents = discord.Intents.default()
client = discord.Client(intents=intents)


def build_overwrites(guild, mode, roles):
    PO = discord.PermissionOverwrite
    ow = {guild.me: PO(view_channel=True, send_messages=True, embed_links=True,
                       read_message_history=True, manage_messages=True)}
    mod = roles["🛡️ Mod"]
    if mode == "readonly":
        ow[guild.default_role] = PO(send_messages=False, add_reactions=True,
                                    create_public_threads=False,
                                    create_private_threads=False)
        ow[mod] = PO(send_messages=True)
    elif mode == "spoil":
        ow[guild.default_role] = PO(view_channel=False)
        ow[roles["🔓 Xem spoil"]] = PO(view_channel=True)
        ow[mod] = PO(view_channel=True)
    return ow


async def ensure_role(guild, name, color, perms, hoist):
    role = discord.utils.get(guild.roles, name=name)
    if role:
        print(f"  = role có sẵn: {name}")
        return role
    role = await guild.create_role(
        name=name, colour=discord.Colour(color),
        permissions=discord.Permissions(**perms),
        hoist=hoist, mentionable=False, reason=REASON)
    print(f"  + tạo role: {name}")
    return role


async def ensure_category(guild, name):
    cat = discord.utils.get(guild.categories, name=name)
    if cat:
        print(f"  = danh mục có sẵn: {name}")
        return cat
    cat = await guild.create_category(name, reason=REASON)
    print(f"  + tạo danh mục: {name}")
    return cat


async def ensure_channel(category, kind, name, overwrites, topic):
    existing = discord.utils.get(category.channels, name=name)
    if existing:
        await existing.edit(overwrites=overwrites, reason=REASON)
        print(f"    = kênh có sẵn (đã cập nhật quyền): {name}")
        return existing
    if kind == "voice":
        ch = await category.create_voice_channel(
            name, overwrites=overwrites, reason=REASON)
    else:
        ch = await category.create_text_channel(
            name, overwrites=overwrites, topic=topic, reason=REASON)
    print(f"    + tạo kênh: {name}")
    return ch


async def post_once(channel, embed=None, content=None, pin=False):
    """Chỉ đăng nếu bot chưa từng đăng trong kênh này."""
    async for msg in channel.history(limit=30):
        if msg.author == client.user:
            return
    msg = await channel.send(content=content, embed=embed)
    if pin:
        await msg.pin()


def pick_guild():
    if GUILD_ID:
        return client.get_guild(int(GUILD_ID))
    if len(client.guilds) == 1:
        return client.guilds[0]
    raise SystemExit("Bot đang ở nhiều server — hãy đặt biến GUILD_ID.")


@client.event
async def on_ready():
    try:
        guild = pick_guild()
        if guild is None:
            raise SystemExit("Không tìm thấy server. Kiểm tra GUILD_ID.")
        print(f"Đang dựng server: {guild.name}\n")

        print("Role:")
        roles = {}
        for name, color, perms, hoist in ROLES:
            roles[name] = await ensure_role(guild, name, color, perms, hoist)

        print("\nKênh:")
        channels = {}
        for cat_name, items in STRUCTURE:
            cat = await ensure_category(guild, cat_name)
            for kind, name, mode, topic in items:
                ow = build_overwrites(guild, mode, roles)
                channels[name] = await ensure_channel(cat, kind, name, ow, topic)

        print("\nĐăng nội dung:")
        rules = discord.Embed(title="📜 LUẬT SERVER", colour=0xF1C40F,
                              description="Đọc kỹ để chơi vui, không bị phạt nhé!")
        for title, text in RULES:
            rules.add_field(name=title, value=text, inline=False)
        await post_once(channels["📜・luật-server"], embed=rules, pin=True)

        hello = discord.Embed(title="🌴 CHÀO MỪNG ĐẾN SERVER GTA 6",
                              description=ANNOUNCE, colour=0xE91E63)
        await post_once(channels["📢・thông-báo"], embed=hello, pin=True)
        await post_once(channels["💡・góp-ý-tưởng"], content=IDEA_GUIDE, pin=True)
        await post_once(channels["🔥・spoil-cốt-truyện"], content=SPOIL_WARN, pin=True)
        await post_once(channels["🕵️・leak-tin-đồn"], content=LEAK_WARN, pin=True)
        print("  + xong")

        # Tin nhắn "X đã tham gia" của Discord sẽ hiện ở chat-chung
        try:
            await guild.edit(system_channel=channels["💬・chat-chung"], reason=REASON)
        except discord.HTTPException:
            print("  ! Không đặt được kênh chào mừng — chỉnh tay trong Cài đặt server.")

        print("\n✅ XONG! Nhớ kéo role 🛡️ Mod lên trên các role khác "
              "và gỡ quyền Administrator của bot.")
    finally:
        await client.close()


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Chưa có DISCORD_TOKEN. Xem hướng dẫn ở đầu file.")
    client.run(TOKEN)
