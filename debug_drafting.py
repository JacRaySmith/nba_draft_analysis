from nba_api.stats.endpoints import playerawards
import time

# Nikola Jokic's PERSON_ID — we know this from our player_stats.csv
JOKIC_ID = 203999

awards_data = playerawards.PlayerAwards(player_id=JOKIC_ID)
df = awards_data.get_data_frames()[0]

print("Column names:")
print(df.columns.tolist())

print("\nAll rows:")
print(df.to_string())