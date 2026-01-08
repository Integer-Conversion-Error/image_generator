import google.generativeai as genai
print(dir(genai))
try:
    m = genai.GenerativeModel("imagen-3.0-generate-001")
    print("GenerativeModel created")
    print(dir(m))
except Exception as e:
    print(e)
