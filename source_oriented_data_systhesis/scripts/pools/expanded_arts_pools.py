#!/usr/bin/env python3
"""
Expanded Arts Data Pools

This module provides expanded, diverse pools for cultural and arts data generation,
designed to minimize bias and maximize global coverage across all art forms and periods.

Coverage:
- All art types: Visual arts, music, literature, architecture, film, theater, dance, design, crafts, heritage
- All time periods: Prehistoric to contemporary (30,000 BC - 2025 AD)
- All regions: Global coverage with emphasis on non-Western traditions
- All movements and styles: From ancient to contemporary

Expanded Wikipedia Categories: 500+ categories across 8 dimensions
- Dimension 1: Specific Civilizations (100+): Ancient Egypt, Greece, Rome, China, Japan, India, Islamic, African, Pre-Columbian, Native American, etc.
- Dimension 2: Art Movements (100+): Renaissance, Baroque, Impressionism, Cubism, Surrealism, Abstract Expressionism, Pop Art, Minimalism, etc.
- Dimension 3: Techniques (80+): Oil painting, watercolor, woodcut, etching, stone carving, bronze casting, textiles, ceramics, etc.
- Dimension 4: Themes (60+): Religious art, portraits, landscapes, still life, vanitas, mythology, genre paintings, etc.
- Dimension 5: Intangible Heritage (40+): Folk music, dance, theater, oral traditions, rituals, festivals, traditional crafts, etc.
- Dimension 6: Institutions (30+): Museums, galleries, opera houses, concert halls, festivals, etc.
- Dimension 7: Literature (30+): Poetry, drama, novels, folk tales, literary movements, etc.
- Dimension 8: Music (40+): Classical, jazz, folk, traditional instruments, etc.
"""

from typing import List, Dict, Set
import random

# Import expanded Wikipedia categories
try:
    from expanded_wiki_cultural_categories import ExpandedWikiCulturalCategories
    USE_EXPANDED_CATEGORIES = True
except ImportError:
    USE_EXPANDED_CATEGORIES = False


class ExpandedArtsPools:
    """
    大规模文化艺术数据池 - 覆盖全球、全时代、多艺术形式
    Designed to minimize bias and maximize diversity
    """

    # ========== ART TYPES AND CATEGORIES ==========

    ART_TYPES = {
        "visual_arts": [
            # Painting and drawing
            "painting", "oil painting", "watercolor", "acrylic painting", "fresco", "tempera",
            "ink painting", "calligraphy", "sumi-e", "miniature painting", "digital painting",
            "drawing", "sketching", "charcoal drawing", "pencil drawing", "pastel",
            # Printmaking
            "woodcut", "engraving", "etching", "lithography", "screen printing", "intaglio",
            # Sculpture
            "sculpture", "carving", "casting", "modeling", "assemblage", "installation art",
            "bronze sculpture", "stone carving", "wood carving", "ivory carving",
            # Photography
            "photography", "black and white photography", "color photography", "digital photography",
            "portrait photography", "landscape photography", "documentary photography",
            # Other visual arts
            "collage", "mixed media", "video art", "performance art", "conceptual art",
            "land art", "environmental art", "light art", "sound art"
        ],
        "music": [
            # Classical traditions
            "classical music", "opera", "symphony", "concerto", "sonata", "chamber music",
            "Western classical music", "Indian classical music", "Chinese classical music",
            # Traditional and folk
            "folk music", "traditional music", "ethnic music", "indigenous music",
            "blues", "jazz", "gospel music", "spirituals",
            # Popular music
            "pop music", "rock music", "hip hop", "electronic music", "dance music",
            "country music", "reggae", "Latin music", "Afrobeat", "K-pop", "J-pop",
            # Contemporary
            "experimental music", "avant-garde music", "minimalism", "electroacoustic music",
            # Instruments and vocal
            "orchestral music", "choral music", "solo instrumental", "vocal music"
        ],
        "literature": [
            # Forms and genres
            "poetry", "epic poetry", "lyric poetry", "haiku", "sonnet", "free verse",
            "prose", "novel", "short story", "novella", "flash fiction",
            "drama", "play", "screenplay", "scriptwriting",
            # Non-fiction
            "essay", "memoir", "biography", "autobiography", "journalism",
            "travel writing", "philosophical writing", "historical writing",
            # Traditions
            "oral literature", "folklore", "mythology", "legend", "fable", "parable",
            # Comics and graphic
            "comics", "graphic novel", "manga", "manhwa", "bande dessinée"
        ],
        "architecture": [
            # Types and styles
            "religious architecture", "secular architecture", "domestic architecture",
            "monumental architecture", "landscape architecture", "urban design",
            # Traditional styles
            "classical architecture", "Gothic architecture", "Byzantine architecture",
            "Islamic architecture", "Chinese architecture", "Japanese architecture",
            "Indian architecture", "Mesoamerican architecture",
            # Modern movements
            "modernist architecture", "Art Deco", "Bauhaus", "Brutalism", "International Style",
            "postmodern architecture", "deconstructivism", "sustainable architecture",
            # Specific elements
            "temple architecture", "palace architecture", "fortress architecture",
            "garden design", "interior design", "vernacular architecture"
        ],
        "performing_arts": [
            # Theater
            "theater", "drama", "comedy", "tragedy", "musical theater", "opera",
            "ballet", "experimental theater", "street theater", "puppet theater",
            # Dance
            "classical dance", "folk dance", "traditional dance", "contemporary dance",
            "modern dance", "ballroom dance", "social dance", "ritual dance",
            # Performance traditions
            "Greek tragedy", "Noh theater", "Kabuki", "Beijing opera", "Wayang kulit",
            "Kathakali", "Commedia dell'arte", "Vaudeville"
        ],
        "film_and_media": [
            # Film
            "cinema", "feature film", "documentary film", "experimental film",
            "animation", "silent film", "short film", "avant-garde cinema",
            # Television and video
            "television", "television series", "miniseries", "music video",
            "video art", "digital media", "new media art",
            # Movements and genres
            "film noir", "neorealism", "French New Wave", "German Expressionism",
            "surrealist cinema", "documentary movement"
        ],
        "design_and_crafts": [
            # Design disciplines
            "graphic design", "industrial design", "fashion design", "textile design",
            "interior design", "product design", "communication design",
            # Crafts
            "pottery", "ceramics", "glassblowing", "jewelry making", "metalwork",
            "woodworking", "weaving", "embroidery", "lace making", "tapestry",
            "bookbinding", "paper craft", "leather craft",
            # Traditional crafts
            "ikat", "batik", "tie-dye", "quilting", "origami", "lacquerware"
        ],
        "cultural_heritage": [
            # Heritage types
            "archaeological site", "historical site", "cultural landscape",
            "sacred site", "pilgrimage site", "memorial", "monument",
            # Preservation
            "museum", "gallery", "archive", "library", "cultural institution",
            "UNESCO World Heritage", "intangible cultural heritage",
            # Traditions
            "festival", "ceremony", "ritual", "tradition", "custom",
            "cultural practice", "living heritage"
        ]
    }

    # ========== TIME PERIODS ==========

    TIME_PERIODS = {
        "prehistoric": [
            "Paleolithic", "Mesolithic", "Neolithic", "Bronze Age", "Iron Age",
            "Rock art", "Cave paintings", "Prehistoric art"
        ],
        "ancient": [
            "Ancient Egypt", "Ancient Mesopotamia", "Ancient Greece", "Ancient Rome",
            "Ancient China", "Ancient India", "Ancient Persia", "Ancient Mesoamerica",
            "Ancient Andes", "Ancient Nubia", "Ancient Japan", "Ancient Korea",
            "Classical antiquity", "Hellenistic period"
        ],
        "medieval": [
            "Early medieval art", "Romanesque art", "Gothic art", "Byzantine art",
            "Islamic Golden Age", "Song Dynasty art", "Tang Dynasty art",
            "Heian period art", "Korean Dynasty art", "Medieval literature",
            "Medieval music", "Church music", "Secular medieval music"
        ],
        "early_modern": [
            "Renaissance", "Northern Renaissance", "Mannerism", "Baroque", "Rococo",
            "Ming Dynasty art", "Qing Dynasty art", "Edo period art", "Mughal art",
            "Safavid art", "Ottoman art", "Colonial art", "Enlightenment culture"
        ],
        "19th_century": [
            "Neoclassicism", "Romanticism", "Realism", "Impressionism", "Post-Impressionism",
            "Symbolism", "Art Nouveau", "Victorian culture", "Meiji art",
            "Bengal Renaissance", "National revival movements", "Early photography"
        ],
        "early_20th_century": [
            "Modernism", "Fauvism", "Expressionism", "Cubism", "Futurism", "Dada",
            "Surrealism", "Bauhaus", "De Stijl", "Constructivism", "Harlem Renaissance",
            "Mexican muralism", "Early cinema", "Jazz age", "Art Deco"
        ],
        "post_war": [
            "Abstract Expressionism", "Pop Art", "Op Art", "Minimalism", "Conceptual Art",
            "Postmodernism", "Fluxus", "Happenings", "Video art", "Performance art",
            "Land art", "Installation art", "New Hollywood cinema", "Rock music"
        ],
        "contemporary": [
            "Contemporary art", "Digital art", "New media art", "Street art", "Graffiti art",
            "Young British Artists", "Relational art", "Interactive art", "Virtual reality art",
            "Global contemporary art", "Postcolonial art", "Feminist art", "Identity art",
            "Internet art", "AI art", "Bio art", "Social practice art"
        ]
    }

    # ========== GEOGRAPHIC REGIONS ==========

    REGIONS = {
        "east_asia": [
            "China", "Japan", "Korea", "Taiwan", "Mongolia",
            "Chinese art", "Japanese art", "Korean art", "East Asian calligraphy",
            "East Asian garden design", "East Asian ceramics"
        ],
        "southeast_asia": [
            "Vietnam", "Thailand", "Cambodia", "Laos", "Myanmar", "Malaysia",
            "Indonesia", "Philippines", "Singapore", "Brunei",
            "Southeast Asian temple architecture", "Wayang", "Batik", "Ikat"
        ],
        "south_asia": [
            "India", "Pakistan", "Bangladesh", "Sri Lanka", "Nepal", "Bhutan", "Maldives",
            "Indian classical music", "Indian classical dance", "Mughal art",
            "Buddhist art", "Hindu temple architecture", "Miniature painting"
        ],
        "central_asia": [
            "Kazakhstan", "Uzbekistan", "Turkmenistan", "Kyrgyzstan", "Tajikistan",
            "Silk Road art", "Central Asian textiles", "Nomadic art",
            "Islamic architecture in Central Asia"
        ],
        "west_asia": [
            "Turkey", "Iran", "Iraq", "Syria", "Lebanon", "Jordan", "Israel", "Palestine",
            "Saudi Arabia", "Yemen", "Oman", "UAE",
            "Islamic art", "Persian art", "Arabic calligraphy", "Ottoman art",
            "Mesopotamian art", "Phoenician art", "Hittite art"
        ],
        "north_africa": [
            "Egypt", "Libya", "Tunisia", "Algeria", "Morocco", "Sudan",
            "Ancient Egyptian art", "Islamic architecture in North Africa",
            "Berber art", "Moorish art", "Andalusian art"
        ],
        "sub_saharan_africa": [
            "West African art", "Central African art", "East African art", "Southern African art",
            "Nigerian art", "Benin art", "Congolese art", "Ethiopian art",
            "Shona sculpture", "Yoruba art", "Akan art", "African textiles",
            "African masks", "African sculpture", "African performance traditions"
        ],
        "europe": [
            "Western European art", "Eastern European art", "Northern European art", "Southern European art",
            "Italian art", "French art", "German art", "Dutch art", "Spanish art", "British art",
            "Renaissance art", "Baroque art", "Romanticism", "Modernism",
            "Classical music", "European literature", "European theater"
        ],
        "americas": [
            "North American art", "Latin American art", "South American art",
            "Pre-Columbian art", "Maya art", "Aztec art", "Inca art",
            "Native American art", "First Nations art", "Indigenous American art",
            "Colonial art", "American art", "Canadian art", "Mexican muralism",
            "Brazilian art", "Argentine art", "Latin American literature", "Magic realism"
        ],
        "oceania": [
            "Australian Aboriginal art", "Maori art", "Pacific Islander art",
            "Polynesian art", "Melanesian art", "Micronesian art",
            "Oceanic textiles", "Tattoo traditions", "Navigation art", "Hula", "Haka"
        ],
        "diaspora": [
            "African diaspora art", "Asian diaspora art", "Jewish diaspora art",
            "Caribbean art", "Afro-Caribbean art", "Indo-Caribbean art",
            "Immigrant art", "Refugee art", "Transnational culture"
        ]
    }

    # ========== ART MOVEMENTS AND SCHOOLS ==========

    MOVEMENTS = {
        "visual_movements": [
            # Historical Western movements
            "Renaissance", "Mannerism", "Baroque", "Rococo", "Neoclassicism",
            "Romanticism", "Realism", "Impressionism", "Post-Impressionism",
            "Symbolism", "Art Nouveau", "Expressionism", "Cubism", "Futurism",
            "Dada", "Surrealism", "Abstract Expressionism", "Pop Art", "Op Art",
            "Minimalism", "Conceptual Art", "Postmodernism", "Street Art",
            # Non-Western movements
            "Chinese literati painting", "Japanese ukiyo-e", "Yamato-e",
            "Indian miniature painting", "Persian miniature", "Ottoman miniature",
            "Islamic calligraphy", "Bengal School", "Nihonga", "Gongan",
            # Contemporary movements
            "Digital art", "New media art", "Interactive art", "Bio art",
            "Social practice art", "Relational aesthetics", "Virtual reality art"
        ],
        "literary_movements": [
            # Western
            "Classicism", "Romanticism", "Realism", "Naturalism", "Symbolism",
            "Modernism", "Postmodernism", "Existentialism", "Beat Generation",
            "Lost Generation", "Harlem Renaissance", "Magical realism",
            # Non-Western
            "Chinese poetry movements", "Japanese Haiku movement", "Indian literary movements",
            "Arabic literature", "Persian literature", "Negritude movement",
            "Postcolonial literature", "Diaspora literature"
        ],
        "musical_movements": [
            # Classical
            "Ars nova", "Baroque music", "Classical era music", "Romantic music",
            "Impressionist music", "Expressionist music", "Serialism", "Minimalism",
            # Popular
            "Blues", "Jazz", "Swing", "Bebop", "Cool jazz", "Free jazz",
            "Rock and roll", "Psychedelic rock", "Punk rock", "Heavy metal",
            "Hip hop", "Electronic music", "Techno", "House", "Ambient",
            # Non-Western
            "Raga", "Maqam", "Gamelan", "Carnatic music", "Hindustani music",
            "Chinese instrumental music", "Gagaku", "Korean court music"
        ],
        "architectural_styles": [
            "Ancient Egyptian architecture", "Greek architecture", "Roman architecture",
            "Byzantine architecture", "Romanesque architecture", "Gothic architecture",
            "Renaissance architecture", "Baroque architecture", "Neoclassical architecture",
            "Art Nouveau architecture", "Modernist architecture", "Bauhaus",
            "Brutalism", "Postmodern architecture", "Deconstructivism",
            "Islamic architecture", "Chinese architecture", "Japanese architecture",
            "Indian temple architecture", "Mesoamerican architecture",
            "Vernacular architecture", "Sustainable architecture"
        ]
    }

    # ========== FAMOUS ARTISTS AND WORKS ==========

    FAMOUS_ARTISTS = {
        "visual_artists": [
            # Western masters
            "Leonardo da Vinci", "Michelangelo", "Raphael", "Titian", "Caravaggio",
            "Rembrandt", "Vermeer", "Velázquez", "Goya", "Turner",
            "Monet", "Manet", "Renoir", "Degas", "Cézanne", "Van Gogh", "Gauguin",
            "Matisse", "Picasso", "Kandinsky", "Malevich", "Monet", "Dalí",
            "Pollock", "Warhol", "Kahlo", "Hockney",
            # Non-Western masters
            "Gu Kaizhi", "Wang Wei", "Hokusai", "Hiroshige", "Sesshu Toyo",
            "Ravi Varma", "Jamini Roy", "Amrita Sher-Gil", "Sadequain",
            "Ibrahim El-Salahi", "Twins Seven-Seven"
        ],
        "composers": [
            # Western classical
            "Bach", "Mozart", "Beethoven", "Chopin", "Brahms", "Wagner",
            "Stravinsky", "Debussy", "Schoenberg", "Shostakovich",
            # Non-Western classical
            "Miyan Tansen", "Tyagaraja", "Muthuswami Dikshitar", "Syama Shastri",
            "Hariprasad Chaurasia", "Ravi Shankar", "Zakir Hussain",
            # Popular music
            "Robert Johnson", "Louis Armstrong", "Duke Ellington", "Miles Davis",
            "Bob Dylan", "Beatles", "Bob Marley", "Fela Kuti", "Youssou N'Dour"
        ],
        "writers": [
            # Western canon
            "Homer", "Virgil", "Dante", "Shakespeare", "Cervantes", "Goethe",
            "Tolstoy", "Dostoevsky", "Proust", "Joyce", "Kafka", "Woolf",
            # Non-Western classics
            "Valmiki", "Vyasa", "Kalidasa", "Du Fu", "Li Bai", "Murasaki Shikibu",
            "Rumi", "Hafiz", "Omar Khayyam",
            # Postcolonial/contemporary
            "Chinua Achebe", "Gabriel García Márquez", "Jorge Luis Borges",
            "Naguib Mahfouz", "Orhan Pamuk", "Mo Yan", "Haruki Murakami",
            "Toni Morrison", "Alice Walker", "Derek Walcott", "Salman Rushdie"
        ],
        "architects": [
            "Imhotep", "Vitruvius", "Sinan", "Christopher Wren", "Andrea Palladio",
            "Frank Lloyd Wright", "Le Corbusier", "Luis Barragán", "Zaha Hadid",
            "I. M. Pei", "B. V. Dosh", "Kenzo Tange", "Fumihiko Maki"
        ]
    }

    # ========== FAMOUS WORKS AND MONUMENTS ==========

    FAMOUS_WORKS = {
        "visual_artworks": [
            "Mona Lisa", "The Last Supper", "The Starry Night", "Guernica",
            "The Persistence of Memory", "Girl with a Pearl Earring",
            "The Great Wave off Kanagawa", "Night at the Tang Court",
            "School of Athens", "The Birth of Venus", "Las Meninas",
            "Liberty Leading the People", "Olympia", "Les Demoiselles d'Avignon"
        ],
        "literary_works": [
            "The Epic of Gilgamesh", "The Iliad", "The Odyssey", "The Aeneid",
            "Ramayana", "Mahabharata", "Tale of Genji", "Dream of the Red Chamber",
            "One Thousand and One Nights", "Divine Comedy", "Don Quixote",
            "Things Fall Apart", "One Hundred Years of Solitude"
        ],
        "musical_works": [
            "Symphony No. 5", "The Rite of Spring", "Clair de Lune",
            "Raga Bhairavi", "Four Seasons", "Messiah", "Carmen",
            "Kind of Blue", "A Love Supreme", "What's Going On"
        ],
        "architectural_monuments": [
            "Great Pyramid of Giza", "Parthenon", "Colosseum", "Taj Mahal",
            "Great Wall of China", "Angkor Wat", "Borobudur", "Machu Picchu",
            "Alhambra", "Hagia Sophia", "Notre-Dame", "Sultan Ahmed Mosque",
            "Petra", "Teotihuacan", "Chichen Itza", "Forbidden City"
        ]
    }

    # ========== CULTURAL INSTITUTIONS ==========

    INSTITUTIONS = {
        "museums": [
            "Louvre", "British Museum", "Metropolitan Museum of Art", "Hermitage Museum",
            "Vatican Museums", "Prado Museum", "Rijksmuseum", "Uffizi Gallery",
            "Museum of Modern Art", "Tate Modern", "Centre Pompidou", "Guggenheim",
            "Palace Museum", "Tokyo National Museum", "National Museum of China",
            "Egyptian Museum", "Museum of Islamic Art"
        ],
        "performance_venues": [
            "La Scala", "Royal Opera House", "Metropolitan Opera", "Bolshoi Theatre",
            "Sydney Opera House", "Globe Theatre", "Comédie-Française",
            "Kabuki-za", "National Noh Theatre", "Beijing Opera House"
        ],
        "festivals": [
            "Venice Biennale", "Documenta", "São Paulo Art Biennial",
            "Edinburgh Festival", "Avignon Festival", "Bayreuth Festival",
            "Cannes Film Festival", "Berlin International Film Festival",
            "Vienna Film Festival", "Diwali", "Chinese New Year celebrations",
            "Rio Carnival", "Day of the Dead", "Holi", "Ramadan"
        ]
    }

    # ========== WIKIPEDIA CATEGORIES ==========

    WIKIPEDIA_CATEGORIES = {
        # By art form
        "visual_arts": [
            "Category:Visual_arts", "Category:Painting", "Category:Sculpture",
            "Category:Drawing", "Category:Printmaking", "Category:Photography",
            "Category:Art_history", "Category:Art_movements", "Category:Contemporary_art"
        ],
        "music": [
            "Category:Music", "Category:Musical_genres", "Category:Classical_music",
            "Category:Jazz", "Category:Rock_music", "Category:Pop_music",
            "Category:Folk_music", "Category:Traditional_music",
            "Category:Musical_compositions", "Category:Musicians"
        ],
        "literature": [
            "Category:Literature", "Category:Poetry", "Category:Novels",
            "Category:Short_stories", "Category:Drama", "Category:Literary_movements",
            "Category:Poets", "Category:Novelists", "Category:Playwrights"
        ],
        "architecture": [
            "Category:Architecture", "Category:Architectural_styles",
            "Category:Buildings_and_structures", "Category:Landscape_architecture",
            "Category:Architects", "Category:Architectural_history"
        ],
        "performing_arts": [
            "Category:Performing_arts", "Category:Theater", "Category:Dance",
            "Category:Ballet", "Category:Opera", "Category:Performance_art",
            "Category:Acting", "Category:Choreography"
        ],
        "film": [
            "Category:Film", "Category:Cinema", "Category:Film_genres",
            "Category:Motion_picture_directors", "Category:Actors", "Category:Screenwriters",
            "Category:Documentary_films", "Category:Animation", "Category:Experimental_film"
        ],
        "design_crafts": [
            "Category:Design", "Category:Graphic_design", "Category:Fashion_design",
            "Category:Industrial_design", "Category:Textile_arts", "Category:Pottery",
            "Category:Jewelry", "Category:Metalworking", "Category:Woodworking",
            "Category:Glass_art", "Category:Handicrafts"
        ],
        # By period
        "period": [
            "Category:Ancient_art", "Category:Medieval_art", "Category:Renaissance_art",
            "Category:Baroque_art", "Category:Romanticism_in_art", "Category:Modern_art",
            "Category:Contemporary_art", "Category:19th-century_art", "Category:20th-century_art"
        ],
        # By region
        "regional": [
            "Category:Asian_art", "Category:Chinese_art", "Category:Japanese_art",
            "Category:Indian_art", "Category:Islamic_art", "Category:African_art",
            "Category:European_art", "Category:American_art", "Category:Latin_American_art",
            "Category:Oceanian_art", "Category:Indigenous_art_of_the_Americas"
        ],
        # Cultural heritage
        "heritage": [
            "Category:World_Heritage_Sites", "Category:Art_museums_and_galleries",
            "Category:National_museums", "Category:Archaeological_sites",
            "Category:Cultural_landscapes", "Category:Historic_monuments",
            "Category:Living_Human_Treasures", "Category:Intangible_cultural_heritage"
        ]
    }

    # ========== MATERIALS AND TECHNIQUES ==========

    MATERIALS = {
        "painting_materials": [
            "oil paint", "watercolor", "acrylic", "tempera", "fresco", "encaustic",
            "ink", "gouache", "pastel", "charcoal", "pencil"
        ],
        "sculpture_materials": [
            "marble", "bronze", "wood", "stone", "ivory", "terracotta",
            "plaster", "metal", "found objects", "mixed media"
        ],
        "craft_materials": [
            "clay", "ceramic", "glass", "textile", "fiber", "paper",
            "leather", "metal", "wood", "bamboo", "lacquer", "pigment"
        ],
        "techniques": [
            "fresco painting", "oil painting technique", "watercolor technique",
            "woodcut", "engraving", "etching", "lithography", "screen printing",
            "weaving", "embroidery", "casting", "carving", "modeling"
        ]
    }

    # ========== HELPER METHODS ==========

    @classmethod
    def get_all_categories(cls) -> List[str]:
        """
        获取所有Wikipedia文化艺术分类

        Returns:
            如果扩展分类可用，返回500+分类
            否则返回基础90+分类
        """
        if USE_EXPANDED_CATEGORIES:
            # Use expanded categories (500+)
            return ExpandedWikiCulturalCategories.get_all_categories()
        else:
            # Use basic categories (90+)
            all_cats = []
            for category_list in cls.WIKIPEDIA_CATEGORIES.values():
                all_cats.extend(category_list)
            return all_cats

    @classmethod
    def get_all_art_types(cls) -> List[str]:
        """获取所有艺术类型"""
        all_types = []
        for type_list in cls.ART_TYPES.values():
            all_types.extend(type_list)
        return list(set(all_types))

    @classmethod
    def get_all_regions(cls) -> List[str]:
        """获取所有地区"""
        all_regions = []
        for region_list in cls.REGIONS.values():
            all_regions.extend(region_list)
        return list(set(all_regions))

    @classmethod
    def get_all_movements(cls) -> List[str]:
        """获取所有艺术运动"""
        all_movements = []
        for movement_list in cls.MOVEMENTS.values():
            all_movements.extend(movement_list)
        return list(set(all_movements))

    @classmethod
    def generate_random_combination(cls) -> Dict[str, str]:
        """
        生成随机的文化艺术探索组合
        Returns: dict with art_type, period, region, movement, material
        """
        # Random art type
        all_art_types = cls.get_all_art_types()
        art_type = random.choice(all_art_types)

        # Random period
        era = random.choice(list(cls.TIME_PERIODS.keys()))
        period = random.choice(cls.TIME_PERIODS[era])

        # Random region
        region = random.choice(cls.get_all_regions())

        # Random movement
        movement = random.choice(cls.get_all_movements())

        # Random material (if applicable)
        all_materials = []
        for material_list in cls.MATERIALS.values():
            all_materials.extend(material_list)
        material = random.choice(all_materials)

        return {
            "art_type": art_type,
            "era": era,
            "period": period,
            "region": region,
            "movement": movement,
            "material": material
        }

    @classmethod
    def generate_search_queries(cls) -> List[str]:
        """生成多样化的文化艺术搜索查询组合"""
        combinations = []

        # 1. Art Type + Region (e.g., "Chinese painting", "Indian classical music")
        art_type = random.choice(cls.get_all_art_types())
        region = random.choice(cls.get_all_regions())
        combinations.append(f"{region} {art_type}")

        # 2. Art Type + Period (e.g., "Renaissance painting", "Baroque music")
        art_type = random.choice(cls.get_all_art_types())
        era = random.choice(list(cls.TIME_PERIODS.keys()))
        period = random.choice(cls.TIME_PERIODS[era])
        combinations.append(f"{period} {art_type}")

        # 3. Movement + Region (e.g., "Impressionism in France", "Bengal School India")
        movement = random.choice(cls.get_all_movements())
        region = random.choice(cls.get_all_regions())
        combinations.append(f"{movement} {region}")

        # 4. Artist + Work (e.g., "Picasso Guernica")
        category = random.choice(list(cls.FAMOUS_ARTISTS.keys()))
        if cls.FAMOUS_ARTISTS[category]:
            artist = random.choice(cls.FAMOUS_ARTISTS[category])
            # Choose corresponding work category
            work_map = {
                "visual_artists": "visual_artworks",
                "composers": "musical_works",
                "writers": "literary_works"
            }
            work_category = work_map.get(category, "visual_artworks")
            if work_category in cls.FAMOUS_WORKS and cls.FAMOUS_WORKS[work_category]:
                work = random.choice(cls.FAMOUS_WORKS[work_category])
                combinations.append(f"{artist} {work}")

        # 5. Institution + Type (e.g., "Louvre painting collection")
        inst_category = random.choice(list(cls.INSTITUTIONS.keys()))
        if cls.INSTITUTIONS[inst_category]:
            institution = random.choice(cls.INSTITUTIONS[inst_category])
            combinations.append(f"{institution} {inst_category}")

        # 6. Material + Art Type (e.g., "oil painting technique", "bronze sculpture")
        material = random.choice(cls.MATERIALS["painting_materials"] + cls.MATERIALS["sculpture_materials"])
        art_type = random.choice(cls.get_all_art_types())
        combinations.append(f"{material} {art_type}")

        # 7. Region + Period + Art Type (e.g., "Tang Dynasty Chinese painting")
        era = random.choice(list(cls.TIME_PERIODS.keys()))
        period = random.choice(cls.TIME_PERIODS[era])
        region = random.choice(cls.get_all_regions())
        art_type = random.choice(cls.get_all_art_types())
        combinations.append(f"{period} {region} {art_type}")

        return combinations


# ============================================================================
# STATISTICS AND TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("EXPANDED CULTURAL ARTS POOLS - STATISTICS")
    print("=" * 70)

    pools = ExpandedArtsPools()

    print(f"\nArt Types: {sum(len(v) for v in pools.ART_TYPES.values())}")
    for art_type, types in pools.ART_TYPES.items():
        print(f"  - {art_type}: {len(types)}")

    print(f"\nTime Periods: {sum(len(v) for v in pools.TIME_PERIODS.values())}")
    for era, periods in pools.TIME_PERIODS.items():
        print(f"  - {era}: {len(periods)}")

    print(f"\nRegions: {sum(len(v) for v in pools.REGIONS.values())}")
    for region, regions in pools.REGIONS.items():
        print(f"  - {region}: {len(regions)}")

    print(f"\nMovements: {sum(len(v) for v in pools.MOVEMENTS.values())}")
    for movement_type, movements in pools.MOVEMENTS.items():
        print(f"  - {movement_type}: {len(movements)}")

    print(f"\nFamous Artists: {sum(len(v) for v in pools.FAMOUS_ARTISTS.values())}")
    for category, artists in pools.FAMOUS_ARTISTS.items():
        print(f"  - {category}: {len(artists)}")

    print(f"\nFamous Works: {sum(len(v) for v in pools.FAMOUS_WORKS.values())}")
    for category, works in pools.FAMOUS_WORKS.items():
        print(f"  - {category}: {len(works)}")

    print(f"\nInstitutions: {sum(len(v) for v in pools.INSTITUTIONS.values())}")
    for category, institutions in pools.INSTITUTIONS.items():
        print(f"  - {category}: {len(institutions)}")

    print(f"\nWikipedia Categories: {len(pools.get_all_categories())}")

    print("\n" + "=" * 70)
    print("SAMPLE RANDOM COMBINATIONS")
    print("=" * 70)

    for i in range(5):
        combo = pools.generate_random_combination()
        print(f"\n[{i+1}] {combo['art_type']} | {combo['period']} | "
              f"{combo['region']} | {combo['movement']}")

    print("\n" + "=" * 70)
    print("SAMPLE SEARCH QUERIES")
    print("=" * 70)

    for i in range(5):
        queries = pools.generate_search_queries()
        for j, query in enumerate(queries):
            print(f"{j+1}. {query}")
        print()
