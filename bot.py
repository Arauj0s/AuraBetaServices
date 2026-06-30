import discord
from discord.ext import commands
import json, os, asyncio, time, re

from flask import Flask
from threading import Thread

# ─── Flask keep-alive ──────────────────────────────────────────────
app = Flask('')

@app.route('/')
def home():
    return "um aurudo esteve aqui"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run).start()

# ─── Config ────────────────────────────────────────────────────────
PREFIX       = ";"
ReisReis_FILE = "ReisReis.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


# ══════════════════════════════════════════════════════════════════
#  ReisReis
# ══════════════════════════════════════════════════════════════════
def load_ReisReis() -> dict:
    if os.path.exists(ReisReis_FILE):
        with open(ReisReis_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_ReisReis(data: dict) -> None:
    with open(ReisReis_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_ReisReis(user_id: int) -> int:
    return load_ReisReis().get(str(user_id), 0)

def is_admin():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

@bot.group(name="ReisReis", invoke_without_command=True)
async def ReisReis_group(ctx):
    await ctx.send(embed=discord.Embed(
        title="✨ Comandos de ReisReis",
        description=(
            "`;ReisReis ver [@pessoa]`\n"
            "`;ReisReis transferir <qtd> <@pessoa>`\n"
            "`;ReisReis ranking`\n"
            "*(Admin)* `;ReisReis add/rem/set <@pessoa> <qtd>`"
        ),
        color=0xA78BFA,
    ))

@ReisReis_group.command(name="ver")
async def ReisReis_ver(ctx, membro: discord.Member = None):
    m = membro or ctx.author
    e = discord.Embed(
        description=f"✨ **{m.display_name}** tem **{get_ReisReis(m.id):,}** de ReisReis.",
        color=0xA78BFA,
    )
    e.set_thumbnail(url=m.display_avatar.url)
    await ctx.send(embed=e)

@ReisReis_group.command(name="transferir")
async def ReisReis_transferir(ctx, qtd: int, dest: discord.Member):
    if dest == ctx.author:
        return await ctx.send("❌ Não pode transferir para si mesmo.")
    if qtd <= 0:
        return await ctx.send("❌ Quantidade inválida.")
    saldo = get_ReisReis(ctx.author.id)
    if saldo < qtd:
        return await ctx.send(f"❌ Saldo insuficiente (**{saldo:,}** ReisReis).")
    msg = await ctx.send(embed=discord.Embed(
        title="💸 Confirmar Transferência",
        description=f"Enviar **{qtd:,}** ✨ para {dest.mention}?\n✅ confirmar  |  ❌ cancelar",
        color=0xFBBF24,
    ))
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    def chk(r, u):
        return u == ctx.author and str(r.emoji) in ("✅","❌") and r.message.id == msg.id
    try:
        r, _ = await bot.wait_for("reaction_add", timeout=30.0, check=chk)
    except asyncio.TimeoutError:
        return await ctx.send("⏰ Tempo esgotado.")
    if str(r.emoji) == "❌":
        return await ctx.send("❌ Cancelado.")
    data = load_ReisReis()
    data[str(ctx.author.id)] = saldo - qtd
    data[str(dest.id)] = data.get(str(dest.id), 0) + qtd
    save_ReisReis(data)
    await ctx.send(embed=discord.Embed(
        title="✅ Transferência Realizada",
        description=f"{ctx.author.mention} → {dest.mention}: **{qtd:,}** ✨",
        color=0x34D399,
    ))

@ReisReis_group.command(name="ranking")
async def ReisReis_ranking(ctx):
    data = load_ReisReis()
    if not data:
        return await ctx.send("Sem dados de ReisReis ainda.")
    top = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
    medals = {0:"🥇",1:"🥈",2:"🥉"}
    linhas = []
    for i,(uid,v) in enumerate(top):
        m = ctx.guild.get_member(int(uid))
        nome = m.display_name if m else f"ID {uid}"
        linhas.append(f"{medals.get(i,f'**#{i+1}**')} {nome} — **{v:,}** ✨")
    await ctx.send(embed=discord.Embed(title="🏆 Ranking de ReisReis",
        description="\n".join(linhas), color=0xFFD700))

@ReisReis_group.command(name="add")
@is_admin()
async def ReisReis_add(ctx, m: discord.Member, qtd: int):
    data = load_ReisReis(); uid = str(m.id)
    data[uid] = data.get(uid, 0) + qtd; save_ReisReis(data)
    await ctx.send(f"✅ **+{qtd:,}** → {m.mention} | Total: **{data[uid]:,}** ✨")

@ReisReis_group.command(name="rem")
@is_admin()
async def ReisReis_rem(ctx, m: discord.Member, qtd: int):
    data = load_ReisReis(); uid = str(m.id)
    data[uid] = data.get(uid, 0) - qtd; save_ReisReis(data)
    await ctx.send(f"✅ **-{qtd:,}** → {m.mention} | Total: **{data[uid]:,}** ✨")

@ReisReis_group.command(name="set")
@is_admin()
async def ReisReis_set(ctx, m: discord.Member, qtd: int):
    data = load_ReisReis(); uid = str(m.id)
    data[uid] = qtd; save_ReisReis(data)
    await ctx.send(f"✅ ReisReis de {m.mention} definida para **{qtd:,}** ✨")


# ══════════════════════════════════════════════════════════════════
#  BATATA — estado global
# ══════════════════════════════════════════════════════════════════
_batatas: dict[int, dict[int, dict]] = {}
_sr:      dict[int, dict]            = {}
_mogando: dict[int, int]             = {}

BATATA_DURACAO = 20.0
_CONTERABLE    = {"normal","sr","raivosa","inglesa"}
_COUNTER_DE    = {"normal":"frita","sr":"frita","raivosa":"frita","inglesa":"doce"}

def _get_batata(gid: int, uid: int) -> dict | None:
    b = _batatas.get(gid, {}).get(uid)
    if b is None: return None
    if time.time() >= b["expires"]:
        _batatas[gid].pop(uid, None); return None
    return b

def _set_batata(gid: int, uid: int, tipo: str, caster_id: int, expires: float, **extra):
    _batatas.setdefault(gid, {})[uid] = {
        "type": tipo, "expires": expires,
        "caster": caster_id, "cast_time": time.time(), **extra,
    }

def _clear_batata(gid: int, uid: int):
    _batatas.get(gid, {}).pop(uid, None)


# ══════════════════════════════════════════════════════════════════
#  PIXEL FONT 5×5
#  FIX: dois passes para evitar que sombra de uma letra cubra a próxima.
#       Suporte a emoji único (sem sombra).
# ══════════════════════════════════════════════════════════════════
_FONT: dict[str, list[str]] = {
    "A":["01110","10001","11111","10001","10001"],
    "B":["11110","10001","11110","10001","11110"],
    "C":["01110","10000","10000","10000","01110"],
    "D":["11100","10010","10001","10010","11100"],
    "E":["11111","10000","11110","10000","11111"],
    "F":["11111","10000","11100","10000","10000"],
    "G":["01110","10000","10111","10001","01111"],
    "H":["10001","10001","11111","10001","10001"],
    "I":["01110","00100","00100","00100","01110"],
    "J":["00111","00010","00010","10010","01100"],
    "K":["10010","10100","11000","10100","10010"],
    "L":["10000","10000","10000","10000","11111"],
    "M":["10001","11011","10101","10001","10001"],
    "N":["10001","11001","10101","10011","10001"],
    "O":["01110","10001","10001","10001","01110"],
    "P":["11110","10001","11110","10000","10000"],
    "Q":["01110","10001","10101","10010","01101"],
    "R":["11110","10001","11110","10010","10001"],
    "S":["01111","10000","01110","00001","11110"],
    "T":["11111","00100","00100","00100","00100"],
    "U":["10001","10001","10001","10001","01110"],
    "V":["10001","10001","10001","01010","00100"],
    "W":["10001","10001","10101","11011","10001"],
    "X":["10001","01010","00100","01010","10001"],
    "Y":["10001","01010","00100","00100","00100"],
    "Z":["11111","00010","00100","01000","11111"],
    "0":["01110","10011","10101","11001","01110"],
    "1":["00100","01100","00100","00100","11111"],
    "2":["01110","10001","00110","01000","11111"],
    "3":["11110","00001","00110","00001","11110"],
    "4":["00110","01010","10010","11111","00010"],
    "5":["11111","10000","11110","00001","11110"],
    "6":["01110","10000","11110","10001","01110"],
    "7":["11111","00001","00010","00100","01000"],
    "8":["01110","10001","01110","10001","01110"],
    "9":["01110","10001","01111","00001","01110"],
    "!":["00100","00100","00100","00000","00100"],
    "?":["01110","10001","00110","00000","00100"],
    " ":["00000","00000","00000","00000","00000"],
}

_BLANK = "\u2800"   # Braille blank — ocupa espaço mas não aparece visualmente

def render_face(text: str, emoji_frente: str, emoji_sombra: str | None = None) -> str:
    """
    Renderiza texto em pixel-art 5×5.
    - Se emoji_sombra for None ou igual a emoji_frente → modo flat (sem efeito 3D).
    - Fix: dois passes garantem que sombra nunca sobrescreve frente de outra letra.
    """
    text  = text.upper()
    H, W, GAP = 5, 5, 1
    chars = [c if c in _FONT else " " for c in text]
    rows  = H + 1
    cols  = len(chars) * (W + GAP) + 1

    # grade começa vazia
    grid: list[list[str]] = [["" for _ in range(cols)] for _ in range(rows)]

    # ── PASSO 1: marca todas as posições "F" (frente) ──────────────
    for ci, ch in enumerate(chars):
        pat = _FONT[ch]
        cs  = ci * (W + GAP)
        for r in range(H):
            for c in range(W):
                if pat[r][c] == "1":
                    grid[r][cs + c] = "F"

    # ── PASSO 2: marca sombras APENAS onde não há "F" ──────────────
    if emoji_sombra and emoji_sombra != emoji_frente:
        for ci, ch in enumerate(chars):
            pat = _FONT[ch]
            cs  = ci * (W + GAP)
            for r in range(H):
                for c in range(W):
                    if pat[r][c] == "1":
                        sr2, sc = r + 1, cs + c + 1
                        if sr2 < rows and sc < cols and grid[sr2][sc] == "":
                            grid[sr2][sc] = "S"

    # ── Renderiza ──────────────────────────────────────────────────
    return "\n".join(
        "".join(
            emoji_frente if cell == "F"
            else (emoji_sombra if cell == "S" else _BLANK)
            for cell in row
        )
        for row in grid
    )


# ══════════════════════════════════════════════════════════════════
#  ;chamar
#  NOVO: mensagem de ping fica no canal (pinga o alvo de verdade).
#        Botão "Parar" é enviado por DM ao autor — só ele vê.
#        Se DM estiver bloqueada, cai de volta para mensagem normal no canal.
# ══════════════════════════════════════════════════════════════════
class PararView(discord.ui.View):
    """Botão de parar enviado por DM ao autor do ;chamar."""

    def __init__(self, autor_id: int, ping_msg_ref: list):
        # ping_msg_ref é uma lista mutável [msg] para podermos atualizar a ref do loop
        super().__init__(timeout=120)
        self.parado       = False
        self.autor_id     = autor_id
        self.ping_msg_ref = ping_msg_ref

    @discord.ui.button(label="⛔ Parar", style=discord.ButtonStyle.danger)
    async def parar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.autor_id:
            return await interaction.response.send_message(
                "Só quem usou o comando pode parar.", ephemeral=True)
        self.parado     = True
        button.disabled = True
        button.label    = "✅ Parado"
        await interaction.response.edit_message(view=self)

        # Edita a última mensagem de ping no canal para indicar encerramento
        ping_msg = self.ping_msg_ref[0] if self.ping_msg_ref else None
        if ping_msg:
            try:
                await ping_msg.edit(content="*(chamado encerrado)*", view=None)
            except (discord.NotFound, discord.Forbidden):
                pass
        self.stop()


@bot.command(name="chamar")
async def chamar(ctx: commands.Context, pessoa: discord.Member, *args):
    """
    ;chamar @pessoa [mensagem] [tempo_em_segundos]

    A mensagem de ping fica no canal (pinga a pessoa de verdade).
    O botão ⛔ Parar é enviado no privado do autor — só ele vê.
    Se DM estiver bloqueada, o botão aparece no canal mesmo.
    """
    # ── Extrai tempo opcional (último arg numérico) ─────────────────
    tempo          = 0.5
    mensagem_parts = list(args)

    if mensagem_parts:
        try:
            tempo          = float(mensagem_parts[-1])
            mensagem_parts = mensagem_parts[:-1]
        except ValueError:
            pass

    tempo    = max(0.1, min(tempo, 10.0))
    max_iter = max(1, int(30 / tempo))

    conteudo = (
        f"📣 {pessoa.mention} — {' '.join(mensagem_parts)}"
        if mensagem_parts
        else f"📣 ooh {pessoa.mention}, esse tal de {ctx.author.mention} ta chamando ae"
    )

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    # Começa o ping no canal
    ping_msg_ref: list = [None]
    ping_msg     = await ctx.send(conteudo)
    ping_msg_ref[0] = ping_msg

    # Tenta mandar o botão por DM
    view       = PararView(ctx.author.id, ping_msg_ref)
    dm_enviada = False
    try:
        dm_msg = await ctx.author.send(
            f"🔔 Você está chamando **{pessoa.display_name}**. Clique para parar:",
            view=view,
        )
        dm_enviada = True
    except discord.Forbidden:
        # DM bloqueada → botão aparece no canal
        ctrl_msg = await ctx.send(
            f"*(botão de controle — só {ctx.author.mention} pode parar)*",
            view=view,
        )

    # Loop de ping
    for _ in range(max_iter):
        if view.parado or view.is_finished():
            break
        await asyncio.sleep(tempo)
        if view.parado or view.is_finished():
            break
        try:
            await ping_msg.delete()
        except (discord.NotFound, discord.Forbidden):
            break
        ping_msg          = await ctx.send(conteudo)
        ping_msg_ref[0]   = ping_msg

    # Encerramento natural (tempo esgotado, botão não foi pressionado)
    if not view.parado:
        view.stop()
        try:
            await ping_msg.edit(
                content=f"✅ {pessoa.mention} foi chamado por {ctx.author.mention}!",
            )
        except discord.NotFound:
            pass
        if dm_enviada:
            try:
                await dm_msg.edit(content="✅ Chamado encerrado (tempo esgotado).", view=None)
            except discord.NotFound:
                pass


# ══════════════════════════════════════════════════════════════════
#  ;texto — pixel-art 3D com rotação e modo ephemeral/normal
#  Suporte a emoji único: ;texto CONTEUDO 🗿 [n]
# ══════════════════════════════════════════════════════════════════
class TextoView(discord.ui.View):
    def __init__(self, autor_id: int, faces: list[str]):
        super().__init__(timeout=300)
        self.autor_id = autor_id
        self.faces    = faces
        self.idx      = 0
        # Se só tem uma face (emoji único) desabilita as setas
        if len(faces) == 1:
            self.children[0].disabled = True   # ◀
            self.children[2].disabled = True   # ▶

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def esquerda(self, interaction: discord.Interaction, _btn):
        self.idx = (self.idx - 1) % len(self.faces)
        await interaction.response.edit_message(content=self.faces[self.idx], view=self)

    @discord.ui.button(label="⏹ Parar Exibição", style=discord.ButtonStyle.danger)
    async def parar_exibicao(self, interaction: discord.Interaction, _btn):
        if (interaction.user.id != self.autor_id
                and not interaction.user.guild_permissions.administrator):
            return await interaction.response.send_message(
                "Só quem usou pode parar.", ephemeral=True)
        for child in self.children:
            child.disabled = True
        _btn.label = "✅ Encerrado"
        await interaction.response.edit_message(content="*(exibição encerrada)*", view=self)
        self.stop()

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def direita(self, interaction: discord.Interaction, _btn):
        self.idx = (self.idx + 1) % len(self.faces)
        await interaction.response.edit_message(content=self.faces[self.idx], view=self)


@bot.command(name="texto")
async def texto_cmd(ctx: commands.Context, *, args: str):
    """
    ;texto CONTEUDO emoji1[,emoji2] [n]

    Com dois emojis → efeito 3D (sombra).
    Com um emoji   → flat (sem sombra, sem setas de giro).
    Sem 'n'        → envia no privado (só você vê).
    Com 'n'        → posta no canal.

    Exemplos:
      ;texto OI 🗿,✂️        → 3D no privado
      ;texto OI 🗿,✂️ n      → 3D no canal
      ;texto OI 🗿            → flat no privado
      ;texto OI 🗿 n          → flat no canal
    """
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    parts  = args.split()
    normal = False

    if parts and parts[-1].lower() == "n":
        normal = True
        parts  = parts[:-1]

    if not parts:
        return await ctx.send("❌ Uso: `;texto CONTEUDO emoji[,emoji2] [n]`", delete_after=7)

    # ── Detecta o token de emoji (último que contém emoji ou vírgula) ──
    # Estratégia: o último token que NÃO seja puro texto ASCII é o emoji
    emoji_idx = None
    for i in range(len(parts) - 1, -1, -1):
        tok = parts[i]
        # contém vírgula → par de emojis
        if "," in tok:
            emoji_idx = i
            break
        # contém caracter não-ASCII ou é emoji Unicode → emoji único
        if any(ord(c) > 127 for c in tok):
            emoji_idx = i
            break

    if emoji_idx is None:
        return await ctx.send(
            "❌ Forneça pelo menos um emoji.\n"
            "Exemplos: `;texto OI 🗿` ou `;texto OI 🗿,✂️`",
            delete_after=8)

    emoji_str = parts[emoji_idx]
    conteudo  = " ".join(parts[:emoji_idx]).strip()

    if not conteudo:
        return await ctx.send("❌ Conteúdo vazio.", delete_after=5)

    # ── Separa emojis ──────────────────────────────────────────────
    if "," in emoji_str:
        ep = emoji_str.split(",", 1)
        e1, e2 = ep[0].strip(), ep[1].strip()
        if not e1 or not e2:
            return await ctx.send("❌ Os dois emojis precisam estar preenchidos.", delete_after=5)
        face_a = render_face(conteudo, e1, e2)
        face_b = render_face(conteudo, e2, e1)
        faces  = [face_a, face_b]
    else:
        e1    = emoji_str.strip()
        faces = [render_face(conteudo, e1)]   # flat, sem sombra

    if any(len(f) > 2000 for f in faces):
        return await ctx.send("❌ Texto muito longo! Use menos caracteres.", delete_after=5)

    view = TextoView(ctx.author.id, faces)

    if normal:
        await ctx.send(faces[0], view=view)
    else:
        try:
            await ctx.author.send(faces[0], view=view)
            await ctx.send(f"📨 {ctx.author.mention} te mandei no privado!", delete_after=5)
        except discord.Forbidden:
            hint = f"`n`" 
            await ctx.send(
                f"❌ Não consigo te enviar DM. Adicione {hint} no final para postar no canal.",
                delete_after=8)


# ══════════════════════════════════════════════════════════════════
#  ;clone  — 1/minuto, via webhook
# ══════════════════════════════════════════════════════════════════
_clone_cd: dict[int, float] = {}

@bot.command(name="clone")
async def clone_cmd(ctx: commands.Context, *, args: str):
    """
    ;clone MENSAGEM @pessoa
    Envia a mensagem como se fosse a pessoa marcada (1 vez por minuto).
    """
    uid   = ctx.author.id
    agora = time.time()
    restante = 60 - (agora - _clone_cd.get(uid, 0))
    if restante > 0:
        return await ctx.send(
            f"⏳ Aguarde **{int(restante) + 1}s** para usar `;clone` novamente.",
            delete_after=5)

    mencoes = re.findall(r"<@!?(\d+)>", args)
    if not mencoes:
        return await ctx.send("❌ Uso: `;clone MENSAGEM @pessoa`", delete_after=5)

    alvo = ctx.guild.get_member(int(mencoes[-1]))
    if not alvo:
        return await ctx.send("❌ Membro não encontrado.", delete_after=5)

    mensagem = re.sub(r"<@!?\d+>", "", args).strip()
    if not mensagem:
        return await ctx.send("❌ Mensagem vazia.", delete_after=5)

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    try:
        webhooks = await ctx.channel.webhooks()
        hook     = next((w for w in webhooks if w.user == bot.user), None)
        if not hook:
            hook = await ctx.channel.create_webhook(name="CloneBot 🥔")
    except discord.Forbidden:
        return await ctx.send(
            "❌ Sem permissão para gerenciar webhooks neste canal.", delete_after=5)

    _clone_cd[uid] = agora
    await hook.send(mensagem, username=alvo.display_name, avatar_url=alvo.display_avatar.url)


# ══════════════════════════════════════════════════════════════════
#  ;batata  — sem args: exibe help com todos os tipos
# ══════════════════════════════════════════════════════════════════
class ContestoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="Contesto", style=discord.ButtonStyle.secondary, emoji="🥔")
    async def contesto(self, interaction: discord.Interaction, _btn):
        try:
            await interaction.message.delete()
        except (discord.NotFound, discord.Forbidden):
            await interaction.response.send_message("Não consegui apagar.", ephemeral=True)


_BATATA_TIPOS = {
    "normal","gulosa","inglesa","doce",
    "frita","purê","pure","sr","raivosa","mogadora",
}

_BATATA_ANUNCIO = {
    "normal":   "🥔 **Batata Normal** em {alvo}",
    "gulosa":   "🥔 **Batata Gulosa** em {alvo}",
    "inglesa":  "🥔 **English Potato (Batata Inglesa)** em {alvo}",
    "doce":     "🥔 **Batata Doce** em {alvo}",
    "frita":    "🥔 **Batata Frita** em {alvo}",
    "purê":     "🥔 **Purê de Batata** em {alvo}",
    "sr":       "🥔 **Sr. Batata** em {alvo}",
    "raivosa":  "🥔 **Batata Raivosa** em {alvo}",
    "mogadora": "🥔 **Batata Mogadora** em {alvo}",
}

_BATATA_HELP = discord.Embed(
    title="🥔 Tipos de Batata",
    description="**Uso:** `;batata [tipo] @[pessoa]`",
    color=0xD97706,
).add_field(
    name="Batatas counteraveis por outras.",
    value=(
        "🥔 **Normal** — deleta a próxima mensagem do alvo\n"
        ":flag_us: **English** — forces the user to speak English (context button)\n"
        "😡 **Raivosa** — alvo tem 10s pra falar ou msgs dele são deletadas\n"
        "🎩 **Sr** — ninguém fala no canal até o alvo falar (ou 20s)"
    ),
    inline=False,
).add_field(
    name="Batatas que não podem ser counteraveis.",
    value=(
        "🍽️ **Gulosa** — 🥔 + no counters = gulosa\n"
        "🥣 **Purê** — não grita\n"
        "🗿 **Mogadora** — moga se o beta falar"
    ),
    inline=False,
).add_field(
    name="Counters de Batatas",
    value=(
        "🍟 **Frita** — cancela: normal, raivosa, sr\n"
        "🍠 **Doce** — cancela: inglesa"
    ),
    inline=False,

).set_footer(text="Servidor Aurudo")


@bot.command(name="batata")
async def batata_cmd(ctx: commands.Context, tipo: str = None, alvo: discord.Member = None):
    # ── Sem args → help ────────────────────────────────────────────
    if tipo is None:
        return await ctx.send(embed=_BATATA_HELP)

    tipo = tipo.lower()
    if tipo == "pure":
        tipo = "purê"

    if tipo not in (_BATATA_TIPOS - {"pure"}):
        return await ctx.send(
            "❌ Tipo inválido! Use `;batata` para ver todos os tipos.")

    if alvo is None:
        return await ctx.send(f"❌ Uso: `;batata {tipo} @pessoa`")

    gid = ctx.guild.id
    uid = alvo.id

    if tipo == "mogadora" and gid in _mogando:
        mogado = ctx.guild.get_member(_mogando[gid])
        nome   = mogado.mention if mogado else "alguém"
        return await ctx.send(f"🥔 Já tem uma batata mogando {nome} neste servidor!")

    anuncio = _BATATA_ANUNCIO[tipo].format(alvo=alvo.mention)

    # ── Batatas contráveis → delay de 2s ──────────────────────────
    if tipo in _CONTERABLE:
        ts = int(time.time() + 2)
        await ctx.send(f"{anuncio}\n*Executando em 2 segundos. <t:{ts}:R>*")
        await asyncio.sleep(2)
        counter     = _COUNTER_DE[tipo]
        b_existente = _get_batata(gid, uid)
        if b_existente and b_existente["type"] == counter:
            return await ctx.send(
                f"🛡️ A **batata {tipo}** em {alvo.mention} foi mogada brutalmente "
                f"pela **batata {counter}**!"
            )
    else:
        await ctx.send(anuncio)

    expires = time.time() + BATATA_DURACAO

    if tipo == "sr":
        _sr[gid] = {"target": uid, "caster": ctx.author.id, "expires": expires}

        async def _sr_expire():
            await asyncio.sleep(BATATA_DURACAO)
            s = _sr.get(gid)
            if s and s["target"] == uid:
                _sr.pop(gid, None)
                try:
                    await ctx.channel.send(
                        f"Podem falar, {alvo.mention} não é mais protagonista.",
                        delete_after=5)
                except Exception:
                    pass
        asyncio.create_task(_sr_expire())

    elif tipo == "mogadora":
        _mogando[gid] = uid
        _set_batata(gid, uid, "mogadora", ctx.author.id, expires)

        async def _mog_expire():
            await asyncio.sleep(BATATA_DURACAO)
            if _mogando.get(gid) == uid:
                _mogando.pop(gid, None)
                _clear_batata(gid, uid)
                try:
                    await ctx.channel.send(
                        f"🥔 A **Batata Mogadora** de {alvo.mention} acabou.",
                        delete_after=5)
                except Exception:
                    pass
        asyncio.create_task(_mog_expire())

    elif tipo == "raivosa":
        _set_batata(gid, uid, "raivosa", ctx.author.id, expires)

        async def _raivosa_expire():
            await asyncio.sleep(BATATA_DURACAO)
            _clear_batata(gid, uid)
        asyncio.create_task(_raivosa_expire())

    else:
        _set_batata(gid, uid, tipo, ctx.author.id, expires)

        async def _expire():
            await asyncio.sleep(BATATA_DURACAO)
            _clear_batata(gid, uid)
        asyncio.create_task(_expire())


# ══════════════════════════════════════════════════════════════════
#  on_message — lógica das batatas
# ══════════════════════════════════════════════════════════════════
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    gid    = message.guild.id
    uid    = message.author.id
    is_cmd = message.content.startswith(PREFIX)

    # ── MOGADORA ───────────────────────────────────────────────────
    if _mogando.get(gid) == uid:
        try:
            await message.channel.send("⚠️ **BETA** DETECTADO!")
        except discord.Forbidden:
            pass

    # ── SR ─────────────────────────────────────────────────────────
    sr = _sr.get(gid)
    if sr:
        if time.time() >= sr["expires"]:
            _sr.pop(gid, None)
        elif uid == sr["target"]:
            _sr.pop(gid, None)
            try:
                await message.channel.send(
                    f"🥔 {message.author.mention} falou! Pratogonismo acabou para os betas.",
                    delete_after=5)
            except discord.Forbidden:
                pass
        else:
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass
            if is_cmd:
                await bot.process_commands(message)
            return

    # ── OUTRAS BATATAS ─────────────────────────────────────────────
    if not is_cmd:
        b = _get_batata(gid, uid)
        if b:
            tipo = b["type"]

            if tipo in ("normal", "gulosa"):
                if not b.get("first_deleted"):
                    b["first_deleted"] = True
                    try:
                        await message.delete()
                    except (discord.Forbidden, discord.NotFound):
                        pass
                    _clear_batata(gid, uid)
                    return

            elif tipo == "inglesa":
                conteudo = message.content
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound):
                    pass
                try:
                    await message.channel.send(
                        f"🥔 *{message.author.mention}* deve falar in English please\n"
                        f"> {conteudo}",
                        view=ContestoView())
                except discord.Forbidden:
                    pass
                return

            elif tipo == "purê":
                if any(c.isupper() for c in message.content):
                    try:
                        await message.delete()
                    except (discord.Forbidden, discord.NotFound):
                        pass
                    try:
                        await message.channel.send(
                            f"🥔 {message.author.mention} não pode gritar (caps lock)",
                            delete_after=4)
                    except discord.Forbidden:
                        pass
                    return

            elif tipo == "raivosa":
                deadline = b["cast_time"] + 10.0
                if not b.get("spoke"):
                    if time.time() <= deadline:
                        b["spoke"] = True
                        _clear_batata(gid, uid)
                    else:
                        try:
                            await message.delete()
                        except (discord.Forbidden, discord.NotFound):
                            pass
                        return

    await bot.process_commands(message)


# ══════════════════════════════════════════════════════════════════
#  ERROS GLOBAIS
# ══════════════════════════════════════════════════════════════════
@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Erro: faltou um tal de `{error.param.name}`")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("Erro: N/H o betinha marcado")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Erro: Batata")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("Erro: Necessita de muitos reis reis para executar este comando")
    else:
        raise error


# ══════════════════════════════════════════════════════════════════
#  START
# ══════════════════════════════════════════════════════════════════
@bot.event
async def on_ready():
    print("congratulations, funcionou")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="Bot Aurudo",
    ))

keep_alive()
bot.run(os.environ["DISCORD_TOKEN"])
