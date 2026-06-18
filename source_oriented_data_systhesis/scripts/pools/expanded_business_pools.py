#!/usr/bin/env python3
"""
Expanded Business Data Pools

This module provides expanded, diverse pools for business data generation,
covering various industries, company types, business concepts, and regions.

Coverage:
- All major industries and sectors
- Company types (startup, corporate, family-owned, etc.)
- Business functions (finance, marketing, operations, etc.)
- Global regions and markets
- Business concepts and terminology
- Time periods (business history)
"""

from typing import List, Dict
import random


# ============================================================================
# EXPANDED BUSINESS POOLS
# ============================================================================

class ExpandedBusinessPools:
    """
    大规模商业数据池 - 覆盖全球、全行业、多种商业形态
    Designed to minimize bias and maximize diversity
    """

    # ========== INDUSTRIES AND SECTORS ==========

    INDUSTRIES = {
        "technology": [
            "Software", "Hardware", "Semiconductors", "Cloud Computing", "Cybersecurity",
            "Artificial Intelligence", "Machine Learning", "Data Analytics", "SaaS",
            "Mobile Apps", "E-commerce", "FinTech", "EdTech", "HealthTech", "CleanTech",
            "Blockchain", "Cryptocurrency", "IoT", "5G", "Quantum Computing"
        ],
        "finance": [
            "Banking", "Investment Banking", "Asset Management", "Insurance", "Venture Capital",
            "Private Equity", "Hedge Funds", "Accounting", "Financial Consulting",
            "Wealth Management", "Corporate Finance", "Mergers & Acquisitions",
            "Risk Management", "Compliance", "Financial Technology"
        ],
        "healthcare": [
            "Pharmaceuticals", "Biotechnology", "Medical Devices", "Healthcare Services",
            "Hospitals", "Telemedicine", "Health Insurance", "Medical Research",
            "Clinical Trials", "Diagnostics", "Digital Health", "Genomics", "Medical AI"
        ],
        "consumer": [
            "Retail", "E-commerce", "Consumer Electronics", "Apparel & Fashion",
            "Food & Beverage", "Luxury Goods", "Consumer Services", "Entertainment",
            "Media & Publishing", "Gaming", "Sports", "Travel & Tourism", "Hospitality"
        ],
        "industrial": [
            "Manufacturing", "Automotive", "Aerospace & Defense", "Chemicals",
            "Construction", "Engineering", "Energy", "Utilities", "Metals & Mining",
            "Materials", "Logistics", "Transportation", "Shipping"
        ],
        "real_estate": [
            "Commercial Real Estate", "Residential Real Estate", "Real Estate Investment Trusts",
            "Property Management", "Real Estate Development", "Real Estate Services"
        ],
        "telecommunications": [
            "Wireless", "Broadband", "Cable", "Satellite", "Telecommunications Equipment",
            "Network Infrastructure", "Communication Services"
        ],
        "energy": [
            "Oil & Gas", "Renewable Energy", "Solar", "Wind", "Hydroelectric",
            "Nuclear Energy", "Energy Storage", "Electric Grid", "Energy Trading"
        ]
    }

    # ========== COMPANY TYPES ==========

    COMPANY_TYPES = {
        "by_size": [
            "Startup", "Small Business", "Medium-sized Enterprise", "Large Corporation",
            "Multinational Corporation", "Conglomerate", "Fortune 500", "SME", "Microenterprise"
        ],
        "by_structure": [
            "Corporation", "LLC", "Partnership", "Sole Proprietorship", "Joint Venture",
            "Holding Company", "Subsidiary", "Nonprofit", "Cooperative", "B Corp"
        ],
        "by_stage": [
            "Pre-seed Startup", "Seed Stage", "Series A", "Series B", "Series C+",
            "IPO", "Public Company", "Private Company", "Acquired", "Bankrupt"
        ],
        "by_ownership": [
            "Family-owned", "Founder-led", "Employee-owned", "ESOP", "State-owned",
            "Private Equity-owned", "Publicly Traded", "Wholly Owned Subsidiary"
        ]
    }

    # ========== BUSINESS FUNCTIONS ==========

    BUSINESS_FUNCTIONS = {
        "leadership": [
            "CEO", "CFO", "COO", "CTO", "CMO", "CHRO", "CLO", "CISO", "Board of Directors",
            "Executive Team", "Management Committee", "Shareholders"
        ],
        "finance": [
            "Financial Planning", "Budgeting", "Financial Reporting", "Accounting",
            "Treasury", "Tax", "Internal Audit", "Investor Relations", "M&A",
            "Financial Analysis", "Cost Management", "Revenue Recognition"
        ],
        "operations": [
            "Supply Chain", "Manufacturing", "Quality Control", "Logistics",
            "Distribution", "Operations Management", "Process Improvement",
            "Lean Manufacturing", "Six Sigma", "Vendor Management"
        ],
        "marketing": [
            "Brand Management", "Digital Marketing", "Content Marketing", "Social Media",
            "Public Relations", "Market Research", "Customer Acquisition", "Growth Marketing",
            "Product Marketing", "Marketing Analytics", "Advertising"
        ],
        "sales": [
            "Direct Sales", "Channel Sales", "Enterprise Sales", "SMB Sales",
            "Sales Operations", "Sales Enablement", "Business Development",
            "Partnership Management", "Customer Success"
        ],
        "product": [
            "Product Management", "Product Design", "User Experience", "Research & Development",
            "Innovation", "Product Strategy", "Roadmap Planning", "Feature Development"
        ],
        "technology": [
            "Software Engineering", "IT Infrastructure", "Data Engineering",
            "DevOps", "Cybersecurity", "Cloud Architecture", "AI/ML", "Technical Support"
        ],
        "hr": [
            "Recruiting", "Talent Acquisition", "Compensation & Benefits", "Learning & Development",
            "Organizational Development", "Employee Relations", "Diversity & Inclusion",
            "Performance Management", "HR Operations"
        ],
        "legal": [
            "Corporate Law", "Contract Management", "Compliance", "Intellectual Property",
            "Regulatory Affairs", "Litigation", "M&A Legal", "Employment Law"
        ]
    }

    # ========== BUSINESS CONCEPTS ==========

    BUSINESS_CONCEPTS = {
        "strategy": [
            "Competitive Advantage", "Market Positioning", "Differentiation Strategy",
            "Cost Leadership", "Blue Ocean Strategy", "Disruptive Innovation",
            "Growth Strategy", "Diversification", "Vertical Integration",
            "Horizontal Integration", "Strategic Alliances", "Joint Ventures",
            "Mergers & Acquisitions", "Divestiture", "Turnaround Strategy"
        ],
        "finance": [
            "Revenue", "Profit Margin", "EBITDA", "Cash Flow", "Working Capital",
            "Capital Expenditure", "Return on Investment", "Return on Equity",
            "Debt to Equity Ratio", "Market Capitalization", "Valuation",
            "Initial Public Offering", "Secondary Offering", "Stock Buyback",
            "Dividend Policy", "Capital Structure"
        ],
        "marketing": [
            "Market Segmentation", "Target Market", "Customer Persona",
            "Value Proposition", "Brand Equity", "Customer Acquisition Cost",
            "Customer Lifetime Value", "Conversion Rate", "Churn Rate",
            "Net Promoter Score", "Brand Awareness", "Market Penetration",
            "Go-to-Market Strategy", "Sales Funnel", "Lead Generation"
        ],
        "operations": [
            "Supply Chain Optimization", "Inventory Management", "Just-in-Time",
            "Lean Operations", "Quality Management", "Continuous Improvement",
            "Operational Efficiency", "Cost Reduction", "Process Automation",
            "Vendor Management", "Outsourcing", "Offshoring", "Nearshoring"
        ],
        "management": [
            "Corporate Governance", "Leadership Development", "Change Management",
            "Organizational Culture", "Performance Management", "Strategic Planning",
            "Executive Compensation", "Board Governance", "Stakeholder Management",
            "Crisis Management", "Business Continuity", "Risk Management"
        ]
    }

    # ========== BUSINESS TERMS ==========

    BUSINESS_TERMS = {
        "financial": [
            "Revenue", "Profit", "Loss", "Assets", "Liabilities", "Equity",
            "Cash Flow", "EBITDA", "Gross Margin", "Net Income", "Depreciation",
            "Amortization", "Capital Expenditure", "Operating Expenses", "COGS",
            "Balance Sheet", "Income Statement", "Cash Flow Statement"
        ],
        "investment": [
            "Venture Capital", "Angel Investment", "Private Equity", "Hedge Fund",
            "Mutual Fund", "ETF", "Index Fund", "Portfolio Management", "Asset Allocation",
            "Diversification", "Risk-Return Tradeoff", "Alpha", "Beta", "Sharpe Ratio",
            "Leveraged Buyout", "Management Buyout", "Mezzanine Financing"
        ],
        "corporate": [
            "Bylaws", "Articles of Incorporation", "Shareholder Agreement",
            "Board Meeting", "Annual General Meeting", "Proxy Statement",
            "Executive Compensation", "Stock Options", "Restricted Stock",
            "Golden Parachute", "Poison Pill", "White Knight", "Tender Offer"
        ],
        "accounting": [
            "GAAP", "IFRS", "Accrual Accounting", "Cash Basis", "Audit",
            "Internal Controls", "Sarbanes-Oxley", "Forensic Accounting",
            "Tax Accounting", "Managerial Accounting", "Cost Accounting",
            "Financial Ratios", "Financial Analysis"
        ]
    }

    # ========== REGIONS AND MARKETS ==========

    BUSINESS_REGIONS = {
        "north_america": [
            "United States", "Canada", "Mexico", "Silicon Valley", "New York",
            "Boston", "Austin", "Toronto", "Vancouver", "Monterrey"
        ],
        "europe": [
            "United Kingdom", "Germany", "France", "Netherlands", "Sweden",
            "Switzerland", "Ireland", "Spain", "Italy", "Poland",
            "London", "Berlin", "Paris", "Amsterdam", "Stockholm"
        ],
        "asia": [
            "China", "Japan", "South Korea", "India", "Singapore",
            "Hong Kong", "Taiwan", "Vietnam", "Indonesia", "Thailand",
            "Beijing", "Shanghai", "Tokyo", "Seoul", "Bangalore", "Singapore"
        ],
        "latam": [
            "Brazil", "Argentina", "Chile", "Colombia", "Peru",
            "Mexico", "São Paulo", "Buenos Aires", "Santiago", "Mexico City"
        ],
        "middle_east_africa": [
            "UAE", "Saudi Arabia", "Israel", "South Africa", "Nigeria",
            "Kenya", "Egypt", "Dubai", "Riyadh", "Tel Aviv", "Lagos"
        ],
        "oceania": [
            "Australia", "New Zealand", "Sydney", "Melbourne", "Auckland"
        ]
    }

    # ========== COMPANY STAGES (by funding) ==========

    FUNDING_STAGES = [
        "Pre-seed", "Seed", "Series A", "Series B", "Series C", "Series D+",
        "Pre-IPO", "IPO", "Post-IPO", "Public", "Acquired", "IPO Withdrawn"
    ]

    # ========== BUSINESS EVENTS ==========

    BUSINESS_EVENTS = {
        "funding": [
            "Seed Round", "Series A Financing", "Series B Financing", "Series C Financing",
            "IPO", "Direct Listing", "SPAC Merger", "Private Placement",
            "Venture Capital Investment", "Angel Investment", "Crowdfunding",
            "Debt Financing", "Convertible Note", "SAFE Agreement"
        ],
        "corporate": [
            "Merger", "Acquisition", "Divestiture", "Spin-off", "Split-off",
            "Joint Venture", "Strategic Partnership", "Asset Sale", "Stock Buyback",
            "Restructuring", "Bankruptcy", "Liquidation", "Delisting"
        ],
        "leadership": [
            "CEO Appointment", "CEO Departure", "Executive Hiring",
            "Board Appointment", "Board Resignation", "Management Shuffle",
            "Founder Exit", "Leadership Transition", "Activist Investor Campaign"
        ],
        "product": [
            "Product Launch", "Product Recall", "New Feature Release",
            "Platform Expansion", "Market Expansion", "International Launch",
            "Strategic Pivot", "Business Model Change", "Acquisition Integration"
        ]
    }

    # ========== FAMOUS COMPANIES ==========

    FAMOUS_COMPANIES = {
        "technology": [
            "Apple", "Microsoft", "Google", "Amazon", "Meta", "Tesla", "NVIDIA",
            "Intel", "AMD", "Samsung", "TSMC", "Adobe", "Salesforce", "Oracle",
            "SAP", "Zoom", "Shopify", "Square", "Stripe", "Palantir", "Snowflake"
        ],
        "finance": [
            "JPMorgan Chase", "Bank of America", "Wells Fargo", "Citigroup",
            "Goldman Sachs", "Morgan Stanley", "BlackRock", "Fidelity",
            "Vanguard", "Charles Schwab", "PayPal", "Visa", "Mastercard"
        ],
        "healthcare": [
            "Johnson & Johnson", "Pfizer", "Moderna", "UnitedHealth",
            "Abbott Laboratories", "Merck", "AbbVie", "Thermo Fisher",
            "Medtronic", "Illumina"
        ],
        "consumer": [
            "Coca-Cola", "Pepsi", "Nike", "Starbucks", "McDonald's",
            "Walmart", "Target", "Costco", "Home Depot", "Nike", "Lululemon"
        ],
        "industrial": [
            "Boeing", "Airbus", "Lockheed Martin", "General Electric",
            "Caterpillar", "3M", "Honeywell", "Union Pacific", "UPS", "FedEx"
        ],
        "energy": [
            "ExxonMobil", "Chevron", "Shell", "BP", "TotalEnergies",
            "NextEra Energy", "First Solar", "Enphase", "Tesla Energy"
        ],
        "chinese_tech": [
            "Alibaba", "Tencent", "ByteDance", "JD.com", "Meituan",
            "Pinduoduo", "Xiaomi", "Huawei", "DiDi", "Baidu"
        ],
        "startups_unicorns": [
            "SpaceX", "Stripe", "ByteDance", "Discord", "Epic Games",
            "Instacart", "Databricks", "Ripple", "Canva", "Notion"
        ]
    }

    # ========== BUSINESS LEADERS ==========

    BUSINESS_LEADERS = {
        "tech_ceos": [
            "Elon Musk", "Tim Cook", "Satya Nadella", "Sundar Pichai",
            "Mark Zuckerberg", "Jensen Huang", "Andy Jassy", "Daniel Ek"
        ],
        "investors": [
            "Warren Buffett", "Charlie Munger", "Ray Dalio", "Ken Griffin",
            "Jim Simons", "Peter Thiel", "Marc Andreessen", "Ben Horowitz",
            "Vinod Khosla", "Reid Hoffman"
        ],
        "founders": [
            "Jeff Bezos", "Bill Gates", "Steve Jobs", "Larry Page", "Sergey Brin",
            "Mark Zuckerberg", "Jack Ma", "Pony Ma", "Zhang Yiming"
        ],
        "wall_street": [
            "Jamie Dimon", "David Solomon", "James Gorman", "Jane Fraser",
            "Brian Moynihan", "Brian Roberts"
        ]
    }

    # ========== BUSINESS METRICS ==========

    BUSINESS_METRICS = {
        "financial": [
            "Revenue Growth", "Profit Margin", "Gross Margin", "Operating Margin",
            "EBITDA Margin", "Return on Assets", "Return on Equity", "Return on Invested Capital",
            "Free Cash Flow", "Operating Cash Flow", "Capital Expenditure"
        ],
        "valuation": [
            "Market Cap", "Enterprise Value", "P/E Ratio", "PEG Ratio",
            "Price-to-Sales", "Price-to-Book", "EV/EBITDA", "EV/Sales",
            "Discounted Cash Flow", "Comparable Company Analysis"
        ],
        "operational": [
            "Customer Acquisition Cost", "Customer Lifetime Value", "Churn Rate",
            "Monthly Active Users", "Daily Active Users", "ARPU", "NPS",
            "Conversion Rate", "Retention Rate", "Gross Merchandise Value"
        ],
        "efficiency": [
            "Inventory Turnover", "Days Sales Outstanding", "Days Payable Outstanding",
            "Cash Conversion Cycle", "Asset Turnover", "Employee Productivity"
        ]
    }

    # ========== WIKIPEDIA BUSINESS CATEGORIES ==========

    WIKIPEDIA_CATEGORIES = [
        "Category:Business",
        "Category:Companies",
        "Category:Companies by country",
        "Category:Companies by industry",
        "Category:Companies established in",
        "Category:Companies disestablished in",
        "Category:Businesspeople",
        "Category:Chief executive officers",
        "Category:American businesspeople",
        "Category:Business organizations",
        "Category:Business law",
        "Category:Business ethics",
        "Category:Business software",
        "Category:Business intelligence",
        "Category:Supply chain management",
        "Category:Management",
        "Category:Marketing",
        "Category:Finance",
        "Category:Accounting",
        "Category:Investment",
        "Category:Financial markets",
        "Category:Stock exchanges",
        "Category:Initial public offerings",
        "Category:Mergers and acquisitions",
        "Category:Corporate finance",
        "Category:Venture capital",
        "Category:Private equity",
        "Category:Hedge funds",
        "Category:Business theorists",
        "Category:Business schools",
        "Category:Harvard Business School",
        "Category:Business books",
        "Category:Economics",
        "Category:Economists",
        "Category:Business journals",
        "Category:Management consulting",
        "Category:Business services"
    ]

    # ========== SEARCH KEYWORD COMPONENTS ==========

    KEYWORD_COMPONENTS = {
        "industries": [
            "Technology", "Software", "SaaS", "FinTech", "HealthTech", "EdTech",
            "E-commerce", "Retail", "Manufacturing", "Healthcare", "Finance",
            "Banking", "Insurance", "Real Estate", "Energy", "Telecommunications",
            "Media", "Entertainment", "Gaming", "Biotechnology", "Pharmaceuticals"
        ],
        "topics": [
            "Revenue", "Profit", "Growth", "Strategy", "Marketing", "Sales",
            "Operations", "Finance", "Leadership", "Innovation", "Digital Transformation",
            "Mergers and Acquisitions", "IPO", "Startup", "Venture Capital",
            "Private Equity", "Corporate Governance", "Business Model", "Disruption"
        ],
        "regions": [
            "Global", "United States", "China", "Europe", "Asia", "Latin America",
            "Silicon Valley", "New York", "London", "Singapore", "Tokyo", "Berlin"
        ],
        "timeframes": [
            "2023", "2022", "2021", "2020", "2019", "Q1 2023", "Q4 2022",
            "FY 2022", "FY 2023", "H1 2023", "post-pandemic", "COVID-19 impact"
        ],
        "modifiers": [
            "trends", "outlook", "forecast", "analysis", "report", "statistics",
            "market size", "growth rate", "key players", "competitive landscape",
            "industry report", "market analysis", "case study", "best practices"
        ]
    }

    # ========== NEWS TOPICS ==========

    NEWS_TOPICS = [
        "Earnings Report", "Mergers and Acquisitions", "IPO", "Stock Market",
        "Federal Reserve", "Interest Rates", "Inflation", "Recession",
        "Corporate Layoffs", "Tech Layoffs", "AI Regulation", "Antitrust",
        "Cryptocurrency", "Bitcoin", "Blockchain", "ESG", "Climate Finance",
        "Supply Chain Crisis", "Chip Shortage", "Energy Crisis", "Oil Prices",
        "Housing Market", "Commercial Real Estate", "Banking Crisis",
        "Debt Ceiling", "Fiscal Policy", "Monetary Policy", "Trade War",
        "Geopolitics", "Sanctions", "Global Economy", "Emerging Markets"
    ]

    # ========== FINANCIAL DOCUMENTS ==========

    FINANCIAL_DOCUMENTS = [
        "10-K Annual Report", "10-Q Quarterly Report", "8-K Current Report",
        "Proxy Statement", "Annual Report to Shareholders", "Earnings Call Transcript",
        "Investor Presentation", "ESG Report", "Sustainability Report",
        "Form 4 Insider Trading", "Form 13F Institutional Holdings",
        "Form S-1 Registration Statement", "Prospectus", "Merger Agreement"
    ]

    # ========== HELPER METHODS ==========

    def get_all_industries(self) -> List[str]:
        """Get all industries as flat list"""
        all_industries = []
        for industry_list in self.INDUSTRIES.values():
            all_industries.extend(industry_list)
        return all_industries

    def get_all_company_types(self) -> List[str]:
        """Get all company types as flat list"""
        all_types = []
        for type_list in self.COMPANY_TYPES.values():
            all_types.extend(type_list)
        return all_types

    def get_all_regions(self) -> List[str]:
        """Get all regions as flat list"""
        all_regions = []
        for region_list in self.BUSINESS_REGIONS.values():
            all_regions.extend(region_list)
        return all_regions

    def get_all_business_functions(self) -> List[str]:
        """Get all business functions as flat list"""
        all_functions = []
        for func_list in self.BUSINESS_FUNCTIONS.values():
            all_functions.extend(func_list)
        return all_functions

    def get_all_categories(self) -> List[str]:
        """Get all Wikipedia categories"""
        return self.WIKIPEDIA_CATEGORIES

    def get_random_company(self) -> str:
        """Get a random famous company"""
        all_companies = []
        for company_list in self.FAMOUS_COMPANIES.values():
            all_companies.extend(company_list)
        return random.choice(all_companies)

    def get_random_leader(self) -> str:
        """Get a random business leader"""
        all_leaders = []
        for leader_list in self.BUSINESS_LEADERS.values():
            all_leaders.extend(leader_list)
        return random.choice(all_leaders)

    def get_all_companies(self) -> Dict[str, List[str]]:
        """Get all famous companies by category"""
        return self.FAMOUS_COMPANIES

    def get_all_leaders(self) -> Dict[str, List[str]]:
        """Get all business leaders by category"""
        return self.BUSINESS_LEADERS

    def generate_search_queries(self, num_queries: int = 50) -> List[str]:
        """
        Generate diverse business search queries

        Returns a list of search query combinations
        """
        queries = []

        # Generate different query patterns
        for _ in range(num_queries):
            pattern = random.choice([
                # Industry + Topic
                lambda: f"{random.choice(self.get_all_industries())} {random.choice(self.KEYWORD_COMPONENTS['topics'])}",
                # Industry + Region
                lambda: f"{random.choice(self.get_all_industries())} in {random.choice(self.get_all_regions())}",
                # Company + Topic
                lambda: f"{self.get_random_company()} {random.choice(self.KEYWORD_COMPONENTS['topics'])}",
                # Leader + Topic
                lambda: f"{self.get_random_leader()} {random.choice(self.KEYWORD_COMPONENTS['topics'])}",
                # Topic + Modifier
                lambda: f"{random.choice(self.KEYWORD_COMPONENTS['topics'])} {random.choice(self.KEYWORD_COMPONENTS['modifiers'])}",
                # Industry + Modifier
                lambda: f"{random.choice(self.get_all_industries())} {random.choice(self.KEYWORD_COMPONENTS['modifiers'])}",
                # News topic
                lambda: random.choice(self.NEWS_TOPICS),
                # Financial document
                lambda: f"{self.get_random_company()} {random.choice(self.FINANCIAL_DOCUMENTS)}",
                # Industry + Region + Modifier
                lambda: f"{random.choice(self.get_all_industries())} {random.choice(self.get_all_regions())} {random.choice(self.KEYWORD_COMPONENTS['modifiers'])}",
                # Company + Event
                lambda: f"{self.get_random_company()} {random.choice(list(self.BUSINESS_EVENTS.keys()))} {random.choice(self.BUSINESS_EVENTS[random.choice(list(self.BUSINESS_EVENTS.keys()))])}",
            ])

            try:
                query = pattern()
                queries.append(query)
            except:
                continue

        return list(set(queries))  # Remove duplicates

    def get_business_concept_combinations(self) -> List[str]:
        """Get business concept combinations for exploration"""
        concepts = []

        # Strategy concepts
        for concept in self.BUSINESS_CONCEPTS['strategy']:
            concepts.append(concept)

        # Finance concepts
        for concept in self.BUSINESS_CONCEPTS['finance']:
            concepts.append(f"{concept} analysis")

        # Marketing concepts
        for concept in self.BUSINESS_CONCEPTS['marketing']:
            concepts.append(f"{concept} strategy")

        return concepts


# ============================================================================
# DEMO / TESTING
# ============================================================================

if __name__ == "__main__":
    pools = ExpandedBusinessPools()

    print("=" * 70)
    print("EXPANDED BUSINESS POOLS")
    print("=" * 70)

    print(f"\nIndustries: {len(pools.get_all_industries())}")
    print(f"Company Types: {len(pools.get_all_company_types())}")
    print(f"Regions: {len(pools.get_all_regions())}")
    print(f"Business Functions: {len(pools.get_all_business_functions())}")
    print(f"Wikipedia Categories: {len(pools.get_all_categories())}")

    print("\nSample Search Queries:")
    queries = pools.generate_search_queries(10)
    for q in queries[:10]:
        print(f"  - {q}")

    print("\nSample Companies:")
    for category, companies in pools.FAMOUS_COMPANIES.items():
        print(f"  {category}: {', '.join(companies[:3])}")
