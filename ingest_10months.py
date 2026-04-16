from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct
import csv

client = QdrantClient(path="./qdrant_db")
client.recreate_collection(  # Fresh start
    collection_name="forge_council",
    vectors_config={"size": 384, "distance": "Cosine"}
)

points = []
id_counter = 1

# Ingest Key Master CSV
with open('key_master.csv', 'r') as csvfile:
    reader = csv.reader(csvfile)
    for row in reader:
        if row:  # Skip empty
            content = ' | '.join(row)
            points.append(PointStruct(
                id=id_counter,
                vector=[float(id_counter % 384)] * 384,  # Placeholder vectors
                payload={"text": content, "source": "key_master"}
            ))
            id_counter += 1

if points:
    client.upsert(collection_name="forge_council", points=points)
    print(f"Ingested {len(points)} Key Master entries — council eyes open to 10 months")
else:
    print("No entries — check CSV")
