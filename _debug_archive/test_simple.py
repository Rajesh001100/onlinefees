from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import sys

try:
    c = canvas.Canvas("test.pdf", pagesize=A4)
    x = 100
    y = 100
    text = "Hello"
    
    print(f"Testing drawString({x}, {y}, '{text}')")
    c.drawString(x, y, text)
    
    print(f"Testing drawCentredString({x}, {y}, '{text}')")
    c.drawCentredString(x, y, text)
    
    print(f"Testing drawRightString({x}, {y}, '{text}')")
    c.drawRightString(x, y, text)
    
    c.save()
    print("Success")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
