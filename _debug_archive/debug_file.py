with open('templates/student/pay_method.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    print("Line 86:", repr(lines[86])) # 0-indexed, so line 87
    print("Line 87:", repr(lines[87])) # line 88
