#!/usr/bin/env python3
"""
Expanded Culture and Traditions Data Pools

This module provides expanded, diverse pools for culture and traditions data generation,
covering various cultural aspects, traditional practices, festivals, cuisine, and more.

Coverage:
- Traditional festivals and celebrations
- Cultural practices and customs
- Traditional clothing and textiles
- Traditional food and cuisine
- Traditional music and dance
- Folk arts and handicrafts
- Religious and spiritual traditions
- Architecture and cultural landscapes
- Mythology and folklore
- Modern cultural phenomena
"""

from typing import List, Dict
import random


# ============================================================================
# EXPANDED CULTURE & TRADITIONS POOLS
# ============================================================================

class ExpandedCultureTraditionsPools:
    """
    大规模文化传统数据池 - 覆盖全球文化传统
    Designed to be comprehensive and diverse across cultures and regions
    """

    # ========== TRADITIONAL FESTIVALS ==========

    TRADITIONAL_FESTIVALS = {
        "asian_festivals": [
            # Chinese festivals
            "Spring Festival", "Chinese New Year", "Lantern Festival", "Qingming Festival",
            "Dragon Boat Festival", "Mid-Autumn Festival", "Double Ninth Festival",
            "Qixi Festival", "Lab Festival", "Winter Solstice Festival",

            # Japanese festivals
            "Oshogatsu", "Hanami", "Tanabata", "Obon", "Shichi-Go-San", "Setsubun",
            "Golden Week", "Bon Festival", "Kodomo no Hi",

            # Korean festivals
            "Seollal", "Chuseok", "Dano", "Chilseok", "Jungyangjeol", "Sollal",

            # Indian festivals
            "Diwali", "Holi", "Navratri", "Durga Puja", "Dussehra", "Raksha Bandhan",
            "Eid ul-Fitr", "Eid ul-Adha", "Pongal", "Onam", "Vaisakhi",
            "Makar Sankranti", "Janmashtami", "Ganesh Chaturthi", "Navratri",

            # Southeast Asian
            "Songkran", "Thingyan", "Lunar New Year", "Mid-Autumn Festival",
            "Hari Raya", "Eid", "Vesak", "Thaipusam", "Kaamatan",

            # Other Asian
            "Tet Nguyen Dan", "Chuseok", "Tsagaan Sar", "Losar", "Nowruz"
        ],
        "western_festivals": [
            # Christian festivals
            "Christmas", "Easter", "Pentecost", "Epiphany", "Ash Wednesday",
            "Good Friday", "Ascension Day", "All Saints Day", "All Souls Day",
            "Advent", "Lent", "Palm Sunday",

            # National holidays
            "Thanksgiving", "Independence Day", "Bastille Day", "St. Patrick's Day",
            "Halloween", "Remembrance Day", "Victoria Day", "Canada Day",
            "Australia Day", "Waitangi Day"
        ],
        "religious_festivals": [
            # Islamic
            "Eid ul-Fitr", "Eid ul-Adha", "Ramadan", "Mawlid", "Isra and Miraj",
            "Laylat al-Qadr",

            # Hindu
            "Diwali", "Holi", "Navratri", "Dussehra", "Raksha Bandhan",
            "Janmashtami", "Ganesh Chaturthi", "Shivratri",

            # Buddhist
            "Vesak", "Buddha's Birthday", "Magha Puja", "Asalha Puja",
            "Kathina", "Songkran",

            # Jewish
            "Passover", "Rosh Hashanah", "Yom Kippur", "Sukkot", "Hanukkah",
            "Purim", "Shavuot", "Tisha B'Av",

            # Sikh
            "Guru Nanak Gurpurab", "Hola Mohalla", "Bandi Chhor Divas",
            "Maggi Purim", "Vaisakhi",

            # Christian
            "Christmas", "Easter", "Pentecost", "Epiphany", "Ascension",
            "Assumption of Mary", "Immaculate Conception", "All Saints"
        ],
        "cultural_festivals": [
            # Music & Arts
            "Carnival", "Mardi Gras", "Oktoberfest", "Rio Carnival", "Venice Carnival",
            "Notting Hill Carnival", "Tomorrowland", "Coachella", "Glastonbury",
            "Burning Man", "Dia de los Muertos", "Holi Festival of Colors",

            # Food festivals
            "Oktoberfest", "Thanksgiving", "Mid-Autumn Festival", "Pongal",
            "Harvest Festival", "Wine Festival", "Food Festival",

            # Flower festivals
            "Cherry Blossom Festival", "Rose Festival", "Lotus Festival",
            "Tulip Festival", "Sunflower Festival",

            # Cultural celebrations
            "Chinese New Year", "Lunar New Year", "Nowruz", "Songkran",
            "Diwali", "Hanukkah", "Christmas", "Easter"
        ]
    }

    # ========== CULTURAL PRACTICES AND CUSTOMS ==========

    CULTURAL_PRACTICES = {
        "life_cycle_customs": [
            # Birth and childhood
            "Baby naming ceremony", "First haircut", "First birthday",
            "Cradle ceremony", "Christening", "Baptism", "Circumcision ceremony",
            "Coming of age ceremony", "Bar Mitzvah", "Bat Mitzvah", "Quinceañera",
            "Seijin-shiki", "Sweet sixteen",

            # Marriage customs
            "Wedding ceremony", "Bridal shower", "Bachelor party",
            "Dowry tradition", "Matchmaking tradition", "Arranged marriage",
            "Wedding vows", "Marriage contract", "Honeymoon tradition",

            # Funeral customs
            "Funeral rites", "Memorial service", "Mourning period",
            "Ancestor worship", "Day of the Dead", "All Souls Day",
            "Qingming Festival", "Obon Festival", "Sadddha"
        ],
        "daily_customs": [
            # Greetings and etiquette
            "Greeting customs", "Handshaking", "Bowing", "Namaste",
            "Wai", "Salaam", "Kowtow", "Cheek kissing",

            # Dining etiquette
            "Chopsticks etiquette", "Table manners", "Dining customs",
            "Tea ceremony", "Sake ceremony", "Coffee ceremony",
            "Communal dining", "Feasting tradition",

            # Social customs
            "Hospitality traditions", "Guest customs", "Gift giving",
            "Tipping customs", "Queueing customs", "Punctuality customs",
            "Dress code", "Shoe removal customs"
        ],
        "seasonal_customs": [
            # Spring festivals
            "Spring cleaning", "Easter customs", "Nowruz customs",
            "Cherry blossom viewing", "Planting traditions",

            # Summer festivals
            "Summer solstice", "Midsummer festivals", "Obon",
            "Summer festivals", "Beach traditions",

            # Harvest festivals
            "Harvest festival", "Thanksgiving", "Moon festival",
            "Wine harvest", "Rice harvest", "Wheat harvest",

            # Winter festivals
            "Winter solstice", "Christmas customs", "Hanukkah traditions",
            "New Year traditions", "Winter festivals"
        ]
    }

    # ========== TRADITIONAL CLOTHING ==========

    TRADITIONAL_CLOTHING = {
        "asian_clothing": [
            # Chinese
            "Hanfu", "Qipao", "Cheongsam", "Tang suit", "Mandarin suit",
            "Silk robe", "Farmer's straw hat",

            # Japanese
            "Kimono", "Yukata", "Hakama", "Samue", "Jūnihitoe",
            "Geta sandals", "Tabi socks",

            # Korean
            "Hanbok", "Gat", "Jogori", "Chima", "Baji",
            "Norigae", "Gat", "Jobawi",

            # Indian
            "Sari", "Salwar kameez", "Lehenga", "Sherwani", "Kurta",
            "Dhoti", "Lungi", "Dupatta", "Pagdi", "Nehru jacket",
            "Bindi", "Mangalsutra", "Sindoor",

            # Southeast Asian
            "Ao dai", "Barong Tagalog", "Sampot", "Kebaya",
            "Baju Melayu", "Batik", "Songket",

            # Central Asian
            "Chapan", "Khalat", "Surpa", "Tyubeteika",

            # Middle Eastern
            "Abaya", "Thobe", "Keffiyeh", "Shemagh", "Agal",
            "Bisht", "Bisht", "Kandura", "Hijab", "Niqab"
        ],
        "western_clothing": [
            # European traditional
            "Kilt", "Lederhosen", "Dirndl", "Tracht", "Clogs",
            "Wooden shoes", "Beret", "Tam o' shanter",

            # Formal wear
            "Tuxedo", "Morning coat", "Tailcoat", "Frock coat",
            "Evening gown", "Ball gown", "Cocktail dress",

            # Folk costumes
            "Tyrolean hat", "Alpine hat", "Dress sporran",
            "Aran sweater", "Fair Isle sweater",

            # Historical
            "Toga", "Stola", "Palla", "Himation", "Chiton",
            "Doublet", "Hose", "Codpiece", "Farthingale"
        ],
        "indigenous_clothing": [
            # Americas
            "Moccasins", "War bonnet", "Powwow regalia",
            "Poncho", "Serape", "Huipil", "Rebozo",

            # African
            "Kente cloth", "Kanga", "Kitenge", "Shemma",
            "Boubou", "Kaftan", "Dashiki",

            # Pacific
            "Grass skirt", "Hula attire", "Tapa cloth",
            "Lava-lava", "Pareu", "Ie lavalava",

            # Arctic
            "Parka", "Mukluk", "Kamik", "Anorak",
            "Caribou skin clothing"
        ],
        "religious_clothing": [
            # Christian
            "Nun's habit", "Monk's habit", "Priest's cassock",
            "Cardinal's cassock", "Bishop's rochet",
            "Kippah", "Yarmulke", "Tallit", "Tzitzit",

            # Islamic
            "Hijab", "Niqab", "Burqa", "Abaya", "Chador",
            "Keffiyeh", "Ihram", "Taqiyah",

            # Buddhist
            "Kasaya", "Robe", "Monk's robe",

            # Jewish
            "Kippah", "Tallit", "Tzitzit", "Tefillin",

            # Sikh
            "Dastar", "Turban", "Chola", "Kachera", "Kanga",
            "Kirpan"
        ]
    }

    # ========== TRADITIONAL FOOD AND CUISINE ==========

    TRADITIONAL_FOOD = {
        "asian_cuisine": [
            # Chinese cuisine
            "Dim sum", "Dumpling", "Spring roll", "Mooncake", "Zongzi",
            "Peking duck", "Hot pot", "Congee", "Noodle soup",
            "Fried rice", "Kung Pao chicken", "Mapo tofu",
            "Hot and sour soup", "Wonton soup", "Egg roll",

            # Japanese cuisine
            "Sushi", "Sashimi", "Ramen", "Tempura", "Udon",
            "Soba", "Donburi", "Takoyaki", "Okonomiyaki",
            "Miso soup", "Tonkatsu", "Yakitori", "Sukiyaki",
            "Matcha", "Wagashi", "Mochi", "Dorayaki",

            # Korean cuisine
            "Kimchi", "Bibimbap", "Bulgogi", "Galbi", "Japchae",
            "Tteokbokki", "Samgyeopsal", "Haemul pajeon",
            "Gimbap", "Jajangmyeon", "Kongnamul",
            "Kimchi jjigae", "Doenjang jjigae",

            # Indian cuisine
            "Curry", "Biryani", "Tandoori", "Naan", "Roti",
            "Samosa", "Pakora", "Dosa", "Idli", "Vada",
            "Thali", "Raita", "Chutney", "Pickles",
            "Gulab jamun", "Jalebi", "Kheer",

            # Southeast Asian
            "Pad Thai", "Tom yum", "Satay", "Nasi goreng", "Rendang",
            "Laksa", "Hainanese chicken rice", "Pho", "Banh mi",
            "Spring rolls", "Summer rolls", "Adobo", "Sinigang"
        ],
        "western_cuisine": [
            # European
            "Pizza", "Pasta", "Risotto", "Lasagna", "Gnocchi",
            "Croissant", "Baguette", "Croissant", "Pain au chocolat",
            "Fish and chips", "Bangers and mash", "Shepherd's pie",
            "Roast beef", "Yorkshire pudding", "Trifle",
            "Sauerbraten", "Bratwurst", "Pretzel", "Schnitzel",
            "Paella", "Tapas", "Gazpacho", "Tortilla",

            # American
            "Hamburger", "Hot dog", "BBQ ribs", "Mac and cheese",
            "Apple pie", "Pumpkin pie", "Turkey", "Stuffing",
            "Clam chowder", "Lobster roll", "Philly cheesesteak",
            "Buffalo wings", "Corn dog", "Deep dish pizza"
        ],
        "middle_eastern_cuisine": [
            "Hummus", "Baba ghanoush", "Falafel", "Shawarma",
            "Tabbouleh", "Fattoush", "Hummus", "Baklava",
            "Kibbeh", "Kofta", "Dolma", "Yogurt",
            "Pita bread", "Naan bread", "Lavash",
            "Turkish delight", "Halva", "Knafeh",
            "Shakshuka", "Ful medames", "Mujadara"
        ],
        "festive_foods": [
            # Christmas foods
            "Christmas ham", "Christmas pudding", "Gingerbread",
            "Eggnog", "Mulled wine", "Minced pie",
            "Panettone", "Stollen", "Yule log",

            # Thanksgiving foods
            "Roast turkey", "Stuffing", "Cranberry sauce",
            "Pumpkin pie", "Sweet potato casserole",
            "Green bean casserole", "Mashed potatoes",

            # Lunar New Year
            "Nian gao", "Dumplings", "Fish", "Nian gao",
            "Tangyuan", "Fa gao", "Eight treasure rice",

            # Diwali foods
            "Mithai", "Laddu", "Gulab jamun", "Jalebi",
            "Karanji", "Murukku", "Sri Krishna sweets"
        ]
    }

    # ========== TRADITIONAL MUSIC AND DANCE ==========

    TRADITIONAL_MUSIC = {
        "folk_music": [
            # Folk genres by region
            "American folk music", "Bluegrass", "Country music",
            "Celtic folk", "Irish folk", "Scottish folk",
            "English folk", "French folk", "Italian folk",
            "Spanish folk", "Russian folk", "Eastern European folk",
            "Chinese folk", "Japanese folk", "Indian folk",
            "African folk music", "Latin American folk",
            "Andean music", "Flamenco", "Tango", "Samba",
            "Bossa nova", "Cumbia", "Mariachi", "Nordic folk"
        ],
        "traditional_instruments": [
            # String instruments
            "Guitar", "Violin", "Cello", "Double bass", "Harp",
            "Sitar", "Sarod", "Veena", "Erhu", "Guqin", "Pipa",
            "Koto", "Shamisen", "Gayageum", "Dan bau",
            "Lute", "Oud", "Bouzouki", "Balalaika", "Bandura",
            "Banjo", "Mandolin", "Ukulele",

            # Wind instruments
            "Flute", "Clarinet", "Oboe", "Bassoon", "Bagpipe",
            "Shakuhachi", "Shakuhachi", "Hichiriki", "Ryuteki",
            "Bansuri", "Shehnai", "Ney", "Kaval", "Fujara",
            "Didgeridoo", "Jew's harp", "Ocarina",
            "Accordion", "Concertina", "Harmonica",

            # Percussion
            "Drums", "Timpani", "Snare drum", "Bass drum",
            "Tabla", "Mridangam", "Djembe", "Dundun", "Talking drum",
            "Taiko", "Samulnori", "Gong", "Temple bells",
            "Marimba", "Xylophone", "Steel drum", "Handpan"
        ],
        "traditional_dance": [
            # Folk dances
            "Square dance", "Contra dance", "Barn dance",
            "English country dance", "Scottish country dance",
            "Irish step dance", "Celtic dance",

            # International folk dances
            "Flamenco", "Tango", "Samba", "Salsa",
            "Ballet folklorico", "Hula", "Bhangra",
            "Dragon dance", "Lion dance",
            "Butoh", "Kabuki", "Noh", "Wayang kulit",
            "Bharatanatyam", "Kathak", "Odissi", "Kathakali",
            "Folk dance", "Line dance", "Circle dance"
        ]
    }

    # ========== FOLK ARTS AND HANDICRAFTS ==========

    FOLK_ARTS = {
        "textile_arts": [
            # Weaving
            "Tapestry", "Embroidery", "Cross-stitch", "Needlepoint",
            "Knitting", "Crochet", "Weaving", "Quilting",
            "Batik", "Ikat", "Kente", "Brocade",
            "Silk weaving", "Wool spinning", "Dyeing",

            # Traditional textiles
            "Navajo weaving", "Persian carpet", "Turkish rug",
            "Indian silk sarees", "Chinese silk embroidery",
            "Japanese textiles", "Peruvian textiles",
            "Andean textiles", "African textiles"
        ],
        "pottery_and_ceramics": [
            # Pottery styles
            "Porcelain", "Stoneware", "Earthenware", "Terracotta",
            "Raku ware", "Majolica", "Delftware",
            "Blue and white pottery", "Celadon",

            # Regional styles
            "Chinese porcelain", "Japanese ceramics", "Korean ceramics",
            "Greek pottery", "Roman pottery",
            "Native American pottery", "Pueblo pottery",
            "African pottery", "Pre-Columbian pottery",
            "English pottery", "Dutch pottery", "French porcelain"
        ],
        "woodworking": [
            # Carving
            "Wood carving", "Woodblock printing", "Intarsia",
            "Marquetry", "Inlay work", "Relief carving",

            # Regional styles
            "Chinese carving", "Japanese netsuke", "Balinese carving",
            "African carving", "Northwest Coast carving",
            "Russian folk carving", "Bavarian carving",

            # Objects
            "Mask making", "Puppet making", "Toy making",
            "Furniture making", "Musical instrument making"
        ],
        "metalwork": [
            # Jewelry
            "Filigree", "Granulation", "Cloisonné", "Niello",
            "Enamel work", "Damascening", "Repoussé",

            # Regional styles
            "Indian jewelry", "Chinese jade carving",
            "Celtic metalwork", "Viking metalwork",
            "Filipino jewelry", "African jewelry",
            "Native American jewelry", "Southwest silver",

            # Objects
            "Sword making", "Armor making", "Bell making",
            "Brass work", "Bronze casting", "Silver work"
        ],
        "paper_and_book_arts": [
            "Calligraphy", "Illuminated manuscript", "Bookbinding",
            "Papermaking", "Origami", "Paper cutting",
            "Printmaking", "Etching", "Engraving",
            "Lithography", "Screen printing", "Woodblock printing",

            # Regional styles
            "Chinese calligraphy", "Japanese calligraphy",
            "Islamic calligraphy", "Western calligraphy",
            "Book illumination", "Manuscript illustration"
        ]
    }

    # ========== RELIGIOUS AND SPIRITUAL TRADITIONS ==========

    RELIGIOUS_TRADITIONS = {
        "christian_traditions": [
            "Baptism", "Christening", "First communion", "Confirmation",
            "Marriage vows", "Last rites", "Funeral rites",
            "Lenten observances", "Advent customs", "Epiphany customs",
            "All Saints Day", "All Souls Day", "Christmas traditions",
            "Easter traditions", "Pentecost traditions",
            "Saint day celebrations", "Pilgrimage", "Religious holidays",
            "Church traditions", "Monastic traditions"
        ],
        "islamic_traditions": [
            "Shahada", "Salah", "Zakat", "Sawm", "Hajj",
            "Eid ul-Fitr", "Eid ul-Adha", "Ramadan observances",
            "Friday prayers", "Call to prayer", "Hajj pilgrimage",
            "Umrah", "Islamic festivals", "Milad un-Nabi",
            "Ashura", "Laylat al-Qadr", "Isra and Miraj",
            "Marriage traditions", "Funeral customs", "Halal dietary laws",
            "Islamic naming customs", "Islamic greeting customs"
        ],
        "hindu_traditions": [
            "Puja", "Aarti", "Darshan", "Prasad",
            "Diwali customs", "Holi celebrations", "Navratri customs",
            "Raksha Bandhan", "Karva Chauth", "Teej",
            "Kumbh Mela", "Varanasi pilgrimage", "Char Dham Yatra",
            "Vastu Shastra", "Ayurveda traditions",
            "Yoga traditions", "Meditation traditions",
            "Wedding customs", "Funeral rites", "Shraddha",
            "Naming ceremony", "Upanayana", "Antyesti"
        ],
        "buddhist_traditions": [
            "Meditation", "Mindfulness", "Vipassana", "Zen meditation",
            "Vesak celebrations", "Buddha's birthday", "Dharma teachings",
            "Sangha", "Monastic traditions", "Temple customs",
            "Pilgrimage", "Stupa worship", "Prayer flags",
            "Prayer wheels", "Mantra chanting", "Sutra recitation",
            "Vegetarianism", "Ahimsa", "Eightfold Path",
            "Four Noble Truths", "Noble Eightfold Path"
        ],
        "jewish_traditions": [
            "Shabbat observance", "Kashrut dietary laws", "Passover Seder",
            "Rosh Hashanah customs", "Yom Kippur observance", "Sukkot",
            "Hanukkah traditions", "Purim customs", "Simchat Torah",
            "Bar Mitzvah", "Bat Mitzvah", "Wedding customs",
            "Funeral customs", "Mourning practices", "Kaddish",
            "Brit milah", "Pidyon haben", "Jewish naming customs",
            "Tefillin", "Mezuzah", "Menorah", "Dreidel"
        ]
    }

    # ========== ARCHITECTURE AND CULTURAL LANDSCAPES ==========

    ARCHITECTURE_STYLES = {
        "religious_architecture": [
            # Christian
            "Gothic cathedral", "Romanesque architecture", "Byzantine architecture",
            "Renaissance architecture", "Baroque architecture",
            "Church architecture", "Chapel design",

            # Islamic
            "Mosque architecture", "Minaret design", "Madrasa architecture",
            "Islamic garden", "Courtyard design",

            # Hindu
            "Temple architecture", "Shikhar", "Vimana", "Mandapa",
            "Temple complex", "Sacred geometry",

            # Buddhist
            "Stupa", "Pagoda", "Temple architecture", "Zen garden",
            "Monastery architecture", "Meditation hall",

            # Jewish
            "Synagogue architecture", "Temple architecture",
            "Ark design", "Eternal flame"
        ],
        "traditional_architecture": [
            # Residential
            "Vernacular architecture", "Traditional house",
            "Courtyard house", "Longhouse", "Stilt house",
            "Igloo", "Yurt", "Tipi", "Wigwam",
            "Hanok", "Minka", "Tulum", "Trulli",

            # Public buildings
            "Traditional markets", "Caravanserai", "Roadhouse",
            "Teahouse", "Ryokan", "Pension", "Guesthouse",

            # Fortifications
            "Castle", "Fortress", "City wall", "Moat",
            "Watchtower", "Drawbridge", "Gatehouse"
        ],
        "cultural_landscapes": [
            # UNESCO categories
            "Cultural landscape", "Historic center", "Old town",
            "Sacred site", "Pilgrimage route",
            "Traditional settlement", "Vernacular landscape",

            # Specific types
            "Rice terraces", "Vineyards", "Olive groves",
            "Tea plantations", "Spice gardens", "Orchards",
            "Pastoral landscape", "Nomadic landscape",
            "Monastic landscape", "Garden landscape"
        ]
    }

    # ========== MYTHOLOGY AND FOLKLORE ==========

    MYTHOLOGY_FOLKLORE = {
        "mythology": [
            # Greek
            "Greek mythology", "Roman mythology", "Norse mythology",
            "Egyptian mythology", "Mesopotamian mythology",

            # Asian
            "Hindu mythology", "Buddhist mythology", "Chinese mythology",
            "Japanese mythology", "Korean mythology",

            # Other
            "Celtic mythology", "Slavic mythology", "Norse gods",
            "Aztec mythology", "Maya mythology", "Inca mythology",
            "Polynesian mythology", "Aboriginal mythology",
            "Native American mythology", "African mythology"
        ],
        "folklore": [
            # Folk tales
            "Fairy tales", "Folk tales", "Legends", "Myths",
            "Fables", "Parables", "Allegories",

            # Creatures
            "Dragons", "Fairies", "Elves", "Dwarves", "Giants",
            "Merfolk", "Shapeshifters", "Ghosts", "Vampires",
            "Werewolves", "Zombies", "Sirens", "Phoenix",
            "Unicorns", "Gryphons", "Chimera",

            # Heroes and figures
            "Folk heroes", "Legendary figures", "Culture heroes",
            "Tricksters", "Demigods", "Saints", "Sages"
        ],
        "superstitions": [
            # Omens
            "Good luck charms", "Bad luck omens", "Fortune telling",
            "Divination", "Astrology", "Numerology",

            # Practices
            "Protection rituals", "Purification rituals",
            "Warding off evil", "Cursing", "Blessing",
            "Voodoo", "Folk magic", "Witchcraft",

            # Beliefs
            "Evil eye", "Curses", "Blessings", "Miracles",
            "Sacred objects", "Taboo subjects", "Sacred spaces"
        ]
    }

    # ========== WIKIPEDIA CULTURE CATEGORIES ==========

    WIKIPEDIA_CATEGORIES = [
        # Main categories
        "Category:Culture",
        "Category:Tradition",
        "Category:Customs",
        "Category:Cultural heritage",
        "Category:Folklore",
        "Category:Festivals",
        "Category:Cultural practices",
        "Category:Rituals",

        # By type
        "Category:Traditional clothing",
        "Category:Traditional music",
        "Category:Traditional dance",
        "Category:Handicrafts",
        "Category:Folk art",
        "Category:Cuisine",
        "Category:Traditional medicine",
        "Category:Oral tradition",

        # Religious/Spiritual
        "Category:Religious festivals",
        "Category:Spirituality",
        "Category:Pilgrimage",
        "Category:Temples",
        "Category:Churches",
        "Category:Monasteries",
        "Category:Mosques",
        "Category:Synagogues",
        "Category:Shrines",

        # Cultural expressions
        "Category:Mythology",
        "Category:Legend",
        "Category:Folklore heroes",
        "Category:Epic poetry",
        "Category:Traditional storytelling",

        # By region
        "Category:Culture by country",
        "Category:Traditions by region",
        "Category:Cultural regions",
        "Category:Ethnocultural traditions"
    ]

    # ========== SEARCH KEYWORD COMPONENTS ==========

    KEYWORD_COMPONENTS = {
        "cultures": [
            "Chinese", "Japanese", "Korean", "Indian", "Thai",
            "Vietnamese", "Indonesian", "Filipino",
            "Arabic", "Persian", "Turkish", "Jewish",
            "Greek", "Roman", "Celtic", "Norse",
            "Mexican", "Peruvian", "Brazilian", "Native American",
            "African", "Polynesian", "Maori", "Aboriginal"
        ],
        "aspects": [
            "festival", "tradition", "custom", "ritual", "ceremony",
            "clothing", "costume", "attire", "dress", "fashion",
            "cuisine", "food", "dish", "recipe", "cooking",
            "music", "dance", "art", "craft", "handicraft",
            "architecture", "temple", "palace", "monument", "statue",
            "mythology", "legend", "folklore", "story", "tale",
            "belief", "religion", "spirituality", "practice"
        ],
        "modifiers": [
            "traditional", "ancient", "historical", "classic",
            "folk", "indigenous", "native", "rural", "regional",
            "religious", "spiritual", "sacred", "ceremonial"
        ]
    }

    # ========== HELPER METHODS ==========

    def get_all_festivals(self) -> List[str]:
        """Get all festivals as flat list"""
        all_festivals = []
        for festival_list in self.TRADITIONAL_FESTIVALS.values():
            all_festivals.extend(festival_list)
        return all_festivals

    def get_all_clothing(self) -> List[str]:
        """Get all clothing items as flat list"""
        all_clothing = []
        for clothing_list in self.TRADITIONAL_CLOTHING.values():
            all_clothing.extend(clothing_list)
        return all_clothing

    def get_all_cuisine(self) -> List[str]:
        """Get all cuisine items as flat list"""
        all_cuisine = []
        for cuisine_list in self.TRADITIONAL_FOOD.values():
            all_cuisine.extend(cuisine_list)
        return all_cuisine

    def get_all_music(self) -> List[str]:
        """Get all music items as flat list"""
        all_music = []
        for music_list in self.TRADITIONAL_MUSIC.values():
            all_music.extend(music_list)
        return all_music

    def get_all_categories(self) -> List[str]:
        """Get all Wikipedia categories"""
        return self.WIKIPEDIA_CATEGORIES

    def generate_search_queries(self, num_queries: int = 50) -> List[str]:
        """Generate diverse culture search queries"""
        queries = []

        for _ in range(num_queries):
            pattern = random.choice([
                # Culture + aspect
                lambda: f"{random.choice(self.KEYWORD_COMPONENTS['cultures'])} {random.choice(self.KEYWORD_COMPONENTS['aspects'])}",
                # Culture + aspect + modifier
                lambda: f"{random.choice(self.KEYWORD_COMPONENTS['modifiers'])} {random.choice(self.KEYWORD_COMPONENTS['cultures'])} {random.choice(self.KEYWORD_COMPONENTS['aspects'])}",
                # Specific item + culture
                lambda: f"{random.choice(self.get_all_clothing())} {random.choice(self.KEYWORD_COMPONENTS['cultures'])}",
                # Food + culture
                lambda: f"{random.choice(self.get_all_cuisine())} {random.choice(self.KEYWORD_COMPONENTS['cultures'])}",
                # Music + culture
                lambda: f"{random.choice(self.get_all_music())} {random.choice(self.KEYWORD_COMPONENTS['cultures'])}",
                # Festival + culture
                lambda: f"{random.choice(self.get_all_festivals())} {random.choice(self.KEYWORD_COMPONENTS['cultures'])}",
                # Tradition + culture
                lambda: f"{random.choice(self.KEYWORD_COMPONENTS['modifiers'])} {random.choice(self.KEYWORD_COMPONENTS['cultures'])} traditions",
            ])

            try:
                query = pattern()
                queries.append(query)
            except:
                continue

        return list(set(queries))


# ============================================================================
# DEMO / TESTING
# ============================================================================

if __name__ == "__main__":
    pools = ExpandedCultureTraditionsPools()

    print("=" * 70)
    print("EXPANDED CULTURE & TRADITIONS POOLS")
    print("=" * 70)

    print(f"\nTotal Festivals: {len(pools.get_all_festivals())}")
    print(f"Total Clothing: {len(pools.get_all_clothing())}")
    print(f"Total Cuisine: {len(pools.get_all_cuisine())}")
    print(f"Total Music: {len(pools.get_all_music())}")
    print(f"Total Categories: {len(pools.get_all_categories())}")

    print("\n" + "=" * 70)
    print("SAMPLE DATA")
    print("=" * 70)

    print("\nFestival Samples:")
    all_festivals = pools.get_all_festivals()
    for f in random.sample(all_festivals, min(10, len(all_festivals))):
        print(f"  - {f}")

    print("\nClothing Samples:")
    all_clothing = pools.get_all_clothing()
    for c in random.sample(all_clothing, min(10, len(all_clothing))):
        print(f"  - {c}")

    print("\nCuisine Samples:")
    all_cuisine = pools.get_all_cuisine()
    for c in random.sample(all_cuisine, min(10, len(all_cuisine))):
        print(f"  - {c}")

    print("\n" + "=" * 70)
    print("SAMPLE SEARCH QUERIES")
    print("=" * 70)

    queries = pools.generate_search_queries(10)
    for q in queries:
        print(f"  - {q}")
