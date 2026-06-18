#!/usr/bin/env python3
"""
Expanded Sports Data Pools

This module provides expanded, diverse pools for sports data generation,
designed to minimize bias and maximize global coverage.

Coverage:
- Multiple sports types (football, basketball, tennis, cricket, rugby, etc.)
- Different competition levels (Olympics, World Cups, leagues)
- Global coverage across all continents
- Various time periods (historical and modern)
"""

from typing import List, Dict, Set
import random


class ExpandedSportsPools:
    """
    大规模体育数据池 - 覆盖全球、多类型、多赛事
    Designed to minimize bias and maximize diversity
    """

    # ========== SPORT TYPES AND CATEGORIES ==========

    SPORTS_TYPES = {
        "team_sports": [
            # Football (Soccer)
            "football", "soccer", "association football",
            # American Football
            "american football", "gridiron football",
            # Basketball
            "basketball", "hoops",
            # Baseball/Softball
            "baseball", "softball",
            # Cricket
            "cricket", "test cricket", "one day cricket", "twenty20 cricket",
            # Rugby
            "rugby union", "rugby league", "rugby sevens",
            # Hockey
            "field hockey", "ice hockey",
            # Volleyball
            "volleyball", "beach volleyball",
            # Handball
            "team handball", "handball",
            # Others
            "water polo", "futsal", "beach soccer", "korfball"
        ],
        "individual_sports": [
            # Racquet sports
            "tennis", "table tennis", "badminton", "squash", "racquetball",
            "pickleball", "padel tennis",
            # Combat sports - Expanded
            "boxing", "wrestling", "judo", "taekwondo", "karate", "fencing",
            "mma", "mixed martial arts", "ufc", "ultimate fighting championship",
            "bjj", "brazilian jiu-jitsu", "muay thai", "kickboxing",
            "sambo", "krav maga", "kung fu", "wushu", "sumo wrestling",
            "pankration", "pancrase", "shooto", "one championship",
            # Athletics/Track and Field
            "athletics", "track and field", "marathon", "sprinting", "distance running",
            "long jump", "high jump", "shot put", "discus", "javelin", "pole vault",
            "cross country running", "steeplechase", "heptathlon", "decathlon",
            # Aquatic sports
            "swimming", "diving", "synchronized swimming", "water skiing",
            "open water swimming", "artistic swimming",
            # Cycling
            "road cycling", "track cycling", "mountain biking", "bmx",
            "cyclocross", "gran fondo", "tour de france", "giro d'italia", "vuelta a espana",
            # Golf
            "golf", "mini golf", "disc golf", "pga tour", "european tour",
            "masters tournament", "us open", "the open championship",
            # Winter sports
            "alpine skiing", "cross-country skiing", "figure skating", "speed skating",
            "short track speed skating", "curling", "snowboarding", "ski jumping",
            "nordic combined", "freestyle skiing", "biathlon",
            # Motorsports
            "formula 1", "formula e", "motogp", "nascar", "indycar", "rallying",
            "wrc", "world rally championship", "world endurance championship",
            "dtm", "super gt", "v8 supercars", "touring car racing",
            # Others
            "archery", "shooting", "equestrian", "gymnastics", "rowing", "canoeing", "kayaking",
            "surfing", "skateboarding", "climbing", "triathlon", "biathlon",
            "darts", "bowling", "billiards", "snooker", "pool", "carom",
            "powerlifting", "weightlifting", "strongman", "crossfit"
        ],
        "esports": [
            # MOBA games
            "league of legends", "lol", "dota 2", "dota", "heroes of the storm",
            # FPS games
            "counter strike", "cs go", "valorant", "overwatch", "call of duty",
            "rainbow six siege", "apex legends", "fortnite",
            # Battle Arena
            "arena of valor", "mobile legends", "wild rift",
            # Strategy games
            "starcraft ii", "age of empires", "warcraft iii",
            # Fighting games
            "street fighter", "tekken", "king of fighters", "guilty gear",
            "super smash bros", "mortal kombat",
            # Sports simulation
            "fifa", "nba 2k", "mlb the show", "nfl madden", "nhl",
            "rocket league", "gran turismo", "forza motorsport",
            # Battle Royale
            "pubg", "pubg mobile", "free fire",
            # Card games
            "hearthstone", "magic the gathering arena", "gwent",
            # Others
            "world of warcraft", "runeterra"
        ]
    }

    # ========== COMPETITIONS AND EVENTS ==========

    COMPETITIONS = {
        "multi_sport_events": [
            # Summer Olympics
            "Summer Olympics", "Olympic Games", "Olympics",
            "Summer Paralympics", "Olympic Summer Games",
            # Winter Olympics
            "Winter Olympics", "Winter Olympic Games", "Winter Paralympics",
            # Regional multi-sport events
            "Commonwealth Games", "Asian Games", "Pan American Games",
            "African Games", "European Games", "Pacific Games",
            "Mediterranean Games", "World Games", "Universiade"
        ],
        "world_championships": [
            "FIFA World Cup", "FIFA Women's World Cup",
            "Basketball World Cup", "FIBA Basketball World Cup",
            "Rugby World Cup", "Rugby World Championship",
            "Cricket World Cup", "ICC Cricket World Cup",
            "World Athletics Championships", "World Championships in Athletics",
            "FINA World Aquatics Championships",
            "UCI Cycling World Championships",
            "ITF Tennis Grand Slams", "tennis grand slams",
            "World Figure Skating Championships",
            "FIS Alpine World Skiing Championships",
            "Formula 1 World Championship", "F1 championship",
            "World Baseball Classic", "WBC Classic"
        ],
        "professional_leagues": [
            # Football/Soccer
            "Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1",
            "Major League Soccer", "MLS", "Chinese Super League", "J-League",
            "Campeonato Brasileiro Serie A", "Liga MX", "A-League",
            # Basketball
            "NBA", "WNBA", "EuroLeague", "Liga ACB",
            "Chinese Basketball Association", "CBA",
            # Baseball
            "MLB", "Major League Baseball", "Nippon Professional Baseball", "NPB",
            "KBO League", "KBO",
            # Ice Hockey
            "NHL", "KHL", "SHL",
            # Rugby
            "Six Nations Championship", "The Rugby Championship",
            "Super Rugby", "English Premiership",
            # Other
            "ATP Tour", "WTA Tour", "PGA Tour", "LPGA Tour",
            "Formula 1", "MotoGP", "World Rally Championship", "WRC"
        ]
    }

    # ========== SPORTS ENTITIES ==========

    SPORTS_ENTITIES = {
        "roles": [
            # Athletes
            "athlete", "player", "sportsperson", "competitor", "contestant",
            "champion", "medalist", "olympian", "paralympian",
            # Team positions
            "forward", "midfielder", "defender", "goalkeeper", "striker",
            "pitcher", "catcher", "batter", "bowler",
            "point guard", "shooting guard", "small forward", "power forward", "center",
            # Officials
            "referee", "umpire", "judge", "linesman", "official",
            # Coaches and staff
            "coach", "manager", "trainer", "instructor",
            # Teams
            "team", "club", "franchise", "squad", "lineup", "roster",
            # Organizations
            "federation", "association", "league", "confederation", "union"
        ],
        "venues": [
            # Stadium types
            "stadium", "arena", "venue", "ground", "field", "court",
            "racetrack", "circuit", "course", "pool",
            # Specific venues
            "Olympic Stadium", "Wembley Stadium", "Madison Square Garden",
            "Camp Nou", "Santiago Bernabéu", "Old Trafford", "San Siro"
        ],
        "events": [
            "match", "game", "fixture", "tournament", "championship",
            "Olympics", "World Cup", "Grand Prix", "meeting", "competition",
            "race", "final", "semifinal", "quarterfinal", "qualifier"
        ]
    }

    # ========== GEOGRAPHIC REGIONS FOR SPORTS ==========

    SPORTS_REGIONS = {
        "global_associations": [
            "FIFA", "IOC", "IAAF", "FINA", "UCI", "FIBA",
            "ICC", "World Rugby", "FIVB", "ITF", "FIH"
        ],
        "continental_federations": [
            # Football
            "UEFA", "CONMEBOL", "CAF", "AFC", "OFC",
            # Basketball
            "FIBA Americas", "FIBA Europe", "FIBA Asia", "FIBA Africa",
            # Other
            "World Athletics", "World Aquatics", "UCI", "ITF"
        ],
        "countries_with_strong_sports": [
            # Football powers
            "Brazil", "Germany", "Argentina", "France", "Spain", "Italy", "England",
            "Netherlands", "Portugal", "Croatia", "Uruguay",
            # Basketball powers
            "USA", "Spain", "Serbia", "Argentina", "France", "Greece", "Lithuania",
            # Cricket powers
            "India", "Australia", "England", "South Africa", "Pakistan", "West Indies",
            # Rugby powers
            "New Zealand", "South Africa", "England", "Ireland", "Wales", "France",
            # Other
            "Jamaica", "Kenya", "Ethiopia", "Norway", "Netherlands", "China", "Russia",
            "South Korea", "Japan", "Canada", "Mexico"
        ]
    }

    # ========== WIKIPEDIA SPORTS CATEGORIES ==========

    WIKIPEDIA_CATEGORIES = {
        # By sport type
        "team_sports": [
            "Category:Association_football",
            "Category:Basketball",
            "Category:Baseball",
            "Category:Cricket",
            "Category:Rugby_union",
            "Category:American_football",
            "Category:Ice_hockey",
            "Category:Field_hockey",
            "Category:Volleyball",
            "Category:Handball",
            "Category:Water_polo"
        ],
        "individual_sports": [
            "Category:Tennis",
            "Category:Golf",
            "Category:Boxing",
            "Category:Swimming",
            "Category:Athletics",
            "Category:Figure_skating",
            "Category:Formula_One",
            "Category:Cycling",
            "Category:Table_tennis",
            "Category:Badminton",
            "Category:Shooting",
            "Category:Archery"
        ],
        # By competition type
        "olympics": [
            "Category:Olympic_games",
            "Category:Summer_Olympic_games",
            "Category:Winter_Olympic_games",
            "Category:Olympics",
            "Category:Olympic_competitors",
            "Category:Olympic_medalists"
        ],
        "world_cups": [
            "Category:FIFA_World_Cup",
            "Category:Cricket_World_Cup",
            "Category:Rugby_World_Cup",
            "Category:Basketball_World_Cup",
            "Category:World_Athletics_Championships",
            "Category:FINA_World_Championships"
        ],
        # By geography
        "by_geography": [
            "Category:Sports_in_Africa",
            "Category:Sports_in_Asia",
            "Category:Sports_in_Europe",
            "Category:Sports_in_North_America",
            "Category:Sports_in_South_America",
            "Category:Sports_in_Oceania"
        ],
        # By organization
        "organizations": [
            "Category:FIFA",
            "Category:International_Olympic_Committee",
            "Category:World_Athletics",
            "Category:National_Basketball_Association",
            "Category:Formula_One",
            "Category:UEFA",
            "Category:CONMEBOL"
        ],
        # Athletes and teams
        "people": [
            "Category:Olympic_competitors_for_country",
            "Category:Sportspeople_from_country"
        ]
    }

    # ========== TIME PERIODS FOR SPORTS ==========

    TIME_PERIODS = {
        "ancient": [
            "Ancient Olympic Games", "Ancient Greek athletics",
            "Roman gladiatorial games", "Ancient chariot racing"
        ],
        "19th_century": [
            "19th century sports", "Victorian era sports",
            "Early modern Olympics", "Traditional sports"
        ],
        "early_20th": [
            "Early 20th century sports", "Pre-WWII sports",
            "Golden Age of sport", "Interwar period sports"
        ],
        "post_war": [
            "Post-war sports", "1950s sports", "1960s sports",
            "1970s sports", "1980s sports", "1990s sports"
        ],
        "modern": [
            "21st century sports", "2000s sports", "2010s sports",
            "Contemporary sports", "Modern athletics"
        ]
    }

    # ========== FAMOUS SPORTS FIGURES AND MOMENTS ==========

    FAMOUS_ATHLETES = {
        "track_field": [
            "Usain Bolt", "Carl Lewis", "Jesse Owens", "Paavo Nurmi",
            "Haile Gebrselassie", "Kenenisa Bekele", "Mo Farah",
            "Allyson Felix", "Shelly-Ann Fraser-Pryce", "Florence Griffith-Joyner"
        ],
        "swimming": [
            "Michael Phelps", "Mark Spitz", "Ian Thorpe", "Katie Ledecky",
            "Missy Franklin", "Ryan Lochte", "Caeleb Dressel"
        ],
        "tennis": [
            "Roger Federer", "Rafael Nadal", "Novak Djokovic",
            "Serena Williams", "Steffi Graf", "Martina Navratilova",
            "Margaret Court", "Billie Jean King"
        ],
        "golf": [
            "Tiger Woods", "Jack Nicklaus", "Arnold Palmer", "Gary Player",
            "Rory McIlroy", "Jordan Spieth", "Brooks Koepka"
        ],
        "boxing": [
            "Muhammad Ali", "Mike Tyson", "Floyd Mayweather", "Manny Pacquiao",
            "Sugar Ray Robinson", "Joe Louis", "Rocky Marciano"
        ],
        "football": [
            "Pelé", "Diego Maradona", "Lionel Messi", "Cristiano Ronaldo",
            "Johan Cruyff", "Franz Beckenbauer", "Zinedine Zidane",
            "Ronaldinho", "Neymar", "Kylian Mbappé"
        ],
        "basketball": [
            "Michael Jordan", "LeBron James", "Kobe Bryant", "Shaquille O'Neal",
            "Kareem Abdul-Jabbar", "Larry Bird", "Magic Johnson", "Stephen Curry"
        ],
        "motorsports": [
            "Michael Schumacher", "Lewis Hamilton", "Ayrton Senna", "Dale Earnhardt",
            "Valentino Rossi", "Sebastian Vettel", "Max Verstappen"
        ],
        "gymnastics": [
            "Simone Biles", "Nadia Comaneci", "Larisa Latynina", "Olga Korbut",
            "Mary Lou Retton", "Vitaly Scherbo", "Kohei Uchimura"
        ]
    }

    FAMOUS_TEAMS = {
        "football": [
            "Real Madrid", "Barcelona", "Manchester United", "Bayern Munich",
            "AC Milan", "Liverpool", "Ajax", "Benfica",
            "São Paulo", "River Plate", "Boca Juniors",
            "Al Ahly", "Kaizer Chiefs", "Sydney FC"
        ],
        "basketball": [
            "Los Angeles Lakers", "Boston Celtics", "Chicago Bulls", "Golden State Warriors",
            "Miami Heat", "San Antonio Spurs", "Chicago Bulls (1960s)",
            "Real Madrid Baloncesto", "FC Barcelona Regal", "Maccabi Tel Aviv"
        ],
        "baseball": [
            "New York Yankees", "Los Angeles Dodgers", "Boston Red Sox",
            "Chicago Cubs", "San Francisco Giants", "St. Louis Cardinals"
        ],
        "rugby": [
            "New Zealand All Blacks", "South Africa Springboks",
            "England national rugby union team", "Ireland national rugby team",
            "British and Irish Lions", "Barbarians"
        ]
    }

    # ========== FAMOUS VENUES ==========

    FAMOUS_VENUES = {
        "stadiums": [
            "Camp Nou", "Santiago Bernabéu", "Wembley Stadium", "Old Trafford",
            "San Siro", "Signal Iduna Park", "Anfield", "Old Trafford (cricket)",
            "Melbourne Cricket Ground", "Lord's", "Eden Gardens",
            "Yankee Stadium", "Madison Square Garden", "Boston Garden",
            "Olympic Stadium (Berlin)", "Panathenaic Stadium",
            "Maracanã", "Estadio Azteca", "Rose Bowl"
        ],
        "circuits": [
            "Circuit de Monaco", "Circuit de Spa-Francorchamps", "Silverstone",
            "Monza", "Nürburgring", "Suzuka", "Indianapolis Motor Speedway",
            "Daytona International Speedway", "Circuit of the Americas"
        ],
        "courses": [
            "Augusta National", "St Andrews", "Pebble Beach",
            "Royal Birkdale", "Royal St George's", "Carnoustie"
        ]
    }

    # ========== HISTORIC SPORTS MOMENTS ==========

    HISTORIC_MOMENTS = [
        "Jesse Owens 1936 Berlin Olympics",
        "Miracle on Ice 1980",
        "Hand of God goal 1986",
        "Usain Bolt 2008/2009/2012/2016 Olympics",
        "Brazil 1-7 Germany 2014 World Cup",
        "France 4-2 Croatia 2022 World Cup final",
        "Muhammad Ali vs Joe Frazier 1971 Fight of the Century",
        "Michael Phelps 2008 Beijing Olympics (8 gold medals)",
        "Usain Bolt 100m world record 2009",
        " Lance Armstrong comeback (1999-2005)"
    ]

    # ========== OFFICIAL SPORTS WEBSITES AND APIs ==========
    # Authoritative data sources for sports statistics, records, and historical data

    OFFICIAL_WEBSITES = {
        # Football/Soccer
        "football": [
            "https://www.fifa.com",  # FIFA official site
            "https://www.uefa.com",  # European football
            "https://www.premierleague.com",  # English Premier League
            "https://www.laliga.com",  # Spanish La Liga
            "https://www.bundesliga.com",  # German Bundesliga
            "https://www.seriea.it",  # Italian Serie A
            "https://www.ligue1.com",  # French Ligue 1
            "https://www.mlssoccer.com",  # MLS
            "https://www.fcbarcelona.com",  # Barcelona official
            "https://www.realmadrid.com",  # Real Madrid official
        ],
        # Basketball
        "basketball": [
            "https://www.nba.com",  # NBA official
            "https://www.fiba.basketball",  # FIBA official
            "https://www.euroleague.net",  # EuroLeague
            "https://www.basketball.eurobasket.com",  # EuroBasket
        ],
        # MMA/Combat Sports
        "mma": [
            "https://www.ufc.com",  # UFC official
            "https://www.bellator.com",  # Bellator MMA
            "https://www.onefc.com",  # ONE Championship
            "https://www.pflmma.com",  # Professional Fighters League
            "https://www.boxrec.com",  # Boxing records
            "https://www.sherdog.com",  # MMA stats and records
        ],
        # Tennis
        "tennis": [
            "https://www.atptour.com",  # ATP Tour (men's)
            "https://www.wtatennis.com",  # WTA (women's)
            "https://www.itftennis.com",  # ITF official
            "https://www.wimbledon.com",  # Wimbledon
            "https://www.rolandgarros.com",  # French Open
            "https://www.usopen.org",  # US Open
            "https://www.ausopen.com",  # Australian Open
        ],
        # Olympics
        "olympics": [
            "https://www.olympics.com",  # IOC official site
            "https://www.worldathletics.org",  # World Athletics (IAAF)
            "https://www.fina.org",  # Aquatics
            "https://www.uci.org",  # Cycling
            "https://www.fig-gymnastics.com",  # Gymnastics
        ],
        # Motorsports
        "motorsports": [
            "https://www.formula1.com",  # F1 official
            "https://www.motogp.com",  # MotoGP
            "https://www.nascar.com",  # NASCAR
            "https://www.indycar.com",  # IndyCar
            "https://www.wrc.com",  # World Rally Championship
            "https://www.imsa.com",  # IMSA sports car racing
        ],
        # Golf
        "golf": [
            "https://www.pgatour.com",  # PGA Tour
            "https://www.randa.org",  # The R&A (governor of golf)
            "https://www.usga.org",  # US Golf Association
            "https://www.dpworldtour.com",  # European Tour
            "https://www.lpga.com",  # LPGA (women's)
        ],
        # Cricket
        "cricket": [
            "https://www.icc-cricket.com",  # ICC official
            "https://www.espncricinfo.com",  # Comprehensive cricket stats
            "https://www.ecb.co.uk",  # England & Wales Cricket Board
            "https://www.bcci.tv",  # Indian cricket board
        ],
        # Esports
        "esports": [
            "https://esportscharts.com",  # Esports stats and analytics
            "https://www.liquipedia.net",  # Esports wiki (like Wikipedia for esports)
            "https://www.hltv.org",  # CS:GO stats
            "https://www.op.gg",  # League of Legends stats
            "https://www.dotabuff.com",  # Dota 2 stats
            "https://www.esportsearnings.com",  # Player earnings and prize pools
            "https://www.lolesports.com",  # Official League of Legends esports
            "https://www.valorantesports.com",  # Official Valorant esports
        ],
        # Baseball
        "baseball": [
            "https://www.mlb.com",  # MLB official
            "https://www.mlb.com/stats",  # MLB stats
            "https://www.npb.jp",  # Japanese baseball
            "https://www.kbo.or.kr",  # Korean baseball
        ],
        # American Football
        "american_football": [
            "https://www.nfl.com",  # NFL official
            "https://www.pro-football-reference.com",  # Comprehensive NFL stats
        ],
        # Hockey
        "hockey": [
            "https://www.nhl.com",  # NHL official
            "https://www.iihf.com",  # International Ice Hockey Federation
        ],
        # Athletics/Track
        "athletics": [
            "https://www.worldathletics.org",  # World Athletics (formerly IAAF)
            "https://www.tfrrs.org",  # U.S. track and field stats
            "https://www.alltime-athletics.com",  # Historical athletics records
        ],
        # Swimming
        "swimming": [
            "https://www.fina.org",  # World Aquatics (formerly FINA)
            "https://www.usaswimming.org",  # USA Swimming
            "https://www.swimswam.com",  # Swimming news and stats
        ],
        # Cycling
        "cycling": [
            "https://www.uci.org",  # UCI (Union Cycliste Internationale)
            "https://www.procyclingstats.com",  # Cycling statistics
            "https://www.cyclingarchives.com",  # Historical cycling data
        ],
        # Boxing
        "boxing": [
            "https://www.boxrec.com",  # Comprehensive boxing records
            "https://www.iboboxing.com",  # International Boxing Federation
            "https://www.wboxing.com",  # WBA boxing
        ],
        # Rugby
        "rugby": [
            "https://www.world.rugby",  # World Rugby (formerly IRB)
            "https://www.sixnationsrugby.com",  # Six Nations Championship
            "https://www.englandrugby.com",  # England Rugby
        ],
        # Volleyball
        "volleyball": [
            "https://www.fivb.com",  # International Volleyball Federation
            "https://www.cev.eu",  # European Volleyball Confederation
        ],
        # Handball
        "handball": [
            "https://www.ihf.info",  # International Handball Federation
        ],
        # Table Tennis
        "table_tennis": [
            "https://www.ittf.com",  # International Table Tennis Federation
        ],
        # Badminton
        "badminton": [
            "https://www.bwfbadminton.com",  # Badminton World Federation
        ],
    }

    # ========== SPORTS EQUIPMENT AND GEAR ==========

    EQUIPMENT = {
        "ball_games": [
            "football", "soccer ball", "basketball", "volleyball",
            "tennis ball", "cricket ball", "baseball", "rugby ball",
            "ping pong ball", "table tennis ball", "shuttlecock"
        ],
        "racket_sports": [
            "tennis racket", "badminton racket", "table tennis bat",
            "squash racket", "racquetball racket"
        ],
        "protective": [
            "helmet", "padding", "shin guards", "mouthguard",
            "goalkeeper gloves", "catcher's mask", "body armor"
        ],
        "other": [
            "golf club", "baseball bat", "cricket bat", "hockey stick",
            "ski", "snowboard", "bicycle", "surfboard", "skateboard"
        ]
    }

    # ========== ========== ==========

    @classmethod
    def get_all_categories(cls) -> List[str]:
        """获取所有Wikipedia体育分类"""
        all_cats = []
        for category_list in cls.WIKIPEDIA_CATEGORIES.values():
            all_cats.extend(category_list)
        return list(set(all_cats))  # Remove duplicates

    @classmethod
    def get_all_sports_types(cls) -> List[str]:
        """获取所有运动类型"""
        all_sports = []
        for sports_list in cls.SPORTS_TYPES.values():
            all_sports.extend(sports_list)
        return list(set(all_sports))

    @classmethod
    def get_all_competitions(cls) -> List[str]:
        """获取所有赛事"""
        all_comps = []
        for comp_list in cls.COMPETITIONS.values():
            all_comps.extend(comp_list)
        return list(set(all_comps))

    @classmethod
    def generate_random_combination(cls) -> Dict[str, str]:
        """
        生成随机的体育探索组合
        Returns: dict with sport, competition, role, region, time_period
        """
        # Random sport type
        all_sports = cls.get_all_sports_types()
        sport = random.choice(all_sports)

        # Random competition
        all_comps = cls.get_all_competitions()
        competition = random.choice(all_comps) if all_comps else ""

        # Random role
        role = random.choice(cls.SPORTS_ENTITIES["roles"])

        # Random region
        region = random.choice(cls.SPORTS_REGIONS["countries_with_strong_sports"])

        # Random time period
        time_period = random.choice(random.choice(list(cls.TIME_PERIODS.values())))

        return {
            "sport": sport,
            "competition": competition,
            "role": role,
            "region": region,
            "time_period": time_period
        }

    @classmethod
    def generate_search_queries(cls) -> List[str]:
        """生成多样化的体育搜索查询组合"""
        combinations = []

        # 1. Sport + Competition (e.g., "football World Cup")
        all_comps = cls.get_all_competitions()
        all_sports = cls.get_all_sports_types()
        if all_comps and all_sports:
            combinations.append(f"{random.choice(all_sports)} {random.choice(all_comps)}")

        # 2. Sport + Region (e.g., "basketball China")
        region = random.choice(cls.SPORTS_REGIONS["countries_with_strong_sports"])
        combinations.append(f"{random.choice(all_sports)} {region}")

        # 3. Athlete + Sport (e.g., "Michael Jordan basketball")
        category = random.choice(list(cls.FAMOUS_ATHLETES.keys()))
        athlete = random.choice(cls.FAMOUS_ATHLETES[category])
        combinations.append(f"{athlete} {category}")

        # 4. Team + Sport (e.g., "Real Madrid football")
        category = random.choice(list(cls.FAMOUS_TEAMS.keys()))
        team = random.choice(cls.FAMOUS_TEAMS[category])
        combinations.append(f"{team} {category}")

        # 5. Venue + Event (e.g., "Wembley Stadium FA Cup final")
        venue_type = random.choice(list(cls.FAMOUS_VENUES.keys()))
        venue = random.choice(cls.FAMOUS_VENUES[venue_type])
        event = random.choice(cls.SPORTS_ENTITIES["events"])
        combinations.append(f"{venue} {event}")

        # 6. Historic moment
        if cls.HISTORIC_MOMENTS:
            moment = random.choice(cls.HISTORIC_MOMENTS)
            combinations.append(moment)

        # 7. Equipment + Sport
        equipment = random.choice(cls.EQUIPMENT["ball_games"])
        combinations.append(f"{equipment} {random.choice(all_sports)}")

        return combinations


# ============================================================================
# STATISTICS AND TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("EXPANDED SPORTS POOLS - STATISTICS")
    print("=" * 70)

    pools = ExpandedSportsPools()

    print(f"\nSport types: {sum(len(v) for v in pools.SPORTS_TYPES.values())}")
    for sport_type, sports in pools.SPORTS_TYPES.items():
        unique_sports = len(set(sports))
        print(f"  - {sport_type}: {unique_sports} unique sports")

    print(f"\nCompetitions: {sum(len(v) for v in pools.COMPETITIONS.values())}")
    for comp_type, comps in pools.COMPETITIONS.items():
        unique_comps = len(set(comps))
        print(f"  - {comp_type}: {unique_comps} unique")

    print(f"\nWikipedia Categories: {len(pools.get_all_categories())}")

    print(f"\nFamous Athletes: {sum(len(v) for v in pools.FAMOUS_ATHLETES.values())}")
    for category, athletes in pools.FAMOUS_ATHLETES.items():
        print(f"  - {category}: {len(athletes)} athletes")

    print(f"\nFamous Teams: {sum(len(v) for v in pools.FAMOUS_TEAMS.values())}")
    for category, teams in pools.FAMOUS_TEAMS.items():
        print(f"  - {category}: {len(teams)} teams")

    print(f"\nFamous Venues: {sum(len(v) for v in pools.FAMOUS_VENUES.values())}")
    for venue_type, venues in pools.FAMOUS_VENUES.items():
        print(f"  - {venue_type}: {len(venues)} venues")

    print("\n" + "=" * 70)
    print("SAMPLE RANDOM COMBINATIONS")
    print("=" * 70)

    for i in range(5):
        combo = pools.generate_random_combination()
        print(f"\n[{i+1}] {combo['sport']} | {combo['competition']} | {combo['role']} | {combo['region']}")

    print("\n" + "=" * 70)
    print("SAMPLE SEARCH QUERIES")
    print("=" * 70)

    for i in range(5):
        queries = pools.generate_search_queries()
        for j, query in enumerate(queries):
            print(f"{j+1}. {query}")
        print()
