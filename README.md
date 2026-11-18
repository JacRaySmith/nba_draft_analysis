NBA Draft Quality Analysis (2010–2022)
Ranks all 30 NBA teams by the quality of players they drafted in the 2010 through 2022 drafts, using a composite scoring model built on career stats, pick position, and individual awards.

Data Sources

Draft history and career stats: nba_api — an unofficial Python client for NBA.com
Awards: nba_api PlayerAwards endpoint

Methodology
Player Score
Each drafted player receives a score calculated as:
per_game_score  = PTS/G + (REB/G × 0.7) + (AST/G × 0.7)
durability      = min(GP / 500, 1.0)
pick_multiplier = 1 + (overall_pick - 1) / 59
draft_score     = per_game_score × durability × pick_multiplier
total_score     = draft_score + award_bonus
per_game_score approximates VORP using per-game production. Rebounds and assists are weighted at 0.7 relative to points.
Durability scales linearly up to 500 career games (roughly 6 seasons), then caps at 1.0, so longevity doesn't dominate the score.
pick_multiplier ranges from 1.0 (pick 1) to 2.0 (pick 60), rewarding late-round value. A 2nd-round player who becomes a starter contributes more to a team's score than a lottery pick with equivalent stats.
Award Bonuses
Award
PointsNBA Most Valuable Player    25
NBA Finals MVP                    15
NBA Champion                      8
NBA Defensive Player of the Year  8
NBA Most Improved Player          6
NBA Rookie of the Year            6
All-NBA First Team                12
All-NBA Second Team               8
All-NBA Third Team                4
NBA Sixth Man of the Year         4
NBA All-Star                      4

Team Score
Only players with at least 82 career games count. Each team's player scores are summed, then divided by the square root of the number of picks it used:
normalized_score = total_score / sqrt(players_drafted)
A raw sum rewards teams that simply had more picks; a plain average rewards teams with a few lucky picks. The square root is a middle ground. The chart plots this normalized score, split into its stats and award parts.

Data Quality
Requests are paced and retried with increasing waits, and stats are checkpointed to CSV after every player so an interrupted run resumes where it stopped. An award lookup that keeps failing is written to failed_awards.csv instead of being scored as zero awards, so a network error can't silently under-score a player.

Running
python drafting.py rebuilds the rankings and chart from the saved CSVs (nba_api is only needed to re-fetch data).

Limitations
Draft-night trades: Credit is given to the selecting team, not the team that ultimately developed the player. Kawhi Leonard (Indiana → San Antonio), Luka Dončić (Atlanta → Dallas), and Rudy Gobert (Denver → Utah) are all credited to their selecting franchise. This measures talent identification, not player development.
Recent draft classes: Players from the 2020–2022 drafts have played only a few seasons. Their scores are systematically lower than those of veterans, which understates their eventual value. Rankings will shift as these players develop.
Awards are voted, not measured: MVP, Most Improved, and the other awards are decided by media voters, so they include a human element (narrative, team record, voter fatigue). MVP is not a direct measure of the best player, and Most Improved rewards change rather than quality. Award bonuses are kept modest relative to the stats score for this reason.
VORP approximation: True VORP (Basketball Reference) is not available via the NBA's API. The per_game_score metric is a proxy that correlates strongly with VORP but is not equivalent to it. It does not account for pace, usage rate, or position scarcity.
Franchise continuity: Relocated teams are merged under their current abbreviation (e.g. NJN → BKN). Charlotte uses a single CHA abbreviation across both the Bobcats and Hornets eras.
