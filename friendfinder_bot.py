import os
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
from supabase import create_client, Client
from datetime import datetime
import asyncio
import json
from typing import Optional

class FriendFinderBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        self.supabase: Client = None
        
    async def setup_hook(self):
        # Register slash commands globally
        await self.tree.sync()
        
    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')



    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

bot = FriendFinderBot()

@bot.event
async def on_ready():
    print(f'Bot is ready!')

# Database operations
async def init_supabase():
    load_dotenv()
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')
    if not url or not key:
        raise ValueError("Missing Supabase credentials in .env file")
    
    # Initialize Supabase client (no headers/options needed)
    bot.supabase = create_client(url, key)

    # Optionally, check if the table exists (will error if not, but that's fine for dev)
    try:
        bot.supabase.table('users').select("*").execute()
        print("Table exists")
    except Exception as e:
        print(f"Table check error (this is normal if the table doesn't exist): {e}")

# Register command
@bot.tree.command(name="register")
@app_commands.describe(
    name="Your display name",
    age="Your age (number, e.g. 15)",
    hobbies="Your hobbies (comma-separated)",
    bio="A short introduction about yourself",
    likes="Things you like",
    dislikes="Things you dislike"
)
async def register(interaction: discord.Interaction,
                  name: str,
                  age: int,
                  hobbies: str,
                  bio: str,
                  likes: str,
                  dislikes: str):
    """Register your profile to find new friends"""
    if not (10 <= age <= 120):
        await interaction.response.send_message("Please enter a valid age (10-120).", ephemeral=True)
        return
    try:
        bot.supabase.table('users').upsert({
            "id": str(interaction.user.id),
            "name": name,
            "age": age,
            "hobbies": hobbies,
            "bio": bio,
            "likes": likes,
            "dislikes": dislikes,
            "created_at": datetime.now().isoformat()
        }).execute()
        await interaction.response.send_message(
            "Profile registered/updated successfully! Use /matchme to find friends."
        )
    except Exception as e:
        await interaction.response.send_message(
            f"Error registering profile: {str(e)}"
        )

from discord.ui import View, Button

# --- Helper Functions ---
def get_best_matches(user_data, all_users, skipped_ids):
    """Return a sorted list of best matches based on age proximity and shared hobbies, excluding skipped IDs."""
    user_hobbies = set(h.strip().lower() for h in user_data['hobbies'].split(','))
    user_age = int(user_data['age'])
    matches = []
    for candidate in all_users:
        if candidate['id'] == user_data['id'] or candidate['id'] in skipped_ids:
            continue
        score = 0
        # Age match: prefer same age, else ±2
        age_diff = abs(int(candidate['age']) - user_age)
        if age_diff == 0:
            score += 10
        elif age_diff <= 2:
            score += 6
        # Shared hobbies
        candidate_hobbies = set(h.strip().lower() for h in candidate['hobbies'].split(','))
        shared = len(user_hobbies & candidate_hobbies)
        score += shared * 2
        matches.append((score, candidate))
    # Sort by score descending, then by created_at
    matches.sort(key=lambda x: (-x[0], x[1]['created_at']))
    return [m[1] for m in matches if m[0] > 0]


async def fetch_discord_tag(bot, user_id):
    try:
        user = await bot.fetch_user(int(user_id))
        return f"{user.name}#{user.discriminator}" if hasattr(user, 'discriminator') else user.name
    except Exception:
        return user_id

def format_match_embed_basic(match, discord_tag=None):
    embed = discord.Embed(color=0xFFC0CB)
    embed.title = f"✨ {match['name']} ✨"
    if discord_tag:
        embed.add_field(name="**Discord Tag**", value=f"`{discord_tag}`", inline=False)
    embed.add_field(name="**Age**", value=f"`{match['age']}`", inline=False)
    embed.add_field(name="**Bio**", value=f"{match['bio']}", inline=False)
    return embed

class ChatModal(discord.ui.Modal, title="Send a Cute Message!"):
    message = discord.ui.TextInput(
        label="Your message to this user",
        style=discord.TextStyle.paragraph,
        placeholder="Write something friendly or cute...",
        required=True,
        max_length=200
    )
    def __init__(self, match, sender_profile, on_submit_callback):
        super().__init__()
        self.match = match
        self.sender_profile = sender_profile
        self.on_submit_callback = on_submit_callback

    async def on_submit(self, interaction: discord.Interaction):
        await self.on_submit_callback(interaction, self.match, self.sender_profile, self.message.value)

class AcceptIgnoreView(View):
    def __init__(self, sender_id, matched_user_id, sender_profile):
        super().__init__(timeout=180)
        self.sender_id = sender_id
        self.matched_user_id = matched_user_id
        self.sender_profile = sender_profile
        self.already_responded = False

    @discord.ui.button(label="Accept ✅", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: Button):
        if self.already_responded:
            await interaction.response.send_message("You already responded.", ephemeral=True)
            return
        self.already_responded = True
        try:
            sender_user = await interaction.client.fetch_user(int(self.sender_id))
            await sender_user.send(f"🎉 Your chat request was accepted!\nYou can now DM or send a friend request.\nTheir User ID: `{self.matched_user_id}`")
        except Exception:
            pass
        await interaction.response.send_message("You accepted the chat request! They have been notified.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Ignore ❌", style=discord.ButtonStyle.danger)
    async def ignore(self, interaction: discord.Interaction, button: Button):
        if self.already_responded:
            await interaction.response.send_message("You already responded.", ephemeral=True)
            return
        self.already_responded = True
        await interaction.response.send_message("You ignored the chat request.", ephemeral=True)
        self.stop()

class MatchView(View):
    def __init__(self, matches, author_id, skipped_ids, bot):
        super().__init__(timeout=120)
        self.matches = matches
        self.index = 0
        self.author_id = author_id
        self.skipped_ids = set(skipped_ids)
        self.message = None
        self.bot = bot

    def get_current(self):
        if 0 <= self.index < len(self.matches):
            return self.matches[self.index]
        return None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You can't use these buttons!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Chat", style=discord.ButtonStyle.primary, emoji="💬")
    async def chat_button(self, interaction: discord.Interaction, button: Button):
        match = self.get_current()
        if not match:
            await interaction.response.send_message("No match to chat with!", ephemeral=True)
            return
        # Fetch sender's Discord tag and intro
        sender_tag = await fetch_discord_tag(self.bot, str(interaction.user.id))
        sender_resp = self.bot.supabase.table('users').select("*").eq("id", str(interaction.user.id)).execute()
        sender_intro = sender_resp.data[0]['bio'] if sender_resp.data else "(no intro)"
        try:
            matched_user = await interaction.client.fetch_user(int(match['id']))
            msg = (
                f"💌 You are matched with **{sender_tag}** on Synx.io!\n"
                f"Here's their intro: {sender_intro}\n"
                f"You can reply to them directly if you want to chat!"
            )
            await matched_user.send(msg)
            await interaction.response.send_message("Your chat request has been sent!", ephemeral=True)
        except Exception:
            await interaction.response.send_message("Couldn't DM this user (maybe DMs are closed).", ephemeral=True)

    @discord.ui.button(label="Skip 🔄", style=discord.ButtonStyle.danger)
    async def skip_button(self, interaction: discord.Interaction, button: Button):
        match = self.get_current()
        if match:
            self.skipped_ids.add(match['id'])
        # Find next match not in skipped_ids
        all_matches = self.matches
        while self.index + 1 < len(all_matches):
            self.index += 1
            if all_matches[self.index]['id'] not in self.skipped_ids:
                break
        else:
            await interaction.response.edit_message(content="No more matches left!", embed=None, view=None)
            return
        next_match = self.get_current()
        tag = await fetch_discord_tag(self.bot, next_match['id'])
        embed = format_match_embed_basic(next_match, tag)
        await interaction.response.edit_message(embed=embed, view=self)

# --- /matchme Command ---
@bot.tree.command(name="matchme")
async def matchme(interaction: discord.Interaction):
    """Find your best match based on age and shared hobbies."""
    try:
        user_resp = bot.supabase.table('users').select("*").eq("id", str(interaction.user.id)).execute()
        if not user_resp.data:
            await interaction.response.send_message("Please register first using /register", ephemeral=True)
            return
        user_data = user_resp.data[0]
        all_resp = bot.supabase.table('users').select("*").neq("id", str(interaction.user.id)).execute()
        all_users = all_resp.data if all_resp.data else []
        skipped_ids = set()
        matches = get_best_matches(user_data, all_users, skipped_ids)
        if not matches:
            await interaction.response.send_message("No matches found yet. Try again later!", ephemeral=True)
            return
        # Show the best match (first in list)
        tag = await fetch_discord_tag(bot, matches[0]['id'])
        embed = format_match_embed_basic(matches[0], tag)
        view = MatchView(matches, interaction.user.id, skipped_ids, bot)
        await interaction.response.send_message(content="Here's your best match!", embed=embed, view=view)
    except Exception as e:
        await interaction.response.send_message(f"Error finding matches: {str(e)}", ephemeral=True)

# Profile command
@bot.tree.command(name="profile")
async def profile(interaction: discord.Interaction):
    """View or edit your profile"""
    try:
        user_data = bot.supabase.table('users')\
            .select("*")\
            .eq("id", str(interaction.user.id))\
            .execute()

        if not user_data.data:
            await interaction.response.send_message(
                "No profile found. Register first using /register"
            )
            return

        # Create styled profile embed
        profile = user_data.data[0]
        embed = discord.Embed(title=f"🌸 Your Profile 🌸", color=0xFFC0CB)
        embed.add_field(name="**Name**", value=f"`{profile['name']}`", inline=False)
        embed.add_field(name="**Age Group**", value=f"`{profile['age_group']}`", inline=False)
        embed.add_field(name="**Hobbies**", value=f"`{profile['hobbies']}`", inline=False)
        embed.add_field(name="**Bio**", value=f"{profile['bio']}", inline=False)
        if profile.get('likes'):
            embed.add_field(name="**Likes**", value=f"{profile['likes']}", inline=True)
        if profile.get('dislikes'):
            embed.add_field(name="**Dislikes**", value=f"{profile['dislikes']}", inline=True)
        embed.set_footer(text=f"User ID: {profile['id']}")
        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(
            f"Error viewing profile: {str(e)}"
        )

# Delete profile command
@bot.tree.command(name="deleteprofile")
async def deleteprofile(interaction: discord.Interaction):
    """Delete your profile from the system"""
    try:
        bot.supabase.table('users')\
            .delete()\
            .eq("id", str(interaction.user.id))\
            .execute()
        
        await interaction.response.send_message(
            "Your profile has been successfully deleted."
        )
    except Exception as e:
        await interaction.response.send_message(
            f"Error deleting profile: {str(e)}"
        )

# Run initialization
asyncio.run(init_supabase())

# Run the bot
bot.run(os.getenv('DISCORD_TOKEN'))
