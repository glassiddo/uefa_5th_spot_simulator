UEFA Coefficient Simulator — Claude MD (Code Generation Spec)
ROLE

You are a senior full-stack engineer. Your task is to generate a production-grade application that simulates UEFA association and club coefficient rankings under user-defined match outcomes, strictly implementing UEFA Annex D rules (2025/26).

You must:

    Produce working Python backend + JavaScript frontend code

    Ensure correctness of coefficient logic per specification

    Separate computation engine from UI

    Avoid placeholders where logic is required (especially coefficient calculations)

1. SYSTEM ARCHITECTURE

Generate a full-stack application with:
Backend

    Python 3.11+

    FastAPI

    Pydantic models for validation

    Stateless simulation engine (core requirement)

    Optional caching layer for UEFA data snapshots

Frontend

    React (TypeScript preferred)

    Minimal UI (tables + forms + scenario controls)

    Chart visualization (optional but recommended)

Data Flow

    Backend fetches UEFA data (or loads cached snapshot)

    User submits “what-if” match results

    Backend runs simulation engine

    Frontend renders updated coefficient tables + qualification outcomes

2. CORE DATA MODEL (MUST IMPLEMENT)

Define the following entities in Python:

Association:
    id: str
    name: str
    clubs: List[Club]
    season_coefficients: Dict[int, float]  # season -> coefficient

Club:
    id: str
    name: str
    association_id: str
    season_points: Dict[int, float]
    club_coefficients: List[float]  # last 5 seasons
    revenue_coefficients: List[float]  # last 10 seasons

Match:
    id: str
    competition: Literal["UCL", "UEL", "UECL"]
    stage: Literal["qualifying", "league", "knockout", "final"]
    home_team: str
    away_team: str
    home_score: int
    away_score: int

3. COEFFICIENT ENGINE (CRITICAL)

Implement a pure module:

/engine/coefficient_engine.py

It must implement Annex D exactly.
3.1 Match Points Rules
League phase and onwards:

    Win = 2 points

    Draw = 1 point

    Loss = 0 points

Qualifying / Play-offs:

    Win = 1 point

    Draw = 0.5 points

    Loss = 0 points

3.2 Competition-Specific Rules
Conference League qualifying elimination bonuses:

    Q1 exit = 1.0

    Q2 exit = 1.5

    Q3 exit = 2.0

    Play-off exit = 2.5

3.3 Bonus Points (D.5)

Implement table-driven lookup:

    UCL: 12.0 → 6.0 descending by rank

    UEL: 6.0 → 0.25

    UECL: 4.0 → 0.125

Plus knockout progression bonuses:

    UCL: 1.5 per round

    UEL: 1.0 per round

    UECL: 0.5 per round

3.4 Association Coefficient Formula

For each season:

association_coefficient =
    total_club_points_in_season / number_of_clubs_entered

IMPORTANT:

    Include ALL clubs from association

    Apply UEFA rounding rule: truncate/compute to 3 decimals (no rounding up)

3.5 Club Coefficient Formula

club_coefficient =
max(
    sum(last_5_seasons),
    0.2 * association_5_year_coefficient
)

Same for revenue coefficient using 10-year window.
3.6 Tie-breakers

Implement deterministic sorting:

    Most recent season coefficient

    Next most recent

    Association coefficient

    Domestic league position (if available)

4. SIMULATION ENGINE

Create:

/engine/simulation.py

Responsibilities:

    Accept baseline UEFA dataset

    Apply user-modified match results

    Recompute:

        Match outcomes → points

        Club coefficients

        Association coefficients

        Rankings

    Return full ranked table

Must support:

simulate(matches: List[Match]) -> SimulationResult

Where:

SimulationResult:
    association_rankings: List[Association]
    club_rankings: List[Club]
    fifth_champions_league_spot_holder: str

5. UEFA DATA INGESTION MODULE

Create:

/data/uefa_fetcher.py

Requirements:

    Fetch current competition data from UEFA website OR cached JSON fallback

    Normalize into Match objects

    Provide:

fetch_current_state() -> List[Match]

Also implement:

    refresh_cache() manual trigger

If scraping is required:

    Use requests + BeautifulSoup

    Do NOT rely on unofficial APIs

6. BACKEND API (FASTAPI)

Create endpoints:
GET /

Health check
GET /data

Returns current UEFA dataset snapshot
POST /simulate

Input:

{
  "matches": [Match]
}

Output:

SimulationResult

POST /refresh

Triggers UEFA data refresh
7. FRONTEND (REACT + TYPESCRIPT)

Generate:
Pages
1. Dashboard

    Current association rankings table

    Highlight “5th UCL spot”

2. Simulation Builder

    Add/edit match results

    Dropdown:

        Competition (UCL/UEL/UECL)

        Stage

    Score inputs

3. Results View

    Before vs after comparison

    Ranking deltas

Components

    MatchInputForm

    AssociationTable

    SimulationControls

    RankingDiffViewer

8. VISUALIZATION (OPTIONAL BUT DESIRED)

Use:

    Chart.js or Recharts

Show:

    Bar chart of association coefficients

    Delta changes after simulation

9. IMPLEMENTATION ORDER (IMPORTANT)

Claude must generate code in this sequence:
STEP 1

Generate backend project structure
STEP 2

Implement data models (Pydantic + domain objects)
STEP 3

Implement coefficient_engine.py (core logic first)
STEP 4

Implement simulation.py
STEP 5

Implement UEFA data fetcher module
STEP 6

Build FastAPI endpoints
STEP 7

Generate React frontend scaffold
STEP 8

Implement UI components
STEP 9

Wire frontend → backend API calls
STEP 10

Add sample dataset + test simulation scenario
10. TESTING REQUIREMENTS

Include unit tests for:

    Match point calculation

    Association coefficient aggregation

    Club coefficient max-rule logic

    Tie-breaking ordering

    Simulation consistency

Use pytest.
11. CRITICAL CONSTRAINTS

    All coefficient logic must strictly follow Annex D provided rules

    No approximations in point systems

    All results must be reproducible given identical inputs

    No hidden state in simulation engine

    Separation of concerns is mandatory

OUTPUT FORMAT EXPECTATION

Claude must output:

    Full project folder structure

    All backend code

    All frontend code

    Minimal run instructions

No pseudocode unless explicitly required for explanation.
