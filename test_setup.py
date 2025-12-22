"""Test script to verify all dependencies are installed correctly."""

print("Testing imports...")

try:
    import spacy
    print("✓ spaCy imported successfully")
    
    nlp = spacy.load('en_core_web_sm')
    print("✓ spaCy English model loaded successfully")
    
    from sentence_transformers import SentenceTransformer
    print("✓ sentence-transformers imported successfully")
    
    import pandas as pd
    print("✓ pandas imported successfully")
    
    import numpy as np
    print("✓ numpy imported successfully")
    
    import pyodbc
    print("✓ pyodbc imported successfully")
    
    from dotenv import load_dotenv
    print("✓ python-dotenv imported successfully")
    
    from bs4 import BeautifulSoup
    print("✓ BeautifulSoup imported successfully")
    
    from sklearn.metrics.pairwise import cosine_similarity
    print("✓ scikit-learn imported successfully")
    
    print("\n✅ ALL DEPENDENCIES INSTALLED SUCCESSFULLY!")
    print(f"\nPython version: {__import__('sys').version}")
    print(f"spaCy version: {spacy.__version__}")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print("Please check the error message above and reinstall the failed package.")