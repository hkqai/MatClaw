"""
Utility functions for retrieving and processing literature metadata.
"""

import requests
from typing import Dict, Optional, List
import time


def get_paper_metadata_from_doi(doi: str, timeout: int = 10) -> Optional[Dict]:
    """
    Retrieve paper metadata from CrossRef API using DOI.
    
    Args:
        doi: Digital Object Identifier (DOI) of the paper (e.g., "10.1021/ja101860r")
        timeout: Request timeout in seconds (default: 10)
    
    Returns:
        Dictionary containing paper metadata with the following keys:
            - doi: The DOI
            - title: Paper title
            - authors: List of author names (as strings)
            - year: Publication year
            - journal: Journal/publication name
            - volume: Volume number (if available)
            - issue: Issue number (if available)
            - pages: Page range (if available)
            - publisher: Publisher name
            - type: Publication type (e.g., "journal-article")
            - url: URL to the paper
            - abstract: Abstract text (if available)
            - references_count: Number of references cited
            - is_referenced_by_count: Citation count
        
        Returns None if the request fails or DOI is not found.
    
    Example:
        >>> metadata = get_paper_metadata_from_doi("10.1021/ja101860r")
        >>> print(metadata['title'])
        >>> print(f"Published in {metadata['year']} in {metadata['journal']}")
    """
    # Clean up DOI (remove common prefixes)
    doi = doi.strip()
    if doi.startswith("https://doi.org/"):
        doi = doi.replace("https://doi.org/", "")
    elif doi.startswith("http://doi.org/"):
        doi = doi.replace("http://doi.org/", "")
    elif doi.startswith("doi:"):
        doi = doi.replace("doi:", "")
    
    # CrossRef API endpoint
    base_url = "https://api.crossref.org/works/"
    url = f"{base_url}{doi}"
    
    # Set headers with a polite user-agent
    headers = {
        "User-Agent": "MatClaw/2.0 (mailto:research@example.com)"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status") != "ok":
            print(f"CrossRef API returned status: {data.get('status')}")
            return None
        
        # Extract metadata from the response
        message = data.get("message", {})
        
        # Extract authors
        authors = []
        for author in message.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            if given and family:
                authors.append(f"{given} {family}")
            elif family:
                authors.append(family)
        
        # Extract publication date (prefer published-print, fallback to published-online)
        year = None
        pub_date = message.get("published-print") or message.get("published-online") or message.get("created")
        if pub_date and "date-parts" in pub_date:
            date_parts = pub_date["date-parts"][0]
            if date_parts and len(date_parts) > 0:
                year = date_parts[0]
        
        # Extract title (usually a list with one element)
        title = message.get("title", [""])[0] if message.get("title") else ""
        
        # Build metadata dictionary
        metadata = {
            "doi": message.get("DOI", doi),
            "title": title,
            "authors": authors,
            "year": year,
            "journal": message.get("container-title", [""])[0] if message.get("container-title") else "",
            "volume": message.get("volume"),
            "issue": message.get("issue"),
            "pages": message.get("page"),
            "publisher": message.get("publisher"),
            "type": message.get("type"),
            "url": message.get("URL"),
            "abstract": message.get("abstract"),
            "references_count": message.get("references-count"),
            "is_referenced_by_count": message.get("is-referenced-by-count"),
        }
        
        return metadata
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"DOI not found: {doi}")
        else:
            print(f"HTTP error occurred: {e}")
        return None
    except requests.exceptions.Timeout:
        print(f"Request timed out after {timeout} seconds")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching metadata: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
