#!/bin/bash
# MindScribe Testing Runner Script

set -e  # Exit on any error

echo "🧪 MindScribe Testing Suite"
echo "=========================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Install/upgrade dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt > /dev/null 2>&1

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}⚠️  .env file not found!${NC}"
    echo "Please create .env file from env.example and configure your settings:"
    echo "  cp env.example .env"
    echo "  # Edit .env with your API keys and database URLs"
    echo ""
    echo "For quick testing with mock data, you can use:"
    echo "  cp test.env .env"
    echo "  # But remember to set real API keys"
    exit 1
fi

# Function to run unit tests
run_unit_tests() {
    echo -e "\n${YELLOW}Running unit tests...${NC}"
    if python -m pytest tests/test_mindscribe.py::TestProcessingState -v; then
        echo -e "${GREEN}✅ Processing State tests passed${NC}"
    else
        echo -e "${RED}❌ Processing State tests failed${NC}"
        return 1
    fi

    if python -m pytest tests/test_mindscribe.py::TestSummaryFunctions -v; then
        echo -e "${GREEN}✅ Summary Functions tests passed${NC}"
    else
        echo -e "${RED}❌ Summary Functions tests failed${NC}"
        return 1
    fi

    if python -m pytest tests/test_mindscribe.py::TestLLMIntegration -v; then
        echo -e "${GREEN}✅ LLM Integration tests passed${NC}"
    else
        echo -e "${RED}❌ LLM Integration tests failed${NC}"
        return 1
    fi

    if python -m pytest tests/test_mindscribe.py::TestHandler -v; then
        echo -e "${GREEN}✅ Handler tests passed${NC}"
    else
        echo -e "${RED}❌ Handler tests failed${NC}"
        return 1
    fi
}

# Function to run integration test with real session
run_integration_test() {
    local session_id=${1:-"test-session-$(date +%s)"}
    
    echo -e "\n${YELLOW}Running integration test with session: $session_id${NC}"
    
    if python tests/test_local.py --session-id "$session_id" --create-mock --user-id "test-user-$(date +%s)"; then
        echo -e "${GREEN}✅ Integration test passed${NC}"
    else
        echo -e "${RED}❌ Integration test failed${NC}"
        return 1
    fi
}

# Function to show help
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --unit-only          Run only unit tests"
    echo "  --integration-only   Run only integration test"
    echo "  --session-id ID      Use specific session ID for integration test"
    echo "  --help               Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run all tests"
    echo "  $0 --unit-only                       # Run only unit tests"
    echo "  $0 --integration-only                # Run integration test with mock data"
    echo "  $0 --session-id my-session-123       # Test specific session"
}

# Parse command line arguments
UNIT_ONLY=false
INTEGRATION_ONLY=false
SESSION_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --unit-only)
            UNIT_ONLY=true
            shift
            ;;
        --integration-only)
            INTEGRATION_ONLY=true
            shift
            ;;
        --session-id)
            SESSION_ID="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
echo -e "${YELLOW}Starting tests...${NC}"

if [ "$UNIT_ONLY" = true ]; then
    run_unit_tests
elif [ "$INTEGRATION_ONLY" = true ]; then
    run_integration_test "$SESSION_ID"
else
    # Run both unit and integration tests
    if run_unit_tests; then
        echo -e "\n${GREEN}All unit tests passed! 🎉${NC}"
        run_integration_test "$SESSION_ID"
    else
        echo -e "\n${RED}Unit tests failed, skipping integration test${NC}"
        exit 1
    fi
fi

echo -e "\n${GREEN}🎉 All tests completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "• Deploy to cloud function"
echo "• Set up cron triggers"  
echo "• Monitor summary processing"
echo ""
echo "For manual testing, use:"
echo "  python tests/test_local.py --session-id YOUR_SESSION_ID --help"
