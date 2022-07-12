from ast import alias
import math
import aiosqlite
import asyncio
import discord
from discord.ext import commands
from discord.utils import get
import os

from music_cog import music_cog

intents = discord.Intents().all()
intents.members = True
bot = commands.Bot(command_prefix=".", intents=intents)
bot.multiplier = 1

bot.add_cog(music_cog(bot))

bot.remove_command("help")

@bot.event
async def on_ready():
    print("Protocol initialized . . . Bot activated")
    
#DATABASE
async def initialise():
    await bot.wait_until_ready()
    bot.db = await aiosqlite.connect("expData.db")
    await bot.db.execute("CREATE TABLE IF NOT EXISTS guildData (guild_id, user_id int, exp int, PRIMARY KEY (guild_id, user_id))")

@bot.event
async def on_message(message):
    if not message.author.bot:
        cursor = await bot.db.execute("INSERT OR IGNORE INTO guildData (guild_id, user_id, exp) VALUES (?,?,?)", (message.guild.id, message.author.id, 1)) 

        if cursor.rowcount == 0:
            await bot.db.execute("UPDATE guildData SET exp = exp + 1 WHERE guild_id = ? AND user_id = ?", (message.guild.id, message.author.id))
            cur = await bot.db.execute("SELECT exp FROM guildData WHERE guild_id = ? AND user_id = ?", (message.guild.id, message.author.id))
            data = await cur.fetchone()
            exp = data[0]
            lvl = math.sqrt(exp) / bot.multiplier
        
            if lvl.is_integer():
                await message.channel.send(f"{message.author.mention} well done! You're now level: {int(lvl)}.")

        await bot.db.commit()

    await bot.process_commands(message)

@bot.command()
async def stats(ctx, member: discord.Member=None):
    if member is None: member = ctx.author

    # get user exp
    async with bot.db.execute("SELECT exp FROM guildData WHERE guild_id = ? AND user_id = ?", (ctx.guild.id, member.id)) as cursor:
        data = await cursor.fetchone()
        exp = data[0]

        # calculate rank
    async with bot.db.execute("SELECT exp FROM guildData WHERE guild_id = ?", (ctx.guild.id,)) as cursor:
        rank = 1
        async for value in cursor:
            if exp < value[0]:
                rank += 1

    lvl = int(math.sqrt(exp)//bot.multiplier)

    current_lvl_exp = (bot.multiplier*(lvl))**2
    next_lvl_exp = (bot.multiplier*((lvl+1)))**2

    lvl_percentage = ((exp-current_lvl_exp) / (next_lvl_exp-current_lvl_exp)) * 100

    embed = discord.Embed(title=f"Stats for {member.name}", colour=discord.Colour.gold())
    embed.add_field(name="Level", value=str(lvl))
    embed.add_field(name="Exp", value=f"{exp}/{next_lvl_exp}")
    embed.add_field(name="Rank", value=f"{rank}/{ctx.guild.member_count}")
    embed.add_field(name="Level Progress", value=f"{round(lvl_percentage, 2)}%")

    await ctx.send(embed=embed)

@bot.command()
async def leaderboard(ctx): 
    buttons = {}
    for i in range(1, 6):
        buttons[f"{i}\N{COMBINING ENCLOSING KEYCAP}"] = i # only show first 5 pages

    previous_page = 0
    current = 1
    index = 1
    entries_per_page = 10

    embed = discord.Embed(title=f"Leaderboard Page {current}", description="", colour=discord.Colour.gold())
    msg = await ctx.send(embed=embed)

    for button in buttons:
        await msg.add_reaction(button)

    while True:
        if current != previous_page:
            embed.title = f"Leaderboard Page {current}"
            embed.description = ""

            async with bot.db.execute(f"SELECT user_id, exp FROM guildData WHERE guild_id = ? ORDER BY exp DESC LIMIT ? OFFSET ? ", (ctx.guild.id, entries_per_page, entries_per_page*(current-1),)) as cursor:
                index = entries_per_page*(current-1)

                async for entry in cursor:
                    index += 1
                    member_id, exp = entry
                    member = ctx.guild.get_member(member_id)
                    embed.description += f"{index}) {member.mention} : {exp}\n"

                await msg.edit(embed=embed)

        try:
            reaction, user = await bot.wait_for("reaction_add", check=lambda reaction, user: user == ctx.author and reaction.emoji in buttons, timeout=60.0)

        except asyncio.TimeoutError:
            return await msg.clear_reactions()

        else:
            previous_page = current
            await msg.remove_reaction(reaction.emoji, ctx.author)
            current = buttons[reaction.emoji]
#-----------------------------------------------------------------------------------------------#

#AUTO-ROLE
@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name='Coder')
    await member.add_roles(role)
#-----------------------------------------------------------------------------------------------#

#CHAT COMMAND
@bot.command()
async def clear(ctx, amount : int ):
    await ctx.channel.purge(limit = amount)
#-----------------------------------------------------------------------------------------------#

#KICK/BAN/UNBAN COMMANDS
@bot.command()
@commands.has_permissions(administrator =True)
async def kick(ctx, member: discord.Member, *, reason=None):
    emb = discord.Embed( title = "Kick", colour = discord.Color.orange())
    await ctx.channel.purge( limit = 1)
    await member.kick(reason=reason)
    
    emb.set_author( name = member.name, icon_url = member.avatar_url )
    emb.add_field( name = "Kick user", value = "Kicked user : {}".format(member.mention) )
    emb.set_footer( text = "Was kicked by {}".format( ctx.author.name), icon_url = ctx.author.avatar_url )

    await ctx.send( embed = emb )

@bot.command()
@commands.has_permissions(administrator =True)
async def ban(ctx, member: discord.Member, *, reason=None):
    emb = discord.Embed( title = "Ban", colour = discord.Color.red())
    await ctx.channel.purge( limit = 1)
    await member.ban(reason=reason)
    
    emb.set_author( name = member.name, icon_url = member.avatar_url )
    emb.add_field( name = "Ban user", value = "Banned user : {}".format(member.mention) )
    emb.set_footer( text = "Was banned by {}".format( ctx.author.name), icon_url = ctx.author.avatar_url )

    await ctx.send( embed = emb )

@bot.command()
@commands.has_permissions(administrator =True)
async def unban(ctx, *, member):
    await ctx.channel.purge( limit = 1)
    
    bannedUsers = await ctx.guild.bans()
    name, discrimator = member.split("#")
    
    for ban in bannedUsers:
        user = ban.user
        
        if(user.name, user.discriminator) == (name, discrimator):
            await ctx.guild.unban(user)
            await ctx.send(f"{user.mention} unbanned on server!")
            return
#-----------------------------------------------------------------------------------------------#

#USERINFO
@bot.command(name="userinfo", aliases = ["uinf"])
async def userinfo(ctx,user:discord.Member=None):
    user = ctx.author
    
    emb = discord.Embed(title="USER INFO", description=f"Here is the we retrieved about {user}", colour=user.colour)
    emb.set_thumbnail( url = user.avatar_url )
    
    emb.add_field( name="NAME", value=user.display_name, inline=True ) 
    emb.add_field( name="NICKNAME", value=user.nick, inline=True )
    emb.add_field( name="ID", value=user.id, inline=False)
    emb.add_field( name="TOP ROLE", value=user.top_role.name, inline=False )
    emb.add_field( name="STATUS", value=user.status, inline=False )
    emb.set_footer( text=f'Requested by - {user}', icon_url=user.avatar_url )
    await ctx.send(embed=emb)
#-----------------------------------------------------------------------------------------------#

#HELP
@bot.command( pass_context = True )
async def help( ctx ):
    emb = discord.Embed(title = "Ohayo sempai ;)")
    emb.add_field( name = "MODERATION", value = "`kick`, `ban`, `unban`", inline = False)
    emb.add_field( name = "CHAT", value = "`clear`, `stats`, `leaderboard`", inline = False)
    emb.add_field( name = "MUSIC", value = "`play`, `pause`, `resume`, `queue`, `skip`, `clearl`, `leave`", inline = False)
    emb.set_footer(text = f'Request by - {ctx.author}', icon_url = ctx.author.avatar_url)
    
    await ctx.send( embed = emb )
#-----------------------------------------------------------------------------------------------#
bot.loop.create_task(initialise())
bot.run("Insert your bot token")
asyncio.run(bot.db.close())
