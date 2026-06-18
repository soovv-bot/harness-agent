#!/usr/bin/env python3
"""
Expanded Biography Data Pools

This module provides expanded, diverse pools for biography data generation,
covering various person types, professions, eras, and regions.

Coverage:
- All major professions and occupations
- Person types (politicians, scientists, artists, athletes, etc.)
- Global regions and nationalities
- Time periods (ancient to contemporary)
- Famous people by category
- Biographical concepts and terminology
"""

from typing import List, Dict
import random


# ============================================================================
# EXPANDED BIOGRAPHY POOLS
# ============================================================================

class ExpandedBiographyPools:
    """
    大规模传记数据池 - 覆盖全球、全时代、多种人物类型
    Designed to minimize bias and maximize diversity
    """

    # ========== PERSON TYPES / CATEGORIES ==========

    PERSON_CATEGORIES = {
        "political": [
            "Heads of State", "Presidents", "Prime Ministers", "Monarchs", "Royalty",
            "Revolutionaries", "Activists", "Diplomats", "Government Officials",
            "Political Leaders", "Founding Fathers", "Reformers", "Resistance Leaders"
        ],
        "business": [
            "Entrepreneurs", "CEOs", "Founders", "Investors", "Innovators",
            "Business Magnates", "Tech Founders", "Philanthropists", "Industrialists",
            "Venture Capitalists", "Wall Street Leaders", "Retail Pioneers"
        ],
        "scientific": [
            "Physicists", "Chemists", "Biologists", "Mathematicians", "Astronomers",
            "Medical Researchers", "Nobel Prize Scientists", "Inventors", "Engineers",
            "Computer Scientists", "Geneticists", "Environmental Scientists"
        ],
        "cultural": [
            "Painters", "Sculptors", "Writers", "Poets", "Playwrights", "Novelists",
            "Philosophers", "Composers", "Musicians", "Conductors", "Singers",
            "Film Directors", "Actors", "Architects", "Photographers", "Dancers",
            "Fashion Designers"
        ],
        "sports": [
            "Athletes", "Olympians", "World Champions", "Record Holders",
            "Team Captains", "Coaches", "Motorsports Drivers", "Tennis Players",
            "Football Players", "Basketball Players", "Baseball Players", "Soccer Players",
            "Swimmers", "Track and Field Athletes", "Gymnasts", "Boxers", "MMA Fighters"
        ],
        "social": [
            "Social Reformers", "Civil Rights Leaders", "Humanitarians",
            "Religious Leaders", "Spiritual Figures", "Feminists", "Labor Leaders",
            "Environmentalists", "Peace Activists", "Educators", "Journalists"
        ],
        "exploration": [
            "Explorers", "Pioneers", "Adventurers", "Mountaineers", "Aviators",
            "Astronauts", "Cosmonauts", "Space Explorers", "Sea Captains"
        ],
        "military": [
            "Generals", "Admirals", "Military Commanders", "War Heroes",
            "Strategists", "Veterans", "Resistance Fighters", "Freedom Fighters"
        ]
    }

    # ========== PROFESSIONS / OCCUPATIONS ==========

    PROFESSIONS = {
        "politics": [
            "President", "Prime Minister", "Chancellor", "Monarch", "Queen", "King",
            "Senator", "Congressman", "Member of Parliament", "Governor", "Mayor",
            "Diplomat", "Ambassador", "Secretary of State", "Foreign Minister",
            "Revolutionary", "Freedom Fighter", "Activist", "Protester"
        ],
        "business": [
            "CEO", "Chairman", "Founder", "Co-founder", "Entrepreneur", "Investor",
            "Venture Capitalist", "Angel Investor", "Hedge Fund Manager", "Banker",
            "Industrialist", "Manufacturer", "Retailer", "E-commerce Founder",
            "Tech Entrepreneur", "Philanthropist"
        ],
        "science": [
            "Physicist", "Chemist", "Biologist", "Mathematician", "Astronomer",
            "Physician", "Surgeon", "Medical Researcher", "Psychologist", "Neuroscientist",
            "Computer Scientist", "Software Engineer", "Data Scientist", "Engineer",
            "Inventor", "Nobel Laureate", "Professor", "Academic"
        ],
        "arts": [
            "Painter", "Sculptor", "Writer", "Author", "Poet", "Playwright", "Novelist",
            "Journalist", "Composer", "Musician", "Singer", "Conductor", "Director",
            "Actor", "Actress", "Producer", "Screenwriter", "Photographer",
            "Architect", "Fashion Designer", "Choreographer", "Dancer"
        ],
        "sports": [
            "Athlete", "Olympian", "Professional Player", "Coach", "Manager",
            "Quarterback", "Point Guard", "Striker", "Pitcher", "Goalkeeper",
            "Tennis Player", "Golfer", "Boxer", "MMA Fighter", "Race Car Driver"
        ],
        "other": [
            "Explorer", "Adventurer", "Missionary", "Clergy", "Priest", "Monk",
            "Nun", "Imam", "Rabbi", "Guru", "Philosopher", "Thinker", "Scholar"
        ]
    }

    # ========== ERAS / TIME PERIODS ==========

    ERAS = {
        "ancient": [
            "Ancient Egypt", "Ancient Greece", "Ancient Rome", "Ancient China",
            "Ancient India", "Mesopotamia", "Persian Empire", "Maya Civilization",
            "Han Dynasty", "Roman Empire", "Alexander the Great's Era"
        ],
        "medieval": [
            "Middle Ages", "Viking Age", "Islamic Golden Age", "Mongol Empire",
            "Song Dynasty", "Crusades", "Holy Roman Empire", "Byzantine Empire",
            "Tang Dynasty", "Ming Dynasty", "Ottoman Empire", "Feudal Japan"
        ],
        "early_modern": [
            "Renaissance", "Age of Exploration", "Reformation", "Enlightenment",
            "Age of Revolution", "Industrial Revolution", "Napoleonic Era",
            "Colonial Era", "Qing Dynasty", "Edo Period", "Mughal Empire"
        ],
        "modern_19th": [
            "Victorian Era", "Gilded Age", "American Civil War", "Meiji Restoration",
            "Unification of Italy", "Unification of Germany", "Belle Époque",
            "Progressive Era"
        ],
        "modern_20th": [
            "World War I Era", "Interwar Period", "World War II Era", "Cold War",
            "Civil Rights Movement", "Space Age", "Digital Revolution",
            "Post-Colonization", "Decolonization"
        ],
        "contemporary": [
            "Information Age", "Internet Era", "Social Media Era", "Globalization",
            "21st Century", "Post-9/11", "Digital Age", "AI Era"
        ]
    }

    # ========== REGIONS / NATIONALITIES ==========

    REGIONS = {
        "north_america": [
            "United States", "Canada", "Mexico", "American", "Canadian", "Mexican"
        ],
        "europe": [
            "United Kingdom", "France", "Germany", "Italy", "Spain", "Russia",
            "British", "French", "German", "Italian", "Spanish", "Russian",
            "European", "Western European", "Eastern European"
        ],
        "east_asia": [
            "China", "Japan", "South Korea", "Taiwan", "Chinese", "Japanese",
            "Korean", "East Asian"
        ],
        "south_asia": [
            "India", "Pakistan", "Bangladesh", "Sri Lanka", "Indian", "Pakistani",
            "Bangladeshi", "South Asian"
        ],
        "southeast_asia": [
            "Indonesia", "Thailand", "Vietnam", "Philippines", "Malaysia", "Singapore",
            "Southeast Asian"
        ],
        "middle_east": [
            "Saudi Arabia", "UAE", "Iran", "Turkey", "Israel", "Egypt", "Jordan",
            "Arab", "Persian", "Turkish", "Middle Eastern"
        ],
        "africa": [
            "Nigeria", "South Africa", "Kenya", "Ethiopia", "Ghana", "Nigerian",
            "South African", "Kenyan", "Ethiopian", "African", "Sub-Saharan African"
        ],
        "latin_america": [
            "Brazil", "Argentina", "Mexico", "Colombia", "Chile", "Peru", "Venezuela",
            "Brazilian", "Argentine", "Latin American", "Hispanic"
        ],
        "oceania": [
            "Australia", "New Zealand", "Australian", "New Zealander", "Oceanian"
        ]
    }

    # ========== FAMOUS PEOPLE BY CATEGORY ==========

    FAMOUS_PEOPLE = {
        "political_leaders": {
            "us_presidents": [
                "George Washington", "Abraham Lincoln", "Theodore Roosevelt",
                "Franklin D. Roosevelt", "John F. Kennedy", "Ronald Reagan",
                "Barack Obama", "Donald Trump", "Joe Biden"
            ],
            "world_leaders": [
                "Winston Churchill", "Charles de Gaulle", "Nelson Mandela",
                "Mahatma Gandhi", "Jawaharlal Nehru", "Mao Zedong", "Deng Xiaoping",
                "Vladimir Putin", "Angela Merkel", "Emmanuel Macron"
            ],
            "historical_figures": [
                "Julius Caesar", "Napoleon Bonaparte", "Alexander the Great",
                "Genghis Khan", "Queen Elizabeth I", "Catherine the Great",
                "Peter the Great", "Suleiman the Magnificent"
            ]
        },
        "business_leaders": {
            "tech_founders": [
                "Steve Jobs", "Bill Gates", "Mark Zuckerberg", "Larry Page", "Sergey Brin",
                "Elon Musk", "Jeff Bezos", "Jack Ma", "Pony Ma", "Zhang Yiming"
            ],
            "investors": [
                "Warren Buffett", "Charlie Munger", "Ray Dalio", "George Soros",
                "Peter Lynch", "Carl Icahn", "Jim Simons", "Ken Griffin"
            ],
            "industrialists": [
                "John D. Rockefeller", "Andrew Carnegie", "J.P. Morgan",
                "Henry Ford", "Cornelius Vanderbilt", "Andrew Mellon"
            ]
        },
        "scientists": {
            "physicists": [
                "Albert Einstein", "Isaac Newton", "Stephen Hawking", "Richard Feynman",
                "Niels Bohr", "Marie Curie", "Galileo Galilei", "Michael Faraday"
            ],
            "biologists": [
                "Charles Darwin", "Gregor Mendel", "James Watson", "Francis Crick",
                "Rosalind Franklin", "Louis Pasteur", "Alexander Fleming"
            ],
            "computer_pioneers": [
                "Alan Turing", "Ada Lovelace", "John von Neumann", "Claude Shannon",
                "Grace Hopper", "Donald Knuth", "Vint Cerf", "Tim Berners-Lee"
            ]
        },
        "artists": {
            "painters": [
                "Leonardo da Vinci", "Michelangelo", "Vincent van Gogh", "Pablo Picasso",
                "Claude Monet", "Rembrandt", "Salvador Dali", "Frida Kahlo"
            ],
            "writers": [
                "William Shakespeare", "Jane Austen", "Charles Dickens", "Mark Twain",
                "Leo Tolstoy", "Fyodor Dostoevsky", "Gabriel Garcia Marquez", "Haruki Murakami"
            ],
            "musicians": [
                "Ludwig van Beethoven", "Wolfgang Amadeus Mozart", "Johann Sebastian Bach",
                "Bob Dylan", "The Beatles", "Michael Jackson", "Madonna", "Taylor Swift"
            ],
            "filmmakers": [
                "Alfred Hitchcock", "Stanley Kubrick", "Steven Spielberg", "Martin Scorsese",
                "Quentin Tarantino", "Christopher Nolan", "Akira Kurosawa"
            ]
        },
        "athletes": {
            "track_field": [
                "Usain Bolt", "Jesse Owens", "Carl Lewis", "Florence Griffith Joyner"
            ],
            "basketball": [
                "Michael Jordan", "LeBron James", "Kobe Bryant", "Shaquille O'Neal",
                "Stephen Curry", "Magic Johnson", "Larry Bird"
            ],
            "soccer": [
                "Pelé", "Diego Maradona", "Lionel Messi", "Cristiano Ronaldo",
                "Neymar", "Zlatan Ibrahimovic", "Kylian Mbappé"
            ],
            "tennis": [
                "Roger Federer", "Rafael Nadal", "Novak Djokovic", "Serena Williams",
                "Steffi Graf", "Martina Navratilova", "Billie Jean King"
            ],
            "boxing": [
                "Muhammad Ali", "Mike Tyson", "Floyd Mayweather", "Manny Pacquiao"
            ],
            "motorsports": [
                "Michael Schumacher", "Lewis Hamilton", "Ayrton Senna", "Dale Earnhardt"
            ]
        },
        "social_figures": {
            "civil_rights": [
                "Martin Luther King Jr.", "Rosa Parks", "Malcolm X", "Nelson Mandela",
                "Mahatma Gandhi", "Cesar Chavez", "Harriet Tubman", "Sojourner Truth"
            ],
            "women_leaders": [
                "Susan B. Anthony", "Elizabeth Cady Stanton", "Emmeline Pankhurst",
                "Indira Gandhi", "Margaret Thatcher", "Angela Merkel", "Benazir Bhutto"
            ],
            "humanitarians": [
                "Mother Teresa", "Florence Nightingale", "Albert Schweitzer",
                "Oskar Schindler", "Mahatma Gandhi", "Nelson Mandela"
            ]
        },
        "explorers": [
            "Christopher Columbus", "Marco Polo", "Vasco da Gama", "Ferdinand Magellan",
            "James Cook", "David Livingstone", "Ernest Shackleton", "Roald Amundsen",
            "Neil Armstrong", "Buzz Aldrin", "Yuri Gagarin", "Valentina Tereshkova"
        ],
        "non_western_figures": {
            "asian_leaders": [
                "Confucius", "Laozi", "Siddhartha Gautama", "Ashoka", "Qin Shi Huang",
                "Genghis Khan", "Kublai Khan", "Toyotomi Hideyoshi", "Lee Kuan Yew",
                "Park Chung-hee", "Deng Xiaoping", "Mahatma Gandhi", "Jawaharlal Nehru",
                "Lee Kuan Yew", "Sun Yat-sen", "Chiang Kai-shek", "Mao Zedong"
            ],
            "african_figures": [
                "Nelson Mandela", "Desmond Tutu", "Kwame Nkrumah", "Julius Nyerere",
                "Haile Selassie", "Shaka Zulu", "Yaa Asantewaa", "Wangari Maathai"
            ],
            "latin_american_figures": [
                "Simón Bolívar", "Che Guevara", "Fidel Castro", "Eva Perón",
                "Diego Rivera", "Frida Kahlo", "Gabriel Garcia Marquez", "Pablo Neruda"
            ],
            "middle_eastern_figures": [
                "Saladin", "Suleiman the Magnificent", "Rumi", "Omar Khayyam",
                "Gamal Abdel Nasser", "Yasser Arafat", "Anwar Sadat"
            ]
        }
    }

    # ========== BIOGRAPHICAL CONCEPTS ==========

    BIOGRAPHICAL_CONCEPTS = {
        "early_life": [
            "Birth and family background", "Childhood and education",
            "Early influences", "Formative experiences", "Family circumstances",
            "Geographic origin", "Socioeconomic background"
        ],
        "career": [
            "Career beginnings", "Breakthrough moment", "Major achievements",
            "Professional recognition", "Awards and honors", "Notable works",
            "Career transitions", "Collaborations", "Mentorship"
        ],
        "personal_life": [
            "Marriage and family", "Personal relationships", "Health challenges",
            "Personal beliefs", "Lifestyle choices", "Residences",
            "Hobbies and interests", "Personality traits"
        ],
        "legacy": [
            "Historical impact", "Cultural influence", "Lasting achievements",
            "Influence on successors", "Memorials and commemorations",
            "Critical reception", "Posthumous recognition"
        ],
        "controversies": [
            "Scandals", "Controversial decisions", "Criticisms", "Opposition",
            "Legal issues", "Public disputes", "Failures and setbacks"
        ]
    }

    # ========== WIKIPEDIA BIOGRAPHY CATEGORIES ==========

    WIKIPEDIA_CATEGORIES = [
        "Category:Biographies",
        "Category:People by occupation",
        "Category:People by nationality",
        "Category:People by century",
        "Category:People by era",
        "Category:American people",
        "Category:British people",
        "Category:Chinese people",
        "Category:Indian people",
        "Category:Politicians",
        "Category:Scientists",
        "Category:Artists",
        "Category:Writers",
        "Category:Musicians",
        "Category:Actors",
        "Category:Film directors",
        "Category:Philosophers",
        "Category:Mathematicians",
        "Category:Physicists",
        "Category:Chemists",
        "Category:Biologists",
        "Category:Physicians",
        "Category:Psychologists",
        "Category:Economists",
        "Category:Entrepreneurs",
        "Category:Businesspeople",
        "Category:Activists",
        "Category:Humanitarians",
        "Category:Explorers",
        "Category:Journalists",
        "Category:20th-century people",
        "Category:21st-century people",
        "Category:Women by occupation",
        "Category:LGBTQ people",
        "Category:Nobel laureates",
        "Category:African-American people",
        "Category:Asian people",
        "Category:European people",
        "Category:Latino people",
        "Category:Indigenous people"
    ]

    # ========== SEARCH KEYWORD COMPONENTS ==========

    KEYWORD_COMPONENTS = {
        "person_types": [
            "politician", "president", "prime minister", "revolutionary", "activist",
            "entrepreneur", "founder", "CEO", "business leader", "investor",
            "scientist", "inventor", "researcher", "professor", "academic",
            "artist", "painter", "writer", "author", "poet", "musician", "composer",
            "actor", "director", "filmmaker", "photographer", "architect",
            "athlete", "olympian", "champion", "record holder", "coach",
            "explorer", "pioneer", "adventurer", "astronaut", "cosmonaut"
        ],
        "nationalities": [
            "American", "British", "French", "German", "Italian", "Spanish",
            "Chinese", "Japanese", "Korean", "Indian", "Russian",
            "Brazilian", "Argentine", "Mexican", "Canadian", "Australian",
            "South African", "Nigerian", "Egyptian", "Israeli", "Saudi Arabian"
        ],
        "eras": [
            "ancient", "medieval", "Renaissance", "Enlightenment",
            "19th century", "Victorian", "early 20th century",
            "World War I", "World War II", "Cold War", "modern",
            "contemporary", "21st century"
        ],
        "topics": [
            "biography", "autobiography", "memoir", "life story",
            "early life", "education", "career", "achievements",
            "legacy", "influence", "impact", "contributions",
            "quotes", "speeches", "interviews", "letters"
        ],
        "modifiers": [
            "famous", "notable", "influential", "legendary", "iconic",
            "pioneering", "groundbreaking", "revolutionary", "visionary",
            "controversial", "forgotten", "overlooked", "unsung"
        ]
    }

    # ========== NOTABLE AWARD WINNERS ==========

    AWARD_WINNERS = {
        "nobel_prize": [
            "Albert Einstein", "Marie Curie", "Martin Luther King Jr.", "Nelson Mandela",
            "Ernest Hemingway", "Bob Dylan", "Barack Obama", "Malala Yousafzai",
            "Toni Morrison", "Gabriel Garcia Marquez", "Elie Wiesel", "Mother Teresa",
            "Richard Feynman", "Francis Crick", "James Watson", "Alexander Fleming"
        ],
        "academy_award": [
            "Meryl Streep", "Katharine Hepburn", "Jack Nicholson", "Daniel Day-Lewis",
            "Tom Hanks", "Morgan Freeman", "Denzel Washington", "Cate Blanchett",
            "Steven Spielberg", "Martin Scorsese", "Quentin Tarantino"
        ],
        "grammy_award": [
            "Beyoncé", "Taylor Swift", "Jay-Z", "Kanye West", "Adele",
            "Frank Sinatra", "Ella Fitzgerald", "Michael Jackson", "Madonna",
            "The Beatles", "U2", "Coldplay"
        ],
        "olympic_champions": [
            "Usain Bolt", "Michael Phelps", "Simone Biles", "Serena Williams",
            "Roger Federer", "Michael Jordan", "Lionel Messi", "Cristiano Ronaldo"
        ]
    }

    # ========== HELPER METHODS ==========

    def get_all_person_categories(self) -> List[str]:
        """Get all person categories as flat list"""
        all_categories = []
        for cat_list in self.PERSON_CATEGORIES.values():
            all_categories.extend(cat_list)
        return all_categories

    def get_all_professions(self) -> List[str]:
        """Get all professions as flat list"""
        all_professions = []
        for prof_list in self.PROFESSIONS.values():
            all_professions.extend(prof_list)
        return all_professions

    def get_all_regions(self) -> List[str]:
        """Get all regions as flat list"""
        all_regions = []
        for region_list in self.REGIONS.values():
            all_regions.extend(region_list)
        return all_regions

    def get_all_eras(self) -> List[str]:
        """Get all eras as flat list"""
        all_eras = []
        for era_list in self.ERAS.values():
            all_eras.extend(era_list)
        return all_eras

    def get_all_categories(self) -> List[str]:
        """Get all Wikipedia categories"""
        return self.WIKIPEDIA_CATEGORIES

    def get_random_person(self) -> str:
        """Get a random famous person"""
        # Flatten all famous people
        all_people = []
        for category in self.FAMOUS_PEOPLE.values():
            if isinstance(category, dict):
                for subcategory in category.values():
                    all_people.extend(subcategory)
            elif isinstance(category, list):
                all_people.extend(category)
        return random.choice(all_people)

    def get_all_famous_people(self) -> Dict[str, Dict]:
        """Get all famous people by category"""
        return self.FAMOUS_PEOPLE

    def generate_search_queries(self, num_queries: int = 50) -> List[str]:
        """
        Generate diverse biography search queries

        Returns a list of search query combinations
        """
        queries = []

        # Generate different query patterns
        for _ in range(num_queries):
            pattern = random.choice([
                # Person type + nationality
                lambda: f"{random.choice(self.get_all_professions())} {random.choice(self.get_all_regions())}",
                # Person type + era
                lambda: f"{random.choice(self.get_all_professions())} {random.choice(self.get_all_eras())}",
                # Person + topic
                lambda: f"{self.get_random_person()} {random.choice(self.KEYWORD_COMPONENTS['topics'])}",
                # Nationality + person type
                lambda: f"{random.choice(self.get_all_regions())} {random.choice(self.get_all_professions())}",
                # Award winner
                lambda: f"{random.choice(sum(self.AWARD_WINNERS.values(), []))} biography",
                # Modifier + person type
                lambda: f"{random.choice(self.KEYWORD_COMPONENTS['modifiers'])} {random.choice(self.get_all_professions())}",
                # Person type + topic
                lambda: f"{random.choice(self.get_all_professions())} {random.choice(self.KEYWORD_COMPONENTS['topics'])}",
                # Era + person type
                lambda: f"{random.choice(self.get_all_eras())} {random.choice(self.get_all_professions())}",
                # Region + modifier + person type
                lambda: f"{random.choice(self.get_all_regions())} {random.choice(self.KEYWORD_COMPONENTS['modifiers'])} {random.choice(self.get_all_professions())}",
            ])

            try:
                query = pattern()
                queries.append(query)
            except:
                continue

        return list(set(queries))  # Remove duplicates

    def get_biography_concept_combinations(self) -> List[str]:
        """Get biography concept combinations for exploration"""
        concepts = []

        # Biographical concepts
        for concept_list in self.BIOGRAPHICAL_CONCEPTS.values():
            concepts.extend(concept_list)

        # Add person-specific concepts
        concepts.extend([
            f"{self.get_random_person()} early life",
            f"{self.get_random_person()} career achievements",
            f"{self.get_random_person()} personal life",
            f"{self.get_random_person()} legacy and influence"
        ])

        return concepts


# ============================================================================
# DEMO / TESTING
# ============================================================================

if __name__ == "__main__":
    pools = ExpandedBiographyPools()

    print("=" * 70)
    print("EXPANDED BIOGRAPHY POOLS")
    print("=" * 70)

    print(f"\nPerson Categories: {len(pools.get_all_person_categories())}")
    print(f"Professions: {len(pools.get_all_professions())}")
    print(f"Regions: {len(pools.get_all_regions())}")
    print(f"Eras: {len(pools.get_all_eras())}")
    print(f"Wikipedia Categories: {len(pools.get_all_categories())}")

    print("\nSample Search Queries:")
    queries = pools.generate_search_queries(10)
    for q in queries[:10]:
        print(f"  - {q}")

    print("\nSample Famous People:")
    for category, people in pools.FAMOUS_PEOPLE.items():
        print(f"  {category}: {', '.join(list(people.values())[0][:2] if isinstance(list(people.values())[0], list) else list(people.values())[0][:2])}")
