#!/usr/bin/env python3
"""
Expanded Wikipedia Cultural and Arts Categories

This module provides a comprehensive, hierarchical collection of Wikipedia categories
for cultural and arts data generation, designed to cover the full breadth of human
creative expression across all cultures, periods, and forms.

Total Categories: 500+

Hierarchy:
- Primary Dimensions (8): Visual Arts, Music, Literature, Architecture, Performing Arts,
                            Film/TV, Design/Crafts, Cultural Heritage
- Secondary Dimensions (50+): Specific civilizations, art movements, techniques, themes
- Tertiary Dimensions (500+): Individual Wikipedia categories
"""

from typing import List, Dict, Set
import random


class ExpandedWikiCulturalCategories:
    """
    Expanded Wikipedia Cultural Categories

    Provides 500+ Wikipedia categories organized hierarchically for maximum coverage
    of cultural and artistic expressions from all human civilizations.
    """

    # ========================================================================
    # DIMENSION 1: SPECIFIC CIVILIZATIONS AND CULTURES (100+ categories)
    # ========================================================================

    CIVILIZATION_CATEGORIES = {
        # Ancient Civilizations (20+)
        "ancient_egypt": [
            "Category:Ancient_Egyptian_art",
            "Category:Ancient_Egyptian_sculpture",
            "Category:Ancient_Egyptian_paintings",
            "Category:Ancient_Egyptian_architecture",
            "Category:Egyptian_hieroglyphs",
            "Category:Ancient_Egyptian_jewelry",
            "Category:Ancient_Egyptian_pottery",
            "Category:Art_of_ancient_Egypt"
        ],
        "ancient_greece": [
            "Category:Ancient_Greek_art",
            "Category:Ancient_Greek_pottery",
            "Category:Ancient_Greek_sculpture",
            "Category:Ancient_Greek_architecture",
            "Category:Ancient_Greek_paintings",
            "Category:Greek_vase-painters",
            "Category:Corinthian_pottery",
            "Category:Athenian_pottery",
            "Category:Hellenistic_art",
            "Category:Art_of_ancient_Greece"
        ],
        "ancient_rome": [
            "Category:Ancient_Roman_art",
            "Category:Ancient_Roman_architecture",
            "Category:Ancient_Roman_sculpture",
            "Category:Roman_pottery",
            "Category:Roman_mosaics",
            "Category:Roman_frescoes",
            "Category:Roman_glass",
            "Category:Roman_jewelry",
            "Category:Art_of_ancient_Rome"
        ],
        "mesopotamian": [
            "Category:Ancient_Near_Eastern_art",
            "Category:Sumerian_art",
            "Category:Babylonian_art",
            "Category:Assyrian_art",
            "Category:Mesopotamian_sculpture",
            "Category:Cuneiform",
            "Category:Ziggurats"
        ],
        "persian": [
            "Category:Persian_art",
            "Category:Iranian_art",
            "Category:Achaemenid_art",
            "Category:Persian_architecture",
            "Category:Persian_miniatures",
            "Category:Persian_carpet",
            "Category:Persian_calligraphy",
            "Category:Islamic_Persian_art"
        ],
        "chinese": [
            "Category:Chinese_art",
            "Category:Chinese_paintings",
            "Category:Chinese_calligraphy",
            "Category:Chinese_ceramics",
            "Category:Chinese_pottery",
            "Category:Chinese_sculpture",
            "Category:Chinese_jade",
            "Category:Chinese_lacquerware",
            "Category:Chinese_bronzeware",
            "Category:Chinese_innovation",
            "Category:Tang_Dynasty_art",
            "Category:Song_Dynasty_art",
            "Category:Ming_Dynasty_art",
            "Category:Qing_Dynasty_art",
            "Category:Chinese_contemporary_art"
        ],
        "japanese": [
            "Category:Japanese_art",
            "Category:Japanese_paintings",
            "Category:Japanese_calligraphy",
            "Category:Japanese_prints",
            "Category:Ukiyo-e",
            "Category:Japanese_swords",
            "Category:Japanese_pottery",
            "Category:Japanese_lacquerware",
            "Category:Japanese_aesthetics",
            "Category:Japanese_contemporary_art",
            "Category:Manga",
            "Category:Anime",
            "Category:Japanese_woodblock_print",
            "Category:Edo_period_art",
            "Category:Meiji_period_art"
        ],
        "korean": [
            "Category:Korean_art",
            "Category:Korean_paintings",
            "Category:Korean_calligraphy",
            "Category:Korean_ceramics",
            "Category:Korean_pottery",
            "Category:Korean_bronzeware",
            "Category:Korean_lacquerware",
            "Category:Joseon_dynasty_art",
            "Category:Korean_contemporary_art",
            "Category:Minhwa"
        ],
        "indian": [
            "Category:Indian_art",
            "Category:Indian_paintings",
            "Category:Indian_sculpture",
            "Category:Indian_architecture",
            "Category:Indian_miniatures",
            "Category:Indian_classical_dance",
            "Category:Indian_classical_music",
            "Category:Indian_crafts",
            "Category:Mughal_art",
            "Category:Mughal_paintings",
            "Category:Mughal_architecture",
            "Category:Rajput_paintings",
            "Category:Tanjore_paintings",
            "Category:Madhubani_art",
            "Category:Indian_contemporary_art"
        ],
        "southeast_asian": [
            "Category:Southeast_Asian_art",
            "Category:Thai_art",
            "Category:Vietnamese_art",
            "Category:Cambodian_art",
            "Category:Indonesian_art",
            "Category:Burmese_art",
            "Category:Filipino_art",
            "Category:Wayang",
            "Category:Batik",
            "Category:Angkor",
            "Category:Thai_buddhist_art"
        ],
        "islamic": [
            "Category:Islamic_art",
            "Category:Islamic_architecture",
            "Category:Islamic_calligraphy",
            "Category:Islamic_miniatures",
            "Category:Islamic_ceramics",
            "Category:Islamic_metalwork",
            "Category:Islamic_textiles",
            "Category:Islamic_glass",
            "Category:Islamic_manuscripts",
            "Category:Arab_calligraphy",
            "Category:Ottoman_art",
            "Category:Mamluk_art",
            "Category:Samanid_art",
            "Category:Seljuk_art"
        ],
        "african": [
            "Category:African_art",
            "Category:West_African_art",
            "Category:East_African_art",
            "Category:Central_African_art",
            "Category:Southern_African_art",
            "Category:North_African_art",
            "Category:African_sculpture",
            "Category:African_masks",
            "Category:African_textiles",
            "Category:African_pottery",
            "Category:African_jewelry",
            "Category:African_rock_art",
            "Category:Yoruba_art",
            "Category:Akan_art",
            "Category:Benin_bronzes",
            "Category:Shona_sculpture"
        ],
        "pre_columbian": [
            "Category:Pre-Columbian_art",
            "Category:Mesoamerican_art",
            "Category:Andean_art",
            "Category:Aztec_art",
            "Category:Maya_art",
            "Category:Inca_art",
            "Category:Olmec_art",
            "Category:Teotihuacan",
            "Category:Mochica",
            "Category:Nazca_lines",
            "Category:Pre-Columbian_sculpture",
            "Category:Pre-Columbian_textiles",
            "Category:Pre-Columbian_ceramics",
            "Category:Pre-Columbian_jewelry"
        ],
        "native_american": [
            "Category:Native_American_art",
            "Category:First_Nations_art",
            "Category:Inuit_art",
            "Category:Navajo_art",
            "Category:Plains_Indians_art",
            "Category:Northwest_Coast_art",
            "Category:Native_American_textiles",
            "Category:Native_American_pottery",
            "Category:Native_American_basketry",
            "Category:Totem_poles",
            "Category:Native_American_contemporary_art"
        ],
        "european_periods": [
            "Category:Medieval_art",
            "Category:Romanesque_art",
            "Category:Gothic_art",
            "Category:Renaissance_art",
            "Category:Baroque_art",
            "Category:Rococo",
            "Category:Neoclassicism",
            "Category:Romanticism",
            "Category:Realism",
            "Category:Art_Nouveau",
            "Category:Modern_art"
        ]
    }

    # ========================================================================
    # DIMENSION 2: ART MOVEMENTS AND SCHOOLS (100+ categories)
    # ========================================================================

    MOVEMENT_CATEGORIES = {
        # Renaissance to 19th Century (15+)
        "renaissance": [
            "Category:Italian_Renaissance_painting",
            "Category:Italian_Renaissance_sculpture",
            "Category:Northern_Renaissance",
            "Category:Dutch_Golden_Age_painting",
            "Category:Flemish_Painting",
            "Category:Spanish_Renaissance_art",
            "Category:French_Renaissance_art",
            "Category:English_Renaissance_art",
            "Category:Renaissance_portraits",
            "Category:Renaissance_drawings"
        ],
        "baroque": [
            "Category:Baroque_painting",
            "Category:Baroque_sculpture",
            "Category:Baroque_architecture",
            "Category:Italian_Baroque",
            "Category:Flemish_Baroque",
            "Category:Dutch_Baroque",
            "Category:Spanish_Baroque",
            "Category:French_Baroque",
            "Category:German_Baroque"
        ],
        "rococo": [
            "Category:Rococo",
            "Category:Rococo_painting",
            "Category:Rococo_sculpture",
            "Category:French_Rococo",
            "Category:German_Rococo",
            "Category:Italian_Rococo"
        ],
        "neoclassicism": [
            "Category:Neoclassicism",
            "Category:Neoclassical_architecture",
            "Category:Neoclassical_sculpture",
            "Category:Neoclassical_painting"
        ],
        "romanticism": [
            "Category:Romanticism",
            "Category:Romantic_painting",
            "Category:Romanticism_in_literature",
            "Category:Romantic_music",
            "Category:German_Romanticism",
            "Category:English_Romanticism",
            "Category:French_Romanticism"
        ],
        "realism": [
            "Category:Realism",
            "Category:Realism_(arts)",
            "Category:Realist_painting",
            "Category:Social_Realism",
            "Category:French_Realism",
            "Category:American_Realism"
        ],
        # Modernism (40+)
        "impressionism": [
            "Category:Impressionism",
            "Category:Impressionist_painters",
            "Category:French_Impressionism",
            "Category:American_Impressionism",
            "Category:Post-Impressionism",
            "Category:Neo-impressionism",
            "Category:Impressionist_music",
            "Category:Impressionist_literature"
        ],
        "symbolism": [
            "Category:Symbolism",
            "Category:Symbolist_painters",
            "Category:Symbolism_in_literature",
            "Category:French_Symbolism",
            "Category:Russian_Symbolism"
        ],
        "art_nouveau": [
            "Category:Art_Nouveau",
            "Category:Art_Nouveau_architecture",
            "Category:Art_Nouveau_painters",
            "Category:Jugendstil",
            "Category:Modernisme",
            "Category:Secession",
            "Category:Arts_and_Crafts_movement"
        ],
        "expressionism": [
            "Category:Expressionism",
            "Category:German_Expressionism",
            "Category:Expressionist_painting",
            "Category:Expressionist_literature",
            "Category:Expressionist_music",
            "Category:Expressionist_architecture",
            "Category:Abstract_expressionism",
            "Category:Neo-expressionism"
        ],
        "cubism": [
            "Category:Cubism",
            "Category:Cubist_painters",
            "Category:Analytic_Cubism",
            "Category:Synthetic_Cubism",
            "Category:Orphism",
            "Category:Crystal_Cubism"
        ],
        "futurism": [
            "Category:Futurism",
            "Category:Italian_Futurism",
            "Category:Russian_Futurism",
            "Category:Futurist_architecture",
            "Category:Futurist_music",
            "Category:Futurist_literature"
        ],
        "dada": [
            "Category:Dada",
            "Category:Dadaist_artists",
            "Category:Dada_music",
            "Category:Dada_literature",
            "Category:Dada_films"
        ],
        "surrealism": [
            "Category:Surrealism",
            "Category:Surrealist_artists",
            "Category:Surrealist_paintings",
            "Category:Surrealist_cinema",
            "Category:Surrealist_literature",
            "Category:Surrealist_music",
            "Category:Magic_realism"
        ],
        "bauhaus": [
            "Category:Bauhaus",
            "Category:Bauhaus_artists",
            "Category:Bauhaus_architecture",
            "Category:Bauhaus_design",
            "Category:De_Stijl"
        ],
        "abstract": [
            "Category:Abstract_art",
            "Category:Abstract_painters",
            "Category:Abstract_sculpture",
            "Category:Abstract_expressionism",
            "Category:Abstract_imagists",
            "Category:Lyrical_abstraction",
            "Category:Hard-edge_painting",
            "Category:Color_field_painting"
        ],
        "pop_art": [
            "Category:Pop_art",
            "Category:Pop_artists",
            "Category:American_Pop_art",
            "Category:British_Pop_art",
            "Category:Pop_art_movement"
        ],
        "minimalism": [
            "Category:Minimalism",
            "Category:Minimalist_art",
            "Category:Minimalist_music",
            "Category:Minimalist_architecture",
            "Category:Post-minimalism"
        ],
        "conceptual": [
            "Category:Conceptual_art",
            "Category:Conceptual_artists",
            "Category:Performance_art",
            "Category:Installation_art",
            "Category:Video_art",
            "Category:Land_art",
            "Category:Earth_art",
            "Category:Body_art"
        ],
        # Contemporary (20+)
        "contemporary": [
            "Category:Contemporary_art",
            "Category:Contemporary_painters",
            "Category:Contemporary_sculptors",
            "Category:Digital_art",
            "Category:New_media_art",
            "Category:Internet_art",
            "Category:Generative_art",
            "Category:Interactive_art",
            "Category:Bio_art",
            "Category:Street_art",
            "Category:Graffiti",
            "Category:Urban_art",
            "Category:Postmodern_art",
            "Category:Postmodernism",
            "Category:Appropriation_art",
            "Category:Young_British_Artists"
        ]
    }

    # ========================================================================
    # DIMENSION 3: TECHNIQUES AND MATERIALS (80+ categories)
    # ========================================================================

    TECHNIQUE_CATEGORIES = {
        # Painting Techniques (20+)
        "painting_media": [
            "Category:Oil_painting",
            "Category:Watercolor_painting",
            "Category:Acrylic_painting",
            "Category:Gouache",
            "Category:Tempera",
            "Category:Pastel",
            "Category:Charcoal_drawing",
            "Category:Ink_wash_painting",
            "Category:Encaustic_painting",
            "Category:Fresco",
            "Category:Mosaic",
            "Category:Digital_painting",
            "Category:Spray_painting",
            "Category:Finger_painting"
        ],
        "drawing": [
            "Category:Drawing",
            "Category:Sketches",
            "Category:Illustration",
            "Category:Technical_drawing",
            "Category:Architectural_drawing",
            "Category:Cartooning",
            "Category:Comics",
            "Category:Manga",
            "Category:Graphic_novel",
            "Category:Storyboarding"
        ],
        "printmaking": [
            "Category:Printmaking",
            "Category:Woodcut",
            "Category:Engraving",
            "Category:Etching",
            "Category:Mezzotint",
            "Category:Aquatint",
            "Category:Drypoint",
            "Category:Lithography",
            "Category:Screen_printing",
            "Category:Monotyping",
            "Category:Linocut",
            "Category:Chiaroscuro_woodcut"
        ],
        # Sculpture Materials (15+)
        "sculpture_materials": [
            "Category:Stone_sculpture",
            "Category:Marble_sculpture",
            "Category:Wood_carving",
            "Category:Ivory_carving",
            "Category:Bronze_sculpture",
            "Category:Metal_sculpture",
            "Category:Steel_sculpture",
            "Category:Clay_sculpture",
            "Category:Terra_cotta",
            "Category:Plaster_sculpture",
            "Category:Wax_sculpture",
            "Category:Glass_sculpture",
            "Category:Ice_sculpture",
            "Category:Sand_sculpture",
            "Category:Found_object"
        ],
        # Craft Techniques (20+)
        "crafts": [
            "Category:Pottery",
            "Category:Ceramics",
            "Category:Glass_art",
            "Category:Glassblowing",
            "Category:Stained_glass",
            "Category:Textile_arts",
            "Category:Weaving",
            "Category:Embroidery",
            "Category:Knitting",
            "Category:Crochet",
            "Category:Tapestry",
            "Category:Quilting",
            "Category:Batik",
            "Category:Ikat",
            "Category:Dyeing",
            "Category:Silk",
            "Category:Wool",
            "Category:Lace",
            "Category:Felt",
            "Category:Leather_craft",
            "Category:Bookbinding",
            "Category:Papermaking",
            "Category:Calligraphy",
            "Category:Jewelry",
            "Category:Metalworking",
            "Category:Blacksmithing",
            "Category:Goldsmithing",
            "Category:Silversmithing"
        ],
        # Photography (10+)
        "photography": [
            "Category:Photography_by_genre",
            "Category:Portrait_photography",
            "Category:Landscape_photography",
            "Category:Documentary_photography",
            "Category:Street_photography",
            "Category:Fine_art_photography",
            "Category:Fashion_photography",
            "Category:Wildlife_photography",
            "Category:Architectural_photography",
            "Category:Black_and_white_photography",
            "Category:Digital_photography",
            "Category:Analog_photography"
        ]
    }

    # ========================================================================
    # DIMENSION 4: THEMES AND SUBJECTS (60+ categories)
    # ========================================================================

    THEME_CATEGORIES = {
        # Religious Themes (15+)
        "religious_art": [
            "Category:Religious_art",
            "Category:Christian_art",
            "Category:Biblical_art",
            "Category:Saints_in_art",
            "Category:Madonna_and_Child",
            "Category:Crucifixion",
            "Category:Depiction_of_Jesus",
            "Category:Last_Supper",
            "Category:Buddhist_art",
            "Category:Buddha_statues",
            "Category:Hindu_art",
            "Category:Hindu_deities_in_art",
            "Category:Islamic_calligraphy",
            "Category:Jewish_art",
            "Category:Sikh_art",
            "Category:Religious_iconography",
            "Category:Altarpieces",
            "Category:Icons"
        ],
        # Genre/Subject (20+)
        "genres": [
            "Category:Genre_paintings",
            "Category:Portrait_painting",
            "Category:Self-portraits",
            "Category:Landscape_art",
            "Category:Marine_art",
            "Category:Cityscape",
            "Category:Still_life_painting",
            "Category:Vanitas",
            "Category:History_painting",
            "Category:Battle_paintings",
            "Category:Animal_painting",
            "Category:Flower_painting",
            "Category: Nude_(art)",
            "Category:Allegory",
            "Category:Mythological_paintings",
            "Category:Fantasy_art",
            "Category:Science_fiction_art",
            "Category:Horror_art"
        ],
        # Social Themes (10+)
        "social_themes": [
            "Category:Political_art",
            "Category:War_art",
            "Category:Protest_art",
            "Category:Feminist_art",
            "Category:Social_realism",
            "Category:Propaganda",
            "Category:Satire",
            "Category:Caricature",
            "Category:Cartoon",
            "Category:Editorial_cartoon"
        ],
        # Cultural Themes (15+)
        "cultural_themes": [
            "Category:Everyday_life",
            "Category:Domestic_life",
            "Category:Rural_life",
            "Category:Urban_life",
            "Category:Workers",
            "Category:Labor",
            "Category:Leisure",
            "Category:Sports",
            "Category:Games",
            "Category:Festival",
            "Category:Celebration",
            "Category:Ritual",
            "Category:Custom",
            "Category:Tradition",
            "Category:Music_in_art",
            "Category:Dance_in_art",
            "Category:Theater_in_art"
        ]
    }

    # ========================================================================
    # DIMENSION 5: INTANGIBLE CULTURAL HERITAGE (40+ categories)
    # ========================================================================

    INTANGIBLE_HERITAGE_CATEGORIES = {
        # Performing Arts (15+)
        "performing_traditions": [
            "Category:Folk_music",
            "Category:Traditional_music",
            "Category:Folk_dance",
            "Category:Traditional_dance",
            "Category:Folk_theater",
            "Category:Traditional_theater",
            "Category:Puppetry",
            "Category:Shadow_play",
            "Category:Storytelling",
            "Category:Oral_tradition",
            "Category:Epic_poetry",
            "Category:Ballad",
            "Category:Folk_song",
            "Category:Work_song",
            "Category:Lullaby",
            "Category:Children's_music",
            "Category:Dance_music"
        ],
        # Crafts and Skills (15+)
        "traditional_crafts": [
            "Category:Handicraft",
            "Category:Traditional_medicine",
            "Category:Traditional_clothing",
            "Category:Traditional_architecture",
            "Category:Vernacular_architecture",
            "Category:Traditional_food",
            "Category:Culinary_traditions",
            "Category:Foodways",
            "Category:Traditional_games",
            "Category:Traditional_sports",
            "Category:Martial_arts",
            "Category:Craft_industry",
            "Category:Artisan",
            "Category:Guild",
            "Category:Apprenticeship"
        ],
        # Cultural Practices (10+)
        "cultural_practices": [
            "Category:Ceremony",
            "Category:Ritual",
            "Category:Festival",
            "Category:Pilgrimage",
            "Category:Rite_of_passage",
            "Category:Wedding_traditions",
            "Category:Funeral_practices",
            "Category:Religious_festivals",
            "Category:Seasonal_festivals",
            "Category:Harvest_festivals",
            "Category:New_Year_celebrations",
            "Category:Cultural_landscapes"
        ]
    }

    # ========================================================================
    # DIMENSION 6: INSTITUTIONS AND VENUES (30+ categories)
    # ========================================================================

    INSTITUTION_CATEGORIES = {
        # Museums (15+)
        "museums": [
            "Category:Art_museums",
            "Category:Art_museums_and_galleries",
            "Category:National_museums",
            "Category:Contemporary_art_museums",
            "Category:Science_museums",
            "Category:History_museums",
            "Category:Archaeological_museums",
            "Category:Ethnographic_museums",
            "Category:Open-air_museums",
            "Category:Virtual_museums",
            "Category:Museums_by_country",
            "Category:Museums_in_Europe",
            "Category:Museums_in_North_America",
            "Category:Museums_in_Asia",
            "Category:Museums_in_Africa",
            "Category:Private_collections",
            "Category:Royal_collections"
        ],
        # Performance Venues (10+)
        "venues": [
            "Category:Opera_houses",
            "Category:Concert_halls",
            "Category:Theaters",
            "Category:Dance_studios",
            "Category:Music_venues",
            "Category:Jazz_clubs",
            "Category:Festivals",
            "Category:Film_festivals",
            "Category:Music_festivals",
            "Category:Literary_festivals",
            "Category:Cultural_festivals"
        ]
    }

    # ========================================================================
    # DIMENSION 7: LITERATURE AND WRITING (30+ categories)
    # ========================================================================

    LITERATURE_CATEGORIES = {
        # Literary Forms (15+)
        "forms": [
            "Category:Poetry",
            "Category:Epic_poetry",
            "Category:Lyric_poetry",
            "Category:Narrative_poetry",
            "Category:Drama",
            "Category:Tragedy",
            "Category:Comedy",
            "Category:Satire",
            "Category:Prose",
            "Category:Novel",
            "Category:Short_stories",
            "Category:Novella",
            "Category:Flash_fiction",
            "Category:Essay",
            "Category:Biography",
            "Category:Autobiography",
            "Category:Memoir",
            "Category:History",
            "Category:Philosophy",
            "Category:Religious_text"
        ],
        # Literary Movements (10+)
        "movements": [
            "Category:Romanticism_in_literature",
            "Category:Realism_in_literature",
            "Category:Modernist_literature",
            "Category:Postmodern_literature",
            "Category:Beat_generation",
            "Category:Harlem_Renaissance",
            "Category:Lost_Generation",
            "Category:Negritude",
            "Category:Magical_realism",
            "Category:Existentialist_literature"
        ],
        # Oral Traditions (5+)
        "oral": [
            "Category:Oral_tradition",
            "Category:Folklore",
            "Category:Mythology",
            "Category:Legend",
            "Category:Fairy_tale",
            "Category:Fable"
        ]
    }

    # ========================================================================
    # DIMENSION 8: MUSIC AND SOUND (40+ categories)
    # ========================================================================

    MUSIC_CATEGORIES = {
        # Music Genres (20+)
        "genres": [
            "Category:Classical_music",
            "Category:Opera",
            "Category:Choral_music",
            "Category:Chamber_music",
            "Category:Orchestral_music",
            "Category:Symphony",
            "Category:Concerto",
            "Category:Sonata",
            "Category:Jazz",
            "Category:Blues",
            "Category:Rock_music",
            "Category:Pop_music",
            "Category:Folk_music",
            "Category:Country_music",
            "Category:Electronic_music",
            "Category:Hip_hop_music",
            "Category:Reggae",
            "Category:Soul_music",
            "Category:Funk",
            "Category:Disco",
            "Category:Punk_rock",
            "Category:Metal_music",
            "Category:Ambient_music",
            "Category:Experimental_music"
        ],
        # Traditional Music (10+)
        "traditional": [
            "Category:Traditional_music_by_country",
            "Category:Folk_songs",
            "Category:Work_songs",
            "Category:Ballads",
            "Category:Dance_music",
            "Category:Religious_music",
            "Category:Ritual_music",
            "Category:Ceremonial_music",
            "Category:Shanties",
            "Category:Lullabies",
            "Category:Children's_songs"
        ],
        # Music Instruments (10+)
        "instruments": [
            "Category:Musical_instruments",
            "Category:String_instruments",
            "Category:Wind_instruments",
            "Category:Percussion_instruments",
            "Category:Keyboard_instruments",
            "Category:Electronic_musical_instruments",
            "Category:Folk_musical_instruments",
            "Category:Traditional_musical_instruments",
            "Category:Musical_instruments_by_country"
        ]
    }

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    @classmethod
    def get_all_categories(cls) -> List[str]:
        """获取所有Wikipedia文化艺术分类（500+）"""
        all_cats = []

        # Add all dimension categories
        for dimension_dict in [
            cls.CIVILIZATION_CATEGORIES,
            cls.MOVEMENT_CATEGORIES,
            cls.TECHNIQUE_CATEGORIES,
            cls.THEME_CATEGORIES,
            cls.INTANGIBLE_HERITAGE_CATEGORIES,
            cls.INSTITUTION_CATEGORIES,
            cls.LITERATURE_CATEGORIES,
            cls.MUSIC_CATEGORIES
        ]:
            for category_list in dimension_dict.values():
                all_cats.extend(category_list)

        # Remove duplicates while preserving order
        seen = set()
        unique_cats = []
        for cat in all_cats:
            if cat not in seen:
                seen.add(cat)
                unique_cats.append(cat)

        return unique_cats

    @classmethod
    def get_categories_by_dimension(cls, dimension: str) -> List[str]:
        """按维度获取分类"""
        dimension_map = {
            'civilization': cls.CIVILIZATION_CATEGORIES,
            'movement': cls.MOVEMENT_CATEGORIES,
            'technique': cls.TECHNIQUE_CATEGORIES,
            'theme': cls.THEME_CATEGORIES,
            'heritage': cls.INTANGIBLE_HERITAGE_CATEGORIES,
            'institution': cls.INSTITUTION_CATEGORIES,
            'literature': cls.LITERATURE_CATEGORIES,
            'music': cls.MUSIC_CATEGORIES,
        }

        if dimension in dimension_map:
            all_cats = []
            for category_list in dimension_map[dimension].values():
                all_cats.extend(category_list)
            return all_cats

        return []

    @classmethod
    def get_random_category(cls, dimension: str = None) -> str:
        """获取随机分类"""
        if dimension:
            categories = cls.get_categories_by_dimension(dimension)
        else:
            categories = cls.get_all_categories()

        if categories:
            return random.choice(categories)
        return ""

    @classmethod
    def get_sample_categories(cls, n: int = 20) -> List[str]:
        """获取n个随机分类作为样本"""
        all_cats = cls.get_all_categories()
        return random.sample(all_cats, min(n, len(all_cats)))

    @classmethod
    def get_statistics(cls) -> Dict[str, int]:
        """获取分类统计信息"""
        stats = {}

        stats['civilization'] = sum(len(cats) for cats in cls.CIVILIZATION_CATEGORIES.values())
        stats['movement'] = sum(len(cats) for cats in cls.MOVEMENT_CATEGORIES.values())
        stats['technique'] = sum(len(cats) for cats in cls.TECHNIQUE_CATEGORIES.values())
        stats['theme'] = sum(len(cats) for cats in cls.THEME_CATEGORIES.values())
        stats['heritage'] = sum(len(cats) for cats in cls.INTANGIBLE_HERITAGE_CATEGORIES.values())
        stats['institution'] = sum(len(cats) for cats in cls.INSTITUTION_CATEGORIES.values())
        stats['literature'] = sum(len(cats) for cats in cls.LITERATURE_CATEGORIES.values())
        stats['music'] = sum(len(cats) for cats in cls.MUSIC_CATEGORIES.values())

        stats['total'] = sum(stats.values())

        return stats


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("EXPANDED WIKIPEDIA CULTURAL CATEGORIES - STATISTICS")
    print("=" * 70)

    stats = ExpandedWikiCulturalCategories.get_statistics()

    print(f"\nTotal Categories: {stats['total']}")
    print("\nBy Dimension:")
    for dimension, count in stats.items():
        if dimension != 'total':
            print(f"  {dimension:20s}: {count:4d} categories")

    print("\n" + "=" * 70)
    print("SAMPLE CATEGORIES (20 random)")
    print("=" * 70)

    samples = ExpandedWikiCulturalCategories.get_sample_categories(20)
    for i, cat in enumerate(samples, 1):
        print(f"{i:2d}. {cat}")

    print("\n" + "=" * 70)
    print("SAMPLES BY DIMENSION")
    print("=" * 70)

    for dimension in ['civilization', 'movement', 'technique', 'theme', 'heritage']:
        print(f"\n{dimension.upper()} (5 samples):")
        samples = ExpandedWikiCulturalCategories.get_categories_by_dimension(dimension)
        for sample in random.sample(samples, min(5, len(samples))):
            print(f"  - {sample}")
