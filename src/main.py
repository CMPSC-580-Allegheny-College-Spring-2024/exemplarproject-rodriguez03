import streamlit as st
import sqlite3
import os
import tarfile
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def extract_data_from_xml(xml_path):
    """Extract and process data from XML Files."""
    with open(xml_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'xml')
        title = soup.find('article-title').text.strip()
        abstract = soup.find('abstract').text.strip() if soup.find('abstract') else ""
        text = title + " " + abstract
        return text

def process_corpus(corpus_path, db_path):
    """Process XML files and store data in database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            text TEXT
        )
    ''')

    for root, dirs, files in os.walk(corpus_path):
        for file in files:
            if file.endswith(".xml"):
                xml_path = os.path.join(root, file)
                text = extract_data_from_xml(xml_path)
                cursor.execute('INSERT INTO articles (title, text) VALUES (?, ?)', (file, text))

    conn.commit()
    conn.close()

def fact_check(query, db_path):
    """Preform fact-checking"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Retrieving data from the database
    cursor.execute('SELECT id, text FROM articles')
    rows = cursor.fetchall()

    vectorizer = TfidfVectorizer(stop_words='english')
    vectors = vectorizer.fit_transform([row[1] for row in rows] + [query])

    similarities = cosine_similarity(vectors[:-1], vectors[-1])
    
    most_similar_index = similarities.argmax() #most similar article

    if similarities[most_similar_index] > 0.2:  # Adjust the similarity as needed
        result = f"The fact is supported by article: {rows[most_similar_index][0]}"
    else:
        result = "No matching article found to support the fact."

    conn.close()
    return result

def main():
    "Main Streamlit Application."
    st.title("Corroboration Dashboard")

    corpus_file = st.file_uploader("Upload PubMed Corpus (tar.gz file)", type=["tar.gz"])
    if corpus_file:
    
        with tarfile.open(fileobj=corpus_file, mode="r:gz") as tar:
            tar.extractall(path="./corpus_data")

    if st.button("Process Corpus"):
        process_corpus("./corpus_data", "corroboration_db.sqlite")
        st.success("Corpus processed successfully!")

    user_query = st.text_area("Enter the fact you want to check:")
    if st.button("Fact Check"):
        result = fact_check(user_query, "corroboration_db.sqlite")
        st.info(result)

if __name__ == "__main__":
    main()
