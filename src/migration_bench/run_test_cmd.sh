set -x

python ./common/test_file_utils.py
python ./common/test_git_repo.py
python ./common/test_hash_utils.py
python ./common/test_maven_utils.py
python ./common/test_prompt_manager_factory.py
python ./common/test_send_email.py
python ./common/test_traceback_retriever.py
python ./common/test_utils.py
python ./datasets/test_hf_utils.py
python ./eval/test_final_eval.py
python ./eval/test_repos.py
python ./lang/java/eval/test_parse_file.py
python ./lang/java/eval/test_parse_repo.py
python ./metrics/test_utils.py
