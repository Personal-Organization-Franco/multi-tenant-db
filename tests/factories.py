"""
Factory classes for test data generation.

Provides factory classes using factory-boy for generating test data
with realistic fintech examples.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import factory
from faker import Faker
from pydantic import ValidationError

from src.multi_tenant_db.models.tenant import Tenant, TenantType
from src.multi_tenant_db.schemas.tenant import (
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantListItem,
)

fake = Faker()

# Fintech company names for realistic test data
FINTECH_PARENT_COMPANIES = [
    "HSBC Holdings",
    "JP Morgan Chase",
    "Goldman Sachs",
    "Morgan Stanley",
    "Barclays",
    "Deutsche Bank",
    "Credit Suisse",
    "UBS Group",
    "Bank of America",
    "Wells Fargo",
    "Citigroup",
    "Royal Bank of Canada",
]

FINTECH_SUBSIDIARY_NAMES = [
    "Hong Kong",
    "Singapore",
    "London",
    "New York",
    "Tokyo",
    "Sydney",
    "Toronto",
    "Frankfurt",
    "Zurich",
    "Dubai",
    "Mumbai",
    "Seoul",
]

BUSINESS_UNITS = [
    "retail_banking",
    "investment_banking",
    "wealth_management",
    "corporate_banking",
    "trading",
    "risk_management",
    "compliance",
    "technology",
]

COUNTRIES = [
    "United Kingdom", "United States", "Hong Kong", "Singapore", 
    "Canada", "Germany", "Switzerland", "Japan", "Australia",
    "United Arab Emirates", "India", "South Korea"
]


class TenantFactory(factory.Factory):
    """Factory for Tenant model instances."""
    
    class Meta:
        model = Tenant
    
    tenant_id = factory.LazyFunction(uuid4)
    name = factory.LazyFunction(lambda: fake.random_element(FINTECH_PARENT_COMPANIES))
    parent_tenant_id = None
    tenant_type = TenantType.PARENT
    tenant_metadata = factory.LazyFunction(lambda: {
        "country": fake.random_element(COUNTRIES),
        "business_unit": fake.random_element(BUSINESS_UNITS),
        "status": "active",
        "founded_year": fake.random_int(min=1980, max=2023),
        "employee_count": fake.random_int(min=100, max=100000),
    })
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class ParentTenantFactory(TenantFactory):
    """Factory for parent tenant instances."""
    
    tenant_type = TenantType.PARENT
    parent_tenant_id = None
    name = factory.LazyFunction(lambda: fake.random_element(FINTECH_PARENT_COMPANIES))


class SubsidiaryTenantFactory(TenantFactory):
    """Factory for subsidiary tenant instances."""
    
    tenant_type = TenantType.SUBSIDIARY
    parent_tenant_id = factory.LazyFunction(uuid4)
    name = factory.LazyFunction(
        lambda: f"{fake.random_element(FINTECH_PARENT_COMPANIES)} {fake.random_element(FINTECH_SUBSIDIARY_NAMES)}"
    )
    tenant_metadata = factory.LazyFunction(lambda: {
        "country": fake.random_element(COUNTRIES),
        "business_unit": fake.random_element(BUSINESS_UNITS),
        "status": "active",
        "region": fake.random_element(FINTECH_SUBSIDIARY_NAMES),
        "local_currency": fake.currency_code(),
    })


class TenantCreateSchemaFactory(factory.Factory):
    """Factory for TenantCreate schema instances."""
    
    class Meta:
        model = TenantCreate
    
    name = factory.LazyFunction(lambda: fake.random_element(FINTECH_PARENT_COMPANIES))
    tenant_type = TenantType.PARENT
    parent_tenant_id = None
    metadata = factory.LazyFunction(lambda: {
        "country": fake.random_element(COUNTRIES),
        "business_unit": fake.random_element(BUSINESS_UNITS),
        "status": "active",
    })


class ParentTenantCreateSchemaFactory(TenantCreateSchemaFactory):
    """Factory for parent tenant creation schemas."""
    
    tenant_type = TenantType.PARENT
    parent_tenant_id = None


class SubsidiaryTenantCreateSchemaFactory(TenantCreateSchemaFactory):
    """Factory for subsidiary tenant creation schemas."""
    
    tenant_type = TenantType.SUBSIDIARY
    parent_tenant_id = factory.LazyFunction(uuid4)
    name = factory.LazyFunction(
        lambda: f"{fake.random_element(FINTECH_PARENT_COMPANIES)} {fake.random_element(FINTECH_SUBSIDIARY_NAMES)}"
    )


class TenantUpdateSchemaFactory(factory.Factory):
    """Factory for TenantUpdate schema instances."""
    
    class Meta:
        model = TenantUpdate
    
    name = factory.LazyFunction(
        lambda: f"{fake.random_element(FINTECH_PARENT_COMPANIES)} Updated"
    )
    metadata = factory.LazyFunction(lambda: {
        "country": fake.random_element(COUNTRIES),
        "business_unit": fake.random_element(BUSINESS_UNITS),
        "status": "updated",
        "last_audit": fake.date_time_this_year().isoformat(),
    })


class TenantResponseSchemaFactory(factory.Factory):
    """Factory for TenantResponse schema instances."""
    
    class Meta:
        model = TenantResponse
    
    tenant_id = factory.LazyFunction(uuid4)
    name = factory.LazyFunction(lambda: fake.random_element(FINTECH_PARENT_COMPANIES))
    parent_tenant_id = None
    tenant_type = TenantType.PARENT
    metadata = factory.LazyFunction(lambda: {
        "country": fake.random_element(COUNTRIES),
        "business_unit": fake.random_element(BUSINESS_UNITS),
        "status": "active",
    })
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class TenantListItemSchemaFactory(factory.Factory):
    """Factory for TenantListItem schema instances."""
    
    class Meta:
        model = TenantListItem
    
    tenant_id = factory.LazyFunction(uuid4)
    name = factory.LazyFunction(lambda: fake.random_element(FINTECH_PARENT_COMPANIES))
    tenant_type = TenantType.PARENT
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


# Utility functions for test data generation
def generate_valid_tenant_name() -> str:
    """Generate a valid tenant name."""
    return fake.random_element(FINTECH_PARENT_COMPANIES)


def generate_invalid_tenant_names() -> list[str]:
    """Generate a list of invalid tenant names for testing."""
    return [
        "",  # Empty string
        "   ",  # Whitespace only  
        "a" * 201,  # Too long (>200 chars)
        "\t\n",  # Only whitespace chars
    ]


def generate_valid_metadata() -> dict:
    """Generate valid metadata dictionary."""
    return {
        "country": fake.random_element(COUNTRIES),
        "business_unit": fake.random_element(BUSINESS_UNITS),
        "status": "active",
        "contact_email": fake.email(),
        "phone": fake.phone_number(),
        "address": {
            "street": fake.street_address(),
            "city": fake.city(),
            "postal_code": fake.postcode(),
        },
        "compliance": {
            "kyc_status": "verified",
            "aml_check": "passed",
            "last_audit": fake.date_this_year().isoformat(),
        }
    }


def generate_realistic_parent_tenant_data() -> dict:
    """Generate realistic parent tenant data."""
    company_name = fake.random_element(FINTECH_PARENT_COMPANIES)
    return {
        "name": company_name,
        "tenant_type": TenantType.PARENT,
        "metadata": {
            "country": fake.random_element(COUNTRIES),
            "business_unit": "corporate_headquarters",
            "status": "active",
            "founded_year": fake.random_int(min=1980, max=2020),
            "employee_count": fake.random_int(min=10000, max=500000),
            "regulatory_licenses": [
                "banking_license",
                "investment_services",
                "insurance_license",
            ],
            "primary_currency": fake.currency_code(),
        }
    }


def generate_realistic_subsidiary_tenant_data(parent_id: UUID) -> dict:
    """Generate realistic subsidiary tenant data."""
    parent_company = fake.random_element(FINTECH_PARENT_COMPANIES)
    region = fake.random_element(FINTECH_SUBSIDIARY_NAMES)
    return {
        "name": f"{parent_company} {region}",
        "parent_tenant_id": parent_id,
        "tenant_type": TenantType.SUBSIDIARY,
        "metadata": {
            "country": fake.random_element(COUNTRIES),
            "business_unit": fake.random_element(BUSINESS_UNITS),
            "region": region,
            "status": "active",
            "local_currency": fake.currency_code(),
            "employee_count": fake.random_int(min=50, max=5000),
            "local_licenses": [
                "local_banking_license",
                "money_services_license",
            ],
            "parent_company": parent_company,
        }
    }