#!/usr/bin/env python3
"""
Expanded Science and Engineering Data Pools

This module provides expanded, diverse pools for science and engineering data generation,
with detailed categorization of scientific disciplines, concepts, and entities.

Coverage:
- All major scientific disciplines with detailed sub-disciplines
- Medical and health sciences (comprehensive)
- Life sciences with all branches
- Physical sciences with all branches
- Earth and environmental sciences
- Formal sciences
- Engineering and applied sciences
- Agricultural and food sciences
- Psychological sciences
- Scientific entities, concepts, and institutions
"""

from typing import List, Dict
import random


# ============================================================================
# EXPANDED SCIENCE POOLS
# ============================================================================

class ExpandedSciencePools:
    """
    大规模科学数据池 - 全面覆盖所有科学学科
    Designed to be comprehensive and diverse like business/biography domains
    """

    # ========== PHYSICAL SCIENCES ==========

    PHYSICAL_SCIENCES = {
        "physics": [
            # Classical physics
            "Classical mechanics", "Newtonian mechanics", "Lagrangian mechanics",
            "Hamiltonian mechanics", "Fluid mechanics", "Solid mechanics",
            "Acoustics", "Optics", "Thermodynamics", "Statistical mechanics",

            # Modern physics
            "Quantum mechanics", "Quantum field theory", "Particle physics",
            "Nuclear physics", "Atomic physics", "Molecular physics",
            "Condensed matter physics", "Solid state physics", "Plasma physics",

            # Relativity and cosmology
            "Special relativity", "General relativity", "Cosmology",
            "Astrophysics", "High-energy physics",

            # Applied physics
            "Medical physics", "Biophysics", "Geophysics", "Chemical physics",
            "Engineering physics", "Computational physics",

            # Specialized topics
            "Superconductivity", "Superfluidity", "Quantum entanglement",
            "String theory", "Chaos theory", "Nonlinear dynamics",
            "Plasma physics", "Fusion", "Fission", "Radioactivity"
        ],
        "chemistry": [
            # Main branches
            "Organic chemistry", "Inorganic chemistry", "Physical chemistry",
            "Analytical chemistry", "Biochemistry", "Theoretical chemistry",

            # Specialized areas
            "Polymer chemistry", "Materials chemistry", "Medicinal chemistry",
            "Pharmaceutical chemistry", "Nuclear chemistry", "Electrochemistry",
            "Environmental chemistry", "Green chemistry", "Photochemistry",
            "Surface chemistry", "Colloid chemistry", "Supramolecular chemistry",

            # Applied chemistry
            "Industrial chemistry", "Forensic chemistry", "Food chemistry",
            "Agricultural chemistry", "Geochemistry", "Astrochemistry",

            # Techniques
            "Spectroscopy", "Chromatography", "Crystallography",
            "Electrochemistry", "Calorimetry", "Nuclear magnetic resonance"
        ],
        "astronomy": [
            # Main branches
            "Astrophysics", "Cosmology", "Planetary science", "Stellar astronomy",
            "Galactic astronomy", "Extragalactic astronomy", "Radio astronomy",
            "X-ray astronomy", "Gamma-ray astronomy", "Infrared astronomy",

            # Solar system
            "Solar physics", "Planetary geology", "Astronautics", "Space science",
            "Aeronomy", "Magnetosphere", "Heliosphere",

            # Objects and phenomena
            "Stellar evolution", "Stellar populations", "Interstellar medium",
            "Galactic dynamics", "Exoplanets", "Black holes", "Neutron stars",
            "Pulsars", "Quasars", "Supernovae", "Gamma-ray bursts",

            # Techniques
            "Observational astronomy", "Theoretical astronomy", "Astrostatistics",
            "Astrometry", "Celestial mechanics"
        ]
    }

    # ========== LIFE SCIENCES ==========

    LIFE_SCIENCES = {
        "biology_core": [
            # Molecular and cellular
            "Cell biology", "Molecular biology", "Genetics", "Genomics",
            "Proteomics", "Bioinformatics", "Systems biology", "Synthetic biology",

            # Microbiology
            "Microbiology", "Bacteriology", "Virology", "Mycology",
            "Parasitology", "Immunology", "Pathology",

            # Physiology and anatomy
            "Physiology", "Anatomy", "Histology", "Cytology",
            "Developmental biology", "Reproductive biology", "Aging biology",

            # Evolution and ecology
            "Evolutionary biology", "Ecology", "Population biology",
            "Behavioral biology", "Ethology", "Sociobiology"
        ],
        "botany": [
            # Plant biology
            "Plant anatomy", "Plant physiology", "Plant morphology",
            "Plant biochemistry", "Plant genetics", "Plant molecular biology",

            # Plant groups
            "Bryology", "Pteridology", "Gymnosperms", "Angiosperms",
            "Plant taxonomy", "Plant systematics", "Paleobotany",

            # Applied botany
            "Agriculture", "Horticulture", "Forestry", "Plant pathology",
            "Economic botany", "Ethnobotany", "Plant breeding",
            "Crop science", "Soil science", "Agronomy",

            # Specialized
            "Plant ecology", "Plant geography", "Phytogeography",
            "Marine botany", "Plant biotechnology"
        ],
        "zoology": [
            # Animal biology
            "Zoology", "Invertebrate zoology", "Vertebrate zoology",
            "Animal physiology", "Animal anatomy", "Animal behavior",

            # Specific groups
            "Entomology", "Ichthyology", "Herpetology", "Ornithology",
            "Mammalogy", "Primatology", "Cetology", "Malacology",
            "Arachnology", "Carcinology", "Nematology",

            # Applied zoology
            "Wildlife biology", "Conservation biology", "Zoo biology",
            "Marine biology", "Limnology", "Fisheries science",

            # Specialized
            "Ethology", "Primatology", "Zoogeography", "Paleozoology"
        ],
        "microbiology": [
            # Core microbiology
            "Bacteriology", "Virology", "Mycology", "Parasitology",
            "Phycology", "Protozoology",

            # Applied
            "Medical microbiology", "Environmental microbiology",
            "Industrial microbiology", "Food microbiology",
            "Agricultural microbiology", "Soil microbiology",

            # Molecular
            "Microbial genetics", "Microbial physiology", "Microbial ecology",
            "Microbial genomics", "Proteomics", "Metagenomics",

            # Emerging
            "Geomicrobiology", "Astrobiology", "Synthetic microbiology"
        ],
        "ecology_and_environmental": [
            # Ecology levels
            "Microbial ecology", "Population ecology", "Community ecology",
            "Ecosystem ecology", "Landscape ecology", "Global ecology",

            # Applied ecology
            "Conservation ecology", "Restoration ecology", "Urban ecology",
            "Agroecology", "Marine ecology", "Freshwater ecology",

            # Environmental science
            "Environmental science", "Environmental chemistry",
            "Environmental toxicology", "Environmental microbiology",

            # Specialized
            "Biogeography", "Ecophysiology", "Evolutionary ecology",
            "Behavioral ecology", "Chemical ecology", "Tropical ecology",

            # Climate and systems
            "Climatology", "Bioclimatology", "Ecological modeling",
            "Systems ecology", "Biogeochemistry"
        ]
    }

    # ========== MEDICAL AND HEALTH SCIENCES ==========

    MEDICAL_SCIENCES = {
        "clinical_medicine": [
            # Main specialties
            "Internal medicine", "Surgery", "Pediatrics", "Obstetrics and gynecology",
            "Psychiatry", "Radiology", "Anesthesiology", "Emergency medicine",
            "Pathology", "Family medicine", "Geriatrics", "Sports medicine",

            # Internal medicine subspecialties
            "Cardiology", "Endocrinology", "Gastroenterology", "Hematology",
            "Infectious disease", "Nephrology", "Oncology", "Pulmonology",
            "Rheumatology", "Allergy and immunology", "Neurology",

            # Surgical subspecialties
            "Neurosurgery", "Cardiothoracic surgery", "Orthopedic surgery",
            "Plastic surgery", "Vascular surgery", "Pediatric surgery",
            "Surgical oncology", "Transplant surgery",

            # Other specialties
            "Dermatology", "Ophthalmology", "Otolaryngology", "Urology",
            "Physical medicine", "Rehabilitation medicine"
        ],
        "basic_medical_sciences": [
            # Core sciences
            "Anatomy", "Histology", "Embryology", "Cell biology",
            "Biochemistry", "Molecular biology", "Genetics", "Immunology",
            "Microbiology", "Pathology", "Pharmacology", "Physiology",

            # Specialized
            "Neuroscience", "Neuroanatomy", "Neurophysiology", "Neurochemistry",
            " Cardiovascular physiology", "Respiratory physiology", "Renal physiology",
            "Gastrointestinal physiology", "Endocrine physiology",

            # Applied
            "Pathophysiology", "Medical microbiology", "Medical genetics",
            "Molecular medicine", "Cellular pathology", "Clinical biochemistry"
        ],
        "pharmacy_and_pharmacology": [
            # Main areas
            "Pharmacology", "Pharmacy", "Pharmaceutical chemistry",
            "Pharmacognosy", "Pharmaceutics", "Pharmacokinetics",
            "Pharmacodynamics", "Clinical pharmacology", "Toxicology",

            # Specialized pharmacology
            "Cardiovascular pharmacology", "Neuropharmacology", "Psychopharmacology",
            "Cancer pharmacology", "Antimicrobial pharmacology", "Immunopharmacology",

            # Drug development
            "Medicinal chemistry", "Drug design", "Drug delivery",
            "Pharmaceutical analysis", "Quality control", "Regulatory affairs",

            # Practice areas
            "Hospital pharmacy", "Clinical pharmacy", "Community pharmacy",
            "Industrial pharmacy", "Nuclear pharmacy", "Veterinary pharmacy"
        ],
        "public_health": [
            # Main areas
            "Public health", "Epidemiology", "Biostatistics", "Environmental health",
            "Occupational health", "Health policy", "Health management",

            # Disease control
            "Infectious disease epidemiology", "Chronic disease epidemiology",
            "Tropical medicine", "Travel medicine", "Vaccinology",

            # Health promotion
            "Health education", "Health promotion", "Disease prevention",
            "Nutritional epidemiology", "Maternal and child health",

            # Global health
            "Global health", "International health", "Humanitarian health",
            "Disaster medicine", "Refugee health"
        ],
        "allied_health": [
            # Nursing
            "Nursing", "Pediatric nursing", "Geriatric nursing", "Critical care nursing",
            "Psychiatric nursing", "Midwifery",

            # Therapies
            "Physical therapy", "Occupational therapy", "Speech therapy",
            "Respiratory therapy", "Radiation therapy", "Dietetics",

            # Diagnostics
            "Medical imaging", "Radiography", "Sonography", "Medical laboratory science",
            "Clinical chemistry", "Hematology", "Medical microbiology",

            # Other
            "Optometry", "Podiatry", "Chiropractic", "Osteopathic medicine",
            "Emergency medical services", "Athletic training"
        ],
        "dental_sciences": [
            "Dentistry", "Oral surgery", "Orthodontics", "Periodontics",
            "Endodontics", "Prosthodontics", "Pediatric dentistry",
            "Oral pathology", "Oral radiology", "Dental public health",
            "Oral medicine", "Dental materials", "Dental anatomy"
        ],
        "veterinary_sciences": [
            "Veterinary medicine", "Veterinary anatomy", "Veterinary physiology",
            "Veterinary pharmacology", "Veterinary surgery", "Veterinary pathology",
            "Veterinary microbiology", "Veterinary parasitology",
            "Veterinary epidemiology", "Veterinary public health",
            "Small animal medicine", "Large animal medicine", "Avian medicine",
            "Exotic animal medicine", "Wildlife medicine", "Aquatic animal medicine"
        ]
    }

    # ========== EARTH SCIENCES ==========

    EARTH_SCIENCES = {
        "geology": [
            # Core geology
            "Geology", "Mineralogy", "Petrology", "Crystallography",
            "Sedimentology", "Stratigraphy", "Structural geology",
            "Tectonics", "Geodynamics", "Plate tectonics",

            # Specialized
            "Volcanology", "Seismology", "Geothermometry", "Geomorphology",
            "Glacial geology", "Quaternary geology", "Engineering geology",
            "Environmental geology", "Economic geology", "Petroleum geology",

            # Applied
            "Mining geology", "Coal geology", "Geotechnical engineering",
            "Hydrogeology", "Groundwater hydrology"
        ],
        "paleontology": [
            # Main areas
            "Paleontology", "Paleozoology", "Paleobotany", "Micropaleontology",
            "Palynology", "Ichnology", "Taphonomy", "Biostratigraphy",

            # Fossil groups
            "Vertebrate paleontology", "Invertebrate paleontology",
            "Paleobotany", "Palynology", "Dinosaur paleontology",
            "Human paleontology", "Paleoanthropology",

            # Time periods
            "Paleozoic paleontology", "Mesozoic paleontology",
            "Cenozoic paleontology", "Quaternary paleontology",

            # Applications
            "Evolutionary paleontology", "Paleoecology", "Paleoclimatology",
            "Geobiology", "Molecular paleontology"
        ],
        "oceanography_and_hydrology": [
            # Oceanography
            "Oceanography", "Physical oceanography", "Chemical oceanography",
            "Biological oceanography", "Geological oceanography",
            "Marine geology", "Marine geophysics",

            # Hydrology
            "Hydrology", "Hydrogeology", "Limnology", "Glaciology",
            "Cryology", "Snow science", "Ice sheet dynamics",

            # Water resources
            "Water resources", "Hydrological modeling", "Ecohydrology",
            "Isotope hydrology", "Groundwater dynamics", "Watershed management"
        ],
        "atmospheric_science": [
            # Meteorology
            "Meteorology", "Synoptic meteorology", "Dynamic meteorology",
            "Physical meteorology", "Aviation meteorology", "Marine meteorology",

            # Climatology
            "Climatology", "Paleoclimatology", "Microclimatology",
            "Urban climatology", "Tropical climatology",

            # Atmospheric physics/chemistry
            "Atmospheric physics", "Atmospheric chemistry", "Aeronomy",
            "Atmospheric thermodynamics", "Atmospheric dynamics",

            # Specialized
            "Weather forecasting", "Severe weather", "Tropical meteorology",
            "Mountain meteorology", "Agricultural meteorology", "Air quality"
        ],
        "geophysics": [
            # Main areas
            "Geophysics", "Seismology", "Geomagnetism", "Paleomagnetism",
            "Gravimetry", "Geodesy", "Geodynamics",

            # Applied geophysics
            "Exploration geophysics", "Engineering geophysics",
            "Environmental geophysics", "Marine geophysics",

            # Specialized
            "Tectonophysics", "Rock physics", "Georadar", "Magnetotellurics",
            "Seismic tomography", "Geophysical inversion"
        ]
    }

    # ========== FORMAL SCIENCES ==========

    FORMAL_SCIENCES = {
        "mathematics": [
            # Pure mathematics
            "Algebra", "Linear algebra", "Abstract algebra", "Number theory",
            "Geometry", "Topology", "Algebraic geometry", "Differential geometry",
            "Analysis", "Real analysis", "Complex analysis", "Functional analysis",

            # Discrete mathematics
            "Combinatorics", "Graph theory", "Set theory", "Mathematical logic",
            "Category theory", "Order theory", "Lattice theory",

            # Applied mathematics
            "Differential equations", "Calculus of variations", "Dynamical systems",
            "Chaos theory", "Fractal geometry", "Game theory", "Optimization",

            # Specialized
            "Probability theory", "Measure theory", "Ergodic theory",
            "Harmonic analysis", "Representation theory", "K-theory"
        ],
        "statistics_and_data_science": [
            # Core statistics
            "Statistics", "Mathematical statistics", "Probability theory",
            "Bayesian statistics", "Nonparametric statistics",
            "Multivariate statistics", "Time series analysis", "Survival analysis",

            # Applied statistics
            "Biostatistics", "Econometrics", "Psychometrics", "Chemometrics",
            "Geostatistics", "Spatial statistics", "Environmental statistics",

            # Data science
            "Data science", "Machine learning", "Data mining", "Big data analytics",
            "Predictive analytics", "Statistical learning", "Computational statistics",

            # Experimental design
            "Design of experiments", "Survey methodology", "Sampling theory",
            "Quality control", "Reliability theory"
        ],
        "computer_science": [
            # Foundations
            "Algorithms", "Data structures", "Theory of computation",
            "Computational complexity", "Automata theory", "Formal languages",

            # Systems
            "Operating systems", "Distributed systems", "Computer networks",
            "Database systems", "Computer architecture", "Parallel computing",

            # Software
            "Software engineering", "Programming languages", "Compilers",
            "Software testing", "Requirements engineering", "DevOps",

            # AI and ML
            "Artificial intelligence", "Machine learning", "Deep learning",
            "Computer vision", "Natural language processing", "Robotics",
            "Neural networks", "Reinforcement learning",

            # Specialized
            "Computer graphics", "Human-computer interaction", "Information retrieval",
            "Cryptography", "Information theory", "Computational biology",
            "High-performance computing", "Cloud computing"
        ],
        "logic_and_computation": [
            "Mathematical logic", "Philosophical logic", "Modal logic",
            "Temporal logic", "Fuzzy logic", "Intuitionistic logic",
            "Proof theory", "Model theory", "Recursion theory", "Set theory",
            "Type theory", "Category theory", "Computability theory",
            "Complexity theory", "Automated reasoning", "Formal verification"
        ],
        "information_and_systems": [
            "Information theory", "Coding theory", "Cryptography",
            "Network theory", "Systems theory", "Control theory",
            "Signal processing", "Image processing", "Pattern recognition",
            "Computational linguistics", "Bioinformatics", "Neuroinformatics"
        ]
    }

    # ========== ENGINEERING AND TECHNOLOGY ==========

    ENGINEERING = {
        "mechanical_engineering": [
            "Mechanical engineering", "Mechanics", "Thermodynamics", "Fluid mechanics",
            "Heat transfer", "Mass transfer", "Machine design", "Mechatronics",
            "Robotics", "Automotive engineering", "Aerospace propulsion",
            "HVAC engineering", "Manufacturing engineering", "Tribology",
            "Finite element analysis", "Computational fluid dynamics"
        ],
        "electrical_and_electronic": [
            "Electrical engineering", "Electronics", "Power engineering",
            "Control engineering", "Signal processing", "Telecommunications",
            "Computer engineering", "VLSI design", "Embedded systems",
            "Digital electronics", "Analog electronics", "Microwave engineering",
            "Antenna theory", "Electromagnetic theory", "Photonics"
        ],
        "civil_and_architectural": [
            "Civil engineering", "Structural engineering", "Geotechnical engineering",
            "Transportation engineering", "Hydraulic engineering", "Coastal engineering",
            "Construction engineering", "Surveying", "Architecture",
            "Urban planning", "Landscape architecture", "Building science",
            "Construction management", "Infrastructure engineering"
        ],
        "chemical_and_process": [
            "Chemical engineering", "Process engineering", "Biochemical engineering",
            "Petroleum engineering", "Polymer engineering", "Materials processing",
            "Separation processes", "Reaction engineering", "Transport phenomena",
            "Process control", "Process design", "Industrial chemistry"
        ],
        "materials_engineering": [
            "Materials science", "Metallurgy", "Ceramic engineering",
            "Polymer engineering", "Composite materials", "Nomaterials",
            "Biomaterials", "Electronic materials", "Magnetic materials",
            "Optical materials", "Smart materials", "Materials characterization",
            "Corrosion engineering", "Surface engineering"
        ],
        "biomedical_engineering": [
            "Biomedical engineering", "Bioinstrumentation", "Biomaterials",
            "Biomechanics", "Rehabilitation engineering", "Medical imaging",
            "Tissue engineering", "Regenerative medicine", "Neural engineering",
            "Bioinformatics", "Computational biology", "Systems biology",
            "Clinical engineering", "Prosthetics and orthotics"
        ],
        "aerospace_engineering": [
            "Aerospace engineering", "Aeronautical engineering", "Astronautical engineering",
            "Flight dynamics", "Aerodynamics", "Propulsion systems",
            "Avionics", "Flight control systems", "Spacecraft design",
            "Satellite engineering", "Rocket propulsion", "Astrodynamics"
        ],
        "industrial_and_systems": [
            "Industrial engineering", "Systems engineering", "Operations research",
            "Manufacturing engineering", "Quality engineering", "Reliability engineering",
            "Human factors engineering", "Ergonomics", "Supply chain engineering",
            "Logistics engineering", "Facility planning", "Production engineering",
            "Engineering management", "Engineering economics"
        ],
        "emerging_engineering": [
            "Nanotechnology", "Microelectromechanical systems", "Quantum engineering",
            "Energy engineering", "Environmental engineering", "Green engineering",
            "Sustainable engineering", "Renewable energy systems",
            "Smart grid technology", "Battery technology", "Fuel cell technology",
            "Carbon capture", "Water treatment engineering"
        ]
    }

    # ========== AGRICULTURAL AND FOOD SCIENCES ==========

    AGRICULTURAL_SCIENCES = {
        "agronomy_and_crops": [
            "Agronomy", "Crop science", "Plant breeding", "Genetic improvement",
            "Seed technology", "Crop physiology", "Crop protection",
            "Weed science", "Plant pathology", "Entomology", "Nematology",
            "Soil science", "Soil chemistry", "Soil physics", "Soil microbiology",
            "Soil ecology", "Plant nutrition", "Fertilizer technology",
            "Irrigation science", "Water management"
        ],
        "horticulture": [
            "Horticulture", "Pomology", "Olericulture", "Floriculture",
            "Ornamental horticulture", "Landscape horticulture",
            "Greenhouse management", "Nursery management", "Turfgrass science",
            "Postharvest physiology", "Postharvest technology",
            "Vegetable production", "Fruit production", "Viticulture"
        ],
        "animal_science": [
            "Animal science", "Animal breeding", "Animal genetics",
            "Animal nutrition", "Animal physiology", "Animal behavior",
            "Livestock production", "Poultry science", "Swine science",
            "Dairy science", "Beef cattle science", "Sheep science",
            "Equine science", "Aquaculture", "Mariculture",
            "Animal welfare science", "Pasture management"
        ],
        "forestry": [
            "Forestry", "Silviculture", "Forest ecology", "Forest management",
            "Forest economics", "Forest engineering", "Forest biometry",
            "Dendrology", "Wood science", "Wood technology",
            "Forest protection", "Forest pathology", "Forest entomology",
            "Urban forestry", "Agroforestry", "Social forestry",
            "Watershed management", "Forest hydrology"
        ],
        "food_science": [
            "Food science", "Food chemistry", "Food microbiology",
            "Food engineering", "Food processing", "Food preservation",
            "Food packaging", "Food safety", "Food toxicology",
            "Food analysis", "Sensory evaluation", "Quality control",
            "Dairy technology", "Cereal technology", "Meat science",
            "Fruit and vegetable processing", "Beverage technology",
            "Fermentation technology", "Enzyme technology"
        ]
    }

    # ========== PSYCHOLOGICAL AND COGNITIVE SCIENCES ==========

    PSYCHOLOGICAL_SCIENCES = {
        "psychology": [
            # Core areas
            "Cognitive psychology", "Developmental psychology", "Social psychology",
            "Clinical psychology", "Counseling psychology", "Educational psychology",

            # Specialized
            "Neuropsychology", "Health psychology", "Forensic psychology",
            "Industrial-organizational psychology", "Sports psychology",

            # Research
            "Experimental psychology", "Psychometrics", "Psychological statistics",
            "Qualitative research methods", "Psychophysiology",

            # Applied
            "School psychology", "Child psychology", "Geriatric psychology",
            "Rehabilitation psychology", "Community psychology"
        ],
        "cognitive_science": [
            "Cognitive science", "Cognitive neuroscience", "Computational neuroscience",
            "Neurolinguistics", "Psycholinguistics", "Philosophy of mind",
            "Consciousness studies", "Artificial intelligence",
            "Cognitive modeling", "Brain mapping", "Neuroimaging",
            "Attention research", "Memory research", "Language processing",
            "Decision making", "Reasoning", "Problem solving"
        ],
        "neuroscience": [
            "Neuroscience", "Molecular neuroscience", "Cellular neuroscience",
            "Systems neuroscience", "Behavioral neuroscience", "Cognitive neuroscience",
            "Computational neuroscience", "Developmental neuroscience",
            "Neuroanatomy", "Neurophysiology", "Neurochemistry",
            "Neuropharmacology", "Neuroendocrinology", "Neuroimmunology"
        ],
        "educational_and_learning": [
            "Educational psychology", "Learning sciences", "Instructional design",
            "Educational technology", "Special education", "Gifted education",
            "Educational assessment", "Educational measurement",
            "Curriculum development", "Teacher education", "Adult education",
            "Distance education", "E-learning", "Learning disabilities"
        ]
    }

    # ========== INTERDISCIPLINARY SCIENCES ==========

    INTERDISCIPLINARY_SCIENCES = [
        # Bio-based
        "Bioinformatics", "Computational biology", "Systems biology",
        "Synthetic biology", "Biotechnology", "Biophysics",
        "Biochemistry", "Molecular biology", "Genomics", "Proteomics",
        "Metabolomics", "Transcriptomics", "Epigenomics",

        # Environmental
        "Environmental science", "Environmental engineering",
        "Sustainability science", "Ecological engineering",
        "Climate science", "Atmospheric science", "Oceanography",

        # Medical-technology
        "Biomedical engineering", "Medical physics", "Health informatics",
        "Telemedicine", "Personalized medicine", "Precision medicine",
        "Regenerative medicine", "Gene therapy", "Nanomedicine",

        # Cognitive-tech
        "Cognitive science", "Artificial intelligence", "Neuroinformatics",
        "Computational neuroscience", "Brain-computer interface",

        # Other
        "Complex systems", "Network science", "Data science",
        "Science and technology studies", "History of science",
        "Philosophy of science", "Scientific methodology"
    ]

    # ========== SCIENTIFIC ENTITIES ==========

    SCIENTIFIC_ENTITIES = {
        "chemical_elements": [
            # Main group elements
            "Hydrogen", "Helium", "Lithium", "Beryllium", "Boron", "Carbon",
            "Nitrogen", "Oxygen", "Fluorine", "Neon", "Sodium", "Magnesium",
            "Aluminum", "Silicon", "Phosphorus", "Sulfur", "Chlorine", "Argon",
            "Potassium", "Calcium",

            # Transition metals
            "Titanium", "Vanadium", "Chromium", "Manganese", "Iron", "Cobalt",
            "Nickel", "Copper", "Zinc",

            # Other important elements
            "Silver", "Gold", "Mercury", "Lead", "Uranium", "Plutonium",
            "Silicon", "Germanium", "Tin", "Tungsten"
        ],
        "subatomic_particles": [
            # Fundamental particles
            "Quark", "Lepton", "Electron", "Muon", "Tau", "Neutrino",
            "Photon", "Gluon", "Z boson", "W boson", "Higgs boson",

            # Hadrons
            "Proton", "Neutron", "Pion", "Kaon", "Baryon", "Meson",

            # Exotic
            "Positron", "Antiproton", "Antineutron", "Muon", "Pion",
            "Alpha particle", "Beta particle", "Gamma ray"
        ],
        "biological_structures": [
            # Molecular
            "DNA", "RNA", "Gene", "Chromosome", "Nucleotide",
            "Protein", "Enzyme", "Antibody", "Antigen", "Hormone",
            "Lipid", "Carbohydrate", "Vitamin", "ATP", "NADH",

            # Cellular
            "Cell", "Nucleus", "Mitochondria", "Ribosome", "Endoplasmic reticulum",
            "Golgi apparatus", "Lysosome", "Chloroplast", "Vacuole", "Cytoplasm",
            "Cell membrane", "Cytoskeleton",

            # Neural
            "Neuron", "Synapse", "Axon", "Dendrite", "Myelin sheath",
            "Neurotransmitter", "Action potential", "Glial cell",

            # Higher level
            "Tissue", "Organ", "Organ system", "Organism", "Population",
            "Community", "Ecosystem", "Biosphere", "Biome", "Habitat",
            "Niche", "Trophic level"
        ],
        "astronomical_objects": [
            # Solar system
            "Sun", "Mercury", "Venus", "Earth", "Moon", "Mars", "Phobos", "Deimos",
            "Jupiter", "Io", "Europa", "Ganymede", "Callisto",
            "Saturn", "Titan", "Rings of Saturn", "Uranus", "Neptune",
            "Pluto", "Ceres", "Eris", "Sedna", "Makemake", "Haumea",

            # Beyond solar system
            "Star", "Red dwarf", "White dwarf", "Red giant", "Blue giant",
            "Neutron star", "Pulsar", "Magnetar", "Black hole",
            "Nebula", "Supernova", "Protostar", "Main sequence star",

            # Galactic
            "Galaxy", "Milky Way", "Andromeda Galaxy", "Elliptical galaxy",
            "Spiral galaxy", "Irregular galaxy", "Dwarf galaxy", "Galaxy cluster",

            # Large scale
            "Exoplanet", "Super-Earth", "Hot Jupiter", "Gas giant", "Ice giant",
            "Supercluster", "Void", "Quasar", "Blazar", "Gamma-ray burst",
            "Cosmic microwave background", "Dark matter", "Dark energy"
        ],
        "mathematical_objects": [
            # Basic
            "Number", "Integer", "Rational number", "Real number", "Complex number",
            "Set", "Function", "Sequence", "Series", "Limit",

            # Algebraic
            "Group", "Ring", "Field", "Vector space", "Matrix", "Tensor",
            "Polynomial", "Equation", "Inequality", "Algebraic variety",

            # Geometric/topological
            "Manifold", "Topology", "Curve", "Surface", "Metric space",
            "Fractal", "Knot", "Link", "Graph", "Tree", "Network",

            # Special
            "Prime number", "Fibonacci sequence", "Golden ratio", "Pi", "Euler's number",
            "Imaginary unit", "Infinity", "Derivative", "Integral", "Differential equation"
        ],
        "computing_objects": [
            # Fundamentals
            "Algorithm", "Data structure", "Array", "Linked list", "Stack", "Queue",
            "Tree", "Graph", "Hash table", "Heap", "Set", "Map",

            # Systems
            "Operating system", "Process", "Thread", "File system", "Database",
            "Network", "Protocol", "API", "Library", "Framework",
            "Virtual machine", "Container", "Microservice", "Serverless",

            # Programming
            "Variable", "Function", "Class", "Object", "Method", "Inheritance",
            "Polymorphism", "Closure", "Coroutine", "Promise", "Future",

            # Concurrency
            "Semaphore", "Mutex", "Lock", "Monitor", "Deadlock", "Race condition",
            "Atomic operation", "Memory barrier", "Cache coherence",

            # AI/ML
            "Neural network", "Deep learning", "Convolution", "Attention mechanism",
            "Transformer", "Gradient descent", "Backpropagation", "Overfitting",
            "Regularization", "Feature extraction", "Dimensionality reduction"
        ]
    }

    # ========== FAMOUS SCIENTISTS AND ENGINEERS ==========

    FAMOUS_SCIENTISTS = {
        "physicists": [
            # Foundational
            "Isaac Newton", "Galileo Galilei", "Albert Einstein", "James Clerk Maxwell",
            "Michael Faraday", "Niels Bohr", "Max Planck", "Louis de Broglie",

            # Quantum era
            "Richard Feynman", "Paul Dirac", "Werner Heisenberg", "Erwin Schrödinger",
            "Enrico Fermi", "Wolfgang Pauli", "John von Neumann",

            # Modern
            "Stephen Hawking", "Roger Penrose", "Murray Gell-Mann", "Sheldon Glashow",
            "Steven Weinberg", "Peter Higgs", "Kip Thorne", "Lene Hau",

            # Women in physics
            "Marie Curie", "Lise Meitner", "Maria Goeppert-Mayer", "Chien-Shiung Wu",
            "Rosalind Franklin", "Vera Rubin", "Jocelyn Bell Burnell", "Donna Strickland"
        ],
        "chemists": [
            "Dmitri Mendeleev", "Linus Pauling", "Robert Boyle", "John Dalton",
            "Marie Curie", "Louis Pasteur", "Friedrich Wöhler", "August Kekulé",
            "Ahmed Zewail", "Frances Arnold", "Jennifer Doudna", "Emmanuelle Charpentier",
            "Carolyn Bertozzi", "M. Stanley Whittingham", "John Goodenough"
        ],
        "biologists_and_life_scientists": [
            # Foundational
            "Charles Darwin", "Gregor Mendel", "Jean-Baptiste Lamarck", "Alfred Russel Wallace",
            "Thomas Hunt Morgan", "Barbara McClintock", "Rosalind Franklin",

            # Modern
            "James Watson", "Francis Crick", "Maurice Wilkins", "Frederick Sanger",
            "Kary Mullis", "Paul Nurse", "Elizabeth Blackburn", "Carol Greider",

            # Botanists
            "Carl Linnaeus", "Joseph Banks", "Gregor Mendel", "George Washington Carver",

            # Zoologists
            "Jane Goodall", "Dian Fossey", "Birute Galdikas", "David Attenborough",
            "Edward O. Wilson", "Ernst Mayr", "George Gaylord Simpson", "Stephen Jay Gould",

            # Ecologists
            "Rachel Carson", "Eugene Odum", "G. Evelyn Hutchinson", "Robert MacArthur",
            "Daniel Janzen", "Paul Ehrlich"
        ],
        "medical_scientists": [
            # Historical
            "Hippocrates", "Galen", "William Harvey", "Edward Jenner",
            "Louis Pasteur", "Robert Koch", "Alexander Fleming",

            # Modern
            "Jonas Salk", "Albert Sabin", "Frederick Banting", "Charles Best",
            "James Black", "Gertrude Elion", "George Hitchings", "Tu Youyou",

            # Women in medicine
            "Elizabeth Blackwell", "Rebecca Lee Crumpler", "Virginia Apgar",
            "Helen Brooke Taussig", "Gerty Cori", "Rosalyn Yalow"
        ],
        "earth_scientists": [
            # Geologists
            "James Hutton", "Charles Lyell", "Georges Cuvier", "Louis Agassiz",
            "Alfred Wegener", "Harry Hess", "Marie Tharp",

            # Paleontologists
            "Mary Anning", "Richard Owen", "Othniel Marsh", "Edward Cope",
            "Stephen Jay Gould", "Jack Horner", "Paul Sereno", "Mary Leakey",

            # Meteorologists/Climatologists
            " Vilhelm Bjerknes", "Carl-Gustaf Rossby", "Syukuro Manabe",
            "Katherine Hayhoe", "Michael Mann"
        ],
        "mathematicians": [
            # Ancient/Medieval
            "Euclid", "Pythagoras", "Archimedes", "Aryabhata", "Brahmagupta",
            "Al-Khwarizmi", "Omar Khayyam", "Fibonacci", "Nicole Oresme",

            # Modern
            "Leonhard Euler", "Carl Friedrich Gauss", "Bernhard Riemann",
            "Henri Poincaré", "David Hilbert", "John von Neumann", "Alan Turing",

            # Contemporary
            "Andrew Wiles", "Grigori Perelman", "Terence Tao", "Maryam Mirzakhani",
            "Karen Uhlenbeck", "Jean-Pierre Serre", "Alexander Grothendieck",

            # Non-Western
            "Srinivasa Ramanujan", "Shiing-Shen Chern", "Kodaira Kunihiko",
            "Atiyah Michael", "John Tate"
        ],
        "computer_scientists": [
            "Alan Turing", "John von Neumann", "Claude Shannon", "Donald Knuth",
            "Tim Berners-Lee", "Vint Cerf", "Bob Kahn", "Dennis Ritchie",
            "Ken Thompson", "Bjarne Stroustrup", "Guido van Rossum", "James Gosling",
            "Ada Lovelace", "Grace Hopper", "Margaret Hamilton", "Lynn Conway",
            "Sophie Wilson", "Frances Allen", "Shafi Goldwasser", "Leslie Lamport"
        ],
        "engineers_and_inventors": [
            "Nikola Tesla", "Thomas Edison", "Alexander Graham Bell", "Guglielmo Marconi",
            "Henry Ford", "Wright Brothers", "Gustave Eiffel", "Isambard Kingdom Brunel",
            "George Stephenson", "James Watt", "Robert Fulton", "Samuel Morse",
            "Rudolf Diesel", "Fritz Lang", "Wernher von Braun", "Qian Xuesen"
        ],
        "non_western_scientists": [
            # Ancient/Classical
            "Zhang Heng", "Shen Kuo", "Su Song", "Aryabhata", "Brahmagupta",
            "Alhazen", "Al-Biruni", "Ibn Sina", "Omar Khayyam", "Nasir al-Din al-Tusi",

            # Modern
            "C. V. Raman", "Subrahmanyan Chandrasekhar", "Homi Bhabha", "Abdus Salam",
            "Chen-Ning Yang", "Tsung-Dao Lee", "Koji Fukushima", "Hideki Yukawa",
            "Tu Youyou", "Katherine Cheung", "Chien-Shiung Wu", "Zhang Cunhao"
        ]
    }

    # ========== FAMOUS DISCOVERIES AND INVENTIONS ==========

    DISCOVERIES_INVENTIONS = {
        "physics": [
            "Law of universal gravitation", "Laws of motion", "Electromagnetic induction",
            "Photoelectric effect", "Radioactivity", "X-rays", "Electron", "Neutron",
            "Positron", "Muon", "Higgs boson", "Gravitational waves", "Superconductivity",
            "Laser", "Maser", "Transistor", "Integrated circuit", "LED"
        ],
        "chemistry": [
            "Periodic table", "Electron configuration", "Chemical bonding theory",
            "DNA structure", "Penicillin", "Vitamin C", "Insulin", "Aspirin",
            "Polyethylene", "Nylon", "Teflon", "Plastic", "Graphene", "Fullerene",
            "PCR", "CRISPR", "DNA sequencing"
        ],
        "biology_medicine": [
            "Evolution by natural selection", "Germ theory of disease", "DNA double helix",
            "Vaccination", "Antibiotics", "Anesthesia", "MRI", "CT scan",
            "Gene therapy", "Monoclonal antibodies", "Stem cells", "Immune checkpoint",
            "Circadian rhythm", "Epigenetics", "Telomerase"
        ],
        "astronomy_earth": [
            "Heliocentrism", "Laws of planetary motion", "Universal gravitation",
            "Expansion of universe", "Cosmic microwave background", "Black holes",
            "Exoplanets", "Gravitational waves", "Plate tectonics", "Continental drift",
            "Magnetic field reversals", "Ice ages", "Mass extinctions"
        ],
        "technology": [
            "Printing press", "Steam engine", "Telegraph", "Telephone", "Light bulb",
            "Radio", "Television", "Transistor", "Integrated circuit", "Microprocessor",
            "Internet", "World Wide Web", "GPS", "Smartphone", "Aircraft", "Rocket",
            "3D printing", "Quantum computer"
        ]
    }

    # ========== SCIENTIFIC INSTITUTIONS ==========

    INSTITUTIONS = {
        "research_labs": [
            "CERN", "NASA", "ESA", "JAXA", "ISRO", "CNES", "ROSCOSMOS",
            "Max Planck Institute", "Fraunhofer Society", "Kavli Institutes",
            "Bell Labs", "IBM Research", "Google DeepMind", "OpenAI",
            "Brookhaven National Laboratory", "Lawrence Berkeley National Lab",
            "Fermilab", "SLAC", "Stanford Linear Accelerator Center",
            "Riken", "KAIST", "CSIR"
        ],
        "universities": [
            # US
            "MIT", "Stanford University", "Caltech", "Harvard University",
            "Princeton University", "UC Berkeley", "Carnegie Mellon",

            # Europe
            "University of Cambridge", "University of Oxford", "ETH Zurich",
            "Imperial College London", "UCL", "Sorbonne University",
            "Technical University of Munich", "Delft University of Technology",

            # Asia
            "Tsinghua University", "Peking University", "Tokyo University",
            "National University of Singapore", "KAIST", "IIT Bombay",
            "University of Melbourne", "Australian National University"
        ],
        "facilities": [
            "Large Hadron Collider", "Hubble Space Telescope", "James Webb Space Telescope",
            "LIGO", "VIRGO", "IceCube Neutrino Observatory", "Super-Kamiokande",
            "National Ignition Facility", "ITER", "International Space Station",
            "Very Large Telescope", "Atacama Large Millimeter Array",
            "Event Horizon Telescope", "Voyager program"
        ]
    }

    # ========== WIKIPEDIA SCIENCE CATEGORIES ==========

    WIKIPEDIA_CATEGORIES = [
        # Main
        "Category:Science", "Category:Scientific disciplines", "Category:Scientific methodology",

        # Physical sciences
        "Category:Physics", "Category:Classical mechanics", "Category:Quantum mechanics",
        "Category:Thermodynamics", "Category:Electromagnetism", "Category:Optics",
        "Category:Relativity", "Category:Particle physics", "Category:Nuclear physics",

        "Category:Chemistry", "Category:Organic chemistry", "Category:Inorganic chemistry",
        "Category:Physical chemistry", "Category:Analytical chemistry", "Category:Biochemistry",

        # Life sciences
        "Category:Biology", "Category:Cell biology", "Category:Molecular biology",
        "Category:Genetics", "Category:Microbiology", "Category:Virology", "Category:Bacteriology",

        # Botany
        "Category:Botany", "Category:Plants", "Category:Plant anatomy", "Category:Plant physiology",
        "Category:Plant taxonomy", "Category:Agriculture", "Category:Horticulture", "Category:Forestry",

        # Zoology
        "Category:Zoology", "Category:Animals", "Category:Invertebrates", "Category:Vertebrates",
        "Category:Entomology", "Category:Ornithology", "Category:Mammalogy", "Category:Ichthyology",

        # Paleontology
        "Category:Paleontology", "Category:Paleozoology", "Category:Paleobotany",
        "Category:Fossils", "Category:Dinosaurs", "Category:Evolutionary biology",

        # Medical sciences
        "Category:Medicine", "Category:Clinical medicine", "Category:Surgery",
        "Category:Internal medicine", "Category:Pediatrics", "Category:Obstetrics and gynecology",
        "Category:Psychiatry", "Category:Radiology", "Category:Pathology",
        "Category:Pharmacology", "Category:Pharmacy", "Category:Pharmaceuticals",
        "Category:Nursing", "Category:Public health", "Category:Epidemiology",
        "Category:Dentistry", "Category:Veterinary medicine",

        # Earth sciences
        "Category:Earth sciences", "Category:Geology", "Category:Mineralogy",
        "Category:Meteorology", "Category:Oceanography", "Category:Paleontology",
        "Category:Seismology", "Category:Volcanology", "Category:Glaciology",

        # Astronomy
        "Category:Astronomy", "Category:Astrophysics", "Category:Planetary science",
        "Category:Cosmology", "Category:Stellar astronomy", "Category:Galactic astronomy",

        # Formal sciences
        "Category:Mathematics", "Category:Algebra", "Category:Geometry", "Category:Calculus",
        "Category:Number theory", "Category:Topology", "Category:Statistics", "Category:Logic",

        "Category:Computer science", "Category:Algorithms", "Category:Artificial intelligence",
        "Category:Machine learning", "Category:Computer vision", "Category:Cryptography",

        # Engineering
        "Category:Engineering", "Category:Mechanical engineering", "Category:Electrical engineering",
        "Category:Civil engineering", "Category:Chemical engineering", "Category:Biomedical engineering",
        "Category:Aerospace engineering", "Category:Materials science", "Category:Nanotechnology",

        # Agricultural sciences
        "Category:Agriculture", "Category:Agronomy", "Category:Horticulture",
        "Category:Animal science", "Category:Forestry", "Category:Food science",

        # Psychological sciences
        "Category:Psychology", "Category:Cognitive psychology", "Category:Clinical psychology",
        "Category:Neuroscience", "Category:Cognitive science", "Category:Educational psychology",

        # Scientists
        "Category:Physicists", "Category:Chemists", "Category:Biologists", "Category:Mathematicians",
        "Category:Computer scientists", "Category:Engineers", "Category:Physicians",
        "Category:Nobel laureates in Physics", "Category:Nobel laureates in Chemistry",
        "Category:Nobel laureates in Physiology or Medicine",

        # Scientific entities
        "Category:Chemical elements", "Category:Subatomic particles", "Category:Fundamental physics concepts",
        "Category:Biological structures", "Category:Mathematical objects", "Category:Astronomical objects"
    ]

    # ========== SEARCH KEYWORD COMPONENTS ==========

    KEYWORD_COMPONENTS = {
        "disciplines": [
            "physics", "chemistry", "biology", "botany", "zoology", "microbiology",
            "paleontology", "geology", "astronomy", "mathematics", "computer science",
            "engineering", "medicine", "pharmacology", "psychology", "neuroscience",
            "ecology", "genetics", "biochemistry", "materials science", "nanotechnology"
        ],
        "concepts": [
            "theory", "law", "principle", "phenomenon", "mechanism", "process",
            "equation", "formula", "algorithm", "structure", "function", "model",
            "discovery", "invention", "innovation", "breakthrough", "paradigm",
            "synthesis", "reaction", "interaction", "classification", "taxonomy"
        ],
        "modifiers": [
            "fundamental", "applied", "theoretical", "experimental", "computational",
            "quantum", "classical", "modern", "ancient", "contemporary", "molecular",
            "atomic", "nano", "macro", "micro", "interdisciplinary", "multidisciplinary",
            "clinical", "preclinical", "in vitro", "in vivo", "in silico"
        ],
        "questions": [
            "what is", "how does", "why is", "explain", "theory of",
            "principles of", "applications of", "history of", "discovery of",
            "invention of", "formula for", "equation for", "algorithm for"
        ],
        "entities": [
            "element", "compound", "particle", "organism", "species", "genus",
            "structure", "system", "machine", "device", "instrument", "tool",
            "method", "technique", "enzyme", "protein", "gene", "cell"
        ]
    }

    # ========== HELPER METHODS ==========

    def get_all_disciplines(self) -> List[str]:
        """Get all disciplines as flat list"""
        all_disciplines = []

        # Get from all category dictionaries
        for category_dict in [self.PHYSICAL_SCIENCES, self.LIFE_SCIENCES,
                              self.MEDICAL_SCIENCES, self.EARTH_SCIENCES,
                              self.FORMAL_SCIENCES, self.ENGINEERING,
                              self.AGRICULTURAL_SCIENCES, self.PSYCHOLOGICAL_SCIENCES]:
            for subcategory, discipline_list in category_dict.items():
                if isinstance(discipline_list, list):
                    all_disciplines.extend(discipline_list)

        all_disciplines.extend(self.INTERDISCIPLINARY_SCIENCES)
        return all_disciplines

    def get_all_entities(self) -> List[str]:
        """Get all scientific entities as flat list"""
        all_entities = []
        for entity_list in self.SCIENTIFIC_ENTITIES.values():
            all_entities.extend(entity_list)
        return all_entities

    def get_all_categories(self) -> List[str]:
        """Get all Wikipedia categories"""
        return self.WIKIPEDIA_CATEGORIES

    def get_random_scientist(self) -> str:
        """Get random famous scientist"""
        all_scientists = []
        for scientist_dict in self.FAMOUS_SCIENTISTS.values():
            if isinstance(scientist_dict, list):
                all_scientists.extend(scientist_dict)
        return random.choice(all_scientists)

    def get_random_discovery(self) -> str:
        """Get random discovery or invention"""
        all_discoveries = []
        for discovery_list in self.DISCOVERIES_INVENTIONS.values():
            all_discoveries.extend(discovery_list)
        return random.choice(all_discoveries)

    def get_all_famous_scientists(self) -> Dict[str, List[str]]:
        """Get all famous scientists by category"""
        return self.FAMOUS_SCIENTISTS

    def generate_search_queries(self, num_queries: int = 50) -> List[str]:
        """Generate diverse science search queries"""
        queries = []

        all_disciplines = self.get_all_disciplines()
        all_entities = self.get_all_entities()

        # Concept queries
        concept_lists = []
        for concept_dict in self.DISCOVERIES_INVENTIONS.values():
            concept_lists.extend(concept_dict)

        for _ in range(num_queries):
            pattern = random.choice([
                # Discipline + concept
                lambda: f"{random.choice(all_disciplines)} {random.choice(self.KEYWORD_COMPONENTS['concepts'])}",
                # Entity + discipline
                lambda: f"{random.choice(all_entities)} in {random.choice(all_disciplines)}",
                # Scientist + discovery
                lambda: f"{self.get_random_scientist()} {random.choice(['discovery', 'invention', 'theory', 'law', 'research'])}",
                # Discovery + field
                lambda: f"{random.choice(concept_lists)} {random.choice(['in physics', 'in chemistry', 'in biology', 'in medicine', 'in mathematics'])}",
                # Entity + concept
                lambda: f"{random.choice(all_entities)} {random.choice(self.KEYWORD_COMPONENTS['concepts'])}",
                # Discipline + modifier
                lambda: f"{random.choice(self.KEYWORD_COMPONENTS['modifiers'])} {random.choice(all_disciplines)}",
                # Institution + field
                lambda: f"{random.choice(self.INSTITUTIONS['research_labs'])} {random.choice(all_disciplines)}",
                # Complex query
                lambda: f"{random.choice(self.KEYWORD_COMPONENTS['modifiers'])} {random.choice(all_entities)} in {random.choice(all_disciplines)}",
                # Question format
                lambda: f"{random.choice(self.KEYWORD_COMPONENTS['questions'])} {random.choice(all_disciplines)}",
                # Application focused
                lambda: f"applications of {random.choice(all_disciplines)} in {random.choice(['medicine', 'industry', 'agriculture', 'environment', 'energy'])}",
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
    pools = ExpandedSciencePools()

    print("=" * 70)
    print("EXPANDED SCIENCE POOLS - COMPREHENSIVE VERSION")
    print("=" * 70)

    print(f"\nTotal Disciplines: {len(pools.get_all_disciplines())}")
    print(f"Entities: {len(pools.get_all_entities())}")
    print(f"Wikipedia Categories: {len(pools.get_all_categories())}")

    print("\n" + "=" * 70)
    print("DISCIPLINE BREAKDOWN")
    print("=" * 70)

    print("\nPhysical Sciences:")
    for cat, items in pools.PHYSICAL_SCIENCES.items():
        print(f"  {cat}: {len(items)} items")

    print("\nLife Sciences:")
    for cat, items in pools.LIFE_SCIENCES.items():
        print(f"  {cat}: {len(items)} items")

    print("\nMedical Sciences:")
    for cat, items in pools.MEDICAL_SCIENCES.items():
        print(f"  {cat}: {len(items)} items")

    print("\nEarth Sciences:")
    for cat, items in pools.EARTH_SCIENCES.items():
        print(f"  {cat}: {len(items)} items")

    print("\nFormal Sciences:")
    for cat, items in pools.FORMAL_SCIENCES.items():
        print(f"  {cat}: {len(items)} items")

    print("\nEngineering:")
    for cat, items in pools.ENGINEERING.items():
        print(f"  {cat}: {len(items)} items")

    print("\nAgricultural Sciences:")
    for cat, items in pools.AGRICULTURAL_SCIENCES.items():
        print(f"  {cat}: {len(items)} items")

    print("\nPsychological Sciences:")
    for cat, items in pools.PSYCHOLOGICAL_SCIENCES.items():
        print(f"  {cat}: {len(items)} items")

    print("\nInterdisciplinary Sciences:")
    print(f"  {len(pools.INTERDISCIPLINARY_SCIENCES)} items")

    print("\n" + "=" * 70)
    print("SAMPLE SEARCH QUERIES")
    print("=" * 70)

    queries = pools.generate_search_queries(15)
    for q in queries[:15]:
        print(f"  - {q}")

    print("\n" + "=" * 70)
    print("STATISTICS")
    print("=" * 70)
    print(f"Total disciplines: {len(pools.get_all_disciplines())}")
    print(f"Total entities: {len(pools.get_all_entities())}")
    print(f"Total categories: {len(pools.get_all_categories())}")
    print(f"Famous scientists: {sum(len(v) if isinstance(v, list) else 0 for v in pools.FAMOUS_SCIENTISTS.values())}")
