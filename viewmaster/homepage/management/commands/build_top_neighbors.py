import json
from pathlib import Path

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from homepage.catalog import data_dir, load_videos_txt_lines, videos_txt_path


def default_embeddings_path():
    repo_root = Path(settings.BASE_DIR).parent
    return repo_root.parent / 'ViewMasterApp' / 'video_embeddings.json'


def load_embedding_matrix(filenames, embeddings_path):
    raw = json.loads(Path(embeddings_path).read_text(encoding='utf-8'))
    vectors = []
    missing = []
    for filename in filenames:
        entry = raw.get(filename)
        if not entry or 'embedding' not in entry:
            missing.append(filename)
            continue
        vectors.append(entry['embedding'])
    if missing:
        raise CommandError(
            f'Missing embeddings for {len(missing)} file(s), e.g. {missing[0]}'
        )
    return np.array(vectors, dtype=np.float64)


def build_top_neighbors_matrix(vectors, neighbor_count=6):
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = vectors / norms
    similarity = normalized @ normalized.T

    neighbor_lists = []
    for index in range(similarity.shape[0]):
        scores = similarity[index].copy()
        scores[index] = -np.inf
        top_indices = np.argsort(-scores)
        neighbors = []
        for candidate in top_indices:
            if candidate == index:
                continue
            neighbors.append(int(candidate))
            if len(neighbors) == neighbor_count:
                break
        neighbor_lists.append(neighbors)
    return neighbor_lists


class Command(BaseCommand):
    help = 'Build top_neighbors.json from CLIP embeddings and videos.txt.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--embeddings-path',
            type=Path,
            default=None,
            help='Path to video_embeddings.json (default: ../ViewMasterApp/video_embeddings.json)',
        )
        parser.add_argument(
            '--output',
            type=Path,
            default=None,
            help='Output path (default: homepage/data/top_neighbors.json)',
        )
        parser.add_argument(
            '--neighbors',
            type=int,
            default=6,
            help='Neighbors per video (default: 6)',
        )

    def handle(self, *args, **options):
        embeddings_path = options['embeddings_path'] or default_embeddings_path()
        output_path = options['output'] or (data_dir() / 'top_neighbors.json')

        if not embeddings_path.is_file():
            raise CommandError(f'Embeddings file not found: {embeddings_path}')
        if not videos_txt_path().is_file():
            raise CommandError(f'videos.txt not found: {videos_txt_path()}')

        filenames = load_videos_txt_lines()
        self.stdout.write(f'Loading {len(filenames)} embeddings from {embeddings_path}...')
        vectors = load_embedding_matrix(filenames, embeddings_path)

        self.stdout.write('Computing cosine-similarity neighbors...')
        neighbor_lists = build_top_neighbors_matrix(vectors, neighbor_count=options['neighbors'])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(neighbor_lists), encoding='utf-8')
        self.stdout.write(
            self.style.SUCCESS(
                f'Wrote {len(neighbor_lists)} entries ({options["neighbors"]} neighbors each) to {output_path}'
            )
        )
