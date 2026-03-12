"""Real-time F1 data from public APIs. No auth needed."""
import httpx

ERGAST_BASE = "https://api.jolpi.ca/ergast/f1"  # community Ergast mirror
OPENF1_BASE = "https://api.openf1.org/v1"


async def get_driver_standings(year: int = 2025) -> list[dict]:
    """Current WDC standings."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{ERGAST_BASE}/{year}/driverstandings/?format=json")
            r.raise_for_status()
            data = r.json()
            standings = data["MRData"]["StandingsTable"]["StandingsLists"]
            if not standings:
                return []
            return [{
                "position": int(s["position"]),
                "driver": s["Driver"]["code"] if "code" in s["Driver"] else s["Driver"]["familyName"][:3].upper(),
                "name": f"{s['Driver']['givenName']} {s['Driver']['familyName']}",
                "team": s["Constructors"][0]["name"] if s["Constructors"] else "",
                "points": float(s["points"]),
                "wins": int(s["wins"]),
            } for s in standings[0]["DriverStandings"]]
    except Exception as e:
        return [{"error": str(e)}]


async def get_constructor_standings(year: int = 2025) -> list[dict]:
    """Current WCC standings."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{ERGAST_BASE}/{year}/constructorstandings/?format=json")
            r.raise_for_status()
            data = r.json()
            standings = data["MRData"]["StandingsTable"]["StandingsLists"]
            if not standings:
                return []
            return [{
                "position": int(s["position"]),
                "team": s["Constructor"]["name"],
                "points": float(s["points"]),
                "wins": int(s["wins"]),
            } for s in standings[0]["ConstructorStandings"]]
    except Exception as e:
        return [{"error": str(e)}]


async def get_race_results(year: int, round_num: int) -> dict:
    """Results from a specific race."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{ERGAST_BASE}/{year}/{round_num}/results/?format=json")
            r.raise_for_status()
            data = r.json()
            races = data["MRData"]["RaceTable"]["Races"]
            if not races:
                return {"error": "No data"}
            race = races[0]
            return {
                "race": race["raceName"],
                "circuit": race["Circuit"]["circuitName"],
                "date": race["date"],
                "round": race["round"],
                "results": [{
                    "position": r["position"],
                    "driver": r["Driver"]["code"] if "code" in r["Driver"] else r["Driver"]["familyName"][:3].upper(),
                    "name": f"{r['Driver']['givenName']} {r['Driver']['familyName']}",
                    "team": r["Constructor"]["name"],
                    "time": r.get("Time", {}).get("time", r.get("status", "")),
                    "points": float(r["points"]),
                    "grid": r.get("grid", ""),
                } for r in race["Results"]]
            }
    except Exception as e:
        return {"error": str(e)}


async def get_last_race_results(year: int = 2025) -> dict:
    """Results from most recent race."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{ERGAST_BASE}/{year}/last/results/?format=json")
            r.raise_for_status()
            data = r.json()
            race = data["MRData"]["RaceTable"]["Races"][0]
            return {
                "race": race["raceName"],
                "circuit": race["Circuit"]["circuitName"],
                "date": race["date"],
                "results": [{
                    "position": r["position"],
                    "driver": r["Driver"]["code"] if "code" in r["Driver"] else r["Driver"]["familyName"][:3].upper(),
                    "name": f"{r['Driver']['givenName']} {r['Driver']['familyName']}",
                    "team": r["Constructor"]["name"],
                    "time": r.get("Time", {}).get("time", r.get("status", "")),
                    "points": float(r["points"]),
                } for r in race["Results"]]
            }
    except Exception as e:
        return {"error": str(e)}


async def get_qualifying_results(year: int = 2025, round_num: int = None) -> dict:
    """Get qualifying results."""
    try:
        round_str = str(round_num) if round_num else "last"
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{ERGAST_BASE}/{year}/{round_str}/qualifying/?format=json")
            r.raise_for_status()
            data = r.json()
            races = data["MRData"]["RaceTable"]["Races"]
            if not races:
                return {"grid": [], "race": "N/A"}
            race = races[0]
            return {
                "race": race["raceName"],
                "date": race["date"],
                "grid": [{
                    "position": int(q["position"]),
                    "driver": q["Driver"]["code"] if "code" in q["Driver"] else q["Driver"]["familyName"][:3].upper(),
                    "name": f"{q['Driver']['givenName']} {q['Driver']['familyName']}",
                    "team": q["Constructor"]["name"],
                    "q1": q.get("Q1", ""),
                    "q2": q.get("Q2", ""),
                    "q3": q.get("Q3", ""),
                } for q in race["QualifyingResults"]]
            }
    except Exception as e:
        return {"error": str(e)}


async def get_live_timing() -> list[dict]:
    """Get latest session data from OpenF1 (live during sessions)."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            # Get latest session
            r = await c.get(f"{OPENF1_BASE}/sessions?session_type=Race&limit=1&sort=-date_start")
            r.raise_for_status()
            sessions = r.json()
            if not sessions:
                return []
            session_key = sessions[0]["session_key"]
            
            # Get latest lap data
            r2 = await c.get(f"{OPENF1_BASE}/laps?session_key={session_key}&sort=-lap_number&limit=20")
            r2.raise_for_status()
            return r2.json()
    except Exception as e:
        return [{"error": str(e)}]


async def get_speed_traps(year: int = 2025) -> list[dict]:
    """Top speed data from OpenF1."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{OPENF1_BASE}/sessions?year={year}&session_type=Race&limit=1&sort=-date_start")
            r.raise_for_status()
            sessions = r.json()
            if not sessions:
                return []
            session_key = sessions[0]["session_key"]
            
            r2 = await c.get(f"{OPENF1_BASE}/car_data?session_key={session_key}&speed>=300&limit=50")
            r2.raise_for_status()
            return r2.json()
    except Exception as e:
        return [{"error": str(e)}]


# ═══════════════════════════════════════════════
# EXPANDED F1 DATA FOR NERD-SCALE HUB
# ═══════════════════════════════════════════════

async def get_season_races(year: int = 2025) -> list[dict]:
    """Get all races in a season with results."""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{ERGAST_BASE}/{year}/results/?format=json&limit=500")
            r.raise_for_status()
            data = r.json()
            races = data["MRData"]["RaceTable"]["Races"]
            out = []
            for race in races:
                results = race.get("Results", [])
                winner = results[0] if results else None
                out.append({
                    "round": int(race["round"]),
                    "name": race["raceName"],
                    "circuit": race["Circuit"]["circuitName"],
                    "country": race["Circuit"]["Location"]["country"],
                    "date": race["date"],
                    "winner": f"{winner['Driver']['givenName']} {winner['Driver']['familyName']}" if winner else None,
                    "winner_code": winner["Driver"].get("code", winner["Driver"]["familyName"][:3].upper()) if winner else None,
                    "winner_team": winner["Constructor"]["name"] if winner else None,
                    "podium": [
                        {
                            "position": int(r["position"]),
                            "driver": r["Driver"].get("code", r["Driver"]["familyName"][:3].upper()),
                            "name": f"{r['Driver']['givenName']} {r['Driver']['familyName']}",
                            "team": r["Constructor"]["name"],
                            "grid": int(r.get("grid", 0)),
                        }
                        for r in results[:3]
                    ],
                    "dnf_count": sum(1 for r in results if r.get("status") not in ["Finished", "+1 Lap", "+2 Laps", "+3 Laps"]),
                    "total_drivers": len(results),
                })
            return out
    except Exception as e:
        return [{"error": str(e)}]


async def get_driver_race_history(year: int = 2025) -> list[dict]:
    """Per-driver per-race finishing positions for the whole season."""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{ERGAST_BASE}/{year}/results/?format=json&limit=500")
            r.raise_for_status()
            data = r.json()
            races = data["MRData"]["RaceTable"]["Races"]
            driver_history = {}
            for race in races:
                rd = int(race["round"])
                race_name = race["raceName"].replace(" Grand Prix", "").replace(" GP", "")
                for res in race.get("Results", []):
                    code = res["Driver"].get("code", res["Driver"]["familyName"][:3].upper())
                    name = f"{res['Driver']['givenName']} {res['Driver']['familyName']}"
                    team = res["Constructor"]["name"]
                    if code not in driver_history:
                        driver_history[code] = {"code": code, "name": name, "team": team, "races": []}
                    pos = int(res["position"]) if res["position"].isdigit() else 20
                    driver_history[code]["races"].append({
                        "round": rd, "race": race_name, "position": pos,
                        "grid": int(res.get("grid", 0)),
                        "points": float(res["points"]),
                        "status": res.get("status", ""),
                    })
            return list(driver_history.values())
    except Exception as e:
        return [{"error": str(e)}]


async def get_qualifying_pace(year: int = 2025) -> list[dict]:
    """Qualifying head-to-head data for all rounds."""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            all_quali = []
            # Get all qualifying results at once
            r = await c.get(f"{ERGAST_BASE}/{year}/qualifying/?format=json&limit=600")
            r.raise_for_status()
            data = r.json()
            races = data["MRData"]["RaceTable"]["Races"]
            team_battles = {}
            for race in races:
                rd = int(race["round"])
                team_drivers = {}
                for q in race.get("QualifyingResults", []):
                    team = q["Constructor"]["name"]
                    code = q["Driver"].get("code", q["Driver"]["familyName"][:3].upper())
                    pos = int(q["position"])
                    if team not in team_drivers:
                        team_drivers[team] = []
                    team_drivers[team].append({"code": code, "position": pos, "round": rd})
                for team, drivers in team_drivers.items():
                    if len(drivers) >= 2:
                        d1, d2 = sorted(drivers, key=lambda x: x["code"])
                        key = f"{d1['code']}-{d2['code']}"
                        if key not in team_battles:
                            team_battles[key] = {"driver1": d1["code"], "driver2": d2["code"], "team": team, "rounds": [], "d1_wins": 0, "d2_wins": 0}
                        team_battles[key]["rounds"].append({
                            "round": rd, "d1_pos": d1["position"], "d2_pos": d2["position"]
                        })
                        if d1["position"] < d2["position"]:
                            team_battles[key]["d1_wins"] += 1
                        else:
                            team_battles[key]["d2_wins"] += 1
            return list(team_battles.values())
    except Exception as e:
        return [{"error": str(e)}]
