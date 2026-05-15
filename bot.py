import discord
from discord.ext import commands
import json
import os
import asyncio

# ─────────────────────────────────────────
#  CONFIGURAÇÃO
# ─────────────────────────────────────────
PREFIX = ";"
AURA_FILE = "aura.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


# ─────────────────────────────────────────
#  HELPERS — AURA
# ─────────────────────────────────────────
def load_aura() -> dict:
    if os.path.exists(AURA_FILE):
        with open(AURA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_aura(data: dict) -> None:
    with open(AURA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_aura(user_id: int) -> int:
    return load_aura().get(str(user_id), 0)


def is_admin():
    async def predicate(ctx: commands.Context):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)


# ─────────────────────────────────────────
#  GRUPO ;aura
# ─────────────────────────────────────────
@bot.group(name="aura", invoke_without_command=True)
async def aura_group(ctx: commands.Context):
    embed = discord.Embed(
        title="✨ Comandos de Aura",
        description=(
            "`;aura ver` — veja sua aura\n"
            "`;aura transferir <qtd> <@pessoa>` — transfira aura\n"
            "`;aura ranking` — top 10 do servidor\n"
            "*(Admin)* `;aura add/rem/set <@pessoa> <qtd>`"
        ),
        color=0xA78BFA,
    )
    await ctx.send(embed=embed)


# ── ;aura ver ────────────────────────────
@aura_group.command(name="ver")
async def aura_ver(ctx: commands.Context, membro: discord.Member = None):
    membro = membro or ctx.author
    quantidade = get_aura(membro.id)
    embed = discord.Embed(
        description=f"✨ **{membro.display_name}** tem **{quantidade:,}** de aura.",
        color=0xA78BFA,
    )
    embed.set_thumbnail(url=membro.display_avatar.url)
    await ctx.send(embed=embed)


# ── ;aura transferir ─────────────────────
@aura_group.command(name="transferir")
async def aura_transferir(ctx: commands.Context, quantidade: int, destino: discord.Member):
    if destino == ctx.author:
        return await ctx.send("❌ Você não pode transferir aura para si mesmo.")
    if quantidade <= 0:
        return await ctx.send("❌ A quantidade precisa ser maior que zero.")

    saldo = get_aura(ctx.author.id)
    if saldo < quantidade:
        return await ctx.send(
            f"❌ Aura insuficiente! Você tem apenas **{saldo:,}** de aura."
        )

    embed = discord.Embed(
        title="💸 Confirmar Transferência",
        description=(
            f"Enviar **{quantidade:,}** de aura para {destino.mention}?\n\n"
            "Reaja com ✅ para confirmar ou ❌ para cancelar."
        ),
        color=0xFBBF24,
    )
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

    def check(reaction, user):
        return (
            user == ctx.author
            and str(reaction.emoji) in ("✅", "❌")
            and reaction.message.id == msg.id
        )

    try:
        reaction, _ = await bot.wait_for("reaction_add", timeout=30.0, check=check)
    except asyncio.TimeoutError:
        return await ctx.send("⏰ Tempo esgotado. Transferência cancelada.")

    if str(reaction.emoji) == "❌":
        return await ctx.send("❌ Transferência cancelada.")

    data = load_aura()
    data[str(ctx.author.id)] = saldo - quantidade
    data[str(destino.id)] = data.get(str(destino.id), 0) + quantidade
    save_aura(data)

    embed_ok = discord.Embed(
        title="✅ Transferência Realizada",
        description=(
            f"{ctx.author.mention} enviou **{quantidade:,}** de aura para {destino.mention}."
        ),
        color=0x34D399,
    )
    await ctx.send(embed=embed_ok)


# ── ;aura ranking ────────────────────────
@aura_group.command(name="ranking")
async def aura_ranking(ctx: commands.Context):
    data = load_aura()
    if not data:
        return await ctx.send("Ainda não há dados de aura neste servidor.")

    top = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}

    linhas = []
    for i, (uid, valor) in enumerate(top):
        membro = ctx.guild.get_member(int(uid))
        nome = membro.display_name if membro else f"ID {uid}"
        icone = medals.get(i, f"**#{i + 1}**")
        linhas.append(f"{icone} {nome} — **{valor:,}** ✨")

    embed = discord.Embed(
        title="🏆 Ranking de Aura",
        description="\n".join(linhas),
        color=0xFFD700,
    )
    embed.set_footer(text=f"Top {len(top)} do servidor")
    await ctx.send(embed=embed)


# ── ;aura add (admin) ────────────────────
@aura_group.command(name="add")
@is_admin()
async def aura_add(ctx: commands.Context, membro: discord.Member, quantidade: int):
    data = load_aura()
    uid = str(membro.id)
    data[uid] = data.get(uid, 0) + quantidade
    save_aura(data)
    await ctx.send(
        f"✅ **+{quantidade:,}** de aura adicionado a {membro.mention}. "
        f"Total: **{data[uid]:,}** ✨"
    )


# ── ;aura rem (admin) ────────────────────
@aura_group.command(name="rem")
@is_admin()
async def aura_rem(ctx: commands.Context, membro: discord.Member, quantidade: int):
    data = load_aura()
    uid = str(membro.id)
    data[uid] = data.get(uid, 0) - quantidade
    save_aura(data)
    await ctx.send(
        f"✅ **-{quantidade:,}** de aura removido de {membro.mention}. "
        f"Total: **{data[uid]:,}** ✨"
    )


# ── ;aura set (admin) ────────────────────
@aura_group.command(name="set")
@is_admin()
async def aura_set(ctx: commands.Context, membro: discord.Member, quantidade: int):
    data = load_aura()
    uid = str(membro.id)
    data[uid] = quantidade
    save_aura(data)
    await ctx.send(
        f"✅ Aura de {membro.mention} definida para **{quantidade:,}** ✨"
    )


# ─────────────────────────────────────────
#  COMANDO ;chamar
# ─────────────────────────────────────────
class PararView(discord.ui.View):
    """View com botão de parar o loop de chamar."""

    def __init__(self, autor_id: int):
        super().__init__(timeout=60)  # auto-expira em 1 minuto pq sim
        self.parado = False
        self.autor_id = autor_id

    @discord.ui.button(label="⛔ Parar", style=discord.ButtonStyle.danger)
    async def parar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Só quem chamou (ou admin) pode parar
        if (
            interaction.user.id != self.autor_id
            and not interaction.user.guild_permissions.administrator
        ):
            return await interaction.response.send_message(
                "Só quem usou o comando pode parar.", ephemeral=True
            )
        self.parado = True
        button.disabled = True
        button.label = "Parou"
        await interaction.response.edit_message(view=self)
        self.stop()


@bot.command(name="chamar")
async def chamar(ctx: commands.Context, pessoa: discord.Member, *, mensagem: str):
    """
    ;chamar @pessoa mensagem
    Fica mandando e apagando a mensagem para chamar a atenção.
    Pressione o botão para parar.
    """
    # Apaga a mensagem original para não poluir o chat
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    view = PararView(autor_id=ctx.author.id)
    conteudo = f"📣 {pessoa.mention} — {mensagem}"

    msg = await ctx.send(conteudo, view=view)

    # Loop: apaga e reenvia para re-pingar (Discord só pinga em mensagem nova)
    for _ in range(30):  # máximo de 15 ciclos (~30 s)
        if view.parado or view.is_finished():
            break
        await asyncio.sleep(0.5)
        if view.parado or view.is_finished():
            break
        try:
            await msg.delete()
        except (discord.NotFound, discord.Forbidden):
            break
        msg = await ctx.send(conteudo, view=view)

    # Mensagem final
    if not view.parado:
        try:
            await msg.edit(
                content=f"✅ {pessoa.mention} foi chamado por {ctx.author.mention}!",
                view=None,
            )
        except discord.NotFound:
            pass


# ─────────────────────────────────────────
#  ERROS GLOBAIS
# ─────────────────────────────────────────
@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argumento faltando: `{error.param.name}`")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Membro não encontrado.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Argumento inválido.")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Você não tem permissão para usar esse comando.")
    else:
        raise error


# ─────────────────────────────────────────
#  START
# ─────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ Bot online como {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, name=";aura | ;chamar"
        )
    )


bot.run(os.environ["DISCORD_TOKEN"])
