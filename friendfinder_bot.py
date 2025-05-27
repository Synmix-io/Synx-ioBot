import os
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
from supabase import create_client, Client
from datetime import datetime
import asyncio
import uuid
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

    def convert_to_uuid(self, user_id: str) -> str:
        """Convert Discord user ID to UUID string format"""
        try:
            return str(uuid.UUID(user_id))
        except ValueError:
            return user_id  # Return original if conversion fails

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
    
    # Initialize Supabase with proper options
    options = {
        'auth_client': True,
        'schema': 'public'
    }
    bot.supabase = create_client(url, key, options)
    
    # Create table if it doesn't exist
    try:
        # Check if table exists
        bot.supabase.table('users').select("*").execute()
        print("Table exists")
    except Exception as e:
        print(f"Creating table: {e}")
        # Create table with proper UUID type
        bot.supabase.table('users').insert([
            {
                "id": "uuid_generate_v4()",
                "name": "name",
                "age_group": "age_group",
                "hobbies": "hobbies",
                "bio": "bio",
                "likes": "likes",
                "dislikes": "dislikes",
                "created_at": "created_at"
            }
        ]).execute()

# Register command
@bot.tree.command(name="register")
@app_commands.describe(
    name="Your display name",
    age_group="Choose your age group: Teen (13-19), Adult (20-60), Elder (60+)",
    hobbies="Your hobbies (comma-separated)",
    bio="A short introduction about yourself",
    likes="Things you like",
    dislikes="Things you dislike"
)
async def register(interaction: discord.Interaction,
                  name: str,
                  age_group: str,
                  hobbies: str,
                  bio: str,
                  likes: str,
                  dislikes: str):
    """Register your profile to find new friends"""
    
    # Validate age group
    valid_age_groups = ["Teen", "Adult", "Elder"]
    if age_group not in valid_age_groups:
        await interaction.response.send_message(
            "Invalid age group. Choose from: Teen, Adult, Elder"
        )
        return

    # Save to database
    try:
        # Convert Discord ID to UUID format
        user_id = bot.convert_to_uuid(str(interaction.user.id))
        
        bot.supabase.table('users').insert({
            "id": user_id,
            "name": name,
            "age_group": age_group,
            "hobbies": hobbies,
            "bio": bio,
            "likes": likes,
            "dislikes": dislikes,
            "created_at": datetime.now().isoformat()
        }).execute()
        
        await interaction.response.send_message(
            "Profile registered successfully! Use /matchme to find friends."
        )
    except Exception as e:
        await interaction.response.send_message(
            f"Error registering profile: {str(e)}"
        )

# Match command
@bot.tree.command(name="matchme")
async def matchme(interaction: discord.Interaction):
    """Find users with similar interests or age group"""
    try:
        # Get user's own data
        user_id = self.convert_to_uuid(str(interaction.user.id))
        user_data = bot.supabase.table('users')\
            .select("*")\
            .eq("id", user_id)\
            .execute()
            
        if not user_data.data:
            await interaction.response.send_message(
                "Please register first using /register"
            )
            return

        # Find matches based on age group and hobbies
        matches = bot.supabase.table('users')\
            .select("*")\
            .eq("age_group", user_data.data[0]["age_group"])\
            .neq("id", user_id)\
            .execute()

        if not matches.data:
            await interaction.response.send_message(
                "No matches found yet. Try again later!"
            )
            return

        # Format matches as embeds
        embeds = []
        for match in matches.data[:5]:  # Show top 5 matches
            embed = discord.Embed(title=match["name"], color=0x00ff00)
            embed.add_field(name="Age Group", value=match["age_group"])
            embed.add_field(name="Hobbies", value=match["hobbies"])
            embed.add_field(name="Bio", value=match["bio"])
            embed.set_footer(text=f"User ID: {match['id']}")
            embeds.append(embed)

        await interaction.response.send_message(
            "Here are some potential matches!",
            embeds=embeds
        )

    except Exception as e:
        await interaction.response.send_message(
            f"Error finding matches: {str(e)}"
        )

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

        # Create profile embed
        profile = user_data.data[0]
        embed = discord.Embed(title="Your Profile", color=0x00ff00)
        embed.add_field(name="Name", value=profile["name"])
        embed.add_field(name="Age Group", value=profile["age_group"])
        embed.add_field(name="Hobbies", value=profile["hobbies"])
        embed.add_field(name="Bio", value=profile["bio"])
        embed.add_field(name="Likes", value=profile["likes"])
        embed.add_field(name="Dislikes", value=profile["dislikes"])
        
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
        user_id = self.convert_to_uuid(str(interaction.user.id))
        bot.supabase.table('users')\
            .delete()\
            .eq("id", user_id)\
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
