NBA Draft Quality Analysis (2010–2023)
Ranks all 30 NBA teams by the quality of players they drafted between 2010 and 2023, using a composite scoring model built on career stats, pick position, and individual awards.

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

Limitations
Draft-night trades: Credit is given to the selecting team, not the team that ultimately developed the player. Kawhi Leonard (Indiana → San Antonio), Luka Dončić (Atlanta → Dallas), and Rudy Gobert (Denver → Utah) are all credited to their selecting franchise. This measures talent identification, not player development.
Recent draft classes: Players from 2021–2023 have played 2–4 seasons at most. Their scores are systematically lower than those of veterans, which understates their eventual value. Rankings will shift as these players develop.
VORP approximation: True VORP (Basketball Reference) is not available via the NBA's API. The per_game_score metric is a proxy that correlates strongly with VORP but is not equivalent to it. It does not account for pace, usage rate, or position scarcity.
Franchise continuity: Relocated teams are merged under their current abbreviation (e.g. NJN → BKN). Charlotte uses a single CHA abbreviation across both the Bobcats and Hornets eras.
