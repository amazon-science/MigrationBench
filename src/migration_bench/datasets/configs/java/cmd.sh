FILE=$1

sed -i "s/^  {/  dataset_repos { github_repo {/g" $FILE
sed -i 's/^    "commented_/    # "commented_/g' $FILE
sed -i 's/^    "commit_id"/    commit_id/g' $FILE
sed -i 's/^    "github_url"/    github_url/g' $FILE
sed -i 's/^    "commit_index"/    # "commit_index"/g' $FILE
sed -i 's/^    "name"/    name/g' $FILE

sed -i "s/,$//g" $FILE
sed -i "s/^  }$/  } }/g" $FILE
