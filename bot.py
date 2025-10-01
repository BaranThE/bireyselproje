import discord
from discord.ext import commands
import sqlite3
import asyncio
from config import TOKEN

# Veritabanı dosyasının adı
DB_FILE = 'tasks.db'

# Intents nesnesi oluştur
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Veritabanı bağlantısı ve tablo oluşturma
def setup_database():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            "group" TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Bot başarıyla başlatıldığında
@bot.event
async def on_ready():
    print(f'{bot.user} olarak giriş yapıldı.')
    setup_database()

# Görev eklemek için Modal (Pop-up penceresi)
class AddTaskModal(discord.ui.Modal, title="Yeni Görev Ekle"):
    group_input = discord.ui.TextInput(
        label="Grup Adı",
        placeholder="Örnek: Alışveriş, Okul, Proje...",
        required=True
    )
    task_input = discord.ui.TextInput(
        label="Görev Açıklaması",
        placeholder="Örnek: 1 kg elma al",
        style=discord.TextStyle.paragraph,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        group_name = self.group_input.value
        task_content = self.task_input.value
        user_id = str(interaction.user.id)

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO tasks (user_id, content, \"group\") VALUES (?, ?, ?)", (user_id, task_content, group_name))
        conn.commit()
        conn.close()
        
        await interaction.response.send_message(f'Görev eklendi: "{task_content}" (Grup: {group_name})', ephemeral=True)

# Sadece "Görev Ekle" butonunu içeren View sınıfı
class TaskMenuView(discord.ui.View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="Görev Ekle", style=discord.ButtonStyle.green, custom_id="add_task")
    async def add_task_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddTaskModal())

# Buton menüsü komutu
@bot.command()
async def task_menu(ctx):
    await ctx.send("Lütfen yapmak istediğiniz işlemi seçin:", view=TaskMenuView())

# Diğer komutlar
@bot.command()
async def task(ctx, action=None, *, content=None):
    user_id = str(ctx.author.id)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    if action == 'add':
        if not content:
            await ctx.send('Lütfen bir görev açıklaması sağlayın. Örnek: `!task add "Grup Adı" "Görev Açıklaması"`')
            conn.close()
            return

        parts = content.split('"', 2)
        if len(parts) >= 3 and parts[0].strip() == "" and parts[2].strip() != "":
            group_name = parts[1]
            task_content = parts[2].strip().strip('"')
            
            c.execute("INSERT INTO tasks (user_id, content, \"group\") VALUES (?, ?, ?)", (user_id, task_content, group_name))
            conn.commit()
            await ctx.send(f'Görev eklendi: "{task_content}" (Grup: {group_name})')
        else:
            await ctx.send('Geçersiz format. Lütfen şu formatı kullanın: `!task add "Grup Adı" "Görev Açıklaması"`')
        
        conn.close()

    elif action == 'remove':
        if content and content.isdigit():
            task_id = int(content)
            c.execute("SELECT id FROM tasks WHERE user_id = ? AND id = ?", (user_id, task_id))
            if c.fetchone():
                c.execute("DELETE FROM tasks WHERE user_id = ? AND id = ?", (user_id, task_id))
                conn.commit()
                await ctx.send(f'ID {task_id} olan görev kaldırıldı.')
            else:
                await ctx.send(f'ID {task_id} olan görev bulunamadı.')
        else:
            await ctx.send('Lütfen kaldırmak için geçerli bir görev ID sağlayın.')
        
        conn.close()

    elif action == 'list':
        group_filter = content
        
        if group_filter:
            c.execute("SELECT id, content FROM tasks WHERE user_id = ? AND \"group\" = ?", (user_id, group_filter))
            tasks_from_db = c.fetchall()
            if not tasks_from_db:
                await ctx.send(f"'{group_filter}' grubuna ait görev bulunamadı.")
            else:
                response = f"'{group_filter}' grubundaki görevler:\n"
                response += "\n".join([f"ID: {task[0]}, Açıklama: {task[1]}" for task in tasks_from_db])
                await ctx.send(response)
        else:
            c.execute("SELECT \"group\", id, content FROM tasks WHERE user_id = ? ORDER BY \"group\"", (user_id,))
            tasks_from_db = c.fetchall()
            
            if not tasks_from_db:
                await ctx.send("Hiç göreviniz bulunmuyor.")
            else:
                groups = {}
                for task_from_db in tasks_from_db:
                    group, task_id, task_content = task_from_db
                    if group not in groups:
                        groups[group] = []
                    groups[group].append((task_id, task_content))
                
                response = "Mevcut görevleriniz:\n"
                for group_name, group_tasks in groups.items():
                    response += f"\n**{group_name} Grubu**:\n"
                    response += "\n".join([f"ID: {task[0]}, Açıklama: {task[1]}" for task in group_tasks])
                await ctx.send(response)
        
        conn.close()
    
    else:
        await ctx.send('Bilinmeyen eylem. Lütfen `add`, `remove` veya `list` kullanın.')

@bot.command()
async def info(ctx):
    response = (
        "Mevcut komutlar:\n"
        "`!task_menu` - Buton menüsünü açar.\n"
        "`!task add \"Grup Adı\" \"Görev Açıklaması\"` - Yeni bir görev ekler.\n"
        "`!task remove [görev ID'si]` - Belirtilen ID'ye sahip görevi kaldırır.\n"
        "`!task list [isteğe bağlı grup adı]` - Mevcut görevleri veya belirli bir gruptaki görevleri listeler.\n"
        "`!info` - Bu yardım bilgilerini görüntüler."
    )
    await ctx.send(response)

bot.run(TOKEN)
