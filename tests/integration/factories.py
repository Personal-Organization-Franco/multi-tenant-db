"""
Integration test data factories for realistic fintech scenarios.

Provides factories for creating comprehensive test data that mirrors
real-world fintech and banking scenarios.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import factory
from faker import Faker

from src.multi_tenant_db.models.tenant import Tenant, TenantType
from src.multi_tenant_db.schemas.tenant import TenantCreate, TenantResponse

fake = Faker()

# Global financial institutions for realistic test data
GLOBAL_BANKS = [
    "HSBC Holdings plc",
    "JP Morgan Chase & Co",
    "Bank of America Corporation", 
    "Wells Fargo & Company",
    "Goldman Sachs Group Inc",
    "Morgan Stanley",
    "Citigroup Inc",
    "Deutsche Bank AG",
    "UBS Group AG",
    "Credit Suisse Group AG",
    "Barclays plc",
    "Royal Bank of Canada",
    "Toronto-Dominion Bank",
    "Bank of Nova Scotia",
    "BNP Paribas",
    "Société Générale",
    "ING Group",
    "Santander Group",
    "BBVA",
    "UniCredit Group",
    "Standard Chartered plc"
]

# Regional and subsidiary locations
FINANCIAL_HUBS = [
    "London", "New York", "Hong Kong", "Singapore", "Tokyo", "Frankfurt", 
    "Zurich", "Geneva", "Dubai", "Sydney", "Toronto", "Toronto", "Paris",
    "Amsterdam", "Madrid", "Barcelona", "Milan", "Dublin", "Luxembourg",
    "Stockholm", "Copenhagen", "Oslo", "Helsinki", "Warsaw", "Prague",
    "Vienna", "Budapest", "Bucharest", "Sofia", "Istanbul", "Tel Aviv",
    "Mumbai", "Delhi", "Bangalore", "Shanghai", "Beijing", "Seoul",
    "Taipei", "Jakarta", "Bangkok", "Kuala Lumpur", "Manila", "Ho Chi Minh City",
    "São Paulo", "Rio de Janeiro", "Buenos Aires", "Santiago", "Lima",
    "Bogotá", "Mexico City", "Monterrey", "Johannesburg", "Cape Town",
    "Cairo", "Casablanca", "Lagos", "Nairobi", "Accra"
]

# Business units in financial institutions
BUSINESS_UNITS = [
    "retail_banking", "commercial_banking", "investment_banking", 
    "private_banking", "wealth_management", "asset_management",
    "corporate_banking", "institutional_banking", "treasury",
    "trading", "sales", "research", "risk_management", "compliance",
    "operations", "technology", "human_resources", "legal",
    "audit", "finance", "strategy", "marketing", "customer_service"
]

# Currency codes for international operations
CURRENCIES = [
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "SEK", "NOK",
    "DKK", "PLN", "CZK", "HUF", "RON", "BGN", "HRK", "RSD", "MKD", "BAM",
    "TRY", "RUB", "UAH", "BYN", "KZT", "UZS", "KGS", "TJS", "TMT", "AZN",
    "GEL", "AMD", "ILS", "JOD", "SAR", "AED", "QAR", "KWD", "BHD", "OMR",
    "CNY", "HKD", "TWD", "KRW", "SGD", "MYR", "THB", "PHP", "IDR", "VND",
    "INR", "PKR", "BDT", "LKR", "NPR", "BTN", "MVR", "AFN", "MMK", "KHR"
]

# Regulatory frameworks
REGULATORY_FRAMEWORKS = [
    "Basel_III", "Basel_IV", "CRD_V", "CRR_II", "MiFID_II", "EMIR", "SFTR",
    "Dodd_Frank", "Volcker_Rule", "CCAR", "DFAST", "LCR", "NSFR", "TLAC",
    "FRTB", "SA_CCR", "IFRS_9", "CECL", "GDPR", "PCI_DSS", "SOX", "FCPA"
]


class GlobalBankFactory(factory.Factory):
    """Factory for creating realistic global bank parent entities."""
    
    class Meta:
        model = Tenant
    
    tenant_id = factory.LazyFunction(uuid4)
    name = factory.LazyFunction(lambda: fake.random_element(GLOBAL_BANKS))
    parent_tenant_id = None
    tenant_type = TenantType.PARENT
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    
    @factory.lazy_attribute
    def tenant_metadata(self):
        return {
            "country": fake.random_element(["United States", "United Kingdom", "Switzerland", "Germany", "Canada"]),
            "headquarters": fake.random_element(["New York", "London", "Zurich", "Frankfurt", "Toronto"]),
            "business_type": "multinational_bank",
            "founded_year": fake.random_int(min=1800, max=1980),
            "employee_count": fake.random_int(min=50000, max=300000),
            "regulatory_licenses": fake.random_elements(
                elements=["banking_license", "securities_license", "insurance_license", 
                         "investment_advisory", "custody_services", "clearing_services"],
                length=fake.random_int(min=3, max=6),
                unique=True
            ),
            "primary_currency": fake.random_element(["USD", "EUR", "GBP", "CHF", "CAD"]),
            "market_cap_billion_usd": round(fake.random.uniform(20.0, 500.0), 2),
            "total_assets_billion_usd": round(fake.random.uniform(500.0, 4000.0), 2),
            "tier1_capital_ratio": round(fake.random.uniform(12.0, 18.0), 2),
            "total_capital_ratio": round(fake.random.uniform(15.0, 22.0), 2),
            "credit_rating": {
                "moodys": fake.random_element(["Aaa", "Aa1", "Aa2", "Aa3", "A1", "A2", "A3"]),
                "sp": fake.random_element(["AAA", "AA+", "AA", "AA-", "A+", "A", "A-"]),
                "fitch": fake.random_element(["AAA", "AA+", "AA", "AA-", "A+", "A", "A-"])
            },
            "regulatory_status": "fully_authorized",
            "systemic_importance": fake.random_element(["G-SIB", "D-SIB", "regional_bank"]),
            "business_segments": fake.random_elements(
                elements=["retail_banking", "commercial_banking", "investment_banking",
                         "wealth_management", "asset_management", "trading"],
                length=fake.random_int(min=3, max=6),
                unique=True
            )
        }


class RegionalSubsidiaryFactory(factory.Factory):
    """Factory for creating realistic regional subsidiary banks."""
    
    class Meta:
        model = Tenant
    
    tenant_id = factory.LazyFunction(uuid4)
    parent_tenant_id = factory.LazyFunction(uuid4)
    tenant_type = TenantType.SUBSIDIARY
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    
    @factory.lazy_attribute
    def name(self):
        parent_bank = fake.random_element(GLOBAL_BANKS).split()[0]  # Get first word
        location = fake.random_element(FINANCIAL_HUBS)
        return f"{parent_bank} Bank {location}"
    
    @factory.lazy_attribute
    def tenant_metadata(self):
        local_currency = fake.random_element(CURRENCIES)
        return {
            "country": fake.country(),
            "region": fake.random_element(["Asia Pacific", "Europe", "North America", 
                                          "Latin America", "Middle East", "Africa"]),
            "business_unit": fake.random_element(BUSINESS_UNITS),
            "local_currency": local_currency,
            "employee_count": fake.random_int(min=500, max=25000),
            "local_licenses": fake.random_elements(
                elements=["local_banking_license", "securities_license", "insurance_license",
                         "money_services_license", "foreign_exchange_license"],
                length=fake.random_int(min=2, max=5),
                unique=True
            ),
            "established_year": fake.random_int(min=1950, max=2020),
            "branches": fake.random_int(min=5, max=200),
            "atm_count": fake.random_int(min=20, max=1000),
            "customer_base": fake.random_int(min=10000, max=2000000),
            "local_assets_millions": round(fake.random.uniform(1000.0, 50000.0), 2),
            "regulatory_capital_millions": round(fake.random.uniform(100.0, 5000.0), 2),
            "loan_portfolio_millions": round(fake.random.uniform(500.0, 30000.0), 2),
            "deposit_base_millions": round(fake.random.uniform(800.0, 40000.0), 2),
            "market_share_percentage": round(fake.random.uniform(1.0, 25.0), 2),
            "specialization": fake.random_element([
                "retail_banking", "private_banking", "commercial_banking",
                "investment_banking", "wealth_management", "corporate_banking"
            ]),
            "regulatory_framework": fake.random_element(REGULATORY_FRAMEWORKS),
            "compliance_status": {
                "capital_adequacy": "COMPLIANT",
                "liquidity_requirements": "COMPLIANT",
                "operational_risk": "COMPLIANT",
                "market_risk": "COMPLIANT",
                "credit_risk": "COMPLIANT"
            },
            "performance_metrics": {
                "return_on_assets": round(fake.random.uniform(0.5, 2.5), 2),
                "return_on_equity": round(fake.random.uniform(8.0, 20.0), 2),
                "cost_income_ratio": round(fake.random.uniform(45.0, 75.0), 2),
                "net_interest_margin": round(fake.random.uniform(1.5, 4.5), 2)
            }
        }


class InvestmentBankFactory(factory.Factory):
    """Factory for creating investment banking subsidiaries."""
    
    class Meta:
        model = Tenant
    
    tenant_id = factory.LazyFunction(uuid4)
    parent_tenant_id = factory.LazyFunction(uuid4)
    tenant_type = TenantType.SUBSIDIARY
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    
    @factory.lazy_attribute
    def name(self):
        parent_bank = fake.random_element(GLOBAL_BANKS).split()[0]
        return f"{parent_bank} Investment Bank"
    
    @factory.lazy_attribute
    def tenant_metadata(self):
        return {
            "country": fake.random_element(["United States", "United Kingdom", "Germany", "Hong Kong", "Singapore"]),
            "business_unit": "investment_banking",
            "primary_services": fake.random_elements(
                elements=["mergers_acquisitions", "equity_capital_markets", "debt_capital_markets",
                         "structured_finance", "derivatives", "prime_brokerage", "research"],
                length=fake.random_int(min=3, max=7),
                unique=True
            ),
            "employee_count": fake.random_int(min=1000, max=15000),
            "regulatory_licenses": [
                "securities_license", "investment_advisory", "broker_dealer",
                "swap_dealer", "derivatives_license"
            ],
            "trading_revenues_millions_usd": round(fake.random.uniform(500.0, 8000.0), 2),
            "advisory_fees_millions_usd": round(fake.random.uniform(200.0, 3000.0), 2),
            "underwriting_volumes_billions_usd": round(fake.random.uniform(50.0, 500.0), 2),
            "assets_under_custody_billions_usd": round(fake.random.uniform(100.0, 2000.0), 2),
            "var_millions_usd": round(fake.random.uniform(10.0, 150.0), 2),  # Value at Risk
            "stress_test_capital_impact_millions": round(fake.random.uniform(500.0, 5000.0), 2),
            "regulatory_framework": fake.random_element([
                "MiFID_II", "Dodd_Frank", "EMIR", "Basel_III_trading_book"
            ]),
            "risk_metrics": {
                "market_risk_capital_millions": round(fake.random.uniform(200.0, 2000.0), 2),
                "operational_risk_capital_millions": round(fake.random.uniform(100.0, 1000.0), 2),
                "credit_risk_capital_millions": round(fake.random.uniform(50.0, 800.0), 2),
                "leverage_ratio": round(fake.random.uniform(4.0, 8.0), 2)
            },
            "market_making": {
                "currencies_traded": fake.random_elements(elements=CURRENCIES[:20], length=10, unique=True),
                "asset_classes": ["equity", "fixed_income", "commodities", "fx", "derivatives"],
                "daily_trading_volume_millions": round(fake.random.uniform(1000.0, 50000.0), 2)
            }
        }


class PrivateBankFactory(factory.Factory):
    """Factory for creating private banking subsidiaries."""
    
    class Meta:
        model = Tenant
    
    tenant_id = factory.LazyFunction(uuid4)
    parent_tenant_id = factory.LazyFunction(uuid4)
    tenant_type = TenantType.SUBSIDIARY
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    
    @factory.lazy_attribute
    def name(self):
        parent_bank = fake.random_element(GLOBAL_BANKS).split()[0]
        location = fake.random_element(["Switzerland", "Monaco", "Luxembourg", "Singapore", "Hong Kong"])
        return f"{parent_bank} Private Bank {location}"
    
    @factory.lazy_attribute
    def tenant_metadata(self):
        return {
            "country": fake.random_element(["Switzerland", "Luxembourg", "Singapore", "Hong Kong", "Monaco"]),
            "business_unit": "private_banking",
            "client_segments": [
                "ultra_high_net_worth", "high_net_worth", "affluent", "family_offices"
            ],
            "minimum_relationship_usd_millions": round(fake.random.uniform(1.0, 25.0), 1),
            "employee_count": fake.random_int(min=200, max=3000),
            "client_count": fake.random_int(min=500, max=15000),
            "assets_under_management_billions_usd": round(fake.random.uniform(50.0, 800.0), 2),
            "average_client_portfolio_millions_usd": round(fake.random.uniform(5.0, 100.0), 2),
            "services": [
                "investment_advisory", "portfolio_management", "estate_planning",
                "tax_advisory", "philanthropic_services", "family_office_services",
                "structured_products", "alternative_investments", "art_financing"
            ],
            "geographic_coverage": fake.random_elements(
                elements=["Europe", "Asia_Pacific", "North_America", "Latin_America", "Middle_East"],
                length=fake.random_int(min=2, max=5),
                unique=True
            ),
            "regulatory_licenses": [
                "investment_advisory", "portfolio_management", "insurance_mediation",
                "custody_services", "financial_planning"
            ],
            "performance_metrics": {
                "net_new_money_billions_usd": round(fake.random.uniform(5.0, 50.0), 2),
                "management_fees_bp": fake.random_int(min=50, max=200),  # Basis points
                "client_retention_rate": round(fake.random.uniform(92.0, 98.0), 1),
                "advisor_productivity_millions": round(fake.random.uniform(80.0, 200.0), 2)
            },
            "investment_capabilities": {
                "asset_classes": [
                    "equities", "fixed_income", "alternatives", "commodities",
                    "real_estate", "private_equity", "hedge_funds", "structured_products"
                ],
                "currencies_managed": fake.random_elements(elements=CURRENCIES[:15], length=8, unique=True),
                "esg_integration": True,
                "sustainable_investing_aum_billions": round(fake.random.uniform(10.0, 200.0), 2)
            }
        }


class CorporateBankFactory(factory.Factory):
    """Factory for creating corporate banking subsidiaries."""
    
    class Meta:
        model = Tenant
    
    tenant_id = factory.LazyFunction(uuid4)
    parent_tenant_id = factory.LazyFunction(uuid4)
    tenant_type = TenantType.SUBSIDIARY
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    
    @factory.lazy_attribute
    def name(self):
        parent_bank = fake.random_element(GLOBAL_BANKS).split()[0]
        return f"{parent_bank} Corporate Banking"
    
    @factory.lazy_attribute
    def tenant_metadata(self):
        return {
            "country": fake.country(),
            "business_unit": "corporate_banking",
            "client_segments": [
                "large_corporates", "mid_market", "financial_institutions", 
                "government_entities", "multinational_corporations"
            ],
            "employee_count": fake.random_int(min=800, max=8000),
            "client_count": fake.random_int(min=200, max=2000),
            "loan_portfolio_billions_usd": round(fake.random.uniform(10.0, 300.0), 2),
            "deposit_base_billions_usd": round(fake.random.uniform(15.0, 250.0), 2),
            "credit_facilities_outstanding_billions": round(fake.random.uniform(20.0, 400.0), 2),
            "services": [
                "credit_facilities", "cash_management", "trade_finance", 
                "foreign_exchange", "interest_rate_derivatives", "project_finance",
                "structured_finance", "acquisition_finance", "real_estate_finance"
            ],
            "sector_exposure": {
                "technology": round(fake.random.uniform(10.0, 25.0), 1),
                "healthcare": round(fake.random.uniform(8.0, 20.0), 1),
                "financial_services": round(fake.random.uniform(5.0, 15.0), 1),
                "energy": round(fake.random.uniform(8.0, 18.0), 1),
                "real_estate": round(fake.random.uniform(10.0, 22.0), 1),
                "manufacturing": round(fake.random.uniform(12.0, 25.0), 1),
                "retail": round(fake.random.uniform(6.0, 15.0), 1)
            },
            "credit_quality": {
                "investment_grade_percentage": round(fake.random.uniform(60.0, 85.0), 1),
                "non_performing_loans_percentage": round(fake.random.uniform(0.5, 3.0), 2),
                "provision_coverage_ratio": round(fake.random.uniform(40.0, 80.0), 1),
                "average_loan_size_millions": round(fake.random.uniform(50.0, 500.0), 2)
            },
            "trade_finance": {
                "letters_of_credit_billions": round(fake.random.uniform(5.0, 100.0), 2),
                "guarantees_billions": round(fake.random.uniform(10.0, 150.0), 2),
                "documentary_collections_billions": round(fake.random.uniform(2.0, 50.0), 2),
                "supply_chain_finance_billions": round(fake.random.uniform(3.0, 75.0), 2)
            },
            "cash_management": {
                "client_accounts": fake.random_int(min=500, max=5000),
                "daily_payment_volume_millions": round(fake.random.uniform(1000.0, 25000.0), 2),
                "currency_clearing_volumes": {
                    currency: round(fake.random.uniform(100.0, 5000.0), 2)
                    for currency in fake.random_elements(elements=CURRENCIES[:10], length=5, unique=True)
                }
            }
        }


class RegulatoryComplianceFactory(factory.Factory):
    """Factory for creating regulatory compliance data."""
    
    @factory.lazy_attribute
    def compliance_metadata(self):
        return {
            "regulatory_framework": fake.random_element(REGULATORY_FRAMEWORKS),
            "capital_adequacy": {
                "tier1_capital_ratio": round(fake.random.uniform(12.0, 18.0), 2),
                "total_capital_ratio": round(fake.random.uniform(15.0, 22.0), 2),
                "leverage_ratio": round(fake.random.uniform(4.0, 8.0), 2),
                "risk_weighted_assets_millions": round(fake.random.uniform(10000.0, 500000.0), 2)
            },
            "liquidity_metrics": {
                "liquidity_coverage_ratio": round(fake.random.uniform(110.0, 180.0), 2),
                "net_stable_funding_ratio": round(fake.random.uniform(105.0, 150.0), 2),
                "liquidity_buffer_billions": round(fake.random.uniform(5.0, 100.0), 2)
            },
            "stress_testing": {
                "last_test_date": fake.date_between(start_date="-1y", end_date="today").isoformat(),
                "severely_adverse_scenario": {
                    "tier1_ratio_after_stress": round(fake.random.uniform(8.0, 12.0), 2),
                    "status": fake.random_element(["PASS", "CONDITIONAL_PASS"])
                },
                "adverse_scenario": {
                    "tier1_ratio_after_stress": round(fake.random.uniform(10.0, 14.0), 2),
                    "status": "PASS"
                }
            },
            "regulatory_reporting": {
                "frequency": fake.random_element(["monthly", "quarterly", "semi_annual", "annual"]),
                "last_submission": fake.date_between(start_date="-3m", end_date="today").isoformat(),
                "next_due_date": fake.date_between(start_date="today", end_date="+3m").isoformat(),
                "submission_status": fake.random_element(["submitted", "under_review", "approved"])
            },
            "examination_results": {
                "last_examination_date": fake.date_between(start_date="-2y", end_date="-6m").isoformat(),
                "examination_rating": fake.random_element(["1", "2", "3"]),  # 1 is best
                "supervisory_actions": fake.random_elements(
                    elements=["none", "informal_action", "formal_agreement", "consent_order"],
                    length=1
                )[0],
                "next_examination_date": fake.date_between(start_date="+6m", end_date="+18m").isoformat()
            },
            "compliance_violations": {
                "aml_violations_ytd": fake.random_int(min=0, max=5),
                "sanctions_violations_ytd": fake.random_int(min=0, max=2),
                "consumer_protection_violations_ytd": fake.random_int(min=0, max=10),
                "data_privacy_violations_ytd": fake.random_int(min=0, max=3)
            }
        }


# Schema factories for API testing
class TenantCreateSchemaFactory(factory.Factory):
    """Factory for TenantCreate schema with realistic fintech data."""
    
    class Meta:
        model = TenantCreate
    
    name = factory.LazyFunction(lambda: fake.random_element(GLOBAL_BANKS))
    tenant_type = TenantType.PARENT
    parent_tenant_id = None
    
    @factory.lazy_attribute
    def metadata(self):
        return GlobalBankFactory().tenant_metadata


class SubsidiaryTenantCreateSchemaFactory(factory.Factory):
    """Factory for subsidiary TenantCreate schema."""
    
    class Meta:
        model = TenantCreate
    
    tenant_type = TenantType.SUBSIDIARY
    parent_tenant_id = factory.LazyFunction(uuid4)
    
    @factory.lazy_attribute
    def name(self):
        parent_bank = fake.random_element(GLOBAL_BANKS).split()[0]
        location = fake.random_element(FINANCIAL_HUBS)
        return f"{parent_bank} {location}"
    
    @factory.lazy_attribute
    def metadata(self):
        return RegionalSubsidiaryFactory().tenant_metadata


# Utility functions for test data generation
def create_banking_hierarchy(parent_name: str, subsidiary_count: int = 3) -> dict:
    """Create a complete banking hierarchy with parent and subsidiaries."""
    parent_bank = GlobalBankFactory(name=parent_name)
    subsidiaries = []
    
    for i in range(subsidiary_count):
        location = fake.random_element(FINANCIAL_HUBS)
        subsidiary = RegionalSubsidiaryFactory(
            name=f"{parent_name} {location}",
            parent_tenant_id=parent_bank.tenant_id
        )
        subsidiaries.append(subsidiary)
    
    return {
        "parent": parent_bank,
        "subsidiaries": subsidiaries
    }


def generate_realistic_financial_metrics() -> dict:
    """Generate realistic financial performance metrics."""
    return {
        "revenue_millions_usd": round(fake.random.uniform(1000.0, 50000.0), 2),
        "net_income_millions_usd": round(fake.random.uniform(200.0, 15000.0), 2),
        "total_assets_billions_usd": round(fake.random.uniform(100.0, 4000.0), 2),
        "shareholders_equity_billions_usd": round(fake.random.uniform(50.0, 300.0), 2),
        "book_value_per_share": round(fake.random.uniform(30.0, 200.0), 2),
        "return_on_assets": round(fake.random.uniform(0.8, 2.0), 2),
        "return_on_equity": round(fake.random.uniform(10.0, 18.0), 2),
        "efficiency_ratio": round(fake.random.uniform(50.0, 70.0), 2),
        "net_interest_margin": round(fake.random.uniform(2.0, 4.0), 2),
        "cost_of_risk": round(fake.random.uniform(0.2, 1.5), 2)
    }


def generate_regulatory_capital_data() -> dict:
    """Generate regulatory capital data compliant with Basel III."""
    rwa = fake.random.uniform(50000.0, 1000000.0)  # Risk-weighted assets
    tier1_ratio = fake.random.uniform(12.0, 18.0)
    
    return {
        "risk_weighted_assets_millions_usd": round(rwa, 2),
        "tier1_capital_millions_usd": round((tier1_ratio / 100) * rwa, 2),
        "tier1_capital_ratio": round(tier1_ratio, 2),
        "total_capital_ratio": round(tier1_ratio + fake.random.uniform(2.0, 5.0), 2),
        "leverage_ratio": round(fake.random.uniform(4.5, 7.0), 2),
        "capital_conservation_buffer": 2.5,
        "countercyclical_buffer": round(fake.random.uniform(0.0, 2.5), 2),
        "systemic_risk_buffer": round(fake.random.uniform(0.0, 3.0), 2) if fake.boolean() else 0.0
    }


def generate_liquidity_data() -> dict:
    """Generate liquidity metrics compliant with Basel III."""
    return {
        "liquidity_coverage_ratio": round(fake.random.uniform(110.0, 200.0), 2),
        "net_stable_funding_ratio": round(fake.random.uniform(105.0, 150.0), 2),
        "high_quality_liquid_assets_billions": round(fake.random.uniform(10.0, 500.0), 2),
        "net_cash_outflows_30_days_billions": round(fake.random.uniform(8.0, 300.0), 2),
        "stable_funding_required_billions": round(fake.random.uniform(100.0, 2000.0), 2),
        "stable_funding_available_billions": round(fake.random.uniform(110.0, 2200.0), 2),
        "funding_concentration_risk": {
            "largest_depositor_percentage": round(fake.random.uniform(5.0, 15.0), 2),
            "top_10_depositors_percentage": round(fake.random.uniform(25.0, 45.0), 2),
            "wholesale_funding_percentage": round(fake.random.uniform(20.0, 60.0), 2)
        }
    }