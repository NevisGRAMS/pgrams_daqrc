#!/bin/bash
# Launch the pGRAMS TPC Configuration GUI
#
# Usage:
#   ./run_config_gui.sh
#
# Prerequisites:
#   - conda environment 'pgrams_tpc_metrics' with datamon, tkinter, mysql-connector-python
#   - source your credentials script first (temp_setup_credentials.sh)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate conda environment
eval "$(conda shell.bash hook)"
conda activate pgrams_tpc_metrics

# Run the GUI
python -m config_gui.config_gui
