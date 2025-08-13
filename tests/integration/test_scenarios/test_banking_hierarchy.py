"""
Integration tests for banking hierarchy scenarios.

Tests realistic multinational banking scenarios with parent-subsidiary
relationships, regulatory compliance, and business rule enforcement.
"""

import time
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.multi_tenant_db.models.tenant import Tenant


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.tenant
@pytest.mark.slow
class TestBankingHierarchyScenarios:
    """Integration tests for banking hierarchy business scenarios."""

    async def test_multinational_bank_setup_scenario(
        self,
        integration_client: AsyncClient,
        integration_db_session: AsyncSession,
        hsbc_headers: dict[str, str],
        performance_threshold_ms: int,
    ) -> None:
        """
        Test complete multinational bank setup scenario.
        
        Scenario: HSBC establishes operations in new markets by creating
        subsidiary banks with proper regulatory compliance and hierarchy.
        """
        # Step 1: Create parent bank (HSBC Global)
        parent_bank_data = {
            "name": "HSBC Global Banking Corporation",
            "tenant_type": "parent",
            "metadata": {
                "country": "United Kingdom",
                "headquarters": "London",
                "business_type": "multinational_bank",
                "founded_year": 1865,
                "employee_count": 220000,
                "regulatory_licenses": [
                    "UK_banking_license",
                    "FCA_authorization",
                    "PRA_authorization",
                    "ECB_supervision"
                ],
                "primary_currency": "GBP",
                "capital_adequacy_ratio": 15.8,
                "tier1_capital_billion_usd": 185.2,
                "total_assets_billion_usd": 2963.0,
                "credit_rating": {
                    "moodys": "Aa3",
                    "sp": "A",
                    "fitch": "AA-"
                },
                "regulatory_status": "fully_authorized",
                "systemic_importance": "G-SIB"  # Global Systemically Important Bank
            }
        }

        start_time = time.time()
        parent_response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=parent_bank_data
        )
        end_time = time.time()
        
        assert parent_response.status_code == 201
        assert (end_time - start_time) * 1000 <= performance_threshold_ms
        
        parent_bank = parent_response.json()
        parent_id = parent_bank["tenant_id"]

        # Step 2: Create Asia Pacific regional hub
        asia_hub_data = {
            "name": "HSBC Asia Pacific Holdings",
            "tenant_type": "subsidiary",
            "parent_tenant_id": parent_id,
            "metadata": {
                "country": "Hong Kong",
                "region": "Asia Pacific",
                "business_unit": "regional_headquarters",
                "local_currency": "HKD",
                "employee_count": 45000,
                "local_licenses": [
                    "HKMA_banking_license",
                    "SFC_comprehensive_license",
                    "MPF_registration"
                ],
                "established_year": 1865,
                "branches": 280,
                "regulatory_capital_billion_usd": 45.8,
                "risk_weighted_assets_billion_usd": 285.6,
                "loan_loss_provisions_percentage": 0.24,
                "regulatory_status": "regional_hub",
                "oversight_markets": [
                    "Hong Kong", "Singapore", "Malaysia", "Thailand", "Philippines"
                ]
            }
        }

        asia_response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=asia_hub_data
        )
        
        assert asia_response.status_code == 201
        asia_hub = asia_response.json()
        asia_hub_id = asia_hub["tenant_id"]

        # Step 3: Create local market subsidiaries under Asia hub
        subsidiaries = [
            {
                "name": "HSBC Bank (Singapore) Limited",
                "country": "Singapore",
                "local_currency": "SGD",
                "business_focus": "private_banking",
                "regulatory_licenses": ["MAS_bank_license", "MAS_securities_license"],
                "employee_count": 8500,
                "branches": 45
            },
            {
                "name": "HSBC Bank Malaysia Berhad",
                "country": "Malaysia",
                "local_currency": "MYR", 
                "business_focus": "retail_banking",
                "regulatory_licenses": ["BNM_banking_license", "SC_capital_markets_license"],
                "employee_count": 12000,
                "branches": 125
            },
            {
                "name": "HSBC Bank (Thailand) Public Company Limited",
                "country": "Thailand",
                "local_currency": "THB",
                "business_focus": "commercial_banking",
                "regulatory_licenses": ["BOT_commercial_bank_license"],
                "employee_count": 4200,
                "branches": 28
            }
        ]

        created_subsidiaries = []
        for sub_data in subsidiaries:
            subsidiary_payload = {
                "name": sub_data["name"],
                "tenant_type": "subsidiary",
                "parent_tenant_id": asia_hub_id,  # Report to regional hub
                "metadata": {
                    "country": sub_data["country"],
                    "region": "Asia Pacific",
                    "business_unit": sub_data["business_focus"],
                    "local_currency": sub_data["local_currency"],
                    "employee_count": sub_data["employee_count"],
                    "local_licenses": sub_data["regulatory_licenses"],
                    "branches": sub_data["branches"],
                    "established_year": 1994,
                    "parent_company": "HSBC Asia Pacific Holdings",
                    "ultimate_parent": "HSBC Global Banking Corporation",
                    "compliance_framework": "Basel_III",
                    "reporting_currency": "USD",
                    "local_incorporation": True
                }
            }
            
            response = await integration_client.post(
                "/api/v1/tenants/",
                headers=hsbc_headers,
                json=subsidiary_payload
            )
            
            assert response.status_code == 201
            created_subsidiaries.append(response.json())

        # Step 4: Verify hierarchy structure and access patterns
        # Parent should see all entities
        parent_list_response = await integration_client.get(
            "/api/v1/tenants/",
            headers=hsbc_headers
        )
        
        assert parent_list_response.status_code == 200
        parent_visible_tenants = parent_list_response.json()["items"]
        
        # Should see parent + regional hub + 3 subsidiaries = 5 total (plus any existing test data)
        hsbc_tenant_names = {t["name"] for t in parent_visible_tenants}
        expected_names = {
            "HSBC Global Banking Corporation",
            "HSBC Asia Pacific Holdings",
            "HSBC Bank (Singapore) Limited",
            "HSBC Bank Malaysia Berhad", 
            "HSBC Bank (Thailand) Public Company Limited"
        }
        assert expected_names.issubset(hsbc_tenant_names)

        # Step 5: Verify business rules and compliance
        # Check that subsidiary metadata contains required compliance fields
        for subsidiary in created_subsidiaries:
            metadata = subsidiary["metadata"]
            assert "local_licenses" in metadata
            assert "compliance_framework" in metadata
            assert metadata["compliance_framework"] == "Basel_III"
            assert metadata["local_incorporation"] is True
            assert "ultimate_parent" in metadata

        # Step 6: Test regulatory reporting aggregation
        # Simulate consolidation query that parent bank would run
        await integration_db_session.execute(
            text("SELECT set_current_tenant_id(:tenant_id)"),
            {"tenant_id": parent_id}
        )

        aggregation_result = await integration_db_session.execute(
            text("""
                SELECT 
                    COUNT(*) as total_entities,
                    COUNT(*) FILTER (WHERE tenant_type = 'parent') as parent_entities,
                    COUNT(*) FILTER (WHERE tenant_type = 'subsidiary') as subsidiary_entities,
                    array_agg(DISTINCT tenant_metadata->>'country') as countries,
                    SUM(CAST(tenant_metadata->>'employee_count' AS INTEGER)) as total_employees
                FROM tenants
                WHERE tenant_metadata->>'ultimate_parent' = 'HSBC Global Banking Corporation'
                   OR name = 'HSBC Global Banking Corporation'
            """)
        )
        
        agg_data = aggregation_result.fetchone()
        assert agg_data[0] >= 4  # Parent + hub + subsidiaries
        assert agg_data[1] >= 1   # At least 1 parent
        assert agg_data[2] >= 3   # At least 3 subsidiaries
        assert agg_data[4] >= 75000  # Total employees across all entities

    async def test_banking_competition_isolation_scenario(
        self,
        integration_client: AsyncClient,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        barclays_parent_tenant: Tenant,
        hsbc_headers: dict[str, str],
        barclays_headers: dict[str, str],
        verify_tenant_isolation,
    ) -> None:
        """
        Test banking competition isolation scenario.
        
        Scenario: Competing banks (HSBC vs Barclays) must have complete
        data isolation even when operating in same markets.
        """
        # Create competing operations in same market (Hong Kong)
        
        # HSBC Hong Kong operations
        hsbc_hk_data = {
            "name": "HSBC Hong Kong - Retail Division",
            "tenant_type": "subsidiary",
            "parent_tenant_id": str(hsbc_parent_tenant.tenant_id),
            "metadata": {
                "country": "Hong Kong",
                "region": "Asia Pacific",
                "business_unit": "retail_banking",
                "local_currency": "HKD",
                "market_share_percentage": 28.5,
                "customer_base": 1200000,
                "branch_count": 127,
                "atm_count": 450,
                "products": [
                    "savings_accounts", "mortgages", "personal_loans", 
                    "credit_cards", "investment_products"
                ],
                "competitive_advantages": [
                    "international_network", "digital_banking", "wealth_management"
                ],
                "regulatory_capital_hkd_millions": 89500,
                "loan_portfolio_hkd_billions": 285.6
            }
        }

        hsbc_hk_response = await integration_client.post(
            "/api/v1/tenants/",
            headers=hsbc_headers,
            json=hsbc_hk_data
        )
        assert hsbc_hk_response.status_code == 201

        # Barclays Hong Kong operations
        barclays_hk_data = {
            "name": "Barclays Private Banking Hong Kong",
            "tenant_type": "subsidiary", 
            "parent_tenant_id": str(barclays_parent_tenant.tenant_id),
            "metadata": {
                "country": "Hong Kong",
                "region": "Asia Pacific",
                "business_unit": "private_banking",
                "local_currency": "HKD",
                "market_share_percentage": 8.2,
                "customer_base": 15000,  # Smaller, high-net-worth focus
                "branch_count": 8,
                "minimum_relationship_hkd_millions": 8.0,
                "products": [
                    "private_banking", "wealth_management", "investment_advisory",
                    "structured_products", "foreign_exchange"
                ],
                "competitive_advantages": [
                    "investment_banking_synergies", "global_markets_access"
                ],
                "assets_under_management_hkd_billions": 125.8,
                "client_average_portfolio_hkd_millions": 45.2
            }
        }

        barclays_hk_response = await integration_client.post(
            "/api/v1/tenants/",
            headers=barclays_headers,
            json=barclays_hk_data
        )
        assert barclays_hk_response.status_code == 201

        # Verify complete isolation between competitors
        hsbc_hk_id = UUID(hsbc_hk_response.json()["tenant_id"])
        barclays_hk_id = UUID(barclays_hk_response.json()["tenant_id"])

        # HSBC should not see Barclays operations
        is_isolated_hsbc = await verify_tenant_isolation(
            integration_db_session,
            hsbc_parent_tenant.tenant_id,
            {hsbc_parent_tenant.tenant_id, hsbc_hk_id}
        )
        assert is_isolated_hsbc

        # Barclays should not see HSBC operations
        is_isolated_barclays = await verify_tenant_isolation(
            integration_db_session,
            barclays_parent_tenant.tenant_id,
            {barclays_parent_tenant.tenant_id, barclays_hk_id}
        )
        assert is_isolated_barclays

        # Test competitive intelligence protection
        # HSBC tries to access Barclays data via API
        competitive_access_response = await integration_client.get(
            f"/api/v1/tenants/{barclays_hk_id}",
            headers=hsbc_headers
        )
        assert competitive_access_response.status_code == 404

        # Test market analysis queries show no cross-pollination
        await integration_db_session.execute(
            text("SELECT set_current_tenant_id(:tenant_id)"),
            {"tenant_id": str(hsbc_parent_tenant.tenant_id)}
        )

        market_analysis = await integration_db_session.execute(
            text("""
                SELECT 
                    tenant_metadata->>'country' as country,
                    SUM(CAST(tenant_metadata->>'customer_base' AS INTEGER)) as total_customers,
                    AVG(CAST(tenant_metadata->>'market_share_percentage' AS NUMERIC)) as avg_market_share
                FROM tenants
                WHERE tenant_metadata->>'country' = 'Hong Kong'
                GROUP BY tenant_metadata->>'country'
            """)
        )
        
        hsbc_market_data = market_analysis.fetchone()
        if hsbc_market_data:
            # Should only see HSBC's customer base, not Barclays
            assert hsbc_market_data[1] == 1200000  # Only HSBC customers
            assert float(hsbc_market_data[2]) == 28.5  # Only HSBC market share

    async def test_regulatory_compliance_scenario(
        self,
        integration_client: AsyncClient,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        hsbc_headers: dict[str, str],
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """
        Test regulatory compliance reporting scenario.
        
        Scenario: Bank must demonstrate compliance with Basel III regulations
        across all subsidiaries and provide consolidated reporting.
        """
        # Create subsidiaries with detailed regulatory data
        jurisdictions = [
            {
                "name": "HSBC Bank USA, National Association",
                "country": "United States",
                "regulator": "OCC",
                "capital_requirements": {
                    "minimum_tier1_ratio": 8.0,
                    "actual_tier1_ratio": 12.5,
                    "minimum_total_capital_ratio": 10.5,
                    "actual_total_capital_ratio": 15.8
                },
                "stress_test_results": {
                    "severely_adverse_scenario": {
                        "tier1_ratio_after_stress": 9.2,
                        "pass_threshold": 4.5,
                        "status": "PASS"
                    }
                }
            },
            {
                "name": "HSBC Bank Canada",
                "country": "Canada", 
                "regulator": "OSFI",
                "capital_requirements": {
                    "minimum_tier1_ratio": 8.0,
                    "actual_tier1_ratio": 11.8,
                    "minimum_total_capital_ratio": 10.5,
                    "actual_total_capital_ratio": 14.2
                },
                "liquidity_coverage_ratio": {
                    "minimum_lcr": 100.0,
                    "actual_lcr": 145.8,
                    "status": "COMPLIANT"
                }
            },
            {
                "name": "HSBC Continental Europe",
                "country": "France",
                "regulator": "ECB",
                "capital_requirements": {
                    "minimum_tier1_ratio": 8.0,
                    "actual_tier1_ratio": 13.2,
                    "minimum_total_capital_ratio": 10.5,
                    "actual_total_capital_ratio": 16.4
                },
                "srep_requirements": {
                    "pillar2_requirement": 2.25,
                    "combined_buffer_requirement": 2.5,
                    "total_srep_capital_requirement": 12.75,
                    "status": "COMPLIANT"
                }
            }
        ]

        created_regulatory_entities = []
        for jurisdiction in jurisdictions:
            entity_data = {
                "name": jurisdiction["name"],
                "tenant_type": "subsidiary",
                "parent_tenant_id": str(hsbc_parent_tenant.tenant_id),
                "metadata": {
                    "country": jurisdiction["country"],
                    "primary_regulator": jurisdiction["regulator"],
                    "business_unit": "full_service_bank",
                    "regulatory_framework": "Basel_III",
                    "capital_adequacy": jurisdiction["capital_requirements"],
                    "regulatory_reporting": {
                        "frequency": "quarterly",
                        "next_submission": "2025-10-15",
                        "last_examination": "2025-06-30",
                        "examination_rating": "1",  # Highest rating
                        "supervisory_actions": []
                    },
                    "compliance_status": {
                        "capital_adequacy": "COMPLIANT",
                        "liquidity_requirements": "COMPLIANT", 
                        "operational_risk": "COMPLIANT",
                        "market_risk": "COMPLIANT",
                        "credit_risk": "COMPLIANT"
                    }
                }
            }
            
            # Add jurisdiction-specific regulatory data
            if "stress_test_results" in jurisdiction:
                entity_data["metadata"]["stress_test_results"] = jurisdiction["stress_test_results"]
            if "liquidity_coverage_ratio" in jurisdiction:
                entity_data["metadata"]["liquidity_coverage_ratio"] = jurisdiction["liquidity_coverage_ratio"]
            if "srep_requirements" in jurisdiction:
                entity_data["metadata"]["srep_requirements"] = jurisdiction["srep_requirements"]

            response = await integration_client.post(
                "/api/v1/tenants/",
                headers=hsbc_headers,
                json=entity_data
            )
            
            assert response.status_code == 201
            created_regulatory_entities.append(response.json())

        # Generate consolidated regulatory report
        await set_tenant_context(integration_db_session, hsbc_parent_tenant.tenant_id)

        # Consolidated capital adequacy report
        capital_report = await integration_db_session.execute(
            text("""
                SELECT 
                    tenant_metadata->>'country' as jurisdiction,
                    tenant_metadata->>'primary_regulator' as regulator,
                    CAST(tenant_metadata->'capital_adequacy'->>'actual_tier1_ratio' AS NUMERIC) as tier1_ratio,
                    CAST(tenant_metadata->'capital_adequacy'->>'actual_total_capital_ratio' AS NUMERIC) as total_capital_ratio,
                    tenant_metadata->'compliance_status'->>'capital_adequacy' as capital_compliance
                FROM tenants
                WHERE tenant_metadata->'capital_adequacy' IS NOT NULL
                ORDER BY tenant_metadata->>'country'
            """)
        )
        
        capital_data = capital_report.fetchall()
        assert len(capital_data) == 3  # Three jurisdictions
        
        # Verify all entities are compliant
        for row in capital_data:
            jurisdiction, regulator, tier1, total_cap, compliance = row
            assert compliance == "COMPLIANT"
            assert tier1 >= 8.0  # Minimum Basel III requirement
            assert total_cap >= 10.5  # Minimum total capital requirement

        # Stress test aggregation report
        stress_test_report = await integration_db_session.execute(
            text("""
                SELECT 
                    COUNT(*) as entities_with_stress_tests,
                    COUNT(*) FILTER (WHERE tenant_metadata->'stress_test_results'->'severely_adverse_scenario'->>'status' = 'PASS') as entities_passed
                FROM tenants
                WHERE tenant_metadata->'stress_test_results' IS NOT NULL
            """)
        )
        
        stress_data = stress_test_report.fetchone()
        entities_tested, entities_passed = stress_data
        assert entities_tested >= 1  # At least US entity has stress tests
        assert entities_passed == entities_tested  # All tested entities passed

        # Compliance dashboard summary
        compliance_summary = await integration_db_session.execute(
            text("""
                SELECT 
                    COUNT(*) as total_entities,
                    COUNT(*) FILTER (WHERE tenant_metadata->'compliance_status'->>'capital_adequacy' = 'COMPLIANT') as capital_compliant,
                    COUNT(*) FILTER (WHERE tenant_metadata->'compliance_status'->>'liquidity_requirements' = 'COMPLIANT') as liquidity_compliant,
                    COUNT(*) FILTER (WHERE tenant_metadata->'compliance_status'->>'operational_risk' = 'COMPLIANT') as operational_risk_compliant,
                    COUNT(*) FILTER (WHERE tenant_metadata->'regulatory_reporting'->>'examination_rating' = '1') as highest_rated
                FROM tenants
                WHERE tenant_metadata->'compliance_status' IS NOT NULL
            """)
        )
        
        compliance_data = compliance_summary.fetchone()
        total, capital_ok, liquidity_ok, op_risk_ok, highest_rated = compliance_data
        
        assert total == 3  # Three regulatory entities
        assert capital_ok == total  # 100% capital compliance
        assert liquidity_ok == total  # 100% liquidity compliance
        assert op_risk_ok == total  # 100% operational risk compliance
        assert highest_rated == total  # All have highest examination rating

        await clear_tenant_context(integration_db_session)

    async def test_merger_acquisition_scenario(
        self,
        integration_client: AsyncClient,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        hsbc_headers: dict[str, str],
        performance_threshold_ms: int,
    ) -> None:
        """
        Test merger and acquisition integration scenario.
        
        Scenario: HSBC acquires a regional bank and needs to integrate
        it into their tenant hierarchy with proper data migration.
        """
        # Step 1: Create target acquisition bank (independent entity)
        target_bank_data = {
            "name": "Regional Trust Bank Limited",
            "tenant_type": "parent",  # Currently independent
            "metadata": {
                "country": "United Kingdom",
                "business_type": "regional_bank",
                "established_year": 1987,
                "employee_count": 2500,
                "branches": 45,
                "customer_base": 125000,
                "total_assets_gbp_millions": 8500,
                "loan_portfolio_gbp_millions": 6200,
                "deposit_base_gbp_millions": 7200,
                "specialization": "small_business_banking",
                "market_focus": "northern_england",
                "acquisition_status": "target",
                "due_diligence_completed": "2025-07-15",
                "integration_phase": "pre_acquisition"
            }
        }

        # Create acquisition target with temporary parent context
        temp_headers = {"X-Tenant-ID": "acquisition-temp", "Content-Type": "application/json"}
        
        target_response = await integration_client.post(
            "/api/v1/tenants/",
            headers=temp_headers,
            json=target_bank_data
        )
        assert target_response.status_code == 201
        
        target_bank = target_response.json()
        target_bank_id = target_bank["tenant_id"]

        # Step 2: Create subsidiary entities of target bank
        target_subsidiaries = [
            {
                "name": "Regional Trust Business Banking",
                "business_unit": "business_banking",
                "customer_segment": "SME",
                "loan_portfolio_gbp_millions": 4200
            },
            {
                "name": "Regional Trust Retail Services", 
                "business_unit": "retail_banking",
                "customer_segment": "individual",
                "deposit_base_gbp_millions": 3600
            }
        ]

        target_subsidiary_ids = []
        for sub_data in target_subsidiaries:
            subsidiary_payload = {
                "name": sub_data["name"],
                "tenant_type": "subsidiary",
                "parent_tenant_id": target_bank_id,
                "metadata": {
                    "country": "United Kingdom",
                    "business_unit": sub_data["business_unit"],
                    "customer_segment": sub_data["customer_segment"],
                    "integration_phase": "pre_acquisition",
                    **{k: v for k, v in sub_data.items() if k not in ["name", "business_unit", "customer_segment"]}
                }
            }
            
            response = await integration_client.post(
                "/api/v1/tenants/",
                headers=temp_headers,
                json=subsidiary_payload
            )
            assert response.status_code == 201
            target_subsidiary_ids.append(response.json()["tenant_id"])

        # Step 3: Simulate acquisition completion - convert to HSBC subsidiary
        start_time = time.time()
        
        acquisition_update = {
            "name": "HSBC Regional Trust Bank Limited",
            "metadata": {
                "country": "United Kingdom",
                "business_type": "acquired_regional_bank",
                "established_year": 1987,
                "employee_count": 2500,
                "branches": 45,
                "customer_base": 125000,
                "total_assets_gbp_millions": 8500,
                "loan_portfolio_gbp_millions": 6200,
                "deposit_base_gbp_millions": 7200,
                "specialization": "small_business_banking", 
                "market_focus": "northern_england",
                "acquisition_status": "completed",
                "acquisition_date": "2025-08-15",
                "integration_phase": "post_acquisition",
                "acquiring_entity": "HSBC Holdings plc",
                "integration_milestones": {
                    "legal_completion": "2025-08-15",
                    "systems_integration_target": "2025-11-15",
                    "brand_conversion_target": "2026-02-15",
                    "full_integration_target": "2026-05-15"
                },
                "synergy_targets": {
                    "cost_synergies_gbp_millions": 45.2,
                    "revenue_synergies_gbp_millions": 28.8,
                    "integration_costs_gbp_millions": 125.0
                }
            }
        }

        # Update target bank to be HSBC subsidiary
        integration_update = await integration_client.put(
            f"/api/v1/tenants/{target_bank_id}",
            headers=hsbc_headers,  # Now using HSBC context
            json=acquisition_update
        )
        
        end_time = time.time()
        assert integration_update.status_code == 200
        assert (end_time - start_time) * 1000 <= performance_threshold_ms

        # Step 4: Update subsidiary entities to reflect new ownership
        for i, subsidiary_id in enumerate(target_subsidiary_ids):
            subsidiary_update = {
                "name": f"HSBC Regional Trust {target_subsidiaries[i]['name'].split(' ')[-1]}",
                "metadata": {
                    "country": "United Kingdom",
                    "business_unit": target_subsidiaries[i]["business_unit"],
                    "customer_segment": target_subsidiaries[i]["customer_segment"],
                    "integration_phase": "post_acquisition",
                    "acquired_from": "Regional Trust Bank Limited",
                    "acquiring_entity": "HSBC Holdings plc",
                    "integration_priority": "high" if i == 0 else "medium",
                    "systems_integration_status": "planning",
                    "staff_retention_rate": 92.5,
                    **{k: v for k, v in target_subsidiaries[i].items() 
                       if k not in ["name", "business_unit", "customer_segment"]}
                }
            }
            
            sub_update_response = await integration_client.put(
                f"/api/v1/tenants/{subsidiary_id}",
                headers=hsbc_headers,
                json=subsidiary_update
            )
            assert sub_update_response.status_code == 200

        # Step 5: Verify post-acquisition hierarchy and reporting
        await integration_db_session.execute(
            text("SELECT set_current_tenant_id(:tenant_id)"),
            {"tenant_id": str(hsbc_parent_tenant.tenant_id)}
        )

        # Consolidation report including acquired entities
        post_acquisition_report = await integration_db_session.execute(
            text("""
                SELECT 
                    COUNT(*) FILTER (WHERE tenant_metadata->>'integration_phase' = 'post_acquisition') as acquired_entities,
                    SUM(CAST(tenant_metadata->>'employee_count' AS INTEGER)) FILTER (WHERE tenant_metadata->>'integration_phase' = 'post_acquisition') as acquired_employees,
                    SUM(CAST(tenant_metadata->>'total_assets_gbp_millions' AS NUMERIC)) FILTER (WHERE tenant_metadata->>'total_assets_gbp_millions' IS NOT NULL) as total_assets_gbp_millions
                FROM tenants
                WHERE tenant_metadata IS NOT NULL
            """)
        )
        
        consolidation_data = post_acquisition_report.fetchone()
        acquired_entities, acquired_employees, total_assets = consolidation_data
        
        assert acquired_entities >= 3  # Target bank + subsidiaries
        assert acquired_employees >= 2500  # Acquired employees
        if total_assets:
            assert total_assets >= 8500  # At least the acquired assets

        # Integration tracking report
        integration_status = await integration_db_session.execute(
            text("""
                SELECT 
                    tenant_metadata->>'name' as entity_name,
                    tenant_metadata->>'integration_phase' as phase,
                    tenant_metadata->>'systems_integration_status' as systems_status,
                    tenant_metadata->'integration_milestones'->>'systems_integration_target' as integration_target
                FROM tenants
                WHERE tenant_metadata->'integration_phase' = '"post_acquisition"'
                ORDER BY name
            """)
        )
        
        integration_data = integration_status.fetchall()
        assert len(integration_data) >= 1  # At least one acquired entity
        
        # Verify all acquired entities are in post-acquisition phase
        for row in integration_data:
            entity_name, phase, systems_status, target_date = row
            assert phase == "post_acquisition"
            # Systems integration should be planned or in progress
            if systems_status:
                assert systems_status in ["planning", "in_progress", "completed"]

    async def test_cross_border_compliance_scenario(
        self,
        integration_client: AsyncClient,
        integration_db_session: AsyncSession,
        hsbc_parent_tenant: Tenant,
        hsbc_headers: dict[str, str],
        set_tenant_context,
        clear_tenant_context,
    ) -> None:
        """
        Test cross-border compliance and reporting scenario.
        
        Scenario: HSBC must comply with different regulatory requirements
        across multiple jurisdictions while maintaining consolidated oversight.
        """
        # Create entities in different regulatory jurisdictions
        jurisdictional_entities = [
            {
                "name": "HSBC Middle East Limited",
                "country": "United Arab Emirates",
                "regulatory_framework": "UAE_Central_Bank",
                "islamic_banking": True,
                "sanctions_compliance": {
                    "ofac_compliance": True,
                    "eu_sanctions": True,
                    "un_sanctions": True,
                    "local_sanctions": ["UAE_sanctions_list"]
                },
                "aml_kyc": {
                    "enhanced_due_diligence_threshold_usd": 15000,
                    "suspicious_activity_reports_ytd": 24,
                    "customer_screening_frequency": "monthly"
                }
            },
            {
                "name": "HSBC Bank Brasil S.A.",
                "country": "Brazil",
                "regulatory_framework": "BACEN",
                "local_requirements": {
                    "reserve_requirements_percentage": 4.5,
                    "operational_risk_capital_brl_millions": 850,
                    "stress_test_frequency": "semi_annual"
                },
                "tax_compliance": {
                    "corporate_tax_rate": 34.0,
                    "financial_transactions_tax": 0.38,
                    "digital_bookkeeping_required": True
                }
            },
            {
                "name": "HSBC Bank (China) Company Limited",
                "country": "China",
                "regulatory_framework": "PBOC_CBIRC", 
                "foreign_bank_restrictions": {
                    "rmb_business_license": True,
                    "local_incorporation_required": True,
                    "minimum_capital_rmb_billions": 1.0
                },
                "capital_controls": {
                    "daily_fx_position_limit_usd_millions": 50,
                    "cross_border_rmb_settlement": True,
                    "qualified_institutional_investor": True
                }
            }
        ]

        created_entities = []
        for entity_data in jurisdictional_entities:
            entity_payload = {
                "name": entity_data["name"],
                "tenant_type": "subsidiary",
                "parent_tenant_id": str(hsbc_parent_tenant.tenant_id),
                "metadata": {
                    "country": entity_data["country"],
                    "regulatory_framework": entity_data["regulatory_framework"],
                    "business_unit": "international_banking",
                    "compliance_officer": f"CCO-{entity_data['country'][:3].upper()}",
                    "regulatory_reporting_frequency": "monthly",
                    "last_regulatory_exam": "2025-04-15",
                    "next_regulatory_exam": "2025-10-15",
                    **{k: v for k, v in entity_data.items() 
                       if k not in ["name", "country", "regulatory_framework"]}
                }
            }
            
            response = await integration_client.post(
                "/api/v1/tenants/",
                headers=hsbc_headers,
                json=entity_payload
            )
            assert response.status_code == 201
            created_entities.append(response.json())

        # Generate global compliance dashboard
        await set_tenant_context(integration_db_session, hsbc_parent_tenant.tenant_id)

        # Sanctions compliance aggregation
        sanctions_report = await integration_db_session.execute(
            text("""
                SELECT 
                    tenant_metadata->>'country' as jurisdiction,
                    tenant_metadata->'sanctions_compliance'->>'ofac_compliance' as ofac_compliant,
                    tenant_metadata->'sanctions_compliance'->>'eu_sanctions' as eu_compliant,
                    tenant_metadata->'sanctions_compliance'->>'un_sanctions' as un_compliant
                FROM tenants
                WHERE tenant_metadata->'sanctions_compliance' IS NOT NULL
            """)
        )
        
        sanctions_data = sanctions_report.fetchall()
        for row in sanctions_data:
            jurisdiction, ofac, eu, un = row
            # All entities should be compliant with major sanctions regimes
            if ofac: assert ofac == "true"
            if eu: assert eu == "true"
            if un: assert un == "true"

        # AML/KYC compliance summary
        aml_report = await integration_db_session.execute(
            text("""
                SELECT 
                    COUNT(*) as entities_with_aml,
                    AVG(CAST(tenant_metadata->'aml_kyc'->>'suspicious_activity_reports_ytd' AS INTEGER)) as avg_sars_ytd
                FROM tenants
                WHERE tenant_metadata->'aml_kyc' IS NOT NULL
            """)
        )
        
        aml_data = aml_report.fetchone()
        if aml_data[0] > 0:
            assert aml_data[1] >= 0  # Average SARs should be non-negative

        # Cross-border regulatory framework diversity
        frameworks_report = await integration_db_session.execute(
            text("""
                SELECT 
                    COUNT(DISTINCT tenant_metadata->>'regulatory_framework') as unique_frameworks,
                    array_agg(DISTINCT tenant_metadata->>'regulatory_framework') as frameworks_list
                FROM tenants
                WHERE tenant_metadata->>'regulatory_framework' IS NOT NULL
            """)
        )
        
        frameworks_data = frameworks_report.fetchone()
        unique_count, frameworks_list = frameworks_data
        assert unique_count >= 3  # At least 3 different regulatory frameworks
        
        expected_frameworks = {"UAE_Central_Bank", "BACEN", "PBOC_CBIRC"}
        actual_frameworks = set(frameworks_list) if frameworks_list else set()
        assert expected_frameworks.issubset(actual_frameworks)

        # Consolidated risk assessment
        risk_assessment = await integration_db_session.execute(
            text("""
                SELECT 
                    tenant_metadata->>'country' as country,
                    CASE 
                        WHEN tenant_metadata->>'country' = 'United Arab Emirates' THEN 'HIGH'
                        WHEN tenant_metadata->>'country' = 'Brazil' THEN 'MEDIUM'
                        WHEN tenant_metadata->>'country' = 'China' THEN 'HIGH'
                        ELSE 'LOW'
                    END as regulatory_complexity,
                    CASE 
                        WHEN tenant_metadata->'sanctions_compliance' IS NOT NULL THEN 'ENHANCED'
                        ELSE 'STANDARD'
                    END as compliance_level
                FROM tenants
                WHERE tenant_metadata->>'country' IN ('United Arab Emirates', 'Brazil', 'China')
                ORDER BY tenant_metadata->>'country'
            """)
        )
        
        risk_data = risk_assessment.fetchall()
        assert len(risk_data) == 3  # Three jurisdictions
        
        high_risk_count = sum(1 for row in risk_data if row[1] == 'HIGH')
        assert high_risk_count >= 2  # UAE and China are high complexity
        
        enhanced_compliance_count = sum(1 for row in risk_data if row[2] == 'ENHANCED')
        assert enhanced_compliance_count >= 1  # At least UAE has enhanced compliance

        await clear_tenant_context(integration_db_session)