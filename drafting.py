from nba_api.stats.endpoints import drafthistory, playercareerstats, playerawards
import pandas as pd
import time

def get_draft_history():
    import os
    if os.path.exists('draft_history.csv'):
        print("Draft history already exists, loading from file...")
        return pd.read_csv('draft_history.csv')

    draft_data = []

    for year in range(2010, 2023):
        print(f"Fetching draft history for year: {year}")

        draft = drafthistory.DraftHistory(league_id='00', season_year_nullable=year)
        df = draft.get_data_frames()[0]
        draft_data.append(df)

        # Sleep to avoid hitting rate limits
        time.sleep(1)

    full_draft = pd.concat(draft_data, ignore_index=True)
    full_draft.to_csv('draft_history.csv', index=False)
    print("Draft history saved to draft_history.csv")
    print(f"\nDone! Saved {len(full_draft)} players to draft_history.csv")
    print("\nColumns available:", full_draft.columns.tolist())
    print("\nFirst 3 rows:\n", full_draft.head(3))
    return full_draft

def get_player_stats(person_id, player_name):
    for attempt in range(3):  # try up to 3 times
        try:
            career = playercareerstats.PlayerCareerStats(player_id=person_id)
            career_totals = career.get_data_frames()[1]

            if career_totals.empty:
                return None
            
            row = career_totals.iloc[0]

            return {
                'PERSON_ID': person_id,
                'PLAYER_NAME': player_name,
                'GP': row['GP'],
                'PTS': row['PTS'],
                'REB': row['REB'],
                'AST': row['AST'],
                'PTS_PER_G': round(row['PTS'] / row['GP'], 1) if row['GP'] > 0 else 0,
                'REB_PER_G': round(row['REB'] / row['GP'], 1) if row['GP'] > 0 else 0,
                'AST_PER_G': round(row['AST'] / row['GP'], 1) if row['GP'] > 0 else 0,
            }

        except KeyError:
            # Player never played in NBA, no data available - skip silently
            return None

        except Exception as e:
            print(f"  ⚠️ Attempt {attempt + 1} failed for {player_name}: {e}")
            if attempt < 2:  # only wait after the first failure
                wait = (attempt + 1) * 2  # wait 2s, then 4s
                print(f"  ⏳ Waiting {wait}s before retrying...")
                time.sleep(wait)
    return None

def get_all_player_stats(draft_df):
    # Load already-fetched players if the file exists
    try:
        existing = pd.read_csv('player_stats.csv')
        done_ids = set(existing['PERSON_ID'].tolist())
        results = existing.to_dict('records')
        print(f"Resuming — {len(done_ids)} players already fetched.")
    except FileNotFoundError:
        done_ids = set()
        results = []

    total = len(draft_df)

    for i, row in draft_df.iterrows():
        if row['PERSON_ID'] in done_ids:
            print(f"[{i+1}/{total}] Skipping {row['PLAYER_NAME']} (already fetched)")
            continue

        print(f"[{i+1}/{total}] Fetching stats for {row['PLAYER_NAME']}, pick: {row['OVERALL_PICK']}...")

        stats = get_player_stats(row['PERSON_ID'], row['PLAYER_NAME'])

        if stats:
            stats['TEAM_ABBREVIATION'] = row['TEAM_ABBREVIATION']
            stats['SEASON'] = row['SEASON']
            stats['OVERALL_PICK'] = row['OVERALL_PICK']
            stats['ROUND_NUMBER'] = row['ROUND_NUMBER']
            results.append(stats)
            done_ids.add(row['PERSON_ID'])

            # Save after every player so progress is never lost
            pd.DataFrame(results).to_csv('player_stats.csv', index=False)

        time.sleep(2)

    stats_df = pd.DataFrame(results)
    print(f"\nDone! Saved stats for {len(stats_df)} players.")
    return stats_df


FRANCHISE_MAP = {
    'NJN': 'BKN',   # New Jersey Nets -> Brooklyn Nets (moved 2012)
    'NOH': 'NOP',   # New Orleans Hornets -> New Orleans Pelicans (renamed 2013)
    'NOK': 'NOP',   # New Orleans/Oklahoma City Hornets (older)
    'SEA': 'OKC',   # Seattle SuperSonics -> Oklahoma City Thunder (moved 2008)
    'CHA': 'CHA',   # Keep as-is — Charlotte Hornets (we'll check this separately)
}

AWARD_VALUES = {
    'NBA Most Valuable Player':           25,
    'NBA Finals Most Valuable Player':    15,
    'NBA Champion':                        8,
    'NBA Defensive Player of the Year':    8,
    'NBA Most Improved Player':            6,
    'NBA Rookie of the Year':              6,
    'NBA Sixth Man of the Year':           4,
    'NBA All-Star':                        4,
    'All-NBA':                             0,  # handled separately below
}

ALL_NBA_VALUES = {
    1: 12,  # First Team
    2:  8,  # Second Team
    3:  4,  # Third Team
}

def get_awards_for_player(person_id, player_name):
    try:
        awards_data = playerawards.PlayerAwards(player_id=person_id)
        df = awards_data.get_data_frames()[0]

        if df.empty:
            return 0

        total_bonus = 0

        for _, award_row in df.iterrows():
            description = award_row['DESCRIPTION']

            if description == 'All-NBA':
                team_number = award_row['ALL_NBA_TEAM_NUMBER']
                # team_number comes back as a string '1', '2', or '3'
                # so we convert it to int before looking it up
                try:
                    bonus = ALL_NBA_VALUES.get(int(team_number), 0)
                    total_bonus += bonus
                except (ValueError, TypeError):
                    pass  # skip if team_number is NaN or unparseable

            elif description in AWARD_VALUES:
                total_bonus += AWARD_VALUES[description]

        return total_bonus

    except Exception as e:
        print(f"  Error fetching awards for {player_name}: {e}")
        return 0



def get_all_awards(stats_df):
    # Only fetch awards for players who actually had impact (saves ~400 API calls)
    df = stats_df.copy()
    df['PER_GAME_SCORE'] = df['PTS_PER_G'] + (df['REB_PER_G'] * 0.7) + (df['AST_PER_G'] * 0.7)
    df['DURABILITY'] = (df['GP'] / 500).clip(upper=1.0)
    df['PICK_MULTIPLIER'] = 1 + (df['OVERALL_PICK'] - 1) / 59
    df['DRAFT_SCORE'] = df['PER_GAME_SCORE'] * df['DURABILITY'] * df['PICK_MULTIPLIER']

    # Only bother checking awards for players with meaningful draft scores
    worthy = df[df['DRAFT_SCORE'] >= 5.0].copy()
    print(f"Fetching awards for {len(worthy)} players with draft score >= 5...")

    award_bonuses = {}

    for i, row in worthy.iterrows():
        print(f"  [{i}] {row['PLAYER_NAME']}...")
        bonus = get_awards_for_player(row['PERSON_ID'], row['PLAYER_NAME'])
        if bonus > 0:
            print(f"       -> {bonus} award points")
        award_bonuses[row['PERSON_ID']] = bonus
        time.sleep(0.8)

    # Save so we don't have to re-fetch
    awards_df = pd.DataFrame([
        {'PERSON_ID': pid, 'AWARD_BONUS': bonus}
        for pid, bonus in award_bonuses.items()
    ])
    awards_df.to_csv('player_awards.csv', index=False)
    print(f"\nDone! Saved awards for {len(awards_df)} players.")
    return awards_df

def calculate_final_scores(stats_df, awards_df):
    df = stats_df.copy()

    # Fix franchise abbreviations
    df['TEAM_ABBREVIATION'] = df['TEAM_ABBREVIATION'].replace(FRANCHISE_MAP)

    # Filter players who never stuck in the league
    df = df[df['GP'] >= 82].copy()

    # Merge awards in — left join so players with no awards get 0
    # A 'left join' keeps every row in df, and pulls in matching rows from awards_df
    # Players with no match in awards_df get NaN, which we fill with 0
    df = df.merge(awards_df, on='PERSON_ID', how='left')
    df['AWARD_BONUS'] = df['AWARD_BONUS'].fillna(0)

    # Print the top 20 award earners so we can verify the data is real
    print("--- Top 20 award bonus earners ---")
    top_awards = df[df['AWARD_BONUS'] > 0].sort_values('AWARD_BONUS', ascending=False)
    print(top_awards[['PLAYER_NAME', 'TEAM_ABBREVIATION', 'OVERALL_PICK', 'AWARD_BONUS']].head(20).to_string(index=False))

    # Scoring
    df['PER_GAME_SCORE']  = df['PTS_PER_G'] + (df['REB_PER_G'] * 0.7) + (df['AST_PER_G'] * 0.7)
    df['DURABILITY']      = (df['GP'] / 500).clip(upper=1.0)
    df['PICK_MULTIPLIER'] = 1 + (df['OVERALL_PICK'] - 1) / 59
    df['DRAFT_SCORE']     = df['PER_GAME_SCORE'] * df['DURABILITY'] * df['PICK_MULTIPLIER']
    df['TOTAL_SCORE']     = df['DRAFT_SCORE'] + df['AWARD_BONUS']

    # Aggregate by team
    team_scores = df.groupby('TEAM_ABBREVIATION').agg(
        TOTAL_DRAFT_SCORE  = ('TOTAL_SCORE',  'sum'),
        PLAYERS_DRAFTED    = ('PLAYER_NAME',  'count'),
        AVG_PLAYER_SCORE   = ('TOTAL_SCORE',  'mean'),
        TOTAL_AWARD_POINTS = ('AWARD_BONUS',  'sum'),
        BEST_PLAYER        = ('TOTAL_SCORE',  lambda x: df.loc[x.idxmax(), 'PLAYER_NAME'])
    ).reset_index()

    team_scores['NORMALIZED_SCORE'] = (
        team_scores['TOTAL_DRAFT_SCORE'] / team_scores['PLAYERS_DRAFTED'].pow(0.5)
    )

    team_scores = team_scores.sort_values('NORMALIZED_SCORE', ascending=False).reset_index(drop=True)
    team_scores.index += 1  # rank starts at 1, not 0
    team_scores.to_csv('final_rankings.csv')

    print("\n--- FINAL DRAFT RANKINGS (normalized) ---")
    print(team_scores.head(15).to_string())

    print("\n--- Bottom 5 ---")
    print(team_scores.tail(5).to_string())

    return df, team_scores

import os

stats_df = pd.read_csv('player_stats.csv')

# Only fetch awards if file does not exist
if not os.path.exists('player_awards.csv'):
    print("Awards file not found — fetching from API...")
    awards_df = get_all_awards(stats_df)
else:
    awards_df = pd.read_csv('player_awards.csv')

player_df, team_scores = calculate_final_scores(stats_df, awards_df)


stats_df = pd.read_csv('player_stats.csv')
gobert = stats_df[stats_df['PLAYER_NAME'].str.contains('Gobert')]
print(gobert[['PLAYER_NAME', 'TEAM_ABBREVIATION', 'OVERALL_PICK', 'SEASON']])
