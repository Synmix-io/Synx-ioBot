# Discord Friend Finder Bot

A Discord bot that helps users find new friends based on their interests and age groups.

## Features

- Register with personal information (name, age group, hobbies, bio)
- Find matches based on similar interests and age groups
- View and edit your profile
- Delete your profile when desired

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file based on `.env.example` and add your credentials:
   - Discord Bot Token
   - Supabase Project URL and Anon Key

3. Run the bot:
```bash
python friendfinder_bot.py
```

## Commands

- `/register`: Register your profile
  - Parameters: name, age_group, hobbies, bio, likes, dislikes

- `/matchme`: Find users with similar interests or age group

- `/profile`: View your current profile

- `/deleteprofile`: Remove your profile from the system

## Safety Features

- Age group separation to prevent inappropriate interactions
- Data stored securely in Supabase
- Users can delete their profiles at any time
- Optional reporting system can be added in the future

## Future Improvements

- Enhanced matching algorithm
- User reporting system
- Profile verification
- More detailed user preferences
- Chat functionality between matched users
