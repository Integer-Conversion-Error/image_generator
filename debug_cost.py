try:
    from google.genai import types
    print("GenerateVideosResponse fields:", types.GenerateVideosResponse.model_fields.keys())
    # print("UsageMetadata fields:", types.UsageMetadata.model_fields.keys()) # Check if this type exists
except Exception as e:
    print(e)
