import streamlit as st
import sqlite3
import os
import tarfile
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CHUNK_SIZE = 500 


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

def process_chunk(conn, cursor, chunk):
    with conn:
        for xml_path in chunk:
            text = extract_data_from_xml(xml_path)
            cursor.execute('INSERT INTO articles (title, text) VALUES (?, ?)', (os.path.basename(xml_path), text))
    conn.commit()

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

    st.info("Processing, please wait...")

    for root, dirs, files in os.walk(corpus_path):
        for file in files:
            if file.endswith(".xml"):
                xml_path = os.path.join(root, file)
                chunk.append(xml_path)

                if len(chunk) >= CHUNK_SIZE:
                    process_chunk(conn, cursor, chunk)
                    chunk = []
                    files_processed += CHUNK_SIZE

    if chunk:
        process_chunk(conn, cursor, chunk)
        files_processed += len(chunk)

    conn.close()
    st.success(f"Processed {files_processed} XML files successfully!")


def fact_check(query, db_path, similarity_threshold=0.2, show_contents=False):
    """Perform fact-checking on all articles."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, text FROM articles')
    rows = cursor.fetchall()

    if not rows:
        conn.close()
        return "No articles found. Please process the corpus before fact-checking."

    article_data = [(row[0], row[1], row[2]) for row in rows]

    # Query Sanitization
    query = query.lower()

    vectorizer = TfidfVectorizer(stop_words='english')
    vectors = vectorizer.fit_transform([query] + [text for _, _, text in article_data])

    query_vector = vectors[0]
    article_vectors = vectors[1:]

    similarities = cosine_similarity(query_vector, article_vectors)

    matching_articles = [
        (article_data[i][0], article_data[i][1], similarities[0][i])
        for i in range(len(similarities))
        if similarities[0][i] >= similarity_threshold
    ]

    if not matching_articles:
        result = "No matching article found to support the fact."
    else:
        result = "The fact is supported by the following articles:\n\n"
        for article in matching_articles:
            article_id, title, similarity_score = article
            result += f"Article ID: {article_id}\nTitle: {title}\nSimilarity Score: {float(similarity_score):.4f}\n\n"
            if show_contents:
                result += "Full Text:\n" + article_data[article_id - 1][2] + "\n\n"

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
        process_corpus("./corpus_data", "corroboration_db.sqlite")

    user_query = st.text_area("Enter the fact you want to check:")

    show_contents = st.checkbox("Show contents of articles")
    
    if st.button("Fact Check"):
        st.info("Fact-checking, please wait...")
        result = fact_check(user_query, "corroboration_db.sqlite", show_contents=show_contents)
        st.success(result)

if __name__ == "__main__":
    main()
