#!/bin/bash
# pre-requisity to have pyenv on the system
#pyenv install -f 3.12.3
pyenv local 3.12.3
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
