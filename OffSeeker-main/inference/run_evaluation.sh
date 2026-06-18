#!/bin/bash

# OffSeeker Evaluation Script
# This script sets up environment variables and runs the evaluation

set -e  # Exit on error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}OffSeeker Evaluation Script${NC}"
echo "====================================="

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"



# VLLM Server Configuration
# Note: These variables are for reference only when using run_vllm_server.py
# The actual server configuration is done via command-line arguments in run_vllm_server.py
export MODEL_PATH=/path/to/your/model
export MODEL_NAME=your_model_name

# DeepSeek API Configuration (for webpage extraction and answer judging)
# Get your DeepSeek API key from https://platform.deepseek.com/
export DEEPSEEK_API_KEY=your_deepseek_api_key

# API Keys
# Get your Serper API key from https://serper.dev/
export SERPER_API_KEY=your_serper_api_key

# Get your Jina API key from https://jina.ai/ (Optional)
export JINA_API_KEY=your_jina_api_key

# Crawler Engine Selection
# Options: jina (default) or html2text
export CRAWLER_ENGINE=jina

# Display configuration
echo -e "${BLUE}Environment Configuration:${NC}"
if [ ! -z "$DEEPSEEK_API_KEY" ]; then
    echo "  DEEPSEEK_API_KEY: [SET] (for webpage extraction and answer judging)"
else
    echo -e "  DEEPSEEK_API_KEY: ${YELLOW}[NOT SET - Webpage extraction and answer judging may not work]${NC}"
fi
if [ ! -z "$SERPER_API_KEY" ]; then
    echo "  SERPER_API_KEY: [SET]"
else
    echo -e "  SERPER_API_KEY: ${YELLOW}[NOT SET - Google search may not work]${NC}"
fi
if [ ! -z "$JINA_API_KEY" ]; then
    echo "  JINA_API_KEY: [SET]"
else
    echo -e "  JINA_API_KEY: ${YELLOW}[NOT SET - Using html2text for crawling]${NC}"
    export CRAWLER_ENGINE=html2text
fi
echo "  CRAWLER_ENGINE: ${CRAWLER_ENGINE}"
echo ""


# Add src to PYTHONPATH if not already there
if [[ ":$PYTHONPATH:" != *":$SCRIPT_DIR/src:"* ]]; then
    export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
fi

# Run the evaluation script with all passed arguments
echo -e "${GREEN}Running evaluation...${NC}"
echo ""

# Pass all command line arguments to the Python script
python evaluate.py "$@"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}Evaluation completed successfully!${NC}"
else
    echo ""
    echo -e "${RED}Evaluation failed with exit code: $EXIT_CODE${NC}"
    exit $EXIT_CODE
fi

