"""
Integration tests for fintech business rule scenarios.

Tests complex business rules, data integrity constraints, and 
regulatory compliance scenarios in financial services.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.multi_tenant_db.models.tenant import Tenant


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.tenant
class TestFintechBusinessRules:
    """Integration tests for fintech business rules and constraints."""

    async def test_capital_adequacy_business_rules(
        self,
        integration_client: AsyncClient,
        integration_db_session: AsyncSession,
        hsbc_headers: dict[str, str],
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """
        Test capital adequacy business rules enforcement.
        
        Scenario: Bank must maintain minimum capital ratios across all
        subsidiaries and trigger alerts when approaching limits.
        """
        # Create parent bank with capital requirements
        parent_bank_data = {
            "name": "Capital Test Bank Holdings",
            "tenant_type": "parent",
            "metadata": {
                "country": "United Kingdom",
                "business_type": "bank_holding_company",
                "regulatory_framework": "Basel_III",
                "capital_requirements": {
                    "minimum_tier1_ratio": 8.0,
                    "minimum_total_capital_ratio": 10.5,
                    "capital_conservation_buffer": 2.5,
                    "systemic_risk_buffer": 1.0,
                    "countercyclical_buffer": 0.0
                },
                "consolidated_capital": {
                    "tier1_capital_millions_usd": 15000,
                    "total_capital_millions_usd": 18500,
                    "risk_weighted_assets_millions_usd": 125000
                }
            }
        }

        parent_response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=parent_bank_data
        )
        assert parent_response.status_code == 201
        parent_id = parent_response.json()["tenant_id"]

        # Create subsidiaries with varying capital levels
        subsidiaries = [
            {
                "name": "Capital Test Bank - Well Capitalized Sub",
                "tier1_ratio": 15.2,
                "total_ratio": 18.8,
                "status": "well_capitalized"
            },
            {
                "name": "Capital Test Bank - Adequately Capitalized Sub",
                "tier1_ratio": 9.1,
                "total_ratio": 11.2,
                "status": "adequately_capitalized"
            },
            {
                "name": "Capital Test Bank - Warning Level Sub",
                "tier1_ratio": 8.3,
                "total_ratio": 10.7,
                "status": "approaching_minimum"
            }
        ]

        created_subsidiaries = []
        for sub_data in subsidiaries:
            subsidiary_payload = {
                "name": sub_data["name"],
                "tenant_type": "subsidiary",
                "parent_tenant_id": parent_id,
                "metadata": {
                    "country": "United Kingdom",
                    "business_unit": "commercial_banking",
                    "regulatory_framework": "Basel_III",
                    "capital_ratios": {
                        "tier1_capital_ratio": sub_data["tier1_ratio"],
                        "total_capital_ratio": sub_data["total_ratio"],
                        "tier1_capital_millions_usd": 2500,
                        "total_capital_millions_usd": 3100,
                        "risk_weighted_assets_millions_usd": 16000
                    },
                    "capitalization_status": sub_data["status"],
                    "regulatory_alerts": {
                        "prompt_corrective_action": sub_data["tier1_ratio"] < 9.0,
                        "enhanced_supervision": sub_data["tier1_ratio"] < 8.5,
                        "capital_restoration_required": sub_data["tier1_ratio"] < 8.0
                    }
                }
            }
            
            response = await integration_client.post(
                "/api/v1/tenants/",
                headers=hsbc_headers,
                json=subsidiary_payload
            )
            assert response.status_code == 201
            created_subsidiaries.append(response.json())

        # Test consolidated capital adequacy reporting
        await set_tenant_context(integration_db_session, parent_id)

        capital_report = await integration_db_session.execute(
            text("""
                SELECT 
                    name,
                    CAST(tenant_metadata->'capital_ratios'->>'tier1_capital_ratio' AS NUMERIC) as tier1_ratio,
                    CAST(tenant_metadata->'capital_ratios'->>'total_capital_ratio' AS NUMERIC) as total_ratio,
                    tenant_metadata->>'capitalization_status' as status,
                    tenant_metadata->'regulatory_alerts'->>'prompt_corrective_action' as pca_required
                FROM tenants
                WHERE tenant_metadata->'capital_ratios' IS NOT NULL
                ORDER BY CAST(tenant_metadata->'capital_ratios'->>'tier1_capital_ratio' AS NUMERIC) DESC
            """)
        )
        
        capital_data = capital_report.fetchall()
        assert len(capital_data) == 3  # Three subsidiaries

        # Validate business rules
        well_capitalized_count = 0
        warning_level_count = 0
        pca_required_count = 0

        for name, tier1, total, status, pca in capital_data:
            # Basic capital ratio validation
            assert tier1 >= 8.0  # Minimum regulatory requirement
            assert total >= 10.5  # Minimum total capital requirement
            
            # Status classification validation
            if tier1 >= 12.0 and total >= 15.0:
                assert status == "well_capitalized"
                well_capitalized_count += 1
            elif tier1 >= 9.0 and total >= 11.0:
                assert status in ["adequately_capitalized", "well_capitalized"]
            else:
                assert status == "approaching_minimum"
                warning_level_count += 1
            
            # PCA trigger validation
            if tier1 < 9.0:
                assert pca == "true"
                pca_required_count += 1

        assert well_capitalized_count >= 1  # At least one well-capitalized
        assert warning_level_count >= 1  # At least one approaching minimum

        # Test capital ratio aggregation for regulatory reporting
        consolidated_ratios = await integration_db_session.execute(
            text("""
                SELECT 
                    SUM(CAST(tenant_metadata->'capital_ratios'->>'tier1_capital_millions_usd' AS NUMERIC)) as total_tier1,
                    SUM(CAST(tenant_metadata->'capital_ratios'->>'total_capital_millions_usd' AS NUMERIC)) as total_capital,
                    SUM(CAST(tenant_metadata->'capital_ratios'->>'risk_weighted_assets_millions_usd' AS NUMERIC)) as total_rwa,
                    MIN(CAST(tenant_metadata->'capital_ratios'->>'tier1_capital_ratio' AS NUMERIC)) as lowest_tier1_ratio
                FROM tenants
                WHERE tenant_metadata->'capital_ratios' IS NOT NULL
            """)
        )
        
        consolidated_data = consolidated_ratios.fetchone()
        total_tier1, total_capital, total_rwa, lowest_ratio = consolidated_data
        
        # Validate consolidated metrics
        assert total_tier1 >= 7500  # Sum of subsidiary Tier 1 capital
        assert total_capital >= 9300  # Sum of subsidiary total capital
        assert total_rwa >= 48000  # Sum of subsidiary RWA
        assert lowest_ratio >= 8.0  # Minimum ratio across all subsidiaries

        await clear_tenant_context(integration_db_session)

    async def test_liquidity_risk_management_rules(
        self,
        integration_client: AsyncClient,
        integration_db_session: AsyncSession,
        hsbc_headers: dict[str, str],
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """
        Test liquidity risk management business rules.
        
        Scenario: Banks must maintain adequate liquidity buffers and
        monitor funding concentration risks across different currencies.
        """
        # Create bank with liquidity management requirements
        liquidity_bank_data = {
            "name": "Liquidity Management Test Bank",
            "tenant_type": "parent",
            "metadata": {
                "country": "Switzerland",
                "business_type": "private_bank",
                "regulatory_framework": "FINMA",
                "liquidity_requirements": {
                    "lcr_minimum": 100.0,
                    "nsfr_minimum": 100.0,
                    "liquidity_buffer_minimum_percentage": 15.0
                },
                "funding_profile": {
                    "retail_deposits_percentage": 45.0,
                    "wholesale_funding_percentage": 35.0,
                    "interbank_funding_percentage": 20.0,
                    "concentration_limit_single_source": 10.0
                }
            }
        }

        parent_response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=liquidity_bank_data
        )
        assert parent_response.status_code == 201
        parent_id = parent_response.json()["tenant_id"]

        # Create currency-specific liquidity entities
        currency_entities = [
            {
                "name": "USD Liquidity Desk",
                "currency": "USD",
                "lcr": 125.8,
                "nsfr": 118.2,
                "liquid_assets_millions": 2500,
                "net_outflows_millions": 1980
            },
            {
                "name": "EUR Liquidity Desk",
                "currency": "EUR",
                "lcr": 115.3,
                "nsfr": 108.7,
                "liquid_assets_millions": 1800,
                "net_outflows_millions": 1560
            },
            {
                "name": "CHF Liquidity Desk",
                "currency": "CHF",
                "lcr": 142.1,
                "nsfr": 128.5,
                "liquid_assets_millions": 3200,
                "net_outflows_millions": 2250
            },
            {
                "name": "GBP Liquidity Desk",
                "currency": "GBP",
                "lcr": 98.5,  # Below minimum - should trigger alerts
                "nsfr": 102.1,
                "liquid_assets_millions": 980,
                "net_outflows_millions": 995
            }
        ]

        created_desks = []
        for desk_data in currency_entities:
            desk_payload = {
                "name": desk_data["name"],
                "tenant_type": "subsidiary",
                "parent_tenant_id": parent_id,
                "metadata": {
                    "country": "Switzerland",
                    "business_unit": "treasury",
                    "currency": desk_data["currency"],
                    "liquidity_metrics": {
                        "liquidity_coverage_ratio": desk_data["lcr"],
                        "net_stable_funding_ratio": desk_data["nsfr"],
                        "high_quality_liquid_assets_millions": desk_data["liquid_assets_millions"],
                        "net_cash_outflows_30_days_millions": desk_data["net_outflows_millions"]
                    },
                    "risk_alerts": {
                        "lcr_below_minimum": desk_data["lcr"] < 100.0,
                        "nsfr_below_minimum": desk_data["nsfr"] < 100.0,
                        "liquidity_warning": desk_data["lcr"] < 105.0,
                        "regulatory_reporting_required": desk_data["lcr"] < 100.0 or desk_data["nsfr"] < 100.0
                    },
                    "funding_sources": {
                        "central_bank_facilities": 15.0,
                        "interbank_market": 25.0,
                        "repo_market": 35.0,
                        "deposit_base": 25.0
                    }
                }
            }
            
            response = await integration_client.post(
                "/api/v1/tenants/",
                headers=hsbc_headers,
                json=desk_payload
            )
            assert response.status_code == 201
            created_desks.append(response.json())

        # Test liquidity risk aggregation and monitoring
        await set_tenant_context(integration_db_session, parent_id)

        # Liquidity coverage ratio monitoring
        lcr_report = await integration_db_session.execute(
            text("""
                SELECT 
                    tenant_metadata->>'currency' as currency,
                    CAST(tenant_metadata->'liquidity_metrics'->>'liquidity_coverage_ratio' AS NUMERIC) as lcr,
                    CAST(tenant_metadata->'liquidity_metrics'->>'net_stable_funding_ratio' AS NUMERIC) as nsfr,
                    tenant_metadata->'risk_alerts'->>'lcr_below_minimum' as lcr_breach,
                    tenant_metadata->'risk_alerts'->>'regulatory_reporting_required' as reporting_required
                FROM tenants
                WHERE tenant_metadata->'liquidity_metrics' IS NOT NULL
                ORDER BY tenant_metadata->>'currency'
            """)
        )
        
        lcr_data = lcr_report.fetchall()
        assert len(lcr_data) == 4  # Four currency desks

        compliant_count = 0
        breach_count = 0
        warning_count = 0

        for currency, lcr, nsfr, lcr_breach, reporting_req in lcr_data:
            # Validate LCR and NSFR business rules
            if lcr < 100.0:
                assert lcr_breach == "true"
                assert reporting_req == "true"
                breach_count += 1
            elif lcr < 105.0:
                warning_count += 1
            else:
                compliant_count += 1
            
            # NSFR should generally be above 100%
            assert nsfr >= 100.0

        assert breach_count == 1  # GBP desk should be in breach
        assert compliant_count >= 2  # At least two currencies compliant

        # Currency concentration analysis
        currency_concentration = await integration_db_session.execute(
            text("""
                SELECT 
                    tenant_metadata->>'currency' as currency,
                    CAST(tenant_metadata->'liquidity_metrics'->>'high_quality_liquid_assets_millions' AS NUMERIC) as hqla,
                    ROUND(
                        CAST(tenant_metadata->'liquidity_metrics'->>'high_quality_liquid_assets_millions' AS NUMERIC) * 100.0 / 
                        NULLIF(SUM(CAST(tenant_metadata->'liquidity_metrics'->>'high_quality_liquid_assets_millions' AS NUMERIC)) OVER(), 0), 
                        2
                    ) as concentration_percentage
                FROM tenants
                WHERE tenant_metadata->'liquidity_metrics' IS NOT NULL
                ORDER BY concentration_percentage DESC
            """)
        )
        
        concentration_data = concentration_concentration.fetchall()
        
        for currency, hqla, concentration in concentration_data:
            assert concentration <= 50.0  # No single currency should dominate liquidity
            assert hqla >= 500  # Minimum liquidity buffer per currency

        # Funding source diversification check
        funding_diversification = await integration_db_session.execute(
            text("""
                SELECT 
                    AVG(CAST(tenant_metadata->'funding_sources'->>'central_bank_facilities' AS NUMERIC)) as avg_cb_reliance,
                    AVG(CAST(tenant_metadata->'funding_sources'->>'interbank_market' AS NUMERIC)) as avg_interbank_reliance,
                    MAX(CAST(tenant_metadata->'funding_sources'->>'repo_market' AS NUMERIC)) as max_repo_concentration
                FROM tenants
                WHERE tenant_metadata->'funding_sources' IS NOT NULL
            """)
        )
        
        funding_data = funding_diversification.fetchone()
        avg_cb, avg_interbank, max_repo = funding_data
        
        # Validate funding diversification rules
        assert avg_cb <= 30.0  # Not over-reliant on central bank
        assert avg_interbank <= 40.0  # Reasonable interbank market usage
        assert max_repo <= 50.0  # Repo market concentration within limits

        await clear_tenant_context(integration_db_session)

    async def test_credit_risk_portfolio_rules(
        self,
        integration_client: AsyncClient,
        integration_db_session: AsyncSession,
        hsbc_headers: dict[str, str],
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """
        Test credit risk portfolio management business rules.
        
        Scenario: Banks must monitor credit concentrations, maintain
        adequate provisions, and comply with exposure limits.
        """
        # Create credit portfolio management bank
        credit_bank_data = {
            "name": "Credit Risk Management Bank",
            "tenant_type": "parent",
            "metadata": {
                "country": "Germany",
                "business_type": "commercial_bank",
                "regulatory_framework": "CRR_CRD",
                "credit_risk_framework": {
                    "large_exposure_limit_percentage": 25.0,
                    "sector_concentration_limit_percentage": 15.0,
                    "country_concentration_limit_percentage": 30.0,
                    "expected_loss_provision_percentage": 1.2,
                    "unexpected_loss_buffer_percentage": 2.5
                },
                "total_loan_portfolio_millions_eur": 25000
            }
        }

        parent_response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=credit_bank_data
        )
        assert parent_response.status_code == 201
        parent_id = parent_response.json()["tenant_id"]

        # Create sector-specific credit portfolios
        credit_portfolios = [
            {
                "name": "Real Estate Credit Portfolio",
                "sector": "real_estate",
                "portfolio_size_millions": 6500,
                "avg_pd": 2.8,  # Probability of default %
                "avg_lgd": 45.0,  # Loss given default %
                "concentration_risk": "high"
            },
            {
                "name": "Manufacturing Credit Portfolio", 
                "sector": "manufacturing",
                "portfolio_size_millions": 4200,
                "avg_pd": 1.9,
                "avg_lgd": 40.0,
                "concentration_risk": "medium"
            },
            {
                "name": "Technology Credit Portfolio",
                "sector": "technology",
                "portfolio_size_millions": 3800,
                "avg_pd": 3.2,
                "avg_lgd": 65.0,
                "concentration_risk": "medium"
            },
            {
                "name": "Energy Credit Portfolio",
                "sector": "energy",
                "portfolio_size_millions": 5200,
                "avg_pd": 4.1,
                "avg_lgd": 55.0,
                "concentration_risk": "high"
            },
            {
                "name": "Healthcare Credit Portfolio",
                "sector": "healthcare",
                "portfolio_size_millions": 2800,
                "avg_pd": 1.5,
                "avg_lgd": 30.0,
                "concentration_risk": "low"
            }
        ]

        created_portfolios = []
        for portfolio_data in credit_portfolios:
            # Calculate expected loss and required provisions
            expected_loss = (portfolio_data["avg_pd"] / 100) * (portfolio_data["avg_lgd"] / 100) * portfolio_data["portfolio_size_millions"]
            concentration_percentage = (portfolio_data["portfolio_size_millions"] / 25000) * 100
            
            portfolio_payload = {
                "name": portfolio_data["name"],
                "tenant_type": "subsidiary",
                "parent_tenant_id": parent_id,
                "metadata": {
                    "country": "Germany",
                    "business_unit": "credit_risk_management",
                    "sector": portfolio_data["sector"],
                    "portfolio_metrics": {
                        "portfolio_size_millions_eur": portfolio_data["portfolio_size_millions"],
                        "weighted_average_pd_percentage": portfolio_data["avg_pd"],
                        "weighted_average_lgd_percentage": portfolio_data["avg_lgd"],
                        "expected_loss_millions_eur": round(expected_loss, 2),
                        "concentration_percentage": round(concentration_percentage, 1),
                        "number_of_obligors": int(portfolio_data["portfolio_size_millions"] / 2.5),  # Avg 2.5M per obligor
                        "largest_single_exposure_millions_eur": portfolio_data["portfolio_size_millions"] * 0.12  # 12% of portfolio
                    },
                    "risk_classification": {
                        "concentration_risk_level": portfolio_data["concentration_risk"],
                        "sector_limit_breach": concentration_percentage > 15.0,
                        "provisioning_adequate": expected_loss >= portfolio_data["portfolio_size_millions"] * 0.01,
                        "diversification_score": min(10, int(portfolio_data["portfolio_size_millions"] / 500))
                    },
                    "regulatory_capital": {
                        "risk_weighted_assets_millions_eur": portfolio_data["portfolio_size_millions"] * 0.75,
                        "capital_requirement_millions_eur": portfolio_data["portfolio_size_millions"] * 0.75 * 0.08,
                        "economic_capital_millions_eur": expected_loss * 2.5
                    }
                }
            }
            
            response = await integration_client.post(
                "/api/v1/tenants/",
                headers=hsbc_headers,
                json=portfolio_payload
            )
            assert response.status_code == 201
            created_portfolios.append(response.json())

        # Test credit portfolio risk aggregation and limits monitoring
        await set_tenant_context(integration_db_session, parent_id)

        # Sector concentration analysis
        concentration_report = await integration_db_session.execute(
            text("""
                SELECT 
                    tenant_metadata->>'sector' as sector,
                    CAST(tenant_metadata->'portfolio_metrics'->>'portfolio_size_millions_eur' AS NUMERIC) as portfolio_size,
                    CAST(tenant_metadata->'portfolio_metrics'->>'concentration_percentage' AS NUMERIC) as concentration_pct,
                    tenant_metadata->'risk_classification'->>'concentration_risk_level' as risk_level,
                    tenant_metadata->'risk_classification'->>'sector_limit_breach' as limit_breach
                FROM tenants
                WHERE tenant_metadata->>'sector' IS NOT NULL
                ORDER BY CAST(tenant_metadata->'portfolio_metrics'->>'concentration_percentage' AS NUMERIC) DESC
            """)
        )
        
        concentration_data = concentration_report.fetchall()
        assert len(concentration_data) == 5  # Five sector portfolios

        high_concentration_count = 0
        limit_breach_count = 0
        total_portfolio_size = 0

        for sector, size, concentration, risk_level, breach in concentration_data:
            total_portfolio_size += size
            
            # Validate concentration limits
            if concentration > 15.0:
                assert breach == "true"
                limit_breach_count += 1
            
            if risk_level == "high":
                high_concentration_count += 1
                assert concentration >= 15.0  # High risk should have high concentration

        assert total_portfolio_size <= 25000  # Total should not exceed bank portfolio
        assert limit_breach_count >= 2  # Real estate and energy should breach limits
        assert high_concentration_count == 2  # Real estate and energy are high risk

        # Expected loss and provisioning analysis
        provisioning_report = await integration_db_session.execute(
            text("""
                SELECT 
                    SUM(CAST(tenant_metadata->'portfolio_metrics'->>'expected_loss_millions_eur' AS NUMERIC)) as total_expected_loss,
                    AVG(CAST(tenant_metadata->'portfolio_metrics'->>'weighted_average_pd_percentage' AS NUMERIC)) as avg_pd,
                    AVG(CAST(tenant_metadata->'portfolio_metrics'->>'weighted_average_lgd_percentage' AS NUMERIC)) as avg_lgd,
                    COUNT(*) FILTER (WHERE tenant_metadata->'risk_classification'->>'provisioning_adequate' = 'true') as adequate_provisions
                FROM tenants
                WHERE tenant_metadata->'portfolio_metrics' IS NOT NULL
            """)
        )
        
        provisioning_data = provisioning_report.fetchone()
        total_el, avg_pd, avg_lgd, adequate_count = provisioning_data
        
        # Validate provisioning adequacy
        assert total_el >= 100  # Minimum expected loss across portfolios
        assert total_el <= 500  # Should not be excessive
        assert avg_pd >= 1.0 and avg_pd <= 5.0  # Reasonable PD range
        assert avg_lgd >= 30.0 and avg_lgd <= 70.0  # Reasonable LGD range
        assert adequate_count == 5  # All portfolios should have adequate provisions

        # Regulatory capital adequacy check
        capital_report = await integration_db_session.execute(
            text("""
                SELECT 
                    SUM(CAST(tenant_metadata->'regulatory_capital'->>'risk_weighted_assets_millions_eur' AS NUMERIC)) as total_rwa,
                    SUM(CAST(tenant_metadata->'regulatory_capital'->>'capital_requirement_millions_eur' AS NUMERIC)) as total_capital_req,
                    SUM(CAST(tenant_metadata->'regulatory_capital'->>'economic_capital_millions_eur' AS NUMERIC)) as total_economic_capital,
                    ROUND(
                        SUM(CAST(tenant_metadata->'regulatory_capital'->>'capital_requirement_millions_eur' AS NUMERIC)) * 100.0 /
                        NULLIF(SUM(CAST(tenant_metadata->'regulatory_capital'->>'risk_weighted_assets_millions_eur' AS NUMERIC)), 0),
                        2
                    ) as effective_capital_ratio
                FROM tenants
                WHERE tenant_metadata->'regulatory_capital' IS NOT NULL
            """)
        )
        
        capital_data = capital_report.fetchone()
        total_rwa, total_cap_req, total_econ_cap, eff_ratio = capital_data
        
        # Validate capital calculations
        assert total_rwa >= 15000  # Sum of RWA across portfolios
        assert total_cap_req >= 1200  # 8% of RWA minimum
        assert eff_ratio >= 8.0  # Effective capital ratio should meet minimum
        assert total_econ_cap >= total_el * 2.0  # Economic capital should exceed expected loss

        # Large exposure monitoring
        large_exposure_report = await integration_db_session.execute(
            text("""
                SELECT 
                    tenant_metadata->>'sector' as sector,
                    CAST(tenant_metadata->'portfolio_metrics'->>'largest_single_exposure_millions_eur' AS NUMERIC) as largest_exposure,
                    ROUND(
                        CAST(tenant_metadata->'portfolio_metrics'->>'largest_single_exposure_millions_eur' AS NUMERIC) * 100.0 / 25000.0,
                        2
                    ) as exposure_percentage_of_capital
                FROM tenants
                WHERE tenant_metadata->'portfolio_metrics' IS NOT NULL
                ORDER BY CAST(tenant_metadata->'portfolio_metrics'->>'largest_single_exposure_millions_eur' AS NUMERIC) DESC
            """)
        )
        
        exposure_data = large_exposure_report.fetchall()
        
        for sector, exposure, exposure_pct in exposure_data:
            # Large exposure limit check (25% of capital)
            assert exposure_pct <= 25.0, f"Large exposure limit exceeded for {sector}: {exposure_pct}%"
            
            # Single exposure should be reasonable portion of sector portfolio
            assert exposure >= 100  # Minimum meaningful exposure
            assert exposure <= 1000  # Should not be excessive

        await clear_tenant_context(integration_db_session)

    async def test_operational_risk_business_rules(
        self,
        integration_client: AsyncClient,
        integration_db_session: AsyncSession,
        hsbc_headers: dict[str, str],
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """
        Test operational risk management business rules.
        
        Scenario: Banks must monitor operational risk events, maintain
        adequate capital buffers, and implement control frameworks.
        """
        # Create operational risk management bank
        oprisk_bank_data = {
            "name": "Operational Risk Management Bank",
            "tenant_type": "parent",
            "metadata": {
                "country": "United States",
                "business_type": "national_bank",
                "regulatory_framework": "Basel_III_US",
                "operational_risk_framework": {
                    "approach": "standardised_approach",
                    "business_indicator_millions_usd": 1500,
                    "capital_requirement_millions_usd": 120,
                    "risk_appetite_millions_usd": 50,
                    "control_environment_rating": "satisfactory"
                },
                "risk_tolerance": {
                    "maximum_single_loss_millions_usd": 25,
                    "annual_loss_budget_millions_usd": 75,
                    "key_risk_indicator_thresholds": {
                        "system_downtime_hours_monthly": 4,
                        "failed_transactions_percentage": 0.1,
                        "staff_turnover_percentage_annual": 15
                    }
                }
            }
        }

        parent_response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=oprisk_bank_data
        )
        assert parent_response.status_code == 201
        parent_id = parent_response.json()["tenant_id"]

        # Create business line operational risk units
        business_lines = [
            {
                "name": "Investment Banking Operational Risk",
                "business_line": "investment_banking",
                "gross_income_millions": 450,
                "loss_events_ytd": 12,
                "total_losses_millions": 8.5,
                "control_effectiveness": "effective",
                "system_downtime_hours": 2.5
            },
            {
                "name": "Retail Banking Operational Risk",
                "business_line": "retail_banking", 
                "gross_income_millions": 650,
                "loss_events_ytd": 35,
                "total_losses_millions": 15.2,
                "control_effectiveness": "effective",
                "system_downtime_hours": 6.5  # Above threshold
            },
            {
                "name": "Trading Operational Risk",
                "business_line": "trading",
                "gross_income_millions": 280,
                "loss_events_ytd": 8,
                "total_losses_millions": 12.8,
                "control_effectiveness": "partially_effective",
                "system_downtime_hours": 1.2
            },
            {
                "name": "Corporate Banking Operational Risk",
                "business_line": "corporate_banking",
                "gross_income_millions": 320,
                "loss_events_ytd": 18,
                "total_losses_millions": 6.3,
                "control_effectiveness": "effective",
                "system_downtime_hours": 3.8
            }
        ]

        created_business_lines = []
        for bl_data in business_lines:
            # Calculate operational risk capital and KRIs
            capital_multiplier = 0.15 if bl_data["business_line"] == "trading" else 0.12
            op_risk_capital = bl_data["gross_income_millions"] * capital_multiplier
            loss_rate = (bl_data["total_losses_millions"] / bl_data["gross_income_millions"]) * 100
            
            bl_payload = {
                "name": bl_data["name"],
                "tenant_type": "subsidiary",
                "parent_tenant_id": parent_id,
                "metadata": {
                    "country": "United States",
                    "business_unit": "operational_risk",
                    "business_line": bl_data["business_line"],
                    "operational_metrics": {
                        "gross_income_millions_usd": bl_data["gross_income_millions"],
                        "operational_risk_capital_millions_usd": round(op_risk_capital, 2),
                        "loss_events_count_ytd": bl_data["loss_events_ytd"],
                        "total_operational_losses_millions_usd": bl_data["total_losses_millions"],
                        "loss_rate_percentage": round(loss_rate, 3),
                        "average_loss_per_event_thousands_usd": round((bl_data["total_losses_millions"] * 1000) / max(bl_data["loss_events_ytd"], 1), 2)
                    },
                    "control_assessment": {
                        "control_effectiveness_rating": bl_data["control_effectiveness"],
                        "last_assessment_date": "2025-06-30",
                        "next_assessment_date": "2025-12-31",
                        "key_controls_tested": True,
                        "control_deficiencies_count": 2 if bl_data["control_effectiveness"] == "partially_effective" else 0
                    },
                    "key_risk_indicators": {
                        "system_downtime_hours_monthly": bl_data["system_downtime_hours"],
                        "failed_transactions_percentage": 0.05 if bl_data["business_line"] == "trading" else 0.08,
                        "staff_turnover_percentage_annual": 12.5,
                        "customer_complaints_per_1000_accounts": 2.1,
                        "processing_errors_per_10000_transactions": 3.2
                    },
                    "risk_alerts": {
                        "downtime_threshold_exceeded": bl_data["system_downtime_hours"] > 4.0,
                        "loss_budget_exceeded": bl_data["total_losses_millions"] > 20.0,
                        "control_effectiveness_concern": bl_data["control_effectiveness"] != "effective",
                        "high_frequency_losses": bl_data["loss_events_ytd"] > 30
                    }
                }
            }
            
            response = await integration_client.post(
                "/api/v1/tenants/",
                headers=hsbc_headers,
                json=bl_payload
            )
            assert response.status_code == 201
            created_business_lines.append(response.json())

        # Test operational risk aggregation and monitoring
        await set_tenant_context(integration_db_session, parent_id)

        # Operational loss event analysis
        loss_analysis = await integration_db_session.execute(
            text("""
                SELECT 
                    tenant_metadata->>'business_line' as business_line,
                    CAST(tenant_metadata->'operational_metrics'->>'loss_events_count_ytd' AS INTEGER) as loss_events,
                    CAST(tenant_metadata->'operational_metrics'->>'total_operational_losses_millions_usd' AS NUMERIC) as total_losses,
                    CAST(tenant_metadata->'operational_metrics'->>'loss_rate_percentage' AS NUMERIC) as loss_rate,
                    tenant_metadata->'control_assessment'->>'control_effectiveness_rating' as control_rating
                FROM tenants
                WHERE tenant_metadata->'operational_metrics' IS NOT NULL
                ORDER BY CAST(tenant_metadata->'operational_metrics'->>'total_operational_losses_millions_usd' AS NUMERIC) DESC
            """)
        )
        
        loss_data = loss_analysis.fetchall()
        assert len(loss_data) == 4  # Four business lines

        total_loss_events = 0
        total_losses = 0
        high_loss_rate_count = 0
        control_issues_count = 0

        for bl, events, losses, loss_rate, control_rating in loss_data:
            total_loss_events += events
            total_losses += losses
            
            # Validate business rules
            assert events >= 0
            assert losses >= 0
            assert loss_rate >= 0
            
            # High loss rate threshold (>3% of gross income)
            if loss_rate > 3.0:
                high_loss_rate_count += 1
            
            # Control effectiveness issues
            if control_rating != "effective":
                control_issues_count += 1
                assert control_rating == "partially_effective"

        # Aggregate validation
        assert total_loss_events >= 50  # Total events across business lines
        assert total_losses >= 30.0  # Total losses in millions
        assert high_loss_rate_count >= 1  # At least one business line with high loss rate
        assert control_issues_count == 1  # Trading should have control issues

        # Key Risk Indicator monitoring
        kri_analysis = await integration_db_session.execute(
            text("""
                SELECT 
                    tenant_metadata->>'business_line' as business_line,
                    CAST(tenant_metadata->'key_risk_indicators'->>'system_downtime_hours_monthly' AS NUMERIC) as downtime,
                    CAST(tenant_metadata->'key_risk_indicators'->>'failed_transactions_percentage' AS NUMERIC) as failed_txns,
                    tenant_metadata->'risk_alerts'->>'downtime_threshold_exceeded' as downtime_alert,
                    tenant_metadata->'risk_alerts'->>'control_effectiveness_concern' as control_alert
                FROM tenants
                WHERE tenant_metadata->'key_risk_indicators' IS NOT NULL
            """)
        )
        
        kri_data = kri_analysis.fetchall()
        
        downtime_alerts = 0
        control_alerts = 0
        
        for bl, downtime, failed_txns, downtime_alert, control_alert in kri_data:
            # KRI threshold validation
            if downtime > 4.0:
                assert downtime_alert == "true"
                downtime_alerts += 1
            
            if control_alert == "true":
                control_alerts += 1
            
            # Failed transaction rate should be reasonable
            assert failed_txns <= 0.2  # Maximum 0.2%

        assert downtime_alerts == 1  # Retail banking should exceed downtime threshold
        assert control_alerts == 1  # Trading should have control concerns

        # Operational risk capital adequacy
        capital_analysis = await integration_db_session.execute(
            text("""
                SELECT 
                    SUM(CAST(tenant_metadata->'operational_metrics'->>'operational_risk_capital_millions_usd' AS NUMERIC)) as total_op_risk_capital,
                    SUM(CAST(tenant_metadata->'operational_metrics'->>'gross_income_millions_usd' AS NUMERIC)) as total_gross_income,
                    ROUND(
                        SUM(CAST(tenant_metadata->'operational_metrics'->>'operational_risk_capital_millions_usd' AS NUMERIC)) * 100.0 /
                        NULLIF(SUM(CAST(tenant_metadata->'operational_metrics'->>'gross_income_millions_usd' AS NUMERIC)), 0),
                        2
                    ) as capital_as_percentage_of_income
                FROM tenants
                WHERE tenant_metadata->'operational_metrics' IS NOT NULL
            """)
        )
        
        capital_data = capital_analysis.fetchone()
        total_capital, total_income, capital_percentage = capital_data
        
        # Capital adequacy validation
        assert total_capital >= 150  # Minimum operational risk capital
        assert total_income >= 1500  # Total gross income
        assert capital_percentage >= 10.0  # Reasonable capital percentage
        assert capital_percentage <= 20.0  # Not excessive

        await clear_tenant_context(integration_db_session)