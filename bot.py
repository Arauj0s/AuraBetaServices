import discord
from discord.ext import commands
import json
import os
import asyncio
import time

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
#  ESTADO — BATATA
# ─────────────────────────────────────────
# guild_id -> user_id -> {type, expires, caster, cast_time, ...extras}
_batatas: dict[int, dict[int, dict]] = {}

# guild_id -> {target: user_id, caster: user_id, expires: float}
_sr: dict[int, dict] = {}

# guild_id -> user_id  (quem está sendo mogado; só um por servidor)
_mogando: dict[int, int] = {}

BATATA_DURACAO = 20.0

_CONTERABLE = {"normal", "sr", "raivosa", "inglesa"}
_COUNTER_DE  = {"normal": "frita", "sr": "frita", "raivosa": "frita", "inglesa": "doce"}


def _get_batata(gid: int, uid: int) -> dict | None:
    b = _batatas.get(gid, {}).get(uid)
    if b is None:
        return None
    if time.time() >= b["expires"]:
        _batatas[gid].pop(uid, None)
        return None
    return b


def _set_batata(gid: int, uid: int, tipo: str, caster_id: int, expires: float, **extra):
    _batatas.setdefault(gid, {})[uid] = {
        "type": tipo,
        "expires": expires,
        "caster": caster_id,
        "cast_time": time.time(),
        **extra,
    }


def _clear_batata(gid: int, uid: int):
    _batatas.get(gid, {}).pop(uid, None)


# ─────────────────────────────────────────
#  PIXEL FONT 5×5  (uppercase + números + ! ?)
# ─────────────────────────────────────────
_FONT: dict[str, list[str]] = {
    "A": ["01110","10001","11111","10001","10001"],
    "B": ["11110","10001","11110","10001","11110"],
    "C": ["01110","10001","10000","10001","01110"],
    "D": ["11100","10010","10001","10010","11100"],
    "E": ["11111","10000","11110","10000","11111"],
    "F": ["11111","10000","11110","10000","10000"],
    "G": ["01110","10000","10111","10001","01111"],
    "H": ["10001","10001","11111","10001","10001"],
    "I": ["11111","00100","00100","00100","11111"],
    "J": ["00111","00010","00010","10010","01100"],
    "K": ["10010","10100","11000","10100","10010"],
    "L": ["10000","10000","10000","10000","11111"],
    "M": ["10001","11011","10101","10001","10001"],
    "N": ["10001","11001","10101","10011","10001"],
    "O": ["01110","10001","10001","10001","01110"],
    "P": ["11110","10001","11110","10000","10000"],
    "Q": ["01110","10001","10101","10010","01101"],
    "R": ["11110","10001","11110","10010","10001"],
    "S": ["01111","10000","01110","00001","11110"],
    "T": ["11111","00100","00100","00100","00100"],
    "U": ["10001","10001","10001","10001","01110"],
    "V": ["10001","10001","10001","01010","00100"],
    "W": ["10001","10001","10101","11011","10001"],
    "X": ["10001","01010","00100","01010","10001"],
    "Y": ["10001","01010","00100","00100","00100"],
    "Z": ["11111","00010","00100","01000","11111"],
    "0": ["01110","10011","10101","11001","01110"],
    "1": ["00100","01100","00100","00100","01110"],
    "2": ["01110","10001","00110","01000","11111"],
    "3": ["11110","00001","00110","00001","11110"],
    "4": ["00110","01010","10010","11111","00010"],
    "5": ["11111","10000","11110","00001","11110"],
    "6": ["01110","10000","11110","10001","01110"],
    "7": ["11111","00001","00010","00100","01000"],
    "8": ["01110","10001","01110","10001","01110"],
    "9": ["01110","10001","01111","00001","01110"],
    "!": ["00100","00100","00100","00000","00100"],
    "?": ["01110","10001","00110","00000","00100"],
    " ": ["00000","00000","00000","00000","00000"],
}

# Braille blank — visualmente invisível mas mantém largura de emoji
_BLANK = "\u2800"


def render_texto(text: str, e1: str, e2: str) -> str:
    """
    Renderiza 'text' em pixel-art "3D":
      e1 = emoji da frente (face principal)
      e2 = emoji da sombra (deslocado 1px para baixo-direita)
    """
    text = text.upper()
    H, W, GAP = 5, 5, 1
    chars = [c if c in _FONT else " " for c in text]
    rows  = H + 1                          # +1 para a sombra extravasar
    cols  = len(chars) * (W + GAP) + 1     # +1 para sombra à direita

    grid: list[list[str]] = [["" for _ in range(cols)] for _ in range(rows)]

    for ci, ch in enumerate(chars):
        pat = _FONT[ch]
        cs  = ci * (W + GAP)
        for r in range(H):
            for c in range(W):
                if pat[r][c] == "1":
                    grid[r][cs + c] = "F"           # frente
                    sr2, sc = r + 1, cs + c + 1
                    if sr2 < rows and sc < cols and grid[sr2][sc] != "F":
                        grid[sr2][sc] = "S"         # sombra

    return "\n".join(
        "".join(e1 if cell == "F" else e2 if cell == "S" else _BLANK for cell in row)
        for row in grid
    )


# ─────────────────────────────────────────
#  COMANDO ;chamar  (atualizado)
# ─────────────────────────────────────────
class PararView(discord.ui.View):
    """Botão de parar o loop de ;chamar."""

    def __init__(self, autor_id: int):
        super().__init__(timeout=120)
        self.parado   = False
        self.autor_id = autor_id

    @discord.ui.button(label="⛔ Parar", style=discord.ButtonStyle.danger)
    async def parar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if (
            interaction.user.id != self.autor_id
            and not interaction.user.guild_permissions.administrator
        ):
            return await interaction.response.send_message(
                "Só quem usou o comando pode parar.", ephemeral=True
            )
        self.parado     = True
        button.disabled = True
        button.label    = "✅ Parado"
        try:
            await interaction.response.edit_message(view=self)
        except discord.NotFound:
            pass  # mensagem já deletada no loop; tudo bem
        self.stop()


@bot.command(name="chamar")
async def chamar(ctx: commands.Context, pessoa: discord.Member, *, mensagem: str):
    """
    ;chamar @pessoa mensagem
    Fica mandando e apagando a mensagem (a cada 0,5s) para chamar atenção.
    Ao parar: a última mensagem fica intacta; nada mais é apagado ou criado.
    """
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    view     = PararView(autor_id=ctx.author.id)
    conteudo = f"📣 {pessoa.mention} — {mensagem}"
    msg      = await ctx.send(conteudo, view=view)

    # 60 ciclos × 0,5s ≈ 30s no máximo
    for _ in range(60):
        if view.parado or view.is_finished():
            break
        await asyncio.sleep(0.5)
        if view.parado or view.is_finished():
            break  # ← checa ANTES de apagar: garante que a msg "✅ Parado" fica
        try:
            await msg.delete()
        except (discord.NotFound, discord.Forbidden):
            break
        msg = await ctx.send(conteudo, view=view)

    # Encerramento natural (tempo esgotado)
    if not view.parado:
        try:
            await msg.edit(
                content=f"✅ {pessoa.mention} foi chamado por {ctx.author.mention}!",
                view=None,
            )
        except discord.NotFound:
            pass


# ─────────────────────────────────────────
#  COMANDO ;texto
# ─────────────────────────────────────────
class TextoView(discord.ui.View):
    """
    Botão 'Parar Exibição'.
    (em breve: giro entre os dois lados do texto 3D)
    """

    def __init__(self, autor_id: int):
        super().__init__(timeout=300)
        self.autor_id = autor_id

    @discord.ui.button(label="⛔ Parar Exibição", style=discord.ButtonStyle.danger)
    async def parar_exibicao(self, interaction: discord.Interaction, button: discord.ui.Button):
        if (
            interaction.user.id != self.autor_id
            and not interaction.user.guild_permissions.administrator
        ):
            return await interaction.response.send_message(
                "Só quem usou o comando pode parar.", ephemeral=True
            )
        button.disabled = True
        button.label    = "✅ Exibição Encerrada"
        await interaction.response.edit_message(content="*(exibição encerrada)*", view=self)
        self.stop()


@bot.command(name="texto")
async def texto_cmd(ctx: commands.Context, conteudo: str, emojis: str):
    """
    ;texto <conteúdo> <emoji1,emoji2>
    Exibe o conteúdo em pixel-art "3D" com dois emojis.
    Exemplo: ;texto OI 🗿,✂️
    """
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    partes = emojis.split(",")
    if len(partes) < 2 or not partes[0].strip() or not partes[1].strip():
        return await ctx.send(
            "❌ Forneça dois emojis separados por vírgula.\n"
            "Exemplo: `;texto OI 🗿,✂️`"
        )

    e1, e2    = partes[0].strip(), partes[1].strip()
    resultado = render_texto(conteudo, e1, e2)

    if len(resultado) > 2000:
        return await ctx.send("❌ Texto muito longo! Use menos caracteres.")

    view = TextoView(autor_id=ctx.author.id)
    await ctx.send(resultado, view=view)


# ─────────────────────────────────────────
#  COMANDO ;batata
# ─────────────────────────────────────────
class ContestoView(discord.ui.View):
    """Botão para apagar a mensagem substituída pela batata inglesa."""

    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="Contesto", style=discord.ButtonStyle.secondary, emoji="🥔")
    async def contesto(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.message.delete()
        except (discord.NotFound, discord.Forbidden):
            await interaction.response.send_message(
                "Não consegui apagar a mensagem.", ephemeral=True
            )


_BATATA_TIPOS = {
    "normal", "gulosa", "inglesa", "doce",
    "frita", "purê", "pure", "sr", "raivosa", "mogadora",
}

_BATATA_ANUNCIO = {
    "normal":   "🥔 **Batata Normal** em {alvo}! Próxima mensagem vai sumir.",
    "gulosa":   "🥔 **Batata Gulosa** em {alvo}! Próxima mensagem vai sumir *(sem counter)*.",
    "inglesa":  "🥔 **Batata Inglesa** em {alvo}! Mensagens serão substituídas com requinte.",
    "doce":     "🥔 **Batata Doce** em {alvo}! Protegido contra batata inglesa por 20s.",
    "frita":    "🥔 **Batata Frita** em {alvo}! Protegido contra normal, raivosa e sr por 20s.",
    "purê":     "🥔 **Batata Purê** em {alvo}! Sem CAPS LOCK por 20s.",
    "sr":       "🥔 **Batata Sr.** em {alvo}! Ninguém fala até {alvo} falar (ou 20s).",
    "raivosa":  "🥔 **Batata Raivosa** em {alvo}! Fale em 10s ou suas mensagens serão deletadas!",
    "mogadora": "🥔 **Batata Mogadora** em {alvo}! Toda vez que falar... 👀",
}


@bot.command(name="batata")
async def batata_cmd(ctx: commands.Context, tipo: str, alvo: discord.Member):
    """
    ;batata <tipo> @alvo

    Tipos disponíveis:
      normal   — silencia: próxima msg some
      gulosa   — igual normal, sem counter
      inglesa  — substitui msgs por versão "britânica"
      doce     — countera batata inglesa
      frita    — countera normal, raivosa, sr
      purê     — proíbe CAPS LOCK por 20s
      sr       — silencia o servidor até o alvo falar
      raivosa  — alvo tem 10s pra falar ou msgs são deletadas
      mogadora — responde "🅱🅴🆃🅰" toda vez que o alvo falar (1 por vez)

    Batatas com counter (delay de 2s antes de ativar): normal, sr, raivosa, inglesa
    Batatas instantâneas: gulosa, frita, doce, purê, mogadora
    """
    tipo = tipo.lower()
    if tipo == "pure":
        tipo = "purê"

    if tipo not in (_BATATA_TIPOS - {"pure"}):
        return await ctx.send(
            "❌ Tipo inválido! Opções:\n"
            "`normal` `gulosa` `inglesa` `doce` `frita` `purê` `sr` `raivosa` `mogadora`"
        )

    gid = ctx.guild.id
    uid = alvo.id

    # Regra: só uma mogadora ativa por servidor
    if tipo == "mogadora" and gid in _mogando:
        mogado = ctx.guild.get_member(_mogando[gid])
        nome   = mogado.mention if mogado else "alguém"
        return await ctx.send(f"🥔 Já tem uma batata mogando {nome} neste servidor!")

    anuncio = _BATATA_ANUNCIO[tipo].format(alvo=alvo.mention)

    # ── Batatas contráveis → delay de 2s antes de ativar ─────────────────────
    if tipo in _CONTERABLE:
        await ctx.send(f"{anuncio}\n*⏳ Lançando em 2s…*")
        await asyncio.sleep(2)

        counter     = _COUNTER_DE[tipo]
        b_existente = _get_batata(gid, uid)
        if b_existente and b_existente["type"] == counter:
            return await ctx.send(
                f"🛡️ A **batata {tipo}** em {alvo.mention} foi bloqueada "
                f"pela **batata {counter}**!"
            )
    else:
        await ctx.send(anuncio)

    expires = time.time() + BATATA_DURACAO

    # ── SR ────────────────────────────────────────────────────────────────────
    if tipo == "sr":
        _sr[gid] = {"target": uid, "caster": ctx.author.id, "expires": expires}

        async def _sr_expire():
            await asyncio.sleep(BATATA_DURACAO)
            s = _sr.get(gid)
            if s and s["target"] == uid:
                _sr.pop(gid, None)
                try:
                    await ctx.channel.send(
                        f"🥔 Tempo esgotado! A **Batata Sr.** de {alvo.mention} acabou.",
                        delete_after=5,
                    )
                except Exception:
                    pass

        asyncio.create_task(_sr_expire())

    # ── MOGADORA ──────────────────────────────────────────────────────────────
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
                        delete_after=5,
                    )
                except Exception:
                    pass

        asyncio.create_task(_mog_expire())

    # ── RAIVOSA ───────────────────────────────────────────────────────────────
    elif tipo == "raivosa":
        _set_batata(gid, uid, "raivosa", ctx.author.id, expires)

        async def _raivosa_expire():
            await asyncio.sleep(BATATA_DURACAO)
            _clear_batata(gid, uid)

        asyncio.create_task(_raivosa_expire())

    # ── DEMAIS (normal, gulosa, inglesa, frita, doce, purê) ──────────────────
    else:
        _set_batata(gid, uid, tipo, ctx.author.id, expires)

        async def _expire():
            await asyncio.sleep(BATATA_DURACAO)
            _clear_batata(gid, uid)

        asyncio.create_task(_expire())


# ─────────────────────────────────────────
#  EVENT — on_message  (lógica das batatas)
# ─────────────────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    # Ignora bots e DMs
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    gid    = message.guild.id
    uid    = message.author.id
    is_cmd = message.content.startswith(PREFIX)

    # ── MOGADORA: responde toda vez que o alvo falar ──────────────────────────
    if _mogando.get(gid) == uid:
        try:
            await message.channel.send("🅱🅴🆃🅰")
        except discord.Forbidden:
            pass
        # A mensagem original do alvo passa normalmente

    # ── SR: silêncio geral até o alvo falar ──────────────────────────────────
    sr = _sr.get(gid)
    if sr:
        if time.time() >= sr["expires"]:
            _sr.pop(gid, None)

        elif uid == sr["target"]:
            # Alvo falou → encerra o sr
            _sr.pop(gid, None)
            try:
                await message.channel.send(
                    f"🥔 {message.author.mention} falou! **Batata Sr.** encerrada.",
                    delete_after=5,
                )
            except discord.Forbidden:
                pass
            # Mensagem do alvo segue normalmente

        else:
            # Qualquer outro usuário: deleta msg comum; comandos passam em memória
            if not is_cmd:
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound):
                    pass
                return
            # É um comando: apaga do chat mas ainda processa a resposta
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass
            await bot.process_commands(message)
            return

    # ── OUTRAS BATATAS (só em msgs comuns, não em comandos) ───────────────────
    if not is_cmd:
        b = _get_batata(gid, uid)
        if b:
            tipo = b["type"]

            # ── normal / gulosa: deleta só a primeira mensagem (one-shot) ────
            if tipo in ("normal", "gulosa"):
                if not b.get("first_deleted"):
                    b["first_deleted"] = True
                    try:
                        await message.delete()
                    except (discord.Forbidden, discord.NotFound):
                        pass
                    _clear_batata(gid, uid)
                    return

            # ── inglesa: substitui mensagem por versão "britânica" ───────────
            elif tipo == "inglesa":
                conteudo = message.content
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound):
                    pass
                view = ContestoView()
                try:
                    await message.channel.send(
                        f"🥔 *{message.author.display_name} disse, com muito refinamento britânico:*\n"
                        f"> {conteudo}",
                        view=view,
                    )
                except discord.Forbidden:
                    pass
                return

            # ── purê: sem CAPS LOCK ──────────────────────────────────────────
            elif tipo == "purê":
                if any(c.isupper() for c in message.content):
                    try:
                        await message.delete()
                    except (discord.Forbidden, discord.NotFound):
                        pass
                    try:
                        await message.channel.send(
                            f"🥔 {message.author.mention} SEM CAPS LOCK! *(batata purê)*",
                            delete_after=4,
                        )
                    except discord.Forbidden:
                        pass
                    return

            # ── raivosa: 10s para falar ou msgs deletadas ────────────────────
            elif tipo == "raivosa":
                deadline = b["cast_time"] + 10.0
                if not b.get("spoke"):
                    if time.time() <= deadline:
                        # Falou no prazo → batata encerrada, nada acontece
                        b["spoke"] = True
                        _clear_batata(gid, uid)
                    else:
                        # Passou o prazo → deleta
                        try:
                            await message.delete()
                        except (discord.Forbidden, discord.NotFound):
                            pass
                        return

    await bot.process_commands(message)


# ─────────────────────────────────────────
#  ERROS GLOBAIS
# ─────────────────────────────────────────
@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Erro: o comando necessita de `{error.param.name}`.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("Erro: O usuário não existe.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Erro: Batata")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("Erro: Necessita de aura para executar este comando.")
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
            type=discord.ActivityType.watching,
            name="sem ;aura porque sim",
        )
    )


bot.run(os.environ["DISCORD_TOKEN"])
