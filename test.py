import re
def extract_rating(text: str) -> float:
    if not text:
        return 0.0
    match = re.search(r'(\d+(\.\d+)?)', text)
    if match:
        return float(match.group(1))
    stars = text.count("★")
    return float(stars) if stars > 0 else 0.0
print(extract_rating("4.5 ★"))