import json

from self_debug.common.utils import do_run_command
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Union
import pickle

from transformers import AutoModel, AutoTokenizer
from transformers.dynamic_module_utils import get_imports
import torch
import hashlib
from torch import Tensor
import glob
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi
import nltk

# nltk.download('punkt_tab')
os.environ["TOKENIZERS_PARALLELISM"] = "false"
TREE_STRUCTURE_CMD = "tree --charset=ascii"


class EmbeddingSimilarity(ABC):
    models = {}

    def load_model(self, ckpt: str):
        if ckpt not in EmbeddingSimilarity.models:
            try:
                model = AutoModel.from_pretrained(ckpt, trust_remote_code=True).to(
                    self.device
                )
                if ckpt.startswith("codesage/codesage"):
                    tokenizer = AutoTokenizer.from_pretrained(
                        ckpt, trust_remote_code=True, add_eos_token=True
                    )
                else:
                    tokenizer = AutoTokenizer.from_pretrained(
                        ckpt, trust_remote_code=True
                    )
            except Exception as e:
                print("Catching exception: ", e)

                # work around starts for flash_attn on cpu. From https://huggingface.co/qnguyen3/nanoLLaVA-1.5/discussions/4
                def fixed_get_imports(filename: Union[str, os.PathLike]) -> List[str]:
                    """Work around for https://huggingface.co/microsoft/phi-1_5/discussions/72."""
                    imports = get_imports(filename)
                    if not torch.cuda.is_available() and "flash_attn" in imports:
                        imports.remove("flash_attn")
                    return imports

                with patch(
                    "transformers.dynamic_module_utils.get_imports", fixed_get_imports
                ):
                    model = AutoModel.from_pretrained(ckpt, trust_remote_code=True).to(
                        self.device
                    )
                    if ckpt.startswith("codesage/codesage"):
                        tokenizer = AutoTokenizer.from_pretrained(
                            ckpt, trust_remote_code=True, add_eos_token=True
                        )
                    else:
                        tokenizer = AutoTokenizer.from_pretrained(
                            ckpt, trust_remote_code=True
                        )
                # word around ends.
            model.eval()
            EmbeddingSimilarity.models[ckpt] = (model, tokenizer)

        return EmbeddingSimilarity.models[ckpt]

    def __init__(self, ckpt: str, device=None) -> None:
        if device is None or not torch.cuda.is_available():
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.max_length = 1024
        self.model, self.tokenizer = self.load_model(ckpt)

    def _get_embedding(self, query):
        batch_dict = self.tokenizer(
            query,
            max_length=self.max_length,
            padding=True,
            truncation=True,
            return_tensors="pt",
        ).to(self.device)
        output = self.model(**batch_dict)
        query_embedding = output.last_hidden_state[0][-1].detach().cpu().numpy()
        return query_embedding

    def compute_similarity(self, query1, query2):
        query_embedding_1 = self._get_embedding(query1)
        query_embedding_2 = self._get_embedding(query2)
        return np.dot(query_embedding_1, query_embedding_2) / np.maximum(
            (np.linalg.norm(query_embedding_1) * np.linalg.norm(query_embedding_2)),
            1e-8,
        )


def hash_string(string_to_hash):
    hash_object = hashlib.sha256()
    hash_object.update(string_to_hash.encode("utf-8"))
    return hash_object.hexdigest()


def snapshot_exists(maybe_hashed_snapshot, snapshot_dict, threshold=0.9):
    if not snapshot_dict:
        return False, None
    if maybe_hashed_snapshot in snapshot_dict:
        return True, snapshot_dict[maybe_hashed_snapshot]
    return False, None


def dedup_by_EM(benchmark_folder):
    snapshot_dict = {}
    removed = set()
    cant_get_tree = set()
    cant_get_pom = set()

    for file in sorted(os.listdir(benchmark_folder)):
        full_path = os.path.join(benchmark_folder, file)
        result = do_run_command(TREE_STRUCTURE_CMD, cwd=full_path)
        pom_path = os.path.join(full_path, "pom.xml")

        if result.return_code == 0:
            tree = result.stdout
        else:
            cant_get_tree.add(file)
            continue

        if os.path.exists(pom_path):
            with open(pom_path, "r") as f:
                pom_content = f.read()
        else:
            cant_get_pom.add(file)
            continue

        snapshot = (tree, pom_content)
        maybe_hashed_snapshot = hash_string("\n".join(list(snapshot)))
        exists, original = snapshot_exists(maybe_hashed_snapshot, snapshot_dict)
        if exists:
            print(f"Repo {file} is detected as a copy of {original}.")
            removed.add(file)
        else:
            snapshot_dict[maybe_hashed_snapshot] = file

    print(f"Dedup over {len(os.listdir(benchmark_folder))} repos")
    print(f"Found {len(removed)} potential copies")
    print(f"{len(snapshot_dict)} repos remain")
    print(f"Can't generate tree structure {len(cant_get_tree)}")
    print(f"Can't read pom {len(cant_get_pom)}")

    print(f"Removed the following repos: {removed}")
    print(f"Remaining repos are {list(snapshot_dict.values())}")


def need_compute(repo1, repo2):
    if not equal_pom(repo1, repo2):
        print(f"Reject since not equal pom files: {repo1} vs {repo2}")
        return False
    if not similar_n_java_files(repo1, repo2, threshold=0.05):
        print(f"Reject by # of java files: {repo1} vs {repo2}")
        return False
    return True


def equal_pom(repo1, repo2):
    pom_files_1 = sorted(
        glob.glob(os.path.join(repo1, "**", "pom.xml"), recursive=True)
    )
    pom_files_2 = sorted(
        glob.glob(os.path.join(repo2, "**", "pom.xml"), recursive=True)
    )
    return len(pom_files_1) == len(pom_files_2) and len(pom_files_1) > 0


def similar_n_java_files(repo1, repo2, threshold=0.05):
    java_files_1 = sorted(
        glob.glob(os.path.join(repo1, "**", "*.java"), recursive=True)
    )
    java_files_2 = sorted(
        glob.glob(os.path.join(repo2, "**", "*.java"), recursive=True)
    )
    return (
        abs(len(java_files_1) - len(java_files_2))
        / min(len(java_files_1), len(java_files_2))
        <= threshold
    )


def get_repo_representation(repo):
    result = do_run_command(TREE_STRUCTURE_CMD, cwd=repo)
    pom_path = os.path.join(repo, "pom.xml")

    if result.return_code == 0:
        tree = result.stdout
    else:
        tree = ""

    if os.path.exists(pom_path):
        with open(pom_path, "r") as f:
            pom_content = f.read()
    else:
        pom_content = ""
    if not tree and not pom_content:
        return None
    return "\n".join([tree, pom_content])


def compute_sim(repo1, repo2, ckpt="Alibaba-NLP/gte-large-en-v1.5"):
    char_repo1 = get_repo_representation(repo1)
    char_repo2 = get_repo_representation(repo2)
    if char_repo1 and char_repo2:
        embedding_model = EmbeddingSimilarity(ckpt=ckpt, device="cuda:0")
        similarity = embedding_model.compute_similarity(char_repo1, char_repo2)
    else:
        similarity = None
    return similarity


def find_repo_name(full_repo_path):
    return full_repo_path.split("/")[-1]


def generate_and_store_sim_dict(all_repos, sim_dict_output_path):
    sim_dict = {}

    for i in range(len(all_repos)):
        for j in range(i + 1, len(all_repos)):
            full_path_i = all_repos[i]
            full_path_j = all_repos[j]
            if need_compute(full_path_i, full_path_j):
                similarity = compute_sim(full_path_i, full_path_j)
                if similarity is not None:
                    sim_dict[
                        (find_repo_name(full_path_i), find_repo_name(full_path_j))
                    ] = similarity

    print(f"{len(sim_dict)} pairs of similarities are generated")

    with open(sim_dict_output_path, "wb") as f:
        pickle.dump(sim_dict, f)

    return sim_dict


def dedup_by_similarity(
    benchmark_folder, sim_dict_output_path="./sim_dict.pkl", threshold=0.9
):
    all_repos = sorted(
        [os.path.join(benchmark_folder, file) for file in os.listdir(benchmark_folder)]
    )
    if os.path.exists(sim_dict_output_path):
        with open(sim_dict_output_path, "rb") as f:
            sim_dict = pickle.load(f)
    else:
        sim_dict = generate_and_store_sim_dict(all_repos, sim_dict_output_path)

    remove = set()

    for pair in sorted(sim_dict.keys()):
        if pair[0] in remove:
            continue
        sim = sim_dict[pair]
        if sim > threshold:
            remove.add(pair[1])
            print(f"Removed {pair[1]} because it's similar to {pair[0]}")

    print(f"Removed {len(remove)} repos")
    print(f"Removed the following repos: {remove}")


def dedup(benchmark_folder, dedup_alg="EM"):
    if dedup_alg == "EM":
        print("=" * 6, "dedup by EM")
        dedup_by_EM(benchmark_folder)
    elif dedup_alg == "similarity":
        print("=" * 6, "dedup by similarity")
        dedup_by_similarity(benchmark_folder)


if __name__ == "__main__":
    benchmark_folder = Path(__file__).parent.parent / "test/test_benchmark"
    dedup_alg = "similarity"
    dedup(benchmark_folder, dedup_alg)
