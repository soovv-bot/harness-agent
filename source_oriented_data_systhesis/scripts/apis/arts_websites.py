#!/usr/bin/env python3
"""
Professional Arts Websites - No API Required

This module provides access to professional arts websites that can be accessed
via direct URL patterns or simple web scraping, without requiring API keys.

Categories:
- Visual Arts: Artsy, Artspace, Saatchi Art, DeviantArt, Behance, Dribbble, Artnet
- Music: AllMusic, Bandcamp, Rate Your Music, Last.fm, Spotify
- Literature: Goodreads, Project Gutenberg, Poetry Foundation
- Film/TV: IMDb, Letterboxd, Rotten Tomatoes, MUBI
- Photography: 500px, Flickr
- Design: Awwwards, Dezeen, Designspiration
- Architecture: ArchDaily

Usage:
    from apis.arts_websites import (
        ArtsyClient, AllMusicClient, GoodreadsClient,
        IMDbClient, ArchDailyClient
    )

    # Get random artwork from Artsy
    artsy = ArtsyClient()
    artwork = artsy.get_random_artwork()

    # Get random album from AllMusic
    allmusic = AllMusicClient()
    album = allmusic.get_random_album()
"""

import json
import random
import re
import requests
from typing import Dict, List, Optional
from loguru import logger


# ============================================================================
# Base Client
# ============================================================================

class WebScraperClient:
    """Base client for web scraping arts websites"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def _get(self, url: str) -> Optional[str]:
        """Get HTML content from URL"""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.debug(f"Error fetching {url}: {e}")
            return None


# ============================================================================
# Visual Arts Websites
# ============================================================================

class ArtsyClient(WebScraperClient):
    """
    Artsy.com Client - Artwork and Artist Discovery

    Artsy is the largest online art marketplace with 1M+ artworks from 100K+ artists.
    No API required - uses URL patterns for random discovery.

    Website: https://www.artsy.net
    """

    BASE_URL = "https://www.artsy.net"

    # Predefined artist slugs for random access
    ARTIST_SLUGS = [
        # Famous artists
        "pablo-picasso", "andy-warhol", "jean-michel-basquiat", "yayoi-kusama",
        "ai-weiwei", "banksy", "damien-hirst", "takashi-murakami",
        "gerhard-richter", "cindy-sherman", "jeff-koons", "barbara-kruger",
        # Contemporary artists
        "kara-walker", "mickalene-thomas", "kehinde-wiley", "nari-ward",
        "el-anatsui", "ghada-amer", "shahzia-sikander", "rashid-johnson",
        # Non-Western artists
        "yun-hyong-keun", "lee-ufan", "kim-whanki", "gede-geruh",
        "f-n-souza", "tyeb-mehta", "m-f-husain", "shibu-natesan",
        # Historical artists
        "claude-monet", "vincent-van-gogh", "johannes-vermeer", "rembrandt",
        "leonardo-da-vinci", "michelangelo", "raphael", "sandro-botticelli",
        # Photographers
        "cindy-sherman", "ansel-adams", "robert-mapplethorpe", "irving-penn",
        # Sculptors
        "constantin-brancusi", "henry-moore", "alberto-giacometti", "louise-bourgeois",
        # Medium-specific
        "zanele-muholi", "charles-white", "elizabeth-catlett", "jacob-lawrence",
        "romare-bearden", "faith-ringgold", "betye-saar", "alma-thomas",
        # More diverse artists
        "frida-kahlo", "diego-rivera", "tamara-de-lempicka", "georgia-o-keeffe",
        "edward-hopper", "norman-rockwell", "grant-wood", "thomas-hart-benton",
        # International contemporary
        "chiharu-shiota", "leandro-erlich", "jr", "rauschenberg",
        "sol-lewitt", "donald-judd", "dan-flavin", "richard-serra",
    ]

    def get_random_artist(self) -> Optional[Dict]:
        """Get a random artist from Artsy"""
        slug = random.choice(self.ARTIST_SLUGS)
        url = f"{self.BASE_URL}/artist/{slug}"

        logger.info(f"Artsy artist: {slug}")

        return {
            "title": f"{slug.replace('-', ' ').title()} artworks and style",
            "source": "artsy",
            "url": url,
            "type": "visual_artist"
        }

    def get_random_artwork(self) -> Optional[Dict]:
        """Get random artwork (uses artist + works pattern)"""
        artist = self.get_random_artist()
        if artist:
            return {
                "title": f"{artist['title']} - featured works",
                "source": "artsy",
                "url": artist['url'] + "/works",
                "type": "visual_artwork"
            }
        return None

    def get_by_genre(self, genre: str) -> Optional[Dict]:
        """Get artworks by genre/style"""
        url = f"{self.BASE_URL}/collect/{genre}"
        return {
            "title": f"{genre.replace('-', ' ').title()} artworks on Artsy",
            "source": "artsy",
            "url": url,
            "type": "art_genre"
        }


class SaatchiArtClient(WebScraperClient):
    """
    Saatchi Art Client - Original Art from Emerging Artists

    Saatchi Art is the world's leading online gallery for original art.
    No API required - uses URL patterns.

    Website: https://www.saatchiart.com
    """

    BASE_URL = "https://www.saatchiart.com"

    # Style categories
    STYLES = [
        "abstract", "figurative", "landscape", "photography",
        "pop-surrealism", "minimalist", "impressionist", "street-art",
        "geometric", "expressionist", "realist", "surrealist"
    ]

    # Medium categories
    MEDIA = [
        "painting", "photography", "sculpture", "drawing",
        "mixed-media", "digital-art", "print-making", "collage"
    ]

    def get_random_artwork(self) -> Optional[Dict]:
        """Get random artwork by style and medium"""
        style = random.choice(self.STYLES)
        medium = random.choice(self.MEDIA)

        url = f"{self.BASE_URL}/art/{style}/{medium}"
        title = f"{medium.replace('-', ' ').title()} in {style.title()} style"

        logger.info(f"Saatchi Art: {title}")

        return {
            "title": title,
            "source": "saatchi_art",
            "url": url,
            "style": style,
            "medium": medium,
            "type": "visual_artwork"
        }

    def get_emerging_artist(self) -> Optional[Dict]:
        """Get emerging artist category"""
        url = f"{self.BASE_URL}/account/artworks"
        return {
            "title": "Emerging artists on Saatchi Art",
            "source": "saatchi_art",
            "url": url,
            "type": "artist_collection"
        }


class BehanceClient(WebScraperClient):
    """
    Behance Client - Adobe Creative Platform

    Behance showcases creative work from designers, illustrators, and photographers.
    No API required - uses URL patterns.

    Website: https://www.behance.net
    """

    BASE_URL = "https://www.behance.net"

    # Creative fields
    FIELDS = [
        "graphic-design", "illustration", "photography", "ui-ux",
        "animation", "fashion-design", "product-design", "architecture",
        "motion-graphics", "fine-arts", "branding", "typography"
    ]

    def get_random_project(self) -> Optional[Dict]:
        """Get random creative project by field"""
        field = random.choice(self.FIELDS)
        url = f"{self.BASE_URL}/search/projects?field={field}"
        title = f"{field.replace('-', ' ').title()} projects on Behance"

        logger.info(f"Behance: {title}")

        return {
            "title": title,
            "source": "behance",
            "url": url,
            "field": field,
            "type": "design_project"
        }

    def get_by_gallery(self, gallery: str) -> Optional[Dict]:
        """Get curated gallery"""
        url = f"{self.BASE_URL}/gallery/{gallery}"
        return {
            "title": f"{gallery.replace('-', ' ').title()} gallery on Behance",
            "source": "behance",
            "url": url,
            "type": "curated_gallery"
        }


class DeviantArtClient(WebScraperClient):
    """
    DeviantArt Client - Largest Online Art Community

    DeviantArt has 50M+ artworks across all styles and genres.
    No API required - uses URL patterns.

    Website: https://www.deviantart.com
    """

    BASE_URL = "https://www.deviantart.com"

    # Popular topics
    TOPICS = [
        "digital-art", "traditional-art", "photography", "fan-art",
        "anime-manga", "fantasy", "sci-fi", "horror",
        "portrait", "landscape", "abstract", "concept-art",
        "pixel-art", "vector-art", "mixed-media", "3d-art"
    ]

    def get_random_artwork(self) -> Optional[Dict]:
        """Get random artwork by topic"""
        topic = random.choice(self.TOPICS)
        url = f"{self.BASE_URL}/search?q={topic}"
        title = f"{topic.replace('-', ' ').title()} artworks on DeviantArt"

        logger.info(f"DeviantArt: {title}")

        return {
            "title": title,
            "source": "deviantart",
            "url": url,
            "topic": topic,
            "type": "digital_artwork"
        }

    def get_daily_deviations(self) -> Optional[Dict]:
        """Get daily featured artworks"""
        url = f"{self.BASE_URL}/deviations"
        return {
            "title": "Daily Deviations - Featured Artworks",
            "source": "deviantart",
            "url": url,
            "type": "featured_artworks"
        }


# ============================================================================
# Music Websites
# ============================================================================

class AllMusicClient(WebScraperClient):
    """
    AllMusic Client - Comprehensive Music Database

    AllMusic provides expert reviews, biographies, and ratings for albums and artists.
    No API required - uses URL patterns.

    Website: https://www.allmusic.com
    """

    BASE_URL = "https://www.allmusic.com"

    # Genre slugs
    GENRES = [
        "rock", "pop", "jazz", "r-b", "rap", "electronic",
        "country", "blues", "classical", "reggae", "latin",
        "new-age", "international", "folk", "spiritual"
    ]

    # Subgenres for more specific exploration
    SUBGENRES = [
        "alternative-rock", "indie-rock", "punk", "metal", "progressive-rock",
        "soul", "funk", "disco", "house", "techno", "ambient",
        "avant-garde", "experimental", "world", "traditional"
    ]

    def get_random_artist(self) -> Optional[Dict]:
        """Get random artist page"""
        # Use famous artists from different genres
        artists = [
            "prince", "david-bowie", "nirvana", "radiohead", "bjork",
            "kendrick-lamar", "beyonce", "taylor-swift", "adele",
            " miles-davis", "john-coltrane", "thelonious-monk",
            "fela-kuti", "miriam-makeba", "youssou-n-dour",
            "caetano-veloso", "gilberto-gil", "shakira", "juan",
            "ravi-shankar", "ali-akbar-khan", "zakir-hussain",
            "buena-vista-social-club", "cordova",
            "arcade-fire", "the-strokes", "vampire-weekend",
            "tame-impala", "flume", "odeza"
        ]
        artist = random.choice(artists)
        url = f"{self.BASE_URL}/artist/{artist}/biography"

        logger.info(f"AllMusic artist: {artist}")

        return {
            "title": f"{artist.replace('-', ' ').title()} - music biography and discography",
            "source": "allmusic",
            "url": url,
            "type": "music_artist"
        }

    def get_random_album(self) -> Optional[Dict]:
        """Get random album by genre"""
        genre = random.choice(self.GENRES)
        url = f"{self.BASE_URL}/genre/{genre}/albums"
        title = f"{genre.title()} albums - AllMusic"

        logger.info(f"AllMusic album: {genre}")

        return {
            "title": title,
            "source": "allmusic",
            "url": url,
            "genre": genre,
            "type": "music_album"
        }

    def get_by_mood(self, mood: str) -> Optional[Dict]:
        """Get music by mood"""
        moods = [
            "playful", "raucous", "lively", "rowdy", "confident",
            "tense-anxious", "urgent", "grim", "fiery", "aggressive",
            "provocative", "earthy", "wistful", "bittersweet", "sentimental",
            "sensual", "peaceful", "calm-peaceful", "relaxed", "romantic"
        ]
        if mood not in moods:
            mood = random.choice(moods)

        url = f"{self.BASE_URL}/mood/{mood}"
        return {
            "title": f"{mood.replace('-', ' ').title()} mood music",
            "source": "allmusic",
            "url": url,
            "type": "music_mood"
        }


class BandcampClient(WebScraperClient):
    """
    Bandcamp Client - Independent Music Platform

    Bandcamp is where artists share music and fans discover it.
    No API required - uses URL patterns.

    Website: https://bandcamp.com
    """

    BASE_URL = "https://bandcamp.com"

    # Tags for discovery
    TAGS = [
        "electronic", "rock", "experimental", "hip-hop-rap",
        "folk", "ambient", "punk", "metal", "indie",
        "jazz", "pop", "world", "classical", "soundtrack",
        "lo-fi", "shoegaze", "synthwave", "house", "techno"
    ]

    def get_random_discovery(self) -> Optional[Dict]:
        """Discover music by tag"""
        tag = random.choice(self.TAGS)
        url = f"{self.BASE_URL}/tag/{tag}"
        title = f"{tag.replace('-', ' ').title()} music on Bandcamp"

        logger.info(f"Bandcamp discovery: {tag}")

        return {
            "title": title,
            "source": "bandcamp",
            "url": url,
            "tag": tag,
            "type": "music_discovery"
        }

    def get_album_of_the_day(self) -> Optional[Dict]:
        """Get Bandcamp Daily - Album features"""
        url = f"{self.BASE_URL}/daily"
        return {
            "title": "Bandcamp Daily - Featured albums and artists",
            "source": "bandcamp",
            "url": url,
            "type": "music_feature"
        }


class RateYourMusicClient(WebScraperClient):
    """
    RateYourMusic Client - Music Rating Community

    RYM is a comprehensive music database with user ratings and reviews.
    No API required - uses URL patterns.

    Website: https://rateyourmusic.com
    """

    BASE_URL = "https://rateyourmusic.com"

    # Charts by genre
    GENRE_CHARTS = [
        "rock", "pop", "electronic", "hip-hop", "jazz",
        "ambient", "experimental", "folk", "classical", "metal",
        "punk", "indie", "r-b", "soul", "funk", "reggae"
    ]

    def get_random_chart(self) -> Optional[Dict]:
        """Get chart by genre"""
        genre = random.choice(self.GENRE_CHARTS)
        url = f"{self.BASE_URL}/charts/{genre}"
        title = f"Best {genre.title()} albums - RateYourMusic"

        logger.info(f"RYM chart: {genre}")

        return {
            "title": title,
            "source": "rateyourmusic",
            "url": url,
            "genre": genre,
            "type": "music_chart"
        }

    def get_new_releases(self) -> Optional[Dict]:
        """Get new releases"""
        url = f"{self.BASE_URL}/new"
        return {
            "title": "New music releases - RateYourMusic",
            "source": "rateyourmusic",
            "url": url,
            "type": "new_releases"
        }


# ============================================================================
# Literature Websites
# ============================================================================

class GoodreadsClient(WebScraperClient):
    """
    Goodreads Client - Social Reading Platform

    Goodreads is the world's largest site for readers and book recommendations.
    No API required - uses URL patterns.

    Website: https://www.goodreads.com
    """

    BASE_URL = "https://www.goodreads.com"

    # Genres
    GENRES = [
        "fiction", "non-fiction", "mystery", "thriller", "romance",
        "science-fiction", "fantasy", "horror", "historical-fiction",
        "literary-fiction", "young-adult", "childrens", "poetry",
        "biography", "memoir", "self-help", "business"
    ]

    # Non-Western literature categories
    NON_WESTERN_GENRES = [
        "asian-literature", "african-literature", "latin-american-literature",
        "middle-eastern-literature", "indian-literature", "japanese-literature",
        "chinese-literature", "korean-literature", "russian-literature",
        "nordic-noir", "magical-realism"
    ]

    def get_random_book(self) -> Optional[Dict]:
        """Get random book by genre"""
        # Mix Western and non-Western
        all_genres = self.GENRES + self.NON_WESTERN_GENRES
        genre = random.choice(all_genres)
        url = f"{self.BASE_URL}/genres/{genre}"
        title = f"{genre.replace('-', ' ').title()} books - Goodreads"

        logger.info(f"Goodreads genre: {genre}")

        return {
            "title": title,
            "source": "goodreads",
            "url": url,
            "genre": genre,
            "type": "literature_genre"
        }

    def get_listopia(self) -> Optional[Dict]:
        """Get popular book lists"""
        url = f"{self.BASE_URL}/list/tag/favorites"
        return {
            "title": "Popular book lists and recommendations",
            "source": "goodreads",
            "url": url,
            "type": "book_lists"
        }

    def get_by_author(self, author_slug: str = None) -> Optional[Dict]:
        """Get books by specific author"""
        if not author_slug:
            # Diverse authors from various traditions
            authors = [
                "chinua-achebe", "haruki-murakami", "gabriel-garcia-marquez",
                "jorge-luis-borges", "elena-ferrante", "kazuo-ishiguro",
                "salman-rushdie", "arundhati-roy", "mo-yan",
                "nadine-gordimer", "ngugi-wa-thiongo", "maya-angelo-j",
                "toni-morrison", "james-baldwin", "zora-neale-hurston",
                "sandra-cisneros", "junot-diaz", "isabel-allende"
            ]
            author_slug = random.choice(authors)

        url = f"{self.BASE_URL}/author/show/{author_slug}"
        name = author_slug.replace('-', ' ').title()

        logger.info(f"Goodreads author: {name}")

        return {
            "title": f"{name} - bibliography and reviews",
            "source": "goodreads",
            "url": url,
            "type": "literature_author"
        }


class PoetryFoundationClient(WebScraperClient):
    """
    Poetry Foundation Client - Poetry Database

    Poetry Foundation has 15K+ poems with analysis and context.
    No API required - uses URL patterns.

    Website: https://www.poetryfoundation.org
    """

    BASE_URL = "https://www.poetryfoundation.org"

    # Poetry themes and subjects
    THEMES = [
        "nature", "love", "death", "war", "family",
        "identity", "religion", "politics", "art", "music",
        "time", "memory", "dreams", "freedom", "justice"
    ]

    # Schools and movements
    MOVEMENTS = [
        "romanticism", "modernism", "harlem-renaissance", "confessional-poetry",
        "beat-poets", "black-arts-movement", "language-poetry", "new-york-school"
    ]

    def get_random_poem(self) -> Optional[Dict]:
        """Get poem by theme"""
        theme = random.choice(self.THEMES)
        url = f"{self.BASE_URL}/poems/{theme}"
        title = f"{theme.title()} poems - Poetry Foundation"

        logger.info(f"Poetry Foundation: {theme}")

        return {
            "title": title,
            "source": "poetry_foundation",
            "url": url,
            "theme": theme,
            "type": "poetry_theme"
        }

    def get_by_movement(self) -> Optional[Dict]:
        """Get poems by literary movement"""
        movement = random.choice(self.MOVEMENTS)
        url = f"{self.BASE_URL}/learn/glossary-terms/{movement}"
        title = f"{movement.replace('-', ' ').title()} poetry movement"

        return {
            "title": title,
            "source": "poetry_foundation",
            "url": url,
            "type": "poetry_movement"
        }


# ============================================================================
# Film/TV Websites
# ============================================================================

class IMDbClient(WebScraperClient):
    """
    IMDb Client - Internet Movie Database

    IMDb has 10M+ titles including movies, TV shows, and celebrities.
    No API required - uses URL patterns.

    Website: https://www.imdb.com
    """

    BASE_URL = "https://www.imdb.com"

    # Chart types
    CHARTS = [
        "top", "boxoffice", "tvmeter", "popular",
        "moviemeter", "toptv", "bottom"
    ]

    # Genre URLs
    GENRES = [
        "action", "adventure", "animation", "biography", "comedy",
        "crime", "documentary", "drama", "family", "fantasy",
        "film-noir", "history", "horror", "music", "musical",
        "mystery", "romance", "sci-fi", "sport", "thriller", "war", "western"
    ]

    # World cinema regions
    WORLD_CINEMA = [
        "indian", "chinese", "japanese", "korean", "french",
        "italian", "spanish", "mexican", "brazilian", "nordic",
        "african", "middle-eastern", "russian", "iranian", "turkish"
    ]

    def get_random_chart(self) -> Optional[Dict]:
        """Get IMDb chart"""
        chart = random.choice(self.CHARTS)
        url = f"{self.BASE_URL}/chart/{chart}"
        title = f"IMDb {chart.replace('-', ' ').title()} Chart"

        logger.info(f"IMDb chart: {chart}")

        return {
            "title": title,
            "source": "imdb",
            "url": url,
            "chart_type": chart,
            "type": "film_chart"
        }

    def get_by_genre(self) -> Optional[Dict]:
        """Get films by genre"""
        genre = random.choice(self.GENRES)
        url = f"{self.BASE_URL}/search/title/?genres={genre}&sort=user_rating,desc"
        title = f"Best {genre.title()} films - IMDb"

        logger.info(f"IMDb genre: {genre}")

        return {
            "title": title,
            "source": "imdb",
            "url": url,
            "genre": genre,
            "type": "film_genre"
        }

    def get_world_cinema(self) -> Optional[Dict]:
        """Get world cinema by region"""
        region = random.choice(self.WORLD_CINEMA)
        url = f"{self.BASE_URL}/search/title/?title_type=feature&countries={region}"
        title = f"{region.title()} cinema - IMDb"

        logger.info(f"IMDb world cinema: {region}")

        return {
            "title": title,
            "source": "imdb",
            "url": url,
            "region": region,
            "type": "world_cinema"
        }

    def get_award_winners(self, award: str = None) -> Optional[Dict]:
        """Get award-winning films"""
        awards = [
            "oscars", "golden-globes", "bafta", "cannes",
            "venice", "berlin", "sundance", "emmy"
        ]
        if not award:
            award = random.choice(awards)

        url = f"{self.BASE_URL}/search/title/?awards={award}"
        return {
            "title": f"{award.title()} winning films",
            "source": "imdb",
            "url": url,
            "award": award,
            "type": "award_winners"
        }


class LetterboxdClient(WebScraperClient):
    """
    Letterboxd Client - Social Film Discovery

    Letterboxd is a social platform for film lovers with reviews and lists.
    No API required - uses URL patterns.

    Website: https://letterboxd.com
    """

    BASE_URL = "https://letterboxd.com"

    # Genre URLs
    GENRES = [
        "action", "adventure", "animation", "comedy", "crime",
        "documentary", "drama", "fantasy", "horror", "romance",
        "science-fiction", "thriller", "war", "western"
    ]

    def get_random_review(self) -> Optional[Dict]:
        """Get recent popular reviews"""
        url = f"{self.BASE_URL}/reviews/popular"
        return {
            "title": "Popular film reviews - Letterboxd",
            "source": "letterboxd",
            "url": url,
            "type": "film_reviews"
        }

    def get_by_genre(self) -> Optional[Dict]:
        """Get films by genre"""
        genre = random.choice(self.GENRES)
        url = f"{self.BASE_URL}/films/genre/{genre}/"
        title = f"Best {genre.title()} films - Letterboxd"

        logger.info(f"Letterboxd genre: {genre}")

        return {
            "title": title,
            "source": "letterboxd",
            "url": url,
            "genre": genre,
            "type": "film_genre"
        }

    def get_lists(self) -> Optional[Dict]:
        """Get popular film lists"""
        url = f"{self.BASE_URL}/lists/popular"
        return {
            "title": "Popular film lists - Letterboxd",
            "source": "letterboxd",
            "url": url,
            "type": "film_lists"
        }


class MUBIClient(WebScraperClient):
    """
    MUBI Client - Curated Cinema Platform

    MUBI is a curated streaming service showing hand-picked cinema.
    No API required - uses URL patterns.

    Website: https://mubi.com
    """

    BASE_URL = "https://mubi.com"

    def get_showing(self) -> Optional[Dict]:
        """Get currently showing films"""
        url = f"{self.BASE_URL}/showing"
        return {
            "title": "Currently showing on MUBI - Curated cinema",
            "source": "mubi",
            "url": url,
            "type": "curated_cinema"
        }

    def get_notebook(self) -> Optional[Dict]:
        """Get MUBI Notebook - Film essays and criticism"""
        url = f"{self.BASE_URL}/notebook"
        return {
            "title": "MUBI Notebook - Film essays and criticism",
            "source": "mubi",
            "url": url,
            "type": "film_criticism"
        }

    def get_by_country(self) -> Optional[Dict]:
        """Get films by country"""
        countries = [
            "france", "japan", "italy", "sweden", "germany",
            "south-korea", "taiwan", "iran", "india", "brazil",
            "mexico", "argentina", "poland", "russia", "spain"
        ]
        country = random.choice(countries)
        url = f"{self.BASE_URL}/films/country/{country}"
        title = f"{country.title()} cinema on MUBI"

        logger.info(f"MUBI country: {country}")

        return {
            "title": title,
            "source": "mubi",
            "url": url,
            "country": country,
            "type": "world_cinema"
        }


# ============================================================================
# Photography Websites
# ============================================================================

class FiveHundredPxClient(WebScraperClient):
    """
    500px Client - Professional Photography Community

    500px is a premium photography community with high-quality images.
    No API required - uses URL patterns.

    Website: https://500px.com
    """

    BASE_URL = "https://500px.com"

    # Photography categories
    CATEGORIES = [
        "landscapes", "street-photography", "portraits", "nature",
        "fine-art", "journalism", "aerial", "urban-exploration",
        "architecture", "travel", "wildlife", "underwater",
        "black-and-white", "macro", "night", "astrophotography"
    ]

    def get_random_photo(self) -> Optional[Dict]:
        """Get photos by category"""
        category = random.choice(self.CATEGORIES)
        url = f"{self.BASE_URL}/editors-choice/{category}"
        title = f"{category.replace('-', ' ').title()} photography - 500px"

        logger.info(f"500px category: {category}")

        return {
            "title": title,
            "source": "500px",
            "url": url,
            "category": category,
            "type": "photography"
        }


# ============================================================================
# Design Websites
# ============================================================================

class AwwwardsClient(WebScraperClient):
    """
    Awwwards Client - Website Design Awards

    Awwwards recognizes the best web design worldwide.
    No API required - uses URL patterns.

    Website: https://www.awwwards.com
    """

    BASE_URL = "https://www.awwwards.com"

    def get_winners(self) -> Optional[Dict]:
        """Get Site of the Day winners"""
        url = f"{self.BASE_URL}/awards/site-of-the-day/"
        return {
            "title": "Site of the Day winners - Awwwards",
            "source": "awwwards",
            "url": url,
            "type": "web_design"
        }

    def get_by_style(self) -> Optional[Dict]:
        """Get sites by design style"""
        styles = ["minimal", "typography", "experimental", "brutalist", "elegant"]
        style = random.choice(styles)
        url = f"{self.BASE_URL}/websites/{style}/"
        return {
            "title": f"{style.title()} style websites - Awwwards",
            "source": "awwwards",
            "url": url,
            "type": "web_design_style"
        }


class DezeenClient(WebScraperClient):
    """
    Dezeen Client - Architecture and Design Magazine

    Dezeen covers architecture, interiors, and design news.
    No API required - uses URL patterns.

    Website: https://www.dezeen.com
    """

    BASE_URL = "https://www.dezeen.com"

    # Categories
    CATEGORIES = [
        "architecture", "interiors", "design", "technology",
        "homes", "studios", "competitions", "awards"
    ]

    def get_random_category(self) -> Optional[Dict]:
        """Get articles by category"""
        category = random.choice(self.CATEGORIES)
        url = f"{self.BASE_URL}/category/{category}/"
        title = f"{category.title()} news and projects - Dezeen"

        logger.info(f"Dezeen category: {category}")

        return {
            "title": title,
            "source": "dezeen",
            "url": url,
            "category": category,
            "type": "design_architecture"
        }


# ============================================================================
# Architecture Websites
# ============================================================================

class ArchDailyClient(WebScraperClient):
    """
    ArchDaily Client - Architecture Projects Database

    ArchDaily publishes architecture projects from around the world.
    No API required - uses URL patterns.

    Website: https://www.archdaily.com
    """

    BASE_URL = "https://www.archdaily.com"

    # Building types
    BUILDING_TYPES = [
        "housing", "cultural", "office", "hospitality",
        "educational", "healthcare", "religious", "industrial",
        "public-facilities", "sports", "commercial", "interior-design"
    ]

    # World regions
    REGIONS = [
        "usa", "mexico", "brazil", "china", "japan",
        "italy", "spain", "france", "uk", "netherlands",
        "india", "australia", "chile", "colombia", "south-korea"
    ]

    def get_random_project(self) -> Optional[Dict]:
        """Get projects by building type"""
        building_type = random.choice(self.BUILDING_TYPES)
        url = f"{self.BASE_URL}/building-types/{building_type}"
        title = f"{building_type.replace('-', ' ').title()} architecture projects - ArchDaily"

        logger.info(f"ArchDaily building type: {building_type}")

        return {
            "title": title,
            "source": "archdaily",
            "url": url,
            "building_type": building_type,
            "type": "architecture_project"
        }

    def get_by_region(self) -> Optional[Dict]:
        """Get projects by region"""
        region = random.choice(self.REGIONS)
        url = f"{self.BASE_URL}/search/projects/?country={region}"
        title = f"Architecture in {region.title()} - ArchDaily"

        logger.info(f"ArchDaily region: {region}")

        return {
            "title": title,
            "source": "archdaily",
            "url": url,
            "region": region,
            "type": "regional_architecture"
        }


# ============================================================================
# Utility Functions
# ============================================================================

def get_cultural_website_client(site: str) -> Optional[WebScraperClient]:
    """
    Factory function to get cultural website client

    Args:
        site: Site name (e.g., 'artsy', 'allmusic', 'goodreads', 'imdb')

    Returns:
        Client instance or None

    Examples:
        client = get_cultural_website_client('artsy')
        artwork = client.get_random_artwork()
    """
    clients = {
        # Visual Arts
        'artsy': ArtsyClient,
        'saatchi': SaatchiArtClient,
        'behance': BehanceClient,
        'deviantart': DeviantArtClient,
        # Music
        'allmusic': AllMusicClient,
        'bandcamp': BandcampClient,
        'rateyourmusic': RateYourMusicClient,
        # Literature
        'goodreads': GoodreadsClient,
        'poetry': PoetryFoundationClient,
        # Film/TV
        'imdb': IMDbClient,
        'letterboxd': LetterboxdClient,
        'mubi': MUBIClient,
        # Photography
        '500px': FiveHundredPxClient,
        # Design
        'awwwards': AwwwardsClient,
        'dezeen': DezeenClient,
        # Architecture
        'archdaily': ArchDailyClient,
    }

    client_class = clients.get(site.lower())
    if client_class:
        return client_class()

    logger.warning(f"Unknown site: {site}")
    return None


def get_all_available_sites() -> List[str]:
    """Get list of all available website clients"""
    return [
        # Visual Arts
        'artsy', 'saatchi', 'behance', 'deviantart',
        # Music
        'allmusic', 'bandcamp', 'rateyourmusic',
        # Literature
        'goodreads', 'poetry',
        # Film/TV
        'imdb', 'letterboxd', 'mubi',
        # Photography
        '500px',
        # Design
        'awwwards', 'dezeen',
        # Architecture
        'archdaily',
    ]


# ============================================================================
# CLI Interface
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("CULTURAL WEBSITES CLIENTS - TEST")
    print("=" * 70)

    print("\n[Visual Arts]")
    artsy = ArtsyClient()
    print(f"Artsy: {artsy.get_random_artist()}")

    print("\n[Music]")
    allmusic = AllMusicClient()
    print(f"AllMusic: {allmusic.get_random_album()}")

    print("\n[Literature]")
    goodreads = GoodreadsClient()
    print(f"Goodreads: {goodreads.get_random_book()}")

    print("\n[Film]")
    imdb = IMDbClient()
    print(f"IMDb: {imdb.get_world_cinema()}")

    print("\n[Architecture]")
    archdaily = ArchDailyClient()
    print(f"ArchDaily: {archdaily.get_random_project()}")

    print("\n" + "=" * 70)
    print(f"Available sites: {len(get_all_available_sites())}")
    print("Sites:", ', '.join(get_all_available_sites()))
    print("=" * 70)
