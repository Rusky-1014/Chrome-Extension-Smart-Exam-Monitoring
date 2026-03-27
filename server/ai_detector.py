def detect_category(url):
    url = url.lower()

    if "youtube" in url:
        return "Entertainment"
    elif "instagram" in url or "facebook" in url or "twitter" in url:
        return "Social Media"
    elif "netflix" in url:
        return "Streaming"
    elif "chatgpt" in url or "openai" in url:
        return "AI Tool"
    elif "github" in url or "stackoverflow" in url:
        return "Educational"
    else:
        return "Other"