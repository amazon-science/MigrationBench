FILE00=java__lite_20250121.pbtxt
FILE01=java__lite_iter_gt_3_20250127.pbtxt
FILE02=java__lite_iter_gt_3_fast_20250127.pbtxt
FILE03=java__lite_iter_gt_3_fast_v2_20250128.pbtxt

set -ex

grep partition_repos java__lite_* | sort
echo ""

diff $FILE00 $FILE01 | grep "^>"
diff $FILE01 $FILE02 | grep "^<" | wc

diff $FILE01 $FILE02 | grep "^>"
diff $FILE01 $FILE02 | grep "^<" | wc

diff $FILE02 $FILE03 | grep "^>"
diff $FILE02 $FILE03 | grep "^<" | wc
