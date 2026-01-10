from google.genai import types
try:
    print("types.GeneratedVideo:", types.GeneratedVideo.model_fields.keys())
except:
    pass

try:
    print("types.Video:", types.Video.model_fields.keys())
except:
    pass
    
try:
    print("types.File:", types.File.model_fields.keys())
except:
    pass
