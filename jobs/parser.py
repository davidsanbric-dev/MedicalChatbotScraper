"""HTML parsing utilities for medical condition data extraction."""


def extract_nested_list(list_element):
    """
    Recursively extract nested list structure from HTML ul/ol elements.
    Returns a list of items, where each item can have text and optionally subitems.
    """
    items = []
    for li in list_element.find_all('li', recursive=False):
        # Check if this li has nested lists
        nested_list = li.find(['ul', 'ol'])
        
        if nested_list:
            # Extract text content that comes before the nested list
            # We need to get only the text that's directly in this li, not in nested lists
            item_text = ""
            for content in li.contents:
                if content.name in ['ul', 'ol']:
                    break
                elif isinstance(content, str):
                    item_text += content.strip() + " "
                elif hasattr(content, 'get_text'):
                    item_text += content.get_text(' ', strip=True) + " "
            
            item_text = item_text.strip()
            
            # Recursively extract the nested list
            subitems = extract_nested_list(nested_list)
            
            items.append({
                "text": item_text,
                "subitems": subitems
            })
        else:
            # No nested list, just extract the text
            item_text = li.get_text(' ', strip=True).strip()
            items.append({"text": item_text})
    
    return items