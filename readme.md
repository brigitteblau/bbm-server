# BBM Server (Hunda)

API para generación de prótesis caninas 3D-printables.

## Correr local
python3 -m venv venv
source venv/bin/activate   # mac
pip install -r requirements.txt
uvicorn app.main:app --reload

## Tests
python -m pytest tests/ -v