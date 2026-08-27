python -m coverage xml -o /Users/utron/Documents/challenge_MLE/reports/coverage.xml --include="challenge/*" && python -m coverage html -d /Users/utron/Documents/challenge_MLE/reports/htmlcov --include="challenge/*" 2>&1


python -m pytest tests/model/test_model.py -v --tb=short --co 2>&1 | head -30

python -m pytest tests/model/test_model.py -v --tb=short 2>&1 | tail -30


python -m pytest tests/model/test_model.py --cov=challenge.model --cov-report=term-missing -v --tb=short 2>&1 | tail -20

python -m coverage report --include="challenge/model.py" --show-missing 2>&1

Name                 Stmts   Miss  Cover   Missing
--------------------------------------------------
challenge/model.py      40      0   100%
--------------------------------------------------
TOTAL                   40      0   100%


python -m pytest tests/model/test_model.py -v --tb=short 2>&1 | tail -30

python -m coverage run -m pytest tests/model/test_model.py -v --tb=short 2>&1 | tail -5

python -m coverage report --include="challenge/model.py" --show-missing 2>&1

python -m pytest tests/api/test_api.py -v --tb=short 2>&1 | tail -20

python -m pytest tests/ -v --junitxml=reports/junit.xml --cov=challenge --cov-report=xml:reports/coverage.xml --cov-report=html:reports/htmlcov 2>&1 | tail -25


