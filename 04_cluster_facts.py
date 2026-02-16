import os
import json
from collections import deque
import pandas as pd
import numpy as np
from sklearn.cluster import HDBSCAN, KMeans
from sklearn.metrics.pairwise import cosine_similarity

# Configuration
INPUT_DIR = "content_embedded"
OUTPUT_FILE = "data/fact_clusters.csv"

# Semantic Deduplication
SIMILARITY_THRESHOLD = 0.95

# Clustering Constraints
MIN_CLUSTER_SIZE = 5    # If a group is smaller than this, it's "Noise" (-1)
MAX_CLUSTER_SIZE = 15   # If a group is larger than this, we MUST split it

def load_embedded_facts():
    all_rows = []

    if not os.path.exists(INPUT_DIR):
        print(f"Directory not found: {INPUT_DIR}")
        return pd.DataFrame()

    files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".json")]
    print(f"Loading data from {len(files)} cached files...")

    for filename in files:
        filepath = os.path.join(INPUT_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                source = data.get('source_file', filename)

                if 'facts_with_embeddings' in data:
                    for item in data['facts_with_embeddings']:
                        all_rows.append({
                            "fact": item['text'],
                            "vector": item['vector'],
                            "source": source
                        })
            except Exception as e:
                print(f"Error reading {filename}: {e}")

    return pd.DataFrame(all_rows)

def deduplicate_facts(df):
    """
    Removes semantic duplicates based on cosine similarity.
    """
    if df.empty:
        return df

    print(f"Running semantic deduplication on {len(df)} facts...")

    # Stack vectors
    matrix = np.vstack(df['vector'].values)

    # Calculate Similarity
    sim_matrix = cosine_similarity(matrix)

    keep_mask = np.ones(len(df), dtype=bool)
    source_sets = [set(s.split("; ")) for s in df['source'].tolist()]

    np.fill_diagonal(sim_matrix, 0)

    duplicates_count = 0

    for i in range(len(df)):
        if not keep_mask[i]:
            continue

        similar_indices = np.where(sim_matrix[i, i+1:] > SIMILARITY_THRESHOLD)[0] + (i + 1)

        for j in similar_indices:
            if keep_mask[j]:
                keep_mask[j] = False
                duplicates_count += 1
                source_sets[i] |= source_sets[j]

    df['source'] = ["; ".join(sorted(s)) for s in source_sets]
    clean_df = df[keep_mask].copy()

    print(f"Removed {duplicates_count} duplicates. Reduced from {len(df)} to {len(clean_df)} facts.")
    return clean_df

def recursive_cluster(df):
    """
    Uses a queue to recursively split clusters until they obey MAX_CLUSTER_SIZE.
    """
    print(f"\nStarting Recursive Clustering (Max Size: {MAX_CLUSTER_SIZE})...")

    # Initialize all rows with a temporary cluster ID of 0
    # We use a 'label_trace' column to keep track of the hierarchy (e.g. "0_5_2")
    df['cluster_label'] = "0"

    # The Queue: deque for O(1) popleft
    cluster_queue = deque(["0"])

    while cluster_queue:
        current_label = cluster_queue.popleft()

        # Get the subset of data for this label
        subset_mask = df['cluster_label'] == current_label
        subset_df = df[subset_mask]

        # If it's small enough, we are done with this group
        if len(subset_df) <= MAX_CLUSTER_SIZE:
            continue

        print(f"  Processing Cluster '{current_label}' ({len(subset_df)} items)...", end=" ")

        # Prepare vectors
        subset_vectors = np.vstack(subset_df['vector'].values)

        # 1. Try HDBSCAN first (Structure-based split)
        hdb = HDBSCAN(min_cluster_size=MIN_CLUSTER_SIZE, min_samples=2, metric='euclidean')
        new_labels = hdb.fit_predict(subset_vectors)

        num_new_clusters = len(set(new_labels)) - (1 if -1 in new_labels else 0)

        # 2. Logic Check: Did it actually split?
        # If HDBSCAN found 0 or 1 cluster, it failed to separate the dense blob.
        if num_new_clusters < 2:
            print("HDBSCAN found dense blob. Forcing K-Means split.", end=" ")
            # Smarter k: target ~10 facts per cluster instead of always 2
            k = max(2, len(subset_df) // 10)
            kmeans = KMeans(n_clusters=k, n_init=10, random_state=42)
            new_labels = kmeans.fit_predict(subset_vectors)

        print(f"-> Split into {len(set(new_labels))} parts.")

        # 3. Assign new labels and add to queue
        # We need to map the new sub-labels back to the original dataframe indices
        subset_indices = subset_df.index.tolist()

        for local_idx, sub_label in enumerate(new_labels):
            original_idx = subset_indices[local_idx]

            # Create new hierarchical ID: e.g. "0_1" or "0_-1" (noise)
            if sub_label == -1:
                new_id = f"{current_label}_noise"
                # We don't add noise to queue; we just accept it as noise
            else:
                new_id = f"{current_label}_{sub_label}"
                # Add to queue to check if THIS new part is also too big
                if new_id not in cluster_queue:
                    cluster_queue.append(new_id)

            df.at[original_idx, 'cluster_label'] = new_id

    return df

def recover_noise(df):
    """
    Assign noise facts to their nearest non-noise cluster by cosine similarity.
    """
    noise_mask = df['cluster_label'].str.endswith('_noise')
    noise_df = df[noise_mask]
    valid_df = df[~noise_mask]

    if len(noise_df) == 0 or len(valid_df) == 0:
        return df

    print(f"\nRecovering {len(noise_df)} noise facts into nearest clusters...")

    # Compute centroid for each non-noise cluster
    cluster_labels = valid_df['cluster_label'].unique()
    centroids = {}
    for label in cluster_labels:
        cluster_vectors = np.vstack(valid_df[valid_df['cluster_label'] == label]['vector'].values)
        centroids[label] = cluster_vectors.mean(axis=0)

    centroid_labels = list(centroids.keys())
    centroid_matrix = np.vstack([centroids[l] for l in centroid_labels])

    # For each noise fact, find nearest cluster
    noise_vectors = np.vstack(noise_df['vector'].values)
    similarities = cosine_similarity(noise_vectors, centroid_matrix)

    for i, noise_idx in enumerate(noise_df.index):
        best_cluster_idx = similarities[i].argmax()
        df.at[noise_idx, 'cluster_label'] = centroid_labels[best_cluster_idx]

    print(f"  Reassigned {len(noise_df)} noise facts to {len(set(df.loc[noise_df.index, 'cluster_label']))} clusters.")
    return df

def print_statistics(df):
    """
    Calculates and prints statistics about the clustering results.
    """
    total_facts = len(df)

    # Identify Noise (labels ending in _noise)
    noise_mask = df['cluster_label'].str.endswith('_noise')
    noise_df = df[noise_mask]
    valid_df = df[~noise_mask]

    noise_count = len(noise_df)
    valid_count = len(valid_df)

    # Cluster Metrics
    if valid_count > 0:
        # Group by label to get sizes
        cluster_sizes = valid_df['cluster_label'].value_counts()
        num_clusters = len(cluster_sizes)
        avg_size = cluster_sizes.mean()
        min_size = cluster_sizes.min()
        max_size = cluster_sizes.max()
    else:
        num_clusters = 0
        avg_size = 0
        min_size = 0
        max_size = 0

    print("\n" + "="*40)
    print("       CLUSTERING STATISTICS")
    print("="*40)
    print(f"Total Facts Processed: {total_facts}")
    print(f"Total Clusters Found:  {num_clusters}")
    print("-" * 40)

    # Avoid division by zero
    valid_pct = (valid_count / total_facts * 100) if total_facts > 0 else 0
    noise_pct = (noise_count / total_facts * 100) if total_facts > 0 else 0

    print(f"Facts in Clusters:     {valid_count} ({valid_pct:.1f}%)")
    print(f"Facts labeled Noise:   {noise_count} ({noise_pct:.1f}%)")
    print("-" * 40)

    if num_clusters > 0:
        print(f"Avg Cluster Size:      {avg_size:.2f}")
        print(f"Min Cluster Size:      {min_size}")
        print(f"Max Cluster Size:      {max_size}")
    print("="*40 + "\n")

def main():
    # 1. Load
    df = load_embedded_facts()
    if df.empty:
        print("No data found.")
        return

    # Scalability warning
    if len(df) > 5000:
        print(f"WARNING: {len(df)} facts detected. The O(n^2) similarity matrix may be slow for datasets this large.")

    # 2. Deduplicate
    df = deduplicate_facts(df)

    # Reset index to ensure clean lookups during recursion
    df = df.reset_index(drop=True)

    # 3. Recursive Cluster
    df = recursive_cluster(df)

    # 4. Noise Recovery: assign noise facts to nearest cluster
    df = recover_noise(df)

    # 5. Cleanup & Export
    # Sort for easier reading: 0_0_0, 0_0_1, etc.
    output_df = df[['cluster_label', 'source', 'fact']].sort_values(by=['cluster_label', 'source'])

    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    output_df.to_csv(OUTPUT_FILE, index=False)

    print(f"\nDone! Saved granular clusters to {OUTPUT_FILE}")
    print("Check the 'cluster_label' column to see the hierarchy (e.g., '0_3_1').")

    # 6. Output Stats
    print_statistics(output_df)

if __name__ == "__main__":
    main()
