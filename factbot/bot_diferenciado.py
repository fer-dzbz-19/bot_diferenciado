
from multiprocessing.dummy import connection
import os
import asyncio
from unittest import result

import discord
import requests
import pyttsx3
import sqlite3

from dotenv import load_dotenv
from discord.ext import commands
from urllib.parse import quote
from contextlib import closing
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DB_PATH = "tasks.db"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

bot.remove_command("help")

def speak(text):

    engine = pyttsx3.init()
    engine.setProperty("rate", 150)
    engine.setProperty("volume", 1.0)
    engine.setProperty("voice", "brazil")
    engine.say(text)
    engine.runAndWait()

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0
                )
            """)


def add_task(task):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            conn.execute(
                "INSERT INTO tasks (description, completed) VALUES (?, ?)",
                (task, 0)
            )
        return "Tarefa adicionada com sucesso!"

def get_tasks():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        return conn.execute("SELECT id, description, completed FROM tasks ORDER BY id").fetchall()

def delete_task(task_id):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            cursor =conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cursor.rowcount > 0

def get_fact(language = "en"):

    url = "https://uselessfacts.jsph.pl/api/v2/facts/random"

    if language not in {"en", "es", "pt-BR"}:
        raise ValueError("A API aceita apenas os idiomas: 'en', 'es' e 'pt-BR'.")

    try:
        response = requests.get(
            url,
            params={"language": language},
            timeout=10
        )

        # Mostra o status HTTP da requisição.
        print("Status HTTP:", response.status_code)

        if response.status_code != 200:
            print("Erro ao consultar a API.")
            return None

        data = response.json()

        # Exibe a resposta JSON completa no terminal.
        print(data)

        # O campo 'text' contém a curiosidade.
        return data.get("text")

    except requests.RequestException as error:
        print("Falha na conexão com a API:", error)
        return None

    except ValueError as error:
        print("A API retornou uma resposta JSON inválida.", error)
        return None


def get_weather(city: str):
    url = f"https://wttr.in/{quote(city)}"
    response = None

    try:
        response = requests.get(
            url,
            params={"format": "j1"},
            headers={"User-Agent": "FactBot/1.0"},
            timeout=15
        )

        print("Status HTTP:", response.status_code)

        response.raise_for_status()
        data = response.json()

        current = data["current_condition"][0]

        weather = {
            "condition": current["weatherDesc"][0]["value"],
            "temperature": current["temp_C"],
            "feels_like": current["FeelsLikeC"],
            "humidity": current["humidity"],
            "wind_speed": current["windspeedKmph"],
            "wind_direction": current["winddir16Point"]
        }

        print("Dados do clima recebidos:", weather)
        return weather

    except requests.RequestException as error:
        print("Erro de conexão ou HTTP:", repr(error))
        return None

    except (ValueError, KeyError, IndexError, TypeError) as error:
        if response is not None:
            print("Resposta recebida:", response.text[:500])
        else:
            print("Nenhuma resposta HTTP foi recebida.")


def translate_to_portuguese(text: str) -> str:
    url = "https://api.mymemory.translated.net/get"

    try:
        response = requests.get(
            url,
            params={
                "q": text,
                "langpair": "en|pt-BR"
            },
            timeout=10
        )

        response.raise_for_status()
        data = response.json()

        translated = data.get(
            "responseData", {}
        ).get("translatedText")

        if translated:
            return translated

        return text

    except (requests.RequestException, ValueError) as error:
        print("Erro na tradução:", error)
        return text

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    print("O bot está pronto para receber comandos!")

@bot.event
async def on_member_join(member):
    if member.guild.system_channel is not None:
        await member.guild.system_channel.send(
            f"Olá, {member.mention}! 👋 Bem-vindo(a) ao servidor!\n"
            "Sou o FactBot. Digite `!help` para conhecer meus comandos."
        )

@bot.command(name="start")
#@commands.cooldown(1, 3600, commands.BucketType.user)
async def start(ctx):
    await ctx.send(
        f"Olá, {ctx.author.mention}! 👋\n"
        "Sou o FactBot, seu bot de curiosidades!\n"
        "Use `!fact` para descobrir um fato interessante.\n"
        "Use `!weather <cidade>` para consultar o clima.\n"
        "Use `!help` para ver todos os comandos disponíveis."
    )

@bot.command(name="fact")
async def fact(ctx, language: str = "pt"):
    language = language.lower()

    if language == "pt":
        original = await asyncio.to_thread(get_fact, "en")
        text = None

        if original:
            text = await asyncio.to_thread(
                translate_to_portuguese,
                original
            )

    elif language in {"en", "es"}:
        text = await asyncio.to_thread(get_fact, language)

    else:
        await ctx.send("Use `pt`, `en` ou `es`.")
        return

    if not text:
        await ctx.send("Não consegui buscar uma curiosidade agora.")
        return

    await ctx.send(f"🧠 **Você sabia?**\n{text}")
    await asyncio.to_thread(speak, text)



@bot.command(name="weather")
#@commands.cooldown(5, 3600, commands.BucketType.user)
async def weather(ctx, *, city: str):
    weather_info = await asyncio.to_thread(get_weather, city)

    if weather_info is None:
        await ctx.send(
            "Não consegui consultar o clima dessa cidade. "
            "Verifique o nome e tente novamente."
        )
        return

    embed = discord.Embed(
        title=f"🌦️ Previsão do tempo — {city}",
        description=weather_info["condition"],
        color=discord.Color.blue()
    )

    embed.add_field(
        name="🌡️ Temperatura",
        value=f'{weather_info["temperature"]} °C',
        inline=True
    )

    embed.add_field(
        name="🌡️ Sensação térmica",
        value=f'{weather_info["feels_like"]} °C',
        inline=True
    )

    embed.add_field(
        name="💧 Umidade",
        value=f'{weather_info["humidity"]}%',
        inline=True
    )

    embed.add_field(
        name="💨 Velocidade do vento",
        value=f'{weather_info["wind_speed"]} km/h',
        inline=True
    )

    embed.add_field(
        name="🧭 Direção do vento",
        value=weather_info["wind_direction"],
        inline=True
    )

    embed.set_footer(text="FactBot • Dados meteorológicos")

    await ctx.send(embed=embed)



@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="🤖 FactBot — Central de Ajuda",
        description=(
            "Olá! Aqui estão os comandos disponíveis.\n"
            "Use-os no chat do servidor."
        ),
        color=discord.Color.green()
    )

    embed.add_field(
        name="👋 !start",
        value="Apresenta o FactBot e explica o básico.",
        inline=False
    )

    embed.add_field(
        name="🧠 !fact",
        value=(
            "Recebe uma curiosidade em português.\n"
            "`!fact` — português\n"
            "`!fact en` — inglês\n"
            "`!fact es` — espanhol"
        ),
        inline=False
    )

    embed.add_field(
        name="🌦️ !weather <cidade>",
        value=(
            "Consulta as condições meteorológicas atuais.\n"
            "Exemplo: `!weather Humaitá`"
        ),
        inline=False
    )

    embed.add_field(
        name="❓ !help",
        value="Mostra esta lista de comandos.",
        inline=False
    )

    embed.add_field(
    name="📝 Tarefas",
    value=(
        "`!addtask <descrição>` — adiciona uma tarefa.\n"
        "Exemplo: `!addtask terminar o módulo`\n"
        "`!listtasks` — mostra as tarefas cadastradas e seus IDs.\n"
        "`!deletetask <id>` — remove a tarefa pelo ID.\n"
        "Exemplo: `!deletetask 2`"
    ),
    inline=False
    )

    embed.set_footer(text="FactBot • Mais funcionalidades em breve!")

    await ctx.send(embed=embed)

@bot.command(name="addtask")
async def add_task_command(ctx, *, task: str):
    result = await asyncio.to_thread(add_task, task)

    embed = discord.Embed(
        title="✅ Tarefa Adicionada",
        description=result,
        color=discord.Color.red()
    )

    await ctx.send(embed=embed)

@bot.command(name="listtasks")
async def list_tasks_command(ctx):

    embed = discord.Embed(
        title="📋 Lista de Tarefas",
        description=("Aqui estão as tarefas cadastradas:"),
        color=discord.Color.red()
    )

    await ctx.send(embed=embed)

    tasks = await asyncio.to_thread(get_tasks)
    await ctx.send(tasks)

@bot.command(name="deletetask")
async def delete_task_command(ctx, task_id: int):
    delete = await asyncio.to_thread(delete_task, task_id)

    if delete:
        title = "✅ Tarefa Removida"
        description = f"A tarefa {task_id} foi removida."
        color = discord.Color.red()
    else:
        title = "❌ Tarefa Não Encontrada"
        description = (f"A tarefa {task_id} não existe."
                       " Você já a deletou ?"
        )
        color = discord.Color.blue()

    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )

    await ctx.send(embed=embed)

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError(
            "Token não encontrado! Configure a variável "
            "de ambiente DISCORD_TOKEN."
        )
    init_db()
    print("Banco de dados inicializado.")
    bot.run(TOKEN)