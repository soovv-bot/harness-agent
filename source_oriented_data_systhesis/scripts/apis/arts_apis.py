#!/usr/bin/env python3
"""
API Clients for Arts Data Sources

This module provides Python clients for accessing various arts APIs
and websites that provide high-quality, structured data for art generation.

Supported APIs:
- Museums: Met Museum, MoMA, Rijksmuseum, British Museum, Smithsonian, V&A
- Art Databases: WikiArt, Google Arts & Culture
- Music: MusicBrainz, Discogs
- Literature: Open Library, Google Books
- Film: TMDb, OMDb
- Architecture/Heritage: UNESCO Heritage, ArchDaily

Usage:
    from arts_apis import MetMuseumClient, RijksmuseumClient, WikiArtClient

    # Get artwork from Met Museum
    met = MetMuseumClient()
    artwork = met.get_random_object()

    # Get artwork from Rijksmuseum
    rijks = RijksmuseumClient(api_key="your_key")
    artwork = rijks.get_random_collection()
"""

import json
import random
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from loguru import logger


# ============================================================================
# Base Client
# ============================================================================

@dataclass
class APIError(Exception):
    """Custom exception for API errors"""
    status_code: int
    message: str


class BaseClient:
    """Base class for arts API clients"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; ArtsBot/1.0)'
        })

    def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make GET request and return JSON response"""
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise APIError(401, "Authentication required")
            elif e.response.status_code == 403:
                raise APIError(403, "Access forbidden")
            elif e.response.status_code == 429:
                raise APIError(429, "Rate limit exceeded")
            else:
                raise APIError(e.response.status_code, str(e))
        except requests.exceptions.Timeout:
            raise APIError(408, "Request timeout")
        except Exception as e:
            raise APIError(500, str(e))


# ============================================================================
# Museum API Clients
# ============================================================================

class MetMuseumClient(BaseClient):
    """
    Metropolitan Museum of Art API Client

    The Met provides a completely open API for their collection of over 400,000 artworks.
    No API key required.

    API Documentation: https://metmuseum.org/api/collection
    """

    BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"

    def get_objects(self, department_ids: Optional[List[int]] = None,
                    keyword: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Search for objects in the Met collection

        Args:
            department_ids: Optional list of department IDs to filter
            keyword: Optional search keyword
            limit: Maximum number of results

        Returns:
            List of object IDs
        """
        params = {"limit": limit}

        if department_ids:
            for dept_id in department_ids:
                params.setdefault("departmentId", []).append(dept_id)

        if keyword:
            params["q"] = keyword

        try:
            data = self._get(f"{self.BASE_URL}/search", params=params)
            return data.get("objectIDs", [])[:limit]
        except Exception as e:
            logger.error(f"Met search error: {e}")
            return []

    def get_object(self, object_id: int) -> Optional[Dict]:
        """
        Get details for a specific object

        Args:
            object_id: The Met object ID

        Returns:
            Object details including title, artist, date, medium, dimensions, etc.
        """
        try:
            data = self._get(f"{self.BASE_URL}/objects/{object_id}")
            return data
        except Exception as e:
            logger.error(f"Met get_object error: {e}")
            return None

    def get_random_object(self, department_id: Optional[int] = None) -> Optional[Dict]:
        """
        Get a random object from the collection

        Args:
            department_id: Optional department ID to filter

        Returns:
            Random object details
        """
        try:
            # Get total count
            if department_id:
                objects = self.get_objects(department_ids=[department_id], limit=100)
            else:
                objects = self.get_objects(limit=100)

            if not objects:
                return None

            # Select random object
            object_id = random.choice(objects)
            return self.get_object(object_id)

        except Exception as e:
            logger.error(f"Met random_object error: {e}")
            return None

    def get_departments(self) -> List[Dict]:
        """Get all museum departments"""
        try:
            data = self._get(f"{self.BASE_URL}/departments")
            return data.get("departments", [])
        except Exception as e:
            logger.error(f"Met departments error: {e}")
            return []

    def search_by_department(self, department_id: int, limit: int = 50) -> List[Dict]:
            """Search for objects within a specific department

            Args:
                department_id: Department ID (use get_departments to find IDs)
                limit: Maximum results

            Returns:
                List of object details

            Met Department IDs (examples):
                1: American Decorative Arts
                3: Ancient Near Eastern Art
                5: Arts of Africa, Oceania, and the Americas
                6: Asian Art
                7: The Cloisters
                8: The Costume Institute
                9: Drawings and Prints
                10: Egyptian Art
                11: European Paintings
                13: Greek and Roman Art
                14: Islamic Art
                15: The Robert Lehman Collection
                16: The Libraries
                17: Medieval Art
                18: Musical Instruments
                19: 19th- and Early 20th-Century European Paintings and Sculpture
                21: Modern and Contemporary Art
            """
            try:
                objects = self.get_objects(department_ids=[department_id], limit=limit)

                results = []
                for obj_id in objects[:limit]:
                    obj = self.get_object(obj_id)
                    if obj:
                        results.append(obj)

                return results

            except Exception as e:
                logger.error(f"Met search_by_department error: {e}")
                return []


class MoMAClient(BaseClient):
    """
    Museum of Modern Art (MoMA) API Client

    MoMA provides a collection API with ~80k artists and 44k works.
    Requires free API key.

    API Documentation: https://github.com/MuseumofModernArt/collection-api
    """

    BASE_URL = "https://github.com/MuseumofModernArt/collection"
    API_URL = "https://moma.org/collection/api"

    def __init__(self, api_key: str):
        """
        Initialize MoMA client

        Args:
            api_key: MoMA Collection API key (free at https://github.com/MuseumofModernArt/collection)
        """
        super().__init__()
        self.session.headers.update({
            'X-MOMA-API-Key': api_key
        })

    def get_artists(self, query: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """
        Search for artists

        Args:
            query: Optional search term
            limit: Maximum results

        Returns:
            List of artist information
        """
        params = {"query": query or "", "limit": limit}

        try:
            data = self._get(f"{self.API_URL}/artists", params=params)
            return data
        except Exception as e:
            logger.error(f"MoMA artists error: {e}")
            return []

    def get_artworks(self, artist_id: Optional[str] = None,
                     query: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """
        Search for artworks

        Args:
            artist_id: Optional artist ID filter
            query: Optional search term
            limit: Maximum results

        Returns:
            List of artwork information
        """
        params = {"query": query or "", "limit": limit}

        if artist_id:
            params["artistId"] = artist_id

        try:
            data = self._get(f"{self.API_URL}/artworks", params=params)
            return data
        except Exception as e:
            logger.error(f"MoMA artworks error: {e}")
            return []

    def get_random_artwork(self) -> Optional[Dict]:
        """Get a random artwork from MoMA collection"""
        try:
            artworks = self.get_artworks(limit=100)
            if artworks:
                return random.choice(artworks)
        except Exception as e:
            logger.error(f"MoMA random_artwork error: {e}")
        return None


class RijksmuseumClient(BaseClient):
    """
    Rijksmuseum API Client

    The Rijksmuseum in Amsterdam provides a rich API with Dutch Golden Age masterpieces.
    Requires free API key.

    API Documentation: https://data.rijksmuseum.nl/object-metadata/api/
    """

    BASE_URL = "https://www.rijksmuseum.nl/api/en"

    def __init__(self, api_key: str):
        """
        Initialize Rijksmuseum client

        Args:
            api_key: Rijksmuseum API key (free at https://data.rijksmuseum.nl/api-keys/)
        """
        super().__init__()
        self.api_key = api_key

    def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Override to include API key"""
        if params is None:
            params = {}
        params["key"] = self.api_key
        return super()._get(url, params)

    def get_collection(self, query: Optional[str] = None,
                       maker: Optional[str] = None,
                       limit: int = 100) -> List[Dict]:
        """
        Search the collection

        Args:
            query: Optional search query
            maker: Optional artist/maker name
            limit: Maximum results

        Returns:
            List of artwork information
        """
        params = {"ps": limit, "imgonly": True}

        if query:
            params["q"] = query

        if maker:
            params["maker"] = maker

        try:
            data = self._get(f"{self.BASE_URL}/collection", params=params)
            return data.get("artObjects", [])
        except Exception as e:
            logger.error(f"Rijksmuseum collection error: {e}")
            return []

    def get_object_details(self, object_number: str) -> Optional[Dict]:
        """
        Get detailed information about an object

        Args:
            object_number: The object number (SK-C identifier)

        Returns:
            Detailed object information including description, materials, dimensions
        """
        try:
            data = self._get(f"{self.BASE_URL}/collection/{object_number}")
            return data.get("artObject", {})
        except Exception as e:
            logger.error(f"Rijksmuseum object details error: {e}")
            return None

    def get_random_collection(self) -> Optional[Dict]:
        """Get a random artwork with details"""
        try:
            # Get random page
            page = random.randint(1, 10)
            artworks = self.get_collection(limit=100)

            if not artworks:
                return None

            # Select random artwork and get details
            artwork = random.choice(artworks)
            object_number = artwork.get("objectNumber")

            if object_number:
                return self.get_object_details(object_number)

            return artwork

        except Exception as e:
            logger.error(f"Rijksmuseum random_collection error: {e}")
            return None

    def get_dutch_masters(self, limit: int = 50) -> List[Dict]:
        """
        Get Dutch Golden Age masterpieces

        Returns:
            List of Dutch Golden Age artworks
        """
        # Famous Dutch masters keywords
        masters = ["Rembrandt", "Vermeer", "Frans Hals", "Jan Steen",
                  "Jacob van Ruisdael", "Johannes Vermeer", "Mondriaan",
                  "Van Gogh"]

        master = random.choice(masters)
        return self.get_collection(maker=master, limit=limit)


class BritishMuseumClient(BaseClient):
    """
    British Museum Collection API Client

    The British Museum provides a collection API for their 8 million objects.
    No API key required for basic access.

    API Documentation: https://research.britishmuseum.org/collection-online
    """

    BASE_URL = "https://www.britishmuseum.org"

    def search_collection(self, keyword: Optional[str] = None,
                         limit: int = 50) -> List[Dict]:
        """
        Search the British Museum collection

        Note: The British Museum doesn't have a fully open API,
        so this uses the search endpoint (may require web scraping fallback)

        Args:
            keyword: Search keyword
            limit: Maximum results

        Returns:
            List of object information
        """
        # This is a placeholder - British Museum API access is limited
        # In practice, you might need to use their API beta or web scraping
        logger.warning("British Museum API access is limited - returning placeholder")
        return []

    def get_african_collections(self, limit: int = 50) -> List[Dict]:
        """Get African art and artifacts"""
        logger.warning("British Museum API access is limited - returning placeholder")
        return []

    def get_asian_collections(self, limit: int = 50) -> List[Dict]:
        """Get Asian art and artifacts"""
        logger.warning("British Museum API access is limited - returning placeholder")
        return []


class SmithsonianClient(BaseClient):
    """
    Smithsonian API Client

    Smithsonian provides multiple museum collections through their API.
    No API key required for basic access.

    API Documentation: https://edan.si.edu/openaccess/apidocs/
    """

    BASE_URL = "https://api.si.edu/openaccess/api/v1.0"

    def search(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search across all Smithsonian collections

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of object records
        """
        params = {
            "q": query,
            "rows": limit
        }

        try:
            data = self._get(f"{self.BASE_URL}/search", params=params)
            return data.get("response", {}).get("rows", [])
        except Exception as e:
            logger.error(f"Smithsonian search error: {e}")
            return []

    def get_by_category(self, category: str, limit: int = 50) -> List[Dict]:
        """
        Get objects by category

        Args:
            category: Category (e.g., "Paintings", "Sculpture", "Photography")
            limit: Maximum results

        Returns:
            List of object records
        """
        return self.search(f"{category}", limit=limit)

    def get_african_art(self, limit: int = 50) -> List[Dict]:
        """Get African art collections"""
        return self.search("African art", limit=limit)

    def get_asian_art(self, limit: int = 50) -> List[Dict]:
        """Get Asian art collections"""
        return self.search("Asian art", limit=limit)

    def get_american_indian_art(self, limit: int = 50) -> List[Dict]:
        """Get American Indian art collections"""
        return self.search("American Indian art", limit=limit)


class VAClient(BaseClient):
    """
    Victoria and Albert Museum (V&A) API Client

    The V&A is the world's leading museum of art, design and performance.
    Requires API key for full access.

    API Documentation: https://developers.vam.ac.uk/
    """

    BASE_URL = "https://api.vam.ac.uk/v2"

    def __init__(self, api_key: str):
        """
        Initialize V&A client

        Args:
            api_key: V&A API key
        """
        super().__init__()
        self.session.headers.update({
            'X-Api-Key': api_key
        })

    def search_objects(self, query: Optional[str] = None,
                      limit: int = 50) -> List[Dict]:
        """
        Search the V&A collection

        Args:
            query: Optional search query
            limit: Maximum results

        Returns:
            List of object records
        """
        params = {
            "page_size": limit
        }

        if query:
            params["q"] = query

        try:
            data = self._get(f"{self.BASE_URL}/objects/search", params=params)
            return data.get("records", [])
        except Exception as e:
            logger.error(f"V&A search error: {e}")
            return []

    def get_random_object(self) -> Optional[Dict]:
        """Get a random object from V&A collection"""
        try:
            objects = self.search_objects(limit=100)
            if objects:
                return random.choice(objects)
        except Exception as e:
            logger.error(f"V&A random_object error: {e}")
        return None

    def get_fashion_collection(self, limit: int = 50) -> List[Dict]:
        """Get fashion and textiles collection"""
        return self.search_objects("fashion", limit=limit)

    def get_ceramics_collection(self, limit: int = 50) -> List[Dict]:
        """Get ceramics collection"""
        return self.search_objects("ceramics", limit=limit)

    def get_sculpture_collection(self, limit: int = 50) -> List[Dict]:
        """Get sculpture collection"""
        return self.search_objects("sculpture", limit=limit)


# ============================================================================
# Art Database Clients
# ============================================================================

class WikiArtClient(BaseClient):
    """
    WikiArt API Client

    WikiArt is a visual art encyclopedia with artworks from 70,000+ artists.
    Limited public API, may require web scraping.

    Website: https://wikiart.org
    """

    BASE_URL = "https://wikiart.org"

    def get_artist_by_name(self, name: str) -> Optional[Dict]:
        """
        Get artist information by name

        Args:
            name: Artist name

        Returns:
            Artist information
        """
        # WikiArt doesn't have a fully public API
        # This is a placeholder for potential web scraping
        logger.warning(f"WikiArt API access is limited for artist: {name}")
        return None

    def get_random_artwork(self) -> Optional[Dict]:
        """Get a random artwork (requires scraping)"""
        logger.warning("WikiArt API access is limited - returning placeholder")
        return None


class GoogleArtsCultureClient(BaseClient):
    """
    Google Arts & Culture API Client

    Google Arts & Culture partners with museums worldwide to provide
    high-resolution images and virtual tours.

    Website: https://artsandculture.google.com
    """

    BASE_URL = "https://artsandculture.google.com"

    def get_artist_highlights(self, artist_name: str) -> List[Dict]:
        """
        Get highlighted artworks for an artist

        Args:
            artist_name: Artist name

        Returns:
            List of artwork information
        """
        # This is a placeholder - Google Arts & Culture doesn't have a public API
        logger.warning(f"Google Arts & Culture API access is limited for artist: {artist_name}")
        return []

    def get_museum_virtual_tours(self) -> List[str]:
        """Get available museum virtual tour URLs"""
        logger.warning("Google Arts & Culture API access is limited - returning placeholder")
        return []


# ============================================================================
# Music Database Clients
# ============================================================================

class MusicBrainzClient(BaseClient):
    """
    MusicBrainz API Client

    MusicBrainz is an open music encyclopedia that collects music metadata.
    No API key required (but rate limited).

    API Documentation: https://musicbrainz.org/doc/MusicBrainz_API
    """

    BASE_URL = "https://musicbrainz.org/ws/2"

    def __init__(self):
        super().__init__()
        self.session.headers.update({
            'User-Agent': 'ArtsBot/1.0 (https://github.com/your-repo)'
        })

    def search_artist(self, name: str, limit: int = 10) -> List[Dict]:
        """
        Search for artists

        Args:
            name: Artist name
            limit: Maximum results

        Returns:
            List of artist information
        """
        params = {
            "query": f"artist:{name}",
            "limit": limit,
            "fmt": "json"
        }

        try:
            data = self._get(f"{self.BASE_URL}/artist/", params=params)
            return data.get("artists", [])
        except Exception as e:
            logger.error(f"MusicBrainz search_artist error: {e}")
            return []

    def search_work(self, title: str, limit: int = 10) -> List[Dict]:
        """
        Search for musical works (compositions)

        Args:
            title: Work title
            limit: Maximum results

        Returns:
            List of work information
        """
        params = {
            "query": f"work:{title}",
            "limit": limit,
            "fmt": "json"
        }

        try:
            data = self._get(f"{self.BASE_URL}/work/", params=params)
            return data.get("works", [])
        except Exception as e:
            logger.error(f"MusicBrainz search_work error: {e}")
            return []

    def get_random_classical_composer(self) -> Optional[Dict]:
        """Get a random classical composer"""
        # List of famous classical composers
        composers = ["Johann Sebastian Bach", "Wolfgang Amadeus Mozart",
                     "Ludwig van Beethoven", "Frédéric Chopin", "Franz Schubert",
                     "Pyotr Ilyich Tchaikovsky", "Johannes Brahms", "Antonín Dvořák",
                     "Gustav Mahler", "Richard Wagner"]

        name = random.choice(composers)
        results = self.search_artist(name, limit=1)

        if results:
            return results[0]

        return {"name": name, "type": "classical composer"}

    def get_random_traditional_music(self) -> Optional[Dict]:
        """Get random traditional/folk music artist"""
        # List of traditional music traditions
        traditions = [
            {"name": "Indian classical music", "region": "India"},
            {"name": "Chinese traditional music", "region": "China"},
            {"name": "Japanese traditional music", "region": "Japan"},
            {"name": "African drumming traditions", "region": "Africa"},
            {"name": "Flamenco", "region": "Spain"},
            {"name": "Fado", "region": "Portugal"},
            {"name": "Tango", "region": "Argentina"},
            {"name": "Samba", "region": "Brazil"},
            {"name": "Gamelan", "region": "Indonesia"},
            {"name": "Celtic folk music", "region": "Ireland"}
        ]

        return random.choice(traditions)


class DiscogsClient(BaseClient):
    """
    Discogs API Client

    Discogs is a database of music information, including releases, artists, and labels.
    Requires API key (personal access token).

    API Documentation: https://www.discogs.com/developers/
    """

    BASE_URL = "https://api.discogs.com"

    def __init__(self, token: str):
        """
        Initialize Discogs client

        Args:
            token: Discogs personal access token
        """
        super().__init__()
        self.session.headers.update({
            'Authorization': f'Discogs token={token}'
        })

    def search_artist(self, name: str, limit: int = 10) -> List[Dict]:
        """
        Search for artists

        Args:
            name: Artist name
            limit: Maximum results

        Returns:
            List of artist information
        """
        params = {
            "q": name,
            "type": "artist",
            "per_page": limit
        }

        try:
            data = self._get(f"{self.BASE_URL}/database/search", params=params)
            return data.get("results", [])
        except Exception as e:
            logger.error(f"Discogs search_artist error: {e}")
            return []

    def get_random_album(self) -> Optional[Dict]:
        """Get a random album (placeholder)"""
        logger.warning("Discogs random album requires search first")
        return None


# ============================================================================
# Literature Database Clients
# ============================================================================

class OpenLibraryClient(BaseClient):
    """
    Open Library API Client

    Open Library is an open, editable library catalog with millions of book records.
    No API key required.

    API Documentation: https://openlibrary.org/developers/api
    """

    BASE_URL = "https://openlibrary.org"

    def search_books(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search for books

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of book information
        """
        params = {
            "q": query,
            "limit": limit
        }

        try:
            data = self._get(f"{self.BASE_URL}/search.json", params=params)
            return data.get("docs", [])
        except Exception as e:
            logger.error(f"OpenLibrary search error: {e}")
            return []

    def get_work_by_key(self, key: str) -> Optional[Dict]:
        """
        Get work details by Open Library key

        Args:
            key: Work key (e.g., OL123W)

        Returns:
            Work details including editions, descriptions, subjects
        """
        try:
            data = self._get(f"{self.BASE_URL}/works/{key}.json")
            return data
        except Exception as e:
            logger.error(f"OpenLibrary get_work error: {e}")
            return None

    def get_random_book(self, subject: Optional[str] = None) -> Optional[Dict]:
        """Get a random book, optionally by subject"""
        if subject:
            books = self.search_books(f"subject:{subject}", limit=50)
        else:
            books = self.search_books("", limit=50)

        if books:
            book = random.choice(books)
            # Get full details if we have a key
            key = book.get("key")
            if key:
                return self.get_work_by_key(key.split("/")[-1])
            return book

        return None

    def get_classic_literature(self, limit: int = 50) -> List[Dict]:
        """Get classic literature books"""
        classic_subjects = ["Classical literature", "Fiction classics",
                           "Literature", "Classic Fiction", "Canon"]

        books = []
        for subject in classic_subjects:
            results = self.search_books(f"subject:{subject}", limit=limit//len(classic_subjects))
            books.extend(results)

        return books[:limit]

    def get_non_western_literature(self, limit: int = 50) -> List[Dict]:
        """Get non-Western literature books"""
        subjects = ["African literature", "Asian literature",
                   "Japanese literature", "Chinese literature",
                   "Indian literature", "Arabic literature",
                   "Latin American literature"]

        books = []
        for subject in subjects:
            results = self.search_books(f"subject:{subject}", limit=limit//len(subjects))
            books.extend(results)

        return books[:limit]


class GoogleBooksClient(BaseClient):
    """
    Google Books API Client

    Google Books provides access to the world's most comprehensive index of books.
    Requires API key.

    API Documentation: https://developers.google.com/books
    """

    BASE_URL = "https://www.googleapis.com/books/v1/volumes"

    def __init__(self, api_key: str):
        """
        Initialize Google Books client

        Args:
            api_key: Google Books API key
        """
        super().__init__()
        self.api_key = api_key

    def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Override to include API key"""
        if params is None:
            params = {}
        params["key"] = self.api_key
        return super()._get(url, params)

    def search_books(self, query: str, limit: int = 40) -> List[Dict]:
        """
        Search for books

        Args:
            query: Search query
            limit: Maximum results (max 40 per request)

        Returns:
            List of volume information
        """
        params = {
            "q": query,
            "maxResults": limit,
            "printType": "books"
        }

        try:
            data = self._get(self.BASE_URL, params=params)
            return data.get("items", [])
        except Exception as e:
            logger.error(f"Google Books search error: {e}")
            return []

    def get_random_book(self, query: Optional[str] = None) -> Optional[Dict]:
        """Get a random book"""
        if query:
            books = self.search_books(query, limit=40)
        else:
            # Search for classic literature
            books = self.search_books("subject:classics", limit=40)

        if books:
            return random.choice(books)

        return None


# ============================================================================
# Film Database Clients
# ============================================================================

class TMDbClient(BaseClient):
    """
    The Movie Database (TMDb) API Client

    TMDb is a community built movie and TV database.
    Requires API key (free).

    API Documentation: https://developers.themoviedb.org/3
    """

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str):
        """
        Initialize TMDb client

        Args:
            api_key: TMDb API key (free at https://www.themoviedb.org/settings/api)
        """
        super().__init__()
        self.api_key = api_key

    def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Override to include API key"""
        if params is None:
            params = {}
        params["api_key"] = self.api_key
        return super()._get(url, params)

    def search_movies(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search for movies

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of movie information
        """
        params = {
            "query": query,
            "page": 1
        }

        try:
            data = self._get(f"{self.BASE_URL}/search/movie", params=params)
            return data.get("results", [])[:limit]
        except Exception as e:
            logger.error(f"TMDb search_movies error: {e}")
            return []

    def get_movie(self, movie_id: int) -> Optional[Dict]:
        """
        Get movie details

        Args:
            movie_id: TMDb movie ID

        Returns:
            Movie details including overview, credits, similar movies
        """
        try:
            data = self._get(f"{self.BASE_URL}/movie/{movie_id}")
            return data
        except Exception as e:
            logger.error(f"TMDb get_movie error: {e}")
            return None

    def get_random_movie(self, genre: Optional[str] = None) -> Optional[Dict]:
        """Get a random movie, optionally by genre"""
        # This would require genre discovery first
        # For now, do a general search
        searches = ["classic cinema", "art film", "foreign film", "indie film"]
        query = random.choice(searches)

        movies = self.search_movies(query, limit=20)
        if movies:
            movie = random.choice(movies)
            # Get full details
            movie_id = movie.get("id")
            if movie_id:
                return self.get_movie(movie_id)
            return movie

        return None

    def get_world_cinema(self, limit: int = 50) -> List[Dict]:
        """Get international/non-English films"""
        # Search for films from different regions
        regions = ["French cinema", "Japanese cinema", "Italian cinema",
                  "Indian cinema", "Chinese cinema", "Korean cinema",
                  "African cinema", "Latin American cinema"]

        movies = []
        for region in regions:
            results = self.search_movies(region, limit=limit//len(regions))
            movies.extend(results)

        return movies[:limit]


class OMDbClient(BaseClient):
    """
    OMDb API Client

    The Open Movie Database is a RESTful web service to obtain movie information.
    Requires API key (free tier available).

    API Documentation: http://www.omdbapi.com/
    """

    BASE_URL = "http://www.omdbapi.com"

    def __init__(self, api_key: str):
        """
        Initialize OMDb client

        Args:
            api_key: OMDb API key (free at http://www.omdbapi.com/apikey.aspx)
        """
        super().__init__()
        self.api_key = api_key

    def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Override to include API key"""
        if params is None:
            params = {}
        params["apikey"] = self.api_key
        return super()._get(url, params)

    def search_movies(self, query: str) -> List[Dict]:
        """
        Search for movies

        Args:
            query: Search query (movie title)

        Returns:
            List of movie information
        """
        params = {
            "s": query,
            "type": "movie"
        }

        try:
            data = self._get(self.BASE_URL, params=params)
            return data.get("Search", [])
        except Exception as e:
            logger.error(f"OMDb search error: {e}")
            return []

    def get_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """
        Get detailed movie information

        Args:
            title: Movie title
            year: Optional release year

        Returns:
            Detailed movie information
        """
        params = {
            "t": title,
            "plot": "full"
        }

        if year:
            params["y"] = year

        try:
            data = self._get(self.BASE_URL, params=params)
            if data.get("Response") == "True":
                return data
        except Exception as e:
            logger.error(f"OMDb get_movie error: {e}")

        return None


# ============================================================================
# Architecture/Heritage Clients
# ============================================================================

class UNESCOHeritageClient(BaseClient):
    """
    UNESCO World Heritage Centre API Client

    UNESCO provides data on World Heritage Sites around the world.
    No API key required (uses open data).

    API Documentation: https://whc.unesco.org/en/help/
    """

    BASE_URL = "https://whc.unesco.org"

    def get_heritage_sites(self, region: Optional[str] = None,
                          limit: int = 50) -> List[Dict]:
        """
        Get World Heritage Sites

        Args:
            region: Optional region filter
            limit: Maximum results

        Returns:
            List of heritage site information
        """
        # UNESCO doesn't have a proper API, but provides data feeds
        # This is a placeholder - would need web scraping or CSV import
        logger.warning("UNESCO Heritage requires CSV import or web scraping")
        return []

    def get_random_heritage_site(self) -> Optional[Dict]:
        """Get a random World Heritage Site"""
        logger.warning("UNESCO Heritage site data requires special handling")
        return None


class ArchDailyClient(BaseClient):
    """
    ArchDaily API Client

    ArchDaily is the world's most visited architecture website.
    No public API available - requires web scraping.

    Website: https://www.archdaily.com
    """

    BASE_URL = "https://www.archdaily.com"

    def get_random_project(self) -> Optional[Dict]:
        """Get a random architectural project"""
        # This would require web scraping
        logger.warning("ArchDaily requires web scraping - returning placeholder")
        return None


# ============================================================================
# Utility Functions
# ============================================================================

def get_cultural_client(client_type: str, **kwargs) -> Optional[BaseClient]:
    """
    Factory function to get appropriate cultural arts client

    Args:
        client_type: Type of client (met, moma, rijks, etc.)
        **kwargs: Additional arguments (api_key, etc.)

    Returns:
        Client instance or None

    Examples:
        met = get_cultural_client("met")
        moma = get_cultural_client("moma", api_key="your_key")
        rijks = get_cultural_client("rijks", api_key="your_key")
    """
    clients = {
        # Museums
        'met': MetMuseumClient,
        'moma': MoMAClient,
        'rijks': RijksmuseumClient,
        'british': BritishMuseumClient,
        'smithsonian': SmithsonianClient,
        'va': VAClient,
        # Art databases
        'wikiart': WikiArtClient,
        'google_arts': GoogleArtsCultureClient,
        # Music
        'musicbrainz': MusicBrainzClient,
        'discogs': DiscogsClient,
        # Literature
        'openlibrary': OpenLibraryClient,
        'google_books': GoogleBooksClient,
        # Film
        'tmdb': TMDbClient,
        'omdb': OMDbClient,
        # Architecture/Heritage
        'unesco': UNESCOHeritageClient,
        'archdaily': ArchDailyClient,
    }

    client_class = clients.get(client_type.lower())
    if client_class:
        try:
            return client_class(**kwargs)
        except TypeError as e:
            logger.error(f"Error creating {client_type} client: {e}")
            return None

    logger.warning(f"Unknown client type: {client_type}")
    return None


# ============================================================================
# CLI Interface
# ============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 70)
    print("CULTURAL ARTS API CLIENTS - TEST")
    print("=" * 70)

    # Test Met Museum (no API key required)
    print("\n[Testing Met Museum Client]")
    met = MetMuseumClient()

    # Get departments
    depts = met.get_departments()
    print(f"Departments: {len(depts)}")
    if depts:
        print(f"  First 3 departments: {[d['displayName'] for d in depts[:3]]}")

    # Get random object
    obj = met.get_random_object()
    if obj:
        print(f"\nRandom object: {obj.get('title')}")

    # Test MusicBrainz (no API key required)
    print("\n[Testing MusicBrainz Client]")
    mb = MusicBrainzClient()

    results = mb.search_artist("Mozart", limit=3)
    print(f"Mozart results: {len(results)}")
    if results:
        print(f"  First result: {results[0].get('name', 'N/A')}")

    # Test Open Library (no API key required)
    print("\n[Testing OpenLibrary Client]")
    ol = OpenLibraryClient()

    books = ol.search_books("Pride and Prejudice", limit=3)
    print(f"Books found: {len(books)}")
    if books:
        print(f"  First book: {books[0].get('title', 'N/A')}")

    print("\n" + "=" * 70)
    print("For API-key-required clients (MoMA, Rijksmuseum, TMDb, etc.),")
    print("set your API key in environment variables or pass it directly:")
    print("  moma = MoMAClient(api_key='your_key')")
    print("=" * 70)
