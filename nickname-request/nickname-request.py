from discord import Embed, Guild, Member, TextChannel
from discord.ext import commands

from core import checks
from core.models import PermissionLevel


class NicknameRequest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._db = self.bot.plugin_db.get_partition(self)

        self._requests = []

        self.bot.loop.create_task(self._init_requests())

    async def _add_request(self, message_id):
        self._requests.append(str(message_id))

        await self._db.find_one_and_update(
            {"_id": "req"}, {"$set": {"requests": self._requests}}, upsert=True
        )

    async def _remove_request(self, message_id):
        self._requests.remove(str(message_id))

        await self._db.find_one_and_update(
            {"_id": "req"}, {"$set": {"requests": self._requests}}, upsert=True
        )

    async def _init_requests(self):
        req = await self._db.find_one({"_id": "req"})

        if req is None:
            return

        self._requests = req["requests"]

    @checks.has_permissions(PermissionLevel.ADMIN)
    @commands.command()
    async def nchannel(self, ctx, channel: TextChannel):
        """Sets a channel to receive nickname requests"""
        await self._db.find_one_and_update(
            {"_id": "channel"}, {"$set": {"snowflake": str(channel.id)}}, upsert=True
        )
        await ctx.send(embed=Embed(description=f"Successfully set the channel as <#{channel.id}>", colour=0X7289DA))

    @commands.command()
    async def rnick(self, ctx, nickname):
        """Request a nickname change"""
        channel = self.bot.get_channel(int((await self._db.find_one({"_id": "channel"}))["snowflake"]) or 0)

        if channel is None:
            await ctx.send(
                embed=Embed(description=f"A nickname requests channel is not set. Use `{ctx.prefix}nchannel` to set the channel")
            )
            return

        embed = Embed(
            title="New Nickname Request", 
            description=f"**{ctx.author}** wants their nickname changed to **{nickname}**.",
            colour=0X7289DA
        )
        embed.set_author(name=ctx.author.id, icon_url=ctx.author.avatar_url)
        embed.set_footer(text="React with ✅ to approve this nickname, or ❌ to decline it.")
        
        msg = await channel.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        await self._add_request(msg.id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if not payload.guild_id:
            return

        if payload.member and payload.member.bot:
            return
        
        if payload.emoji.name not in ["✅", "❌"]:
            return

        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        member = guild.get_member(int(message.embeds[0].author.name))

        if str(message.id) not in self._requests:
            return

        if payload.emoji.name == "✅":
            await member.edit(nick=message.content.split(" wants their nickname changed to ")[1][2:-3])
            await message.edit(description="Approved!", colour=0x00FF7F)
            await member.send(embed=Embed(description="Your nickname change has been approved!", colour=0X00FF7F))
        else:
            await message.edit(description="Denied.", colour=0xFF0000)
            await member.send(embed=Embed(description="Your nickname change has been rejected...", colour=0XFF0000))

        await message.clear_reactions()
        await self._remove_request(message.id)


def setup(bot):
    bot.add_cog(NicknameRequest(bot))