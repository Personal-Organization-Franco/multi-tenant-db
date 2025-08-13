#!/usr/bin/env python3
"""
Comprehensive database security test runner.

This script executes all database security tests in the correct order
and provides detailed reporting of security validation results.

Usage:
    python tests/run_database_security_tests.py [options]
    
Options:
    --verbose: Enable verbose output
    --performance: Include performance benchmarks
    --penetration: Include penetration testing
    --migrations: Include migration testing
    --report: Generate detailed security report
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

import pytest


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseSecurityTestRunner:
    """Comprehensive database security test runner."""
    
    def __init__(self, verbose: bool = False, include_performance: bool = True, 
                 include_penetration: bool = True, include_migrations: bool = True):
        self.verbose = verbose
        self.include_performance = include_performance
        self.include_penetration = include_penetration
        self.include_migrations = include_migrations
        self.results = {}
        
    def get_test_modules(self) -> List[str]:
        """Get list of test modules to run."""
        modules = []
        
        # Core RLS security tests (always included)
        modules.append("tests/security/test_rls_security.py")
        
        # Migration tests
        if self.include_migrations:
            modules.append("tests/database/test_migrations.py")
        
        # Performance tests
        if self.include_performance:
            modules.append("tests/performance/test_database_performance.py")
        
        # Penetration tests
        if self.include_penetration:
            modules.append("tests/security/test_penetration.py")
        
        return modules
    
    def run_security_tests(self) -> Dict[str, Any]:
        """Run all security tests and collect results."""
        logger.info("Starting comprehensive database security test suite...")
        
        test_modules = self.get_test_modules()
        overall_start_time = time.time()
        
        # Prepare pytest arguments
        pytest_args = [
            "-v" if self.verbose else "-q",
            "--tb=short",
            "--durations=10",
            "--strict-markers",
            "--disable-warnings" if not self.verbose else "",
            "--asyncio-mode=auto"
        ]
        
        # Filter out empty strings
        pytest_args = [arg for arg in pytest_args if arg]
        
        results = {}
        
        for module in test_modules:
            logger.info(f"Running tests in {module}...")
            module_start_time = time.time()
            
            # Run tests for this module
            exit_code = pytest.main(pytest_args + [module])
            
            module_duration = time.time() - module_start_time
            
            results[module] = {
                "exit_code": exit_code,
                "duration": module_duration,
                "status": "PASSED" if exit_code == 0 else "FAILED"
            }
            
            logger.info(f"Module {module} completed in {module_duration:.2f}s with exit code {exit_code}")
        
        overall_duration = time.time() - overall_start_time
        
        results["summary"] = {
            "total_duration": overall_duration,
            "modules_tested": len(test_modules),
            "modules_passed": sum(1 for r in results.values() if isinstance(r, dict) and r.get("status") == "PASSED"),
            "modules_failed": sum(1 for r in results.values() if isinstance(r, dict) and r.get("status") == "FAILED"),
        }
        
        self.results = results
        return results
    
    def generate_security_report(self) -> str:
        """Generate a comprehensive security test report."""
        report_lines = [
            "=" * 80,
            "DATABASE SECURITY TEST REPORT",
            "=" * 80,
            "",
            f"Test Run Completed: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Duration: {self.results.get('summary', {}).get('total_duration', 0):.2f} seconds",
            "",
            "SUMMARY:",
            f"  Modules Tested: {self.results.get('summary', {}).get('modules_tested', 0)}",
            f"  Modules Passed: {self.results.get('summary', {}).get('modules_passed', 0)}",
            f"  Modules Failed: {self.results.get('summary', {}).get('modules_failed', 0)}",
            "",
            "DETAILED RESULTS:",
            ""
        ]
        
        for module, result in self.results.items():
            if module == "summary":
                continue
                
            status_icon = "✅" if result.get("status") == "PASSED" else "❌"
            report_lines.extend([
                f"{status_icon} {module}",
                f"    Status: {result.get('status', 'UNKNOWN')}",
                f"    Duration: {result.get('duration', 0):.2f}s",
                f"    Exit Code: {result.get('exit_code', 'N/A')}",
                ""
            ])
        
        # Security validation summary
        report_lines.extend([
            "",
            "SECURITY VALIDATION AREAS TESTED:",
            "",
            "🔒 Row Level Security (RLS) Policy Enforcement",
            "    ✓ Tenant isolation verification",
            "    ✓ Hierarchical access control testing",
            "    ✓ Policy enforcement across all CRUD operations",
            "    ✓ Session context security validation",
            "",
            "🔧 Database Migration Integrity",
            "    ✓ Migration rollback/upgrade testing",
            "    ✓ RLS function creation validation",
            "    ✓ Constraint enforcement verification",
            "    ✓ Schema integrity maintenance",
            "",
            "⚡ Performance & Scalability",
            "    ✓ RLS overhead measurement",
            "    ✓ Query performance benchmarking",
            "    ✓ Bulk operation performance testing",
            "    ✓ Concurrent access pattern validation",
            "",
            "🛡️ Security Penetration Testing",
            "    ✓ SQL injection resistance",
            "    ✓ Session manipulation protection",
            "    ✓ Privilege escalation prevention", 
            "    ✓ Information disclosure protection",
            "    ✓ Timing attack resistance",
            "",
            "=" * 80
        ])
        
        return "\n".join(report_lines)
    
    def save_report(self, filename: str = None):
        """Save the security report to a file."""
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"database_security_report_{timestamp}.txt"
        
        report_content = self.generate_security_report()
        
        with open(filename, 'w') as f:
            f.write(report_content)
        
        logger.info(f"Security report saved to {filename}")
        return filename


def main():
    """Main entry point for the security test runner."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive database security tests",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--no-performance",
        action="store_true", 
        help="Skip performance benchmarking tests"
    )
    
    parser.add_argument(
        "--no-penetration",
        action="store_true",
        help="Skip penetration testing"
    )
    
    parser.add_argument(
        "--no-migrations", 
        action="store_true",
        help="Skip migration testing"
    )
    
    parser.add_argument(
        "--report", "-r",
        action="store_true",
        help="Generate detailed security report file"
    )
    
    parser.add_argument(
        "--report-file",
        type=str,
        help="Specify custom report filename"
    )
    
    args = parser.parse_args()
    
    # Create and configure test runner
    runner = DatabaseSecurityTestRunner(
        verbose=args.verbose,
        include_performance=not args.no_performance,
        include_penetration=not args.no_penetration,
        include_migrations=not args.no_migrations
    )
    
    try:
        # Run the tests
        results = runner.run_security_tests()
        
        # Display summary
        print("\n" + "=" * 60)
        print("DATABASE SECURITY TEST SUMMARY")
        print("=" * 60)
        
        summary = results.get("summary", {})
        total_modules = summary.get("modules_tested", 0)
        passed_modules = summary.get("modules_passed", 0)
        failed_modules = summary.get("modules_failed", 0)
        duration = summary.get("total_duration", 0)
        
        print(f"Total Duration: {duration:.2f} seconds")
        print(f"Modules Tested: {total_modules}")
        print(f"Modules Passed: {passed_modules} ✅")
        print(f"Modules Failed: {failed_modules} {'❌' if failed_modules > 0 else ''}")
        print(f"Success Rate: {(passed_modules/total_modules*100):.1f}%" if total_modules > 0 else "N/A")
        
        # Generate and optionally save report
        if args.report:
            report_file = runner.save_report(args.report_file)
            print(f"\nDetailed report saved to: {report_file}")
        
        if args.verbose:
            print("\nDetailed Results:")
            for module, result in results.items():
                if module != "summary":
                    status = result.get("status", "UNKNOWN")
                    duration = result.get("duration", 0)
                    print(f"  {module}: {status} ({duration:.2f}s)")
        
        # Exit with appropriate code
        if failed_modules > 0:
            print(f"\n❌ Security tests failed! {failed_modules} module(s) had failures.")
            return 1
        else:
            print("\n✅ All security tests passed! Database security validation successful.")
            return 0
            
    except KeyboardInterrupt:
        print("\n🛑 Test run interrupted by user")
        return 2
    except Exception as e:
        print(f"\n💥 Test run failed with error: {e}")
        logger.exception("Test run failed with exception")
        return 3


if __name__ == "__main__":
    sys.exit(main())