async def analyze_typology(_analyzed_methods):
    method_typologies = {
        "0x095ea7b3": "Wash Trading",  # Approve
        "0xa9059cbb": "ML: Flow Through",  # Transfer
    }

    typologies = set()

    for entry in _analyzed_methods:
        # Check if the entry is a tuple with at least one element
        if isinstance(entry, tuple) and len(entry) >= 1:
            method = entry[0]  # Get the first element (method signature)
            if method in method_typologies:
                typologies.add(method_typologies[method])

    if not typologies:
        return "Asset Farming"

    return ", ".join(typologies)
