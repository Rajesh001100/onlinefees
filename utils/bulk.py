
import csv
import io
from typing import List, Dict, Any, Tuple

def parse_student_csv(file_stream) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parses a CSV file stream and returns a list of student dictionaries and a list of errors.
    Expected headers: AdmissionNo, Name, DOB, Year, Class, Course, StudentEmail, ParentEmail, StudentPhone, ParentPhone
    """
    students = []
    errors = []
    
    try:
        stream = io.StringIO(file_stream.read().decode("UTF-8"), newline=None)
        reader = csv.DictReader(stream)
        
        # Normalize headers to lowercase/stripped
        headers = [h.strip().lower() for h in (reader.fieldnames or [])]
        
        # Check required
        required = {"admissionno", "name", "dob", "year", "class", "course"}
        if not required.issubset(set(headers)):
            missing = required - set(headers)
            return [], [f"Missing required columns: {', '.join(missing)}"]
            
        for row_idx, row in enumerate(reader, start=2):
            # Clean keys
            data = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            
            # Validation
            adm = data.get("admissionno")
            name = data.get("name")
            dob = data.get("dob") # YYYY-MM-DD
            year = data.get("year")
            cls = data.get("class")
            course = data.get("course")
            
            if not all([adm, name, dob, year, cls, course]):
                errors.append(f"Row {row_idx}: Missing required fields.")
                continue
                
            try:
                year_int = int(year)
                if year_int not in (1, 2, 3, 4):
                    errors.append(f"Row {row_idx}: Invalid Year (must be 1-4).")
                    continue
            except:
                errors.append(f"Row {row_idx}: Invalid Year format.")
                continue
                
            # Construct student object
            students.append({
                "admission_no": adm,
                "name": name,
                "dob": dob,
                "year": year_int,
                "class": cls,
                "course": course,
                "student_email": data.get("studentemail", ""),
                "parent_email": data.get("parentemail", ""),
                "student_phone": data.get("studentphone", ""),
                "parent_phone": data.get("parentphone", ""),
            })
            
    except Exception as e:
        errors.append(f"File parsing error: {str(e)}")
        
    return students, errors
