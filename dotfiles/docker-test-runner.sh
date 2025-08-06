#!/bin/bash
# Docker test runner with statistics tracking
# Provides clear pass/fail counts and formatted output

set -o pipefail

# ANSI color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Test statistics
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

# Test results array
declare -a TEST_RESULTS

# Function to run a test and track results
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_failure="${3:-false}"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -e "${BLUE}[TEST ${TOTAL_TESTS}]${NC} Running: ${BOLD}$test_name${NC}"
    
    # Execute the test command
    if eval "$test_command" > /tmp/test_output_$$.txt 2>&1; then
        if [ "$expected_failure" = "true" ]; then
            # Test passed but was expected to fail
            echo -e "  ${RED}✗ FAILED${NC} - Test passed but was expected to fail"
            FAILED_TESTS=$((FAILED_TESTS + 1))
            TEST_RESULTS+=("FAIL:$test_name:Expected failure but passed")
        else
            # Test passed as expected
            echo -e "  ${GREEN}✓ PASSED${NC}"
            PASSED_TESTS=$((PASSED_TESTS + 1))
            TEST_RESULTS+=("PASS:$test_name")
        fi
    else
        if [ "$expected_failure" = "true" ]; then
            # Test failed as expected
            echo -e "  ${GREEN}✓ PASSED${NC} (expected failure)"
            PASSED_TESTS=$((PASSED_TESTS + 1))
            TEST_RESULTS+=("PASS:$test_name:Failed as expected")
        else
            # Test failed unexpectedly
            echo -e "  ${RED}✗ FAILED${NC}"
            echo -e "  ${YELLOW}Output:${NC}"
            cat /tmp/test_output_$$.txt | sed 's/^/    /'
            FAILED_TESTS=$((FAILED_TESTS + 1))
            TEST_RESULTS+=("FAIL:$test_name:$(head -n1 /tmp/test_output_$$.txt)")
        fi
    fi
    
    rm -f /tmp/test_output_$$.txt
    echo ""
}

# Function to skip a test
skip_test() {
    local test_name="$1"
    local reason="$2"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    SKIPPED_TESTS=$((SKIPPED_TESTS + 1))
    echo -e "${BLUE}[TEST ${TOTAL_TESTS}]${NC} Skipping: ${BOLD}$test_name${NC}"
    echo -e "  ${YELLOW}⊘ SKIPPED${NC} - $reason"
    TEST_RESULTS+=("SKIP:$test_name:$reason")
    echo ""
}

# Print test summary
print_summary() {
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}TEST EXECUTION SUMMARY${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # Calculate pass rate
    if [ $TOTAL_TESTS -gt 0 ]; then
        PASS_RATE=$(( (PASSED_TESTS * 100) / TOTAL_TESTS ))
    else
        PASS_RATE=0
    fi
    
    # Print statistics with color coding
    echo -e "Total Tests:    ${BOLD}$TOTAL_TESTS${NC}"
    
    if [ $PASSED_TESTS -gt 0 ]; then
        echo -e "Passed:         ${GREEN}${BOLD}$PASSED_TESTS${NC} ${GREEN}✓${NC}"
    else
        echo -e "Passed:         ${BOLD}$PASSED_TESTS${NC}"
    fi
    
    if [ $FAILED_TESTS -gt 0 ]; then
        echo -e "Failed:         ${RED}${BOLD}$FAILED_TESTS${NC} ${RED}✗${NC}"
    else
        echo -e "Failed:         ${BOLD}$FAILED_TESTS${NC}"
    fi
    
    if [ $SKIPPED_TESTS -gt 0 ]; then
        echo -e "Skipped:        ${YELLOW}${BOLD}$SKIPPED_TESTS${NC} ${YELLOW}⊘${NC}"
    else
        echo -e "Skipped:        ${BOLD}$SKIPPED_TESTS${NC}"
    fi
    
    echo -e "Pass Rate:      ${BOLD}$PASS_RATE%${NC}"
    
    # Overall result
    echo ""
    if [ $FAILED_TESTS -eq 0 ] && [ $TOTAL_TESTS -gt 0 ]; then
        echo -e "${GREEN}${BOLD}✅ ALL TESTS PASSED!${NC}"
    elif [ $FAILED_TESTS -gt 0 ]; then
        echo -e "${RED}${BOLD}❌ TESTS FAILED${NC}"
        echo ""
        echo -e "${BOLD}Failed Tests:${NC}"
        for result in "${TEST_RESULTS[@]}"; do
            IFS=':' read -r status name reason <<< "$result"
            if [ "$status" = "FAIL" ]; then
                echo -e "  ${RED}✗${NC} $name"
                if [ -n "$reason" ] && [ "$reason" != "$name" ]; then
                    echo -e "    ${YELLOW}↳ $reason${NC}"
                fi
            fi
        done
    else
        echo -e "${YELLOW}${BOLD}⚠ NO TESTS EXECUTED${NC}"
    fi
    
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Export functions for use in Docker container
export -f run_test
export -f skip_test
export -f print_summary

# Main execution
main() {
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}DOTFILES DOCKER INTEGRATION TESTS${NC}"
    echo -e "Variant: ${BLUE}${DOTFILES_VARIANT:-default}${NC}"
    echo -e "Test Mode: ${BLUE}${DOTFILES_TEST_MODE:-true}${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # Source the actual test file if it exists
    if [ -f "/home/testuser/dotfiles/docker-tests.sh" ]; then
        source /home/testuser/dotfiles/docker-tests.sh
    else
        # Fallback to inline tests if no test file exists
        
        # Test 1: Version check
        run_test "Version Check" "uv run dotfiles-sync --version"
        
        # Test 2: Configuration validation
        run_test "Configuration Validation" "uv run dotfiles-sync --config test-config.toml validate"
        
        # Test 3: Dry run (default)
        run_test "Dry Run Mode" "uv run dotfiles-sync --config test-config.toml sync"
        
        # Test 4: Verify dry run safety
        run_test "Dry Run Safety Check" "! test -f ~/.test-zshrc && ! test -f ~/.test-gitconfig && ! test -f ~/.test-aliases"
        
        # Test 5: Create backup test file
        run_test "Backup Setup" "echo '# Original file' > ~/.test-gitconfig"
        
        # Test 6: Apply changes
        run_test "Apply Operations" "uv run dotfiles-sync --config test-config.toml --apply sync"
        
        # Test 7: Verify link creation
        run_test "Verify Link Creation" "test -L ~/.test-zshrc"
        
        # Test 8: Verify copy creation
        run_test "Verify Copy Creation" "test -f ~/.test-gitconfig"
        
        # Test 9: Verify symlink target
        run_test "Verify Symlink Target" "test \"\$(readlink ~/.test-zshrc)\" = \"/home/testuser/dotfiles/test-dotfiles/test-zshrc\""
        
        # Test 10: Check backup directory
        if [ -d ~/.local/state/dotfiles/backups ]; then
            run_test "Backup Directory Exists" "ls ~/.local/state/dotfiles/backups/ > /dev/null"
        else
            skip_test "Backup Directory Check" "No backups created for this test case"
        fi
        
        # Test 11: Safety validation (expected to fail)
        run_test "Safety Validation (Invalid Path)" \
            "printf '[package]\nname=\"test\"\nversion=\"1.0.0\"\n[security]\nblacklist_paths=[\"/etc/**\"]\n[[step]]\nop=\"copy\"\nsrc=\"test-dotfiles/test-gitconfig\"\ndst=\"/etc/invalid\"\nvariants=[\"all\"]\n' | uv run dotfiles-sync --config /dev/stdin sync" \
            "true"
        
        # Test 12: Status command
        run_test "Status Command" "uv run dotfiles-sync status"
        
        # Test 13: Unit tests
        run_test "Unit Test Suite" "uv run pytest tests/unit/ -q"
        
        # Test 14: Safety component tests
        if [ -d tests/unit/safety ]; then
            run_test "Safety Component Tests" "uv run pytest tests/unit/safety/ -q"
        else
            skip_test "Safety Component Tests" "Safety tests not yet implemented"
        fi
    fi
    
    # Print final summary
    print_summary
    
    # Save results to JSON
    cat > /tmp/test-results.json <<EOF
{
  "suite": "Docker Integration Tests",
  "variant": "${DOTFILES_VARIANT:-default}",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "total_tests": $TOTAL_TESTS,
  "passed": $PASSED_TESTS,
  "failed": $FAILED_TESTS,
  "skipped": $SKIPPED_TESTS,
  "pass_rate": $PASS_RATE,
  "status": $([ $FAILED_TESTS -eq 0 ] && echo '"SUCCESS"' || echo '"FAILURE"')
}
EOF
    
    # Exit with appropriate code
    if [ $FAILED_TESTS -gt 0 ]; then
        exit 1
    else
        exit 0
    fi
}

# Run main if executed directly
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi