import streamlit as st
import sqlite3
import os
import tarfile
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CHUNK_SIZE = 500  # Process 500 XML files at a time

def extract_data_from_xml(xml_path):
    """Extract and process data from XML Files."""
    with open(xml_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'xml')
        title_tag = soup.find('article-title')
        title = title_tag.text.strip() if title_tag else ""
        
        abstract_tag = soup.find('abstract')
        abstract = abstract_tag.text.strip() if abstract_tag else ""

        text = title + " " + abstract
        return text

def process_chunk(cursor, chunk):
    for xml_path in chunk:
        text = extract_data_from_xml(xml_path)
        cursor.execute('INSERT INTO articles (title, text) VALUES (?, ?)', (os.path.basename(xml_path), text))

def process_corpus(corpus_path, db_path):
    """Process XML files and store data in the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            text TEXT
        )
    ''')

    files_processed = 0
    chunk = []

    for root, dirs, files in os.walk(corpus_path):
        for file in files:
            if file.endswith(".xml"):
                xml_path = os.path.join(root, file)
                chunk.append(xml_path)

                if len(chunk) >= CHUNK_SIZE:
                    process_chunk(cursor, chunk)
                    conn.commit()
                    chunk = []
                    files_processed += CHUNK_SIZE

    # Process the remaining files
    if chunk:
        process_chunk(cursor, chunk)
        conn.commit()
        files_processed += len(chunk)

    conn.close()
    return files_processed

def fact_check(query, db_path):
    """Perform fact-checking on all articles."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Retrieving data from all articles
    cursor.execute('SELECT id, title, text FROM articles')
    rows = cursor.fetchall()

    if not rows:
        conn.close()
        return "No articles found. Please process the corpus before fact-checking."

    # Extract article titles and texts for comparison
    article_data = [(row[1], row[2]) for row in rows]

    # Use TF-IDF vectorizer for similarity comparison
    vectorizer = TfidfVectorizer(stop_words='english')
    vectors = vectorizer.fit_transform([query] + [text for _, text in article_data])

    # Calculate cosine similarity between query and article texts
    similarities = cosine_similarity(vectors[:-1], vectors[-1])

    # Find the most similar article
    most_similar_index = similarities.argmax()

    if similarities[most_similar_index] > 0.2:  # Adjust the similarity threshold as needed
        article_title = article_data[most_similar_index][0]
        article_text = article_data[most_similar_index][1]

        result = f"The fact is supported by article: {article_title}\n\n{article_text}"
    else:
        result = "No matching article found to support the fact."

    conn.close()
    return result

def main():
    "Main Streamlit Application."
    st.title("Corroboration Dashboard")

    corpus_file = st.file_uploader("Upload PubMed Corpus (tar.gz file)", type=["tar", "gz"])
    if corpus_file:
        try:
            with tarfile.open(fileobj=corpus_file, mode="r:gz") as tar:
                tar.extractall(path="./corpus_data")
        except tarfile.ReadError:
            st.error("Invalid or corrupted gzip file. Please upload a valid tar.gz file.")
            return

    if st.button("Process Corpus"):
        files_processed = process_corpus("./corpus_data", "corroboration_db.sqlite")
        st.success(f"Processed {files_processed} XML files successfully!")

    user_query = st.text_area("Enter the fact you want to check:")

    if st.button("Fact Check"):
        result = fact_check(user_query, "corroboration_db.sqlite")
        st.info(result)

if __name__ == "__main__":
    main()
