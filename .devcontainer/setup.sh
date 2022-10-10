#!/usr/bin/env bash
# Setups the repository.

# Stop on errors
set -e

cd "$(dirname "$0")/.."

pip3 install -r .github/workflows/constraints.txt
pre-commit install

container install
