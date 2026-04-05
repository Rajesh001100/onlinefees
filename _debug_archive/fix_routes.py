import os

path = "c:/college_fees_system/blueprints/student/routes.py"

with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False

for line in lines:
    if "def _build_receipt_pdf_bytes" in line:
        new_lines.append("from .receipt_utils import build_receipt_pdf_bytes as _build_receipt_pdf_bytes\n")
        skip = True
        continue
    
    if skip:
        # Stop skipping when we hit the next route definition or big separator
        # The next route is @student_bp.post("/pay/complete...
        if '@student_bp.post("/pay/complete' in line:
            skip = False
            new_lines.append("\n") # Add some spacing
            new_lines.append(line)
        elif "# -----------------------------" in line and "Complete Payment" in lines[lines.index(line)+1]:
             # This handles the comment block before the route
             skip = False
             new_lines.append("\n")
             new_lines.append(line)
    else:
        new_lines.append(line)

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Fixed routes.py")
