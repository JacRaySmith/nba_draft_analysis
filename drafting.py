import os
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# nba_api is imported inside the fetch functions, so the scoring and chart can be
# rebuilt from the saved CSVs without it installed.

FIRST_DRAFT, LAST_DRAFT = 2010, 2022  # inclusive


def get_draft_history():
    if os.path.exists('draft_history.csv'):
        print("Draft history already exists, loading from file...")
        return pd.read_csv('draft_history.csv')

    from nba_api.stats.endpoints import drafthistory

    draft_data = []

    for year in range(FIRST_DRAFT, LAST_DRAFT + 1):
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
    from nba_api.stats.endpoints import playercareerstats

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
    """Return the player's award bonus, or None if the API kept failing.

    None (not 0) matters: a failed request must not look like "no awards",
    or the player is silently under-scored.
    """
    from nba_api.stats.endpoints import playerawards

    for attempt in range(3):
        try:
            df = playerawards.PlayerAwards(player_id=person_id).get_data_frames()[0]
            break
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed for {player_name}: {e}")
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))  # 2s, then 4s
    else:
        return None

    total_bonus = 0
    for _, award_row in df.iterrows():
        description = award_row['DESCRIPTION']
        if description == 'All-NBA':
            # team number comes back as a string '1', '2', or '3'
            try:
                total_bonus += ALL_NBA_VALUES.get(int(award_row['ALL_NBA_TEAM_NUMBER']), 0)
            except (ValueError, TypeError):
                pass  # NaN or unparseable team number
        elif description in AWARD_VALUES:
            total_bonus += AWARD_VALUES[description]
    return total_bonus


def add_base_scores(df):
    df['PER_GAME_SCORE']  = df['PTS_PER_G'] + (df['REB_PER_G'] * 0.7) + (df['AST_PER_G'] * 0.7)
    df['DURABILITY']      = (df['GP'] / 500).clip(upper=1.0)
    df['PICK_MULTIPLIER'] = 1 + (df['OVERALL_PICK'] - 1) / 59
    df['DRAFT_SCORE']     = df['PER_GAME_SCORE'] * df['DURABILITY'] * df['PICK_MULTIPLIER']
    return df


def get_all_awards(stats_df):
    # Only fetch awards for players who actually had impact (saves ~400 API calls)
    df = add_base_scores(stats_df.copy())
    worthy = df[df['DRAFT_SCORE'] >= 5.0]
    print(f"Fetching awards for {len(worthy)} players with draft score >= 5...")

    award_bonuses, failed = {}, []
    for _, row in worthy.iterrows():
        bonus = get_awards_for_player(row['PERSON_ID'], row['PLAYER_NAME'])
        if bonus is None:
            failed.append({'PERSON_ID': row['PERSON_ID'], 'PLAYER_NAME': row['PLAYER_NAME']})
        else:
            award_bonuses[row['PERSON_ID']] = bonus
        time.sleep(0.8)

    awards_df = pd.DataFrame(
        [{'PERSON_ID': pid, 'AWARD_BONUS': bonus} for pid, bonus in award_bonuses.items()]
    )
    awards_df.to_csv('player_awards.csv', index=False)
    print(f"\nDone! Saved awards for {len(awards_df)} players.")

    if failed:
        pd.DataFrame(failed).to_csv('failed_awards.csv', index=False)
        print(f"WARNING: {len(failed)} award lookups failed; see failed_awards.csv and re-run.")
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
    df = add_base_scores(df)
    df['TOTAL_SCORE']     = df['DRAFT_SCORE'] + df['AWARD_BONUS']

    # Aggregate by team
    team_scores = df.groupby('TEAM_ABBREVIATION').agg(
        TOTAL_DRAFT_SCORE  = ('TOTAL_SCORE',  'sum'),
        PLAYERS_DRAFTED    = ('PLAYER_NAME',  'count'),
        AVG_PLAYER_SCORE   = ('TOTAL_SCORE',  'mean'),
        TOTAL_AWARD_POINTS = ('AWARD_BONUS',  'sum'),
        BEST_PLAYER        = ('TOTAL_SCORE',  lambda x: df.loc[x.idxmax(), 'PLAYER_NAME'])
    ).reset_index()

    # Divide by sqrt(picks): a raw sum rewards teams that simply had more picks,
    # a plain average rewards teams with a few lucky ones. sqrt is the middle ground.
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

def visualize_rankings(team_scores):
    fig, ax = plt.subplots(figsize=(14, 10))

    top20 = team_scores.head(20).copy()
    top20 = top20.iloc[::-1].reset_index(drop=True)

    # Plot the same normalized score the ranking is sorted by, split into its
    # stats and award parts (both divided by sqrt(picks)).
    scale = top20['PLAYERS_DRAFTED'].pow(0.5)
    base_scores = (top20['TOTAL_DRAFT_SCORE'] - top20['TOTAL_AWARD_POINTS']) / scale
    award_scores = top20['TOTAL_AWARD_POINTS'] / scale
    teams = top20['TEAM_ABBREVIATION'].tolist()  # convert to plain list
    best_players = top20['BEST_PLAYER'].tolist()

    y = np.arange(len(teams))

    ax.barh(y, base_scores, color='steelblue', label='Stats Score')
    ax.barh(y, award_scores, left=base_scores, color='gold', label='Award Bonus')

    for i, (base, award, player) in enumerate(zip(base_scores, award_scores, best_players)):
        total = base + award
        ax.text(total + 1, i, player, va='center', fontsize=8, color='black')

    # Force linear scale and set team labels explicitly
    ax.set_yscale('linear')
    ax.set_yticks(y)
    ax.set_yticklabels(teams, fontsize=10)
    ax.set_xlabel('Normalized draft score (total ÷ √picks)', fontsize=12)
    ax.set_title(f'NBA Draft Quality Rankings {FIRST_DRAFT}–{LAST_DRAFT}\n(Normalized by picks used)', fontsize=14, fontweight='bold')
    ax.legend(loc='lower right')
    ax.set_xlim(0, top20['NORMALIZED_SCORE'].max() * 1.35)

    ax.xaxis.grid(True, linestyle='--', alpha=0.5)
    ax.set_axisbelow(True)

    plt.tight_layout()
    plt.savefig('draft_rankings.png', dpi=150)
    if plt.get_backend().lower() != 'agg':
        plt.show()
    print("Chart saved to draft_rankings.png")



def main():
    draft_df = get_draft_history()
    stats_df = (pd.read_csv('player_stats.csv') if os.path.exists('player_stats.csv')
                else get_all_player_stats(draft_df))
    awards_df = (pd.read_csv('player_awards.csv') if os.path.exists('player_awards.csv')
                 else get_all_awards(stats_df))
    _, team_scores = calculate_final_scores(stats_df, awards_df)
    visualize_rankings(team_scores)


if __name__ == '__main__':
    main()
