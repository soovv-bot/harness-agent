#!/usr/bin/env python3
"""
Expanded Academia and Scholarly Communication Data Pools

This module provides expanded, diverse pools for academia and scholarly communication
data generation, covering various academic disciplines, roles, institutions, and concepts.

Coverage:
- All academic disciplines and fields
- Academic roles and ranks
- Institution types (universities, research institutes, etc.)
- Publication venues (journals, conferences, etc.)
- Research concepts and methodologies
- Academic metrics and terminology
- Notable scholars and academics
- Wikipedia categories for academia
"""

from typing import List, Dict
import random


# ============================================================================
# EXPANDED ACADEMIA POOLS
# ============================================================================

class ExpandedAcademiaPools:
    """
    大规模学术界数据池 - 覆盖全球学术界
    Designed to be comprehensive and diverse
    """

    # ========== ACADEMIC DISCIPLINES ==========

    ACADEMIC_DISCIPLINES = {
        "natural_sciences": [
            # Physics
            "Atomic and Molecular Physics", "Condensed Matter Physics", "Particle Physics",
            "Astrophysics", "Biophysics", "Chemical Physics", "Geophysics",
            "Optical Physics", "Plasma Physics", "Quantum Physics", "Statistical Mechanics",
            "Theoretical Physics", "Computational Physics", "Medical Physics",

            # Chemistry
            "Analytical Chemistry", "Biochemistry", "Chemical Biology", "Chemical Physics",
            "Inorganic Chemistry", "Materials Chemistry", "Medicinal Chemistry",
            "Organic Chemistry", "Physical Chemistry", "Polymer Chemistry",
            "Theoretical Chemistry", "Environmental Chemistry", "Green Chemistry",

            # Earth Sciences
            "Atmospheric Science", "Climatology", "Geochemistry", "Geology",
            "Geophysics", "Hydrology", "Meteorology", "Mineralogy", "Oceanography",
            "Paleoclimatology", "Paleontology", "Petrology", "Seismology",
            "Stratigraphy", "Volcanology",

            # Astronomy
            "Astronomy", "Astrophysics", "Cosmology", "Exoplanet Science",
            "Planetary Science", "Radio Astronomy", "Solar Physics", "Stellar Astronomy"
        ],
        "life_sciences": [
            # Biology subfields
            "Biochemistry", "Biophysics", "Botany", "Cell Biology", "Developmental Biology",
            "Ecology", "Evolutionary Biology", "Genetics", "Immunology", "Marine Biology",
            "Microbiology", "Molecular Biology", "Neuroscience", "Physiology",
            "Structural Biology", "Systems Biology", "Zoology",

            # Medical Sciences
            "Anatomy", "Anesthesiology", "Bioengineering", "Biomedical Research",
            "Cardiology", "Dermatology", "Emergency Medicine", "Endocrinology",
            "Epidemiology", "Family Medicine", "Gastroenterology", "General Surgery",
            "Geriatrics", "Hematology", "Immunology", "Infectious Disease",
            "Internal Medicine", "Medical Genetics", "Nephrology", "Neurology",
            "Neurosurgery", "Oncology", "Ophthalmology", "Orthopedics",
            "Otolaryngology", "Pathology", "Pediatrics", "Pharmacology",
            "Physical Medicine", "Psychiatry", "Public Health", "Pulmonology",
            "Radiology", "Rheumatology", "Surgery", "Urology",

            # Agriculture
            "Agricultural Science", "Agroforestry", "Animal Science", "Aquaculture",
            "Crop Science", "Dairy Science", "Fisheries", "Food Science",
            "Forestry", "Horticulture", "Plant Breeding", "Plant Pathology",
            "Plant Science", "Soil Science", "Veterinary Medicine"
        ],
        "formal_sciences": [
            # Mathematics
            "Algebra", "Analysis", "Applied Mathematics", "Combinatorics",
            "Computational Mathematics", "Differential Equations", "Dynamical Systems",
            "Geometry", "Logic", "Mathematical Physics", "Number Theory",
            "Numerical Analysis", "Optimization", "Probability Theory", "Statistics",
            "Topology",

            # Computer Science
            "Algorithms and Data Structures", "Artificial Intelligence",
            "Computer Graphics", "Computer Networks", "Computer Security",
            "Computer Vision", "Databases", "Distributed Systems",
            "Formal Methods", "Game Development", "Human-Computer Interaction",
            "Machine Learning", "Natural Language Processing", "Operating Systems",
            "Programming Languages", "Robotics", "Software Engineering",
            "Theory of Computation",

            # Statistics
            "Bayesian Statistics", "Biostatistics", "Data Science", "Econometrics",
            "Mathematical Statistics", "Psychometrics", "Social Statistics",
            "Statistical Computing", "Statistical Genetics", "Survey Methodology",

            # Logic
            "Computational Logic", "Mathematical Logic", "Modal Logic",
            "Philosophical Logic", "Proof Theory", "Set Theory"
        ],
        "engineering_and_technology": [
            # Engineering
            "Aerospace Engineering", "Agricultural Engineering", "Architectural Engineering",
            "Automotive Engineering", "Bioengineering", "Biomedical Engineering",
            "Chemical Engineering", "Civil Engineering", "Computer Engineering",
            "Construction Engineering", "Control Systems", "Electrical Engineering",
            "Electronic Engineering", "Environmental Engineering", "Industrial Engineering",
            "Manufacturing Engineering", "Materials Engineering", "Mechanical Engineering",
            "Mechatronics", "Mining Engineering", "Nanotechnology", "Naval Architecture",
            "Nuclear Engineering", "Petroleum Engineering", "Robotics", "Software Engineering",
            "Structural Engineering", "Systems Engineering", "Telecommunications",

            # Technology
            "Cloud Computing", "Computer Networking", "Cryptography",
            "Data Science", "Information Systems", "Internet of Things",
            "Network Security", "Software Development", "Web Development"
        ],
        "medical_and_health_sciences": [
            "Anatomy", "Anesthesiology", "Biochemistry", "Biophysics",
            "Biotechnology", "Cardiology", "Cardiovascular Surgery", "Cell Biology",
            "Clinical Biochemistry", "Clinical Medicine", "Dentistry", "Dermatology",
            "Emergency Medicine", "Endocrinology", "Epidemiology", "Family Medicine",
            "Gastroenterology", "Genetics", "Geriatrics", "Health Informatics",
            "Health Sciences", "Hematology", "Immunology", "Infectious Diseases",
            "Internal Medicine", "Medical Biophysics", "Medical Biotechnology",
            "Medical Chemistry", "Medical Genetics", "Medical Microbiology",
            "Medical Physics", "Molecular Biology", "Molecular Medicine",
            "Nanomedicine", "Nephrology", "Neurobiology", "Neurology",
            "Neuroscience", "Nursing", "Nutritional Sciences", "Obstetrics and Gynecology",
            "Oncology", "Ophthalmology", "Optometry", "Oral Biology",
            "Oral Medicine", "Orthopedics", "Otolaryngology", "Pathology",
            "Pediatrics", "Pharmacology", "Pharmacy", "Physical Therapy",
            "Physiology", "Preventive Medicine", "Primary Care", "Psychiatry",
            "Psychology", "Public Health", "Pulmonology", "Radiology",
            "Rehabilitation Medicine", "Rheumatology", "Sports Medicine", "Surgery",
            "Translational Medicine", "Tropical Medicine", "Urology", "Virology"
        ],
        "agricultural_sciences": [
            "Agricultural Botany", "Agricultural Chemistry", "Agricultural Engineering",
            "Agricultural Microbiology", "Agricultural Physics", "Agronomy",
            "Animal Breeding", "Animal Genetics", "Animal Husbandry", "Animal Nutrition",
            "Aquaculture", "Dairy Science", "Fisheries", "Food Technology",
            "Forestry", "Horticulture", "Pasture Science", "Plant Breeding",
            "Plant Pathology", "Plant Protection", "Poultry Science", "Rural Sociology",
            "Soil Science", "Veterinary Medicine", "Wildlife Management"
        ],
        "social_sciences": [
            # Core social sciences
            "Anthropology", "Archaeology", "Criminology", "Demography",
            "Economics", "Geography", "Human Geography", "Political Science",
            "Psychology", "Social Psychology", "Sociology",

            # Applied social sciences
            "African Studies", "American Studies", "Asian Studies", "Communication Studies",
            "Cultural Studies", "Development Studies", "Education", "Environmental Studies",
            "European Studies", "Gender Studies", "International Relations", "Law",
            "Library Science", "Management", "Media Studies", "Middle Eastern Studies",
            "Peace and Conflict Studies", "Public Administration", "Public Policy",
            "Regional Studies", "Social Policy", "Social Work", "Urban Studies",
            "Women's Studies"
        ],
        "humanities": [
            # Core humanities
            "Classics", "History", "Philosophy", "Religious Studies", "Theology",

            # Arts
            "Art History", "Creative Writing", "Dance", "Design", "Drama",
            "Film Studies", "Fine Arts", "Literary Studies", "Literature",
            "Music", "Musicology", "Performance Studies", "Studio Art",
            "Theater", "Visual Arts",

            # Specific fields
            "Aesthetics", "American Literature", "Ancient History", "Biblical Studies",
            "Comparative Literature", "Continental Philosophy", "Early Modern History",
            "English Literature", "Ethics", "Folklore", "Intellectual History",
            "Medieval History", "Modern History", "Modern Languages", "Musicology",
            "Philosophy of Language", "Philosophy of Mind", "Philosophy of Science",
            "Religious Education", "Rhetoric"
        ],
        "interdisciplinary": [
            "African American Studies", "American Studies", "Area Studies",
            "Asian Studies", "Bioethics", "Biomathematics", "Biophysics",
            "Cognitive Science", "Communication", "Complex Systems",
            "Cultural Studies", "Development Studies", "Disability Studies",
            "Environmental Science", "Environmental Studies", "Ethnic Studies",
            "Gender and Sexuality", "Gender Studies", "Global Studies",
            "Health Policy", "History and Philosophy of Science", "Holistic Health",
            "Human Ecology", "Human-Computer Interaction", "Immigration Studies",
            "Indigenous Studies", "Information Science", "International Studies",
            "Latin American Studies", "Law and Society", "Lesbian, Gay, Bisexual, and Transgender Studies",
            "Life Sciences", "Marine Science", "Medieval and Renaissance Studies",
            "Middle Eastern Studies", "Molecular Biosciences", "Native American Studies",
            "Neuroscience", "Peace Studies", "Philosophy of Science",
            "Religious Studies", "Science and Technology Studies", "Slavic Studies",
            "Social Justice", "Sustainability", "Sustainability Studies",
            "Urban Studies", "Western Hemisphere Studies", "Women's Studies"
        ]
    }

    # ========== ACADEMIC ROLES AND RANKS ==========

    ACADEMIC_ROLES = {
        "faculty_ranks": [
            # Entry level
            "Adjunct Professor", "Assistant Professor", "Associate Professor",
            "Full Professor", "Emeritus Professor", "Visiting Professor",

            # Special positions
            "Distinguished Professor", "Endowed Chair", "Honorary Professor",
            "Named Chair", "Regents Professor", "University Professor",

            # Temporary/contract
            "Adjunct Faculty", "Contract Faculty", "Instructor", "Lecturer",
            "Postdoctoral Researcher", "Research Associate", "Teaching Assistant"
        ],
        "research_positions": [
            "Principal Investigator", "Co-Investigator", "Research Scientist",
            "Senior Researcher", "Research Fellow", "Postdoctoral Fellow",
            "Research Assistant", "Graduate Research Assistant", "Lab Director",
            "Group Leader", "Team Leader"
        ],
        "administration": [
            "Department Chair", "Department Head", "Program Director",
            "Associate Dean", "Dean", "Vice President", "Provost",
            "Chancellor", "President", "Rector", "Vice-Chancellor"
        ],
        "support_staff": [
            "Academic Advisor", "Career Counselor", "Instructional Designer",
            "Learning Specialist", "Librarian", "Research Administrator",
            "Research Librarian", "Student Affairs", "Writing Center Director"
        ]
    }

    # ========== INSTITUTION TYPES ==========

    INSTITUTION_TYPES = {
        "universities": [
            "Research University", "Public University", "Private University",
            "State University", "Liberal Arts College", "Technical University",
            "Institute of Technology", "Polytechnic University", "University College",
            "Community College", "Junior College", "College"
        ],
        "research_institutes": [
            "National Laboratory", "Research Institute", "Think Tank",
            "Independent Research Organization", "Government Research Lab",
            "Private Research Institute", "Nonprofit Research Center"
        ],
        "medical_institutions": [
            "Medical School", "Teaching Hospital", "University Hospital",
            "Academic Medical Center", "Research Hospital", "Medical Institute",
            "Health Science Center", "School of Medicine"
        ],
        "specialized": [
            "Art School", "Business School", "Conservatory", "Design School",
            "Engineering School", "Law School", "Medical Center",
            "Music School", "Seminary", "Theological School"
        ]
    }

    # ========== PUBLICATION VENUES ==========

    PUBLICATION_VENUES = {
        "journals": [
            # Journal types
            "Academic Journal", "Scholarly Journal", "Peer-Reviewed Journal",
            "Open Access Journal", "Electronic Journal", "International Journal",

            # Impact levels
            "High Impact Journal", "Premier Journal", "Flagship Journal",
            "Specialized Journal", "Interdisciplinary Journal", "Review Journal",
            "Rapid Publication Journal", "Letters Journal"
        ],
        "conferences": [
            # Conference types
            "Academic Conference", "International Conference", "Symposium",
            "Workshop", "Seminar", "Colloquium", "Congress",

            # By discipline
            "Computer Science Conference", "Medical Conference", "Science Conference",
            "Engineering Conference", "Humanities Conference"
        ],
        "other": [
            "Book", "Monograph", "Edited Volume", "Textbook", "Handbook",
            "Dissertation", "Thesis", "Technical Report", "Working Paper",
            "Preprint Server", "arXiv", "bioRxiv", "SSRN", "RePEc"
        ]
    }

    # ========== RESEARCH CONCEPTS ==========

    RESEARCH_CONCEPTS = {
        "methodology": [
            "Quantitative Research", "Qualitative Research", "Mixed Methods",
            "Experimental Design", "Quasi-Experimental Design", "Longitudinal Study",
            "Cross-Sectional Study", "Case Study", "Meta-Analysis", "Systematic Review",
            "Literature Review", "Survey Research", "Observational Study",
            "Action Research", "Participatory Research", "Grounded Theory",
            "Ethnography", "Phenomenology", "Content Analysis", "Discourse Analysis"
        ],
        "statistical": [
            "Statistical Significance", "Effect Size", "Power Analysis",
            "Confidence Interval", "P-value", "Null Hypothesis", "Alternative Hypothesis",
            "Regression Analysis", "ANOVA", "Chi-Square Test", "t-Test",
            "Correlation", "Factor Analysis", "Cluster Analysis", "Multivariate Analysis",
            "Bayesian Statistics", "Maximum Likelihood", "Structural Equation Modeling"
        ],
        "academic_writing": [
            "Abstract", "Introduction", "Literature Review", "Methodology",
            "Results", "Discussion", "Conclusion", "References", "Citation",
            "Bibliography", "Footnote", "Endnote", "Appendix", "Supplementary Material"
        ],
        "publishing": [
            "Peer Review", "Double-Blind Review", "Open Review", "Editorial Review",
            "Acceptance Rate", "Impact Factor", "H-Index", "Citation Count",
            "Journal Metrics", "Altmetrics", "Citation Index", "Indexing",
            "DOI", "ORCID", "PubMed ID", "arXiv ID", "Submission",
            "Revision", "Resubmission", "Rejection", "Acceptance"
        ]
    }

    # ========== ACADEMIC TOPICS BY FIELD ==========

    ACADEMIC_TOPICS = {
        "computer_science": [
            "Artificial Intelligence", "Machine Learning", "Deep Learning",
            "Computer Vision", "Natural Language Processing", "Robotics",
            "Algorithms", "Data Structures", "Complexity Theory",
            "Distributed Systems", "Cloud Computing", "Cybersecurity",
            "Software Engineering", "Programming Languages", "Computer Graphics",
            "Human-Computer Interaction", "Information Retrieval", "Databases",
            "Neural Networks", "Reinforcement Learning", "Transfer Learning"
        ],
        "medicine": [
            "Cancer Research", "Cardiovascular Disease", "Infectious Diseases",
            "Neurological Disorders", "Autoimmune Diseases", "Genetic Disorders",
            "Drug Discovery", "Clinical Trials", "Precision Medicine",
            "Personalized Medicine", "Immunotherapy", "Gene Therapy",
            "Stem Cell Research", "Regenerative Medicine", "Medical Imaging",
            "Epidemiology", "Public Health", "Health Policy"
        ],
        "economics": [
            "Microeconomics", "Macroeconomics", "Econometrics", "Game Theory",
            "Development Economics", "International Economics", "Labor Economics",
            "Monetary Economics", "Public Economics", "Financial Economics",
            "Behavioral Economics", "Experimental Economics", "Environmental Economics",
            "Health Economics", "Education Economics", "Industrial Organization"
        ],
        "physics": [
            "Quantum Computing", "Quantum Information", "Condensed Matter Physics",
            "High Energy Physics", "Particle Physics", "Astrophysics",
            "Cosmology", "Plasma Physics", "Biophysics", "Geophysics",
            "Materials Science", "Nanotechnology", "Photonics", "Optics"
        ],
        "psychology": [
            "Cognitive Psychology", "Developmental Psychology", "Social Psychology",
            "Clinical Psychology", "Counseling Psychology", "Educational Psychology",
            "Organizational Psychology", "Neuropsychology", "Health Psychology",
            "Forensic Psychology", "Sports Psychology", "Environmental Psychology"
        ]
    }

    # ========== FAMOUS ACADEMICS AND SCHOLARS ==========

    FAMOUS_ACADEMICS = {
        "scientists": [
            # Physics
            "Albert Einstein", "Isaac Newton", "Marie Curie", "Richard Feynman",
            "Stephen Hawking", "Niels Bohr", "Erwin Schrödinger", "Werner Heisenberg",
            "Enrico Fermi", "Paul Dirac", "Max Planck", "Michael Faraday",
            "James Clerk Maxwell", "Galileo Galilei", "Leonardo da Vinci",

            # Chemistry
            "Dmitri Mendeleev", "Linus Pauling", "Robert Boyle", "John Dalton",
            "Louis Pasteur", "Florence Nightingale",

            # Biology
            "Charles Darwin", "Gregor Mendel", "James Watson", "Francis Crick",
            "Rosalind Franklin", "Louis Pasteur", "Alexander Fleming",
            "Jane Goodall", "Rachel Carson", "Edward O. Wilson",

            # Computer Science
            "Alan Turing", "John von Neumann", "Claude Shannon", "Donald Knuth",
            "Tim Berners-Lee", "Vint Cerf", "Grace Hopper", "Ada Lovelace",

            # Mathematics
            "Carl Friedrich Gauss", "Leonhard Euler", "Bernhard Riemann",
            "David Hilbert", "Henri Poincaré", "John von Neumann", "Alan Turing",
            "Srinivasa Ramanujan", "Andrew Wiles", "Grigori Perelman"
        ],
        "social_scientists": [
            # Psychology
            "Sigmund Freud", "Carl Jung", "B.F. Skinner", "Jean Piaget",
            "Daniel Kahneman", "Amos Tversky", "Elizabeth Loftus",

            # Economics
            "Adam Smith", "John Maynard Keynes", "Milton Friedman", "Paul Samuelson",
            "Gary Becker", "Elinor Ostrom", "Daniel Kahneman", "Amartya Sen",

            # Sociology
            "Émile Durkheim", "Max Weber", "Karl Marx", "Pierre Bourdieu",
            "Anthony Giddens", "Judith Butler",

            # Anthropology
            "Franz Boas", "Margaret Mead", "Claude Lévi-Strauss", "Clifford Geertz"
        ],
        "humanities_scholars": [
            # Philosophy
            "Plato", "Aristotle", "Immanuel Kant", "Friedrich Nietzsche",
            "John Rawls", "Judith Butler", "Slavoj Žižek", "Martha Nussbaum",

            # Literature
            "Harold Bloom", "Edward Said", "Gayatri Spivak", "Homi Bhabha",
            "Northrop Frye", "Mikhail Bakhtin", "Roland Barthes",

            # History
            "Arnold Toynbee", "Fernand Braudel", "Leopold von Ranke",
            "E.H. Carr", "Eric Hobsbawm"
        ],
        "nobel_laureates": [
            # Physics
            "Albert Einstein", "Niels Bohr", "Richard Feynman", "Marie Curie",
            "Werner Heisenberg", "Paul Dirac", "Erwin Schrödinger", "Enrico Fermi",

            # Chemistry
            "Linus Pauling", "Dorothy Hodgkin", "Robert Burns Woodward",
            "Ahmed Zewail", "Frances Arnold", "Jennifer Doudna", "Emmanuelle Charpentier",

            # Physiology/Medicine
            "Alexander Fleming", "Frederick Banting", "John Macleod", "Corneille Heymans",
            "Gerty Cori", "Carl Cori", "Hermann Muller", "Joshua Lederberg",
            "Edward Kendall", "Philip Hench", "Selman Waksman",

            # Economics
            "Paul Samuelson", "Kenneth Arrow", "Milton Friedman", "Gunnar Myrdal",
            "Friedrich Hayek", "Herbert Simon", "James Buchanan", "Maurice Allais",
            "Trygve Haavelmo", "Jan Tinbergen", "Daniel Kahneman", "Vernon Smith",
            "Amartya Sen", "Robert Aumann", "Thomas Schelling", "Eric Maskin",
            "Leonid Hurwicz", "Paul Krugman", "Oliver Williamson", "Elinor Ostrom",
            "Peter Diamond", "Thomas Sargent", "Christopher Sims", "Alvin Roth",
            "Lloyd Shapley", "Eugene Fama", "Lars Hansen", "Robert Shiller",
            "Jean Tirole", "Angus Deaton", "Bengt Holmström", "Oliver Hart",
            "Richard Thaler", "Paul Romer", "William Nordhaus", "Esther Duflo",
            "Abhijit Banerjee", "Michael Kremer", "Paul Milgrom", "Robert Wilson",

            # Literature
            "Rudyard Kipling", "William Butler Yeats", "George Bernard Shaw",
            "Thomas Mann", "Ernest Hemingway", "John Steinbeck", "Toni Morrison",
            "Gabriel Garcia Marquez", "Samuel Beckett", "Harold Pinter",
            "Alice Munro", "Bob Dylan", "Kazuo Ishiguro", "Olga Tokarczuk",

            # Peace
            "Martin Luther King Jr.", "Nelson Mandela", "Mother Teresa",
            "Malala Yousafzai", "Barack Obama", "Al Gore", "Jimmy Carter",
            "Henry Kissinger", "Linus Pauling", "Albert Schweitzer"
        ]
    }

    # ========== WIKIPEDIA ACADEMIA CATEGORIES ==========

    WIKIPEDIA_CATEGORIES = [
        # Main categories
        "Category:Academia",
        "Category:Academic disciplines",
        "Category:Scholarly communication",
        "Category:Research",
        "Category:Academic publishing",

        # By discipline
        "Category:Academic disciplines by field",
        "Category:Natural sciences",
        "Category:Formal sciences",
        "Category:Social sciences",
        "Category:Humanities",
        "Category:Applied sciences",

        # Academic roles
        "Category:Academic administrators",
        "Category:Professors",
        "Category:Academic ranks",
        "Category:Researchers",
        "Category:Scholars",
        "Category:Scientists",
        "Category:Mathematicians",
        "Category:Engineers",

        # Publishing
        "Category:Academic journals",
        "Category:Open access journals",
        "Category:Scientific journals",
        "Category:Peer review",
        "Category:Academic conferences",
        "Category:Scientific conferences",

        # Institutions
        "Category:Universities and colleges",
        "Category:Research institutes",
        "Category:Academic libraries",
        "Category:University research",
        "Category:Academic organizations",

        # By region
        "Category:Universities and colleges by country",
        "Category:Research institutes by country",

        # Degrees
        "Category:Doctoral degrees",
        "Category:Master's degrees",
        "Category:Bachelor's degrees",
        "Category:Academic degrees",

        # Concepts
        "Category:Citation analysis",
        "Category:Bibliometrics",
        "Category:Scientific method",
        "Category:Research methods",
        "Category:Academic terminology",

        # Academic output
        "Category:Academic works",
        "Category:Theses and dissertations",
        "Category:Preprints",
        "Category:Technical reports",

        # Metrics
        "Category:Bibliometric indicators",
        "Category:Library science",
        "Category:Scholarly communication"
    ]

    # ========== SEARCH KEYWORD COMPONENTS ==========

    KEYWORD_COMPONENTS = {
        "disciplines": [
            "computer science", "machine learning", "artificial intelligence",
            "physics", "chemistry", "biology", "mathematics", "statistics",
            "economics", "psychology", "sociology", "political science",
            "history", "philosophy", "literature", "engineering", "medicine"
        ],
        "topics": [
            "research", "publication", "journal", "conference", "paper",
            "thesis", "dissertation", "citation", "impact factor", "peer review",
            "academic career", "professor", "research grant", "funding",
            "university", "institute", "lab", "collaboration"
        ],
        "modifiers": [
            "interdisciplinary", "multidisciplinary", "cross-disciplinary",
            "international", "global", "comparative", "theoretical", "experimental",
            "applied", "empirical", "quantitative", "qualitative", "mixed methods"
        ],
        "metrics": [
            "h-index", "impact factor", "citation count", "altmetric",
            "g-index", "i10-index", "h-index", "m-index", "eigenfactor",
            "sJR", "SNIP", "CiteScore", "JCR quartile"
        ]
    }

    # ========== HELPER METHODS ==========

    def get_all_disciplines(self) -> List[str]:
        """Get all academic disciplines as flat list"""
        all_disciplines = []
        for discipline_list in self.ACADEMIC_DISCIPLINES.values():
            all_disciplines.extend(discipline_list)
        return all_disciplines

    def get_all_roles(self) -> List[str]:
        """Get all academic roles as flat list"""
        all_roles = []
        for role_list in self.ACADEMIC_ROLES.values():
            all_roles.extend(role_list)
        return all_roles

    def get_all_institution_types(self) -> List[str]:
        """Get all institution types as flat list"""
        all_types = []
        for type_list in self.INSTITUTION_TYPES.values():
            all_types.extend(type_list)
        return all_types

    def get_all_categories(self) -> List[str]:
        """Get all Wikipedia categories"""
        return self.WIKIPEDIA_CATEGORIES

    def get_random_scholar(self) -> str:
        """Get random famous scholar"""
        all_scholars = []
        for scholar_list in self.FAMOUS_ACADEMICS.values():
            all_scholars.extend(scholar_list)
        return random.choice(all_scholars)

    def generate_search_queries(self, num_queries: int = 50) -> List[str]:
        """Generate diverse academia search queries"""
        queries = []

        for _ in range(num_queries):
            pattern = random.choice([
                # Discipline + topic
                lambda: f"{random.choice(self.get_all_disciplines())} {random.choice(self.KEYWORD_COMPONENTS['topics'])}",
                # Scholar + topic
                lambda: f"{self.get_random_scholar()} {random.choice(self.KEYWORD_COMPONENTS['topics'])}",
                # Institution + discipline
                lambda: f"{random.choice(self.get_all_institution_types())} {random.choice(self.get_all_disciplines())}",
                # Topic + modifier
                lambda: f"{random.choice(self.KEYWORD_COMPONENTS['modifiers'])} {random.choice(self.KEYWORD_COMPONENTS['topics'])}",
                # Discipline metrics
                lambda: f"{random.choice(self.get_all_disciplines())} {random.choice(self.KEYWORD_COMPONENTS['metrics'])}",
                # Research topic
                lambda: f"{random.choice(self.get_all_disciplines())} research methods",
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
    pools = ExpandedAcademiaPools()

    print("=" * 70)
    print("EXPANDED ACADEMIA POOLS")
    print("=" * 70)

    print(f"\nTotal Disciplines: {len(pools.get_all_disciplines())}")
    print(f"Total Roles: {len(pools.get_all_roles())}")
    print(f"Total Institution Types: {len(pools.get_all_institution_types())}")
    print(f"Total Categories: {len(pools.get_all_categories())}")

    print("\n" + "=" * 70)
    print("DISCIPLINE BREAKDOWN")
    print("=" * 70)

    for category, disciplines in pools.ACADEMIC_DISCIPLINES.items():
        print(f"\n{category}: {len(disciplines)} items")
        samples = random.sample(disciplines, min(3, len(disciplines)))
        for s in samples:
            print(f"  - {s}")

    print("\n" + "=" * 70)
    print("SAMPLE SEARCH QUERIES")
    print("=" * 70)

    queries = pools.generate_search_queries(10)
    for q in queries:
        print(f"  - {q}")
