import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=';', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot iniciado com sucesso como {bot.user}')

# =====================================================================
# CHAMAR COM MUITA AURA AEEEE
# =====================================================================
@bot.command()
async def chamar(ctx, membro: discord.Member):
    if membro == ctx.author:
        await ctx.send("Tem amigo não é?")
        return
    if membro.bot:
        await ctx.send("Eu sou alérgico a betas, por isso eu não aceito que um betinha me chame.")
        return

    try:
        mensagem = f"ACORDA CARAI! VOCÊ {membro.mention} ESTÁ PERDENDO AURA DEMAIS. O {ctx.author.mention} Quer jogar, mas você, sim você mesmo está atrasando tudo! Vai lá no **{ctx.guild.name}** e entra call🎧"
        await membro.send(mensagem)
        await ctx.send(f"Aquele beta({membro.mention}) foi mogado na DM com sucesso!")
        
    except discord.Forbidden:
        await ctx.send(f"Não consegui enviar DM para {membro.mention}. Ele não abre a porta dele para estranhos, como você, por exemplo.")

# ===================================================
# Craques do futebol
# =======================================================================

class OpcoesJogadas:
    # Ataque
    CORRER = "Continuar Correndo"
    PASSE_NORMAL = "Passe Normal"
    PASSE_PROF= "Passe em Profundidade"
    CHUTE_FORTE = "Chute Forte de Longe"
    CABECEIO = "Cabeceio Direcionado"
    
    # Defesa
    IR_NA_BOLA = "Ir na Bola (Corpo)"
    MARCAR_RIVAL = "Marcar Companheiro"
    CARRINHO = "Dar Carrinho"
    COBRIR_ALTO = "Cobrir Bola Alta"

    # Goleiro e Chute Final
    ESQUERDA = "Canto Esquerdo"
    DIREITA = "Canto Direito"
    MEIO = "Centro do Gol"


class PainelEscolhaEscondida(discord.ui.View):
    """Gera os botões efêmeros secretos para cada jogador"""
    def __init__(self, gerenciador, papel, usuario_alvo):
        super().__init__(timeout=10.0)
        self.gerenciador = gerenciador
        self.papel = papel
        self.usuario_alvo = usuario_alvo
        self.escolha = None
        self.configurar_botoes()

    def configurar_botoes(self):
        if self.papel == "ataque_linha":
            opcoes = [OpcoesJogadas.CORRER, OpcoesJogadas.PASSE_NORMAL, OpcoesJogadas.PASSE_PROF, OpcoesJogadas.CHUTE_FORTE, OpcoesJogadas.CABECEIO]
            estilo = discord.ButtonStyle.primary
        elif self.papel == "defesa_linha":
            opcoes = [OpcoesJogadas.IR_NA_BOLA, OpcoesJogadas.MARCAR_RIVAL, OpcoesJogadas.CARRINHO, OpcoesJogadas.COBRIR_ALTO]
            estilo = discord.ButtonStyle.danger
        elif self.papel == "ataque_goleiro":
            opcoes = [OpcoesJogadas.ESQUERDA, OpcoesJogadas.DIREITA, OpcoesJogadas.MEIO]
            estilo = discord.ButtonStyle.success
        elif self.papel == "defesa_goleiro":
            opcoes = [OpcoesJogadas.ESQUERDA, OpcoesJogadas.DIREITA, OpcoesJogadas.MEIO]
            estilo = discord.ButtonStyle.secondary

        for opcao in opcoes:
            btn = discord.ui.Button(label=opcao, style=estilo, custom_id=opcao)
            btn.callback = self.processar_clique
            self.add_item(btn)

    async def processar_clique(self, interaction: discord.Interaction):
        if interaction.user != self.usuario_alvo:
            await interaction.response.send_message("Você não tem permissão para usar este painel.", ephemeral=True)
            return
            
        self.escolha = interaction.data['custom_id']
        for item in self.children:
            item.disabled = True
            
        await interaction.response.edit_message(content=f"Decisão registrada: {self.escolha}. Aguardando os demais...", view=self)
        await self.gerenciador.computar_voto(self.papel, self.escolha)

    async def on_timeout(self):
        if not self.escolha:
            # Seleção automática por W.O de tempo
            opcoes_padrao = {
                "ataque_linha": OpcoesJogadas.CORRER,
                "defesa_linha": OpcoesJogadas.IR_NA_BOLA,
                "ataque_goleiro": OpcoesJogadas.MEIO,
                "defesa_goleiro": OpcoesJogadas.MEIO
            }
            self.escolha = opcoes_padrao[self.papel]
            await self.gerenciador.computar_voto(self.papel, f"{self.escolha} (Estourou o Tempo)")


class PainelGatilhoPublico(discord.ui.View):
    """Botoes no chat publico para os jogadores abrirem seus menus privados"""
    def __init__(self, gerenciador):
        super().__init__(timeout=60.0)
        self.gerenciador = gerenciador

    @discord.ui.button(label="Painel de Ataque", style=discord.ButtonStyle.primary)
    async def abrir_ataque(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.gerenciador.atq_linha:
            await interaction.response.send_message("Você não é o Atacante de linha ativo.", ephemeral=True)
            return
        view = PainelEscolhaEscondida(self.gerenciador, "ataque_linha", interaction.user)
        await interaction.response.send_message("Selecione sua jogada de ataque:", view=view, ephemeral=True)

    @discord.ui.button(label="Painel de Defesa", style=discord.ButtonStyle.danger)
    async def abrir_defesa(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.gerenciador.def_linha:
            await interaction.response.send_message("Você não é o Defensor de linha ativo.", ephemeral=True)
            return
        view = PainelEscolhaEscondida(self.gerenciador, "defesa_linha", interaction.user)
        await interaction.response.send_message("Selecione sua estratégia de defesa:", view=view, ephemeral=True)


class PainelGoleiroPublico(discord.ui.View):
    """Botoes no chat publico para o duelo final com o goleiro"""
    def __init__(self, gerenciador):
        super().__init__(timeout=60.0)
        self.gerenciador = gerenciador

    @discord.ui.button(label="Definir Direção do Chute", style=discord.ButtonStyle.success)
    async def mirar_chute(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.gerenciador.atq_linha:
            await interaction.response.send_message("Você não é o chutador.", ephemeral=True)
            return
        view = PainelEscolhaEscondida(self.gerenciador, "ataque_goleiro", interaction.user)
        await interaction.response.send_message("Para qual canto você vai chutar?", view=view, ephemeral=True)

    @discord.ui.button(label="Definir Salto do Goleiro", style=discord.ButtonStyle.secondary)
    async def saltar_goleiro(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.gerenciador.def_goleiro:
            await interaction.response.send_message("Você não é o Goleiro deste lance.", ephemeral=True)
            return
        view = PainelEscolhaEscondida(self.gerenciador, "defesa_goleiro", interaction.user)
        await interaction.response.send_message("Para qual canto você vai pular?", view=view, ephemeral=True)


class PartidaFutebol:
    """Controlador central de dados da partida 2v2 melhor de 3"""
    def __init__(self, ctx, t1_linha, t1_goleiro, t2_linha, t2_goleiro):
        self.ctx = ctx
        
        # Equipes
        self.t1_linha = t1_linha
        self.t1_goleiro = t1_goleiro
        self.t2_linha = t2_linha
        self.t2_goleiro = t2_goleiro
        
        # Placar
        self.gols_t1 = 0
        self.gols_t2 = 0
        self.rodada_atual = 1
        
        # Definindo posições iniciais (Time 1 começa atacando)
        self.atq_linha = t1_linha
        self.atq_goleiro = t1_goleiro
        self.def_linha = t2_linha
        self.def_goleiro = t2_goleiro
        
        # Armazenamento de turnos
        self.voto_atq_linha = None
        self.voto_def_linha = None
        self.voto_atq_gol = None
        self.voto_def_gol = None
        
        self.msg_painel = None

    async def iniciar(self):
        await self.ctx.send(
            f"PARTIDA INICIADA - MELHOR DE 3! Que vença o melhor\n"
            f"Time 1: Linha {self.t1_linha.mention} | Goleiro {self.t1_goleiro.mention}\n"
            f"Time 2: Linha {self.t2_linha.mention} | Goleiro {self.t2_goleiro.mention}\n"
            f"--------------------------------------------------"
        )
        await self.executar_rodada()

    async def executar_rodada(self):
        self.voto_atq_linha = None
        self.voto_def_linha = None
        self.voto_atq_gol = None
        self.voto_def_gol = None

        conteudo = (
            f"RODADA {self.rodada_atual} de 3\n"
            f"Placar Atual: Time 1 [{self.gols_t1}] vs [{self.gols_t2}] Time 2\n\n"
            f"O atacante {self.atq_linha.mention} avança contra o zagueiro {self.def_linha.mention}.\n"
            f"Jogadores, cliquem nos botões abaixo para abrir suas escolhas efêmeras. Vocês têm 10 segundos!"
        )
        view = PainelGatilhoPublico(self)
        self.msg_painel = await self.ctx.send(content=conteudo, view=view)

    async def computar_voto(self, papel, escolha):
        if papel == "ataque_linha":
            self.voto_atq_linha = escolha
        elif papel == "defesa_linha":
            self.voto_def_linha = escolha
        elif papel == "ataque_goleiro":
            self.voto_atq_gol = escolha
        elif papel == "defesa_goleiro":
            self.voto_def_gol = escolha

        # Verifica se a primeira fase (linha) terminou
        if self.voto_atq_linha and self.voto_def_linha and not self.voto_atq_gol:
            await self.processar_fase_linha()
            
        # Verifica se a segunda fase (goleiro) terminou
        if self.voto_atq_gol and self.voto_def_gol:
            await self.processar_fase_goleiro()

    async def processar_fase_linha(self):
        atq = self.voto_atq_linha.split(" (")[0]
        deff = self.voto_def_linha.split(" (")[0]
        
        resultado_texto = f"Confronto de Linha:\nAtacante escolheu: {atq}\nDefensor escolheu: {deff}\n\n"
        chute_liberado = False

        # Matrix de Decisão Pura (Sem RNG)
        if atq == OpcoesJogadas.CHUTE_FORTE:
            if deff == OpcoesJogadas.IR_NA_BOLA:
                resultado_texto += "O zagueiro tentou o jogo de corpo, mas o atacante limpou espaço e soltou uma bomba! A bola vai em direção ao gol!"
                chute_liberado = True
            elif deff == OpcoesJogadas.CARRINHO:
                resultado_texto += "FALTA CRUEL! O zagueiro deu um carrinho desproporcional. Cartão amarelo e falta direta frontal contra o goleiro!"
                chute_liberado = True
            else:
                resultado_texto += "A zaga ficou marcando passe e deu espaço. O atacante soltou um chute fortíssimo de fora da área!"
                chute_liberado = True

        elif atq == OpcoesJogadas.CABECEIO:
            if deff == OpcoesJogadas.COBRIR_ALTO:
                resultado_texto += "O zagueiro subiu junto no tempo certo e desviou o cabeceio para escanteio! Chance perdida."
            else:
                resultado_texto += "Cruzamento perfeito na área! O atacante subiu sozinho e testou firme para o gol!"
                chute_liberado = True

        elif atq == OpcoesJogadas.PASSE_NORMAL:
            if deff == OpcoesJogadas.MARCAR_RIVAL:
                resultado_texto += "O atacante tentou o passe curto lateral, mas o zagueiro antecipou a jogada de forma perfeita e roubou a bola!"
            else:
                resultado_texto += "Passe curto executado com sucesso, o companheiro infiltrou e bateu de primeira na saída do goleiro!"
                chute_liberado = True

        elif atq == OpcoesJogadas.PASSE_PROF:
            if deff == OpcoesJogadas.CARRINHO:
                resultado_texto += "O zagueiro deu o carrinho no vento! A bola passou em profundidade rasgando a zaga e deixando o atacante cara a cara!"
                chute_liberado = True
            else:
                resultado_texto += "O passe em profundidade correu demais no campo molhado e saiu diretamente pela linha de fundo."

        elif atq == OpcoesJogadas.CORRER:
            if deff == OpcoesJogadas.IR_NA_BOLA:
                resultado_texto += "O zagueiro usou o jogo de corpo com precisão, desestabilizou o atacante e ficou com a posse de bola."
            elif deff == OpcoesJogadas.CARRINHO:
                resultado_texto += "O zagueiro acertou um carrinho limpo na bola e desarmou o contra-ataque!"
            else:
                resultado_texto += "O atacante usou a velocidade, deixou o zagueiro para trás e invadiu a grande área de frente pro gol!"
                chute_liberado = True

        if chute_liberado:
            await self.msg_painel.edit(content=f"{resultado_texto}\n\n**FASE FINAL: DUELO COM O GOLEIRO!**\nChutador vai chutar, e Goleiro ({self.def_goleiro.mention}) não vai deixar a bola entrar fácil.", view=PainelGoleiroPublico(self))
        else:
            await self.msg_painel.edit(content=f"{resultado_texto}\n\nO ataque erra no lance...", view=None)
            await self.finalizar_rodada(gol=False)

    async def processar_fase_goleiro(self):
        canto_chute = self.voto_atq_gol.split(" (")[0]
        canto_goleiro = self.voto_def_gol.split(" (")[0]
        
        resultado_texto = f"Faz ou não faz? **\nChutador chuta no(a) {canto_chute}**, e **\nGoleiro pula para {canto_goleiro}**\n\n"
        
        if canto_chute == canto_goleiro:
            resultado_texto += f"É GOL, É GOL? É NADA! QUE DEFESA DO GOLEIRO! Leu a jogada perfeitamente e pula para {canto_goleiro} e salva o time."
            gol = False
        else:
            resultado_texto += "É GOL, É GOL? É GOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOL! QUE JOGADA DO TIME! O goleiro não teve chance e falhou no lance"
            gol = True
            
        await self.msg_painel.edit(content=resultado_texto, view=None)
        await self.finalizar_rodada(gol=gol)

    async def finalizar_rodada(self, gol):
        if gol:
            if self.atq_linha == self.t1_linha:
                self.gols_t1 += 1
            else:
                self.gols_t2 += 1

        await asyncio.sleep(4) # Janela de tempo para leitura do resultado
        
        self.rodada_atual += 1
        
        # Alterna os papéis para o próximo lance (Quem defendia agora ataca)
        if self.rodada_atual <= 3:
            if self.atq_linha == self.t1_linha:
                self.atq_linha, self.atq_goleiro = self.t2_linha, self.t2_goleiro
                self.def_linha, self.def_goleiro = self.t1_linha, self.t1_goleiro
            else:
                self.atq_linha, self.atq_goleiro = self.t1_linha, self.t1_goleiro
                self.def_linha, self.def_goleiro = self.t2_linha, self.t2_goleiro
                
            await self.executar_rodada()
        else:
            await self.encerrar_partida()

    async def encerrar_partida(self):
        vencedor = ""
        if self.gols_t1 > self.gols_t2:
            vencedor = f"FIM DE JOGO! {self.gols_t1} a {self.gols_t2} pro Time 1"
        elif self.gols_t2 > self.gols_t1:
            vencedor = f"FIM DE JOGO! {self.gols_t2} a {self.gols_t1} pro Time 2"
        else:
            vencedor = f"FIM DE JOGO! {self.gols_t1} a {self.gols_t2}, um empate entre times"

        await self.ctx.send(f"==================================\n{vencedor}\n==================================")


@bot.command()
async def jogar(ctx, t1_goleiro: discord.Member, t2_linha: discord.Member, t2_goleiro: discord.Member):
    """Inicia a partida de futebol no formato 2v2 (Melhor de 3)"""
    # uso vira jogador de linha do time 1
    t1_linha = ctx.author
    
    todos_jogadores = [t1_linha, t1_goleiro, t2_linha, t2_goleiro]
    if len(set(todos_jogadores)) < 4:
        await ctx.send("Erro: Para uma partida de 2v2 realista, você precisa convocar 4 usuários distintos.")
        return

    for jogador in todos_jogadores:
        if jogador.bot:
            await ctx.send("Bots não fazem gols, igual você, um beta mogado...")
            return

    partida = PartidaFutebol(ctx, t1_linha, t1_goleiro, t2_linha, t2_goleiro)
    await partida.iniciar()

# Token safe
bot.run(TOKEN)
