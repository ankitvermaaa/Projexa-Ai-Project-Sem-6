import uuid
import datetime
import json
import os

# JSON file for persistent storage
JSON_FILE = "patient_data.json"

def _load_from_json():
    """Load data from JSON file."""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def _save_to_json(data):
    """Save data to JSON file."""
    with open(JSON_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def make_patient_entry(name, age, sex, pid, disease="Unknown", specialization="general"):
    """Creates a dictionary structure for a patient."""
    return {
        "id": pid,
        "uuid": str(uuid.uuid4()),
        "name": name,
        "age": age,
        "sex": sex,
        "disease": disease,
        "specialization": specialization,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Pending Review"
    }

def add_record(record):
    """Adds a record to the database."""
    data = _load_from_json()
    data.append(record)
    _save_to_json(data)
    return True

def load_all():
    """Returns all records."""
    return _load_from_json()

def find_by_id(pid):
    """Finds a record by Patient ID."""
    data = _load_from_json()
    for r in data:
        if r["id"] == pid:
            return r
    return None

def search(query, specialization=None):
    """Search by text or filter by specialization."""
    results = _load_from_json()
    if specialization and specialization != "all":
        results = [r for r in results if r["specialization"].lower() == specialization.lower()]
    
    # Simple text search (if query exists)
    if query:
        q = query.lower()
        results = [r for r in results if q in r["name"].lower() or q in r["id"].lower()]
        
    return results

def update_record(pid, updates):
    """Updates specific fields of a record."""
    data = _load_from_json()
    for rec in data:
        if rec["id"] == pid:
            rec.update(updates)
            _save_to_json(data)
            return True
    return False

def delete_record(pid):
    """Removes a record."""
    data = _load_from_json()
    initial_len = len(data)
    data = [r for r in data if r["id"] != pid]
    if len(data) < initial_len:
        _save_to_json(data)
        return True
    return False